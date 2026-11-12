"""Pure decision engine. Future weather comes from historical analogues, NEVER a forecast.
WP/FC normalization is relative plant-available moisture, NOT physical saturation.
"""
from datetime import date, timedelta
from statistics import mean

class DataUnavailable(ValueError): pass

def thermal(value, limits):
    a,b,c,d = limits
    if value <= a or value >= d: return 0.0
    if b <= value <= c: return 1.0
    return (value-a)/(b-a) if value < b else (d-value)/(d-c)

def moisture_band(value, band):
    lo,hi = band
    if value <= 0 or value >= 1: return 0.0
    if lo <= value <= hi: return 1.0
    return value/lo if value < lo else (1-value)/(1-hi)

def normalize_moisture(value, wp, fc):
    if wp is None or fc is None or fc <= wp: return None
    return max(0., min(1., (value-wp)/(fc-wp)))

def rain_total(rows, end, days):
    values = [rows.get(end-timedelta(days=i),{}).get('rain_mm') for i in range(days)]
    if any(v is None for v in values): raise DataUnavailable('Recent daily rainfall has gaps; run ingestion again.')
    return sum(values)

def analogues(history, target, today, config, crop):
    """Require complete 14-day analogues from 20 distinct historical years.
    Historical days are strictly earlier than today; no future leakage in backtests.
    """
    samples = []
    for year in sorted({d.year for d in history if d.year < today.year}):
        try: anchor = target.replace(year=year)
        except ValueError: continue
        block = [history.get(anchor+timedelta(days=i)) for i in range(14)]
        if any(r is None or any(r.get(k) is None for k in ('rain_mm','tmax','tmin','tmean')) for r in block): continue
        if anchor+timedelta(days=13) >= today: continue
        dry = longest = 0
        for r in block:
            dry = dry+1 if r['rain_mm'] < config['policy']['dry_day_mm'] else 0
            longest = max(longest,dry)
        risk = (sum(r['rain_mm'] for r in block)>crop['flood_14d_mm'] or
                any(r['tmax']>=crop['thermal'][3] or r['tmin']<=crop['thermal'][0] for r in block) or
                longest>crop['dry_tolerance_days'])
        samples.append({'rain7':sum(r['rain_mm'] for r in block[:7]),'risk':float(risk),
                        'thermal':mean(thermal(r['tmean'],crop['thermal']) for r in block[:3])})
    if len(samples)<config['policy']['minimum_climate_years']:
        raise DataUnavailable('At least 20 complete historical years are required for this sowing window.')
    return {'rain7':mean(s['rain7'] for s in samples),'risk':mean(s['risk'] for s in samples),
            'thermal':mean(s['thermal'] for s in samples),'years':len(samples)}

def windows(candidates, minimum, avoid_score=40):
    groups, current = [], []
    for c in candidates:
        if c['vetoes'] or c['score'] < avoid_score:
            if len(current)>=minimum: groups.append(current)
            current=[]
        else: current.append(c)
    if len(current)>=minimum: groups.append(current)
    # Rank disjoint minimum-length slots; permit fallback in the same long workable period.
    slots=[]
    for group in groups:
        for i in range(len(group)-minimum+1):
            span=group[i:i+minimum]
            slots.append({'start':span[0]['day'],'end':span[-1]['day'],'mean_score':round(mean(c['smoothed_score'] for c in span),1)})
    slots.sort(key=lambda x:(-x['mean_score'],x['start']))
    result=[]
    for w in slots:
        if all(w['end']<p['start'] or w['start']>p['end'] for p in result): result.append(w)
        if len(result)==2: break
    return result

def advise(today, history, config, crop_id, smap=None, horizon=14, lang='en'):
    crop=config['crops'][crop_id]; policy=config['policy']; weights=config['weights']
    recent={d:r for d,r in history.items() if d < today}
    if not recent: raise DataUnavailable('No observations cached. Run POWER ingestion first.')
    last=max(recent); age=(today-last).days
    if age>policy['max_rain_age_days']: raise DataUnavailable('Rain observations are stale. Refresh ingestion before requesting advice.')
    rain3=rain_total(recent,last,3); rain7=rain_total(recent,last,7); rain14=rain_total(recent,last,14)
    rain48=rain_total(recent,last,2)
    lastrow=recent[last]
    if any(lastrow.get(k) is None for k in ('tmax','tmin','tmean')): raise DataUnavailable('Latest temperature observation is incomplete.')
    soil_age=(today-smap['day']).days if smap else None
    soil_known=bool(smap and 0<=soil_age<=policy['max_smap_age_days'] and smap.get('surface') is not None)
    dry=0; d=last
    while d in recent and recent[d].get('rain_mm') is not None and recent[d]['rain_mm']<policy['dry_day_mm']:
        dry+=1; d-=timedelta(days=1)
    candidates=[]
    for i in range(horizon):
        day=today+timedelta(days=i); climate=analogues(recent,day,today,config,crop)
        season=float(crop['calendar'][0]<=day.strftime('%m-%d')<=crop['calendar'][1])
        # No fabricated soil: use a conservative zero contribution when unavailable.
        soil=moisture_band(smap['surface'],crop['soil_band']) if soil_known else 0.
        if rain48>policy['heavy_48h_mm']: soil=min(soil,.3)
        root=smap.get('root') if soil_known else None
        root_day=smap.get('root_day',smap['day']) if soil_known else None
        if root_day is None or not 0<=(today-root_day).days<=policy['max_smap_age_days']:
            root=None
        germ=(.5*moisture_band(root,crop['soil_band'])+.5*min(1,climate['rain7']/crop['expected_rain_7d_mm'])) if root is not None else 0.
        components={'soil':soil,'germination':germ,'thermal':climate['thermal'],'risk':1-climate['risk'],'season':season}
        score=100*sum(weights[k]*v for k,v in components.items())
        vetoes=[]
        # Observed vetoes apply today only. Future days cannot be asserted safe using past weather.
        if i==0:
            if soil_known and smap['surface']>crop['waterlogging_limit']: vetoes.append('soil_wet')
            if age<=1 and lastrow['rain_mm']>crop['heavy_rain_mm']: vetoes.append('heavy_rain')
            if age<=1 and (lastrow['tmax']>=crop['thermal'][3] or lastrow['tmin']<=crop['thermal'][0]): vetoes.append('temperature')
        candidates.append({'day':day.isoformat(),'score':round(score,1),'vetoes':vetoes,'components':components,'basis':'climatology; current soil held constant, no forecast'})
    for i,c in enumerate(candidates):
        c['smoothed_score']=round(mean(x['score'] for x in candidates[max(0,i-1):i+2]),1)
    ranked=windows(candidates,policy['min_window_days'],policy['avoid_score']); best=ranked[0] if ranked else None
    current=candidates[0]
    better=bool(best and 0<(date.fromisoformat(best['start'])-today).days<=7 and best['mean_score']>current['score']+policy['better_window_margin'])
    status='AVOID' if current['vetoes'] or current['score']<policy['avoid_score'] else ('GO' if current['score']>=policy['go_score'] and not better and soil_known and root is not None and age<=1 else 'WAIT')
    disagreement=any(r.get('rain_disagreement',False) for d,r in recent.items() if (last-d).days<7)
    close=len(ranked)>1 and abs(ranked[0]['mean_score']-ranked[1]['mean_score'])<policy['close_window_margin']
    # All future days use climatology; HIGH is deliberately unavailable without forecasts/calibration.
    confidence='LOW' if not soil_known or root is None or age>2 or disagreement or close else 'MEDIUM'
    if lang=='bn':
        reasons=[f'গত ৩ দিনে {rain3:.1f} মিমি এবং ৭ দিনে {rain7:.1f} মিমি বৃষ্টি হয়েছে।','আগামী দিনের হিসাব পুরোনো বছরের তথ্য থেকে করা; এটি আবহাওয়ার পূর্বাভাস নয়।']
        reasons.append('মাটির আর্দ্রতার সাম্প্রতিক তথ্য নেই। জমি পরীক্ষা করুন।' if not soil_known else f'মাটির আর্দ্রতার তথ্য {soil_age} দিন পুরোনো।')
        if current['vetoes']: reasons.append('সাম্প্রতিক বৃষ্টি, তাপমাত্রা বা অতিরিক্ত ভেজা মাটির কারণে এখন বপন এড়িয়ে চলুন।')
        action='স্থানীয় কৃষি কর্মকর্তার সঙ্গে কথা বলে জমি পরীক্ষা করুন; নতুন তথ্য এলে আবার দেখুন।'
        confidence_reason='পুরোনো বছরের গড় ব্যবহার করা হয়েছে; মাটি, বৃষ্টির তথ্য বা কাছাকাছি স্কোরের কারণে অনিশ্চয়তা আছে।' if confidence=='LOW' else 'পুরোনো বছরের তথ্য ব্যবহার করা হয়েছে; বপনের আগে বর্তমান আবহাওয়া ও জমি পরীক্ষা করুন।'
    else:
        reasons=[f'{rain3:.1f} mm of rain in the last 3 days; {rain7:.1f} mm in 7 days.', 'Future dates use historical climate patterns, not a weather forecast.']
        reasons.append('Recent soil moisture is unavailable. Check the field before sowing.' if not soil_known else f'Soil moisture observation is {soil_age} days old; future soil conditions remain unknown.')
        if current['vetoes']: reasons.append('Recent heavy rain, extreme temperature or very wet soil blocks sowing today.')
        action='Check the field and local forecast with an agricultural extension officer; refresh this advice before sowing.'
        flags=[]
        if not soil_known: flags.append('missing or stale surface soil moisture')
        if root is None: flags.append('missing root-zone moisture')
        if age>2: flags.append(f'rain data is {age} days old')
        if disagreement: flags.append('POWER and IMERG disagree')
        if close: flags.append('top windows have similar scores')
        confidence_reason='Uses climatology, not a forecast. '+('; '.join(flags) if flags else 'Fresh observations, but future weather and soil conditions are uncertain.')
    return dict(status=status,today_score=current['score'],best_window=best,next_best_window=ranked[1] if len(ranked)>1 else None,
                reasons=reasons,action=action,confidence=confidence,confidence_reason=confidence_reason,candidates=candidates,
                indicators=dict(rain_3d=rain3,rain_7d=rain7,rain_14d=rain14,dry_spell_days=dry),model_version=config['version'],
                limitations=['Unvalidated crop thresholds; agronomist review required.','WP/FC normalization is approximate relative available moisture, not physical saturation.','NDVI is never a live input.'])
