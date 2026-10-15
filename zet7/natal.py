"""Натальная карта: планеты, узлы, Лилит, Хирон, доп. точки, дома, углы."""
from __future__ import annotations

import math
import os

import swisseph as swe

from .aspects import find_aspects
from .config import SIGNS, Config
from .timeconv import InputError, format_offset, parse_input

BODIES = {
    "sun": swe.SUN, "moon": swe.MOON, "mercury": swe.MERCURY, "venus": swe.VENUS,
    "mars": swe.MARS, "jupiter": swe.JUPITER, "saturn": swe.SATURN, "uranus": swe.URANUS,
    "neptune": swe.NEPTUNE, "pluto": swe.PLUTO, "chiron": swe.CHIRON,
    "ceres": swe.CERES, "pallas": swe.PALLAS, "juno": swe.JUNO, "vesta": swe.VESTA,
    "selena": 56,       # SE_WHITE_MOON (seorbel.txt)
    "proserpina": 57,   # SE_PROSERPINA (seorbel.txt)
}
NODE_IDS = {"true": swe.TRUE_NODE, "mean": swe.MEAN_NODE}
LILITH_IDS = {"mean": swe.MEAN_APOG, "true": swe.OSCU_APOG, "osc": swe.OSCU_APOG, "intp": swe.INTP_APOG}

_state = {"ephe_path": None}


def norm(x: float) -> float:
    x %= 360.0
    return 0.0 if x >= 360.0 else x


def sign_of(lon: float) -> tuple[str, float]:
    i = int(lon // 30) % 12
    return SIGNS[i], lon - 30.0 * (lon // 30)


def house_of(lon: float, cusps: list[float]) -> int:
    for i in range(12):
        a, b = cusps[i], cusps[(i + 1) % 12]
        if norm(lon - a) < norm(b - a) or norm(b - a) == 0.0 and lon == a:
            return i + 1
    return 12


def _setup(cfg: Config, lat: float, lon: float, alt: float) -> int:
    path = cfg.ephe_path if os.path.isdir(cfg.ephe_path) else ""
    if _state["ephe_path"] != path:
        swe.set_ephe_path(path or None)
        _state["ephe_path"] = path
    flags = swe.FLG_SPEED | (swe.FLG_SWIEPH if cfg.ephe_mode == "swiss" else swe.FLG_MOSEPH)
    if cfg.topocentric:
        swe.set_topo(lon, lat, alt or cfg.altitude_m)
        flags |= swe.FLG_TOPOCTR
    if cfg.zodiac == "sidereal":
        swe.set_sid_mode(cfg.ayanamsa)
        flags |= swe.FLG_SIDEREAL
    return flags


WGS84_F = 1.0 / 298.257223563
J2000 = 2451545.0


def _proserpina(cfg: Config, jd_tt: float, flags: int) -> float:
    """Геоцентрическая долгота Прозерпины ZET: круговая гелиоцентрическая орбита радиуса a."""
    xx, _ = swe.calc(jd_tt, swe.SUN, flags)
    e = math.radians(xx[0] + 180.0)
    L = math.radians(cfg.proserpina_l0 + cfg.proserpina_n * (jd_tt - J2000))
    x = cfg.proserpina_a * math.cos(L) - xx[2] * math.cos(e)
    y = cfg.proserpina_a * math.sin(L) - xx[2] * math.sin(e)
    return norm(math.degrees(math.atan2(y, x)))


def geocentric_lat(lat: float) -> float:
    if abs(lat) >= 90.0:
        return lat
    return math.degrees(math.atan((1.0 - WGS84_F) ** 2 * math.tan(math.radians(lat))))


def _houses(jd_ut: float, lat: float, lon: float, cfg: Config):
    hflags = swe.FLG_SIDEREAL if cfg.zodiac == "sidereal" else 0
    if cfg.house_lat == "geocentric":
        lat = geocentric_lat(lat)
    cusps, ascmc = swe.houses_ex(jd_ut, lat, lon, cfg.house_system.encode(), hflags)
    return [norm(c) for c in cusps[:12]], ascmc


def compute(data: dict, cfg: Config | None = None, with_aspects: bool = True) -> dict:
    cfg = cfg or Config()
    try:
        cfg.validate()
    except ValueError as e:
        raise InputError("config", str(e)) from None
    inp = parse_input(data)
    jd_ut, lat, lon = inp["jd_ut"], inp["lat"], inp["lon"]
    flags = _setup(cfg, lat, lon, inp["alt"])
    ephflag = swe.FLG_SWIEPH if cfg.ephe_mode == "swiss" else swe.FLG_MOSEPH
    dt_s = swe.deltat_ex(jd_ut, ephflag) * 86400.0 if cfg.delta_t == "auto" else float(cfg.delta_t)
    jd_tt = jd_ut + dt_s / 86400.0

    raw: dict[str, tuple[float, float, float]] = {}
    missing: list[str] = []
    used = set()

    def calc(name: str, body: int):
        try:
            xx, ret = swe.calc(jd_tt, body, flags)
        except swe.Error:
            missing.append(name)
            return
        if body in BODIES.values() and body not in (56, 57):
            used.add("moshier" if ret & swe.FLG_MOSEPH else "swiss")
        raw[name] = (norm(xx[0]), xx[1], xx[3])

    wanted = set(cfg.points)
    zet_models = {n for n in ("selena", "proserpina") if getattr(cfg, n) == "zet"}
    for name, body in BODIES.items():
        if name in wanted and name not in zet_models:
            calc(name, body)
    ayan = swe.get_ayanamsa_ut(jd_ut) if cfg.zodiac == "sidereal" else 0.0
    if "selena" in wanted and "selena" in zet_models:
        raw["selena"] = (norm(cfg.selena_l0 + cfg.selena_n * (jd_ut - J2000) - ayan), 0.0, cfg.selena_n)
    if "proserpina" in wanted and "proserpina" in zet_models:
        f0 = flags & ~(swe.FLG_TOPOCTR | swe.FLG_SIDEREAL)
        l0 = _proserpina(cfg, jd_tt - 0.5, f0)
        l1 = _proserpina(cfg, jd_tt + 0.5, f0)
        lp = _proserpina(cfg, jd_tt, f0)
        raw["proserpina"] = (norm(lp - ayan), 0.0, (l1 - l0 + 180.0) % 360.0 - 180.0)
    if wanted & {"node", "south_node"}:
        calc("node", NODE_IDS[cfg.node])
        if "node" in raw:
            l, b, v = raw["node"]
            raw["south_node"] = (norm(l + 180.0), -b, v)
            if "node" not in wanted:
                del raw["node"]
    if "lilith" in wanted:
        calc("lilith", LILITH_IDS[cfg.lilith])

    try:
        cusps, ascmc = _houses(jd_ut, lat, lon, cfg)
    except swe.Error as e:
        raise InputError("lat", f"houses failed: {e}") from None
    asc, mc = norm(ascmc[0]), norm(ascmc[1])
    angles = {"asc": asc, "mc": mc, "dsc": norm(asc + 180.0), "ic": norm(mc + 180.0),
              "vertex": norm(ascmc[3])}

    if "fortune" in wanted and "sun" in raw and "moon" in raw:
        sun, moon = raw["sun"][0], raw["moon"][0]
        day = norm(sun - angles["dsc"]) < 180.0
        f = asc + moon - sun if (day or cfg.fortune == "day") else asc + sun - moon
        raw["fortune"] = (norm(f), 0.0, 0.0)

    planets = {}
    for name in cfg.points:
        if name not in raw:
            continue
        l, b, v = raw[name]
        sgn, deg = sign_of(l)
        planets[name] = {"lon": round(l, 4), "lat": round(b, 4), "sign": sgn, "deg": round(deg, 4),
                         "house": house_of(l, cusps), "speed": round(v, 6), "retro": v < 0}

    result = {
        "v": "1",
        "meta": {
            "ephe": "mixed" if len(used) > 1 else (used.pop() if used else cfg.ephe_mode),
            "house_system": cfg.house_system, "house_lat": cfg.house_lat, "node": cfg.node, "lilith": cfg.lilith,
            "topocentric": cfg.topocentric, "zodiac": cfg.zodiac,
            "dt_s": round(dt_s, 3),
            "ut": inp["ut"].strftime("%Y-%m-%dT%H:%M:%S") + "Z",
            "utc_offset": format_offset(inp["offset_h"]),
            "jd_ut": round(jd_ut, 6),
        },
        "planets": planets,
        "angles": {k: round(v, 4) for k, v in angles.items()},
        "houses": [round(c, 4) for c in cusps],
        "aspects": [],
    }
    if missing:
        result["meta"]["missing"] = sorted(set(missing))
    if with_aspects:
        step = 1.0 / 1440.0
        _, a2 = _houses(jd_ut + step, lat, lon, cfg)
        ang_speed = {"asc": ((a2[0] - asc + 180.0) % 360.0 - 180.0) / step,
                     "mc": ((a2[1] - mc + 180.0) % 360.0 - 180.0) / step}
        pts = {}
        for n in cfg.aspect_points:
            if n in raw:
                pts[n] = (raw[n][0], raw[n][2])
            elif n in angles:
                pts[n] = (angles[n], ang_speed.get(n, 0.0))
        result["aspects"] = find_aspects(pts, cfg)
    return result


def compact(result: dict) -> dict:
    return {
        "planets": {k: {"lon": p["lon"], "house": p["house"], "retro": p["retro"]}
                    for k, p in result["planets"].items()},
        "angles": result["angles"],
        "aspects": result["aspects"],
    }
