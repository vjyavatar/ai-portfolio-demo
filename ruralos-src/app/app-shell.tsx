'use client';
import {useEffect,useState} from 'react';
import FamilyApp from './family-app';
import GuidedApp from './guided-app';
import {Language} from '@/lib/languages';
export default function AppShell(){const[language,setLanguage]=useState<Language>('en');const[guided,setGuided]=useState(false);useEffect(()=>{const p=new URLSearchParams(location.search);const l=p.get('language');if(l==='hi'||l==='te'||l==='en'){setLanguage(l);setGuided(true)}else document.documentElement.lang='en'},[]);function change(l:Language){setLanguage(l);setGuided(true);if(!(window as any).__SAATHI_NATIVE__)history.replaceState(null,'','/ruralos/?language='+l);document.documentElement.lang=l}return guided?<GuidedApp key={language} language={language} onLanguage={change}/>:<FamilyApp/>}
