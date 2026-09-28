import React,{useState} from 'react';
import {ArrowRight,Search,Sparkles} from 'lucide-react';
import {serviceTitle,type DirectoryLanguage} from '../lib/service-directory';
import {launchCopy,launchMatches,quickServices} from '../lib/home-launch';

export default function HomeLaunch({language,onOpen,onBrowse}:{language:DirectoryLanguage;onOpen:(id:string)=>void;onBrowse:(query:string)=>void}){
 const [query,setQuery]=useState('');const c=launchCopy[language],results=launchMatches(query,language);
 return <section className="home-launch" aria-labelledby="launch-title">
  <div className="launch-heading"><span><Sparkles size={21}/></span><h2 id="launch-title">{c.title}</h2></div>
  <form role="search" onSubmit={e=>{e.preventDefault();if(results.length===1)onOpen(results[0].id);else onBrowse(query)}}>
   <label><Search size={23}/><span className="sr-only">{c.title}</span><input value={query} maxLength={250} placeholder={c.hint} onChange={e=>setQuery(e.target.value)} /></label>
   <button type="submit">{c.search}<ArrowRight size={19}/></button>
  </form>
  {query.trim()?<div className="launch-results"><p role="status">{results.length?`${c.results} · ${results.length}`:c.empty}</p>{results.slice(0,4).map(s=><button key={s.id} onClick={()=>onOpen(s.id)}><span>{serviceTitle(s.id,language)}<small>{s.source?c.official:c.preparation}</small></span><ArrowRight size={17}/></button>)}<button className="launch-all" onClick={()=>onBrowse(query)}>{results.length?c.more:c.all}<ArrowRight size={17}/></button></div>:<div className="launch-popular"><p>{c.popular}</p><div>{quickServices.map(id=><button key={id} onClick={()=>onOpen(id)}>{serviceTitle(id,language)}<ArrowRight size={15}/></button>)}</div></div>}
 </section>
}
