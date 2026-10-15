"""Перебор комбинаций настроек против эталонов ZET 7. Ошибки в угловых минутах."""
from __future__ import annotations

import argparse
import itertools
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from calibrate.refio import (HERE, angdiff_arcmin, calc_points, load_refs, parse_angle,  # noqa: E402
                             ref_input, ref_points)
from zet7.config import CORE_POINTS, HOUSE_SYSTEMS, Config  # noqa: E402
from zet7.natal import compute  # noqa: E402

import swisseph as swe  # noqa: E402

CORE_KEYS = list(CORE_POINTS) + ["asc", "mc"] + [f"h{i}" for i in range(1, 13)]


def evaluate(cfg: Config, refs: list[dict], coords: str):
    """→ errs[point] = [(ref, err' | None)], results[ref_file] = result."""
    errs, results = {}, {}
    for r in refs:
        res = compute(ref_input(r, coords), cfg, with_aspects=False)
        results[r["_file"]] = res
        calc = calc_points(res)
        for k, v in ref_points(r).items():
            errs.setdefault(k, []).append((r, angdiff_arcmin(calc[k], v) if k in calc else None))
    return errs, results


def score(errs) -> tuple[int, int, float, float]:
    """(пропуски, число ошибок >1′, средняя′, макс′) — устойчиво к одной карте с ошибкой времени."""
    vals, missing = [], 0
    for k in CORE_KEYS:
        for _, e in errs.get(k, []):
            if e is None:
                missing += 1
            else:
                vals.append(e)
    return (missing, sum(e > 1.0 for e in vals), (sum(vals) / len(vals) if vals else 0.0),
            max(vals, default=0.0))


def fit_time(ref: dict) -> tuple[str, float]:
    """Подбор момента UT, при котором Солнце..Плутон совпадают с эталоном (поиск даты/года/пояса)."""
    rp = ref_points(ref)
    bodies = [(k, i) for i, k in enumerate(("sun", "moon", "mercury", "venus", "mars", "jupiter",
                                            "saturn", "uranus", "neptune", "pluto"))]

    def err(jd, ks):
        return max(angdiff_arcmin(swe.calc_ut(jd, b, swe.FLG_MOSEPH)[0][0], rp[k]) for k, b in ks)

    slow = [b for b in bodies if b[0] != "moon"]
    jd, best = swe.julday(1800, 1, 1, 0.0), (1e18, 0.0)
    while jd < swe.julday(2100, 1, 1, 0.0):
        e = err(jd, slow)
        if e < best[0]:
            best = (e, jd)
        jd += 1.0
    j, st = best[1], 0.5
    while st > 1e-7:
        for c in (j - st, j + st):
            if err(c, bodies) < err(j, bodies):
                j = c
        st /= 2
    y, m, d, h = swe.revjul(j)
    sec = round(h * 3600)
    return f"{y:04d}-{m:02d}-{d:02d} {sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d} UT", err(j, bodies)


def label(c: dict) -> str:
    return (f"hs={c['house_system']} hlat={c['house_lat'][:5]} node={c['node']:<4} lil={c['lilith']:<4} "
            f"topo={int(c['topocentric'])} "
            f"ephe={c['ephe_mode']:<7} dT={c['delta_t']!s:<4} coords={c['coords']}")


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--coords", default="dm/dm,dec/dec,dec/dm", help="формат lat/lon в эталоне")
    ap.add_argument("--delta-t", default="auto,0")
    ap.add_argument("--keep-bad", action="store_true", help="не исключать карты с ошибкой даты/времени")
    args = ap.parse_args(argv)
    all_refs = load_refs()
    if not all_refs:
        print("нет эталонов в calibrate/reference/ (запусти calibrate/txt2json.py)")
        return 1

    # Солнце не зависит от перебираемых настроек: ошибка >2' = неверные дата/время/пояс во входе.
    errs0, _ = evaluate(Config(), all_refs, "dm/dm")
    bad_time = [r for r, e in errs0["sun"] if e is not None and e > 2.0]
    if bad_time:
        print("КАРТЫ С ОШИБКОЙ ДАТЫ/ВРЕМЕНИ (Солнце >2′ при любых настройках):")
        for r in bad_time:
            when, e = fit_time(r)
            print(f"  {r['name']}: вход {r['date']} {r['time']} {r['utc_offset']} → ZET считал {when} (ост. {e:.3f}′)")
        print()
    refs = all_refs if args.keep_bad else [r for r in all_refs if r not in bad_time]

    dts = [d if d == "auto" else float(d) for d in args.delta_t.split(",")]
    grid = itertools.product(HOUSE_SYSTEMS, ("geodetic", "geocentric"), ("true", "mean"), ("mean", "true"),
                             (False, True), ("swiss", "moshier"), dts, args.coords.split(","))
    rows = []
    for hs, hlat, node, lil, topo, ephe, dt, coords in grid:
        c = dict(house_system=hs, house_lat=hlat, node=node, lilith=lil, topocentric=topo, ephe_mode=ephe,
                 delta_t=dt)
        errs, _ = evaluate(Config().with_(**c), refs, coords)
        c["coords"] = coords
        rows.append((score(errs), c))
    rows.sort(key=lambda x: x[0])

    print(f"эталонов: {len(refs)}, комбинаций: {len(rows)}\n\nТОП-5 (core: планеты, узлы, Лилит, Хирон, ASC/MC, куспиды)")
    print(f"{'#':>2} {'missing':>7} {'n>1′':>5} {'mean′':>7} {'max′':>8}  настройки")
    for i, ((mis, n1, mn, mx), c) in enumerate(rows[:5], 1):
        print(f"{i:>2} {mis:>7} {n1:>5} {mn:7.3f} {mx:8.3f}  {label(c)}")

    best = rows[0][1]
    cfg = Config().with_(**{k: v for k, v in best.items() if k != "coords"})
    errs, results = evaluate(cfg, refs, best["coords"])

    print(f"\nЛУЧШАЯ: {label(best)}\n{'точка':<11} {'max′':>8} {'mean′':>7}  худшая карта")
    over = []
    for k in list(errs):
        vals = [(r, e) for r, e in errs[k] if e is not None]
        if not vals:
            print(f"{k:<11} {'n/a':>8}")
            continue
        r_w, e_w = max(vals, key=lambda x: x[1])
        mean = sum(e for _, e in vals) / len(vals)
        print(f"{k:<11} {e_w:8.3f} {mean:7.3f}  {r_w['name']}")
        over += [(k, r, e) for r, e in vals if e > 1.0]

    print("\nТОЧКИ С ОШИБКОЙ >1′:" if over else "\nТОЧКИ С ОШИБКОЙ >1′: нет")
    for k, r, e in sorted(over, key=lambda x: -x[2]):
        print(f"  {k:<11} {e:9.3f}′  {r['name']} {r['date']} {r['time']} {r.get('utc_offset', r.get('tz'))}")

    print("\nПО КАРТАМ (core max′, сдвиг времени по Луне, с)")
    chart_max, shifts = {}, {}
    for r in refs:
        res = results[r["_file"]]
        calc, ref = calc_points(res), ref_points(r)
        es = {k: angdiff_arcmin(calc[k], ref[k]) for k in CORE_KEYS if k in calc and k in ref}
        k_w = max(es, key=es.get)
        chart_max[r["_file"]] = es[k_w]
        mo = res["planets"]["moon"]
        d = (ref["moon"] - mo["lon"] + 180.0) % 360.0 - 180.0
        shift = d / mo["speed"] * 86400.0
        shifts[r["_file"]] = shift
        print(f"  {r['name']:<9} {r['date']} {r['time']:>5} {r.get('utc_offset', '')}  max {es[k_w]:7.3f}′ ({k_w:<6}) "
              f"Δt(Луна) {shift:+8.1f} с  dT={res['meta']['dt_s']:.1f}")
    med = statistics.median(chart_max.values())
    bad = [r for r in refs if (chart_max[r["_file"]] > 1.0 and chart_max[r["_file"]] > 3 * max(med, 0.05))
           or abs(shifts[r["_file"]]) > 20.0]
    if bad:
        print("\nВЕРОЯТНО ПРОБЛЕМА ВРЕМЕНИ/ПОЯСА (ошибка карты ≫ медианы или Луна смещена >20 с):")
        for r in bad:
            print(f"  {r['name']} {r['date']} {r['time']} {r.get('utc_offset')} {r.get('place', '')}: "
                  f"по Луне ZET считал на {shifts[r['_file']]:+.0f} с позже")

    print("\nСКОРОСТИ: max ошибка, ″/сутки")
    sp = []
    for k in CORE_POINTS:
        e = []
        for r in refs:
            zs = r.get("zet_speed", {}).get(k)
            p = results[r["_file"]]["planets"].get(k)
            if zs is not None and p is not None:
                e.append(abs(parse_angle(zs) - p["speed"]) * 3600.0)
        if e:
            sp.append(f"{k} {max(e):.1f}")
    print("  " + ", ".join(sp))

    with open(os.path.join(HERE, "best.json"), "w", encoding="utf-8") as f:
        json.dump({"settings": best, "score": dict(zip(("missing", "max_arcmin", "mean_arcmin"), rows[0][0]))},
                  f, ensure_ascii=False, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
