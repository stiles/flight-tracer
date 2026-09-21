import unittest
from datetime import date

import pandas as pd

from flight_tracer import FlightTracer, parse_adsbx_url
from flight_tracer.identify import resolve_timezone


class TestGenerateUrls(unittest.TestCase):
    def test_generate_urls_single_day(self):
        tracer = FlightTracer(aircraft_ids=["0d086e"])
        urls = tracer.generate_urls(date(2025, 1, 1), date(2025, 1, 1))
        self.assertEqual(len(urls), 1)
        expected_url = "https://globe.adsbexchange.com/globe_history/2025/01/01/traces/6e/trace_full_0d086e.json"
        self.assertEqual(urls[0][0], expected_url)

    def test_generate_urls_multiple_days(self):
        tracer = FlightTracer(aircraft_ids=["0d086e"])
        urls = tracer.generate_urls(date(2025, 1, 1), date(2025, 1, 2))
        self.assertEqual(len(urls), 2)

    def test_generate_urls_recent(self):
        tracer = FlightTracer(aircraft_ids=["a40442"])
        urls = tracer.generate_urls(None, None, recent=True)
        self.assertEqual(len(urls), 1)
        self.assertIn("trace_full_a40442.json", urls[0][0])
        self.assertIn("/data/traces/", urls[0][0])


class TestParseAdsbxUrl(unittest.TestCase):
    def test_parses_icao_and_replay_date(self):
        url = "https://globe.adsbexchange.com/?replay=2026-09-16-01:58&icao=a40442&lat=34.251&lon=-118.614&zoom=7.0"
        result = parse_adsbx_url(url)
        self.assertEqual(result["icao"], "a40442")
        self.assertEqual(result["date"].isoformat(), "2026-09-16")
        self.assertAlmostEqual(result["lat"], 34.251)
        self.assertAlmostEqual(result["lon"], -118.614)

    def test_parses_icao_without_replay(self):
        url = "https://globe.adsbexchange.com/?icao=a40442"
        result = parse_adsbx_url(url)
        self.assertEqual(result["icao"], "a40442")
        self.assertIsNone(result["date"])

    def test_raises_without_icao(self):
        with self.assertRaises(ValueError):
            parse_adsbx_url("https://globe.adsbexchange.com/?lat=34.2")


class TestProcessFlightData(unittest.TestCase):
    def _raw_row(self, seconds, flags, altitude=1000, lat=34.0, lon=-118.0, details=None):
        return {
            "seconds_after_timestamp": seconds,
            "lat": lat,
            "lon": lon,
            "altitude": altitude,
            "ground_speed": 100.0,
            "track": 90.0,
            "flags": flags,
            "vertical_rate": 0.0,
            "aircraft_details": details,
            "position_source": "adsb_icao",
            "geom_altitude": None,
            "geom_vertical_rate": None,
            "indicated_airspeed": None,
            "roll": None,
            "registration": "N358TV",
            "model": "AS350",
            "desc": "Eurocopter AS350",
            "owner_op": None,
            "icao": "a40442",
        }

    def _raw_df(self, rows):
        df = pd.DataFrame(rows)
        base_time = pd.Timestamp("2026-09-16T01:58:00Z")
        df["point_time_utc"] = base_time + pd.to_timedelta(df["seconds_after_timestamp"], unit="s")
        return df

    def test_call_sign_fills_within_a_leg_not_across_leg_boundaries(self):
        # The callsign broadcast doesn't always arrive in a leg's first few
        # messages. A leg's leading points should pick up its own later
        # callsign (via backfill), not inherit the previous leg's, which
        # would otherwise split one physical leg into two flight_leg groups.
        rows = [
            self._raw_row(0, flags=0, details={"flight": "VOC4071"}),
            self._raw_row(10, flags=0),  # still leg 1, VOC4071
            self._raw_row(20, flags=2),  # new leg -- callsign not yet broadcast
            self._raw_row(30, flags=0),  # still no callsign broadcast this leg
            self._raw_row(40, flags=0, details={"flight": "VOC4062"}),  # now it arrives
            self._raw_row(50, flags=0),
        ]
        df = self._raw_df(rows)
        tracer = FlightTracer(aircraft_ids=["a40442"])
        gdf = tracer.process_flight_data(df, filter_ground=False)

        leg2 = gdf[gdf["leg_id"] == 2]
        self.assertTrue((leg2["call_sign"] == "VOC4062").all())
        self.assertEqual(gdf["flight_leg"].nunique(), 2)

    def test_flags_drive_leg_boundaries_not_a_time_gap(self):
        rows = [
            self._raw_row(0, flags=0, details={"flight": "N358TV"}),
            self._raw_row(10, flags=0),
            self._raw_row(20, flags=2),  # ADS-B Exchange's own new-leg flag
            self._raw_row(30, flags=0),
        ]
        df = self._raw_df(rows)
        tracer = FlightTracer(aircraft_ids=["a40442"])
        gdf = tracer.process_flight_data(df, filter_ground=False)

        self.assertListEqual(gdf["leg_id"].tolist(), [1, 1, 2, 2])
        # Leg 1 has its own callsign; leg 2 broadcasts none in this fixture
        # and correctly falls back to UNKNOWN rather than inheriting leg 1's.
        self.assertTrue((gdf.loc[gdf["leg_id"] == 1, "call_sign"] == "N358TV").all())
        self.assertTrue((gdf.loc[gdf["leg_id"] == 2, "call_sign"] == "UNKNOWN").all())

    def test_filters_ground_points(self):
        rows = [
            self._raw_row(0, flags=0, altitude="ground"),
            self._raw_row(10, flags=0, altitude=1500),
        ]
        df = self._raw_df(rows)
        tracer = FlightTracer(aircraft_ids=["a40442"])
        gdf = tracer.process_flight_data(df, filter_ground=True)
        self.assertEqual(len(gdf), 1)
        self.assertEqual(gdf.iloc[0]["altitude"], 1500)

    def test_summarize_num_legs_counts_distinct_legs_not_max_id(self):
        # A gdf filtered down to a single leg keeps that leg's original
        # leg_id (e.g. 3), which max() would misreport as "3 legs" for what
        # is actually one flight.
        rows = [
            self._raw_row(0, flags=0),
            self._raw_row(10, flags=0),
        ]
        df = self._raw_df(rows)
        tracer = FlightTracer(aircraft_ids=["a40442"])
        gdf = tracer.process_flight_data(df, filter_ground=False)
        gdf["leg_id"] = 3  # simulate a leg filtered out of a longer, multi-leg trace
        gdf["flight_leg"] = "N358TV_leg3"

        summary = tracer.summarize(gdf)
        self.assertEqual(summary["num_legs"], 1)
        self.assertIn("1 leg)", tracer.headline_for(summary))
        self.assertNotIn("3 legs", tracer.headline_for(summary))

    def test_defaults_to_utc_only_no_local_column(self):
        rows = [self._raw_row(0, flags=0)]
        df = self._raw_df(rows)
        tracer = FlightTracer(aircraft_ids=["a40442"])
        gdf = tracer.process_flight_data(df, filter_ground=False)
        self.assertIn("point_time_utc", gdf.columns)
        self.assertNotIn("point_time_local", gdf.columns)

        summary = tracer.summarize(gdf)
        self.assertIn("first_contact_utc", summary)
        self.assertNotIn("first_contact_local", summary)
        self.assertIn("UTC", tracer.headline_for(summary))
        self.assertNotIn("None", tracer.headline_for(summary))

    def test_timezone_adds_local_alongside_utc_never_instead_of(self):
        rows = [self._raw_row(0, flags=0)]
        df = self._raw_df(rows)
        tracer = FlightTracer(aircraft_ids=["a40442"])
        gdf = tracer.process_flight_data(df, filter_ground=False, timezone="America/Los_Angeles")
        self.assertIn("point_time_utc", gdf.columns)
        self.assertIn("point_time_local", gdf.columns)
        self.assertEqual(str(gdf["point_time_local"].dt.tz), "America/Los_Angeles")

        summary = tracer.summarize(gdf, timezone="America/Los_Angeles")
        self.assertIn("first_contact_utc", summary)
        self.assertIn("first_contact_local", summary)
        headline = tracer.headline_for(summary)
        self.assertIn("UTC:", headline)  # local is never shown without UTC alongside it


class TestResolveTimezone(unittest.TestCase):
    def test_none_and_utc_mean_utc_only(self):
        self.assertIsNone(resolve_timezone(None))
        self.assertIsNone(resolve_timezone(""))
        self.assertIsNone(resolve_timezone("UTC"))

    def test_named_zone_passes_through(self):
        self.assertEqual(resolve_timezone("America/New_York"), "America/New_York")

    def test_auto_infers_from_lat_lon(self):
        # The a40442 helicopter's first contact point, in the San Fernando Valley.
        zone = resolve_timezone("auto", lat=34.257339, lon=-118.410420)
        self.assertEqual(zone, "America/Los_Angeles")

    def test_auto_without_coordinates_raises(self):
        with self.assertRaises(ValueError):
            resolve_timezone("auto")


if __name__ == "__main__":
    unittest.main()
