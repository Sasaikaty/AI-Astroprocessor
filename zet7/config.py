"""Все настройки движка в одном dataclass. Значения по умолчанию = лучшая комбинация из calibrate/compare.py."""
from __future__ import annotations

import os
from dataclasses import dataclass, field, replace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_EPHE_PATH = os.environ.get("ZET7_EPHE", os.path.join(ROOT, "ephe"))

SIGNS = ("aries", "taurus", "gemini", "cancer", "leo", "virgo",
         "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces")

PLANETS = ("sun", "moon", "mercury", "venus", "mars", "jupiter",
           "saturn", "uranus", "neptune", "pluto")
CORE_POINTS = PLANETS + ("node", "south_node", "lilith", "chiron")
OPTIONAL_POINTS = ("selena", "proserpina", "ceres", "pallas", "juno", "vesta", "fortune")

HOUSE_SYSTEMS = ("P", "K", "R", "C", "E", "W", "B", "O", "T", "M")
EPHE_MODES = ("swiss", "moshier")
NODE_MODES = ("true", "mean")
LILITH_MODES = ("mean", "true", "osc", "intp")

DEFAULT_ASPECTS = {"conjunction": 0.0, "sextile": 60.0, "square": 90.0,
                   "trine": 120.0, "opposition": 180.0}
DEFAULT_ORBS = {"conjunction": 8.0, "sextile": 5.0, "square": 7.0,
                "trine": 7.0, "opposition": 8.0}


@dataclass(frozen=True)
class Config:
    ephe_mode: str = "swiss"            # swiss (.se1, при отсутствии swe сам падает на moshier) | moshier
    ephe_path: str = DEFAULT_EPHE_PATH
    house_system: str = "P"
    house_lat: str = "geocentric"       # geodetic | geocentric (широта для домов: tanφ' = (1-f)² tanφ) — так считает ZET 7
    node: str = "true"                  # true | mean
    lilith: str = "mean"                # mean | true(=osc) | osc | intp
    topocentric: bool = False
    altitude_m: float = 0.0
    delta_t: object = "auto"            # "auto" (Swiss ΔT) | секунды (float)
    zodiac: str = "tropical"            # tropical | sidereal
    ayanamsa: int = 1                   # swe.SIDM_*, только для sidereal
    # Селена/Прозерпина: "zet" — модели, подогнанные по эталону ZET 7; "swe" — seorbel.txt (не совпадает с ZET)
    selena: str = "zet"
    selena_l0: float = 242.567961       # долгота на J2000.0 (JD 2451545.0 UT), °
    selena_n: float = 0.1408277590      # °/сутки (период 2556.31 сут ≈ 7 лет)
    proserpina: str = "zet"
    proserpina_l0: float = 217.344595   # гелиоц. долгота на J2000.0, круговая орбита в эклиптике
    proserpina_n: float = 0.0012514992  # °/сутки (период ≈ 787.6 лет)
    proserpina_a: float = 85.07288      # а.е.
    fortune: str = "daynight"           # daynight (ночью ASC+Sun-Moon) | day
    points: tuple = CORE_POINTS + OPTIONAL_POINTS
    aspect_points: tuple = PLANETS + ("node", "lilith", "chiron", "asc", "mc")
    aspects: dict = field(default_factory=lambda: dict(DEFAULT_ASPECTS))
    orbs: dict = field(default_factory=lambda: dict(DEFAULT_ORBS))
    luminary_orb_bonus: float = 2.0     # +к орбису, если в аспекте Солнце или Луна

    def with_(self, **kw) -> "Config":
        return replace(self, **kw)

    def validate(self) -> None:
        if self.ephe_mode not in EPHE_MODES:
            raise ValueError(f"ephe_mode: {self.ephe_mode}")
        if len(self.house_system) != 1:
            raise ValueError(f"house_system: {self.house_system}")
        if self.house_lat not in ("geodetic", "geocentric"):
            raise ValueError(f"house_lat: {self.house_lat}")
        if self.node not in NODE_MODES:
            raise ValueError(f"node: {self.node}")
        if self.lilith not in LILITH_MODES:
            raise ValueError(f"lilith: {self.lilith}")
        if self.zodiac not in ("tropical", "sidereal"):
            raise ValueError(f"zodiac: {self.zodiac}")
        if self.delta_t != "auto" and not isinstance(self.delta_t, (int, float)):
            raise ValueError(f"delta_t: {self.delta_t}")
