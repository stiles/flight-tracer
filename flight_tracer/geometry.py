"""Geographic route geometry, including crossings of the antimeridian."""

from shapely.geometry import LineString, MultiLineString, Point


def route_geometry(points):
    """Split a WGS84 route at ±180°, keeping exported segments local.

    Interpolate the crossing latitude between recorded positions. This is
    a drawing boundary, not an additional observation or a new flight leg.
    """
    coords = [(point.x, point.y) for point in points]
    if len(coords) == 1:
        return points[0]
    parts = []
    current = [coords[0]]
    for (x1, y1), (x2, y2) in zip(coords, coords[1:]):
        if abs(x2 - x1) > 180:
            adjusted = x2 + (360 if x2 < x1 else -360)
            boundary = 180 if x1 > 0 else -180
            fraction = (boundary - x1) / (adjusted - x1) if adjusted != x1 else 0
            latitude = y1 + fraction * (y2 - y1)
            current.append((boundary, latitude))
            parts.append(current)
            current = [(-boundary, latitude)]
        current.append((x2, y2))
    parts.append(current)
    lines = [LineString(part) for part in parts if len(set(part)) > 1]
    if not lines:
        return Point(coords[0])
    return lines[0] if len(lines) == 1 else MultiLineString(lines)
