"""Bounded hourly regional research scans; no order execution or option tickets."""
from datetime import datetime
from zoneinfo import ZoneInfo
import logging
import os
import threading
import time
from trading_opportunities import rank_reports

UNIVERSE={
    "US":("SPY","QQQ","SPX","NDX","AAPL","MSFT","NVDA","AMD","AMZN","META"),
    "IN":("NIFTY","BANKNIFTY","SENSEX","RELIANCE","HDFCBANK","ICICIBANK","INFY","TCS","SBIN","LT"),
}
CYCLE_SECONDS=3600
WINDOW_SECONDS=240
MIN_GAP=15
log=logging.getLogger(__name__)

def regular_window(region, now):
    """Clock filter only; provider session evidence is still required."""
    local=datetime.fromtimestamp(now,ZoneInfo("America/New_York" if region=="US" else "Asia/Kolkata"))
    minutes=local.hour*60+local.minute
    start,end=(570,960) if region=="US" else (555,930)
    return local.weekday()<5 and start<=minutes<end

class RegionalScanner:
    def __init__(self, supplier, provider_state, clock=time.time):
        self.supplier=supplier
        self.provider_state=provider_state
        self.clock=clock
        self.lock=threading.Lock()
        self.stop=threading.Event()
        self.thread=None
        self.results={}
        self.active=None
        self.next_due={r:0 for r in UNIVERSE}
        self.enabled=False

    def start(self):
        if os.getenv("CELESYS_REGIONAL_SCAN","0")!="1" or os.getenv("CELESYS_DISABLE_BACKGROUND")=="1":
            return
        with self.lock:
            if self.thread and self.thread.is_alive():
                return
            self.stop.clear()
            self.enabled=True
            self.thread=threading.Thread(target=self.run,name="regional-opportunities",daemon=True)
            self.thread.start()

    def close(self):
        self.stop.set()
        with self.lock:
            self.enabled=False
        # Never block web shutdown on a slow provider.

    def cycle(self,region):
        started=self.clock()
        deadline=started+WINDOW_SECONDS
        reports=[]
        attempted=0
        with self.lock:
            self.active=region
            self.next_due[region]=started+CYCLE_SECONDS
        try:
            for symbol in UNIVERSE[region]:
                now=self.clock()
                if self.stop.is_set() or now>=deadline or not regular_window(region,now):
                    break
                state=self.provider_state()
                retry_at=state.get("retry_after",0) or 0
                wait=max(0,retry_at-now)
                if wait:
                    if now+wait>=deadline or self.stop.wait(wait):
                        break
                if self.clock()>=deadline or not regular_window(region,self.clock()):
                    break
                attempted+=1
                try:
                    report=self.supplier(symbol,region)
                    if isinstance(report,dict) and report.get("symbol")==symbol and report.get("region")==region:
                        reports.append(report)
                except Exception as exc:
                    log.warning("Regional research failed for %s/%s: %s",region,symbol,type(exc).__name__)
                if attempted<len(UNIVERSE[region]) and self.stop.wait(MIN_GAP):
                    break
            finished=self.clock()
            result=rank_reports(reports,region,finished,UNIVERSE[region])
            result.update(cycle_started_at=started,cycle_completed_at=finished,
                coverage={**result["coverage"],"attempted":attempted},
                partial_coverage=attempted<len(UNIVERSE[region]),
                next_cycle_at=started+CYCLE_SECONDS)
            with self.lock:
                self.results[region]=result
            log.info("Regional opportunities %s: %s/%s attempted; %s fresh research candidates",
                     region,attempted,len(UNIVERSE[region]),len(result["opportunities"]))
        finally:
            with self.lock:
                self.active=None

    def run(self):
        # Let the web server and broker session initialize before provider calls.
        if self.stop.wait(45):
            return
        while not self.stop.is_set():
            for region in UNIVERSE:
                now=self.clock()
                if regular_window(region,now) and now>=self.next_due[region]:
                    try:
                        self.cycle(region)
                    except Exception as exc:
                        log.warning("Regional cycle failed: %s",type(exc).__name__)
                        with self.lock:
                            self.next_due[region]=self.clock()+CYCLE_SECONDS
            self.stop.wait(15)

    def snapshot(self,region):
        now=self.clock()
        if region not in UNIVERSE:
            raise ValueError("Unsupported region")
        with self.lock:
            prior=self.results.get(region)
            active=self.active==region
            enabled=self.enabled
            due=self.next_due[region]
        in_window=regular_window(region,now)
        result=dict(region=region,enabled=enabled,scope="BOUNDED_LIQUID_WATCHLIST",
            market_status="REGULAR_HOURS_UNVERIFIED" if in_window else "OUTSIDE_REGULAR_HOURS",
            status="SCANNING" if active else "AWAITING_FIRST_CYCLE" if enabled else "SCANNER_DISABLED",
            coverage=dict(universe_size=len(UNIVERSE[region]),observed=0,attempted=0,fresh_inputs=0),
            universe=list(UNIVERSE[region]),opportunities=[],last_shortlist=[],cycle_completed_at=None,
            next_cycle_at=due if enabled and in_window and due>now else None,generated_at=now,
            note="Hourly shortlist is research only. Open any symbol for a fresh five-minute entry check.")
        if prior:
            result.update(coverage=dict(prior["coverage"]),cycle_completed_at=prior["cycle_completed_at"],
                partial_coverage=prior["partial_coverage"])
            # Last shortlist is explicitly historical, and intentionally omits prices and risk levels.
            result["last_shortlist"]=[dict(rank=x["rank"],symbol=x["symbol"],direction=x["direction"],source=x["source"],
                quote_time=x["quote_time"]) for x in prior["opportunities"]]
            if enabled and in_window:
                result["opportunities"]=[x for x in prior["opportunities"] if x["expires_at"]>now]
                if not active:
                    result["status"]="RESEARCH_CANDIDATES" if result["opportunities"] else "NO_FRESH_CANDIDATES"
        if not in_window:
            result["status"]="MARKET_CLOSED_REGULAR_HOURS"
        return result
