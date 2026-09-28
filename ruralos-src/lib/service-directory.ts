import {services} from './services.ts';
import {travel} from './task-engine.ts';
import {serviceTranslations} from './service-translations.ts';
export type DirectoryLanguage='en'|'hi'|'te';
const travelNames:Record<string,string[]>={rail:['रेल टिकट','రైలు టికెట్లు'],flight:['विमान टिकट','విమాన టికెట్లు'],cab:['टैक्सी यात्रा','క్యాబ్ ప్రయాణం'],holiday:['छुट्टी की योजना','విహార యాత్ర ప్రణాళిక']};
const synonyms:Record<string,string>={schemes:'pension widow senior benefits eligibility पेंशन పెన్షన్',aadhaar:'aadhar mobile phone आधार ఆధార్',land:'property registration जमीन భూమి',flat:'apartment house registration फ्लैट ఫ్లాట్',rail:'train railway रेल రైలు',flight:'airplane airport विमान విమానం',cab:'taxi uber ola टैक्सी క్యాబ్',holiday:'hotel vacation trip छुट्टी విహార',documents:'income caste residence certificate प्रमाण पत्र ధృవీకరణ',ration:'food rice ration card राशन రేషన్',education:'scholarship school छात्रवृत्ति స్కాలర్‌షిప్',telemedicine:'doctor hospital consultation डॉक्टर డాక్టర్',jobs:'employment work नौकरी ఉద్యోగం',farm:'agriculture farmer किसान రైతు'};
export const directory=[...services.map(s=>({...s,kind:'guide' as const})),...travel.map(s=>({...s,category:'Travel',description:'Prepare your details, then continue with a travel provider.',sourceName:s.id==='rail'?'IRCTC':'Choose your provider',checklist:[],caution:'No booking or live prices are available here.',kind:'guide' as const}))];
export function serviceTitle(id:string,language:DirectoryLanguage){const s=directory.find(x=>x.id===id);if(!s)return '';if(language==='en')return s.title;return serviceTranslations[language][id]?.title??travelNames[id]?.[language==='hi'?0:1]??s.title}
export function serviceSteps(id:string,language:DirectoryLanguage){const s=directory.find(x=>x.id===id);if(!s)return [];if(language==='en')return s.steps;return serviceTranslations[language][id]?.steps??s.steps}
function rankedServices(query:string,category='All',language:DirectoryLanguage='en'){
 const stopWords=new Set(['i','need','help','with','my','please','want','to','the','a','an','me','for','how','do','can','get']);
 const tokens=query.slice(0,250).toLocaleLowerCase().trim().split(/\s+/u).filter(t=>t&&!stopWords.has(t));
 return directory.filter(s=>category==='All'||s.category===category).map(s=>{
  const title=serviceTitle(s.id,language).toLocaleLowerCase();const aliases=(synonyms[s.id]??'').toLocaleLowerCase();const hay=[title,s.title,s.description,s.category,aliases,serviceTitle(s.id,'hi'),serviceTitle(s.id,'te')].join(' ').toLocaleLowerCase();
  return {s,score:tokens.reduce((n,t)=>n+(title.includes(t)?4:aliases.includes(t)?2:hay.includes(t)?1:0),0)};
 }).filter(x=>!tokens.length||x.score>0).sort((a,b)=>b.score-a.score);
}
export function findServices(query:string,category='All',language:DirectoryLanguage='en'){
 return rankedServices(query,category,language).map(x=>x.s);
}
export function resolveSpokenService(query:string,language:DirectoryLanguage='en'){
 const clean=query.slice(0,250).trim();if(!clean)return null;
 const ranked=rankedServices(clean,'All',language);if(!ranked.length)return null;
 if(ranked.length===1)return ranked[0].s.id;
 const [first,second]=ranked;
 return first.score>=4&&first.score>=second.score+2?first.s.id:null;
}
export function serviceFromQuery(search:string){const id=new URLSearchParams(search).get('service');return directory.some(s=>s.id===id)?id:null}
export const categories=['All',...new Set(directory.map(s=>s.category))];
