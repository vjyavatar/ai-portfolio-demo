'use strict';
function contribution(values) {
  if(values.some(v=>!Number.isFinite(v)||v<0||v>1000000))return null;
  const [buy,resale,shipping,repairs,fees,reserve]=values;
  const cost=buy+shipping+repairs+fees+reserve;
  return {cost,profit:resale-cost,margin:resale>0?(resale-cost)/resale*100:null};
}
if(typeof module!=='undefined')module.exports={contribution};
if(typeof document!=='undefined'){
  const ids=['buy','resale','shipping','repairs','fees','reserve'];
  const money=new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'});
  function update(){const values=ids.map(id=>{const v=document.getElementById(id).value;return v===''?NaN:Number(v);});const result=contribution(values);document.getElementById('contribution').textContent=result?money.format(result.profit):'Check inputs';document.getElementById('cost-note').textContent=result?'Total costs: '+money.format(result.cost)+' · Estimated margin: '+(result.margin===null?'N/A':result.margin.toFixed(1)+'%'):'Enter a nonnegative amount in every field.';}
  ids.forEach(id=>document.getElementById(id).addEventListener('input',update));update();
}
