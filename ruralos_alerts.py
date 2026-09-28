"""Reviewed public alerts. No sending, anonymous writes, household data or live prices."""
import json
import re
import math
from datetime import datetime, timezone, timedelta
from html import escape
from pathlib import Path
from urllib.parse import urlsplit, quote

DATA = Path(__file__).resolve().parent / 'data/ruralos-alerts.json'
TEXT_FIELDS = ('title', 'subject', 'country', 'market', 'whatChanged', 'catalyst', 'counterevidence', 'invalidation', 'nextStep', 'timing', 'price', 'limitations')
CATEGORIES = {'business_research': 'BUSINESS RESEARCH', 'stock_research': 'STOCK RESEARCH · NOT A TRADE SIGNAL', 'travel_deal': 'OBSERVED FARE · RECHECK BEFORE BOOKING'}
STOCK_FIELDS = ('exchange','ticker','listingType','quoteCurrency','reportingCurrency','observedQuoteAndTime','valuationBasis','financialPeriod','revenueAndProfit','cashFlow','balanceSheetDilutionLiquidity')
TRAVEL_FIELDS = ('route','fareType','passengers','baggage','fees','cancellation','providerUrl')

def safe_url(value):
    if not isinstance(value, str):
        raise ValueError('Invalid URL')
    u = urlsplit(value)
    if u.scheme != 'https' or not u.hostname or u.username or u.password or u.port not in (None, 443) or any(c.isspace() for c in value):
        raise ValueError('Unsafe URL')

def required_details(value, fields):
    if not isinstance(value, dict) or any(not isinstance(value.get(k),str) or not 1 <= len(value[k].strip()) <= 1500 for k in fields):
        raise ValueError('Complete category evidence required')

def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('Timestamp must be text')
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Timestamp needs timezone')
    return dt

def validate(data, now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('alerts'), list) or len(data['alerts']) > 100:
        raise ValueError('Invalid alert catalogue')
    ids = set()
    for a in data['alerts']:
        if not isinstance(a, dict):
            raise ValueError('Invalid alert')
        if not re.fullmatch(r'[a-z0-9-]{5,90}', a.get('id', '')) or a['id'] in ids:
            raise ValueError('Invalid or duplicate alert ID')
        ids.add(a['id'])
        if type(a.get('revision')) is not int or a['revision'] < 1:
            raise ValueError('Invalid revision')
        if a.get('category') not in CATEGORIES:
            raise ValueError('Unsupported category')
        for key in TEXT_FIELDS:
            if not isinstance(a.get(key), str) or not 1 <= len(a[key].strip()) <= 1500:
                raise ValueError('Missing or oversized alert detail')
        for key in ('facts', 'inferences', 'risks'):
            if not isinstance(a.get(key), list) or not 1 <= len(a[key]) <= 12 or any(not isinstance(x, str) or not 1 <= len(x.strip()) <= 1500 for x in a[key]):
                raise ValueError('Invalid evidence list')
        checked, review = timestamp(a['checkedAt']), timestamp(a['reviewBy'])
        if checked > now + timedelta(minutes=5) or not checked < review <= checked + timedelta(days=7):
            raise ValueError('Invalid freshness window')
        if a['category']=='stock_research':
            # Missing values must be explicitly marked "Not verified". All stock cards remain research leads.
            required_details(a.get('stock'), STOCK_FIELDS)
        if a['category']=='travel_deal':
            t=a.get('travel');required_details(t,TRAVEL_FIELDS);safe_url(t['providerUrl'])
            if type(t.get('total')) not in (float,int) or not math.isfinite(t['total']) or t['total']<=0 or not re.fullmatch(r'[A-Z]{3}',t.get('currency','')) or t.get('liveAvailabilityChecked') is not True:
                raise ValueError('Observed total and live availability check required')
            departure=datetime.strptime(t['departureDate'],'%Y-%m-%d').date()
            if departure<checked.date() or (t.get('returnDate') and datetime.strptime(t['returnDate'],'%Y-%m-%d').date()<departure) or review>checked+timedelta(hours=1):
                raise ValueError('Invalid travel dates or fare freshness')
        for key in ('publishedDate', 'eventDate'):
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', a.get(key, '')):
                raise ValueError('Invalid source date')
            date = datetime.strptime(a[key], '%Y-%m-%d').date()
            if date > checked.date():
                raise ValueError('Source date after observation')
        if not isinstance(a.get('sources'), list) or not 1 <= len(a['sources']) <= 8:
            raise ValueError('Sources required')
        for source in a['sources']:
            if not isinstance(source, dict) or not isinstance(source.get('url'), str):
                raise ValueError('Invalid source')
            safe_url(source['url'])
            if not isinstance(source.get('label'), str) or not 1 <= len(source['label']) <= 120:
                raise ValueError('Source label required')
    return data

def load_alerts(now=None):
    if DATA.stat().st_size > 256_000:
        raise ValueError('Alert catalogue too large')
    return validate(json.loads(DATA.read_text()), now)['alerts']

def status(a, now):
    return 'Needs recheck' if now >= timestamp(a['reviewBy']) else 'Fare snapshot' if a['category']=='travel_deal' else 'Research lead'

def public_feed(now=None):
    now = now or datetime.now(timezone.utc)
    alerts = sorted(load_alerts(now), key=lambda a: timestamp(a['checkedAt']), reverse=True)
    return {'version': 1, 'servedAt': now.isoformat(), 'emailDelivery': 'not_connected', 'pushDelivery': 'not_connected',
            'note': 'Reviewed public research; no live price feed or continuous background monitoring.',
            'alerts': [dict(a, status=status(a, now)) for a in alerts]}

def poster(a, now):
    e = escape
    def section(title, content):
        return f'<section><h3>{e(title)}</h3>{content}</section>'
    def lines(values):
        return '<ul>' + ''.join(f'<li>{e(x)}</li>' for x in values) + '</ul>'
    extra=''
    if a['category']=='stock_research':
        extra=section('Listing and financial evidence',lines([k+': '+a['stock'][k] for k in STOCK_FIELDS]))
    if a['category']=='travel_deal':
        t=a['travel'];extra=section('Observed fare details',lines([f"Total: {t['total']:,.2f} {t['currency']}", 'Departure: '+t['departureDate'], 'Return: '+(t.get('returnDate') or 'One way')]+[k+': '+t[k] for k in TRAVEL_FIELDS]))
    return f'''<article id="{e(a['id'])}" class="poster"><p class="eyebrow">{CATEGORIES[a['category']]} · <span data-review-by="{e(a['reviewBy'],quote=True)}" data-checked-at="{e(a['checkedAt'],quote=True)}" data-category="{e(a['category'],quote=True)}">Dated snapshot · check review time below</span></p>
<h2>{e(a['title'])}</h2><p class="subject">{e(a['subject'])}</p><p>{e(a['country'])} · {e(a['market'])}</p>
{section('What changed', '<p>'+e(a['whatChanged'])+'</p>')}
{section('Why it matters', '<p>'+e(a['catalyst'])+'</p>')}
{section('Verified source observations', lines(a['facts']))}
{section('Possible opportunity · inference', lines(a['inferences']))}
{section('Risks', lines(a['risks']))}
{section('Price and timing', '<p>'+e(a['price'])+'</p><p>'+e(a['timing'])+'</p>')}
{extra}
<div class="next">{section('Your next step', '<p>'+e(a['nextStep'])+'</p>')}</div>
<details><summary>Full evidence, limitations and when to stop</summary>
{section('Counterevidence', '<p>'+e(a['counterevidence'])+'</p>')}
{section('Invalidation', '<p>'+e(a['invalidation'])+'</p>')}
{section('Coverage limits', '<p>'+e(a['limitations'])+'</p>')}</details>
<p class="dates">Published: {e(a['publishedDate'])} (time not supplied) · Event: {e(a['eventDate'])}<br>
Checked: {e(a['checkedAt'])} · Recheck by: {e(a['reviewBy'])} · Revision {a['revision']}</p>
<nav aria-label="Sources">{''.join('<a href="'+e(s['url'],quote=True)+'" target="_blank" rel="noopener noreferrer">'+e(s['label'])+' ↗</a>' for s in a['sources'])}</nav>
<p class="disclaimer">Research alert — not investment advice.</p></article>'''

def page(feed, country='all'):
    now = timestamp(feed['servedAt'])
    countries = {'India':'india','United States':'united-states'}
    selected = [a for a in feed['alerts'] if country == 'all' or a['country'] == country]
    filters = '<a href="/ruralos/alerts/">All countries</a>' + ''.join('<a href="/ruralos/alerts/'+slug+'/">'+escape(c)+'</a>' for c,slug in countries.items())
    cards = ''.join(poster(a, now) for a in selected) or '<p>No reviewed alerts in this selection. No opportunity is implied.</p>'
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Celesys research alerts</title><meta name="description" content="Reviewed opportunity research with sources, risks and practical next steps."><link rel="canonical" href="https://celesys.ai/ruralos/alerts/"><link rel="stylesheet" href="/ruralos/alerts.css"></head><body>
<header><a href="/ruralos/">← Home · All services</a><span>CELESYS / SAATHI</span></header><main><p class="eyebrow">OPPORTUNITY RADAR</p><h1>Useful signals.<br>Evidence you can check.</h1><p class="intro">Reviewed research in one place. Open a card for sources, risks and your next action.</p>
<aside><strong>Website alerts are available here.</strong><p>Public email subscriptions and phone push are unavailable. Owner alerts use a separately authorized research watch. This page does not promise instant background alerts. Refresh to see published updates. Detailed research is currently in English.</p><a href="/ruralos/alerts/">Refresh alerts</a></aside>
<nav aria-label="Filter by country">{filters}</nav><p>Checked at source times below. Past the review date, an alert needs rechecking. No live price feed; no exhaustive market coverage.</p>{cards}</main><footer>Public research only. Family records and private tracking remain in the secure family app.</footer><script type="module" src="/ruralos/alerts.js"></script></body></html>'''

def build(destination=None):
    # Offline build only. Validate everything before writing any public file.
    feed=public_feed()
    rendered={'index.html':page(feed),'india/index.html':page(feed,'India'),'united-states/index.html':page(feed,'United States'),'feed.json':json.dumps(feed,ensure_ascii=False)}
    destination=destination or DATA.parent.parent/'ruralos/alerts'
    for filename,content in rendered.items():
        target=destination/filename;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(content)

if __name__=='__main__':
    build()
