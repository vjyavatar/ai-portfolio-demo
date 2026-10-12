const fs=require('node:fs'),vm=require('node:vm'),core=require('../static/workspace-core.js');
const source=fs.readFileSync('static/app.js','utf8'),scope={};
vm.runInNewContext(source.slice(source.indexOf('var TAB_GROUPS ='),source.indexOf("window._activeGroup = 'overview'")),scope);
const items=core.catalog(scope.TAB_GROUPS,{});
items.push({group:'decide',tab:'_active',label:'Active Trading'},{group:'dream',tab:'_today',label:'Today’s Setups'});
const profiles={public:{role:'public'},trading:{role:'trading'},full:{role:'full'},premium:{role:'full',premium:true},dream:{role:'full',premium:true,dream:true},admin:{role:'admin',premium:true,dream:true}};
process.stdout.write(JSON.stringify(items.map(t=>({...t,access:Object.fromEntries(Object.entries(profiles).map(([k,v])=>[k,core.canOpen(t.group,t.tab,v)])),functional_status:'UNVERIFIED',reason:'Menu inventory is not proof of rendered output or financial accuracy.'})),null,2));
