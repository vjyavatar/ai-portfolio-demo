import React,{useEffect,useRef,useState} from 'react';
import {playbooks} from '../lib/service-playbooks';
import {preparationCopy} from './service-preparation';
import {createSpeechSession,type SpeechSession} from '../lib/speech-client';
import type {DirectoryLanguage} from '../lib/service-directory';
import './service-quick-answer.css';
const copy={
 en:{title:'Useful help before you fill anything',note:'General preparation only. Choose your state below for the regional route. This does not check eligibility or submit a request.',details:'Checklist, questions and mistakes to avoid',preview:'Detailed guidance is in English; Hindi and Telugu are review previews.'},
 hi:{title:'कुछ भरने से पहले उपयोगी मदद',note:'यह सामान्य तैयारी है। क्षेत्रीय रास्ते के लिए नीचे राज्य चुनें। इससे पात्रता जाँच या आवेदन जमा नहीं होता।',details:'तैयारी, सवाल और गलतियों से बचाव',preview:'विस्तृत जानकारी अंग्रेज़ी में है; हिन्दी और तेलुगु समीक्षा पूर्वावलोकन हैं।'},
 te:{title:'ఏదైనా నింపే ముందే ఉపయోగకరమైన సహాయం',note:'ఇది సాధారణ తయారీ మాత్రమే. ప్రాంతీయ మార్గం కోసం కింద రాష్ట్రం ఎంచుకోండి. ఇది అర్హత తనిఖీ లేదా అభ్యర్థన సమర్పణ కాదు.',details:'తయారీ, ప్రశ్నలు మరియు తప్పులు నివారించడం',preview:'వివరాలు ఆంగ్లంలో ఉన్నాయి; హిందీ, తెలుగు సమీక్ష ముందస్తు రూపాలు.'}
};
export default function ServiceQuickAnswer({serviceId,language,stopOtherAudio}:{serviceId:string;language:DirectoryLanguage;stopOtherAudio:()=>void}){
 const p=playbooks[serviceId],c=copy[language],pc=preparationCopy[language];
 const [choice,setChoice]=useState(0),[error,setError]=useState(false),[speaking,setSpeaking]=useState(false);
 const speech=useRef<SpeechSession|null>(null);
 useEffect(()=>{speech.current=createSpeechSession(phase=>setSpeaking(phase==='speaking'),'en-IN');const stop=()=>{if(document.hidden)speech.current?.stop()};document.addEventListener('visibilitychange',stop);return()=>{speech.current?.stop();document.removeEventListener('visibilitychange',stop)}},[]);
 useEffect(()=>{speech.current?.stop();setChoice(0);setError(false)},[serviceId,language]);
 if(!p)return null;
 async function listen(){stopOtherAudio();setError(false);try{await speech.current?.speak([copy.en.note,p.actions[choice],...p.prepare,...p.ask,p.trap].join('. '),.9)}catch{setError(true)}}
 return <section className="quick-answer" aria-label={c.title}>
  <h2>{c.title}</h2><p className="quick-answer-note">{c.note}</p>
  {language!=='en'&&<p>{c.preview}</p>}
  <div className="quick-answer-choices" role="group" aria-label={pc.choose}>{p.goals.map((goal,i)=><button type="button" key={goal} lang="en" aria-pressed={choice===i} onClick={()=>{speech.current?.stop();setChoice(i);setError(false)}}>{goal}</button>)}</div>
  <div className="quick-answer-next" aria-live="polite"><strong>{pc.next}</strong><p lang="en">{p.actions[choice]}</p></div>
  <details><summary>{c.details}</summary><h3>{pc.items}</h3><ul lang="en">{p.prepare.map(x=><li key={x}>{x}</li>)}</ul><h3>{pc.ask}</h3><ol lang="en">{p.ask.map(x=><li key={x}>{x}</li>)}</ol><h3>{pc.avoid}</h3><p lang="en">{p.trap}</p><p>{pc.note}</p></details>
  <button type="button" onClick={()=>void listen()} disabled={speaking}>{pc.listen}</button>{speaking&&<button type="button" onClick={()=>speech.current?.stop()}>{pc.stop}</button>}
  {error&&<p role="alert">{pc.error}</p>}
 </section>
}
