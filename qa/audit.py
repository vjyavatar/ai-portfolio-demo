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
class Document(HTMLParser):
    def __init__(self):super().__init__();self.ids=[];self.assets=[];self.title=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='title':self.title=True
        url=a.get('src') if tag=='script' else a.get('href') if tag=='link' and a.get('rel')=='stylesheet' else None
        if url and url.startswith('/') and not url.startswith('//'):self.assets.append(url)
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
    p=argparse.ArgumentParser();p.add_argument('--live');p.add_argument('--output',default='qa-output');p.add_argument('--skip-tests',action='store_true');a=p.parse_args()
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
        for i,cmd in enumerate(suites):
            try:
                result=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,timeout=180)
                (out/f'suite-{i}.log').write_text(result.stdout+result.stderr)
                record(' '.join(cmd[1:]),'PASS' if result.returncode==0 else 'FAIL',f'Full results: suite-{i}.log')
            except subprocess.TimeoutExpired:record(' '.join(cmd),'FAIL','Timed out after 180 seconds')
    assets=set()
    if a.live:
        base=a.live.rstrip('/')
        def page_check(path):
            try:
                code,kind,body,elapsed=fetch(base,path);doc=Document();doc.feed(body.decode('utf-8','replace'))
                verification=path.startswith('/google') and body.decode('utf-8','replace').strip()=='google-site-verification: '+path[1:]
                ok=code==200 and 'text/html' in kind and (doc.title or verification)
                return path,doc,('PASS' if ok else 'FAIL'),f'HTTP {code}; '+('verified search-engine ownership resource' if verification else f'HTML title {doc.title}')+f'; {elapsed}s',body
            except Exception as e:return path,None,'FAIL',type(e).__name__,b''
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            for path,doc,status,detail,body in pool.map(page_check,pages):
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
        probes += [(f'/api/research-brief?mode={mode}&symbol={sym}&region={region}',validate_brief) for mode,sym,region in [('stock','AAPL','US'),('stock','RELIANCE','IN'),('trading','SPY','US'),('trading','NIFTY','IN')]]
        probes += [(f'/api/existing-option-chain?symbol={sym}&region={region}',validate_chain) for sym,region in [('SPY','US'),('NIFTY','IN')]]
        for path,validator in probes:
            try:
                code,kind,body,elapsed=fetch(base,path)
                status,detail=validator(json.loads(body)) if code==200 else ('FAIL',f'HTTP {code}')
                record('Data '+path,status,detail,seconds=elapsed)
            except Exception as e:record('Data '+path,'FAIL',type(e).__name__)
        for path in ['/api/upstox-login','/api/upstox-status']:
            try:code,*_=fetch(base,path);record('Retired '+path,'PASS' if code==410 else 'FAIL',f'HTTP {code}, expected 410')
            except Exception as e:record('Retired '+path,'FAIL',type(e).__name__)
    else:
        record('Live pages and data','UNVERIFIED','Run with --live https://celesys.ai')
    for feature in ['Actual chart canvases rendered','All 50 menu output correctness','Authorized-user server identity','Voice microphone and audible playback','Independent financial calculation reconciliation']:
        record(feature,'UNVERIFIED','Requires browser/authorized fixtures or independent data; not certified by document/schema checks')
    counts=dict(collections.Counter(c['status'] for c in checks))
    report={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'target':a.live or 'local','summary':counts,'checks':checks,'menus':menus,'routes':routes,'functions':functions,'limits':'PASS applies only to the stated check. Function inventory is not function coverage. No orders, private emails, or full API payloads are recorded.'}
    (out/'report.json').write_text(json.dumps(report,indent=2))
    lines=['# Celesys QA report','',f"Target: {report['target']}",f"Checks: {counts}",'','PASS is scoped to each check. UNVERIFIED is not a pass.','','| Check | Result | Evidence |','|---|---|---|']
    lines += ['| '+c['name'].replace('|','/')+' | '+c['status']+' | '+c['detail'].replace('|','/')+' |' for c in checks]
    lines += ['','## Every menu','', '| Tool | UI access profiles | Functional output |','|---|---|---|']
    lines += ['| '+m['label']+' | '+', '.join(k for k,v in m['access'].items() if v)+' | UNVERIFIED |' for m in menus]
    (out/'report.md').write_text('\n'.join(lines)+'\n');print(json.dumps({'summary':counts,'report':str(out/'report.md'),'menus':len(menus),'routes':len(routes),'functions':len(functions)}))
    return int(counts.get('FAIL',0)>0)
if __name__=='__main__':raise SystemExit(main())
