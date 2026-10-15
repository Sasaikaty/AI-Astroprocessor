"""python -m zet7 natal a.json | synastry a.json b.json | transits a.json [--date D | --from D --to D] [--days N]
Общие флаги: --top N, --orb-scale F, --full, --schema. Вывод: компактный JSON, ошибки {"error","field"} + код 1."""
from __future__ import annotations

import argparse
import json
import sys

from . import output as O
from .config import Config
from .natal import compact, compute
from .synastry import synastry
from .timeconv import InputError
from .transits import transits

MODES = {"natal": "nat", "synastry": "syn", "transits": "tr"}


def _fail(error: str, field: str) -> int:
    print(json.dumps({"error": error, "field": field}, ensure_ascii=False, sort_keys=True))
    return 1


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        sys.exit(_fail(message, "args"))


def _load(path: str, field: str):
    try:
        if path == "-":
            return json.load(sys.stdin)
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except OSError as e:
        raise InputError(field, f"cannot read input: {e.strerror}") from None
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise InputError(field, f"invalid JSON: {e}") from None


def _parser() -> _Parser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--top", type=int, default=15)
    common.add_argument("--orb-scale", dest="orb_scale", type=float, default=1.0)
    common.add_argument("--full", action="store_true")
    common.add_argument("--house", dest="house_system")
    common.add_argument("--node", choices=("true", "mean"))
    common.add_argument("--lilith", choices=("mean", "true", "osc", "intp"))
    common.add_argument("--ephe", dest="ephe_mode", choices=("swiss", "moshier"))
    common.add_argument("--topo", dest="topocentric", action="store_true", default=None)
    common.add_argument("--delta-t", dest="delta_t", type=float)
    p = _Parser(prog="zet7")
    sub = p.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("natal", parents=[common])
    n.add_argument("input", help="путь к JSON или '-' для stdin")
    n.add_argument("--compact", action="store_true", help="legacy compact (planets/angles/aspects)")
    s = sub.add_parser("synastry", parents=[common])
    s.add_argument("a")
    s.add_argument("b")
    t = sub.add_parser("transits", parents=[common])
    t.add_argument("input")
    t.add_argument("--date")
    t.add_argument("--from", dest="frm")
    t.add_argument("--to")
    t.add_argument("--days", type=int)
    return p


def run(a) -> dict | str:
    if a.top < 1:
        raise InputError("top", "--top must be >= 1")
    if not a.orb_scale > 0:
        raise InputError("orb-scale", "--orb-scale must be > 0")
    over = {k: getattr(a, k) for k in ("house_system", "node", "lilith", "ephe_mode", "topocentric", "delta_t")
            if getattr(a, k) is not None}
    cfg = Config().with_(**over)
    sc = a.orb_scale
    if a.cmd == "natal":
        data = _load(a.input, "input")
        if not isinstance(data, dict):
            raise InputError("input", "input must be a JSON object")
        scfg = cfg.with_(orbs={k: v * sc for k, v in cfg.orbs.items()},
                         luminary_orb_bonus=cfg.luminary_orb_bonus * sc)
        res = compute(data, scfg)
        if a.full or a.compact:
            return json.dumps(compact(res) if a.compact else res, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":"))
        return O.natal_view(res, scfg, a.top, sc, data.get("name", ""))
    if a.cmd == "synastry":
        res = synastry(_load(a.a, "a"), _load(a.b, "b"), cfg, a.top, sc, a.full)
    else:
        if a.date and (a.frm or a.to):
            raise InputError("date", "--date excludes --from/--to")
        res = transits(_load(a.input, "input"), cfg, a.date, a.frm, a.to, a.days, a.top, sc, a.full)
    res["meta"]["legend"] = O.legend(res["mode"])
    res["meta"]["config"] = O.cfg_summary(cfg, sc)
    return res


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    argv = sys.argv[1:] if argv is None else list(argv)
    if "--schema" in argv:
        mode = next((MODES[x] for x in argv if x in MODES), None)
        print(O.dumps(O.schema(mode)))
        return 0
    a = _parser().parse_args(argv)
    try:
        res = run(a)
    except InputError as e:
        return _fail(e.message, e.field)
    print(res if isinstance(res, str) else O.dumps(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
