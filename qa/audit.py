#!/usr/bin/env python3
"""Bounded, read-only QA coordinator. No emails, orders, LLM calls or credentials.
Run from repository root: python qa/audit.py --live https://celesys.ai
Reports distinguish code tests, document availability and actual data evidence.
"""
import argparse,ast,collections,concurrent.futures,datetime,hashlib,json,math,re,subprocess,sys,time
from pathlib import Path
from html.parser import HTMLParser
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from urllib.parse import urlsplit,urljoin
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from qa.gaps import track_gaps
class Document(HTMLParser):
    def __init__(self):super().__init__();self.ids=[];self.assets=[];self.title=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='title':self.title=True
        url=a.get('src') if tag=='script' else a.get('href') if tag=='link' and a.get('rel')=='stylesheet' else None
        if url and url.startswith('/') and not url.startswith('//'):self.assets.append(url)
def validate_document(path,code,kind,body,doc):
    # Known gated document: denial is expected without an authorized account.
    if path=='/today' and code in (401,403):
        return 'UNVERIFIED',f'HTTP {code}; expected anonymous denial; signed-in document requires authorized verification'
    verification=path.startswith('/google') and body.decode('utf-8','replace').strip()=='google-site-verification: '+path[1:]
    ok=code==200 and 'text/html' in kind and (doc.title or verification)
    return ('PASS' if ok else 'FAIL'),f'HTTP {code}; '+('verified search-engine ownership resource' if verification else f'HTML title {doc.title}')

def validate_brief(data):
    required=['assessment','evidence','counterargument','missing_data','next_check']
    if not isinstance(data,dict) or any(k not in data for k in required):return 'FAIL','Five-part brief schema missing'
    facts=data['evidence']
    if not isinstance(facts,list) or not facts:return 'FAIL','No usable evidence; HTTP 200 is insufficient'
    if any(not isinstance(f,dict) or not f.get('source') or f.get('value') is None for f in facts):return 'FAIL','Evidence missing value or source'
    return 'PASS',f'{len(facts)} source-labelled facts; financial correctness and freshness require separate verification'
def validate_chain(data):
    if not isinstance(data,dict) or not isinstance(data.get('rows'),list):return 'FAIL','Chain schema missing'
    rows=data['rows']
    if data.get('status')!='SNAPSHOT':return 'UNVERIFIED','Feed unavailable; no working live option chain verified'
    if not rows:return 'FAIL','Snapshot claimed without contracts'
    strikes=[r.get('strike') for r in rows]
    if not data.get('expiry') or any(not isinstance(x,(int,float)) or not math.isfinite(x) or x<=0 for x in strikes):return 'FAIL','Invalid expiry or strike'
    if len(set(strikes))!=len(strikes):return 'FAIL','Duplicate strikes'
    return 'PASS',f'{len(rows)} strikes; snapshot structure only, quote freshness not certified'
def validate_trading(data,symbol,region,now=None):
    """Validate observed evidence, never profitability or upstream real-time entitlement."""
    now=time.time() if now is None else now
    def finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
    if not isinstance(data,dict) or data.get('symbol')!=symbol or data.get('region')!=region:
        return 'FAIL','Trading response symbol/market mismatch'
    if data.get('source')!='Yahoo Finance chart' or data.get('currency')!=('INR' if region=='IN' else 'USD'):
        return 'FAIL','Trading source or currency is unverified'
    verdict=data.get('verdict');candidate=verdict in ('LONG_RESEARCH','BEARISH_RESEARCH')
    if verdict not in ('WAIT','LONG_RESEARCH','BEARISH_RESEARCH'):return 'FAIL','Unknown trading verdict'
    start,end=data.get('session_start'),data.get('session_end')
    known=finite(start) and finite(end) and 0<end-start<=86400
    opened=known and start<=now<end
    quote,bar=data.get('quote_time'),data.get('bar_close_time')
    fresh=finite(quote) and finite(bar) and 0<=now-quote<=300 and 0<=now-bar<=300 and quote>=bar
    price=data.get('price');price_ok=finite(price) and price>0
    provider=data.get('provider_status') or {}
    received=isinstance(provider,dict) and provider.get('code')=='RESPONSE_RECEIVED'
    stale_cache=bool(data.get('stale_cache') or provider.get('stale_cache'))
    if stale_cache:
        if candidate or data.get('paper_eligible') or data.get('scenario'):
            return 'FAIL','Last-known outage snapshot improperly offers a trading candidate or scenario'
        return 'UNVERIFIED','Last-known cached chart retained; current feed and trading readiness are not verified'
    if candidate:
        if not (received and opened and data.get('market_status')=='OPEN' and fresh and price_ok):
            return 'FAIL','Candidate without verified open session, source response, price and fresh quote/closed bar'
        bars=data.get('bars');stages=data.get('stages')
        if not isinstance(bars,list) or len(bars)<21 or not isinstance(stages,list):
            return 'FAIL','Candidate lacks closed-bar strategy evidence'
        gates={s.get('name'):s.get('status') for s in stages if isinstance(s,dict)}
        if any(gates.get(name)!='pass' for name in ('Data steward','Session guard','Trend analyst','Setup analyst','Risk critic','Quote guard')):
            return 'FAIL','Candidate has missing or failed strategy guards'
        return 'PASS','Open-session research candidate with fresh source quote and closed bar; performance not validated'
    if not received:return 'UNVERIFIED','Provider unavailable or cooling down; WAIT is safe but live feed is not verified'
    if not known:return 'UNVERIFIED','WAIT with unverified session; not classified as a closed market'
    if not opened:
        if data.get('market_status')=='OPEN':return 'FAIL','Response labels an ended or future session OPEN'
        return 'PASS','Closed-session WAIT; live freshness is not certified outside the session'
    if data.get('market_status')!='OPEN':return 'FAIL','Response session state contradicts its source session times'
    if not (fresh and price_ok):return 'UNVERIFIED','Open-session WAIT; fresh quote/closed-bar evidence unavailable'
    return 'PASS','Open-session WAIT with fresh source evidence; no aligned candidate is required'

def trading_probes(regions):
    return [(f'/api/trading-desk/research?symbol={symbol}&region={region}',
             lambda data,symbol=symbol,region=region:validate_trading(data,symbol,region))
            for region,symbol in [('IN','RELIANCE'),('US','SPY')] if region in regions]

def source_inventory():
    routes=[];functions=[];pages={'/','/research','/today','/trading/','/options/india','/options/us'}
    for path in sorted(ROOT.glob('*.py')):
        try:tree=ast.parse(path.read_text())
        except SyntaxError as e:
            functions.append({'file':path.name,'function':'<file parse>','line':e.lineno,'status':'FAIL','reason':'Python syntax error; may be a non-runtime snippet'})
            continue
        for n in ast.walk(tree):
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
                functions.append({'file':path.name,'function':n.name,'line':n.lineno,'status':'UNVERIFIED'})
                for d in n.decorator_list:
                    if isinstance(d,ast.Call) and isinstance(d.func,ast.Attribute) and d.func.attr in ('get','post','put','patch','delete') and d.args and isinstance(d.args[0],ast.Constant) and isinstance(d.args[0].value,str):
                        route=d.args[0].value;routes.append({'file':path.name,'method':d.func.attr.upper(),'path':route,'status':'UNVERIFIED'})
                        if d.func.attr=='get' and '{' not in route and any(k.arg=='response_class' and isinstance(k.value,ast.Name) and k.value.id=='HTMLResponse' for k in d.keywords):pages.add(route)
            if path.name=='discovery_site.py' and isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='GUIDES' for t in n.targets):pages.update('/learn/'+x for x in ast.literal_eval(n.value))
    return sorted(pages),routes,functions
def fetch(base,path):
    start=time.monotonic()
    req=Request(base+path,headers={'User-Agent':'Celesys-ReadOnly-QA/1.0','Cache-Control':'no-cache'})
    try:
        with urlopen(req,timeout=80) as r:return r.status,r.headers.get('Content-Type',''),r.read(12000000),round(time.monotonic()-start,2)
    except HTTPError as e:return e.code,e.headers.get('Content-Type',''),e.read(2000),round(time.monotonic()-start,2)
def main():
    p=argparse.ArgumentParser();p.add_argument('--live');p.add_argument('--live-data-only',action='store_true',help='Bounded underlying probes only; no page crawl or test suites');p.add_argument('--region',choices=['IN','US','both'],default='both');p.add_argument('--output',default='qa-output');p.add_argument('--skip-tests',action='store_true');p.add_argument('--previous',help='Previous report.json from the same target, for regression memory');a=p.parse_args()
    if a.live_data_only and not a.live:p.error('--live-data-only requires --live')
    if a.live_data_only:a.skip_tests=True
    previous=json.loads(Path(a.previous).read_text()) if a.previous else None
    if a.live:
        u=urlsplit(a.live)
        if u.scheme not in ('http','https') or u.hostname not in ('celesys.ai','localhost','127.0.0.1') or u.query or u.username: p.error('Use the owned celesys.ai site or a local test server')
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True);checks=[]
    def record(name,status,detail,**extra):checks.append(dict(name=name,status=status,detail=detail,**extra))
    pages,routes,functions=source_inventory()
    for f in functions:
        if f['status']=='FAIL':record('Source '+f['file'],'UNVERIFIED',f['reason'])
    menus=json.loads(subprocess.check_output(['node','qa/menu-inventory.cjs'],cwd=ROOT,text=True))
    if not a.skip_tests:
        suites=[['npm','run','build']]+[[sys.executable,'-m','unittest','discover','-s','tests','-p',pattern] for pattern in ['test_existing_engines.py','test_workspace_backend.py','test_discovery.py','test_trading_*.py','test_qa_audit.py','test_secure_trading.py']]
        suites.append([sys.executable,'-m','unittest','discover','-s','qa','-p','test_*.py'])
        for i,cmd in enumerate(suites):
            try:
                result=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,timeout=180)
                (out/f'suite-{i}.log').write_text(result.stdout+result.stderr)
                record(' '.join(cmd[1:]),'PASS' if result.returncode==0 else 'FAIL',f'Full results: suite-{i}.log')
            except subprocess.TimeoutExpired:record(' '.join(cmd),'FAIL','Timed out after 180 seconds')
    if a.skip_tests:record('Regression suites','UNVERIFIED','Skipped by --skip-tests; prior passing suites are not evidence for this run')
    assets=set()
    if a.live:
        base=a.live.rstrip('/')
        def page_check(path):
            try:
                code,kind,body,elapsed=fetch(base,path);doc=Document();doc.feed(body.decode('utf-8','replace'))
                status,detail=validate_document(path,code,kind,body,doc)
                return path,doc,status,detail+f'; {elapsed}s',body
            except Exception as e:return path,None,'FAIL',type(e).__name__,b''
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            for path,doc,status,detail,body in pool.map(page_check,[] if a.live_data_only else pages):
                record('Page '+path,status,detail,scope='Document response only; browser interactions separate')
                if doc:
                    assets.update(doc.assets)
                    duplicates=[k for k,v in collections.Counter(doc.ids).items() if v>1]
                    record('Unique IDs '+path,'FAIL' if duplicates else 'PASS',', '.join(duplicates[:10]) or 'No duplicate IDs')
                if path=='/':
                    text=body.decode('utf-8','replace')
                    record('Original chart entry visible','PASS' if re.search(r'<section id="ws-account"[^>]*>',text) and not re.search(r'<section id="ws-account"[^>]*\bhidden',text) else 'FAIL','Original report form must be exposed on homepage')
        for path in sorted(assets):
            try:
                code,kind,body,elapsed=fetch(base,path)
                record('Asset '+path,'PASS' if code==200 and body and 'text/html' not in kind else 'FAIL',f'HTTP {code}; {len(body)} bytes')
            except Exception as e:record('Asset '+path,'FAIL',type(e).__name__)
        probes=[('/health',lambda d:('PASS','Service healthy') if d.get('status')=='healthy' else ('FAIL','Unhealthy service'))]
        if not a.live_data_only:probes += [(f'/api/research-brief?mode={mode}&symbol={sym}&region={region}',validate_brief) for mode,sym,region in [('stock','AAPL','US'),('stock','RELIANCE','IN'),('trading','SPY','US'),('trading','NIFTY','IN')]]
        if not a.live_data_only:probes += [(f'/api/existing-option-chain?symbol={sym}&region={region}',validate_chain) for sym,region in [('SPY','US'),('NIFTY','IN')]]
        probes += trading_probes(['IN','US'] if a.region=='both' else [a.region])
        for index,(path,validator) in enumerate(probes):
            if index>0 and path.startswith('/api/'):time.sleep(20) # Respect shared upstream pacing; no immediate retries.
            try:
                code,kind,body,elapsed=fetch(base,path)
                status,detail=validator(json.loads(body)) if code==200 else ('FAIL',f'HTTP {code}')
                record('Data '+path,status,detail,seconds=elapsed)
            except Exception as e:record('Data '+path,'FAIL',type(e).__name__)
        for path in ([] if a.live_data_only else ['/api/upstox-login','/api/upstox-status']):
            try:code,*_=fetch(base,path);record('Retired '+path,'PASS' if code==410 else 'FAIL',f'HTTP {code}, expected 410')
            except Exception as e:record('Retired '+path,'FAIL',type(e).__name__)
    else:
        record('Live pages and data','UNVERIFIED','Run with --live https://celesys.ai')
    for feature in ['Actual chart canvases rendered','All 50 menu output correctness','Authorized-user server identity','Voice microphone and audible playback','Independent financial calculation reconciliation']:
        record(feature,'UNVERIFIED','Requires browser/authorized fixtures or independent data; not certified by document/schema checks')
    counts=dict(collections.Counter(c['status'] for c in checks))
    report={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'target':a.live or 'local','summary':counts,'checks':checks,'menus':menus,'routes':routes,'functions':functions,'limits':'PASS applies only to the stated check. Function inventory is not function coverage. No orders, private emails, or full API payloads are recorded.'}
    report['gaps']=track_gaps(checks,previous,target=report['target'],observed_at=report['created_at'])
    (out/'report.json').write_text(json.dumps(report,indent=2))
    lines=['# Celesys QA report','',f"Target: {report['target']}",f"Checks: {counts}",'','PASS is scoped to each check. UNVERIFIED is not a pass.','','| Check | Result | Evidence |','|---|---|---|']
    lines += ['| '+c['name'].replace('|','/')+' | '+c['status']+' | '+c['detail'].replace('|','/')+' |' for c in checks]
    lines += ['','## Tracked gaps','','A check closes only when the same check passes against the same target. Missing checks remain unverified.','','| Check | State | Evidence |','|---|---|---|']
    lines += ['| '+g['check'].replace('|','/')+' | '+g['status']+' | '+g['evidence'].replace('|','/')+' |' for g in report['gaps']]
    lines += ['','## Every menu','', '| Tool | UI access profiles | Functional output |','|---|---|---|']
    lines += ['| '+m['label']+' | '+', '.join(k for k,v in m['access'].items() if v)+' | UNVERIFIED |' for m in menus]
    (out/'report.md').write_text('\n'.join(lines)+'\n');print(json.dumps({'summary':counts,'report':str(out/'report.md'),'menus':len(menus),'routes':len(routes),'functions':len(functions)}))
    return int(counts.get('FAIL',0)>0)
if __name__=='__main__':raise SystemExit(main())
