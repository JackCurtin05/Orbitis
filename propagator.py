"""
propagator.py
-------------
Uses the SGP4 algorithm to propagate orbital positions from TLE data.

SGP4 (Simplified General Perturbations 4) is the standard model used by
NORAD / US Space Command to track every object in Earth orbit. It accounts
for atmospheric drag, Earth's oblateness, solar/lunar gravity, and more.

Output positions are in Earth-Centered Earth-Fixed (ECEF) coordinates,
then converted to latitude/longitude/altitude for plotting.
"""

import math
import datetime
from typing import Optional
from sgp4.api import Satrec, jday


# Earth's equatorial radius in km (WGS-84)
EARTH_RADIUS_KM = 6378.137


def propagate_objects(
    tle_list: list[dict],
    at_time: Optional[datetime.datetime] = None,
) -> list[dict]:
    """
    Propagate a list of TLE objects to a given time and return their
    position as lat/lon/alt plus metadata.

    Args:
        tle_list:  List of dicts with 'name', 'line1', 'line2' (and optionally 'category')
        at_time:   UTC datetime to propagate to. Defaults to now.

    Returns:
        List of dicts with keys:
            name, category, lat, lon, alt_km, x, y, z, error
    """
    if at_time is None:
        at_time = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

    # Convert Python datetime → Julian date (required by sgp4)
    jd, fr = _datetime_to_jd(at_time)

    results = []
    for obj in tle_list:
        result = _propagate_one(obj, jd, fr)
        results.append(result)

    valid = [r for r in results if not r["error"]]
    print(f"[propagator] Propagated {len(valid)}/{len(results)} objects successfully at {at_time.isoformat()}Z")
    return results


def _propagate_one(obj: dict, jd: float, fr: float) -> dict:
    """
    Propagate a single TLE object. Returns a result dict with position data
    or an error flag if SGP4 fails (e.g. decayed orbit).
    """
    base = {
        "name":     obj.get("name", "Unknown"),
        "category": obj.get("category", "unknown"),
        "line1":    obj.get("line1", ""),
        "line2":    obj.get("line2", ""),
        "error":    False,
    }

    try:
        satellite = Satrec.twoline2rv(obj["line1"], obj["line2"])
        e, r, v = satellite.sgp4(jd, fr)

        # e == 0 means success; nonzero codes mean the satellite has decayed
        # or the TLE is invalid
        if e != 0:
            base["error"] = True
            base["error_code"] = e
            return base

        # r is ECI position in km: [x, y, z]
        x, y, z = r

        # Convert ECI → geodetic lat/lon/alt
        lat, lon, alt_km = _eci_to_geodetic(x, y, z, jd + fr)

        base.update({
            "x":      x,
            "y":      y,
            "z":      z,
            "lat":    lat,
            "lon":    lon,
            "alt_km": alt_km,
        })

    except Exception as exc:
        base["error"] = True
        base["error_msg"] = str(exc)

    return base


def _datetime_to_jd(dt: datetime.datetime) -> tuple[float, float]:
    """Convert a UTC datetime to Julian date split into integer + fraction."""
    return jday(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second + dt.microsecond / 1e6)


def _eci_to_geodetic(x: float, y: float, z: float, jd_full: float) -> tuple[float, float, float]:
    """
    Convert Earth-Centered Inertial (ECI) coordinates to geodetic
    latitude, longitude (degrees), and altitude (km).

    Uses a simple iterative algorithm (Bowring's method approximation).
    Accurate to within a few meters for LEO objects.

    Args:
        x, y, z:  ECI position in km
        jd_full:  Full Julian date (integer + fraction combined)

    Returns:
        (latitude_deg, longitude_deg, altitude_km)
    """
    # Greenwich Mean Sidereal Time (GMST) — rotates ECI → ECEF
    gmst = _gmst_from_jd(jd_full)

    # Rotate ECI → ECEF by GMST angle
    lon_rad = math.atan2(y, x) - gmst
    # Normalize longitude to [-π, π]
    lon_rad = (lon_rad + math.pi) % (2 * math.pi) - math.pi

    # Geocentric latitude and range
    rxy = math.sqrt(x**2 + y**2)
    lat_geocentric = math.atan2(z, rxy)

    # Iterative conversion to geodetic latitude (accounts for Earth's oblateness)
    # WGS-84 flattening
    f = 1 / 298.257223563
    e2 = 2 * f - f**2

    lat_rad = lat_geocentric
    for _ in range(5):
        N = EARTH_RADIUS_KM / math.sqrt(1 - e2 * math.sin(lat_rad)**2)
        lat_rad = math.atan2(z + e2 * N * math.sin(lat_rad), rxy)

    # Altitude above ellipsoid
    N = EARTH_RADIUS_KM / math.sqrt(1 - e2 * math.sin(lat_rad)**2)
    alt_km = rxy / math.cos(lat_rad) - N if abs(math.cos(lat_rad)) > 1e-10 else abs(z) - EARTH_RADIUS_KM * (1 - e2)

    return (
        math.degrees(lat_rad),
        math.degrees(lon_rad),
        alt_km,
    )


def _gmst_from_jd(jd: float) -> float:
    """
    Compute Greenwich Mean Sidereal Time (GMST) in radians from a Julian date.
    Based on the IAU formula, accurate to ~0.1 arc-second.
    """
    # Julian centuries from J2000.0
    T = (jd - 2451545.0) / 36525.0
    # GMST in seconds at 0h UT
    theta = (
        67310.54841
        + (876600 * 3600 + 8640184.812866) * T
        + 0.093104 * T**2
        - 6.2e-6 * T**3
    )
    # Convert to radians, normalize to [0, 2π]
    gmst_rad = math.radians(theta / 240.0) % (2 * math.pi)
    return gmst_rad


def altitude_band(alt_km: float) -> str:
    """Classify an altitude into an orbital regime string."""
    if alt_km < 0:
        return "decayed"
    elif alt_km < 2000:
        return "LEO"     # Low Earth Orbit
    elif alt_km < 35786:
        return "MEO"     # Medium Earth Orbit
    elif alt_km < 35887:
        return "GEO"     # Geostationary
    else:
        return "HEO"     # Highly Elliptical / beyond GEO


if __name__ == "__main__":
    # Quick smoke test with a hardcoded ISS TLE
    test_tles = [
        {
            "name": "ISS (ZARYA)",
            "line1": "1 25544U 98067A   24001.50000000  .00016717  00000-0  10270-3 0  9993",
            "line2": "2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.50377579 00000",
            "category": "stations",
        }
    ]
    results = propagate_objects(test_tles)
    for r in results:
        if not r["error"]:
            print(f"{r['name']}: lat={r['lat']:.2f}° lon={r['lon']:.2f}° alt={r['alt_km']:.1f} km [{altitude_band(r['alt_km'])}]")
        else:
            print(f"{r['name']}: ERROR ({r.get('error_code', r.get('error_msg', '?'))})")
