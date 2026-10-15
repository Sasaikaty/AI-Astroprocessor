"""Конвертер calibrate/reference.txt (выгрузка ZET 7) → calibrate/reference/card_N.json."""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from calibrate.refio import REF_DIR, parse_coord_raw  # noqa: E402
from zet7.timeconv import format_offset, parse_offset  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = {
    "Солнце": "sun", "Луна": "moon", "Меркурий": "mercury", "Венера": "venus", "Марс": "mars",
    "Юпитер": "jupiter", "Сатурн": "saturn", "Уран": "uranus", "Нептун": "neptune", "Плутон": "pluto",
    "Узел": "node", "Южн.Узел": "south_node", "Лилит": "lilith", "Селена": "selena",
    "Прозерпина": "proserpina", "Хирон": "chiron", "Церера": "ceres", "Паллада": "pallas",
    "Юнона": "juno", "Веста": "vesta", "Фортуна": "fortune",
}
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
HOUSES = {"плацидус": "P", "кох": "K", "региомонтан": "R", "кампанус": "C", "равные": "E",
          "целые": "W", "алькабитиус": "B", "порфирий": "O", "топоцентрические": "T", "морин": "M"}
NODE = {"истинный": "true", "средний": "mean"}
LILITH = {"средняя": "mean", "истинная": "true", "оскулирующая": "osc"}


def parse_txt(path: str) -> list[dict]:
    settings, cards, cur = {}, [], None
    with open(path, encoding="utf-8-sig") as f:
        lines = f.read().splitlines()
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = re.match(r"^===\s*(.+?)\s*===$", s)
        if m:
            cur = {"name": m.group(1), "zet": {"houses": [None] * 12}, "zet_speed": {}}
            cards.append(cur)
            continue
        if cur is None:
            k, _, v = s.partition(":")
            k, v = k.strip().lower(), v.strip().lower()
            if k == "дома":
                settings["house_system"] = HOUSES.get(v, v)
            elif k == "узел":
                settings["node"] = NODE.get(v, v)
            elif k == "лилит":
                settings["lilith"] = LILITH.get(v, v)
            continue
        parts = [p.strip() for p in line.split("\t") if p.strip()]
        if parts and parts[0] in ROMAN and len(parts) >= 2:
            cur["zet"]["houses"][ROMAN.index(parts[0])] = parts[1]
            continue
        if parts and parts[0] in NAMES and len(parts) >= 2:
            key = NAMES[parts[0]]
            cur["zet"][key] = parts[1]
            if len(parts) >= 3:
                cur["zet_speed"][key] = parts[2].replace(" ", "")
            continue
        k, _, v = s.partition(":")
        k, v = k.strip().lower(), v.strip()
        if k == "дата":
            cur["date"] = v
        elif k == "время":
            cur["time"] = v
        elif k == "пояс":
            cur["utc_offset"] = format_offset(parse_offset(v))
        elif k == "место":
            m = re.match(r"^(.*?),\s*(\S+)\s+(\S+)$", v)
            cur["place"], cur["lat_raw"], cur["lon_raw"] = m.group(1), m.group(2), m.group(3)
            cur["lat"] = round(parse_coord_raw(cur["lat_raw"], "dm"), 6)
            cur["lon"] = round(parse_coord_raw(cur["lon_raw"], "dm"), 6)
    for c in cards:
        c["zet"]["asc"], c["zet"]["mc"] = c["zet"]["houses"][0], c["zet"]["houses"][9]
        c["zet_settings"] = dict(settings)
    return cards


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    argv = argv or sys.argv[1:]
    src = argv[0] if argv else os.path.join(HERE, "reference.txt")
    os.makedirs(REF_DIR, exist_ok=True)
    cards = parse_txt(src)
    for i, c in enumerate(cards, 1):
        with open(os.path.join(REF_DIR, f"card_{i:02d}.json"), "w", encoding="utf-8") as f:
            json.dump(c, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"{len(cards)} cards → {REF_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
