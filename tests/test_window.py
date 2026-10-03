import json
from unittest.mock import patch

import pandas as pd
import pytest
from click.testing import CliRunner

from flight_tracer import FlightTracer
from flight_tracer.cli import cli
from flight_tracer.core import TRACE_COLUMNS
from flight_tracer.window import parse_window, select_window


def raw_trace(altitudes=(100, 'ground', 'ground', 250), times=(0, 60, 1800, 1820)):
    rows = [[t, 33.66, -117.87, a, 0, 0, 0] for t, a in zip(times, altitudes)]
    df = pd.DataFrame(rows).reindex(columns=range(14))
    df.columns = TRACE_COLUMNS
    df['icao'] = 'a9a1ad'
    for key in ('registration', 'model', 'desc', 'owner_op'):
        df[key] = None
    df['point_time_utc'] = pd.Timestamp('2020-01-26T17:00Z') + pd.to_timedelta(df.seconds_after_timestamp, unit='s')
    return df


def test_timezones_inclusive_and_open_bounds():
    start, end = parse_window('2020-01-26T09:00', '2020-01-26T09:30', 'America/Los_Angeles')
    assert start == pd.Timestamp('2020-01-26T17:00Z')
    assert end == pd.Timestamp('2020-01-26T17:30Z')
    df = raw_trace()
    assert len(select_window(df, start, end)) == 3
    assert len(select_window(df, end, None)) == 2
    assert parse_window('2020-01-26T17:00Z', None, 'Asia/Tokyo')[0] == start
    assert parse_window('2020-01-26T09:00-08:00')[0] == start


@pytest.mark.parametrize('after,before,zone', [
    ('09:00', None, 'UTC'),
    ('2020-01-27T00:00', '2020-01-26T00:00', 'UTC'),
    ('2020-11-01T01:30', None, 'America/Los_Angeles'),
    ('2020-03-08T02:30', None, 'America/Los_Angeles'),
    ('2020-01-26T09:00', None, 'not-a-zone'),
])
def test_invalid_or_ambiguous_window(after, before, zone):
    with pytest.raises(Exception):
        parse_window(after, before, zone)


def test_ground_stop_inference_is_opt_in_and_preserves_flags():
    tracer = FlightTracer(aircraft_ids=['a9a1ad'])
    raw = raw_trace()
    assert tracer.process_flight_data(raw).leg_id.tolist() == [1, 1]
    result = tracer.process_flight_data(raw, infer_legs=True)
    assert result.leg_id.tolist() == [1, 2]
    assert result.leg_detection.unique().tolist() == ['inferred_ground_stop']
    assert tracer.summarize(result)['leg_detection'] == ['inferred_ground_stop']
    raw.loc[1, 'flags'] = 2
    flagged = tracer.process_flight_data(raw, infer_legs=True, filter_ground=False)
    assert flagged.leg_id.tolist() == [1, 2, 2, 2]
    assert flagged.leg_detection.unique().tolist() == ['archive_flags']


@pytest.mark.parametrize('altitudes,times,far', [
    ((100, -100, -100, 250), (0, 60, 1800, 1820), False),
    ((100, 100, 100, 250), (0, 60, 1800, 1820), False),
    ((100, 'ground', 'ground', 250), (0, 60, 120, 140), False),
    ((100, 'ground', 'ground', 250), (0, 60, 1800, 1820), True),
])
def test_no_inference_from_low_altitude_gap_short_stop_or_distant_points(altitudes, times, far):
    raw = raw_trace(altitudes, times)
    if far:
        raw.loc[2, 'lat'] = 40
    result = FlightTracer(aircraft_ids=['a9a1ad']).process_flight_data(raw, infer_legs=True)
    assert result.leg_id.nunique() == 1


def test_inference_separate_aircraft():
    a = raw_trace()
    b = raw_trace((100, 100, 100, 250)); b['icao'] = 'a40442'
    result = FlightTracer(aircraft_ids=['a9a1ad', 'a40442']).process_flight_data(pd.concat([a,b]), infer_legs=True)
    assert result[result.icao == 'a9a1ad'].leg_id.nunique() == 2
    assert result[result.icao == 'a40442'].leg_id.nunique() == 1


def test_cli_window_filters_exports_and_infers_utc_dates(tmp_path):
    with patch('flight_tracer.cli.FlightTracer.get_traces', return_value=raw_trace()) as fetch:
        result = CliRunner().invoke(cli, ['trace', '--icao', 'a9a1ad', '--after', '2020-01-26T09:30',
            '--before', '2020-01-26T09:31', '--window-timezone', 'America/Los_Angeles',
            '--infer-legs', '--no-plots', '--output', str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert str(fetch.call_args.args[0]) == '2020-01-26'
    csv = next(tmp_path.rglob('trace.csv'))
    points = pd.read_csv(csv)
    assert len(points) == 1
    assert points.leg_id.tolist() == [2]  # detection happened before trimming
    selection = json.loads((csv.parent / 'selection.json').read_text())
    assert selection['after_utc'] == '2020-01-26 17:30:00+00:00'
    assert '_window_' in csv.parent.name


def test_invalid_window_does_not_fetch():
    with patch('flight_tracer.cli.FlightTracer.get_traces') as fetch:
        result = CliRunner().invoke(cli, ['trace', '--icao', 'a9a1ad', '--after', '09:00'])
        assert result.exit_code != 0
        fetch.assert_not_called()


def test_empty_window_no_outputs(tmp_path):
    with patch('flight_tracer.cli.FlightTracer.get_traces', return_value=raw_trace()):
        result = CliRunner().invoke(cli, ['trace', '--icao', 'a9a1ad', '--after', '2020-01-27T00:00Z',
            '--no-plots', '--output', str(tmp_path)])
    assert result.exit_code != 0
    assert 'No points in the selected time window' in result.output
    assert list(tmp_path.iterdir()) == []
