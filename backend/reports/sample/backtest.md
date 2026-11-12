# NDVI backtest

**Synthetic fixture demonstration; not real-world accuracy.**

Green-up minus a configured lag is a sowing proxy, not a verified planting date.
Evaluated 1 of 1 district-seasons. Skipped rows remain in the CSV.

| Division | Seasons | Median signed offset (days) | Inside window |
| --- | ---: | ---: | ---: |
| ALL | 1 | 1 | 100.0% |
| Dhaka | 1 | 1 | 100.0% |

No soil moisture is supplied to this baseline backtest; confidence is LOW. Do not tune and evaluate on the same seasons.
Original satellite composites can only localize green-up to an interval; the crossing date is not an exact sowing observation.
