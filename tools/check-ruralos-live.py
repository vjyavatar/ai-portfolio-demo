"""Read-only production smoke checks; no sign-in, forms or transactions."""
import json,re,sys,urllib.request,urllib.error
from pathlib import Path
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args):return None
opener=urllib.request.build_opener(NoRedirect)
def get(path):
 try:r=opener.open('https://celesys.ai'+path,timeout=20)
 except urllib.error.HTTPError as error:r=error
 return r.code,r.headers,r.read().decode()
def run():
 checks=[]
 status,headers,html=get('/ruralos/');assert status==200,'Home unavailable'
 expected=re.search(r'src="(/ruralos/assets/[^\"]+\.js)"',Path('ruralos/index.html').read_text()).group(1)
 assert expected in html,'Live release does not match locally validated bundle'
 checks.append('home_matches_tested_release')
 status,headers,body=get(expected);assert status==200 and len(body)>1000,'Main script unavailable';checks.append('entry_script_available')
 status,headers,_=get('/ruralos/tracking');assert status==303 and headers.get('Location')=='https://rural-family-action-os.vjyrcks.chatgpt.site/tracking';assert 'no-store' in headers.get('Cache-Control','');checks.append('private_tracking_handoff')
 status,_,body=get('/ruralos/manifest.webmanifest');assert status==200 and json.loads(body)['scope']=='/ruralos/';checks.append('install_manifest')
 status,_,_=get('/ruralos/does-not-exist');assert status==404;checks.append('missing_route_404')
 print(json.dumps({'status':'passed','checks':checks,'expectedAsset':expected}))
if __name__=='__main__':
 try:run()
 except Exception as error:print(json.dumps({'status':'failed','reason':str(error)}));sys.exit(1)
