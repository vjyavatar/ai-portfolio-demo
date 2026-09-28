import React,{useEffect,useRef,useState} from 'react';
import {workflows,startTask,answerTask,nextField,confirmTask,matchTasks,type Task} from '../lib/task-engine';
import {createSpeechSession,type SpeechSession} from '../lib/speech-client';
import {directory,serviceSteps,serviceTitle,type DirectoryLanguage} from '../lib/service-directory';
import {regionalRoute} from '../lib/regional-guidance';
import {regions} from '../lib/regions';
import {canStartVoiceCapture,voiceCaptureError,type VoicePhase} from '../lib/voice-safety';
import {providerReadinessFor,isSafeProviderUrl} from '../lib/provider-readiness';
import {taskFocusTarget} from '../lib/task-focus';
import {localizeProviderItem,localizeTaskError,taskCopy,taskEventLabel} from '../lib/task-copy';

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

export default function TaskAssistant({initialService,initialLanguage='en',offline=false}:{initialService?:string;initialLanguage?:string;offline?:boolean}={}){
 const[open,setOpen]=useState(!!initialService),[task,setTask]=useState<Task|null>(()=>initialService?startTask(initialService):null),[value,setValue]=useState(''),[query,setQuery]=useState(''),[error,setError]=useState(''),[lang,setLang]=useState(['en','hi','te'].indexOf(initialLanguage)),[phase,setPhase]=useState<VoicePhase>('ready'),[voiceConsent,setVoiceConsent]=useState(false);
 const speech=useRef<SpeechSession|null>(null);
 const focusAfterProgress=useRef(!!initialService),fieldControl=useRef<HTMLInputElement|HTMLSelectElement|null>(null),reviewHeading=useRef<HTMLHeadingElement|null>(null),actionHeading=useRef<HTMLHeadingElement|null>(null);
 useEffect(()=>{speech.current=createSpeechSession(setPhase,['en-IN','hi-IN','te-IN'][lang]);const stop=()=>{if(document.hidden)speech.current?.stop()};document.addEventListener('visibilitychange',stop);return()=>{speech.current?.stop();document.removeEventListener('visibilitychange',stop)}},[lang]);
 const language=['en','hi','te'][lang] as DirectoryLanguage,c=taskCopy[language];
 const w=workflows.find(w=>w.id===task?.serviceId),service=directory.find(s=>s.id===task?.serviceId),field=task?nextField(task):null;
 const localizedTitle=task?.serviceId?serviceTitle(task.serviceId,language):'',localizedSteps=task?.serviceId?serviceSteps(task.serviceId,language):[];
 const localRoute=task?.answers.region&&task.serviceId?regionalRoute(task.answers.region,task.serviceId):null;
 const readiness=task?.serviceId?providerReadinessFor(task.serviceId):null;
 useEffect(()=>{if(!focusAfterProgress.current)return;const target=taskFocusTarget(task,field);const node=target==='field'?fieldControl.current:target==='review'?reviewHeading.current:target==='action'?actionHeading.current:null;if(node){node.focus({preventScroll:true});focusAfterProgress.current=false}},[field,task?.status]);
 function reset(){speech.current?.stop();focusAfterProgress.current=false;setTask(null);setValue('');setQuery('');setError('');setVoiceConsent(false)}
 async function listen(search=false){setError('');if(!voiceConsent){setError(voiceCaptureError(lang,undefined,false));return}try{const text=await speech.current!.listen();search?setQuery(text):setValue(text)}catch(e){setError(voiceCaptureError(lang,e))}}
 async function read(text:string){try{setError('');await speech.current!.speak(text,.9)}catch(e){setError(voiceCaptureError(lang,e))}}
 const candidates=matchTasks(query);
 const spokenSteps=w?[localizedTitle,...localizedSteps,c.onlyOfficial].join('. '):'';
 return <section className="panel task-guide" style={{maxWidth:1100,margin:'20px auto'}}>
  <button className="primary" onClick={()=>{reset();setOpen(!open)}}>{open?c.close:c.open}</button>
  {open&&<>
   <h2>{c.question}</h2>
   <p className="notice">{c.preview}</p>
   <label>{c.language} <select value={lang} onChange={e=>{speech.current?.stop();setLang(+e.target.value)}}><option value={0}>English · India</option><option value={1}>हिन्दी · समीक्षा पूर्वावलोकन</option><option value={2}>తెలుగు · సమీక్ష ముందస్తు రూపం</option></select></label>
   <p>{c.languageNote}</p>
   <div className="task-voice-consent">
    <label><input type="checkbox" checked={voiceConsent} onChange={e=>{setVoiceConsent(e.target.checked);setError('');if(!e.target.checked)speech.current?.stop()}}/> {voiceWords.consent[lang]}</label>
    <p>{voiceWords.fallback[lang]}</p>
    <span role="status" aria-live="polite">{phase==='listening'?voiceWords.listening[lang]:voiceConsent?voiceWords.ready[lang]:''}</span>
   </div>
   {!task?<>
    <label>{c.describe}<input value={query} maxLength={250} onChange={e=>setQuery(e.target.value)} placeholder={c.requestPlaceholder}/></label>
    <button className="outline" disabled={!canStartVoiceCapture(voiceConsent,phase)} onClick={()=>listen(true)}>{c.speakRequest}</button>
    {query&&<p>{c.choose}</p>}
    <div className="form-grid">{(candidates.length?candidates:workflows).map(w=><button className="outline" key={w.id} onClick={()=>{focusAfterProgress.current=true;setTask(startTask(w.id));setQuery('');setError('')}}>{serviceTitle(w.id,language)}</button>)}</div>
   </>:<>
    <h3>{localizedTitle}</h3>
    {localizedSteps[0]&&<p>{localizedSteps[0]}</p>}
    {field&&<form onSubmit={e=>{e.preventDefault();try{const next=answerTask(task,value);focusAfterProgress.current=true;setTask(next);setValue('');setError('')}catch(e){focusAfterProgress.current=false;setError(localizeTaskError((e as Error).message,language))}}}>
     <label>{labels[field][lang]}{field==='region'?<select ref={node=>{fieldControl.current=node}} value={value} onChange={e=>setValue(e.target.value)} required><option value="">{c.chooseRegion}</option>{regions.map(r=><option key={r}>{r}</option>)}</select>:<input ref={node=>{fieldControl.current=node}} value={value} maxLength={250} type={field==='date'?'date':'text'} inputMode={['travellers','budget'].includes(field)?'numeric':'text'} onChange={e=>setValue(e.target.value)} required/>}</label>
     <div className="row"><button type="button" className="outline" onClick={()=>read(labels[field][lang])}>{c.listenQuestion}</button><button type="button" className="outline" disabled={!canStartVoiceCapture(voiceConsent,phase)} onClick={()=>listen()}>{c.speakAnswer}</button><button className="primary" type="submit">{c.confirm}</button></div>
    </form>}
    {task.status!=='collecting'&&<>
     <h3 ref={reviewHeading} className="task-focus-heading" tabIndex={-1}>{c.review}</h3>
     <dl>{Object.entries(task.answers).map(([key,v])=><React.Fragment key={key}><dt>{labels[key][lang]}</dt><dd>{v}</dd></React.Fragment>)}</dl>
     {task.status==='review'?<button className="primary" onClick={()=>{focusAfterProgress.current=true;setTask(confirmTask(task))}}>{c.confirmDetails}</button>:<>
      <article className="task-action-card" aria-labelledby="task-action-title">
       <p className="task-status" role="status">{c.status}</p>
       <h3 ref={actionHeading} className="task-focus-heading" tabIndex={-1} id="task-action-title">{c.next}</h3>
       <p>{localizedSteps[0]}</p>
       {service&&<p className="task-caution">{language==='en'?service.caution:<><strong>{c.important}.</strong> {c.onlyOfficial}<br/><small>{c.englishDetail} <span lang="en">{service.caution}</span></small></>}</p>}
       <div className="task-actions">
        <button type="button" className="outline" onClick={()=>void read(spokenSteps)}>{c.listen}</button>
        <details><summary>{c.show}</summary><ol>{localizedSteps.map(s=><li key={s}>{s}</li>)}</ol></details>
        <a className="outline" href={secureSite+'/?view=Reminders'} target="_blank" rel="noreferrer">{c.reminder}</a>
        <a className="outline" href={secureSite+'/?view=Help'} target="_blank" rel="noreferrer">{c.help}</a>
       </div>
       {(language==='en'?service?.checklist:localizedSteps)?.length?<section className="task-checklist" aria-labelledby="document-checklist-title"><h4 id="document-checklist-title">{c.checklist}</h4><ul>{(language==='en'?service?.checklist:localizedSteps)!.map(item=><li key={item}>□ {item}</li>)}</ul></section>:null}
       {readiness&&<section className="task-provider-card" aria-labelledby="provider-readiness-title">
        <p className="task-provider-state">{c.connection} · {readiness.state==='official_handoff_only'?c.official:c.guidance}</p>
        <h4 id="provider-readiness-title">{c.works}</h4>
        <ul>{readiness.available.map(item=><li key={item}>✓ {localizeProviderItem(item,language)}</li>)}</ul>
        <h4>{c.notConnected}</h4>
        <ul>{readiness.unavailable.map(item=><li key={item}>— {localizeProviderItem(item,language)}</li>)}</ul>
        <p>{c.notSent}</p>
        {offline&&<p className="task-offline-provider" role="alert">{c.offline}</p>}
       </section>}
       {w!.source&&isSafeProviderUrl(w!.source)?offline?<button className="primary task-official-link" type="button" disabled>{c.reconnect}</button>:<a className="primary task-official-link" href={w!.source} target="_blank" rel="noreferrer">{c.openOfficial}</a>:<p>{c.chooseProvider}</p>}
      </article>
      {localRoute&&<aside className="task-region-card" aria-labelledby="region-route-title">
       <p className="task-verified">{c.region} · {localRoute.region}</p>
       <h3 id="region-route-title">{c.regionTitle}</h3>
       <p>{c.regionInfo}</p>
       <a className="outline" href={localRoute.url} target="_blank" rel="noreferrer">{c.openRegion}</a>
       {localRoute.url!==localRoute.directory&&<a className="outline" href={localRoute.directory} target="_blank" rel="noreferrer">{c.openDirectory}</a>}
       <small>{c.directoryChecked} {localRoute.checked} · {c.reviewDue} {localRoute.reviewDue} · {c.localEligibility}</small>
      </aside>}
      <p>{c.onlyOfficial}</p>
      <details><summary>{c.progress}</summary><ol>{task.events.map((e,i)=><li key={i}>{taskEventLabel(e.event,language)}</li>)}</ol></details>
     </>}
    </>}
    <button className="outline" onClick={reset}>{c.restart}</button>
   </>}
   {phase!=='ready'&&<button className="outline" onClick={()=>speech.current?.stop()}>{c.stop}</button>}
   {error&&<p role="alert" className="task-voice-error">{error}</p>}<a href="/ruralos/integrations/">{c.gaps}</a>
  </>}
 </section>
}
