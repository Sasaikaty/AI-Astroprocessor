# zet7 — натал / синастрия / транзиты (откалибровано под ZET 7)
```
python -m zet7 natal a.json                      # digest + топ-15 аспектов (--full: полный натал)
python -m zet7 synastry a.json b.json --top 30   # аспекты A↔B, оверлеи, композит, стихии
python -m zet7 transits a.json                   # сегодня (tz натала) + 60 дней
python -m zet7 transits a.json --date 2026-10-09 # один день, с Луной
python -m zet7 transits a.json --from 2026-10-01 --to 2027-03-01 --orb-scale 0.8
python -m zet7 transits --schema                 # легенда полей
python tests/test_reference.py && python tests/test_modes.py
```
