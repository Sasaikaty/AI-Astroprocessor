"""Синастрия: аспекты A↔B, оверлеи домов, композит (мидпоинты), баланс стихий, digest."""
from __future__ import annotations

from . import scoring as S
from .natal import compute, house_of, norm
from .timeconv import InputError

_EPS = 1.0 / 1440.0
COMP_SHORT = ("su", "mo", "as", "mc")
BAL_PTS = ("su", "mo", "me", "ve", "ma", "ju", "sa", "ur", "ne", "pl", "as")


def points(res: dict, cfg) -> dict[str, tuple[float, float]]:
    """Натальный результат -> {код: (lon, speed)} по cfg.aspect_points."""
    pts = {}
    for n in cfg.aspect_points:
        c = S.CODES.get(n)
        if c is None:
            continue
        if n in res["planets"]:
            p = res["planets"][n]
            pts[c] = (p["lon"], p["speed"])
        elif n in res["angles"]:
            pts[c] = (res["angles"][n], 0.0)
    return pts


def cross(pa: dict, pb: dict, cfg, scale: float = 1.0) -> list[list]:
    """Аспекты только между A и B: [a, b, тип, орб, applying, w], по убыванию w."""
    asp = S.aspect_set(cfg, scale)
    bonus = cfg.luminary_orb_bonus * scale
    rows = []
    for a in sorted(pa, key=S.ORDER.get):
        la, va = pa[a]
        for b in sorted(pb, key=S.ORDER.get):
            lb, vb = pb[b]
            s = S.sep(la, lb)
            lum = a in S.LUM or b in S.LUM
            best = None
            for code, ang, orb in asp:
                mo = orb + (bonus if lum else 0.0)
                o = abs(s - ang)
                if o <= mo and (best is None or o < best[1]):
                    best = (code, o, mo, ang)
            if best is None:
                continue
            code, o, mo, ang = best
            app = abs(S.sep(la + va * _EPS, lb + vb * _EPS) - ang) < o
            rows.append([a, b, code, round(o, 2), int(app), round(S.weight(code, a, b, o, mo), 2)])
    rows.sort(key=lambda r: (-r[5], r[3], S.ORDER[r[0]], S.ORDER[r[1]], r[2]))
    return rows


def rid(r) -> str:
    return f"{r[0]}-{r[1]}-{r[2]}"


def midpoint(a: float, b: float) -> float:
    return norm(a + S.wrap(b - a) / 2.0)


def _overlay(pa: dict, cusps: list[float]) -> dict[str, int]:
    return {c: house_of(l, cusps) for c, (l, _) in pa.items() if c not in ("as", "mc")}


def _natal(data: dict, cfg, tag: str) -> dict:
    if not isinstance(data, dict):
        raise InputError(tag, "input must be a JSON object")
    try:
        return compute(data, cfg, with_aspects=False)
    except InputError as e:
        raise InputError(f"{tag}.{e.field}", e.message) from None


def synastry(da: dict, db: dict, cfg, top: int = 15, scale: float = 1.0, full: bool = False) -> dict:
    ra, rb = _natal(da, cfg, "a"), _natal(db, cfg, "b")
    pa, pb = points(ra, cfg), points(rb, cfg)
    rows = cross(pa, pb, cfg, scale)

    harm = [r for r in rows if not S.is_tense(r[2], r[0], r[1])]
    tense = [r for r in rows if S.is_tense(r[2], r[0], r[1])]
    h, t = sum(r[5] for r in harm), sum(r[5] for r in tense)
    themes = {k: S.saturate(sum(r[5] for r in rows if r[0] in s or r[1] in s)) for k, s in S.THEMES.items()}
    themes["conflict"] = S.saturate(t)

    keys = sorted(set(pa) & set(pb), key=S.ORDER.get) if full else [k for k in COMP_SHORT if k in pa and k in pb]
    return {
        "v": "1", "mode": "syn",
        "digest": {"score": int(round(100.0 * h / (h + t))) if h + t > 0 else 50,
                   "harm": [rid(r) for r in harm[:5]], "tense": [rid(r) for r in tense[:5]],
                   "themes": themes, "n": len(rows)},
        "asp": rows if full else rows[:top],
        "ovl": {"AinB": _overlay(pa, rb["houses"]), "BinA": _overlay(pb, ra["houses"])},
        "comp": {k: round(midpoint(pa[k][0], pb[k][0]), 2) for k in keys},
        "bal": {"A": S.elements(pa[k][0] for k in BAL_PTS if k in pa),
                "B": S.elements(pb[k][0] for k in BAL_PTS if k in pb)},
        "meta": {"names": [da.get("name", "A"), db.get("name", "B")],
                 "ut": [ra["meta"]["ut"], rb["meta"]["ut"]]},
    }
