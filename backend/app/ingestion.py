"""Only ingestion jobs call NASA. API handlers never import network providers."""
import argparse, asyncio, json, logging, math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import httpx
from types import SimpleNamespace
from .db import connect, query, upsert, get_district, record_run, observations
from .seed import seed

log=logging.getLogger(__name__)
PARAMETERS={'PRECTOTCORR':'rain_mm','T2M':'tmean','T2M_MAX':'tmax','T2M_MIN':'tmin','RH2M':'rh','ALLSKY_SFC_SW_DWN':'solar'}
SOURCES={'power','imerg','smap','ndvi'}

def parse_power(payload):
    data=payload['properties']['parameter']; fill=payload.get('header',{}).get('fill_value',-999)
    days=sorted(set().union(*(set(v) for v in data.values())))
    rows=[]
    for key in days:
        values={}
        for parameter,name in PARAMETERS.items():
            v=data.get(parameter,{}).get(key)
            if v is None or v==fill or not math.isfinite(float(v)) or float(v)<=-900: v=None
            if v is not None:
                v=float(v)
                if name in {'rain_mm','solar'} and v<0: v=None
                if name=='rh' and not 0<=v<=100: v=None
            values[name]=v
        rows.append((datetime.strptime(key,'%Y%m%d').date(), values))
    return rows

def store_rows(db, district, source, rows, timestamp=None):
    if source not in SOURCES: raise ValueError('Unknown source')
    now=datetime.now(timezone.utc)
    for day,values in rows:
        if day>now.date(): raise ValueError('Cannot store future observations')
        source_time=timestamp or datetime.combine(day,datetime.min.time(),tzinfo=timezone.utc)
        if source_time.tzinfo is None: raise ValueError('Source timestamp must include a timezone')
        if source=='smap':
            previous=observations(db,district,day.isoformat(),day.isoformat(),('smap',))
            if previous:
                values={**previous[0]['values'],**values}
        upsert(db,district,day,source,values,source_time)

async def power_fetch(client, district, start, end):
    params={'parameters':','.join(PARAMETERS),'community':'AG','latitude':district.lat,'longitude':district.lon,
            'start':start.strftime('%Y%m%d'),'end':end.strftime('%Y%m%d'),'format':'JSON','time-standard':'UTC'}
    for attempt in range(4):
        try:
            response=await client.get('https://power.larc.nasa.gov/api/temporal/daily/point',params=params)
            response.raise_for_status(); return parse_power(response.json())
        except (httpx.HTTPError,ValueError,KeyError):
            if attempt==3: raise
            await asyncio.sleep(2**attempt)

async def refresh_power(district_id=None, years=0):
    seed(); end=date.today()-timedelta(days=1)
    with connect() as db:
        records=query(db,'SELECT * FROM districts WHERE id=?',(district_id,)).fetchall() if district_id else query(db,'SELECT * FROM districts').fetchall()
        districts=[SimpleNamespace(**dict(r)) for r in records]
        if not districts: raise ValueError('Unknown district')
    async with httpx.AsyncClient(timeout=120) as client:
        for district in districts:
            start=date(end.year-years-1,1,1) if years else end-timedelta(days=45)
            while start<=end:
                stop=min(date(start.year,12,31),end)
                rows=await power_fetch(client,district,start,stop)
                if not rows or not any(v.get('rain_mm') is not None for _,v in rows): raise ValueError('POWER returned no usable rainfall')
                with connect() as db: store_rows(db,district.id,'power',rows)
                log.info('POWER %s %s..%s: %s days',district.id,start,stop,len(rows))
                start=stop+timedelta(days=1)

def validate_normalized(source,values):
    if source not in {'imerg','smap','ndvi'}: raise ValueError('Unknown normalized source')
    required={'imerg':{'rain_mm'},'smap':set(),'ndvi':{'ndvi'}}[source]
    if not required<=values.keys(): raise ValueError(f'{source} requires {required}')
    if source=='smap' and not {'sm_surface','sm_root'} & values.keys(): raise ValueError('SMAP requires surface or root moisture')
    for k,v in values.items():
        if v is None: continue
        if not isinstance(v,(int,float)) or not math.isfinite(v): raise ValueError(f'Invalid value for {k}')
        if k=='rain_mm' and v<0: raise ValueError('Negative rain')
        if k.startswith('sm_') and not 0<=v<=1: raise ValueError('Moisture must be volumetric m3/m3')
        if k=='ndvi' and not -1<=v<=1: raise ValueError('NDVI must already be scaled')

def import_normalized(path):
    """Import QA-filtered extracted Earthdata values. Raw files are never interpreted as point values."""
    seed(); payload=json.loads(Path(path).read_text(encoding='utf-8'))
    with connect() as db:
        for record in payload:
            source=record['source']; values=record['values']; validate_normalized(source,values)
            if not get_district(db,record['district_id']): raise ValueError('Unknown district')
            if not record.get('product') or not record.get('quality_checked'): raise ValueError('Product and QA confirmation required')
            values={**values,'product':record['product'],'quality_checked':True}
            store_rows(db,record['district_id'],source,[(date.fromisoformat(record['day']),values)],datetime.fromisoformat(record['source_timestamp']))
        for source in sorted({r['source'] for r in payload}):
            query(db,'INSERT INTO ingestion_runs VALUES (?,?,?,?)',(source,datetime.now(timezone.utc).isoformat(),1,f'Validated import: {len(payload)} records total'))

def main():
    parser=argparse.ArgumentParser(); sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('power'); p.add_argument('--district'); p.add_argument('--years',type=int,default=0)
    p=sub.add_parser('import'); p.add_argument('path')
    args=parser.parse_args(); logging.basicConfig(level=logging.INFO)
    if args.command=='import': return import_normalized(args.path)
    if not 0<=args.years<=40: parser.error('--years must be 0..40')
    success=0; message=''
    try: asyncio.run(refresh_power(args.district,args.years)); success=1; message='POWER refresh complete'
    except Exception as exc: message=str(exc); raise
    finally:
        record_run('power',success,message)
if __name__=='__main__': main()
