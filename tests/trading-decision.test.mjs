import {test} from "node:test";
import assert from "node:assert/strict";
import {classify} from "../trading/decision-state.mjs";
function fixtures(){
 const now=1000000,region="IN",symbol="NIFTY";
 const report={region,symbol,market_status:"OPEN",session_start:now-1000,session_end:now+1000,quote_time:now-10,bar_close_time:now-20,price:25000,bars:[{}],verdict:"LONG_RESEARCH",stages:["Data steward","Session guard","Trend analyst","Setup analyst","Risk critic","Quote guard"].map(name=>({name,status:"pass"}))};
 const base={report,region,symbol,now};
 const us={...base,region:"US",symbol:"SPY",report:{...report,region:"US",symbol:"SPY"}};
 const options={status:"BUY_CALL_CANDIDATE",candidate:{contract:"SPY261130C00600000",bid:2,ask:2.1,bid_time:now-5,ask_time:now-5,expires_at:now+30}};
 return [
 ["closed beats stale",{...base,closed:true,report:null},"CLOSED"],
 ["sample cannot trade",{...base,sample:true},"SAMPLE"],
 ["scanning blocks old decision",{...base,busy:true},"SCANNING"],
 ["missing report",{...base,report:null},"UNAVAILABLE"],
 ["wrong symbol",{...base,symbol:"SENSEX"},"UNAVAILABLE"],
 ["stale cache",{...base,report:{...report,stale_cache:true}},"UNAVAILABLE"],
 ["stale quote",{...base,report:{...report,quote_time:now-301}},"UNAVAILABLE"],
 ["future timestamp",{...base,report:{...report,quote_time:now+1}},"UNAVAILABLE"],
 ["empty bars",{...base,report:{...report,bars:[]}},"UNAVAILABLE"],
 ["zero price",{...base,report:{...report,price:0}},"UNAVAILABLE"],
 ["session ended",{...base,report:{...report,session_end:now}},"UNAVAILABLE"],
 ["wait normal",{...base,report:{...report,verdict:"WAIT"}},"WAIT"],
 ["missing required gate",{...base,report:{...report,stages:[]}},"WAIT"],
 ["blocked gate",{...base,report:{...report,stages:[...report.stages,{status:"blocked"}]}},"WAIT"],
 ["India CE",base,"BIAS"],
 ["India PE",{...base,report:{...report,verdict:"BEARISH_RESEARCH"}},"BIAS"],
 ["India cannot use US ticket",{...base,options},"BIAS"],
 ["US contract conditional",{...us,options},"REVIEW"],
 ["US wrong identity",{...us,options:{...options,candidate:{...options.candidate,contract:"QQQ261130C00600000"}}},"BIAS"],
 ["US expired",{...us,options:{...options,candidate:{...options.candidate,expires_at:now}}},"BIAS"],
 ["US wrong direction",{...us,options:{...options,status:"BUY_PUT_CANDIDATE"}},"BIAS"],
 ["US crossed spread",{...us,options:{...options,candidate:{...options.candidate,bid:3}}},"BIAS"],
 ["US quote predates signal",{...us,options:{...options,candidate:{...options.candidate,bid_time:now-21}}},"BIAS"]];
}
for (const [name,input,expected] of fixtures()) test(name,()=>assert.equal(classify(input).state,expected));
