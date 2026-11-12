from contextlib import asynccontextmanager
from datetime import date, timedelta
from typing import Literal
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path
from .db import connect, query, get_district, observations
from .seed import seed
from .settings import CORS_ORIGINS
from .config import CONFIG
from .scoring import advise, normalize_moisture, DataUnavailable
from .schemas import Advisory
from .user_data import router as user_router, initialize_user_data

@asynccontextmanager
async def lifespan(app):
    seed()
    initialize_user_data()
    yield

app=FastAPI(title='HarvestV advisory API',version=CONFIG['version'],lifespan=lifespan,
 description='Cache-only, experimental decision support. Advice does not replace local DAE extension officers. All thresholds need agronomist review.')
app.add_middleware(CORSMiddleware,allow_origins=[s.strip() for s in CORS_ORIGINS],allow_methods=['GET','POST','PUT'],allow_headers=['Content-Type','X-Device-Token'])
app.include_router(user_router)

def district_or_404(db, district):
    row=get_district(db,district)
    if row is None: raise HTTPException(404,detail={'code':'unknown_district','message':'Choose a district from /api/v1/districts.'})
    return row

@app.get('/health')
def health():
    with connect() as db:
        latest={s:query(db,'SELECT MAX(finished_at) AS t FROM ingestion_runs WHERE source=? AND success=1',(s,)).fetchone()['t'] for s in ['power','imerg','smap','ndvi']}
        failures=query(db,'SELECT * FROM ingestion_runs WHERE success=0 ORDER BY finished_at DESC LIMIT 4').fetchall()
    return {'status':'ok','advisory_ready':False if latest['power'] is None else 'depends_on_district_data',
            'last_successful_ingestion':latest,'recent_failures':[dict(r) for r in failures]}

@app.get('/api/v1/districts')
def districts():
    with connect() as db:
        rows=query(db,'SELECT * FROM districts ORDER BY name').fetchall()
        return [{**dict(d),'coordinate_method':'Approximate district-town point, not official centroid'} for d in rows]

@app.get('/api/v1/crops')
def crops(): return [{'id':k,**v,'review_status':'TODO: agronomist review'} for k,v in CONFIG['crops'].items()]

@app.get('/api/v1/conditions')
def conditions(district: str=Query(min_length=2,max_length=60), days:int=Query(30,ge=1,le=90)):
    today=date.today()
    with connect() as db:
        district_or_404(db,district)
        rows=observations(db,district,(today-timedelta(days=days)).isoformat(),today.isoformat())
        if not rows: raise HTTPException(503,detail={'code':'data_missing','message':'No recent observations cached. Run ingestion.'})
        return {'district':district,'series':[{k:v for k,v in {**r,'data_age_days':(today-date.fromisoformat(r['day'])).days}.items() if k!='payload'} for r in rows], 'basis':'observations, not a forecast'}

@app.get('/api/v1/advisory', response_model=Advisory)
def advisory(district:str=Query(min_length=2,max_length=60),crop:Literal['wheat','mustard','lentil','potato']='wheat',
             lang:Literal['en','bn']='en',target_window_days:int=Query(14,ge=3,le=14)):
    today=date.today(); freshness={s:None for s in ['power','imerg','smap']}; history={}; smap=None
    soil_layers={}
    with connect() as db:
        d=district_or_404(db,district)
        # NDVI excluded from live advisory at query level.
        rows=observations(db,district,end=(today-timedelta(days=1)).isoformat())
        for r in rows:
            day=date.fromisoformat(r['day']); source=r['source']
            if freshness[source] is None or day>freshness[source]: freshness[source]=day
            if source=='power': history[day]=dict(r['values'])
        for r in rows:
            day=date.fromisoformat(r['day']); v=r['values']
            if r['source']=='imerg' and v.get('rain_mm') is not None:
                h=history.setdefault(day,{})
                if h.get('rain_mm') is not None: h['rain_disagreement']=abs(h['rain_mm']-v['rain_mm'])>CONFIG['policy']['disagreement_mm']
                h['rain_mm']=v['rain_mm']
            elif r['source']=='smap':
                for layer,key in [('surface','sm_surface'),('root','sm_root')]:
                    if v.get(key) is not None:
                        soil_layers[layer]=(day,normalize_moisture(v[key],d['wilting_point'],d['field_capacity']))
        if 'surface' in soil_layers:
            smap={'day':soil_layers['surface'][0],'surface':soil_layers['surface'][1],
                  'root':soil_layers.get('root',(None,None))[1],'root_day':soil_layers.get('root',(None,None))[0]}
        try: result=advise(today,history,CONFIG,crop,smap,target_window_days,lang)
        except DataUnavailable as exc: raise HTTPException(503,detail={'code':'data_unavailable','message':str(exc),'message_bn':'প্রয়োজনীয় তথ্য নেই বা পুরোনো। নতুন তথ্য সংগ্রহের পর আবার চেষ্টা করুন।','data_freshness':freshness})
        return {'district':d['name'],'district_id':d['id'],'crop':crop,**result,'data_freshness':freshness,
                'soil_estimate_method':d['estimate_method'],'advisory_type':'experimental decision support, not validated farm instructions'}

@app.get('/demo',include_in_schema=False)
def demo():
    return FileResponse(Path(__file__).resolve().parents[2]/'frontend/demo/index.html')
