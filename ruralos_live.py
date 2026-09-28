"""Bounded, public read-only feeds. Never fetch user-supplied URLs or private IDs."""
import asyncio,copy,math,time
from datetime import datetime,timezone
from typing import Literal
import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse
router=APIRouter()
STATIONS={'VIDP':'Delhi airport','VABB':'Mumbai airport','VOHS':'Hyderabad airport','VOBL':'Bengaluru airport','VOMM':'Chennai airport','VECC':'Kolkata airport','VOTV':'Thiruvananthapuram airport','VAAH':'Ahmedabad airport'}
URLS={'weather':'https://aviationweather.gov/api/data/metar?ids='+','.join(STATIONS)+'&format=json','earthquakes':'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson'}
SOURCES={'weather':'https://aviationweather.gov/data/api/','earthquakes':'https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php'}
_cache={};_locks={key:asyncio.Lock() for key in URLS};_failed={}
def number(v):
    return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def normalize(kind,data,now):
    rows=[]
    if kind=='weather':
        if not isinstance(data,list):raise ValueError('Invalid weather response')
        for item in data:
            station=item.get('icaoId');observed=item.get('obsTime');temp=item.get('temp')
            if station not in STATIONS or not number(observed) or not number(temp) or observed>now+300:continue
            rows.append({'id':station,'name':STATIONS[station],'temperatureC':temp,'observedAt':int(observed)*1000,'outdated':now-observed>10800})
        if not rows:raise ValueError('No current station observations returned')
        return {'items':rows,'scope':'Airport observations only; not village weather or a forecast. Do not use for crop, medical or travel-safety decisions.','generatedAt':None}
    if not isinstance(data,dict) or not isinstance(data.get('features'),list):raise ValueError('Invalid earthquake response')
    generated=data.get('metadata',{}).get('generated')
    if not number(generated) or generated>now*1000+300000:raise ValueError('Invalid feed time')
    for feature in data['features']:
        coords=feature.get('geometry',{}).get('coordinates',[]);p=feature.get('properties',{})
        if len(coords)<2 or not all(number(x) for x in coords[:2]):continue
        lon,lat=coords[:2]
        if not (6<=lat<=38 and 68<=lon<=98):continue
        if not number(p.get('mag')) or not number(p.get('time')):continue
        rows.append({'id':str(feature.get('id',''))[:80],'name':str(p.get('place','Location unavailable'))[:180],'magnitude':p['mag'],'observedAt':p['time']})
    return {'items':sorted(rows,key=lambda r:r['observedAt'],reverse=True)[:30],'generatedAt':generated,'scope':'Reported magnitude 2.5+ events in the past-day feed within 6–38°N, 68–98°E. Includes neighbouring countries. Not predictions or an emergency alert service; absence of reports does not prove safety.'}
async def download(kind):
    async with httpx.AsyncClient(timeout=8,follow_redirects=False) as client:
        async with client.stream('GET',URLS[kind],headers={'Accept':'application/json','User-Agent':'SaathiPublicInfo/1.0'}) as response:
            response.raise_for_status();body=bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body)>2000000:raise ValueError('Feed too large')
    import json
    return json.loads(body)
def envelope(kind,error=False):
    now=time.time();cached=_cache.get(kind)
    if not cached:return {'status':'unavailable','source':SOURCES[kind],'retrievedAt':None,'items':[],'message':'The source is unavailable. No live result can be shown.'}
    saved,payload=cached;result=copy.deepcopy(payload);age=now-saved;generated=result.get('generatedAt');old=bool(generated and now*1000-generated>900000) or (kind=='weather' and all(i['outdated'] for i in result['items']))
    result.update(status='stale' if error or age>600 or old else 'recent',source=SOURCES[kind],retrievedAt=int(saved*1000),cacheAgeSeconds=int(age),message='Previously retrieved data. Refresh failed or the source is old.' if error or age>600 or old else 'Recently retrieved public data; not continuous tracking.')
    return result
@router.get('/ruralos-data/{kind}')
async def feed(kind:Literal['weather','earthquakes']):
    now=time.time()
    if kind in _cache and now-_cache[kind][0]<300:return JSONResponse(envelope(kind),headers={'Cache-Control':'no-store'})
    if now-_failed.get(kind,0)<60:return JSONResponse(envelope(kind,True),headers={'Cache-Control':'no-store'})
    async with _locks[kind]:
        now=time.time()
        if kind in _cache and now-_cache[kind][0]<300:return JSONResponse(envelope(kind),headers={'Cache-Control':'no-store'})
        if now-_failed.get(kind,0)<60:return JSONResponse(envelope(kind,True),headers={'Cache-Control':'no-store'})
        try:_cache[kind]=(now,normalize(kind,await download(kind),now));_failed.pop(kind,None)
        except (httpx.HTTPError,ValueError,TypeError,KeyError,AttributeError):
            _failed[kind]=now
            return JSONResponse(envelope(kind,True),headers={'Cache-Control':'no-store'})
    return JSONResponse(envelope(kind),headers={'Cache-Control':'no-store'})
