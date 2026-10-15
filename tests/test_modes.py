"""Тесты synastry / transits / CLI. Регрессия натала — tests/test_reference.py."""
import contextlib
import io
import json
import os
import sys
import unittest
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import swisseph as swe  # noqa: E402

from zet7 import transits as T  # noqa: E402
from zet7.cli import main  # noqa: E402
from zet7.config import Config  # noqa: E402
from zet7.synastry import synastry  # noqa: E402

REF = os.path.join(ROOT, "calibrate", "reference")
IN = os.path.join(ROOT, "in.json")


def _ref(name):
    with open(os.path.join(REF, name), encoding="utf-8-sig") as f:
        return json.load(f)


def _cli(*argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = main(list(argv))
    return code, buf.getvalue().strip()


class TestSynastry(unittest.TestCase):
    def test_symmetry(self):
        a, b, cfg = _ref("card_01.json"), _ref("card_02.json"), Config()
        ab = synastry(a, b, cfg, full=True)
        ba = synastry(b, a, cfg, full=True)
        self.assertTrue(ab["asp"])
        s1 = {tuple(r) for r in ab["asp"]}
        s2 = {(r[1], r[0], *r[2:]) for r in ba["asp"]}
        self.assertEqual(s1, s2)
        self.assertEqual(ab["digest"]["score"], ba["digest"]["score"])
        self.assertEqual(ab["ovl"]["AinB"], ba["ovl"]["BinA"])
        self.assertEqual(ab["comp"], ba["comp"])

    def test_deterministic(self):
        pa, pb = os.path.join(REF, "card_01.json"), os.path.join(REF, "card_02.json")
        r1, r2 = _cli("synastry", pa, pb), _cli("synastry", pa, pb)
        self.assertEqual(r1, r2)
        self.assertEqual(r1[0], 0)
        self.assertTrue(r1[1].startswith('{"v":"1","mode":"syn","digest":'))


class TestTransits(unittest.TestCase):
    def setUp(self):
        self.eph = T.Ephem(Config())

    def test_sun_ingress_vs_solcross(self):
        jd0, jd1 = swe.julday(2027, 3, 10, 0.0), swe.julday(2027, 3, 30, 0.0)
        ts, lons, _ = T.samples(self.eph, "su", jd0, jd1)
        ing = [x for x in T.ingresses(self.eph, "su", ts, lons, jd0, jd1) if x[2] == "ar"]
        self.assertEqual(len(ing), 1)
        ref = swe.solcross_ut(0.0, jd0, self.eph.flags)
        ref = ref[0] if isinstance(ref, (tuple, list)) else ref
        self.assertLess(abs(ing[0][1] - ref) * 24, 1.0)

    def test_station_sign_change(self):
        jd0 = swe.julday(2026, 1, 1, 0.0)
        ts, _, spd = T.samples(self.eph, "me", jd0, jd0 + 365)
        st = T.stations(self.eph, "me", ts, spd, jd0, jd0 + 365)
        self.assertGreaterEqual(len(st), 6)
        for b, t, kind in st:
            v0, v1 = self.eph.calc(b, t - 1 / 24)[1], self.eph.calc(b, t + 1 / 24)[1]
            self.assertEqual(kind, "R" if v0 > 0 else "D")
            self.assertTrue((v0 < 0) != (v1 < 0))

    def test_retro_triple_pass(self):
        jd0 = swe.julday(2026, 1, 1, 0.0)
        ts, lons, spd = T.samples(self.eph, "sa", jd0, jd0 + 500)
        st = T.stations(self.eph, "sa", ts, spd, jd0, jd0 + 500)
        r = next(x for x in st if x[2] == "R")
        d = next(x for x in st if x[2] == "D" and x[1] > r[1])
        lr, ld = self.eph.lon("sa", r[1]), self.eph.lon("sa", d[1])
        target = (ld + ((lr - ld) % 360.0) / 2.0) % 360.0
        runs = T.target_runs(self.eph, "sa", ts, lons, target, 2.0)
        self.assertEqual(len(runs), 1)
        self.assertEqual(len(runs[0][2]), 3)
        for x in runs[0][2]:
            self.assertLess(abs((self.eph.lon("sa", x) - target + 180) % 360 - 180), 0.01)

    def test_cli_event_merge_and_size(self):
        code, out = _cli("transits", IN)
        self.assertEqual(code, 0)
        self.assertLessEqual(len(out), 3000, len(out))
        res = json.loads(out)
        self.assertEqual(res["mode"], "tr")
        for e in res["ev"]:
            self.assertEqual(len(e), 8)
            if e[6] > 1:
                self.assertIsInstance(e[3], list)

    def test_date_mode_includes_moon(self):
        with open(IN, encoding="utf-8-sig") as f:
            data = json.load(f)
        r = T.transits(data, Config(), on="2026-10-09", full=True)
        self.assertTrue(any(x[0] == "mo" for x in r["now"]) or any(x[0] == "mo" for x in r["ev"]))
        r2 = T.transits(data, Config(), frm="2026-10-09", to="2026-11-09", today=date(2026, 10, 9), full=True)
        self.assertFalse(any(x[0] == "mo" for x in r2["ev"] + r2["now"]))


class TestCli(unittest.TestCase):
    def test_errors(self):
        code, out = _cli("transits", IN, "--date", "2026-13-01")
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)["field"], "date")
        code, out = _cli("synastry", IN, "nope.json")
        self.assertEqual((code, json.loads(out)["field"]), (1, "b"))

    def test_schema_and_natal(self):
        code, out = _cli("transits", "--schema")
        self.assertEqual(code, 0)
        self.assertIn("tr", json.loads(out)["schema"])
        code, out = _cli("natal", IN)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["mode"], "nat")


if __name__ == "__main__":
    unittest.main()
