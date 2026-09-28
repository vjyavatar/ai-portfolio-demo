// Local release check; requires ruralos-src development dependencies.
// Renders actual React components, without browser/audio/provider side effects.
import assert from 'node:assert/strict';
import {createServer} from '../ruralos-src/node_modules/vite/dist/node/index.js';
import {resolve} from 'node:path';
import React from '../ruralos-src/node_modules/react/index.js';
import {renderToStaticMarkup as render} from '../ruralos-src/node_modules/react-dom/server.node.js';
const server=await createServer({configFile:false,root:resolve('ruralos-src'),server:{middlewareMode:true},optimizeDeps:{noDiscovery:true,include:[]},appType:'custom'});
let checks=0;
try{
 const {ProgrammeCards,default:Enterprise}=await server.ssrLoadModule('/app/enterprise-guide.tsx');
 const {default:HomeVideo}=await server.ssrLoadModule('/app/home-video.tsx');
 const {programmes}=await server.ssrLoadModule('/lib/enterprise.ts');
 const {HomeDesk,HomeStarts,HomeSteps}=await server.ssrLoadModule('/app/home-desk.tsx');
 const {default:Travel}=await server.ssrLoadModule('/app/travel-planner.tsx');
 const {default:Preparation}=await server.ssrLoadModule('/app/service-preparation.tsx');
 const {default:Comparison}=await server.ssrLoadModule('/app/travel-comparison.tsx');
 const {playbooks}=await server.ssrLoadModule('/lib/service-playbooks.ts');
 const {default:Mobile}=await server.ssrLoadModule('/app/aadhaar-mobile-help.tsx');
 const {default:Alerts}=await server.ssrLoadModule('/app/alert-preview.tsx');
 const {default:TaskGuide}=await server.ssrLoadModule('/app/task-assistant.tsx');
 const {ScenarioAnswer}=await server.ssrLoadModule('/app/scenario-help.tsx');
 const {serviceScenarios}=await server.ssrLoadModule('/lib/service-scenarios.ts');
 for(const language of ['en','hi','te']){
  for(const offline of [false,true]){
   const cards=render(React.createElement(ProgrammeCards,{language,offline,now:Date.parse('2026-09-29T00:00:00Z')}));
   assert.equal((cards.match(/<article/g)||[]).length,7);for(const p of programmes)assert.ok(cards.includes(p.name));
   if(offline)assert.doesNotMatch(cards,/<a /);else assert.match(cards,/noopener noreferrer/);checks++;
   const expired=render(React.createElement(ProgrammeCards,{language,offline,now:Date.parse('2026-10-12T00:00:00Z')}));assert.doesNotMatch(expired,/₹|5%/);checks++;
   const vid=render(React.createElement(HomeVideo,{language,offline,onSpeak:()=>{},onStop:()=>{},onOpen:()=>{}}));
   if(offline)assert.doesNotMatch(vid,/<video/);else{assert.match(vid,/preload="none"/);assert.match(vid,new RegExp('srcLang="'+language+'"'));assert.doesNotMatch(vid,/autoPlay/);}assert.match(vid,/<ol>/);checks++;
  }

  for(const s of serviceScenarios){
   const props={serviceId:s.service,scenarioId:s.id,region:'Telangana',language,now:Date.parse('2026-09-29T00:00:00Z')};
   const html=render(React.createElement(ScenarioAnswer,props));
   assert.match(html,/<h5/g);assert.ok(html.includes(s.next[language].replaceAll('&','&amp;').replaceAll("'",'&#x27;')));assert.match(html,/2026-09-28/);assert.match(html,/2026-10-12/);assert.doesNotMatch(html,/<input|<textarea|undefined|NaN/);checks++;
   const offline=render(React.createElement(ScenarioAnswer,{...props,offline:true}));assert.doesNotMatch(offline,/<a /);checks++;
   const stale=render(React.createElement(ScenarioAnswer,{...props,now:Date.parse('2026-10-12T00:00:00Z')}));assert.doesNotMatch(stale,/<h5|₹|<a /);assert.match(stale,/role="status"/);checks++;
  }
  for(const initialService of ['schemes','aadhaar','land']){
   const guide=render(React.createElement(TaskGuide,{initialService,initialLanguage:language,onLanguageChange:()=>{}}));
   assert.equal((guide.match(/<select/g)||[]).length,1,'embedded guide uses one regional selector, not a second language selector');
   assert.match(guide,/class="journey-progress" role="status"/);assert.match(guide,/1 \/ 2/);
   assert.match(guide,/<details class="task-voice-consent journey-voice"><summary>/);
   assert.doesNotMatch(guide,/type="checkbox"[^>]*checked|<details[^>]* open/);
   assert.match(guide,/<button[^>]*disabled=""/);assert.match(guide,/class="journey-question"/);checks++;
  }
  const mobile=render(React.createElement(Mobile,{language,stopOtherAudio:()=>{}}));assert.equal((mobile.match(/aria-pressed=/g)||[]).length,4);assert.equal((mobile.match(/aria-pressed="true"/g)||[]).length,1);assert.doesNotMatch(mobile,/<input|<textarea/);assert.match(mobile,/uidai.gov.in/);checks++;
  const alerts=render(React.createElement(Alerts,{language}));assert.match(alerts,/href="\/ruralos\/alerts\/"/);assert.match(alerts,/role="status"/);assert.doesNotMatch(alerts,/undefined|NaN/);checks++;
  const hero=render(React.createElement(HomeDesk,{language,voice:React.createElement('button',null,'Speak'),search:React.createElement('input',{'aria-label':'Search'}),heading:null}));
  assert.match(hero,/<h1/);assert.match(hero,/aria-label="Search"/);assert.doesNotMatch(hero,/undefined|NaN/);checks++;
  const starts=render(React.createElement(HomeStarts,{language,onOpen:()=>{}}));assert.equal((starts.match(/<button/g)||[]).length,6);assert.equal((starts.match(/<small>/g)||[]).length,6);checks++;
  const steps=render(React.createElement(HomeSteps,{language,children:'Tutorial'}));assert.equal((steps.match(/<li>/g)||[]).length,3);assert.match(steps,/<details><summary>/);checks++;
  for(const [serviceId,p] of Object.entries(playbooks))for(const goal of p.goals){
   const html=render(React.createElement(Preparation,{serviceId,goal,region:'Telangana',language,stopOtherAudio:()=>{}}));
   assert.equal((html.match(/type="checkbox"/g)||[]).length,4);assert.equal((html.match(/aria-pressed="true"/g)||[]).length,serviceId==="aadhaar"?2:1);assert.match(html,/Telangana/);assert.match(html,/lang="en"/);assert.doesNotMatch(html,/undefined|NaN/);assert.ok(html.includes(p.actions[p.goals.indexOf(goal)].replaceAll('&','&amp;').replaceAll("'",'&#x27;')));checks++;
  }
  const comparison=render(React.createElement(Comparison,{plan:{origin:'A',destination:'B',when:'2099-01',travellers:'2',budget:'5000'},mode:'flight',language}));assert.equal((comparison.match(/inputMode="decimal"/g)||[]).length,9);assert.doesNotMatch(comparison,/checked=""|NaN|undefined/);assert.match(comparison,/2,500/);checks++;
  for(const initialMode of ['flight','rail','cab','holiday','sea']){
   const html=render(React.createElement(Travel,{initialMode,language,offline:true}));
   assert.match(html,new RegExp(`type="${initialMode==='cab'?'date':'month'}"`));
   assert.equal((html.match(/aria-pressed="true"/g)||[]).length,1);
   assert.match(html,/type="checkbox"/);assert.doesNotMatch(html,/type="checkbox"[^>]*checked/);
   assert.match(html,/<button[^>]*disabled=""/); // capture stays disabled before consent
   assert.match(html,/href="\/ruralos\/tracking"/); // existing protected route only
   assert.doesNotMatch(html,/value="undefined"|value="NaN"/);checks++;
  }
 }
 const hostile=render(React.createElement(Preparation,{serviceId:'land',goal:'<script>alert(1)</script>',region:'<img src=x onerror=alert(1)>',language:'en',stopOtherAudio:()=>{}}));assert.doesNotMatch(hostile,/<script|<img/);assert.match(hostile,/&lt;img/);checks++;
 console.log(`${checks} rendered UI checks passed: all service purposes in three languages, comparison, escaping, direct starts, guide, travel modes, consent and protected tracking.`);
}finally{await server.close()}
