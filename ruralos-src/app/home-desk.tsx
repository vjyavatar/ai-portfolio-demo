import React from 'react';
import {ArrowRight,HeartHandshake,FileCheck2,Plane,House,GraduationCap,Wheat,ShieldCheck,BookOpen,MapPin,Volume2} from 'lucide-react';
import {deskCopy,deskActions} from '../lib/home-desk';
import type {DirectoryLanguage} from '../lib/service-directory';
const icons=[HeartHandshake,FileCheck2,Plane,House,GraduationCap,Wheat];
export function HomeDesk({language,heading,voice,search}:{language:DirectoryLanguage;heading:React.Ref<HTMLHeadingElement>;voice:React.ReactNode;search:React.ReactNode}){
 const c=deskCopy[language];return <section className="desk-hero">
  <div className="desk-welcome"><p className="desk-eyebrow"><span/>{c.eyebrow}</p><h1 ref={heading} tabIndex={-1}>{c.title}<br/><em>{c.accent}</em></h1><p className="desk-intro">{c.intro}</p>{voice}<p className="desk-trust"><ShieldCheck size={17}/>{c.trust}</p><div className="desk-locale"><span><MapPin size={15}/>{c.region}</span><span><Volume2 size={15}/>{c.language}</span></div></div>
  <div className="desk-search">{search}</div>
 </section>;
}
export function HomeStarts({language,onOpen}:{language:DirectoryLanguage;onOpen:(id:string)=>void}){
 const c=deskCopy[language];return <section className="desk-starts" aria-labelledby="desk-starts-title"><h2 id="desk-starts-title">{c.start}</h2><div>{deskActions.map((id,i)=>{const Icon=icons[i];return <button key={id} data-tone={i} onClick={()=>onOpen(id)}><span className="desk-start-icon"><Icon size={26}/></span><strong>{c.labels[i]}</strong><small>{c.details[i]}</small><ArrowRight size={18}/></button>})}</div></section>;
}
export function HomeSteps({language,children}:{language:DirectoryLanguage;children:React.ReactNode}){
 const c=deskCopy[language];return <section className="desk-how" aria-labelledby="desk-how-title"><div className="desk-how-heading"><BookOpen size={24}/><h2 id="desk-how-title">{c.how}</h2></div><ol>{c.steps.map((step,i)=><li key={step}><span>{i+1}</span><div><strong>{step}</strong><p>{c.stepDetails[i]}</p></div></li>)}</ol><details><summary>{c.openGuide}<ArrowRight size={18}/></summary>{children}</details></section>;
}
