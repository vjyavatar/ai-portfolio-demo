
import React from 'react';
import {createRoot} from 'react-dom/client';
import LiveHub from './app/live-hub';
import TaskAssistant from './app/task-assistant';
import FamilyApp from './app/app-shell';
import {evaluatePension} from './lib/rules';
import './app/globals.css';
const origin='https://rural-family-action-os.vjyrcks.chatgpt.site';

const originalFetch=window.fetch.bind(window);
window.fetch=async(input:any,init?:RequestInit)=>{const path=typeof input==='string'?input:input.url;if(path==='/api/session')return Response.json({signedIn:false,name:null,admin:false});if(path==='/api/eligibility'){try{return Response.json(evaluatePension(JSON.parse(String(init?.body))))}catch{return Response.json({error:'Please check your answers.'},{status:400})}}if(path.startsWith('/api/'))return Response.json({error:'Open the secure web app to save private records.'},{status:401});return originalFetch(input,init)};
document.addEventListener('click',e=>{const a=(e.target as Element).closest('a');if(!a)return;const href=a.getAttribute('href');if(href?.startsWith('/ruralos/')){e.preventDefault();location.href=href;return}if(href==='/'){e.preventDefault();location.href='/ruralos/';return}if(href?.startsWith('/?language=')){e.preventDefault();location.search=href.slice(1);return}if(href?.startsWith('/')){e.preventDefault();location.href=origin+href;}});
createRoot(document.getElementById('root')!).render(<React.StrictMode><div className="notice" style={{margin:0,borderRadius:0}}>Public guidance · Early access. For saved family details, reminders and help requests, open the secure family app.</div><LiveHub/><TaskAssistant/><FamilyApp/></React.StrictMode>);

if('serviceWorker' in navigator)navigator.serviceWorker.register('/ruralos/sw.js',{scope:'/ruralos/'}).catch(()=>{});
