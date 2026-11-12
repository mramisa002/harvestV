"""Point-in-time NDVI validation using explicitly dated CSV inputs.

Observations: district,day,available_at,rain_mm,tmean,tmax,tmin
NDVI: district,division,crop,season,day,ndvi
Cutoffs: district,crop,season,as_of
No claim of actual sowing: NDVI green-up minus a crop-specific lag is a proxy.
"""
import argparse
import csv
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import median
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import CONFIG
from app.scoring import advise, DataUnavailable


def read(path):
    with open(path,encoding='utf-8',newline='') as f: return list(csv.DictReader(f))


def greenup(rows, threshold, lag):
    ordered=sorted(rows,key=lambda r:r['day'])
    for previous,current in zip(ordered,ordered[1:]):
        if float(previous['ndvi'])<threshold<=float(current['ndvi']):
            return date.fromisoformat(current['day'])-timedelta(days=lag)
    return None


def evaluate(observations, ndvi, cutoffs):
    results=[]
    for case in cutoffs:
        as_of=date.fromisoformat(case['as_of']); crop=CONFIG['crops'][case['crop']]
        cutoff=datetime.combine(as_of,datetime.min.time(),tzinfo=timezone.utc)
        history={}
        for r in observations:
            if r['district']!=case['district']: continue
            available=datetime.fromisoformat(r['available_at'])
            if available.tzinfo is None: raise ValueError('available_at must include timezone')
            if available>cutoff or date.fromisoformat(r['day'])>=as_of: continue
            history[date.fromisoformat(r['day'])]={k:float(r[k]) for k in ['rain_mm','tmean','tmax','tmin']}
        subset=[r for r in ndvi if all(r[k]==case[k] for k in ['district','crop','season'])]
        observed=greenup(subset,crop['ndvi_threshold'],crop['ndvi_lag_days'])
        result={**case,'division':subset[0]['division'] if subset else '', 'observed_proxy':observed.isoformat() if observed else '',
                'recommended_start':'','recommended_end':'','offset_days':'','inside_window':'','state':'skipped'}
        try:
            recommendation=advise(as_of,history,CONFIG,case['crop'])
            w=recommendation['best_window']
            if w and observed:
                start=date.fromisoformat(w['start']); end=date.fromisoformat(w['end'])
                center=start+(end-start)//2
                result.update(recommended_start=w['start'],recommended_end=w['end'],offset_days=(observed-center).days,
                              inside_window=int(start<=observed<=end),state='evaluated')
            else: result['state']='no green-up crossing or recommended window'
        except DataUnavailable as exc: result['state']=str(exc)
        results.append(result)
    return results


def report(results, synthetic=False):
    valid=[r for r in results if r['state']=='evaluated']
    lines=['# NDVI backtest', '', '**Synthetic fixture demonstration; not real-world accuracy.**' if synthetic else 'No production accuracy claim without validated point-in-time input data.',
           '', 'Green-up minus a configured lag is a sowing proxy, not a verified planting date.',
           f'Evaluated {len(valid)} of {len(results)} district-seasons. Skipped rows remain in the CSV.', '',
           '| Division | Seasons | Median signed offset (days) | Inside window |','| --- | ---: | ---: | ---: |']
    for division in ['ALL']+sorted({r['division'] for r in valid}):
        group=valid if division=='ALL' else [r for r in valid if r['division']==division]
        if group: lines.append(f"| {division} | {len(group)} | {median(r['offset_days'] for r in group):g} | {sum(r['inside_window'] for r in group)/len(group):.1%} |")
    if not valid: lines.append('| ALL | 0 | unavailable | unavailable |')
    lines+=['', 'No soil moisture is supplied to this baseline backtest; confidence is LOW. Do not tune and evaluate on the same seasons.',
            'Original satellite composites can only localize green-up to an interval; the crossing date is not an exact sowing observation.']
    return '\n'.join(lines)+'\n'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['observations','ndvi','cutoffs','out']: p.add_argument('--'+name,required=True)
    p.add_argument('--synthetic',action='store_true'); a=p.parse_args()
    results=evaluate(read(a.observations),read(a.ndvi),read(a.cutoffs)); dest=Path(a.out); dest.mkdir(parents=True,exist_ok=True)
    if results:
        with (dest/'backtest.csv').open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(results[0])); w.writeheader(); w.writerows(results)
    (dest/'backtest.md').write_text(report(results,a.synthetic),encoding='utf-8')


if __name__=='__main__': main()
