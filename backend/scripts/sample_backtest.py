"""Generate a reproducible SYNTHETIC report, never an agricultural accuracy claim."""
from datetime import date,timedelta
from pathlib import Path
from backtest_ndvi import evaluate,report
import csv

today=date(2026,11,12); start=date(2004,1,1)
observations=[]
for i in range((today-start).days):
    d=start+timedelta(days=i)
    observations.append(dict(district='dhaka',day=d.isoformat(),available_at=(d+timedelta(days=1)).isoformat()+'T00:00:00+00:00',
                             rain_mm='2',tmean='20',tmax='26',tmin='12'))
ndvi=[dict(district='dhaka',division='Dhaka',crop='wheat',season='2026-rabi',day='2026-11-01',ndvi='.15'),
      dict(district='dhaka',division='Dhaka',crop='wheat',season='2026-rabi',day='2026-11-28',ndvi='.50')]
cases=[dict(district='dhaka',crop='wheat',season='2026-rabi',as_of=today.isoformat())]
results=evaluate(observations,ndvi,cases)
dest=Path(__file__).resolve().parents[1]/'reports/sample'; dest.mkdir(parents=True,exist_ok=True)
with (dest/'backtest.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(results[0])); w.writeheader(); w.writerows(results)
(dest/'backtest.md').write_text(report(results,synthetic=True),encoding='utf-8')
print('Wrote synthetic demonstration report; no real-world accuracy claim.')
