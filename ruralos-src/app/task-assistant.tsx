import React,{useEffect,useRef,useState} from 'react';
import {workflows,startTask,answerTask,nextField,confirmTask,matchTasks,type Task} from '../lib/task-engine';
import {createSpeechSession,type SpeechSession} from '../lib/speech-client';
import {directory} from '../lib/service-directory';
import {regionalRoute} from '../lib/regional-guidance';
import {regions} from '../lib/regions';
import {canStartVoiceCapture,voiceCaptureError,type VoicePhase} from '../lib/voice-safety';

const labels:Record<string,string[]>={
 region:['Choose your State or Union Territory','अपना राज्य या केंद्र शासित प्रदेश चुनें','మీ రాష్ట్రం లేదా కేంద్ర పాలిత ప్రాంతాన్ని ఎంచుకోండి'],
 goal:['What do you want help with? Do not share identity numbers.','आपको किस काम में मदद चाहिए? पहचान संख्या न दें।','మీకు ఏ పనిలో సహాయం కావాలి? గుర్తింపు సంఖ్యలు చెప్పవద్దు.'],
 origin:['Where will you start? Area or town only.','यात्रा कहाँ से शुरू होगी? केवल इलाका या शहर।','ఎక్కడి నుంచి బయలుదేరుతారు? ప్రాంతం లేదా ఊరు మాత్రమే.'],
 destination:['Where do you want to go?','आप कहाँ जाना चाहते हैं?','మీరు ఎక్కడికి వెళ్లాలి?'],
 date:['Choose a travel date','यात्रा की तारीख चुनें','ప్రయాణ తేదీని ఎంచుకోండి'],
 travellers:['How many travellers?','कितने यात्री हैं?','ఎంత మంది ప్రయాణికులు?'],
 budget:['What is your total budget in rupees?','आपका कुल बजट कितने रुपये है?','మీ మొత్తం బడ్జెట్ ఎన్ని రూపాయలు?']
};
const secureSite='https://rural-family-action-os.vjyrcks.chatgpt.site';
const voiceWords={
 consent:['Allow voice answers. My browser or device may process audio online. Do not speak Aadhaar numbers, PINs, OTPs or bank details.','आवाज़ से जवाब देने की अनुमति दें। ब्राउज़र या फ़ोन ऑडियो को ऑनलाइन प्रोसेस कर सकता है। आधार नंबर, PIN, OTP या बैंक जानकारी न बोलें।','వాయిస్ సమాధానాలకు అనుమతించండి. బ్రౌజర్ లేదా ఫోన్ ఆడియోను ఆన్‌లైన్‌లో ప్రాసెస్ చేయవచ్చు. ఆధార్ నంబర్, PIN, OTP లేదా బ్యాంక్ వివరాలు చెప్పవద్దు.'],
 fallback:['Voice is optional. You can always type or tap a choice.','आवाज़ वैकल्पिक है। आप हमेशा लिख सकते हैं या विकल्प चुन सकते हैं।','వాయిస్ ఐచ్చికం. మీరు ఎప్పుడైనా టైప్ చేయవచ్చు లేదా ఎంపికను నొక్కవచ్చు.'],
 ready:['Microphone ready','माइक्रोफ़ोन तैयार','మైక్రోఫోన్ సిద్ధంగా ఉంది'],
 listening:['Listening…','सुन रहे हैं…','వింటున్నాం…']
};

export default function TaskAssistant({initialService,initialLanguage='en'}:{initialService?:string;initialLanguage?:string}={}){
 const[open,setOpen]=useState(!!initialService),[task,setTask]=useState<Task|null>(()=>initialService?startTask(initialService):null),[value,setValue]=useState(''),[query,setQuery]=useState(''),[error,setError]=useState(''),[lang,setLang]=useState(['en','hi','te'].indexOf(initialLanguage)),[phase,setPhase]=useState<VoicePhase>('ready'),[voiceConsent,setVoiceConsent]=useState(false);
 const speech=useRef<SpeechSession|null>(null);
 useEffect(()=>{speech.current=createSpeechSession(setPhase,['en-IN','hi-IN','te-IN'][lang]);const stop=()=>{if(document.hidden)speech.current?.stop()};document.addEventListener('visibilitychange',stop);return()=>{speech.current?.stop();document.removeEventListener('visibilitychange',stop)}},[lang]);
 const w=workflows.find(w=>w.id===task?.serviceId),service=directory.find(s=>s.id===task?.serviceId),field=task?nextField(task):null;
 const localRoute=task?.answers.region&&task.serviceId?regionalRoute(task.answers.region,task.serviceId):null;
 function reset(){speech.current?.stop();setTask(null);setValue('');setQuery('');setError('');setVoiceConsent(false)}
 async function listen(search=false){setError('');if(!voiceConsent){setError(voiceCaptureError(lang,undefined,false));return}try{const text=await speech.current!.listen();search?setQuery(text):setValue(text)}catch(e){setError(voiceCaptureError(lang,e))}}
 async function read(text:string){try{setError('');await speech.current!.speak(text,.9)}catch(e){setError(voiceCaptureError(lang,e))}}
 const candidates=matchTasks(query);
 const spokenSteps=w&&service?[w.title,service.description,...w.steps,service.caution].join('. '):'';
 return <section className="panel task-guide" style={{maxWidth:1100,margin:'20px auto'}}>
  <button className="primary" onClick={()=>{reset();setOpen(!open)}}>{open?'Close guide':'Plan a task — travel, documents or family services'}</button>
  {open&&<>
   <h2>What would you like to do?</h2>
   <p className="notice">Guided task preview · No booking or submission provider is connected. This uses structured workflows, not a connected general AI model. Answers stay in this tab and are cleared when you close or restart.</p>
   <label>Spoken question language <select value={lang} onChange={e=>{speech.current?.stop();setLang(+e.target.value)}}><option value={0}>English · India</option><option value={1}>हिन्दी · review preview</option><option value={2}>తెలుగు · review preview</option></select></label>
   <p>Service names and next-step instructions below are currently English.</p>
   <div className="task-voice-consent">
    <label><input type="checkbox" checked={voiceConsent} onChange={e=>{setVoiceConsent(e.target.checked);setError('');if(!e.target.checked)speech.current?.stop()}}/> {voiceWords.consent[lang]}</label>
    <p>{voiceWords.fallback[lang]}</p>
    <span role="status" aria-live="polite">{phase==='listening'?voiceWords.listening[lang]:voiceConsent?voiceWords.ready[lang]:''}</span>
   </div>
   {!task?<>
    <label>Describe your task<input value={query} maxLength={250} onChange={e=>setQuery(e.target.value)} placeholder="Book a train, update Aadhaar, find document help…"/></label>
    <button className="outline" disabled={!canStartVoiceCapture(voiceConsent,phase)} onClick={()=>listen(true)}>Speak your request</button>
    {query&&<p>Please choose the matching service below. Your spoken text is not submitted.</p>}
    <div className="form-grid">{(candidates.length?candidates:workflows).map(w=><button className="outline" key={w.id} onClick={()=>{setTask(startTask(w.id));setQuery('');setError('')}}>{w.title}</button>)}</div>
   </>:<>
    <h3>{w!.title}</h3>
    {service&&<p>{service.description}</p>}
    {field&&<form onSubmit={e=>{e.preventDefault();try{setTask(answerTask(task,value));setValue('');setError('')}catch(e){setError((e as Error).message)}}}>
     <label>{labels[field][lang]}{field==='region'?<select value={value} onChange={e=>setValue(e.target.value)} required><option value="">Choose region</option>{regions.map(r=><option key={r}>{r}</option>)}</select>:<input value={value} maxLength={250} type={field==='date'?'date':'text'} inputMode={['travellers','budget'].includes(field)?'numeric':'text'} onChange={e=>setValue(e.target.value)} required/>}</label>
     <div className="row"><button type="button" className="outline" onClick={()=>read(labels[field][lang])}>Listen to question</button><button type="button" className="outline" disabled={!canStartVoiceCapture(voiceConsent,phase)} onClick={()=>listen()}>Speak answer</button><button className="primary" type="submit">Confirm answer & continue</button></div>
    </form>}
    {task.status!=='collecting'&&<>
     <h3>Check your details</h3>
     <dl>{Object.entries(task.answers).map(([key,v])=><React.Fragment key={key}><dt>{labels[key][0]}</dt><dd>{v}</dd></React.Fragment>)}</dl>
     {task.status==='review'?<button className="primary" onClick={()=>setTask(confirmTask(task))}>These details are correct — show next steps</button>:<>
      <article className="task-action-card" aria-labelledby="task-action-title">
       <p className="task-status" role="status">Prepared · not submitted · official approval required</p>
       <h3 id="task-action-title">Your next action</h3>
       <p>{w!.steps[0]}</p>
       {service&&<p className="task-caution">{service.caution}</p>}
       <div className="task-actions">
        <button type="button" className="outline" onClick={()=>void read(spokenSteps)}>Listen</button>
        <details><summary>Show steps</summary><ol>{w!.steps.map(s=><li key={s}>{s}</li>)}</ol></details>
        <a className="outline" href={secureSite+'/?view=Reminders'} target="_blank" rel="noreferrer">Save reminder</a>
        <a className="outline" href={secureSite+'/?view=Help'} target="_blank" rel="noreferrer">Get help</a>
       </div>
       {service?.checklist.length?<section className="task-checklist" aria-labelledby="document-checklist-title"><h4 id="document-checklist-title">Checklist before you continue</h4><ul>{service.checklist.map(item=><li key={item}>□ {item}</li>)}</ul></section>:null}
       {w!.source?<a className="primary task-official-link" href={w!.source} target="_blank" rel="noreferrer">Open {service?.sourceName||'official service'}</a>:<p>Choose a provider you trust. Provider search and booking are unavailable here.</p>}
      </article>
      {localRoute&&<aside className="task-region-card" aria-labelledby="region-route-title">
       <p className="task-verified">Applicable region · {localRoute.region}</p>
       <h3 id="region-route-title">Check your State/UT route</h3>
       <p>This verified government directory helps you locate the responsible regional service. It does not prove local online availability or eligibility.</p>
       <a className="outline" href={localRoute.url} target="_blank" rel="noreferrer">Open {localRoute.region} official route</a>
       {localRoute.url!==localRoute.directory&&<a className="outline" href={localRoute.directory} target="_blank" rel="noreferrer">Open government department directory</a>}
       <small>Directory checked {localRoute.checked} · review due {localRoute.reviewDue} · local eligibility is not automated</small>
      </aside>}
      <p>Only a confirmation from the official service or provider proves completion.</p>
      <details><summary>Task progress in this session</summary><ol>{task.events.map((e,i)=><li key={i}>{e.event}</li>)}</ol></details>
     </>}
    </>}
    <button className="outline" onClick={reset}>Start again / clear answers</button>
   </>}
   {phase!=='ready'&&<button className="outline" onClick={()=>speech.current?.stop()}>Stop audio</button>}
   {error&&<p role="alert" className="task-voice-error">{error}</p>}<a href="/ruralos/integrations/">See all integration gaps</a>
  </>}
 </section>
}
