"""Транзиты к натальной карте: события (вход/точно/выход орба, ретро-проходы), активные, станции, ингрессы."""
from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import swisseph as swe

from . import scoring as S
from .natal import NODE_IDS, _setup, compute, norm
from .timeconv import InputError

BODY_IDS = {"su": swe.SUN, "mo": swe.MOON, "me": swe.MERCURY, "ve": swe.VENUS, "ma": swe.MARS,
            "ju": swe.JUPITER, "sa": swe.SATURN, "ur": swe.URANUS, "ne": swe.NEPTUNE, "pl": swe.PLUTO,
            "ch": swe.CHIRON}
BODIES = ("su", "mo", "me", "ve", "ma", "ju", "sa", "ur", "ne", "pl", "no", "ch")
NATAL_PTS = ("su", "mo", "me", "ve", "ma", "ju", "sa", "ur", "ne", "pl", "no", "as", "mc")
STATION_BODIES = ("me", "ve", "ma", "ju", "sa", "ur", "ne", "pl", "ch")
STEP = {"mo": 0.05, "su": 0.5, "me": 0.25, "ve": 0.25, "ma": 0.5, "ju": 1.0, "sa": 1.0,
        "ur": 2.0, "ne": 2.0, "pl": 2.0, "no": 0.5, "ch": 1.0}          # шаг выборки, сут
PAD = {"mo": 3, "su": 40, "me": 120, "ve": 150, "ma": 250, "ju": 400, "sa": 450,
       "ur": 600, "ne": 600, "pl": 600, "no": 120, "ch": 600}          # запас за окном для полного орба, сут
MERGE = {"mo": 5, "su": 10, "me": 120, "ve": 120, "ma": 250, "no": 60}  # слияние ретро-проходов, сут (иначе 300)
TOL = 1.0 / 1440.0
DEFAULT_DAYS = 60


class Ephem:
    def __init__(self, cfg, lat: float = 0.0, lon: float = 0.0):
        self.flags = _setup(cfg.with_(topocentric=False), lat, lon, 0.0)
        self.ids = dict(BODY_IDS, no=NODE_IDS[cfg.node])

    def calc(self, b: str, jd: float) -> tuple[float, float]:
        xx, _ = swe.calc_ut(jd, self.ids[b], self.flags)
        return norm(xx[0]), xx[3]

    def lon(self, b: str, jd: float) -> float:
        return self.calc(b, jd)[0]

    def available(self, b: str, jd: float) -> bool:
        try:
            self.calc(b, jd)
            return True
        except swe.Error:
            return False


def bisect(f, a: float, b: float, tol: float = TOL) -> float:
    fa = f(a)
    while b - a > tol:
        m = 0.5 * (a + b)
        fm = f(m)
        if (fm < 0) == (fa < 0):
            a, fa = m, fm
        else:
            b = m
    return 0.5 * (a + b)


def samples(eph: Ephem, b: str, jd0: float, jd1: float):
    st = STEP[b]
    n = int(math.ceil((jd1 - jd0) / st)) + 1
    ts = [jd0 + i * st for i in range(n)]
    xs = [eph.calc(b, t) for t in ts]
    return ts, [x[0] for x in xs], [x[1] for x in xs]


def target_runs(eph: Ephem, b: str, ts, lons, target: float, orb: float) -> list[list]:
    """Интервалы в орбе target, ретро-петли слиты в одно событие: [start, end, [exact...], min_orb]."""
    d = [S.wrap(l - target) for l in lons]
    n, runs, i = len(d), [], 0
    g = lambda t: abs(S.wrap(eph.lon(b, t) - target)) - orb
    f = lambda t: S.wrap(eph.lon(b, t) - target)
    while i < n:
        if abs(d[i]) > orb:
            i += 1
            continue
        j = i
        while j + 1 < n and abs(d[j + 1]) <= orb:
            j += 1
        start = ts[i] if i == 0 else bisect(g, ts[i - 1], ts[i])
        end = ts[j] if j == n - 1 else bisect(g, ts[j], ts[j + 1])
        ex = [bisect(f, ts[k], ts[k + 1]) for k in range(max(i - 1, 0), min(j, n - 2) + 1)
              if (d[k] < 0) != (d[k + 1] < 0) and abs(d[k]) < 90 and abs(d[k + 1]) < 90]
        runs.append([start, end, ex, min(abs(x) for x in d[i:j + 1])])
        i = j + 1
    merged, gap = [], MERGE.get(b, 300)
    for r in runs:
        if merged and r[0] - merged[-1][1] < gap:
            m = merged[-1]
            m[1], m[2], m[3] = r[1], m[2] + r[2], min(m[3], r[3])
        else:
            merged.append(r)
    for m in merged:
        if m[2]:
            m[3] = 0.0
    return merged


def stations(eph: Ephem, b: str, ts, spd, jd0: float, jd1: float) -> list[tuple[str, float, str]]:
    out = []
    for k in range(len(ts) - 1):
        if (spd[k] < 0) != (spd[k + 1] < 0):
            t = bisect(lambda x: eph.calc(b, x)[1], ts[k], ts[k + 1])
            if jd0 <= t < jd1:
                out.append((b, t, "R" if spd[k] >= 0 else "D"))
    return out


def ingresses(eph: Ephem, b: str, ts, lons, jd0: float, jd1: float) -> list[tuple[str, float, str]]:
    out = []
    for k in range(len(ts) - 1):
        s0, s1 = int(lons[k] // 30) % 12, int(lons[k + 1] // 30) % 12
        if s0 == s1:
            continue
        if s1 == (s0 + 1) % 12:
            edge = 30.0 * s1
        elif s1 == (s0 - 1) % 12:
            edge = 30.0 * s0
        else:
            continue
        t = bisect(lambda x: S.wrap(eph.lon(b, x) - edge), ts[k], ts[k + 1])
        if jd0 <= t < jd1:
            out.append((b, t, S.SIGN_CODES[s1]))
    return out


# --- время ---

def natal_tz(data: dict, offset_h: float):
    if "utc_offset" in data or "tz" not in data:
        return timezone(timedelta(hours=offset_h))
    try:
        return ZoneInfo(data["tz"])
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise InputError("tz", f"unknown tz: {data['tz']}") from None


def local_jd(d: date, tz, hour: float = 0.0) -> float:
    u = (datetime.combine(d, time()).replace(tzinfo=tz) + timedelta(hours=hour)).astimezone(timezone.utc)
    return swe.julday(u.year, u.month, u.day, u.hour + u.minute / 60.0 + u.second / 3600.0)


def jd_local(jd: float, tz) -> datetime:
    y, m, d, h = swe.revjul(jd)
    return (datetime(y, m, d, tzinfo=timezone.utc) + timedelta(hours=h)).astimezone(tz)


def fmt_hour(jd: float, tz) -> str:
    return (jd_local(jd, tz) + timedelta(minutes=30)).strftime("%Y-%m-%dT%H")


def fmt_day(jd: float, tz) -> str:
    return jd_local(jd, tz).strftime("%Y-%m-%d")


def parse_date(s, field: str) -> date | None:
    if s is None:
        return None
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        raise InputError(field, f"expected YYYY-MM-DD, got {s!r}") from None


# --- основной расчёт ---

def transits(data: dict, cfg, on: str | None = None, frm: str | None = None, to: str | None = None,
             days: int | None = None, top: int = 15, scale: float = 1.0, full: bool = False,
             today: date | None = None) -> dict:
    if not isinstance(data, dict):
        raise InputError("input", "input must be a JSON object")
    nat = compute(data, cfg, with_aspects=False)
    off = nat["meta"]["utc_offset"]
    sign = -1.0 if off.startswith("-") else 1.0
    hh, mm = off.lstrip("+-").split(":")[:2]
    tz = natal_tz(data, sign * (int(hh) + int(mm) / 60.0))
    if days is not None and not 0 <= days <= 3660:
        raise InputError("days", "days must be 0..3660")
    today = today or datetime.now(tz).date()
    d_on, d_from, d_to = parse_date(on, "date"), parse_date(frm, "from"), parse_date(to, "to")
    with_moon = d_on is not None
    if d_on:
        d0, d1, ref = d_on, d_on + timedelta(days=days or 0), d_on
    else:
        d0 = d_from or today
        d1 = d_to or d0 + timedelta(days=DEFAULT_DAYS if days is None else days)
        ref = today if d0 <= today <= d1 else d0
    if d1 < d0:
        raise InputError("to", "to < from")
    if (d1 - d0).days > 3660:
        raise InputError("to", "window > 3660 days")
    jd0, jd1, jref = local_jd(d0, tz), local_jd(d1 + timedelta(days=1), tz), local_jd(ref, tz, 12.0)

    natal = {}
    for n, p in nat["planets"].items():
        c = S.CODES.get(n)
        if c in NATAL_PTS:
            natal[c] = p["lon"]
    natal["as"], natal["mc"] = nat["angles"]["asc"], nat["angles"]["mc"]
    natal = {c: natal[c] for c in NATAL_PTS if c in natal}

    eph = Ephem(cfg, nat_lat(data), 0.0)
    bodies = [b for b in BODIES if (b != "mo" or with_moon) and eph.available(b, jref)]
    missing = [b for b in BODIES if (b != "mo" or with_moon) and b not in bodies]

    ev, now, st, ing = [], [], [], []
    for b in bodies:
        ts, lons, spd = samples(eph, b, jd0 - PAD[b], jd1 + PAD[b])
        if b in STATION_BODIES:
            st += stations(eph, b, ts, spd, jd0, jd1)
        ing += ingresses(eph, b, ts, lons, jd0, jd1)
        lr, vr = eph.calc(b, jref)
        for p, lp in natal.items():
            for code, (ang, k) in S.TRANSIT_ASP.items():
                orb = S.TRANSIT_ORB[b] * k * scale
                for target in sorted({round(norm(lp + ang), 9), round(norm(lp - ang), 9)}):
                    for s0, s1, ex, mn in target_runs(eph, b, ts, lons, target, orb):
                        if s1 < jd0 or s0 > jd1:
                            continue
                        w = round(S.weight(code, b, p, mn, orb, S.TRANSIT_W, S.POINT_W), 2)
                        exf = [fmt_hour(x, tz) for x in sorted(ex)]
                        ev.append([b, p, code, exf[0] if len(exf) == 1 else (exf or None),
                                   fmt_day(s0, tz), fmt_day(s1, tz), len(ex), w, sorted(ex)[:1] or [s0]])
                    dn = abs(S.wrap(lr - target))
                    if dn <= orb:
                        app = abs(S.wrap(lr + vr * TOL - target)) < dn
                        now.append([b, p, code, round(dn, 2), int(app),
                                    S.weight(code, b, p, dn, orb, S.TRANSIT_W, S.POINT_W)])

    ev.sort(key=lambda r: (-r[7], r[8][0], S.ORDER[r[0]], S.ORDER[r[1]], r[2]))
    seen: dict[str, int] = {}
    ids = []
    for r in ev:
        base = f"{r[0]}-{r[1]}-{r[2]}"
        seen[base] = seen.get(base, 0) + 1
        ids.append(base if seen[base] == 1 else f"{base}#{seen[base]}")
        del r[8]
    now.sort(key=lambda r: (-r[5], r[3], S.ORDER[r[0]], S.ORDER[r[1]], r[2]))
    st.sort(key=lambda r: (r[1], S.ORDER[r[0]]))
    ing.sort(key=lambda r: (r[1], S.ORDER[r[0]]))

    def pick(rows):  # обрезка по важности тела, затем по дате
        if full or len(rows) <= top:
            return rows
        keep = sorted(rows, key=lambda r: (-S.TRANSIT_W[r[0]], r[1]))[:top]
        return sorted(keep, key=lambda r: (r[1], S.ORDER[r[0]]))

    st_out, ing_out = pick(st), pick(ing)
    imp = lambda rows: sorted(rows, key=lambda r: (-S.TRANSIT_W[r[0]], r[1]))[:5]
    res = {
        "v": "1", "mode": "tr",
        "digest": {"top": ids[:5],
                   "active_now": [f"{r[0]}-{r[1]}-{r[2]}" for r in now[:5]],
                   "ingress": [f"{r[0]}>{r[2]} {fmt_day(r[1], tz)}" for r in imp(ing)],
                   "stations": [f"{r[0]} {r[2]} {fmt_day(r[1], tz)}" for r in imp(st)],
                   "n": {"ev": len(ev), "now": len(now), "st": len(st), "ing": len(ing)}},
        "ev": ev if full else ev[:top],
        "now": [r[:5] for r in (now if full else now[:top])],
        "st": [[b, fmt_hour(t, tz), k] for b, t, k in st_out],
        "ing": [[b, fmt_hour(t, tz), s] for b, t, s in ing_out],
        "meta": {"natal_ref": {"name": data.get("name", ""), "ut": nat["meta"]["ut"],
                               "tz": data.get("utc_offset") or data.get("tz") or off},
                 "from": d0.isoformat(), "to": d1.isoformat(), "ref": ref.isoformat()},
    }
    if full:
        res["ids"] = ids
    if missing:
        res["meta"]["missing"] = missing
    return res


def nat_lat(data: dict) -> float:
    try:
        return float(data.get("lat", 0.0))
    except (TypeError, ValueError):
        return 0.0
