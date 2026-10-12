import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
class Element {
 constructor(){this.children=[];this.events={};this.dataset={region:'IN'};this.value='';this.hidden=false;this.textContent='';}
 append(...c){this.children.push(...c);}
 replaceChildren(...c){this.children=[...c];}
 addEventListener(name,fn){this.events[name]=fn;}
 async emit(name){await this.events[name]?.({preventDefault(){}});}
}
function setup(file,initial={}){
 const nodes=new Map();
 const element=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
 for(const [id,value] of Object.entries(initial))element(id).value=value;
 let resolveFetch;
 const context=vm.createContext({document:{getElementById:element,createElement:()=>new Element()},Option:class extends Element{constructor(t,v){super();this.textContent=t;this.value=v;}},Intl,Date,URLSearchParams,AbortController,Blob,URL,setTimeout:()=>1,clearTimeout(){},setInterval(){},fetch:()=>new Promise(r=>resolveFetch=r)});
 vm.runInContext(fs.readFileSync(new URL('../discovery/'+file,import.meta.url),'utf8'),context);
 return {element,respond:payload=>resolveFetch({ok:true,json:async()=>payload}),context};
}
test('options discard out-of-order responses after selection changes',async()=>{
 const a=setup('options.js',{'india-symbol':'NIFTY'});const promise=a.element('chain-form').emit('submit');
 await a.element('india-symbol').emit('change');a.respond({status:'SNAPSHOT',rows:[{strike:1}],expiries:[]});await promise;
 assert.equal(a.element('chain-table').hidden,true);assert.equal(a.element('chain-rows').children.length,0);
});
test('option rows render provider text safely and suppress PCR for missing OI',async()=>{
 const a=setup('options.js',{'india-symbol':'NIFTY'});const promise=a.element('chain-form').emit('submit');
 a.respond({status:'SNAPSHOT',source:'Test',currency:'INR',freshness:'UNVERIFIED_OR_STALE',fetched_at:1,expiries:['2099-01-01'],expiry:'2099-01-01',rows:[{strike:100,call:{oi:0,contract:'<script>bad</script>'},put:{oi:null}}],message:'Snapshot'});await promise;
 assert.equal(a.element('chain-table').hidden,false);assert.equal(a.element('chain-rows').children.length,1);assert.match(a.element('chain-summary').textContent,/PCR —/);
 const content=a.element('chain-rows').children[0].children.at(-1).children[0].children.map(e=>e.textContent).join(' ');
 assert.match(content,/<script>bad<\/script>/); // literal textContent, never inserted as HTML
});
test('agents show all five sections, blocked AI and reset stale results',async()=>{
 const a=setup('agents.js',{'brief-mode':'stock','brief-region':'US','brief-symbol':'AAPL'});const promise=a.element('brief-form').emit('submit');
 a.respond({mode:'stock',region:'US',assessment:'Incomplete',counterargument:'Other scenarios',next_check:'Read filings',missing_data:['Source dates'],evidence:[],agents:[],ai_status:'NOT_ENABLED',ai:null});await promise;
 assert.equal(a.element('brief-output').hidden,false);assert.equal(a.element('ai-output').hidden,true);assert.equal(a.element('brief-assessment').textContent,'Incomplete');assert.match(a.element('brief-status').textContent,/not enabled/);
 await a.element('brief-symbol').emit('input');assert.equal(a.element('brief-output').hidden,true);
});
test('legacy shared links forward to research without external redirects',()=>{
 let next;vm.runInNewContext(fs.readFileSync(new URL('../discovery/home.js',import.meta.url),'utf8'),{URLSearchParams,location:{search:'?sym=MU&autoanalyze=1',hash:'',replace:v=>next=v}});assert.equal(next,'/research?sym=MU&autoanalyze=1');
});
