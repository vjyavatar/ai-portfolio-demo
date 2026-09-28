import asyncio,time,json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
import ruralos_live as live
@pytest.fixture(autouse=True)
def reset():
 live._cache.clear();live._failed.clear()
 for key in live._locks:live._locks[key]=asyncio.Lock()
@pytest.fixture
def client():
 app=FastAPI();app.include_router(live.router)
 with TestClient(app) as c:yield c

def weather(now=None):return [{'icaoId':'VOHS','obsTime':time.time() if now is None else now,'temp':28}]
def test_weather_validation():
 now=time.time();r=live.normalize('weather',weather(),now);assert r['items'][0]['temperatureC']==28
 assert live.normalize('weather',weather(now-20000),now)['items'][0]['outdated']
 for bad in [{},[],[{'icaoId':'EVIL','obsTime':now,'temp':28}],[{'icaoId':'VOHS','obsTime':now,'temp':float('nan')}]]:
  with pytest.raises(ValueError):live.normalize('weather',bad,now)
def test_earthquake_scope_empty_not_all_clear():
 now=time.time();f=lambda lon,lat:{'id':'x','geometry':{'coordinates':[lon,lat]},'properties':{'mag':3,'time':now*1000,'place':'Test'}}
 r=live.normalize('earthquakes',{'metadata':{'generated':now*1000},'features':[f(78,18),f(-120,40)]},now)
 assert len(r['items'])==1 and 'neighbouring' in r['scope']
def test_cache_and_no_store(client,monkeypatch):
 calls=[]
 async def download(kind):calls.append(kind);return weather()
 monkeypatch.setattr(live,'download',download)
 for _ in range(5):
  r=client.get('/ruralos-data/weather');assert r.status_code==200;assert r.json()['status']=='recent';assert r.headers['cache-control']=='no-store'
 assert calls==['weather']
def test_failure_not_fake_live_and_backoff(client,monkeypatch):
 calls=[]
 async def fail(kind):calls.append(kind);raise ValueError('bad upstream')
 monkeypatch.setattr(live,'download',fail)
 for _ in range(4):assert client.get('/ruralos-data/weather').json()['status']=='unavailable'
 assert len(calls)==1
 now=time.time();live._cache['weather']=(now-700,live.normalize('weather',weather(),now))
 assert client.get('/ruralos-data/weather').json()['status']=='stale'
def test_unknown_source_and_no_write(client):
 assert client.get('/ruralos-data/internal').status_code==422
 assert client.post('/ruralos-data/weather').status_code==405
 assert client.get('/ruralos-data/http://localhost').status_code==404
def test_single_fetch_for_concurrent_callers(monkeypatch):
 calls=[]
 async def download(kind):calls.append(kind);await asyncio.sleep(.01);return weather()
 monkeypatch.setattr(live,'download',download)
 async def run():return await asyncio.gather(*[live.feed('weather') for _ in range(20)])
 assert len(asyncio.run(run()))==20 and len(calls)==1
def test_stale_source_time():
 now=time.time();live._cache['earthquakes']=(now,{'generatedAt':(now-3600)*1000,'items':[]})
 assert live.envelope('earthquakes')['status']=='stale'
