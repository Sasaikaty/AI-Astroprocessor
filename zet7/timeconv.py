"""Локальное время → UT. Явный utc_offset имеет приоритет над tz (так задаёт время ZET)."""
from __future__ import annotations

import re
from datetime import date as _date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import swisseph as swe


class InputError(ValueError):
    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


_OFF_RE = re.compile(r"^(?:UTC|GMT)?\s*([+-])\s*(\d{1,2})(?::?(\d{2}))?$", re.I)
_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}(?:\.\d+)?))?$")
_COORD_RE = re.compile(r"^\s*([+-]?\d+(?:\.\d+)?)\s*([NSEWnsew]?)\s*$")


def parse_offset(value) -> float:
    """'+03:00', '-3', 'UTC+6:00', '+0530', 5.5 → часы."""
    if isinstance(value, bool):
        raise InputError("utc_offset", "bad offset")
    if isinstance(value, (int, float)):
        h = float(value)
    else:
        s = str(value).strip()
        if s.upper() in ("UTC", "GMT", "Z", "0"):
            return 0.0
        m = _OFF_RE.match(s)
        if not m:
            raise InputError("utc_offset", f"bad offset: {value!r}")
        sign = -1.0 if m.group(1) == "-" else 1.0
        hh, mm = int(m.group(2)), int(m.group(3) or 0)
        if mm >= 60:
            raise InputError("utc_offset", f"bad offset minutes: {value!r}")
        h = sign * (hh + mm / 60.0)
    if not -14.0 <= h <= 14.0:
        raise InputError("utc_offset", f"offset out of range: {value!r}")
    return h


def format_offset(hours: float) -> str:
    sign = "-" if hours < 0 else "+"
    m = round(abs(hours) * 60)
    return f"{sign}{m // 60:02d}:{m % 60:02d}"


def parse_date(value) -> _date:
    try:
        return _date.fromisoformat(str(value).strip())
    except (ValueError, TypeError):
        raise InputError("date", f"bad date: {value!r}, expected YYYY-MM-DD") from None


def parse_time(value) -> tuple[int, int, float]:
    m = _TIME_RE.match(str(value).strip()) if value is not None else None
    if not m:
        raise InputError("time", f"bad time: {value!r}, expected HH:MM[:SS]")
    h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3) or 0)
    if h > 23 or mi > 59 or s >= 60:
        raise InputError("time", f"time out of range: {value!r}")
    return h, mi, s


def parse_coord(value, field: str) -> float:
    """Десятичные градусы; допускается суффикс N/S/E/W (S и W дают минус)."""
    if isinstance(value, bool) or value is None:
        raise InputError(field, f"bad {field}: {value!r}")
    if isinstance(value, (int, float)):
        v = float(value)
    else:
        m = _COORD_RE.match(str(value))
        if not m:
            raise InputError(field, f"bad {field}: {value!r}")
        v = float(m.group(1))
        suf = m.group(2).upper()
        if suf and ((field == "lat" and suf not in "NS") or (field == "lon" and suf not in "EW")):
            raise InputError(field, f"bad hemisphere for {field}: {value!r}")
        if suf in ("S", "W"):
            v = -abs(v)
    lim = 90.0 if field == "lat" else 180.0
    if not -lim <= v <= lim:
        raise InputError(field, f"{field} out of range: {value!r}")
    return v


def to_ut(date_s, time_s, utc_offset=None, tz=None) -> tuple[datetime, float]:
    """Возвращает (datetime в UTC, использованное смещение в часах)."""
    d = parse_date(date_s)
    h, mi, s = parse_time(time_s)
    sec = int(s)
    us = round((s - sec) * 1e6)
    local = datetime(d.year, d.month, d.day, h, mi, sec, us)
    if utc_offset is not None and utc_offset != "":
        off = parse_offset(utc_offset)
        ut = local - timedelta(hours=off)
        return ut.replace(tzinfo=timezone.utc), off
    if tz:
        try:
            zi = ZoneInfo(str(tz))
        except (ZoneInfoNotFoundError, ValueError):
            raise InputError("tz", f"unknown tz: {tz!r}") from None
        aware = local.replace(tzinfo=zi)
        off = aware.utcoffset().total_seconds() / 3600.0
        return aware.astimezone(timezone.utc), off
    raise InputError("utc_offset", "utc_offset or tz is required")


def julday_ut(ut: datetime) -> float:
    hour = ut.hour + ut.minute / 60.0 + (ut.second + ut.microsecond / 1e6) / 3600.0
    return swe.julday(ut.year, ut.month, ut.day, hour, swe.GREG_CAL)


def parse_input(data) -> dict:
    """Валидация входного JSON → нормализованные поля."""
    if not isinstance(data, dict):
        raise InputError("input", "input must be a JSON object")
    for f in ("date", "time", "lat", "lon"):
        if f not in data:
            raise InputError(f, f"missing field: {f}")
    ut, off = to_ut(data["date"], data["time"], data.get("utc_offset"), data.get("tz"))
    return {
        "name": data.get("name", ""),
        "ut": ut,
        "offset_h": off,
        "jd_ut": julday_ut(ut),
        "lat": parse_coord(data["lat"], "lat"),
        "lon": parse_coord(data["lon"], "lon"),
        "alt": float(data.get("alt", 0.0) or 0.0),
    }
