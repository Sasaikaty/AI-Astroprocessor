"""Чтение эталонов ZET 7: DMS/десятичный парсер, загрузка calibrate/reference/*.json."""
from __future__ import annotations

import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REF_DIR = os.path.join(HERE, "reference")

SIGN_ABBR = ("ari", "tau", "gem", "cnc", "leo", "vir", "lib", "sco", "sgr", "cap", "aqr", "psc")
_SIGN_ALIASES = {"can": 3, "sag": 8}
_DMS_RE = re.compile(
    r"""^\s*([+-])?\s*(\d+(?:\.\d+)?)\s*°\s*(?:(\d+(?:\.\d+)?)\s*'\s*)?(?:(\d+(?:\.\d+)?)\s*"\s*)?([A-Za-z]{3})?\s*$""")


def parse_angle(value) -> float:
    """'16°56'14.33"Cnc' → 106.937..; '- 0° 1'26"' → -0.0238; 123.45 → 123.45."""
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    try:
        return float(s)
    except ValueError:
        pass
    m = _DMS_RE.match(s)
    if not m:
        raise ValueError(f"bad angle: {value!r}")
    sign, d, mi, se, sg = m.groups()
    v = float(d) + float(mi or 0) / 60.0 + float(se or 0) / 3600.0
    if sg:
        key = sg.lower()
        idx = SIGN_ABBR.index(key) if key in SIGN_ABBR else _SIGN_ALIASES.get(key)
        if idx is None:
            raise ValueError(f"bad sign: {sg!r}")
        v += 30.0 * idx
    return -v if sign == "-" else v


def parse_coord_raw(raw: str, mode: str) -> float:
    """'55.10N' → 55°10' (mode='dm') или 55.10 (mode='dec')."""
    m = re.match(r"^\s*(\d+)(?:\.(\d+))?\s*([NSEW])\s*$", raw, re.I)
    if not m:
        raise ValueError(f"bad coord: {raw!r}")
    deg, frac, hemi = int(m.group(1)), m.group(2) or "0", m.group(3).upper()
    if mode == "dm":
        v = deg + int(frac.ljust(2, "0")[:2]) / 60.0
    else:
        v = float(f"{deg}.{frac}")
    return -v if hemi in "SW" else v


def angdiff_arcmin(a: float, b: float) -> float:
    d = (a - b + 180.0) % 360.0 - 180.0
    return abs(d) * 60.0


def load_refs(ref_dir: str = REF_DIR) -> list[dict]:
    refs = []
    for p in sorted(glob.glob(os.path.join(ref_dir, "*.json"))):
        with open(p, encoding="utf-8") as f:
            r = json.load(f)
        r["_file"] = os.path.basename(p)
        refs.append(r)
    return refs


def ref_input(ref: dict, coords: str = "dm") -> dict:
    inp = {k: ref[k] for k in ("name", "date", "time") if k in ref}
    for k in ("utc_offset", "tz"):
        if k in ref:
            inp[k] = ref[k]
    if "lat_raw" in ref and coords:
        lat_m, _, lon_m = coords.partition("/")
        inp["lat"] = parse_coord_raw(ref["lat_raw"], lat_m)
        inp["lon"] = parse_coord_raw(ref["lon_raw"], lon_m or lat_m)
    else:
        inp["lat"], inp["lon"] = ref["lat"], ref["lon"]
    return inp


def ref_points(ref: dict) -> dict[str, float]:
    """Все эталонные долготы: планеты, asc, mc, h1..h12."""
    z = ref["zet"]
    out = {}
    for k, v in z.items():
        if k == "houses":
            for i, h in enumerate(v):
                out[f"h{i + 1}"] = parse_angle(h) % 360.0
        else:
            out[k] = parse_angle(v) % 360.0
    return out


def calc_points(res: dict) -> dict[str, float]:
    out = {k: p["lon"] for k, p in res["planets"].items()}
    out["asc"], out["mc"] = res["angles"]["asc"], res["angles"]["mc"]
    for i, h in enumerate(res["houses"]):
        out[f"h{i + 1}"] = h
    return out
