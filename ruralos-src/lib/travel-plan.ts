import {hasIdentityNumber,normalizedDigits} from './private-input.ts';
export const travelModes=['flight','rail','cab','holiday','sea'] as const;
export type TravelMode=typeof travelModes[number];
export type TravelDraft={origin:string;destination:string;when:string;travellers:string;budget:string};
export function indiaToday(now=new Date()){return new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit'}).format(now)}
export function validateTravel(mode:TravelMode,draft:TravelDraft,now=new Date()):TravelDraft{
 if(!travelModes.includes(mode))throw Error('mode');
 const d=Object.fromEntries(Object.entries(draft).map(([k,v])=>[k,normalizedDigits(String(v)).trim()])) as TravelDraft;
 for(const k of ['origin','destination'] as const){const v=d[k];if(!v||v.length>100||hasIdentityNumber(v)||/\d{7,}|@|[<>]|https?:|\b(otp|pin|password|cvv)\b/i.test(v))throw Error('route')}
 if(d.origin.toLocaleLowerCase()===d.destination.toLocaleLowerCase())throw Error('same');
 const today=indiaToday(now);
 if(mode==='cab'){
  if(!/^\d{4}-\d{2}-\d{2}$/.test(d.when))throw Error('date');
  const dt=new Date(d.when+'T00:00:00Z');if(!Number.isFinite(dt.getTime())||dt.toISOString().slice(0,10)!==d.when||d.when<today)throw Error('date');
 }else if(!/^\d{4}-(0[1-9]|1[0-2])$/.test(d.when)||d.when<today.slice(0,7))throw Error('month');
 if(!/^\d{1,2}$/.test(d.travellers)||+d.travellers<1||+d.travellers>20)throw Error('travellers');
 if(d.budget&&(!/^\d{1,7}$/.test(d.budget)||+d.budget<1))throw Error('budget');
 return d;
}
export function travelWindow(month:string,now=new Date()){
 if(!/^\d{4}-(0[1-9]|1[0-2])$/.test(month)||month<indiaToday(now).slice(0,7))throw Error('month');
 const [year,m]=month.split('-').map(Number);const last=new Date(Date.UTC(year,m,0)).getUTCDate();
 return {from:month===indiaToday(now).slice(0,7)?indiaToday(now):month+'-01',to:month+'-'+String(last).padStart(2,'0')};
}
// Public handoffs only: no query, identity, payment or passenger data is transmitted.
export const travelHandoffs:Record<TravelMode,{name:string;url:string}[]>={
 flight:[{name:'Google Flights',url:'https://www.google.com/travel/flights'}],
 rail:[{name:'IRCTC',url:'https://www.irctc.co.in/'}],
 cab:[{name:'Uber',url:'https://m.uber.com/'},{name:'Rapido',url:'https://www.rapido.bike/'}],
 holiday:[{name:'Google Travel',url:'https://www.google.com/travel/'}],sea:[]
};
