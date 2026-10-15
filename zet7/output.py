"""Форматирование: легенды, natal-digest, детерминированный компактный JSON (digest первым)."""
from __future__ import annotations

import json

from . import scoring as S

COMMON = {"pts": "su mo me ve ma ju sa ur ne pl no(node) ch li as mc",
          "asp": "cj0 sx60 sq90 tr120 qc150 op180", "sign": "ar ta ge cn le vi li sc sg cp aq pi",
          "id": "a-b-asp", "w": "0..1 asp*pointA*pointB*closeness", "order": "rows sorted by w desc"}
LEGENDS = {
    "nat": {"pl": "{pt:[lon,house,retro01]}", "ang": "{as,mc:lon}", "hs": "cusps 1..12",
            "asp": "[a,b,asp,orb,applying01,w]", "digest.big3": "[sun,moon,asc] sign",
            "digest.bal": "[fire,earth,air,water] su..pl+as", "digest.top": "ids of top asp"},
    "syn": {"asp": "[a(A),b(B),asp,orb,applying01,w] only A-B", "ovl": "AinB:{A pt:B house},BinA",
            "comp": "{pt:composite midpoint lon}", "bal": "{A,B:[fire,earth,air,water] su..pl+as}",
            "digest.score": "0..100 harmonious share of w", "digest.harm/tense": "top-5 ids",
            "digest.themes": "0..100 emo mind phys karma conflict"},
    "tr": {"ev": "[tr,nat,asp,exact(str|[str] if retro passes|null),orb_start,orb_end,passes,w]",
           "now": "[tr,nat,asp,orb,applying01] at ref 12:00", "st": "[pl,time,R|D]",
           "ing": "[pl,time,new sign]", "time": "local natal tz, YYYY-MM-DDTHH", "id": "tr-nat-asp[#k]",
           "w": "0..1 asp*tr*nat*closeness", "digest.n": "total rows before --top"},
}


def legend(mode: str) -> dict:
    return {**COMMON, **LEGENDS[mode]}


def schema(mode: str | None) -> dict:
    modes = [mode] if mode in LEGENDS else sorted(LEGENDS)
    return {"v": "1", "schema": {m: legend(m) for m in modes}}


def cfg_summary(cfg, scale: float, ephe: str | None = None) -> dict:
    return {"ephe": ephe or cfg.ephe_mode, "hs": cfg.house_system, "node": cfg.node,
            "lilith": cfg.lilith, "orb_scale": scale}


def _sorted(o):
    if isinstance(o, dict):
        return {k: _sorted(o[k]) for k in sorted(o)}
    if isinstance(o, (list, tuple)):
        return [_sorted(x) for x in o]
    return o


def dumps(obj: dict) -> str:
    """Порядок верхнего уровня: v, mode, digest, детали по алфавиту, meta; вложенные ключи отсортированы."""
    head = [k for k in ("v", "mode", "digest") if k in obj]
    rest = sorted(k for k in obj if k not in head and k != "meta")
    keys = head + rest + (["meta"] if "meta" in obj else [])
    return json.dumps({k: _sorted(obj[k]) for k in keys}, ensure_ascii=False, separators=(",", ":"))


def natal_view(res: dict, cfg, top: int = 15, scale: float = 1.0, name: str = "") -> dict:
    """Компактный натал. cfg — уже масштабированный (те же орбисы, что в расчёте аспектов)."""
    pl = {}
    for n, p in res["planets"].items():
        c = S.CODES.get(n)
        if c:
            pl[c] = [round(p["lon"], 2), p["house"], int(p["retro"])]
    rows = []
    for a in res["aspects"]:
        ca, cb, t = S.CODES[a["a"]], S.CODES[a["b"]], S.ASP_CODES[a["type"]]
        mo = cfg.orbs.get(a["type"], 0.0) + (cfg.luminary_orb_bonus if ca in S.LUM or cb in S.LUM else 0.0)
        rows.append([ca, cb, t, round(a["orb"], 2), int(a["applying"]), round(S.weight(t, ca, cb, a["orb"], mo), 2)])
    rows.sort(key=lambda r: (-r[5], r[3], S.ORDER[r[0]], S.ORDER[r[1]], r[2]))
    ang = res["angles"]
    lons = [res["planets"][n]["lon"] for n in ("sun", "moon", "mercury", "venus", "mars", "jupiter",
                                                 "saturn", "uranus", "neptune", "pluto") if n in res["planets"]]
    big3 = [S.sign_code(res["planets"][n]["lon"]) if n in res["planets"] else None for n in ("sun", "moon")]
    m = res["meta"]
    return {
        "v": "1", "mode": "nat",
        "digest": {"big3": big3 + [S.sign_code(ang["asc"])], "bal": S.elements(lons + [ang["asc"]]),
                   "top": [f"{r[0]}-{r[1]}-{r[2]}" for r in rows[:5]],
                   "retro": [c for c, v in pl.items() if v[2] and c not in ("no", "li")], "n": len(rows)},
        "pl": pl, "ang": {"as": round(ang["asc"], 2), "mc": round(ang["mc"], 2)},
        "hs": [round(c, 2) for c in res["houses"]], "asp": rows[:top],
        "meta": {"legend": legend("nat"), "config": cfg_summary(cfg, scale, m.get("ephe")),
                 "name": name, "ut": m["ut"], "tz": m["utc_offset"]},
    }
