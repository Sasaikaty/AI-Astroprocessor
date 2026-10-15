"""Единый словарь кодов, весов и орбисов для natal-digest, synastry и transits."""
from __future__ import annotations

import math

CODES = {"sun": "su", "moon": "mo", "mercury": "me", "venus": "ve", "mars": "ma", "jupiter": "ju",
         "saturn": "sa", "uranus": "ur", "neptune": "ne", "pluto": "pl", "node": "no", "chiron": "ch",
         "lilith": "li", "asc": "as", "mc": "mc"}
ORDER = {c: i for i, c in enumerate(CODES.values())}
ASP_CODES = {"conjunction": "cj", "sextile": "sx", "square": "sq", "trine": "tr",
             "quincunx": "qc", "opposition": "op"}
SIGN_CODES = ("ar", "ta", "ge", "cn", "le", "vi", "li", "sc", "sg", "cp", "aq", "pi")
LUM = ("su", "mo")

# Аспекты сверх config.aspects (только синастрия): код -> (угол, орбис)
EXTRA_ASPECTS = {"qc": (150.0, 2.0)}

ASP_W = {"cj": 1.0, "op": 0.9, "sq": 0.85, "tr": 0.8, "sx": 0.55, "qc": 0.4}
TENSE = {"sq", "op", "qc"}
MALEFIC = {"ma", "sa", "ur", "pl"}

# Важность точки карты (натальная точка / тело в синастрии)
POINT_W = {"su": 1.0, "mo": 1.0, "as": 0.9, "mc": 0.8, "ve": 0.8, "ma": 0.75, "me": 0.6,
           "ju": 0.6, "sa": 0.65, "ur": 0.4, "ne": 0.4, "pl": 0.45, "no": 0.5, "ch": 0.35, "li": 0.3}
# Важность транзитного тела (медленные выше)
TRANSIT_W = {"pl": 1.0, "ne": 0.95, "ur": 0.9, "sa": 0.85, "ju": 0.7, "ch": 0.6, "no": 0.6,
             "ma": 0.5, "su": 0.4, "ve": 0.35, "me": 0.3, "mo": 0.15}
# Орбисы транзитов, ° (узкие для быстрых, шире для медленных) × коэффициент аспекта
TRANSIT_ORB = {"mo": 1.0, "su": 1.5, "me": 1.0, "ve": 1.0, "ma": 1.5, "ju": 2.0, "sa": 2.0,
               "ur": 2.0, "ne": 2.0, "pl": 2.0, "no": 1.5, "ch": 1.5}
TRANSIT_ASP = {"cj": (0.0, 1.0), "sx": (60.0, 0.75), "sq": (90.0, 1.0), "tr": (120.0, 1.0), "op": (180.0, 1.0)}

THEMES = {"emo": {"mo", "ve", "ne"}, "mind": {"me", "ju"}, "phys": {"ma", "ve", "as"},
          "karma": {"sa", "no", "pl", "ch"}}


def aspect_set(cfg, scale: float = 1.0, extra: bool = True) -> list[tuple[str, float, float]]:
    """[(код, угол, орбис)] из config (+ EXTRA), отсортировано по углу."""
    out = {ASP_CODES[n]: (a, cfg.orbs.get(n, 0.0) * scale) for n, a in cfg.aspects.items() if n in ASP_CODES}
    if extra:
        for c, (a, o) in EXTRA_ASPECTS.items():
            out.setdefault(c, (a, o * scale))
    return sorted(((c, a, o) for c, (a, o) in out.items()), key=lambda x: x[1])


def closeness(orb: float, maxorb: float) -> float:
    return max(0.0, 1.0 - orb / maxorb) if maxorb > 0 else 0.0


def weight(t: str, a: str, b: str, orb: float, maxorb: float, wa: dict = POINT_W, wb: dict = POINT_W) -> float:
    return ASP_W.get(t, 0.3) * wa.get(a, 0.3) * wb.get(b, 0.3) * closeness(orb, maxorb)


def is_tense(t: str, a: str, b: str) -> bool:
    return t in TENSE or (t == "cj" and (a in MALEFIC or b in MALEFIC))


def saturate(x: float, k: float = 1.5) -> int:
    """Сумма весов -> 0..100."""
    return int(round(100.0 * (1.0 - math.exp(-x / k))))


def sign_code(lon: float) -> str:
    return SIGN_CODES[int(lon // 30) % 12]


def elements(lons) -> list[int]:
    """[fire, earth, air, water]."""
    out = [0, 0, 0, 0]
    for l in lons:
        out[int(l // 30) % 12 % 4] += 1
    return out


def sep(a: float, b: float) -> float:
    d = (b - a) % 360.0
    return min(d, 360.0 - d)


def wrap(x: float) -> float:
    return (x + 180.0) % 360.0 - 180.0
