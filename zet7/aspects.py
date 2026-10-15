"""Аспекты внутри карты; орбисы и набор аспектов из Config."""
from __future__ import annotations

LUMINARIES = ("sun", "moon")
_EPS_DAYS = 1.0 / 1440.0


def _sep(a: float, b: float) -> float:
    d = (b - a) % 360.0
    return min(d, 360.0 - d)


def find_aspects(points: dict[str, tuple[float, float]], cfg) -> list[dict]:
    """points: name -> (lon, speed °/day). Порядок пар — порядок cfg.aspect_points."""
    names = [n for n in cfg.aspect_points if n in points]
    out = []
    for i, a in enumerate(names):
        la, va = points[a]
        for b in names[i + 1:]:
            if {a, b} <= {"asc", "mc"}:
                continue
            lb, vb = points[b]
            sep = _sep(la, lb)
            bonus = cfg.luminary_orb_bonus if (a in LUMINARIES or b in LUMINARIES) else 0.0
            best = None
            for typ, ang in cfg.aspects.items():
                orb = abs(sep - ang)
                if orb <= cfg.orbs.get(typ, 0.0) + bonus and (best is None or orb < best[1]):
                    best = (typ, orb, ang)
            if best is None:
                continue
            typ, orb, ang = best
            sep2 = _sep(la + va * _EPS_DAYS, lb + vb * _EPS_DAYS)
            out.append({"a": a, "b": b, "type": typ, "orb": round(orb, 4),
                        "applying": abs(sep2 - ang) < orb})
    return out
