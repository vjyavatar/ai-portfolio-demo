import React,{useState,useRef,useEffect} from 'react';
import {ArrowLeft,ArrowRight,Volume2,Check,BookOpen} from 'lucide-react';
import {homeCopy,tutorialSteps} from '../lib/home-experience';
import type {DirectoryLanguage} from '../lib/service-directory';
export default function HowToGuide({language,onSpeak,onTry,onStop}:{language:DirectoryLanguage;onSpeak:(s:string)=>void;onTry:()=>void;onStop:()=>void}){
 const [step,setStep]=useState(0);const c=homeCopy[language],steps=tutorialSteps[language];const title=useRef<HTMLHeadingElement>(null),moved=useRef(false);
 useEffect(()=>{if(moved.current)title.current?.focus();moved.current=false},[step]);
 function move(i:number){onStop();moved.current=true;setStep(Math.max(0,Math.min(steps.length-1,i)))}
 return <section className="saathi-tutorial" aria-label={c.how}>
  <div className="tutorial-intro"><BookOpen size={28}/><p className="directory-eyebrow">{c.how}</p><h2>{c.guideTitle}</h2><p>{c.guideIntro}</p>
   <ol className="tutorial-progress">{steps.map(([label],i)=><li key={i}><button aria-current={step===i?'step':undefined} onClick={()=>move(i)}><span>{i<step?<Check size={18}/>:i+1}</span>{label}</button></li>)}</ol>
  </div>
  <div className="tutorial-detail"><span className="tutorial-count">{c.step} {step+1} / {steps.length}</span><h3 ref={title} tabIndex={-1}>{steps[step][0]}</h3><p>{steps[step][1]}</p>
   <div className="tutorial-actions"><button className="directory-listen" onClick={()=>onSpeak(steps[step].join('. '))}><Volume2 size={20}/>{['Listen','सुनें','వినండి'][language==='hi'?1:language==='te'?2:0]}</button><button className="directory-listen" onClick={onStop}>{c.stop}</button></div>
   <div className="tutorial-navigation"><button disabled={step===0} onClick={()=>move(step-1)}><ArrowLeft size={18}/>{c.previous}</button>{step<steps.length-1?<button onClick={()=>move(step+1)}>{c.next}<ArrowRight size={18}/></button>:<button onClick={onTry}>{c.try}<ArrowRight size={18}/></button>}</div>
  </div>
  <div className="tutorial-faq"><h2>{c.faqTitle}</h2>{c.faqs.map(([question,answer])=><details key={question}><summary>{question}</summary><p>{answer}</p></details>)}</div>
 </section>
}
