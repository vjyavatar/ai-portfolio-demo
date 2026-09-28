import copy,json
from datetime import datetime,timezone,timedelta
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
import ruralos_alerts as alerts
NOW=datetime(2026,9,28,20,tzinfo=timezone.utc)

@pytest.fixture
def data():
 # Freeze the original business example for deterministic mutation tests.
 # Newly published records must not be tested against a historical clock,
 # nor accidentally supply the stock evidence a negative test omits.
 catalogue=json.loads(alerts.DATA.read_text())
 seed=next(a for a in catalogue['alerts'] if a['id']=='saginaw-precision-2026-09-28')
 return {'version':1,'alerts':[seed]}

def test_entire_published_catalogue_at_actual_observation_time():
 catalogue=json.loads(alerts.DATA.read_text())
 assert alerts.validate(catalogue,datetime.now(timezone.utc))==catalogue
 for a in catalogue['alerts']:
  assert alerts.status(a,alerts.timestamp(a['reviewBy']))=='Needs recheck'
  assert a['id'] in alerts.poster(a,datetime.now(timezone.utc))

@pytest.fixture
def client():
 from ruralos_site import attach_ruralos
 app=FastAPI();attach_ruralos(app)
 with TestClient(app) as c:yield c

def test_real_evidence_and_dates(data):
 assert alerts.validate(data,NOW)==data
 a=data['alerts'][0]
 assert alerts.status(a,NOW)=='Research lead'
 assert alerts.status(a,alerts.timestamp(a['reviewBy']))=='Needs recheck'

@pytest.mark.parametrize('value',[None,[],{}, {'version':1,'alerts':[None]}])
def test_invalid_catalogue(value):
 with pytest.raises(ValueError):alerts.validate(value,NOW)

@pytest.mark.parametrize('field',alerts.TEXT_FIELDS+('facts','inferences','risks','sources','checkedAt','reviewBy'))
def test_missing_evidence_rejected(data,field):
 del data['alerts'][0][field]
 with pytest.raises((ValueError,KeyError)):alerts.validate(data,NOW)

@pytest.mark.parametrize('url',['javascript:alert(1)','http://unsafe.test','https://user:pass@example.com','https://example.com:999','https://exa mple.com'])
def test_unsafe_links(data,url):
 data['alerts'][0]['sources'][0]['url']=url
 with pytest.raises(ValueError):alerts.validate(data,NOW)

def test_duplicates_and_unsupported_fare_stock_claims(data):
 data['alerts'].append(copy.deepcopy(data['alerts'][0]))
 with pytest.raises(ValueError):alerts.validate(data,NOW)
 data['alerts'].pop()
 for category in ['stock','travel','verified_stock','travel_deal','stock_research']:
  data['alerts'][0]['category']=category
  with pytest.raises(ValueError):alerts.validate(data,NOW)

def test_future_check_and_long_review_window(data):
 a=data['alerts'][0];a['checkedAt']=(NOW+timedelta(days=1)).isoformat()
 with pytest.raises(ValueError):alerts.validate(data,NOW)
 a['checkedAt']=NOW.isoformat();a['reviewBy']=(NOW+timedelta(days=8)).isoformat()
 with pytest.raises(ValueError):alerts.validate(data,NOW)

def test_escaping_no_script_no_public_email(data):
 a=data['alerts'][0];a['title']='<img src=x onerror=alert(1)>';a['sources'][0]['label']='" onclick="alert(1)'
 html=alerts.page({'servedAt':NOW.isoformat(),'alerts':[a]})
 assert '<img' not in html and '&lt;img' in html
 assert html.count('<script')==1 and '<script type="module" src="/ruralos/alerts.js"></script>' in html and 'vjyavatar' not in html
 assert 'Public email subscriptions and phone push are unavailable' in html
 assert 'Owner alerts use a separately authorized research watch' in html

def test_public_routes_and_filters(client):
 r=client.get('/ruralos/alerts/');assert r.status_code==200
 assert 'Saginaw Precision' in r.text and 'Full evidence' in r.text
 assert r.headers['cache-control']=='no-cache'
 assert "frame-ancestors 'none'" in r.headers['content-security-policy']
 assert 'No reviewed alerts' in client.get('/ruralos/alerts/india/').text
 assert client.get('/ruralos/alerts/unknown-country/').status_code==404
 feed=client.get('/ruralos/alerts/feed.json').json()
 assert feed['emailDelivery']==feed['pushDelivery']=='not_connected'
 assert 'servedAt' in feed and feed['alerts'][0]['sources']

@pytest.mark.parametrize('method',['POST','PUT','DELETE','PATCH'])
def test_no_public_publish_or_send(client,method):
 assert client.request(method,'/ruralos/alerts/feed.json').status_code==405
 assert client.request(method,'/ruralos/alerts/').status_code==405

def test_bad_file_fails_closed(client,monkeypatch,tmp_path):
 p=tmp_path/'bad.json';p.write_text('{broken');monkeypatch.setattr(alerts,'DATA',p)
 target=tmp_path/'output'
 for content in ['{broken','[]','x'*256001]:
  p.write_text(content)
  with pytest.raises((ValueError,KeyError,TypeError)):alerts.build(target)
  assert not target.exists()

def test_stock_lead_requires_explicit_financial_gaps(data):
 a=data['alerts'][0];a['category']='stock_research';a['stock']={k:'Not verified' for k in alerts.STOCK_FIELDS}
 assert alerts.validate(data,NOW)
 assert alerts.status(a,NOW)=='Research lead'
 assert 'Not verified' in alerts.poster(a,NOW)
 del a['stock']['valuationBasis']
 with pytest.raises(ValueError):alerts.validate(data,NOW)

def test_travel_evidence_and_short_freshness(data):
 # Synthetic test fixture only; never published as an observed deal.
 a=data['alerts'][0];a['category']='travel_deal';a['checkedAt']=NOW.isoformat();a['reviewBy']=(NOW+timedelta(minutes=30)).isoformat()
 a['travel']={k:'test fixture' for k in alerts.TRAVEL_FIELDS};a['travel'].update(providerUrl='https://example.com',total=123.45,currency='INR',liveAvailabilityChecked=True,departureDate='2026-10-10',returnDate=None)
 assert alerts.validate(data,NOW)
 assert alerts.status(a,NOW)=='Fare snapshot'
 assert '123.45 INR' in alerts.poster(a,NOW)
 a['travel']['liveAvailabilityChecked']=False
 with pytest.raises(ValueError):alerts.validate(data,NOW)
 a['travel']['liveAvailabilityChecked']=True;a['reviewBy']=(NOW+timedelta(hours=2)).isoformat()
 with pytest.raises(ValueError):alerts.validate(data,NOW)
 a['reviewBy']=(NOW+timedelta(minutes=30)).isoformat();a['travel']['total']=float('nan')
 with pytest.raises(ValueError):alerts.validate(data,NOW)
