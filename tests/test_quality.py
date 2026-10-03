import unittest

import pandas as pd

from flight_tracer.quality import data_quality, quality_notes


def trace(minutes, leg_id=1, **extra):
    n = len(minutes)
    base = pd.Timestamp("2026-09-16T00:00:00Z")
    return pd.DataFrame({
        "point_time_utc": [base + pd.Timedelta(minutes=m) for m in minutes],
        "icao": ["abc123"] * n, "leg_id": [leg_id] * n,
        "altitude": [1000.0] * n, "ground_speed": [90.0] * n,
        "is_stale": [False] * n, "position_source": ["adsb_icao"] * n,
        "leg_detection": ["archive_flags"] * n, "call_sign": ["N1"] * n,
        "registration": ["N1"] * n, "model": ["R44"] * n, "desc": ["ROBINSON"] * n, "owner_op": ["ACME"] * n,
        **extra,
    })


class TestDataQuality(unittest.TestCase):
    def test_clean_trace_has_no_notes(self):
        q = data_quality(trace([0, 1, 2, 3]))
        self.assertEqual((q["gap_count"], q["coverage_pct"], q["missing_metadata"]), (0, 100.0, []))
        self.assertEqual(quality_notes(q), [])

    def test_gap_threshold_is_strictly_greater_than(self):
        self.assertEqual(data_quality(trace([0, 5, 6]))["gap_count"], 0)
        q = data_quality(trace([0, 1, 11, 12]))
        self.assertEqual((q["gap_count"], q["longest_gap_minutes"], q["gap_minutes_total"]), (1, 10.0, 10.0))
        self.assertEqual(q["coverage_pct"], 16.7)
        self.assertEqual(data_quality(trace([0, 1, 11, 12]), gap_minutes=15)["gap_count"], 0)

    def test_time_between_legs_is_not_a_gap(self):
        gdf = pd.concat([trace([0, 1]), trace([120, 121], leg_id=2)], ignore_index=True)
        self.assertEqual(data_quality(gdf)["gap_count"], 0)

    def test_stale_mlat_and_missing_fields(self):
        gdf = trace([0, 1, 2, 3], is_stale=[True, False, False, False],
                    position_source=["mlat", "adsb_icao", "adsb_icao", "adsb_icao"])
        gdf["registration"] = None
        gdf["call_sign"] = "UNKNOWN"
        gdf.loc[0, "altitude"] = None
        q = data_quality(gdf)
        self.assertEqual(q["stale_positions"], {"count": 1, "pct": 25.0})
        self.assertEqual(q["mlat_positions"]["count"], 1)
        self.assertEqual(q["missing_metadata"], ["registration", "call_sign"])
        self.assertEqual(q["missing_values"], {"altitude": 1, "ground_speed": 0})

    def test_leg_boundary_provenance_in_notes(self):
        notes = quality_notes(data_quality(trace([0, 1], leg_detection=["unmarked"] * 2)))
        self.assertIn("leg boundaries unavailable (no archive flags)", notes)
        notes = quality_notes(data_quality(trace([0, 1], leg_detection=["inferred_ground_stop"] * 2)))
        self.assertIn("leg boundaries inferred from ground reports (estimates)", notes)

    def test_empty(self):
        self.assertEqual(data_quality(trace([])), {})


if __name__ == "__main__":
    unittest.main()
