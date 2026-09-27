const fs=require('fs'),vm=require('vm'),assert=require('assert');
class El{
 constructor(tag='div'){this.tagName=tag;this.children=[];this.events={};this.attrs={};this.dataset={};this.style={};this.value='';this.textContent='';this.checked=false;this.validityMessage='';}
 append(...items){this.children.push(...items);for(const i of items)if(i&&typeof i==='object')i.parent=this;}
 replaceChildren(...items){this.children=[];this.append(...items);}
 setAttribute(k,v){this.attrs[k]=v;}
 addEventListener(k,v){(this.events[k]||=[]).push(v);}
 setCustomValidity(v){this.validityMessage=v;}
 async dispatch(k){for(const cb of this.events[k]||[])await cb({preventDefault(){}});}
 click(){return this.dispatch('click');}remove(){if(this.parent)this.parent.children=this.parent.children.filter(x=>x!==this);}scrollIntoView(){}
}
const html=fs.readFileSync('nextstep/index.html','utf8'),ids={};for(const m of html.matchAll(/id="([^"]+)"/g))ids[m[1]]=new El();
const walk=el=>[el,...el.children.flatMap(i=>i instanceof El?walk(i):[])];let downloaded,printed=false;
const document={body:new El('body'),createElement:t=>new El(t),createTextNode:t=>({textContent:t}),getElementById:id=>{assert(ids[id],`Missing HTML id ${id}`);return ids[id]},querySelectorAll:q=>q==='.opportunity'?ids.opportunities.children:q.startsWith('[name=strength]')?walk(ids.skills).filter(e=>e.name==='strength'&&(!q.includes(':checked')||e.checked)):[]};
const ctx=vm.createContext({document,console,Set,Map,Blob,URL:{createObjectURL:b=>{downloaded=b;return'blob:test'},revokeObjectURL(){}},navigator:{clipboard:{writeText:async t=>{ctx.copied=t}}},setTimeout:fn=>fn(),matchMedia:()=>({matches:false}),window:{addEventListener(){},print(){printed=true}}});
vm.runInContext(fs.readFileSync('nextstep/app.js','utf8')+';globalThis.test={recommend,strengths,paths,generate,snapshot,validateSnapshot,evidenceMessage,renderPlan};',ctx);
(async()=>{
const api=ctx.test;assert.equal(ids.opportunities.children.length,3);assert.equal(ids.days.children.length,7);
let combinations=0;for(let mask=0;mask<256;mask++){const skills=api.strengths.filter((_,i)=>mask&(1<<i));if(skills.length>3)continue;for(const hours of [2,5,10])for(const setting of ['either','online','local'])for(const goal of ['income','confidence','community']){const list=api.recommend({skills,hours,setting,goal});assert.equal(list.length,3);assert.equal(new Set(list.map(p=>p.id)).size,3);assert(list.every(p=>setting==='either'||p.mode==='either'||p.mode===setting));combinations++;}}
const inputs=document.querySelectorAll('[name=strength]');for(let i=0;i<4;i++){inputs[i].checked=true;await inputs[i].dispatch('change');}assert.equal(inputs[3].checked,false,'fourth strength is rejected');
api.generate({skills:['Writing'],hours:5,setting:'online',goal:'income'});assert.equal(api.snapshot().path,'writing');const check=ids.days.children[0].children[0];check.checked=true;await check.dispatch('change');assert.equal(ids['progress-label'].textContent,'1 of 7 done');ids.notes.value='<script>alert(1)</script>';await ids.notes.dispatch('input');ids.conversations.value='6';await ids.conversations.dispatch('input');assert(ids['experiment-verdict'].textContent.includes('several conversations'));
const initial=JSON.stringify(api.snapshot());api.renderPlan(api.paths.find(x=>x.id==='design'));api.renderPlan(api.paths.find(x=>x.id==='writing'));assert.equal(JSON.stringify(api.snapshot()),initial,'switching paths preserves progress and notes');
await ids['download-plan'].click();const saved=JSON.parse(await downloaded.text());assert.equal(saved.experiment.notes,'<script>alert(1)</script>');assert.equal(saved.experiment.conversations,6);assert.equal(api.validateSnapshot(saved).path,'writing');
api.generate({skills:[],hours:2,setting:'local',goal:'community'});ids['plan-file'].files=[{size:1000,text:async()=>JSON.stringify(saved)}];await ids['plan-file'].dispatch('change');assert.equal(api.snapshot().path,'writing');assert.equal(ids.notes.value,'<script>alert(1)</script>');assert.equal(ids['progress-label'].textContent,'1 of 7 done');
const before=JSON.stringify(api.snapshot());for(const bad of [{}, {...saved,version:99},{...saved,path:'missing'}, {...saved,experiment:{...saved.experiment,done:[9]}},{...saved,experiment:{...saved.experiment,conversations:-1}},{...saved,experiment:{...saved.experiment,notes:'x'.repeat(4001)}}])assert.throws(()=>api.validateSnapshot(bad));
ids['plan-file'].files=[{size:4,text:async()=>'{bad'}];await ids['plan-file'].dispatch('change');assert.equal(JSON.stringify(api.snapshot()),before);ids['plan-file'].files=[{size:100001}];await ids['plan-file'].dispatch('change');assert.equal(JSON.stringify(api.snapshot()),before);
ids.pilots.value='-3';await ids.pilots.dispatch('input');assert(ids.pilots.validityMessage);assert.equal(api.snapshot().experiment.pilots,0);ids.pilots.value='1';await ids.pilots.dispatch('input');ids.repeats.value='1';await ids.repeats.dispatch('input');assert(ids['experiment-verdict'].textContent.includes('useful signal'));
await ids['copy-prompt'].click();assert(ctx.copied.includes('Help me prepare'));await ids['share-copy'].click();assert.equal(ctx.copied,'https://celesys.ai/nextstep/');assert(!ids['share-whatsapp'].href.includes('script'));await ids['print-plan'].click();assert(printed);
assert.throws(()=>api.recommend({skills:[],hours:5,setting:'either',goal:'income',extra:true}));
console.log(`PASS: ${combinations} recommendation combinations; full plan interactions in a simulated DOM; download/import round-trip; invalid and oversized imports; preserved path progress; metrics validation; text-only notes; sharing and copy actions. This is not visual browser QA.`);
})().catch(e=>{console.error(e);process.exitCode=1;});
