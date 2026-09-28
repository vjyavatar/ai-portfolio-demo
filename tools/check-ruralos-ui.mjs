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
 const {HomeDesk,HomeStarts,HomeSteps}=await server.ssrLoadModule('/app/home-desk.tsx');
 const {default:Travel}=await server.ssrLoadModule('/app/travel-planner.tsx');
 for(const language of ['en','hi','te']){
  const hero=render(React.createElement(HomeDesk,{language,voice:React.createElement('button',null,'Speak'),search:React.createElement('input',{'aria-label':'Search'}),heading:null}));
  assert.match(hero,/<h1/);assert.match(hero,/aria-label="Search"/);assert.doesNotMatch(hero,/undefined|NaN/);checks++;
  const starts=render(React.createElement(HomeStarts,{language,onOpen:()=>{}}));assert.equal((starts.match(/<button/g)||[]).length,6);assert.equal((starts.match(/<small>/g)||[]).length,6);checks++;
  const steps=render(React.createElement(HomeSteps,{language,children:'Tutorial'}));assert.equal((steps.match(/<li>/g)||[]).length,3);assert.match(steps,/<details><summary>/);checks++;
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
 console.log(`${checks} rendered UI checks passed: languages, direct starts, guide, travel modes, consent and protected tracking.`);
}finally{await server.close()}
