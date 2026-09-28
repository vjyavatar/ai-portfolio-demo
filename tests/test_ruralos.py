import ast,json,re,subprocess
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
import ruralos_site
ROOT=Path(__file__).resolve().parents[1]
@pytest.fixture
def client():
    app=FastAPI()
    @app.get('/')
    def home():return HTMLResponse('stock-home-sentinel')
    @app.get('/api/test-stock')
    def stock():return {'stock':'unchanged'}
    assert ruralos_site.attach_ruralos(app)
    with TestClient(app,base_url='https://celesys.ai') as c:yield c

def test_routes_and_assets(client):
    assert client.get('/').text=='stock-home-sentinel'
    assert client.get('/api/test-stock').json()=={'stock':'unchanged'}
    r=client.get('/ruralos',follow_redirects=False)
    assert r.status_code==307 and r.headers['location']=='https://celesys.ai/ruralos/'
    html=client.get('/ruralos/').text
    assert 'Saathi' in html
    for asset in re.findall(r'(?:src|href)="(/ruralos/[^"?]+)"',html):
        assert client.get(asset).status_code==200,asset
    assert client.get('/ruralos/?language=hi').status_code==200
    assert client.get('/ruralos/?language=te').status_code==200
    assert client.head('/ruralos/').content==b''

def test_manifest_headers_and_offline_scope(client):
    m=client.get('/ruralos/manifest.webmanifest').json()
    assert m['scope']==m['start_url']=='/ruralos/'
    for i in m['icons']:assert client.get(i['src']).status_code==200
    r=client.get('/ruralos/sw.js');assert r.status_code==200
    assert "startsWith('/ruralos/')" in r.text
    assert "k.startsWith('saathi-ruralos-')" in r.text
    assert '/api/' not in r.text
    assert r.headers['cache-control']=='no-cache'
    assert r.headers['x-content-type-options']=='nosniff'
    assert "frame-ancestors 'none'" in r.headers['content-security-policy']

@pytest.mark.parametrize('path',['/ruralosevil','/ruralos/missing','/ruralos/%2e%2e%2fapi.py','/ruralos/.git/config','/ruralos/..%5capi.py'])
def test_missing_and_traversal(client,path):assert client.get(path).status_code==404
@pytest.mark.parametrize('method',['POST','PUT','DELETE','PATCH'])
def test_writes(client,method):assert client.request(method,'/ruralos/').status_code==405

def test_optional_assets_missing(monkeypatch,tmp_path):
    monkeypatch.setattr(ruralos_site,'ASSET_DIRECTORY',tmp_path)
    assert ruralos_site.attach_ruralos(FastAPI()) is False

def test_no_stock_code_changes():
    baseline=subprocess.check_output(['git','show','efce519ff46ac10c4c3f18f70043f54601c0f9d0:start.py'],cwd=ROOT,text=True)
    old=ast.parse(baseline);new=ast.parse((ROOT/'start.py').read_text())
    added=[n for n in new.body if isinstance(n,ast.Try) and any(isinstance(c,ast.ImportFrom) and c.module=='ruralos_site' for c in n.body)]
    assert len(added)==1;new.body.remove(added[0]);assert ast.dump(old)==ast.dump(new)
    for name in ['index.html','api.py','requirements.txt','sw.js','nextstep_site.py']:
        assert (ROOT/name).read_bytes()==subprocess.check_output(['git','show',f'efce519ff46ac10c4c3f18f70043f54601c0f9d0:{name}'],cwd=ROOT)

def test_public_adapter_and_prefix():
    main=(ROOT/'ruralos-src/main.tsx').read_text()
    assert "Response.json({signedIn:false" in main
    assert "location.href=origin+href" in main
    assert "https://rural-family-action-os.vjyrcks.chatgpt.site" in main
    for name in ['family-app.tsx','guided-app.tsx']:
        text=(ROOT/'ruralos-src/app'/name).read_text()
        assert "register('/sw.js')" not in text
        assert "encodeURIComponent('/ruralos/" not in text
