import {services} from './services.ts';
import {travel} from './task-engine.ts';

export type ProviderReadiness={
 serviceId:string;
 state:'official_handoff_only'|'guidance_only';
 available:string[];
 unavailable:string[];
 transactionEnabled:false;
 acceptsProviderCredentials:false;
};

const travelServices=new Set(['rail','flight','cab','holiday']);
const finance=new Set(['credit','stocks','cropinsurance']);
const health=new Set(['health','telemedicine','nutrition']);

export function providerReadinessFor(serviceId:string):ProviderReadiness{
 const service=services.find(item=>item.id===serviceId)??travel.find(item=>item.id===serviceId);
 if(!service)throw new Error('Unknown service');
 const unavailable=travelServices.has(serviceId)
  ?['Live availability, prices or provider tracking','Reservation, booking, payment or cancellation']
  :finance.has(serviceId)
   ?['Live rates, quotes, recommendations or account status','Application, purchase, trade, payment or approval']
   :health.has(serviceId)
    ?['Diagnosis, clinical triage or provider availability','Consultation booking, payment or medical-record access']
    :['Provider account, application or status inside Saathi','Submission, payment, appointment or official approval'];
 const sourceName='sourceName'in service?service.sourceName:service.id==='rail'?'IRCTC':'a provider you choose';
 const handoff=service.source?`A handoff link to ${sourceName}`:'Provider-selection guidance; no booking provider is selected';
 return {serviceId,state:service.source?'official_handoff_only':'guidance_only',available:['Guided questions and a preparation checklist',handoff],unavailable,transactionEnabled:false,acceptsProviderCredentials:false};
}

export function isSafeProviderUrl(value:string){
 try{const url=new URL(value);return url.protocol==='https:'&&!url.username&&!url.password&&!['localhost','127.0.0.1','0.0.0.0'].includes(url.hostname)}catch{return false}
}
