import {normalizedDigits} from './private-input.ts';
export type EnteredQuote={fare:string;extras:string;transfer:string};
// Amounts are total INR for the whole party and the same journey. No provider prices fetched.
export function moneyPaise(value:string):number|null{const v=normalizedDigits(value).trim();if(!/^\d{1,7}(\.\d{1,2})?$/.test(v))return null;const [rupees,fraction='']=v.split('.');return Number(rupees)*100+Number(fraction.padEnd(2,'0'))}
export function compareEnteredQuotes(quotes:EnteredQuote[],party:number,budget:string,sameBasis:boolean){
 if(!Number.isInteger(party)||party<1||party>20)throw Error('travellers');
 const limit=budget===''?null:moneyPaise(budget);
 if(budget!==''&&(limit===null||limit<=0))throw Error('budget');
 const rows=quotes.slice(0,3).map(q=>{const values=[q.fare,q.extras,q.transfer].map(moneyPaise);if(values.some(v=>v===null)||values[0]!<=0)return null;const total=values.reduce<number>((n,v)=>n+v!,0);return {total,perPerson:Math.round(total/party),overBudget:limit===null?null:Math.max(0,total-limit)}});
 const complete=rows.map((r,i)=>r?i:-1).filter(i=>i>=0),min=complete.length?Math.min(...complete.map(i=>rows[i]!.total)):null;
 // Never call an incomplete or single quote the cheapest. Ties remain ties.
 return {rows,limit,budgetPerPerson:limit===null?null:Math.floor(limit/party),lowest:sameBasis&&complete.length>=2?complete.filter(i=>rows[i]!.total===min):[],unverified:true as const};
}
