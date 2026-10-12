"""Opt-in verified-email sessions. No shared-session or email-string authentication.
Requires SMTP and CELESYS_AUTH_SECRET; enable enforcement after validating delivery.
In-memory OTP/session state requires one process; restart safely invalidates sessions.
"""
import hashlib,hmac,json,os,re,secrets,smtplib,ssl,threading,time
from contextvars import ContextVar
from email.message import EmailMessage
from fastapi import APIRouter,Request,HTTPException
from fastapi.responses import JSONResponse
router=APIRouter();identity=ContextVar('celesys_identity',default=None)
_lock=threading.Lock();_codes={};_sessions={};_rates={};_roles=lambda email:{}
COOKIE='__Host-celesys_session';TTL=7200

def configured():return all(os.getenv(k) for k in ('CELESYS_AUTH_SECRET','CELESYS_SMTP_HOST','CELESYS_SMTP_USER','CELESYS_SMTP_PASSWORD','CELESYS_SMTP_FROM')) and len(os.getenv('CELESYS_AUTH_SECRET',''))>=32

def enforced():return os.getenv('CELESYS_AUTH_ENFORCE')=='true'

def signature(value):return hmac.new(os.getenv('CELESYS_AUTH_SECRET','').encode(),value.encode(),hashlib.sha256).hexdigest()

def cleanup(now):
    for store in (_codes,_sessions,_rates):
        for k,v in list(store.items()):
            if v['until']<=now:store.pop(k,None)

def session(token):
    if not configured() or not token or '.' not in token:return None
    key,sig=token.split('.',1)
    if not hmac.compare_digest(signature(key),sig):return None
    with _lock:
        value=_sessions.get(key)
        if not value or value['until']<=time.time():return None
        return dict(email=value['email'],**_roles(value['email']))

def require_user():
    user=identity.get()
    if not user or not user.get('full'):raise HTTPException(401,'Verified authorized sign-in required.')
    return user

def origin_check(request):
    if request.headers.get('origin')!=os.getenv('CELESYS_SITE_ORIGIN','https://celesys.ai'):raise HTTPException(403,'Origin rejected.')

def throttle(request):
    # Remote peer address only; do not trust client-supplied forwarded IP headers.
    now=time.time();key=request.client.host if request.client else 'unknown'
    with _lock:
        cleanup(now)
        if key not in _rates:
            if len(_rates)>=5000:raise HTTPException(429,'Try again later.')
            _rates[key]={'until':now+600,'count':0}
        _rates[key]['count']+=1
        if _rates[key]['count']>20:raise HTTPException(429,'Too many attempts. Retry in ten minutes.')

def send_code(email,code):
    msg=EmailMessage();msg['From']=os.environ['CELESYS_SMTP_FROM'];msg['To']=email;msg['Subject']='Your Celesys sign-in code'
    msg.set_content('Your Celesys sign-in code is '+code+'. It expires in 10 minutes. Do not share it. If you did not request it, ignore this email.')
    with smtplib.SMTP_SSL(os.environ['CELESYS_SMTP_HOST'],int(os.getenv('CELESYS_SMTP_PORT','465')),timeout=15,context=ssl.create_default_context()) as server:
        server.login(os.environ['CELESYS_SMTP_USER'],os.environ['CELESYS_SMTP_PASSWORD']);server.send_message(msg)

async def payload(request):
    raw=b''
    async for chunk in request.stream():
        raw+=chunk
        if len(raw)>2048:raise HTTPException(413,'Request too large.')
    try:data=json.loads(raw)
    except (ValueError,UnicodeError):raise HTTPException(422,'Invalid request.')
    if not isinstance(data,dict):raise HTTPException(422,'Invalid request.')
    return data

@router.get('/api/watchlist/research')
def watchlist_research(request:Request,symbol:str='SPY',region:str='US'):
    user=identity.get()
    allowed=bool(user and user.get('full'))
    if not enforced():allowed=allowed or bool(_roles(request.headers.get('x-celesys-email','').strip().lower()).get('full'))
    if not allowed:raise HTTPException(403,'Authorized account required for watchlist scans.')
    from trading_site import research
    return research(symbol,region)

@router.get('/api/access/status')
def status():
    user=identity.get()
    return dict(configured=configured(),enforced=enforced(),verified=bool(user),access={k:user[k] for k in ('full','trades','dream') if user and k in user})

@router.post('/api/access/start')
async def start(request:Request):
    origin_check(request);throttle(request)
    if not configured():raise HTTPException(503,'Verified sign-in awaits operator email-service setup.')
    data=await payload(request);email=str(data.get('email','')).strip().lower()
    if len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):raise HTTPException(422,'Enter a valid email.')
    now=time.time();key=signature(email)
    with _lock:
        cleanup(now)
        if key in _codes and now-_codes[key]['created']<60:raise HTTPException(429,'Wait one minute before requesting another code.')
        if len(_codes)>=5000:raise HTTPException(429,'Try again later.')
        code=''.join(secrets.choice('0123456789') for _ in range(8))
        _codes[key]={'digest':signature(key+code),'until':now+600,'created':now,'attempts':0}
    # Same public answer whether an email is on the allowlist or not.
    if _roles(email).get('full'):
        from starlette.concurrency import run_in_threadpool
        try:await run_in_threadpool(send_code,email,code)
        except Exception:
            with _lock:_codes.pop(key,None)
            # Preserve the same response for allowed and unknown addresses.
            import logging
            logging.getLogger(__name__).error('Celesys sign-in delivery failed; check SMTP configuration')
    return {'message':'If this account has access, a code will arrive shortly.'}

@router.post('/api/access/confirm')
async def confirm(request:Request):
    origin_check(request);throttle(request)
    if not configured():raise HTTPException(503,'Verified sign-in is not configured.')
    data=await payload(request);email=str(data.get('email','')).strip().lower();code=str(data.get('code',''))
    if len(email)>254 or not re.fullmatch(r'\d{8}',code):raise HTTPException(401,'Invalid or expired code.')
    key=signature(email);now=time.time()
    with _lock:
        cleanup(now);value=_codes.get(key)
        if not value or value['attempts']>=5:raise HTTPException(401,'Invalid or expired code.')
        value['attempts']+=1
        if not hmac.compare_digest(value['digest'],signature(key+code)) or not _roles(email).get('full'):raise HTTPException(401,'Invalid or expired code.')
        _codes.pop(key,None)
        if len(_sessions)>=5000:raise HTTPException(429,'Try again later.')
        nonce=secrets.token_urlsafe(32);_sessions[nonce]={'email':email,'until':now+TTL}
    response=JSONResponse({'verified':True,'access':_roles(email)})
    response.set_cookie(COOKIE,nonce+'.'+signature(nonce),max_age=TTL,secure=True,httponly=True,samesite='strict',path='/');return response

@router.post('/api/access/logout')
def logout(request:Request):
    origin_check(request)
    token=request.cookies.get(COOKIE,'');nonce=token.split('.',1)[0]
    with _lock:_sessions.pop(nonce,None)
    response=JSONResponse({'verified':False});response.delete_cookie(COOKIE,secure=True,httponly=True,samesite='strict',path='/');return response

def attach_access(app,roles,protected):
    global _roles
    _roles=roles;app.include_router(router)
    @app.middleware('http')
    async def access_boundary(request,call_next):
        user=session(request.cookies.get(COOKIE));marker=identity.set(user)
        try:
            tier=protected.get(request.url.path)
            if enforced() and tier and (not user or not user.get(tier)):
                response=JSONResponse({'success':False,'error':'Verified account with this feature is required.'},status_code=403)
            else:response=await call_next(request)
            response.headers['X-Content-Type-Options']='nosniff';response.headers['Referrer-Policy']='same-origin';response.headers['X-Frame-Options']='SAMEORIGIN'
            if request.url.path.startswith('/api/access/') or tier:response.headers['Cache-Control']='no-store'
            return response
        finally:identity.reset(marker)
