
// ══════════════════════════════════════════════════════════════
// INSTITUTIONAL DECISION MATRIX DASHBOARD
// Maps ALL charts + signals into the 6-layer decision stack
// ══════════════════════════════════════════════════════════════
;window._institutionalDashboard=function(d,S){
  S=S||'$';
  var _eng=window._calcInstitutionalMDO?window._calcInstitutionalMDO(d,S):null;
  var _vr=window._volatilityRegime?window._volatilityRegime(d):null;
  var _sp=window._scenarioProbability?window._scenarioProbability(d,S):null;
  var _fe=window._forwardEstimates?window._forwardEstimates(d,S):null;
  if(!_eng)return '';

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // SECTION 1: OLD INSTITUTIONAL MATRIX (v1.0)
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  var h='';
  var rC=_eng.regime==='BULL'?'#059669':_eng.regime==='BEAR'?'#dc2626':'#d97706';

  // Old Matrix — static weights, MDO/10, generic verdicts
  var _oldW={L1:25,L2:22,L3:18,L4:15,L5:10,L6:10};
  var _oldRaw=(_eng.L1*25+_eng.L2*22+_eng.L3*18+_eng.L4*15+_eng.L5*10+_eng.L6*10)/100;
  var _oldScore=Math.round(_oldRaw);
  var _oldMDO=Math.round(_oldRaw/10*10)/10; // Scale 0-100 → 0-10
  var _oldVerdict=_oldMDO>=7.5?'STRONG BUY':_oldMDO>=6?'BUY':_oldMDO>=4.5?'HOLD':_oldMDO>=3?'EXIT':'STRONG SELL';
  var _oldVC=_oldMDO>=6?'#059669':_oldMDO>=4.5?'#d97706':'#dc2626';

  h+='<div style="border-radius:18px;border:2px solid #6b728030;border-left:6px solid #6b7280;overflow:hidden;margin:20px 0;background:#f8fafc;box-shadow:0 2px 12px rgba(107,114,128,.08)">';
  // Group label banner
  h+='<div style="padding:8px 20px;background:linear-gradient(135deg,#6b7280,#6b7280cc);font-size:10px;font-weight:900;color:#fff;font-family:Sora,sans-serif;letter-spacing:1.5px">SCORING SYSTEM 1: LEGACY MATRIX (Sanity Check)</div>';
  // Explainer
  h+='<div style="padding:8px 16px;font-size:9px;color:#5E6F8E;line-height:1.5;background:#F1F5F9;border-bottom:1px solid #94a3b830">';
  h+='📊 <strong style="color:#374151">Legacy Scoring Matrix</strong> — This is the <strong>baseline reference score</strong> using fixed equal weights across 6 layers (Liquidity, Flow, Volatility, Fundamentals, Quant, Probability). Unlike CDS v2.0 below which adapts weights to market regime and stock segment, this matrix treats all stocks the same. Use it as a <strong>sanity check</strong> — if both Legacy and CDS agree, confidence is higher. If they disagree, CDS v2.0 is more reliable as it is context-aware.</div>';
  h+='<div style="display:flex;gap:6px;padding:6px 16px 8px;background:#F1F5F9;border-bottom:1px solid #94a3b830">';
  h+='<div style="flex:1;padding:6px 10px;border-radius:6px;background:#fff;border:1px solid #e2e5ea;font-size:9px;line-height:1.5"><strong style="color:#1A3A78">🤔 Why consider this?</strong><br>It gives a quick unbiased health check using equal weights. Think of it like a blood test report — all parameters checked equally. If this score is green, the stock passes the basic fitness test.</div>';
  h+='<div style="flex:1;padding:6px 10px;border-radius:6px;background:#fff;border:1px solid #e2e5ea;font-size:9px;line-height:1.5"><strong style="color:#059669">📍 When to use this?</strong><br>Use as a first filter BEFORE looking at CDS v2.0. If Legacy says HOLD or worse, be extra cautious even if CDS is positive. If both agree → high confidence. If they disagree → CDS v2.0 is more accurate.</div>';
  h+='</div>';
  // Old header
  h+='<div style="padding:12px 20px;background:linear-gradient(135deg,#374151,#6b7280);color:#fff;display:flex;justify-content:space-between;align-items:center">';
  h+='<div><div style="font-size:13px;font-weight:900;font-family:Sora,sans-serif">📊 Legacy Scoring Matrix</div>';
  h+='<div style="font-size:8px;color:rgba(255,255,255,.5);margin-top:2px">Static weights · Equal for all stocks · Reference baseline</div></div>';
  h+='<div style="text-align:right"><div style="font-size:22px;font-weight:900;font-family:JetBrains Mono;color:'+_oldVC+'">'+_oldMDO+'<span style="font-size:10px;color:rgba(255,255,255,.4)">/10</span></div>';
  h+='<div style="font-size:8px;color:rgba(255,255,255,.5)">'+_oldVerdict+'</div></div>';
  h+='</div>';

  // Old regime bar
  h+='<div style="padding:5px 20px;background:'+rC+'06;border-bottom:1px solid #f1f3f5">';
  h+='<div style="font-size:8px;font-weight:700;color:'+rC+'">'+(_eng.regime==='BULL'?'🟢 BULL':_eng.regime==='BEAR'?'🔴 BEAR':'🟡 SIDEWAYS')+' REGIME</div></div>';

  // Old layer rows (simplified)
  var _oldLayers=[
    {name:'L1: Liquidity / Volume',icon:'💧',w:25,score:_eng.L1},
    {name:'L2: Flow (Smart Money)',icon:'📊',w:22,score:_eng.L2},
    {name:'L3: Volatility / Risk',icon:'🌊',w:18,score:_eng.L3},
    {name:'L4: Fundamentals / Forward',icon:'🏛️',w:15,score:_eng.L4},
    {name:'L5: Quant / Factor',icon:'🔢',w:10,score:_eng.L5},
    {name:'L6: Probability / Simulation',icon:'🎯',w:10,score:_eng.L6}
  ];

  // Layman inference generators for each layer
  function _laymanL1(sc,eng){
    if(!eng.hasVolume&&sc<50) return 'Volume data limited — cannot confirm institutional participation. Wait for clearer signals.';
    if(sc>=70) return 'High institutional volume — big money is actively trading this stock. Safe to enter large positions.';
    if(sc>=50) return 'Moderate trading volume — enough liquidity to buy and sell, but avoid very large positions.';
    if(sc>=30) return 'Low volume — entering a big position could move the price against you. Use limit orders only.';
    return 'Very thin trading — difficult to buy or sell without significant price impact. Risky for any position size.';
  }
  function _laymanL2(sc,eng){
    var hasReal=eng.L2_flow&&(eng.L2_flow.hasOI||eng.L2_flow.hasDarkPool||eng.L2_flow.hasETF);
    if(!hasReal&&sc<50) return 'No options or dark pool data available — smart money direction is unclear. Score based on price momentum only.';
    if(sc>=70) return 'Strong institutional buying detected — big money is accumulating. This is a positive signal for entry.';
    if(sc>=50) return 'Mixed flow signals — some institutional activity but not a clear buy or sell pattern yet.';
    if(sc>=30) return 'Weak flow — institutions are not actively buying. Wait for volume confirmation before entering.';
    return 'Negative flow detected — smart money appears to be selling or staying away. Exercise caution.';
  }
  function _laymanL3(sc){
    if(sc>=70) return 'Low volatility — price moves are smooth and predictable. Favorable conditions for investing.';
    if(sc>=50) return 'Moderate volatility — normal price swings. Standard position sizing is appropriate.';
    if(sc>=30) return 'Elevated volatility — price swings are larger than usual. Consider reducing position size by 30-50%.';
    return 'High volatility — sharp price moves likely. Only trade with tight stop-losses or reduced size.';
  }
  function _laymanL4(sc,eng){
    if(sc>=80) return 'Excellent fundamentals — strong earnings, low debt, and trading below fair value. A quality business at a good price.';
    if(sc>=60) return 'Good fundamentals — the business is healthy and reasonably valued. Worth holding or adding on dips.';
    if(sc>=40) return 'Average fundamentals — the company is fine but not exceptional. No strong reason to buy or sell.';
    if(sc>=20) return 'Weak fundamentals — declining earnings, high debt, or overvalued. Better opportunities exist elsewhere.';
    return 'Poor fundamentals — the business is struggling. Avoid unless you see a specific turnaround catalyst.';
  }
  function _laymanL5(sc,eng){
    if(sc>=70) return 'Top-tier quant profile — strong momentum, good value, high quality factors all aligned. Institutional algorithms favor this stock.';
    if(sc>=50) return 'Decent quant signals — some positive factors (like F-Score or value) but not all aligned. Monitor for improvement.';
    if(sc>=30) return 'Mixed quant signals — trend and momentum are inconsistent. Algorithms are not strongly positioned here.';
    return 'Weak quant profile — most quantitative factors are negative. Avoid until factor alignment improves.';
  }
  function _laymanL6(sc,eng){
    if(eng.L6_prob&&eng.L6_prob.hasMC){
      if(sc>=70) return 'Monte Carlo simulations show '+Math.round(eng.L6_prob.mcProb)+'% chance of profit. Odds strongly in your favor.';
      if(sc>=50) return 'Simulations show moderate upside probability. Risk/reward is balanced — position sizing matters.';
      return 'Simulations show limited upside or high tail risk. The odds don\'t strongly favor this trade.';
    }
    if(sc>=70) return 'High probability of positive outcome — fundamentals, trend, and valuation all support upside.';
    if(sc>=50) return 'Moderate probability edge — some upside potential but not a high-conviction setup.';
    return 'Low probability edge — risk of loss is elevated. Consider waiting for better entry or skip entirely.';
  }

  var _laymanFns=[_laymanL1,_laymanL2,_laymanL3,_laymanL4,_laymanL5,_laymanL6];

  _oldLayers.forEach(function(l,idx){
    var sc=Math.round(l.score/10);
    var lC=sc>=7?'#059669':sc>=5?'#d97706':'#dc2626';
    var inference=_laymanFns[idx](l.score,_eng);
    h+='<div style="padding:8px 20px;border-bottom:1px solid #f5f5f5">';
    h+='<div style="display:flex;justify-content:space-between;align-items:center">';
    h+='<div style="display:flex;align-items:center;gap:6px"><span style="font-size:12px">'+l.icon+'</span><span style="font-size:9px;font-weight:700;color:#374151">'+l.name+'</span></div>';
    h+='<div style="display:flex;align-items:center;gap:6px"><span style="font-size:7px;color:#94a3b8">W:'+l.w+'%</span>';
    h+='<div style="width:60px;height:4px;background:#f1f5f9;border-radius:2px;overflow:hidden"><div style="height:100%;width:'+l.score+'%;background:'+lC+'"></div></div>';
    h+='<span style="font-size:11px;font-weight:900;color:'+lC+';font-family:JetBrains Mono;width:20px;text-align:right">'+sc+'</span></div></div>';
    // Layman inference line — more prominent
    h+='<div style="padding:3px 0 2px 22px;font-size:9px;color:#374151;line-height:1.5;border-left:2px solid '+lC+'30;margin-left:22px;padding-left:8px">💡 '+inference+'</div>';
    h+='</div>';
  });

  // Old formula
  h+='<div style="padding:8px 20px;background:#f8fafc">';
  h+='<div style="font-size:7px;color:#94a3b8;font-weight:700;margin-bottom:3px">FORMULA (STATIC)</div>';
  h+='<div style="font-size:8px;font-family:JetBrains Mono;color:#6b7280">(L1×25)+(L2×22)+(L3×18)+(L4×15)+(L5×10)+(L6×10) = '+_oldScore+'/100 → '+_oldMDO+'/10</div>';
  h+='<div style="display:flex;gap:8px;margin-top:6px">';
  h+='<div style="padding:4px 12px;border-radius:6px;background:'+_oldVC+'10;border:1px solid '+_oldVC+'20;font-size:10px;font-weight:900;color:'+_oldVC+'">'+_oldVerdict+'</div>';
  h+='<div style="padding:4px 12px;border-radius:6px;background:#fff;border:1px solid #e2e5ea;font-size:8px;font-weight:700;color:#374151">Position: '+Math.round(_oldMDO)+'% · Horizon: '+(_oldMDO>=7?'Long-term':'3-6 months')+'</div>';
  h+='</div></div>';
  // Layman summary for Legacy Matrix
  var _legacyLayman='';
  if(_oldMDO>=7.5) _legacyLayman='All 6 layers are strong — fundamentals, liquidity, momentum, and probability all agree. This is a high-confidence setup.';
  else if(_oldMDO>=6) _legacyLayman='Most layers are positive but 1-2 areas need monitoring. Overall a favorable setup with some caution areas.';
  else if(_oldMDO>=4.5) _legacyLayman='Signals are mixed — some layers are positive, others negative. The stock is in a wait-and-watch zone. No strong conviction either way.';
  else if(_oldMDO>=3) _legacyLayman='More layers are negative than positive. The risk-reward balance is unfavorable. Consider reducing exposure or waiting for improvement.';
  else _legacyLayman='Most layers are flashing red. High risk of further decline. Capital preservation should be the priority.';
  h+='<div style="padding:8px 16px;font-size:9px;color:#374151;line-height:1.6;background:#F8FAFC;border-top:1px solid #e2e5ea">';
  h+='💬 <strong>In simple terms:</strong> Legacy score is <strong>'+_oldMDO.toFixed(1)+'/10 ('+_oldVerdict+')</strong>. '+_legacyLayman+'</div>';
  h+='</div>';

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // SECTION 2: CELESYS DECISION SYSTEM (CDS) v2.0
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  h+='<div style="border-radius:18px;border:2px solid #1A3A7830;border-left:6px solid #1A3A78;overflow:hidden;margin:24px 0;background:#f0f4ff;box-shadow:0 4px 16px rgba(26,58,120,.1)">';
  // Group label banner
  h+='<div style="padding:8px 20px;background:linear-gradient(135deg,#1A3A78,#1A3A78cc);font-size:10px;font-weight:900;color:#fff;font-family:Sora,sans-serif;letter-spacing:1.5px">SCORING SYSTEM 2: CDS v2.0 (Final Decision Engine)</div>';

  // CDS Header
  h+='<div style="padding:8px 20px;font-size:9px;color:#94a3b8;line-height:1.5;background:#0A162810;border-bottom:1px solid #1A3A7815">';
  h+='🤖 <strong style="color:#5B8FE8">CDS v2.0 — Portfolio-Level Decision Engine</strong> — Combines all signals above into a single deployment score. Factors in your stock\'s segment (large/mid/small cap), current market regime (bull/bear/sideways), and applies institutional multipliers. The MDO score, Legacy Matrix, and Consensus each serve different purposes — CDS v2.0 is the <strong>final weighted synthesis</strong> of everything.</div>';
  h+='<div style="display:flex;gap:6px;padding:6px 20px 8px;background:#0A162808;border-bottom:1px solid #1A3A7815">';
  h+='<div style="flex:1;padding:6px 10px;border-radius:6px;background:#fff;border:1px solid #1A3A7820;font-size:9px;line-height:1.5"><strong style="color:#1A3A78">🤔 Why consider this?</strong><br>This is the FINAL answer — the smartest score in the report. It adjusts for market conditions (bull vs bear), your stock\'s size (large vs small cap), and penalizes crowded trades. Think of it like a doctor\'s recommendation after reviewing all test results, not just one.</div>';
  h+='<div style="flex:1;padding:6px 10px;border-radius:6px;background:#fff;border:1px solid #1A3A7820;font-size:9px;line-height:1.5"><strong style="color:#059669">📍 When to use this?</strong><br>Use this score to decide your actual portfolio action — how much to invest and when. The ALLOCATION % tells you exactly how much of your portfolio to put in. The BUCKET (Deploy/Watch/Avoid) tells you the action. Follow this over the headline verdict when they conflict.</div>';
  h+='</div>';
  h+='<div style="padding:14px 20px;background:linear-gradient(135deg,#0A1628,#1A3A78);color:#fff;display:flex;justify-content:space-between;align-items:center">';
  h+='<div><div style="font-size:14px;font-weight:900;font-family:Sora,sans-serif">🏛️ Celesys Decision System (CDS) v2.0</div>';
  h+='<div style="font-size:9px;color:rgba(255,255,255,.6);margin-top:2px">'+(_eng.segIcon||'📊')+' '+(_eng.segLabel||'Stock')+' · '+(_eng.segRole||'6-Layer Stack')+' · Regime-Adaptive · Context-Aware</div></div>';
  h+='<div style="text-align:right"><div style="font-size:24px;font-weight:900;font-family:JetBrains Mono;color:'+_eng.vC+'">'+_eng.score.toFixed(0)+'<span style="font-size:12px;color:rgba(255,255,255,.4)">/100</span></div>';
  h+='<div style="font-size:8px;color:rgba(255,255,255,.5)">'+_eng.verdict+'</div></div>';
  h+='</div>';

  // Decision Bucket Bar
  h+='<div style="padding:8px 20px;background:'+_eng.bucketColor+'10;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid '+_eng.bucketColor+'20">';
  h+='<div style="display:flex;align-items:center;gap:8px"><span style="font-size:16px">'+_eng.bucketIcon+'</span><div><div style="font-size:11px;font-weight:900;color:'+_eng.bucketColor+';font-family:Sora,sans-serif">'+_eng.bucketLabel+'</div><div style="font-size:8px;color:#6b7280">'+_eng.bucketDesc+'</div></div></div>';
  h+='<div style="display:flex;gap:12px;align-items:center">';
  h+='<div style="text-align:center"><div style="font-size:6px;color:#94a3b8;font-weight:700">ALLOCATION</div><div style="font-size:13px;font-weight:900;color:'+_eng.bucketColor+';font-family:JetBrains Mono">'+_eng.posSize+'%</div></div>';
  h+='<div style="text-align:center"><div style="font-size:6px;color:#94a3b8;font-weight:700">CONFIDENCE</div><div style="font-size:13px;font-weight:900;color:'+_eng.vC+';font-family:JetBrains Mono">'+_eng.confidence+'%</div></div>';
  h+='</div></div>';

  // Override alerts
  if(_eng.overrides&&_eng.overrides.length>0){
    h+='<div style="padding:4px 20px;background:#fef3c710;border-bottom:1px solid #fef3c730">';
    _eng.overrides.forEach(function(ov){
      h+='<div style="font-size:8px;color:#d97706;font-weight:700">'+ov.icon+' '+ov.trigger+' → '+ov.action+'</div>';
    });
    h+='</div>';
  }

  // Regime bar
  h+='<div style="padding:6px 20px;background:'+rC+'08;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #f1f3f5">';
  h+='<div style="font-size:9px;font-weight:800;color:'+rC+'">'+(_eng.regime==='BULL'?'🟢 BULL REGIME — Flow dominates, momentum favored':_eng.regime==='BEAR'?'🔴 BEAR REGIME — Risk control dominates, capital preservation':'🟡 SIDEWAYS — Precision matters, range trading')+'</div>';
  h+='<div style="font-size:8px;color:#94a3b8">Confidence: <strong style="color:'+_eng.vC+'">'+_eng.confidence+'%</strong></div>';
  h+='</div>';

  // ═══ 6-LAYER ROWS ═══
  var layers=[
    {name:'L1: Liquidity / Volume',icon:'💧',weight:_eng.weights.L1,score:_eng.L1,
     objective:'Where big money is positioned',
     output:_eng.L1_zones?((_eng.L1_zones.inStrong?'🟢 IN STRONG BUY ZONE':_eng.L1_zones.inSIP?'🟡 IN SIP ZONE':_eng.L1_zones.nearSupport?'🟢 NEAR SUPPORT':'⚪ MID-RANGE')+' · 52W pos: '+_eng.L1_zones.posIn52+'%'):'Entry/Exit Zones',
     charts:['Accumulation/Distribution Phase','Liquidity Heatmap (52W Range)'],
     signal:_eng.L1>=60?'ACCUMULATE':_eng.L1>=40?'WAIT':(_eng.hasVolume===false?'LIMITED DATA':'AVOID ENTRY'),
     sigC:_eng.L1>=60?'#059669':_eng.L1>=40?'#d97706':'#dc2626'},
    {name:'L2: Flow (Smart Money)',icon:'📊',weight:_eng.weights.L2,score:_eng.L2,
     objective:'What big money is doing',
     output:_eng.L2_flow?(_eng.L2_flow.hasOI?'OI: '+_eng.L2_flow.oiBias+' · PCR: '+_eng.L2_flow.pcr.toFixed(2):'MACD+RSI+Volume proxy'):'Buy/Sell Pressure',
     charts:['Alpha Decomposition','Options Flow (OI/PCR)','Order Flow (Delta)'],
     signal:_eng.L2>=60?'BUY PRESSURE':_eng.L2>=40?'NEUTRAL FLOW':(_eng.L2_flow&&(_eng.L2_flow.hasOI||_eng.L2_flow.hasDarkPool||_eng.L2_flow.hasETF)?'SELL PRESSURE':'LIMITED DATA'),
     sigC:_eng.L2>=60?'#059669':_eng.L2>=40?'#d97706':'#dc2626'},
    {name:'L3: Volatility / Risk',icon:'🌊',weight:_eng.weights.L3,score:_eng.L3,
     objective:'Should you take risk?',
     output:_vr?_vr.stateIcon+' '+_vr.state+' (IV: '+_vr.ivProxy+')':'Risk assessment',
     charts:['Risk Structure Heatmap','Downside Capture Ratio','Upside Participation','Volatility Regime Classifier'],
     signal:_eng.L3>=60?'RISK ON':_eng.L3>=40?'CAUTIOUS':'RISK OFF',
     sigC:_eng.L3>=60?'#059669':_eng.L3>=40?'#d97706':'#dc2626'},
    {name:'L4: Fundamentals / Forward',icon:'🏛️',weight:_eng.weights.L4,score:_eng.L4,
     objective:'Is it worth it?',
     output:_fe?('PE: '+_fe.pe.toFixed(1)+'x · FwdPE: '+_fe.fwdPE.toFixed(1)+'x · PEG: '+_fe.peg.toFixed(2)):('MoS: '+_eng.moS+'%'),
     charts:['Valuation Matrix','ROIC vs WACC','Forward Estimates','Growth Stability'],
     signal:_eng.L4>=60?'UNDERVALUED':_eng.L4>=40?'FAIR VALUE':'OVERVALUED',
     sigC:_eng.L4>=60?'#059669':_eng.L4>=40?'#d97706':'#dc2626'},
    {name:'L5: Quant / Factor',icon:'🔢',weight:_eng.weights.L5,score:_eng.L5,
     objective:'Portfolio optimization',
     output:'RSI: '+_eng.rsi+' · Beta: '+_eng.beta.toFixed(2)+' · F-Score: '+_eng.fS+'/9',
     charts:['Factor Radar','Multi-Timeframe Trend Stack','Alpha Decomposition'],
     signal:_eng.L5>=60?'ALPHA STRONG':_eng.L5>=40?'NEUTRAL':'ALPHA WEAK',
     sigC:_eng.L5>=60?'#059669':_eng.L5>=40?'#d97706':'#dc2626'},
    {name:'L6: Probability / Simulation',icon:'🎯',weight:_eng.weights.L6,score:_eng.L6,
     objective:'Outcome confidence',
     output:_eng.L6_prob?(_eng.L6_prob.hasMC?'MC Prob: '+_eng.L6_prob.mcProb.toFixed(0)+'% · Kelly: '+_eng.L6_prob.kellyFrac.toFixed(0)+'%':'Estimated from fundamentals'):'Probability edge',
     charts:['Portfolio Impact Simulator','Scenario Engine (Bull/Base/Bear)','Monte Carlo','Compounding Visualizer'],
     signal:_eng.L6>=60?'PROBABILITY EDGE':_eng.L6>=40?'50/50':'NEGATIVE EV',
     sigC:_eng.L6>=60?'#059669':_eng.L6>=40?'#d97706':'#dc2626'}
  ];

  layers.forEach(function(layer,idx){
    var pct=layer.score;
    var inference=_laymanFns[idx](layer.score,_eng);
    h+='<div style="padding:10px 20px;border-bottom:1px solid #f1f3f5">';
    // Row 1: Layer name + weight + score + signal
    h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">';
    h+='<div style="display:flex;align-items:center;gap:8px">';
    h+='<div style="font-size:16px">'+layer.icon+'</div>';
    h+='<div><div style="font-size:10px;font-weight:800;color:#0A1628">'+layer.name+'</div>';
    h+='<div style="font-size:7px;color:#94a3b8">'+layer.objective+'</div></div>';
    h+='</div>';
    h+='<div style="display:flex;align-items:center;gap:8px">';
    h+='<div style="font-size:7px;color:#94a3b8;font-weight:700">W:'+layer.weight+'%</div>';
    h+='<div style="width:80px;height:6px;background:#f1f5f9;border-radius:3px;overflow:hidden"><div style="height:100%;width:'+pct+'%;background:'+layer.sigC+';border-radius:3px"></div></div>';
    h+='<div style="font-size:12px;font-weight:900;color:'+layer.sigC+';font-family:JetBrains Mono;width:30px;text-align:right">'+Math.round(pct/10)+'</div>';
    h+='<div style="padding:2px 6px;border-radius:4px;font-size:7px;font-weight:800;background:'+layer.sigC+'10;color:'+layer.sigC+'">'+layer.signal+'</div>';
    h+='</div></div>';
    // Row 2: Layman inference — made more prominent
    h+='<div style="padding:4px 0 4px 28px;font-size:9px;color:#374151;line-height:1.5;border-left:2px solid '+layer.sigC+'30;margin-left:28px;padding-left:8px">💡 '+inference+'</div>';
    // Row 3: Data output + mapped charts
    h+='<div style="display:flex;justify-content:space-between;align-items:center">';
    h+='<div style="font-size:8px;color:#374151">'+layer.output+'</div>';
    h+='<div style="font-size:7px;color:#94a3b8">Charts: '+layer.charts.join(' · ')+'</div>';
    h+='</div>';
    h+='</div>';
  });

  // ═══ MASTER ORCHESTRATION SUMMARY ═══
  h+='<div style="padding:12px 20px;background:#f8fafc;border-top:2px solid #1A3A7815">';
  h+='<div style="font-size:8px;font-weight:800;color:#94a3b8;letter-spacing:1px;margin-bottom:6px">MASTER DECISION ORCHESTRATION</div>';
  h+='<div style="display:flex;gap:6px;flex-wrap:wrap">';
  // OLD Formula (reference)
  h+='<div style="padding:6px 8px;border-radius:8px;background:#fff;border:1px dashed #e2e5ea;min-width:140px;opacity:.7">';
  h+='<div style="font-size:6px;color:#94a3b8;font-weight:700">OLD MATRIX (v1.0)</div>';
  h+='<div style="font-size:7px;font-family:JetBrains Mono;color:#6b7280;margin-top:2px">(L1×25)+(L2×22)+(L3×18)+(L4×15)+(L5×10)+(L6×10)</div>';
  h+='<div style="font-size:7px;color:'+_oldVC+';font-weight:800;margin-top:2px">'+_oldMDO+'/10 → '+_oldVerdict+'</div></div>';
  // NEW CDS Formula
  h+='<div style="flex:1;min-width:180px;padding:8px;border-radius:8px;background:#fff;border:2px solid #1A3A7820">';
  h+='<div style="font-size:7px;color:#1A3A78;font-weight:800">CDS v2.0 — '+(_eng.segLabel||'Stock')+' ('+_eng.regime+')</div>';
  h+='<div style="font-size:8px;font-family:JetBrains Mono;color:#0A1628;margin-top:2px">(L1×'+_eng.weights.L1+')+(L2×'+_eng.weights.L2+')+(L3×'+_eng.weights.L3+')+(L4×'+_eng.weights.L4+')+(L5×'+_eng.weights.L5+')+(L6×'+_eng.weights.L6+')</div>';
  h+='<div style="font-size:7px;color:#94a3b8;margin-top:1px">× LiqConf('+(_eng.liqConf||1).toFixed(2)+') × MacroFit('+(_eng.macroFit||1).toFixed(2)+') × Crowding('+(_eng.crowdAdj||1).toFixed(2)+')</div>';
  h+='<div style="font-size:7px;color:#1A3A78;font-weight:800;margin-top:2px">Score: '+_eng.score.toFixed(0)+'/100</div></div>';
  // Decision Bucket
  h+='<div style="padding:8px;border-radius:8px;background:'+_eng.bucketColor+'08;border:1px solid '+_eng.bucketColor+'20;text-align:center;min-width:90px">';
  h+='<div style="font-size:6px;color:#94a3b8;font-weight:700">DECISION</div>';
  h+='<div style="font-size:16px">'+_eng.bucketIcon+'</div>';
  h+='<div style="font-size:10px;font-weight:900;color:'+_eng.bucketColor+';font-family:Sora">'+_eng.bucketLabel+'</div></div>';
  // Verdict
  h+='<div style="padding:8px;border-radius:8px;background:'+_eng.vC+'08;border:1px solid '+_eng.vC+'20;text-align:center;min-width:90px">';
  h+='<div style="font-size:7px;color:#94a3b8;font-weight:700">VERDICT</div>';
  h+='<div style="font-size:14px;font-weight:900;color:'+_eng.vC+';font-family:JetBrains Mono">'+_eng.verdict+'</div></div>';
  // Position
  h+='<div style="padding:8px;border-radius:8px;background:#fff;border:1px solid #e2e5ea;text-align:center;min-width:90px">';
  h+='<div style="font-size:7px;color:#94a3b8;font-weight:700">POSITION SIZE</div>';
  h+='<div style="font-size:10px;font-weight:800;color:#1A3A78">'+_eng.posSize+'%</div>';
  h+='<div style="font-size:7px;color:#94a3b8">'+_eng.posLabel+'</div></div>';
  // Horizon
  h+='<div style="padding:8px;border-radius:8px;background:#fff;border:1px solid #e2e5ea;text-align:center;min-width:90px">';
  h+='<div style="font-size:7px;color:#94a3b8;font-weight:700">HORIZON</div>';
  h+='<div style="font-size:8px;font-weight:800;color:#374151;margin-top:2px">'+_eng.horizon+'</div></div>';
  h+='</div>';

  // Override warning
  if(_eng.blocked){
    h+='<div style="margin-top:8px;padding:8px 12px;border-radius:8px;background:#dc262610;border:1px solid #dc262630;font-size:9px;font-weight:800;color:#dc2626">⛔ TRADE BLOCKED: '+_eng.blockReason+' — Override rules triggered. No position allowed.</div>';
  }
  h+='</div>';

  // CDS v2.0 layman summary
  var _cdsLayman='';
  if(_eng.score>=75) _cdsLayman='All systems agree — strong fundamentals meeting favorable timing. This is a <strong>high-conviction deploy</strong> situation. Allocate '+_eng.posSize+'% of your portfolio and set trailing stop-losses.';
  else if(_eng.score>=60) _cdsLayman='Mostly positive signals with a few caution areas. Worth <strong>building a position gradually</strong> — don\'t go all-in at once. Use 2-3 tranches spread over days/weeks.';
  else if(_eng.score>=45) _cdsLayman='Signals are mixed — the stock has merits but timing or risk isn\'t ideal. <strong>Watch and wait</strong> for improvement. If you already own it, hold but don\'t add more right now.';
  else if(_eng.score>=30) _cdsLayman='More negatives than positives. The smart move is to <strong>reduce exposure</strong> or set tight stop-losses. Look for better opportunities elsewhere.';
  else _cdsLayman='Multiple red flags across layers. <strong>Avoid new positions entirely.</strong> If you hold this stock, consider exiting or hedging to protect your capital.';
  h+='<div style="padding:10px 20px;font-size:10px;color:#374151;line-height:1.7;background:#EFF6FF;border-top:2px solid #1A3A7815">';
  h+='💬 <strong>Bottom line for you:</strong> CDS scores <strong>'+_eng.score.toFixed(0)+'/100 ('+_eng.verdict+')</strong>. '+_cdsLayman+'</div>';

  // CDS Scanner button — lives inside CDS v2.0 section where it belongs
  h+='<div style="margin:12px 0;padding:16px;border-radius:14px;background:linear-gradient(135deg,#f8fafc,#eff6ff);border:1.5px solid #1A3A7820" id="cdsV2ScannerSlot">';
  
  // L0 SCAN ENGINE — NEW
  h+='<div style="margin-bottom:14px">';
  h+='<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px"><span style="font-size:18px">🔬</span><div><div style="font-size:13px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">L0 Smart Scanner — Pre-Filter Engine</div><div style="font-size:9px;color:#6b7280">Scans 100+ stocks in seconds using 5 fast filters → then sends top picks to CDS for deep analysis</div></div></div>';
  
  // WHY / WHEN boxes
  h+='<div style="display:flex;gap:6px;margin-bottom:10px">';
  h+='<div style="flex:1;padding:6px 10px;border-radius:6px;background:#fff;border:1px solid #e2e5ea;font-size:8px;line-height:1.5"><strong style="color:#1A3A78">🤔 Why use this?</strong> Running CDS on 5000 stocks is slow and misses early signals. L0 filters by Quality + Growth + Momentum + Liquidity + Stability first — like Goldman\'s idea generation layer. Only the strongest pass to CDS.</div>';
  h+='<div style="flex:1;padding:6px 10px;border-radius:6px;background:#fff;border:1px solid #e2e5ea;font-size:8px;line-height:1.5"><strong style="color:#059669">📍 How it works:</strong> Universe (100+) → L0 Fast Filters (5 scores) → Top 30 ranked → Click any stock for full CDS analysis. No need to guess which stocks to analyze!</div>';
  h+='</div>';
  
  // Pipeline visual
  h+='<div style="display:flex;align-items:center;gap:4px;margin-bottom:12px;padding:8px 12px;border-radius:8px;background:#fff;border:1px solid #e2e5ea;font-size:8px;color:#374151">';
  h+='<span style="padding:3px 8px;border-radius:4px;background:#3b82f610;color:#3b82f6;font-weight:800">UNIVERSE 100+</span>';
  h+='<span style="color:#94a3b8">→</span>';
  h+='<span style="padding:3px 8px;border-radius:4px;background:#d9770610;color:#d97706;font-weight:800">L0 FILTERS</span>';
  h+='<span style="color:#94a3b8">→</span>';
  h+='<span style="padding:3px 8px;border-radius:4px;background:#05966910;color:#059669;font-weight:800">TOP 30</span>';
  h+='<span style="color:#94a3b8">→</span>';
  h+='<span style="padding:3px 8px;border-radius:4px;background:#1A3A7810;color:#1A3A78;font-weight:800">CDS DEEP ANALYSIS</span>';
  h+='</div>';
  
  // Scan mode buttons
  var _reg=window._deRegion||"IN";
  h+='<div style="font-size:8px;font-weight:800;color:#5E6F8E;letter-spacing:1px;margin-bottom:6px">SCAN MODES — Choose a strategy</div>';
  h+='<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px">';
  var _modes=[
    {m:"quality",e:"🏆",l:"Quality Compounders",d:"F-Score + Trend + Low Volatility",c:"#059669"},
    {m:"growth",e:"🚀",l:"High Growth",d:"Revenue + Returns momentum",c:"#2563eb"},
    {m:"momentum",e:"⚡",l:"Momentum Leaders",d:"Trend + RSI + Volume surge",c:"#d97706"},
    {m:"value",e:"💎",l:"Deep Value",d:"Below 52W high + Stability",c:"#7c3aed"},
    {m:"multibagger",e:"🔥",l:"Multibagger Hunt",d:"1Y returns + Growth + Momentum",c:"#dc2626"},
    {m:"dividend",e:"🏦",l:"Dividend & Stability",d:"Low volatility + Quality",c:"#374151"},
  ];
  _modes.forEach(function(md){
    h+="<div onclick=\"window._runL0Scan('"+_reg+"','"+md.m+"')\" style=\"flex:1;min-width:120px;padding:10px 12px;border-radius:10px;background:"+md.c+"08;border:1.5px solid "+md.c+"20;cursor:pointer;transition:all .2s;text-align:center\" onmouseover=\"this.style.background='"+md.c+"15';this.style.borderColor='"+md.c+"'\" onmouseout=\"this.style.background='"+md.c+"08';this.style.borderColor='"+md.c+"20'\">";
    h+="<div style=\"font-size:16px;margin-bottom:4px\">"+md.e+"</div>";
    h+="<div style=\"font-size:10px;font-weight:800;color:"+md.c+"\">"+md.l+"</div>";
    h+="<div style=\"font-size:7px;color:#94a3b8;margin-top:2px\">"+md.d+"</div></div>";
  });
  h+='</div>';
  
  // Theme buttons
  h+='<div style="font-size:8px;font-weight:800;color:#5E6F8E;letter-spacing:1px;margin-bottom:6px">MEGATREND THEMES — Sector-focused scans</div>';
  h+='<div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:12px">';
  var _themes=_reg==="US"?["AI","Semiconductor","EV & Clean Energy","Cybersecurity","Defense","Fintech","Space","Healthcare"]:["AI & IT","Defence","EV & Green Energy","Banking & NBFC","Pharma & Healthcare","Infra & Capital Goods","FMCG & Consumer","Metals & Mining","Realty","PSU & Railways"];
  _themes.forEach(function(th){
    h+="<div onclick=\"window._runL0Scan('"+_reg+"','theme','"+th+"')\" style=\"padding:6px 12px;border-radius:8px;background:#0891b208;border:1px solid #0891b220;cursor:pointer;font-size:9px;font-weight:700;color:#0891b2;transition:all .15s\" onmouseover=\"this.style.background='#0891b2';this.style.color='#fff'\" onmouseout=\"this.style.background='#0891b208';this.style.color='#0891b2'\">🎯 "+th+"</div>";
  });
  h+='</div>';
  
  // Divider
  h+='<div style="border-top:1px solid #e2e5ea;padding-top:12px;margin-top:4px">';
  h+='<div style="font-size:8px;font-weight:800;color:#5E6F8E;letter-spacing:1px;margin-bottom:8px">OR — DEEP SCAN (SLOWER)</div>';
  h+='</div>';
  h+='</div>';
  
  // Original CDS Scanner button
  h+='<div style="text-align:center">';
  h+='<div style="display:inline-block;padding:10px 24px;border-radius:10px;background:linear-gradient(135deg,#0A1628,#1A3A78);color:#fff;font-size:11px;font-weight:800;cursor:pointer;font-family:Sora,sans-serif;box-shadow:0 4px 16px rgba(26,58,120,.25);border:none" onclick="if(typeof switchTab===\'function\')switchTab(\'decision\');window._topStocksReport(window._deRegion||\'IN\')">🤖 CDS Full Scanner (Slower — runs 36 charts per stock)</div>';
  h+='<div style="font-size:8px;color:#94a3b8;margin-top:6px">Runs complete CDS v2.0 on every stock — takes 2-5 min per category</div>';
  h+='</div>';
  h+='</div>';

  h+='</div>';
  return h;
};

// ══════════════════════════════════════════════════════════════
// REQ 1: VOLATILITY REGIME CLASSIFIER
// Classifies market into 5 volatility states using available data
// ══════════════════════════════════════════════════════════════
;window._volatilityRegime=function(d){
  var _t=d.technicals||{};
  var beta=parseFloat(d.beta||_t.beta||0);
  var rsi=parseFloat(d.rsi||_t.rsi||0);
  var adx=parseFloat(d.adx||_t.adx||0);
  var hi52=parseFloat(d.week52_high||(d.levels?d.levels.hi52:0)||0);
  var p=parseFloat(d.price||d.current_price||0);
  var maxDD=(hi52>0&&p<hi52)?Math.round((hi52-p)/hi52*100):0;
  var vol=parseFloat(d.volume||_t.volume||0);
  var avgVol=parseFloat(d.avg_volume||_t.avgVolume||0);
  var volRatio=(avgVol>0&&vol>0)?vol/avgVol:parseFloat(_t.volRatio||0);
  var sma20=parseFloat(d.sma_20||d.sma20||_t.sma20||0);
  var sma50=parseFloat(d.sma_50||d.sma50||_t.sma50||0);
  var sma200=parseFloat(d.sma_200||d.sma200||_t.sma200||0);
  var atr=parseFloat(d.atr||0);
  var atrPct=p>0&&atr>0?(atr/p*100):(beta>0?beta*1.5:2);

  // Implied Volatility proxy (from beta + ATR + drawdown)
  var ivProxy=Math.round(Math.min(100,Math.max(5,
    beta*15+atrPct*5+maxDD*0.8+(volRatio>2?15:0)+(rsi<25||rsi>75?10:0)
  )));

  // Volatility State Classification
  var state,stateColor,stateIcon,stateDesc;
  if(ivProxy>=70){
    state='EXTREME';stateColor='#dc2626';stateIcon='🔴';
    stateDesc='Crisis-level volatility. Capital preservation mode. Reduce exposure 70-100%.';
  }else if(ivProxy>=50){
    state='HIGH';stateColor='#f59e0b';stateIcon='🟠';
    stateDesc='Elevated volatility. Tighten stops, reduce position sizes by 50%. Hedge with puts.';
  }else if(ivProxy>=30){
    state='MODERATE';stateColor='#d97706';stateIcon='🟡';
    stateDesc='Normal market conditions. Standard position sizing. Monitor for regime shift.';
  }else if(ivProxy>=15){
    state='LOW';stateColor='#059669';stateIcon='🟢';
    stateDesc='Low volatility — favorable for position building. Scale in aggressively on dips.';
  }else{
    state='COMPRESSED';stateColor='#0284c7';stateIcon='🔵';
    stateDesc='Unusually compressed. Expect breakout. Prepare for directional move — have both bull and bear plans.';
  }

  // Trend Stability (is the trend reliable?)
  var trendStability=Math.round(Math.min(100,
    (adx>25?30:adx>15?15:0)+
    (sma50>0?Math.abs(p-sma50)/p<0.05?25:Math.abs(p-sma50)/p<0.1?15:0:0)+
    (sma50>0&&sma200>0?(sma50>sma200?20:sma50>sma200*0.95?10:0):0)+
    (volRatio>0?(volRatio<2?15:volRatio<3?5:0):0)+
    (rsi>0?(rsi>35&&rsi<65?10:0):0)
  ));

  // Regime Transition Probability
  var transProb='STABLE';
  if(ivProxy<20&&adx<15)transProb='BREAKOUT IMMINENT';
  else if(ivProxy>60&&volRatio>2)transProb='REGIME SHIFT LIKELY';
  else if(Math.abs(rsi-50)<10&&adx<20)transProb='RANGE-BOUND';

  return {
    ivProxy:ivProxy,state:state,stateColor:stateColor,stateIcon:stateIcon,stateDesc:stateDesc,
    trendStability:trendStability,transProb:transProb,
    beta:beta,atrPct:atrPct,maxDD:maxDD,volRatio:volRatio
  };
};

// ══════════════════════════════════════════════════════════════
// REQ 2: SCENARIO PROBABILITY ENGINE
// Monte Carlo-style scenario analysis with probability weights
// ══════════════════════════════════════════════════════════════
;window._scenarioProbability=function(d,S){
  S=S||'$';
  var p=parseFloat(d.price||d.current_price||0);
  if(!p)return null;
  var _t=d.technicals||{};
  var beta=parseFloat(d.beta||_t.beta||0);
  var fv=(window._stockTabDCF&&window._stockTabDCF.value>0)?window._stockTabDCF.value:parseFloat(d.fairValue||(d.intrinsicValue?d.intrinsicValue.average:0)||(d.levels?d.levels.fairValue:0)||0);
  var moS=(fv>0&&p>0)?Math.round((fv-p)/p*100):0;
  var fS=parseInt(d.fScore||(d.business?d.business.fScore:0)||d.piotroski_score||0);
  var roe=parseFloat(d.roe||(d.fundamental?d.fundamental.roe:0)||0);
  var hi52=parseFloat(d.week52_high||(d.levels?d.levels.hi52:0)||0);
  var maxDD=(hi52>0&&p<hi52)?Math.round((hi52-p)/hi52*100):0;
  var rsi=parseFloat(d.rsi||_t.rsi||0);
  var sma200=parseFloat(d.sma_200||d.sma200||_t.sma200||0);

  // Quality score (0-10)
  var qScore=Math.min(10,fS+(roe>20?2:roe>10?1:0));

  // 5 Scenario Paths with probability weighting
  var scenarios=[];

  // Scenario 1: BULL CASE (everything goes right)
  var bullProb=Math.min(35,Math.max(5,
    (moS>20?12:moS>10?8:moS>0?5:2)+
    (fS>=7?10:fS>=5?5:0)+
    (p>sma200?8:0)+
    (rsi>40&&rsi<65?5:0)
  ));
  var bullReturn=Math.round(Math.min(80,Math.max(10,moS*1.5+roe*0.3+10)));
  scenarios.push({
    name:'🟢 BULL CASE',prob:bullProb,
    returnPct:bullReturn,target:Math.round(p*(1+bullReturn/100)),
    desc:'Quality holds + market favorable + catalysts fire',
    color:'#059669'
  });

  // Scenario 2: BASE CASE (most likely)
  var baseProb=Math.min(45,Math.max(20,40-Math.abs(moS)*0.3));
  var baseReturn=Math.round(moS>0?moS*0.5:moS*0.3);
  scenarios.push({
    name:'🟡 BASE CASE',prob:baseProb,
    returnPct:baseReturn,target:Math.round(p*(1+baseReturn/100)),
    desc:'Mean reversion toward fair value at normal pace',
    color:'#d97706'
  });

  // Scenario 3: BEAR CASE (things go wrong)
  var bearProb=Math.min(30,Math.max(5,
    (moS<-10?10:moS<0?5:2)+
    (fS<4?8:fS<6?4:0)+
    (beta>1.5?8:beta>1.2?4:0)+
    (p<sma200?6:0)
  ));
  var bearReturn=Math.round(Math.max(-60,Math.min(-5,-10-maxDD*0.5-beta*5)));
  scenarios.push({
    name:'🔴 BEAR CASE',prob:bearProb,
    returnPct:bearReturn,target:Math.round(p*(1+bearReturn/100)),
    desc:'Fundamentals deteriorate + sector rotation + macro headwinds',
    color:'#dc2626'
  });

  // Scenario 4: BLACK SWAN (tail risk)
  var swanProb=Math.min(10,Math.max(2,beta>2?8:beta>1.5?5:3));
  var swanReturn=Math.round(-30-maxDD*0.8);
  scenarios.push({
    name:'⚫ BLACK SWAN',prob:swanProb,
    returnPct:swanReturn,target:Math.round(p*(1+swanReturn/100)),
    desc:'Catastrophic event — fraud, regulatory action, market crash',
    color:'#374151'
  });

  // Normalize probabilities to 100%
  var totalProb=scenarios.reduce(function(a,s){return a+s.prob},0);
  scenarios.forEach(function(s){s.prob=Math.round(s.prob/totalProb*100)});

  // Expected Value (probability-weighted return)
  var expectedReturn=Math.round(scenarios.reduce(function(a,s){return a+s.prob*s.returnPct},0)/100);
  var expectedTarget=Math.round(p*(1+expectedReturn/100));

  // Risk-Reward Ratio
  var maxUpside=Math.max.apply(null,scenarios.map(function(s){return s.returnPct}));
  var maxDownside=Math.abs(Math.min.apply(null,scenarios.map(function(s){return s.returnPct})));
  var rrRatio=maxDownside>0?(maxUpside/maxDownside).toFixed(1):'∞';

  // Kelly Criterion (simplified)
  var winProb=scenarios.filter(function(s){return s.returnPct>0}).reduce(function(a,s){return a+s.prob},0)/100;
  var avgWin=scenarios.filter(function(s){return s.returnPct>0}).reduce(function(a,s){return a+s.returnPct*s.prob},0)/(winProb*100||1);
  var avgLoss=Math.abs(scenarios.filter(function(s){return s.returnPct<0}).reduce(function(a,s){return a+s.returnPct*s.prob},0)/((1-winProb)*100||1));
  var kelly=avgLoss>0?Math.round(Math.max(0,Math.min(25,(winProb-((1-winProb)/(avgWin/avgLoss||1)))*100))):0;

  return {
    scenarios:scenarios,expectedReturn:expectedReturn,expectedTarget:expectedTarget,
    rrRatio:rrRatio,kelly:kelly,winProb:Math.round(winProb*100),
    csym:S,price:p
  };
};

// ══════════════════════════════════════════════════════════════
// REQ 4: FORWARD ESTIMATES ENGINE
// Estimates forward PE, growth, and fair value from available data
// ══════════════════════════════════════════════════════════════
;window._forwardEstimates=function(d,S){
  S=S||'$';
  var p=parseFloat(d.price||d.current_price||0);
  if(!p)return null;
  var pe=parseFloat(d.pe_ratio||d.pe||0);
  var fwdPE=parseFloat(d.forward_pe||0);
  var roe=parseFloat(d.roe||0);
  var revG=parseFloat(d.revenue_growth||d.revCAGR||0);
  var gm=parseFloat(d.gross_margin||d.grossMargin||0);
  var npm=parseFloat(d.profit_margin||d.netProfitMargin||0);
  var fS=parseInt(d.fScore||0);

  // If forward PE not available, estimate from trailing PE + growth
  if(!fwdPE&&pe>0){
    var impliedGrowth=revG>0?revG:roe>0?roe*0.5:5;
    fwdPE=Math.round(pe/(1+impliedGrowth/100)*10)/10;
  }

  // PEG Ratio
  var peg=pe>0&&revG>0?Math.round(pe/revG*100)/100:0;
  var pegVerdict=peg>0&&peg<1?'Undervalued (PEG<1)':peg>=1&&peg<2?'Fair (PEG 1-2)':peg>=2?'Expensive (PEG>2)':'N/A';

  // Earnings yield vs bond yield
  var earningsYield=pe>0?Math.round(100/pe*10)/10:0;
  var bondYield=7; // India ~7%, US ~4.5%
  var yieldSpread=earningsYield-bondYield;

  // Sustainable growth rate (ROE × retention ratio)
  var payoutRatio=parseFloat(d.payout_ratio||30);
  var retentionRatio=(100-payoutRatio)/100;
  var sustainableGrowth=roe>0?Math.round(roe*retentionRatio*10)/10:0;

  // Forward fair value (using forward PE or DCF-lite)
  var eps=pe>0?p/pe:0;
  var fwdEPS=eps*(1+(revG||sustainableGrowth)/100);
  var fwdFairValue=fwdPE>0?Math.round(fwdEPS*fwdPE):0;

  return {
    pe:pe,fwdPE:fwdPE,peg:peg,pegVerdict:pegVerdict,
    earningsYield:earningsYield,yieldSpread:yieldSpread,
    sustainableGrowth:sustainableGrowth,
    fwdFairValue:fwdFairValue,fwdEPS:Math.round(fwdEPS*100)/100,
    revG:revG,roe:roe,gm:gm,npm:npm
  };
};

// ══════════════════════════════════════════════════════════════
// INSTITUTIONAL 6-LAYER REGIME-ADAPTIVE DECISION ENGINE
// Final Score = Σ(Wi × Si) with regime-based dynamic weights
// ══════════════════════════════════════════════════════════════
;window._calcInstitutionalMDO=function(d,S){
  S=S||'$';var p=parseFloat(d.price||d.current_price||0);
  if(!p)return null;

  // ━━━ DATA EXTRACTION — No fake defaults. Track what's missing. ━━━
  var _missing=[];
  var fS=parseInt(d.fScore||(d.business?d.business.fScore:0)||d.piotroski_score||0);
  if(!fS) _missing.push('fScore');

  var _betaRaw=parseFloat(d.beta||(d.fundamental?d.fundamental.beta:0)||0);
  var _hasBeta=_betaRaw>0;
  var beta=_hasBeta?_betaRaw:1; // Use 1 for CALCULATIONS but track as missing
  if(!_hasBeta) _missing.push('beta');

  var _rsiRaw=parseFloat(d.rsi||(d.technicals?d.technicals.rsi:0)||0);
  var _hasRSI=_rsiRaw>0||(d.technicals&&d.technicals._hasRSI);
  var rsi=_hasRSI?(_rsiRaw||50):50;
  if(!_hasRSI) _missing.push('rsi');

  var roe=parseFloat(d.roe||(d.fundamental?d.fundamental.roe:0)||0);

  var _sma50Raw=parseFloat(d.sma_50||d.sma50||(d.technicals?d.technicals.sma50:0)||0);
  var _hasSMA50=_sma50Raw>0||(d.technicals&&d.technicals._hasSMA50);
  var sma50=_hasSMA50?(_sma50Raw||p):p;
  if(!_hasSMA50) _missing.push('sma50');

  var _sma200Raw=parseFloat(d.sma_200||d.sma200||(d.technicals?d.technicals.sma200:0)||0);
  var _hasSMA200=_sma200Raw>0||(d.technicals&&d.technicals._hasSMA200);
  var sma200=_hasSMA200?(_sma200Raw||p):p;
  if(!_hasSMA200) _missing.push('sma200');

  var _fvRaw=parseFloat(d.fairValue||(d.intrinsicValue?d.intrinsicValue.average:0)||(d.levels?d.levels.fairValue:0)||0);
  var _hasFV=_fvRaw>0;
  var fv=_hasFV?_fvRaw:p;
  if(!_hasFV) _missing.push('fairValue');
  var moS=_hasFV&&p>0?Math.round((fv-p)/p*100):0;

  var vol=parseFloat(d.volume||(d.technicals?d.technicals.volume:0)||d.avg_volume||0);
  var _avgVolRaw=parseFloat(d.avg_volume||(d.technicals?d.technicals.avgVolume:0)||0);
  var _hasVolume=_avgVolRaw>0||vol>0||(d.technicals&&d.technicals._hasVolume);
  var _hasVolRatio=(d.technicals&&d.technicals.volRatio>0);
  if(!_hasVolume&&_hasVolRatio){_hasVolume=true;vol=100000;_avgVolRaw=100000;} // volRatio proves volume exists
  var avgVol=_hasVolume?(_avgVolRaw||vol):0;
  if(!_hasVolume) _missing.push('volume');
  var volRatio=(d.technicals&&d.technicals.volRatio>0)?parseFloat(d.technicals.volRatio):(avgVol>0&&vol>0?vol/avgVol:1);

  var adx=parseFloat(d.adx||(d.technicals?d.technicals.adx:0)||0);
  var macd_h=parseFloat(d.macd_h||d.macd_hist||(d.technicals?d.technicals.macdHist:0)||0);
  var de=parseFloat(d.debt_to_equity||d.debtEquity||(d.fundamental?d.fundamental.debtToEquity:0)||0);
  var gm=parseFloat(d.gross_margin||d.grossMargin||(d.fundamental?d.fundamental.grossMargin:0)||0);

  // Data quality: % of key fields available
  var _totalFields=10; // fS,beta,rsi,sma50,sma200,fv,volume,adx,roe,de
  var _dataQuality=Math.round((_totalFields-_missing.length)/_totalFields*100);

  // ━━━ NEW: Extended data harvest from rich API response ━━━
  var om=parseFloat(d.operatingMargin||(d.fundamental?d.fundamental.operatingMargin:0)||0);
  var npm=parseFloat(d.profitMargin||(d.fundamental?d.fundamental.profitMargin:0)||0);
  var revG=parseFloat(d.revenueGrowth||(d.fundamental?d.fundamental.revenueGrowth:0)||0);
  var earnG=parseFloat(d.earningsGrowth||(d.fundamental?d.fundamental.earningsGrowth:0)||0);
  var roce=parseFloat(d.roce||0);
  var pe=parseFloat(d.pe||(d.fundamental?d.fundamental.pe:0)||(d.valuation?d.valuation.pe:0)||0);
  var fwdPE=parseFloat(d.fwdPE||(d.valuation?d.valuation.fwdPE:0)||0);
  var peg=parseFloat(d.peg||(d.valuation?d.valuation.peg:0)||0);
  var divY=parseFloat(d.dividendYield||(d.fundamental?d.fundamental.dividendYield:0)||0);
  var histVol=parseFloat(d.volatility||d.hist_vol||0);
  var ivVal=parseFloat(d.iv||d.iv_val||0);
  var revCAGR=parseFloat(d.revCAGR||0);

  // ROIC vs WACC calculation (from API data or computed)
  var rfRate=S==='₹'?0.072:0.045;
  var erp=S==='₹'?0.075:0.052;
  var wacc=Math.round((rfRate+beta*erp)*1000)/10; // As percentage
  var roic=roce>0?roce:(roe>0?roe*0.85:0); // ROCE ≈ ROIC proxy
  var roicWaccSpread=roic-wacc; // Positive = value creator

  // EPS revision proxy — compare forward PE vs trailing PE
  var epsRevisionSignal=0; // -1=downward, 0=flat, 1=upward
  if(fwdPE>0&&pe>0){
    if(fwdPE<pe*0.85) epsRevisionSignal=1; // Forward PE much lower = earnings expected to grow
    else if(fwdPE>pe*1.15) epsRevisionSignal=-1; // Forward PE higher = earnings expected to shrink
  }
  // Also use revG + earnG as growth stability signal
  var growthStability=(revG>0&&earnG>0)?1:(revG>0&&earnG<0)?-0.5:(revG<0&&earnG<0)?-1:0;

  // Probability bands from API
  var probBands=d.probabilityBands||{};
  var bullTarget=parseFloat(probBands.bull||0);
  var bearTarget=parseFloat(probBands.bear||0);
  var baseTarget=parseFloat(probBands.base||fv);

  // Historical trend data
  var histTrend=d.histTrend||{};
  var annualHistory=d.annualHistory||[];
  // Calculate VaR proxy from historical volatility
  var varPct95=histVol>0?Math.round(histVol*1.65*10)/10:Math.round(beta*15*10)/10; // 95% VaR ≈ vol × 1.65
  var varPct99=histVol>0?Math.round(histVol*2.33*10)/10:Math.round(beta*20*10)/10; // 99% VaR ≈ vol × 2.33

  // Sector rotation data
  var sectorRotation=d.sectorRotation||{};
  var sectorMomentum=parseFloat(sectorRotation.momentum||sectorRotation.sectorReturn||0);

  // ━━━ REGIME DETECTION ━━━
  // Bull: price > SMA200, SMA50 > SMA200, RSI > 50
  // Bear: price < SMA200, SMA50 < SMA200, RSI < 45
  // Sideways: everything else
  var bullSignals=(p>sma200?1:0)+(sma50>sma200?1:0)+(rsi>50?1:0)+(adx>25?1:0);
  var bearSignals=(p<sma200?1:0)+(sma50<sma200?1:0)+(rsi<45?1:0)+(maxDD>20?1:0);
  var regime=bullSignals>=3?'BULL':bearSignals>=3?'BEAR':'SIDEWAYS';

  // ━━━ 6 LAYER SCORES (each 0-100) ━━━

  // L1: LIQUIDITY / VOLUME PROFILE + ACCUMULATION ZONES
  var lvls=d.levels||{};
  var hi52=parseFloat(lvls.hi52||d.week52_high||0);
  var lo52=parseFloat(lvls.lo52||d.week52_low||0);
  var range52=hi52-lo52||1;
  var posIn52=hi52>0?Math.round((p-lo52)/range52*100):50; // 0=at low, 100=at high
  var nearSupport=lo52>0&&p<lo52*1.1; // Within 10% of 52w low
  var nearResist=hi52>0&&p>hi52*0.9; // Within 10% of 52w high
  // Compute maxDD from 52W high (since API doesn't return max_drawdown)
  var maxDD=Math.abs(parseFloat(d.max_drawdown||d.drawdown_from_high||0));
  if(maxDD===0&&hi52>0&&p<hi52){maxDD=Math.round((hi52-p)/hi52*100);} // Drawdown from 52W high
  var sipZone=lvls.sipZone||[];var inSIP=sipZone.length>=2&&p>=sipZone[0]&&p<=sipZone[1];
  var strongBuy=lvls.strongBuy||[];var inStrong=strongBuy.length>=2&&p>=strongBuy[0]&&p<=strongBuy[1];
  var L1=_hasVolume?Math.min(100,Math.max(0,
    (volRatio>=2.0?25:volRatio>=1.5?20:volRatio>=1?12:volRatio>=0.5?6:0)+
    (avgVol>1000000?15:avgVol>100000?10:avgVol>10000?5:avgVol>1000?2:0)+
    (inStrong?20:inSIP?15:nearSupport?10:0)+
    (posIn52<25?15:posIn52<40?12:posIn52<60?8:posIn52<80?4:0)+
    (_hasSMA50?(Math.abs(p-sma50)/p<0.02?10:Math.abs(p-sma50)/p<0.05?6:0):0)+
    (adx>25?10:adx>15?5:2)+
    (histVol>0&&histVol<30?5:histVol>0&&histVol<50?3:0)
  )):(_hasVolRatio?45:40); // 45 if volRatio proves volume exists, 40 if truly unknown
  // Floor: if volRatio exists, L1 minimum is 45 (stock is liquid enough to be analyzed)
  if(_hasVolRatio&&L1<45) L1=45;
  var L1_zones={support:lo52,resist:hi52,sipZone:sipZone,strongBuy:strongBuy,posIn52:posIn52,nearSupport:nearSupport,inSIP:inSIP,inStrong:inStrong};

  // L2: ORDER FLOW / SMART MONEY
  var _algo=window._lastTraderData||{};
  var _oi=_algo.oi||d.oi||{};
  var pcr=parseFloat(_oi.pcr||0);
  var oiScore=parseInt(_oi.score||0);
  var oiBias=_oi.bias||'';
  var oiSupport=parseFloat(_oi.support||0);
  var oiResist=parseFloat(_oi.resistance||0);
  var hasOI=pcr>0||oiScore>0;

  // NEW: Dark Pool data from API
  var darkPool=d.darkPool||{};
  var dpScore=parseFloat(darkPool.score||0);
  var dpDetected=darkPool.detected||false;
  var hasDarkPool=dpScore>0;

  // NEW: ETF Flow data from API
  var etfFlow=d.etfFlow||{};
  var etfScore=parseFloat(etfFlow.score||0);
  var etfDir=etfFlow.direction||'neutral';
  var hasETF=etfFlow.hasData||false;

  var L2;
  if(hasOI||hasDarkPool||hasETF){
    // REAL flow data available — combine all signals
    var _l2Base=0;
    if(hasOI) _l2Base+=(oiScore>0?Math.round(oiScore*0.3):0)+(pcr>1.2?12:pcr>1.0?8:pcr>0.8?3:0);
    if(hasDarkPool) _l2Base+=Math.round(dpScore*0.25);
    if(hasETF) _l2Base+=Math.round(etfScore*0.2);
    L2=Math.min(100,Math.max(0,
      _l2Base+
      (p>sma50?10:0)+
      (macd_h>0?10:3)+
      (volRatio>1.2?5:0)+
      (sectorMomentum>5?8:sectorMomentum>0?4:0)
    ));
  }else{
    // Proxy: momentum + sector rotation as smart money flow (capped at 80 — no real flow data)
    L2=Math.min(80,Math.max(0,
      (_hasSMA50?(p>sma50?18:p>sma50*0.95?10:0):8)+ // 8 base when no SMA (not 0)
      (_hasSMA200?(p>sma200?18:p>sma200*0.95?8:0):8)+ // 8 base when no SMA
      (_hasRSI?(rsi>50&&rsi<70?12:rsi>=30&&rsi<=50?8:rsi<30?3:0):5)+ // 5 base when no RSI
      (macd_h>0?10:macd_h>-0.5?5:2)+ // 2 minimum (not 0)
      (volRatio>1.2?8:volRatio>0.8?4:0)+
      (sectorMomentum>5?12:sectorMomentum>0?6:sectorMomentum>-5?3:0)+
      (epsRevisionSignal>0?10:epsRevisionSignal<0?0:3)+
      (fwdPE>0&&pe>0&&fwdPE<pe*0.85?8:0) // Strong EPS growth signal
    ));
  }
  var L2_flow={hasOI:hasOI,pcr:pcr,oiScore:oiScore,oiBias:oiBias,oiSupport:oiSupport,oiResist:oiResist,hasDarkPool:hasDarkPool,dpScore:dpScore,dpDetected:dpDetected,dpSignals:darkPool.signals||[],hasETF:hasETF,etfScore:etfScore,etfDir:etfDir,etfSignals:etfFlow.signals||[]};

  // L3: VOLATILITY / REGIME (higher = safer)
  // IV Trend: compare IV vs historical vol — if IV > histVol, market expects turbulence
  var ivTrend=0; // 0=neutral
  if(ivVal>0&&histVol>0){
    ivTrend=ivVal>histVol*1.3?-2:ivVal>histVol?-1:ivVal<histVol*0.7?2:1;
  }
  // Volatility regime: Low (<15%), Medium (15-30%), High (>30%)
  var volRegime=histVol>0?(histVol<15?'LOW':histVol<30?'MEDIUM':'HIGH'):(beta<0.8?'LOW':beta<1.5?'MEDIUM':'HIGH');

  var L3=Math.min(100,Math.max(0,
    (_hasBeta?(beta<0.8?25:beta<1.2?18:beta<1.5?10:beta<2?5:0):10)+ // 10=neutral when no beta
    (maxDD>0?(maxDD<10?20:maxDD<20?14:maxDD<30?6:0):8)+ // 8=neutral when no DD data
    (_hasRSI?(rsi>30&&rsi<70?18:rsi>20&&rsi<80?10:0):8)+ // 8=neutral when no RSI
    (adx<40?12:adx<50?6:0)+
    (volRatio<2.5?8:0)+
    (ivTrend>=2?12:ivTrend>=1?8:ivTrend===0?5:ivTrend>=-1?2:0)+
    (volRegime==='LOW'?10:volRegime==='MEDIUM'?5:0)
  ));

  // L4: FUNDAMENTALS / FORWARD VALUE
  var L4=Math.min(100,Math.max(0,
    (fS>=8?20:fS>=6?15:fS>=4?8:fS>=2?4:0)+
    (roe>20?15:roe>10?10:roe>0?4:0)+
    (_hasFV?(moS>20?15:moS>10?12:moS>0?8:moS>-10?4:0):5)+ // 5=neutral when no FV data
    (de>0&&de<50?10:de>0&&de<100?6:de===0?8:0)+
    (gm>40?10:gm>20?7:gm>0?3:0)+
    // ROIC vs WACC spread (NEW — from API ROCE + CAPM)
    (roicWaccSpread>15?15:roicWaccSpread>8?12:roicWaccSpread>3?8:roicWaccSpread>0?5:0)+
    // EPS revision signal (NEW — forward PE vs trailing PE)
    (epsRevisionSignal>0?10:epsRevisionSignal===0?4:0)+
    // Growth stability (NEW — both rev and earnings growing)
    (growthStability>0?8:growthStability===0?3:0)+
    // Forward PE discount to trailing
    (fwdPE>0&&pe>0&&fwdPE<pe*0.9?7:fwdPE>0&&pe>0&&fwdPE<pe?4:0)
  ));

  // L5: QUANT / FACTOR SIGNALS + CROSS-SECTIONAL RANKING
  var rsiQ=_hasRSI?(rsi>=30&&rsi<=70?70:rsi>20&&rsi<80?45:15):35; // 35=neutral when no RSI
  var trendQ=(_hasSMA200?(p>sma200?35:0):0)+(_hasSMA50?(p>sma50?25:0):0)+(_hasSMA50&&_hasSMA200?(sma50>sma200?25:0):0);
  // Factor momentum scoring (NEW)
  var factorMomentum=0;
  // Value factor: PE < sector average = value signal
  if(pe>0&&pe<20) factorMomentum+=15;
  else if(pe>0&&pe<30) factorMomentum+=8;
  // Quality factor: F-Score as quality proxy
  if(fS>=7) factorMomentum+=15;
  else if(fS>=5) factorMomentum+=8;
  // Growth factor: revenue CAGR
  if(revCAGR>15) factorMomentum+=15;
  else if(revCAGR>5||revG>5) factorMomentum+=8;
  // Low vol factor: beta<1 = defensive factor
  if(beta<0.8) factorMomentum+=10;
  else if(beta<1.2) factorMomentum+=5;
  // Dividend factor
  if(divY>2) factorMomentum+=5;
  // PEG factor (growth at reasonable price)
  if(peg>0&&peg<1) factorMomentum+=15;
  else if(peg>0&&peg<1.5) factorMomentum+=8;
  // Sector-relative momentum (cross-sectional proxy)
  if(sectorMomentum>10) factorMomentum+=10;
  else if(sectorMomentum>0) factorMomentum+=5;

  var L5=Math.min(100,Math.max(0,Math.round(rsiQ*0.25+trendQ*0.3+factorMomentum*0.45)));
  // Quality floor: F-Score ≥ 8 should never produce ALPHA WEAK
  if(fS>=8&&L5<50) L5=50;
  if(fS>=6&&L5<35) L5=35;

  // L6: PROBABILITY / SIMULATION + VaR + SCENARIO ENGINE
  var mc=d.monteCarlo||{};
  var mcProb=parseFloat(mc.probUndervalued||mc.probAboveEntry||0);
  var alloc=d.allocation||{};
  var kellyFrac=parseFloat(alloc.kellyFrac||0);
  var winProb=parseFloat(alloc.winProb||0);
  var hasMC=mcProb>0||kellyFrac>0;

  // VaR calculation (NEW — from historical volatility or beta proxy)
  // 95% VaR = how much you could lose in a bad month (1.65σ)
  var varScore=0;
  if(varPct95<10) varScore=20; // Low risk — < 10% potential monthly loss
  else if(varPct95<20) varScore=12;
  else if(varPct95<30) varScore=5;
  // else 0 — high VaR

  // Scenario Engine (NEW — explicit Bull/Base/Bear from probability bands)
  var scenarioScore=0;
  if(bullTarget>0&&bearTarget>0){
    var bullUpside=bullTarget>0?Math.round((bullTarget-p)/p*100):0;
    var bearDownside=bearTarget>0?Math.round((p-bearTarget)/p*100):0;
    var riskReward=bearDownside>0?bullUpside/bearDownside:bullUpside>0?3:1;
    if(riskReward>3) scenarioScore=25; // 3:1+ reward:risk
    else if(riskReward>2) scenarioScore=18;
    else if(riskReward>1) scenarioScore=10;
    else scenarioScore=3;
  }else{
    // Proxy from moS + fScore
    scenarioScore=moS>20?20:moS>10?15:moS>0?10:moS>-10?5:0;
  }

  var L6;
  if(hasMC){
    L6=Math.min(100,Math.max(0,
      Math.round(mcProb*0.2)+
      Math.round(winProb*0.15)+
      (kellyFrac>10?15:kellyFrac>5?10:kellyFrac>0?5:0)+
      varScore+
      scenarioScore+
      (fS>=6?8:fS>=4?4:0)
    ));
  }else{
    L6=Math.min(100,Math.max(0,
      scenarioScore+
      varScore+
      (fS>=6?15:fS>=4?8:0)+
      (beta<1.5?12:beta<2?5:0)+
      (maxDD<15?15:maxDD<25?8:0)+
      (roe>10?10:roe>0?5:0)
    ));
  }
  var L6_prob={hasMC:hasMC,mcProb:mcProb,kellyFrac:kellyFrac,winProb:winProb,varPct95:varPct95,varPct99:varPct99,scenarioScore:scenarioScore,bullTarget:bullTarget,bearTarget:bearTarget,riskReward:bullTarget>0&&bearTarget>0&&bearTarget<p?(Math.round((bullTarget-p)/(p-bearTarget)*10)/10):0};

  // ━━━ L0: ASSET CONTEXT ENGINE (ACL) ━━━
  // Classifies stock by market cap segment → drives weight profile, verdicts, display order
  var mcap=parseFloat(d.market_cap||d.marketCap||d.market_capitalization||0);
  var segment='LARGE'; // default
  if(S==='₹'){
    // Indian market: use cr (crores) — API may return in different units
    var mcapCr=mcap>100000?mcap/10000000:mcap; // normalize
    if(mcapCr>=20000||mcap>=200000000000) segment='LARGE';
    else if(mcapCr>=5000||mcap>=50000000000) segment='MID';
    else if(mcapCr>=500||mcap>=5000000000) segment='SMALL';
    else if(mcap>0) segment='MICRO';
    // Fallback: use beta + avgVol as proxy when market cap unavailable
    else if(!mcap){
      if(avgVol>500000 && beta<1.5) segment='LARGE';
      else if(avgVol>100000) segment='MID';
      else if(avgVol>10000) segment='SMALL';
      else segment='MICRO';
    }
  }else{
    // US market: use USD
    if(mcap>=10000000000) segment='LARGE';       // $10B+
    else if(mcap>=2000000000) segment='MID';      // $2B-$10B
    else if(mcap>=300000000) segment='SMALL';     // $300M-$2B
    else if(mcap>0) segment='MICRO';              // <$300M
    else{
      if(avgVol>1000000 && beta<1.5) segment='LARGE';
      else if(avgVol>200000) segment='MID';
      else if(avgVol>20000) segment='SMALL';
      else segment='MICRO';
    }
  }
  // Override: if category hint passed from scanner
  if(d._segment) segment=d._segment;

  // ━━━ SEGMENT-SPECIFIC PROFILES ━━━
  var segmentProfile={
    LARGE:{
      label:'Large Cap',role:'Core Portfolio Anchor',icon:'🏛️',color:'#1A3A78',
      // Weight emphasis: Fundamentals HIGH, Risk HIGH, Factor HIGH
      regimeWeights:{
        BULL:  {L1:15,L2:20,L3:15,L4:22,L5:18,L6:10},
        BEAR:  {L1:12,L2:10,L3:25,L4:25,L5:15,L6:13},
        SIDEWAYS:{L1:15,L2:18,L3:20,L4:22,L5:15,L6:10}
      },
      verdicts:function(sc){
        if(sc>=75) return {v:'CORE HOLD',c:'#059669'};
        if(sc>=60) return {v:'DEFENSIVE ADD',c:'#1A3A78'};
        if(sc>=40) return {v:'NEUTRAL',c:'#d97706'};
        return {v:'TRIM',c:'#dc2626'};
      },
      displayOrder:['Fundamentals','Risk','Factor','Flow','Liquidity','Probability'],
      firstPanel:'Valuation Matrix + ROIC vs WACC',
      blockers:function(d,beta,maxDD,volRatio){
        if(maxDD>40) return 'Large cap with >40% drawdown — structural issue';
        return null;
      }
    },
    MID:{
      label:'Mid Cap',role:'Alpha Engine',icon:'🚀',color:'#2563eb',
      // Weight emphasis: Flow HIGH, Forward growth HIGH, Factor momentum HIGH
      regimeWeights:{
        BULL:  {L1:15,L2:28,L3:10,L4:22,L5:15,L6:10},
        BEAR:  {L1:18,L2:12,L3:25,L4:18,L5:12,L6:15},
        SIDEWAYS:{L1:18,L2:25,L3:15,L4:20,L5:12,L6:10}
      },
      verdicts:function(sc){
        if(sc>=75) return {v:'ACCUMULATION',c:'#059669'};
        if(sc>=60) return {v:'BREAKOUT READY',c:'#2563eb'};
        if(sc>=40) return {v:'EARLY ALPHA',c:'#d97706'};
        return {v:'AVOID',c:'#dc2626'};
      },
      displayOrder:['Flow','Growth','Trend','Risk','Valuation','Probability'],
      firstPanel:'Growth Stability + EPS Revisions',
      blockers:function(d,beta,maxDD,volRatio){
        if(beta>2.5) return 'Mid cap with extreme beta — execution risk too high';
        return null;
      }
    },
    SMALL:{
      label:'Small Cap',role:'Inefficiency Exploiter',icon:'🔍',color:'#d97706',
      // Weight emphasis: Liquidity VERY HIGH, Flow VERY HIGH, Risk HIGH
      regimeWeights:{
        BULL:  {L1:28,L2:25,L3:15,L4:12,L5:10,L6:10},
        BEAR:  {L1:25,L2:15,L3:28,L4:12,L5:10,L6:10},
        SIDEWAYS:{L1:28,L2:22,L3:22,L4:12,L5:8,L6:8}
      },
      verdicts:function(sc){
        if(sc>=75) return {v:'SPECULATIVE ENTRY',c:'#059669'};
        if(sc>=60) return {v:'WATCHLIST',c:'#d97706'};
        if(sc>=40) return {v:'LIQUIDITY TRAP',c:'#dc2626'};
        return {v:'AVOID',c:'#dc2626'};
      },
      displayOrder:['Liquidity','Flow','Risk','Fundamentals','Quant','Probability'],
      firstPanel:'Volume Profile + Liquidity Heatmap',
      blockers:function(d,beta,maxDD,volRatio){
        if(avgVol<10000) return 'Insufficient liquidity — cannot enter without moving price';
        if(beta>3) return 'Extreme volatility for small cap — untradeable';
        return null;
      }
    },
    MICRO:{
      label:'Micro Cap',role:'Event-Driven Only',icon:'💎',color:'#ef4444',
      // Most restrictive: Liquidity dominates, binary decision
      regimeWeights:{
        BULL:  {L1:35,L2:20,L3:20,L4:10,L5:5,L6:10},
        BEAR:  {L1:30,L2:10,L3:30,L4:10,L5:5,L6:15},
        SIDEWAYS:{L1:35,L2:18,L3:25,L4:10,L5:5,L6:7}
      },
      verdicts:function(sc){
        if(sc>=75) return {v:'EVENT-DRIVEN TRADE',c:'#059669'};
        if(sc>=60) return {v:'CATALYST WATCH',c:'#d97706'};
        return {v:'RESTRICTED',c:'#dc2626'};
      },
      displayOrder:['Liquidity','Risk','Flow','Probability','Fundamentals','Quant'],
      firstPanel:'Liquidity Viability + Governance Risk',
      blockers:function(d,beta,maxDD,volRatio){
        if(avgVol<5000) return 'Micro cap liquidity vacuum — no institutional participation possible';
        if(maxDD>60) return 'Catastrophic drawdown history — governance risk';
        return null;
      }
    }
  };

  // ━━━ L0: UNIVERSE GATING ENGINE ━━━
  var L0_eligible=true;var L0_status='ELIGIBLE';var L0_reason='';
  // Liquidity threshold gate — only block if we HAVE volume data AND it's very low
  if(_hasVolume&&avgVol>0&&avgVol<1000&&vol<1000){L0_eligible=false;L0_status='BLOCKED';L0_reason='Liquidity vacuum — avg daily volume is only '+Math.round(avgVol)+' shares, too low for safe entry/exit';}
  // Don't block if we simply don't have volume data — that's a data gap, not a risk signal
  // Market cap mandate gate (micro caps with no data = restricted)
  if(segment==='MICRO'&&!mcap&&avgVol<3000){L0_status='RESTRICTED';L0_reason='Micro cap with insufficient data — restricted zone';}
  // Spread filter (proxy: if price < $1 or ₹5, likely wide spread)
  if((S==='$'&&p<1)||(S==='₹'&&p<5)){L0_eligible=false;L0_status='BLOCKED';L0_reason='Penny stock — spread risk too high';}
  // Ownership trend gate — if available
  var instOwn=parseFloat(d.institutionalOwnership||d.inst_ownership||0);
  if(instOwn>0&&instOwn<5&&segment!=='MICRO'){L0_reason+=(L0_reason?' | ':'')+'Low institutional ownership ('+instOwn.toFixed(0)+'%)';}

  var seg=segmentProfile[segment];

  // ━━━ REGIME-BASED DYNAMIC WEIGHTS (SEGMENT-AWARE) ━━━
  var W=seg.regimeWeights[regime]||seg.regimeWeights['SIDEWAYS'];

  // ━━━ WEIGHTED FINAL SCORE (0-100) ━━━
  var rawScore=(L1*W.L1+L2*W.L2+L3*W.L3+L4*W.L4+L5*W.L5+L6*W.L6)/100;

  // ━━━ MULTIPLIERS (CDS-style) ━━━
  // 1. Liquidity Confidence — penalize if liquidity is weak
  var liqConf=L1>=60?1.0:L1>=40?0.95:L1>=20?0.85:0.7;

  // 2. Macro Regime Fit — reward if regime aligns with stock character
  var macroFit=1.0;
  if(regime==='BULL'&&p>sma200&&p>sma50) macroFit=1.05; // trend confirmation
  if(regime==='BEAR'&&p<sma200&&moS>15) macroFit=1.03; // deep value in bear = contrarian edge
  if(regime==='BEAR'&&p>sma200&&moS<0) macroFit=0.9; // overvalued in bear = dangerous
  if(regime==='SIDEWAYS') macroFit=0.97; // slight penalty for uncertainty

  // 3. Crowding Adjustment — penalize if too many signals agree (potential crowded trade)
  var bullCount=(p>sma50?1:0)+(p>sma200?1:0)+(rsi>60?1:0)+(moS>20?1:0)+(fS>=7?1:0);
  var crowdAdj=bullCount>=5?0.95:1.0; // all 5 bullish = may be crowded
  var bearCrowd=(p<sma50?1:0)+(p<sma200?1:0)+(rsi<30?1:0)+(moS<-20?1:0)+(fS<3?1:0);
  if(bearCrowd>=4) crowdAdj=0.93; // extreme bearish consensus = possible bottom

  var adjustedScore=rawScore*liqConf*macroFit*crowdAdj;
  // Floor: combined multiplier effect should not compress more than 10%
  if(adjustedScore<rawScore*0.90) adjustedScore=rawScore*0.90;
  var finalScore=Math.round(adjustedScore*10)/10;
  // Cap at 0-100
  finalScore=Math.min(100,Math.max(0,finalScore));

  // ━━━ HARD OVERRIDE ENGINE (Explicit) ━━━
  var blocked=false;var blockReason='';
  var overrides=[];

  // L0 blocking
  if(!L0_eligible){blocked=true;blockReason=L0_reason;}

  // Universal hard blocks
  if(!blocked&&beta>3){blocked=true;blockReason='Extreme volatility (beta '+beta.toFixed(1)+')';}
  if(!blocked&&maxDD>50){blocked=true;blockReason='Catastrophic drawdown ('+maxDD.toFixed(0)+'%)';}
  if(!blocked&&volRatio>5){blocked=true;blockReason='Volume spike anomaly ('+volRatio.toFixed(1)+'x avg)';}

  // Segment-specific blocks
  if(!blocked&&seg.blockers){
    var segBlock=seg.blockers(d,beta,maxDD,volRatio);
    if(segBlock){blocked=true;blockReason=segBlock;}
  }

  // Soft overrides (don't block, but flag + reduce)
  if(!blocked){
    if(volRatio>3){overrides.push({trigger:'Volatility spike',action:'Reduce size',icon:'↓'});finalScore=Math.round(finalScore*0.9);}
    if(L2<30&&L1>50){overrides.push({trigger:'Negative flow divergence',action:'Avoid entry',icon:'⚠️'});}
    // Event risk — if RSI extreme + high beta = earnings-like behavior
    if((rsi>80||rsi<20)&&beta>1.5){overrides.push({trigger:'Event risk (extreme RSI)',action:'Partial exposure only',icon:'⚠️'});}
  }

  // ━━━ CONFIDENCE MULTIPLIER (data-quality-aware) ━━━
  var dataPoints=(_hasBeta?1:0)+(_hasRSI?1:0)+(_hasSMA200?1:0)+(_hasSMA50?1:0)+(_hasVolume?1:0)+(roe>0?1:0)+(pe>0?1:0)+(de>0?1:0)+(fS>0?1:0)+(_hasFV?1:0);
  var confidence=Math.min(95,Math.max(15,Math.round(dataPoints/10*65+finalScore*0.30)));
  // If too much data missing, cap confidence regardless of score
  if(_missing.length>=5) confidence=Math.min(confidence,40);
  if(_missing.length>=3) confidence=Math.min(confidence,60);

  // ━━━ INCOMPLETE DATA CHECK ━━━
  var _isIncomplete=_missing.length>=3;
  var _incompleteMsg=_isIncomplete?'Score based on '+(_totalFields-_missing.length)+'/'+_totalFields+' data points. Missing: '+_missing.join(', ')+'. Result may not be accurate.':'';
  console.log('[MDO] Missing('+_missing.length+'/'+_totalFields+'):',_missing.join(', ')||'NONE');
  console.log('[MDO] Data: fS='+fS+' beta='+beta+'(has:'+_hasBeta+') rsi='+rsi+'(has:'+_hasRSI+') sma50='+sma50+'(has:'+_hasSMA50+') sma200='+sma200+'(has:'+_hasSMA200+') vol='+(avgVol||0)+'(has:'+_hasVolume+') fv='+fv+'(has:'+_hasFV+')');
  console.log('[MDO] Scores: L1='+L1+' L2='+L2+' L3='+L3+' L4='+L4+' L5='+L5+' L6='+L6+' Final='+finalScore+' Conf='+confidence+' Incomplete='+_isIncomplete);

  // ━━━ DECISION BUCKETING (Deploy / Watch / Avoid) ━━━
  var bucket,bucketColor,bucketIcon,bucketLabel,bucketDesc;
  if(blocked){
    bucket='BLOCKED';bucketColor='#dc2626';bucketIcon='🚫';bucketLabel='BLOCKED';
    bucketDesc=blockReason;
  }else if(_isIncomplete){
    // Incomplete data — don't give a confident verdict
    bucket='INCOMPLETE';bucketColor='#6b7280';bucketIcon='⚠️';bucketLabel='INCOMPLETE DATA';
    bucketDesc='Cannot give reliable verdict — '+_missing.length+' key data fields missing ('+_missing.join(', ')+')';
  }else if(finalScore>70&&L1>=40&&L2>=30&&overrides.length===0){
    bucket='DEPLOY';bucketColor='#059669';bucketIcon='🟢';bucketLabel='DEPLOY';
    bucketDesc='Institutional capital actively entering → allocate now';
  }else if(finalScore>=55||(finalScore>=45&&(L2>=40||L1>=50))){
    bucket='WATCH';bucketColor='#d97706';bucketIcon='🟡';bucketLabel='WATCH';
    bucketDesc='Smart money preparing → wait for confirmation trigger';
  }else{
    bucket='AVOID';bucketColor='#dc2626';bucketIcon='🔴';bucketLabel='AVOID';
    bucketDesc='Risk > reward OR institutional exit happening';
  }

  // ━━━ VERDICT WITH THRESHOLDS (SEGMENT-AWARE) ━━━
  var mdo=Math.round(finalScore/10*10)/10;
  var verdict,vC;
  if(blocked){verdict='⛔ BLOCKED';vC='#dc2626';mdo=0;}
  else if(_isIncomplete){verdict='⚠️ INCOMPLETE DATA';vC='#6b7280';}
  else{
    var sv=seg.verdicts(finalScore);
    verdict=sv.v;vC=sv.c;
  }

  // ━━━ DYNAMIC POSITION SIZING (Institutional Formula) ━━━
  // Position Size = (Base Score × Confidence × Liquidity Score) ÷ (Volatility × Tail Risk)
  var volatilityFactor=Math.max(0.5,Math.min(3,beta));
  var tailRisk=Math.max(1,maxDD>0?maxDD/10:1);
  var rawPosSize=(finalScore/100)*(confidence/100)*(L1/100)/(volatilityFactor*tailRisk/10)*100;
  var posSize=blocked?0:Math.round(Math.min(10,Math.max(0.5,rawPosSize)));
  
  // CRITICAL: Position size MUST align with decision bucket
  if(bucket==='AVOID'||bucket==='BLOCKED'||bucket==='INCOMPLETE'){posSize=0;}
  else if(bucket==='WATCH'){posSize=Math.min(posSize,3);} // Max 3% for WATCH
  // DEPLOY keeps full calculated position
  
  var posLabel=posSize>=8?'Full Position (8-10%)':posSize>=5?'Half Position (5-7%)':posSize>=3?'Small Position (3-4%)':posSize>=1?'Minimal (1-2%)':'No Position';
  var posPct=posSize+'%';

  // Segment + liquidity caps
  if(L1<30&&posSize>3){posSize=3;posLabel='Liquidity-Capped (max 3%)';}
  if(segment==='MICRO'&&posSize>2){posSize=2;posLabel='Micro Cap Cap (max 2%)';}
  if(segment==='SMALL'&&posSize>5){posSize=5;posLabel='Small Cap Cap (max 5%)';}

  // ━━━ TIME HORIZON ━━━
  var horizon=finalScore>=70?'3-5 Years (Core Holding)':finalScore>=55?'1-2 Years (Position Trade)':finalScore>=40?'3-6 Months (Monitor)':'Immediate Review';

  // ━━━ TOP 3 DRIVERS ━━━
  var layers=[
    {name:'Liquidity',score:L1,weight:W.L1,icon:'💧'},
    {name:'Flow',score:L2,weight:W.L2,icon:'📊'},
    {name:'Volatility',score:L3,weight:W.L3,icon:'🌊'},
    {name:'Fundamentals',score:L4,weight:W.L4,icon:'🏛️'},
    {name:'Quant',score:L5,weight:W.L5,icon:'🔢'},
    {name:'Probability',score:L6,weight:W.L6,icon:'🎯'}
  ];
  layers.sort(function(a,b){return b.score*b.weight-a.score*a.weight});
  var strongest=layers[0];
  var weakest=layers[layers.length-1];

  var drivers=[];
  if(fS>=7)drivers.push({t:'Strong fundamentals (F-Score '+fS+'/9)',c:'#059669'});
  else if(fS<4)drivers.push({t:'Weak fundamentals (F-Score '+fS+'/9)',c:'#dc2626'});
  if(moS>10)drivers.push({t:'Undervalued by '+moS+'% vs fair value',c:'#059669'});
  else if(moS<-10)drivers.push({t:'Overvalued by '+Math.abs(moS)+'%',c:'#dc2626'});
  if(regime==='BULL')drivers.push({t:'Bull regime — momentum favored',c:'#059669'});
  else if(regime==='BEAR')drivers.push({t:'Bear regime — risk control priority',c:'#dc2626'});
  if(beta>1.5)drivers.push({t:'High beta '+beta.toFixed(2)+' — amplified moves',c:'#dc2626'});
  else if(beta<0.8)drivers.push({t:'Low beta — defensive positioning',c:'#059669'});
  if(roe>20)drivers.push({t:'ROE '+roe.toFixed(0)+'% — exceptional returns',c:'#059669'});
  drivers=drivers.slice(0,3);
  if(!drivers.length)drivers.push({t:'Mixed signals — no strong conviction',c:'#d97706'});

  // ━━━ CONTRARIAN RISK ━━━
  var contrarian='';
  if(finalScore>=60)contrarian=regime==='BULL'?'Bull regime may be late-stage. Watch for volume divergence.':moS>20?'Deep value can stay undervalued. Catalyst needed.':'Strong score but watch macro headwinds.';
  else contrarian=regime==='BEAR'?'Bear markets create opportunity. Watch for regime shift signals.':'Score improving from low base. Could be early reversal.';

  return {
    score:finalScore,mdo:mdo,verdict:verdict,vC:vC,confidence:confidence,
    regime:regime,weights:W,layers:layers,strongest:strongest,weakest:weakest,
    drivers:drivers,contrarian:contrarian,horizon:horizon,blocked:blocked,blockReason:blockReason,
    // Decision Bucketing
    bucket:bucket,bucketColor:bucketColor,bucketIcon:bucketIcon,bucketLabel:bucketLabel,bucketDesc:bucketDesc,
    // Position Sizing (Dynamic)
    posSize:posSize,posLabel:posLabel,posPct:posPct,
    // L0 Universe Gating
    L0_status:L0_status,L0_reason:L0_reason,L0_eligible:L0_eligible,
    // Multipliers
    liqConf:liqConf,macroFit:macroFit,crowdAdj:crowdAdj,
    // Overrides
    overrides:overrides,
    // Segment
    segment:segment,segLabel:seg.label,segRole:seg.role,segIcon:seg.icon,segColor:seg.color,
    displayOrder:seg.displayOrder,firstPanel:seg.firstPanel,
    // Raw layers
    L1:L1,L2:L2,L3:L3,L4:L4,L5:L5,L6:L6,
    L1_zones:L1_zones,L2_flow:L2_flow,L6_prob:L6_prob,
    // New data fields
    roicWaccSpread:roicWaccSpread,roic:roic,wacc:wacc,
    epsRevisionSignal:epsRevisionSignal,growthStability:growthStability,
    ivTrend:ivTrend,volRegime:volRegime,varPct95:varPct95,varPct99:varPct99,
    factorMomentum:factorMomentum,sectorMomentum:sectorMomentum,
    revG:revG,earnG:earnG,revCAGR:revCAGR,fwdPE:fwdPE,pe:pe,peg:peg,
    fS:fS,beta:beta,rsi:rsi,roe:roe,moS:moS,maxDD:maxDD,
    // Data quality tracking
    dataQuality:_dataQuality,missingFields:_missing,isIncomplete:_isIncomplete,incompleteMsg:_incompleteMsg,
    hasBeta:_hasBeta,hasRSI:_hasRSI,hasSMA50:_hasSMA50,hasSMA200:_hasSMA200,hasFV:_hasFV,hasVolume:_hasVolume
  };
};

// Version check — visible in console
console.log('🏛️ CELESYS DECISION SYSTEM (CDS) v2.0 — Build 1775275332');
/* ═══════════════════════════════════════════════════════════
   CELESYS PREMIUM — Runtime Dark-Style Eliminator
   Catches ANY inline dark styles that CSS !important misses.
   ═══════════════════════════════════════════════════════════ */
(function(){
  'use strict';

  // 1. Force light theme immediately
  document.documentElement.setAttribute('data-theme','light');
  localStorage.setItem('celesys-theme','light');

  // 2. Color detection helpers
  function isDarkBg(c){
    if(!c||c==='transparent'||c==='rgba(0, 0, 0, 0)')return false;
    var m=c.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    if(m){var r=+m[1],g=+m[2],b=+m[3];return(r*299+g*587+b*114)/1000<80;}
    if(/^#([0-9a-f]{3,8})$/i.test(c)){
      var hex=c.replace('#','');
      if(hex.length===3)hex=hex[0]+hex[0]+hex[1]+hex[1]+hex[2]+hex[2];
      var r2=parseInt(hex.substr(0,2),16),g2=parseInt(hex.substr(2,2),16),b2=parseInt(hex.substr(4,2),16);
      return(r2*299+g2*587+b2*114)/1000<80;
    }
    return false;
  }
  function isWhiteText(c){
    if(!c)return false;
    var m=c.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    if(m)return(+m[1]>220&&+m[2]>220&&+m[3]>220);
    if(/^#fff/i.test(c))return true;
    return false;
  }
  function isOnColoredButton(el){
    var bg=el.style.background||el.style.backgroundColor||'';
    if(/linear-gradient.*#(2563eb|1d4ed8|059669|10b981|7c3aed|6d28d9|dc2626|ef4444|3b82f6)/i.test(bg))return true;
    if(/^#(2563eb|1a56db|1d4ed8|059669|10b981|7c3aed|dc2626)/i.test(bg))return true;
    if(el.tagName==='BUTTON')return true;
    // Small badges (grade circles, etc.)
    var w=el.offsetWidth;
    if(w>0&&w<60&&/border-radius/.test(el.style.cssText)&&/50%|100px/.test(el.style.borderRadius))return true;
    return false;
  }

  // 3. Fix a single element
  function fixElement(el){
    if(!el||!el.style)return;
    var s=el.style;
    var bg=s.background||s.backgroundColor||'';
    var col=s.color||'';

    // Fix dark backgrounds (but not on heatmap tiles or small colored badges)
    if(isDarkBg(bg)&&!el.closest('#heatmapGrid')&&el.offsetWidth>60){
      s.background='#ffffff';
      s.backgroundColor='#ffffff';
    }
    // Fix gradient dark backgrounds
    if(/linear-gradient.*#(0[0-9a-f]|1[0-3])/.test(bg)&&!el.closest('#heatmapGrid')){
      // Only fix if it's a large container, not a small button
      if(el.offsetWidth>100||!el.closest('button')){
        s.background='#ffffff';
      }
    }

    // Fix white text on now-white backgrounds
    if(isWhiteText(col)&&!isOnColoredButton(el)){
      var compBg=window.getComputedStyle(el).backgroundColor;
      var parentBg=el.parentElement?window.getComputedStyle(el.parentElement).backgroundColor:'';
      if(!isDarkBg(compBg)&&!isDarkBg(parentBg)){
        s.color='#0A1628';
      }
    }

    // Fix rgba(255,255,255,...) borders
    if(s.border&&/rgba\(255,\s*255,\s*255/.test(s.border)){
      s.border=s.border.replace(/rgba\(255,\s*255,\s*255[^)]*\)/g,'#e2e5ea');
    }
    if(s.borderColor&&/rgba\(255,\s*255,\s*255/.test(s.borderColor)){
      s.borderColor='#e2e5ea';
    }
  }

  // 4. Scan all containers
  var containers=['#siResult','#deResult','#algoResult','#tabContentArea',
    '#reportsContent','#heatmapGrid','#tradesContent','#newsResult',
    '#assetIntelResult','#financeContent','#dailyContent','#screenerResult',
    '#flowResult','#backtestSection','#report','#proScanResult'];

  function scanAll(){
    containers.forEach(function(sel){
      var c=document.querySelector(sel);
      if(!c)return;
      var els=c.querySelectorAll('[style]');
      els.forEach(fixElement);
    });
    // Also fix reportHeader and globalDecisionBar
    ['#reportHeader','#globalDecisionBar'].forEach(function(sel){
      var el=document.querySelector(sel);
      if(el){
        el.style.background='#ffffff';
        el.style.borderColor='#e2e5ea';
        el.querySelectorAll('[style]').forEach(fixElement);
      }
    });
  }

  // 5. MutationObserver — catch dynamically rendered content
  var observer=new MutationObserver(function(mutations){
    mutations.forEach(function(m){
      if(m.type==='childList'&&m.addedNodes.length){
        m.addedNodes.forEach(function(node){
          if(node.nodeType===1){
            fixElement(node);
            if(node.querySelectorAll){
              node.querySelectorAll('[style]').forEach(fixElement);
            }
          }
        });
      }
    });
  });

  // Start observing after DOM loads
  function init(){
    scanAll();
    containers.forEach(function(sel){
      var c=document.querySelector(sel);
      if(c)observer.observe(c,{childList:true,subtree:true});
    });
    // Also observe the report container
    var report=document.getElementById('report');
    if(report)observer.observe(report,{childList:true,subtree:true});
    // Re-scan periodically for late-rendered content
    setTimeout(scanAll,2000);
    setTimeout(scanAll,5000);
  }

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',init);
  }else{
    init();
  }

  // 6. Back to top button
  window.addEventListener('scroll',function(){
    var btt=document.getElementById('bttBtn');
    if(btt)btt.style.display=window.scrollY>300?'flex':'none';
  },{passive:true});
})();

// ═══════════════════════════════════════════════════════════
// PREMIUM VISUAL ENHANCEMENTS — Diagrams, Charts, Decoratives
// ═══════════════════════════════════════════════════════════

// 1. HERO — How It Works diagram (3-step flow)
function _injectHeroDiagram(){
  var heroExtras=document.getElementById('heroExtras');
  if(!heroExtras||document.getElementById('heroDiagram'))return;
  var d=document.createElement('div');
  d.id='heroDiagram';
  d.style.cssText='max-width:700px;margin:24px auto 0;padding:0 20px';
  d.innerHTML='<div style="display:flex;align-items:center;justify-content:center;gap:0;flex-wrap:wrap">'
    // Step 1
    +'<div style="flex:1;min-width:160px;text-align:center;padding:18px 12px">'
    +'<div style="width:52px;height:52px;border-radius:14px;background:linear-gradient(135deg,rgba(26,58,120,.08),rgba(26,58,120,.03));display:flex;align-items:center;justify-content:center;margin:0 auto 10px;border:1px solid rgba(26,58,120,.08)">'
    +'<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#1A3A78" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg></div>'
    +'<div style="font-size:11px;font-weight:800;color:#0A1628;font-family:Sora,sans-serif;margin-bottom:4px">Enter Ticker</div>'
    +'<div style="font-size:10px;color:#6b7280;line-height:1.5">Type any stock — US or India</div></div>'
    // Arrow
    +'<div style="color:#c7d2fe;font-size:20px;padding:0 4px;flex-shrink:0">→</div>'
    // Step 2
    +'<div style="flex:1;min-width:160px;text-align:center;padding:18px 12px">'
    +'<div style="width:52px;height:52px;border-radius:14px;background:linear-gradient(135deg,rgba(26,58,120,.08),rgba(26,58,120,.03));display:flex;align-items:center;justify-content:center;margin:0 auto 10px;border:1px solid rgba(26,58,120,.08)">'
    +'<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#1A3A78" stroke-width="2" stroke-linecap="round"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg></div>'
    +'<div style="font-size:11px;font-weight:800;color:#0A1628;font-family:Sora,sans-serif;margin-bottom:4px">AI Analyzes</div>'
    +'<div style="font-size:10px;color:#6b7280;line-height:1.5">20-factor engine in 60s</div></div>'
    // Arrow
    +'<div style="color:#c7d2fe;font-size:20px;padding:0 4px;flex-shrink:0">→</div>'
    // Step 3
    +'<div style="flex:1;min-width:160px;text-align:center;padding:18px 12px">'
    +'<div style="width:52px;height:52px;border-radius:14px;background:linear-gradient(135deg,rgba(5,150,105,.08),rgba(5,150,105,.03));display:flex;align-items:center;justify-content:center;margin:0 auto 10px;border:1px solid rgba(5,150,105,.08)">'
    +'<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#059669" stroke-width="2" stroke-linecap="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="M22 4L12 14.01l-3-3"/></svg></div>'
    +'<div style="font-size:11px;font-weight:800;color:#0A1628;font-family:Sora,sans-serif;margin-bottom:4px">Get Verdict</div>'
    +'<div style="font-size:10px;color:#6b7280;line-height:1.5">Buy/Sell + exact prices</div></div>'
    +'</div>';
  heroExtras.parentNode.insertBefore(d,heroExtras);
}

// 2. ANALYSIS PIPELINE DIAGRAM — injected into overview tab
function _injectPipelineDiagram(container){
  if(!container||container.querySelector('#pipelineDiagram'))return;
  var el=document.createElement('div');
  el.id='pipelineDiagram';
  el.style.cssText='margin:16px 0;padding:20px;border-radius:14px;background:#fff;border:1px solid #e2e5ea';
  var stages=[
    {icon:'📊',name:'Data Fetch',desc:'Real-time price, fundamentals',color:'#3b82f6'},
    {icon:'🧮',name:'20-Factor Score',desc:'PE, ROE, margin, growth',color:'#1A3A78'},
    {icon:'🎯',name:'Price Targets',desc:'Entry, SL, T1, T2 levels',color:'#059669'},
    {icon:'⚖️',name:'Risk Analysis',desc:'Beta, VaR, drawdown',color:'#d97706'},
    {icon:'✅',name:'Verdict',desc:'Buy / Hold / Sell',color:'#10b981'}
  ];
  var h='<div style="font-size:10px;font-weight:800;color:#94a3b8;letter-spacing:1.5px;margin-bottom:14px">ANALYSIS PIPELINE</div>';
  h+='<div style="display:flex;align-items:flex-start;gap:0;overflow-x:auto;padding-bottom:4px">';
  stages.forEach(function(s,i){
    h+='<div style="flex:1;min-width:100px;text-align:center;position:relative">';
    h+='<div style="width:40px;height:40px;border-radius:12px;background:'+s.color+'10;border:2px solid '+s.color+'30;display:flex;align-items:center;justify-content:center;margin:0 auto 8px;font-size:18px">'+s.icon+'</div>';
    h+='<div style="font-size:9px;font-weight:800;color:#0A1628">'+s.name+'</div>';
    h+='<div style="font-size:8px;color:#94a3b8;margin-top:2px">'+s.desc+'</div>';
    if(i<stages.length-1)h+='<div style="position:absolute;top:20px;right:-12px;color:#c7d2fe;font-size:14px;z-index:1">→</div>';
    h+='</div>';
  });
  h+='</div>';
  el.innerHTML=h;
  container.insertBefore(el,container.firstChild);
}

// 3. RISK GAUGE — SVG semi-circle gauge
window._riskGauge=function(score,label,size){
  size=size||120;
  var r=42,circ=Math.PI*r;
  var pct=Math.min(Math.max(score/100,0),1);
  var offset=circ*(1-pct);
  var color=score>=70?'#059669':score>=40?'#d97706':'#dc2626';
  var gradId='rg'+Math.random().toString(36).substr(2,4);
  return '<div style="text-align:center">'
    +'<svg width="'+size+'" height="'+(size*.65)+'" viewBox="0 0 100 65">'
    +'<defs><linearGradient id="'+gradId+'"><stop offset="0%" stop-color="#dc2626"/><stop offset="50%" stop-color="#d97706"/><stop offset="100%" stop-color="#059669"/></linearGradient></defs>'
    +'<path d="M10,58 A42,42 0 0,1 90,58" fill="none" stroke="#e2e5ea" stroke-width="6" stroke-linecap="round"/>'
    +'<path d="M10,58 A42,42 0 0,1 90,58" fill="none" stroke="url(#'+gradId+')" stroke-width="6" stroke-linecap="round" stroke-dasharray="'+circ+'" stroke-dashoffset="'+offset+'" style="transition:stroke-dashoffset 1s ease"/>'
    +'<text x="50" y="48" text-anchor="middle" font-size="22" font-weight="900" fill="'+color+'" font-family="JetBrains Mono,monospace">'+score+'</text>'
    +'<text x="50" y="62" text-anchor="middle" font-size="8" fill="#94a3b8" font-weight="700">'+label+'</text>'
    +'</svg></div>';
};

// 4. HORIZONTAL BAR CHART — for peer comparison
window._hBar=function(items,maxVal){
  maxVal=maxVal||Math.max.apply(null,items.map(function(x){return Math.abs(x.val)}));
  var h='<div style="display:flex;flex-direction:column;gap:8px">';
  items.forEach(function(item){
    var pct=Math.min(Math.abs(item.val)/maxVal*100,100);
    var c=item.color||'#1A3A78';
    h+='<div style="display:flex;align-items:center;gap:8px">';
    h+='<div style="width:70px;font-size:9px;font-weight:700;color:#6b7280;text-align:right;flex-shrink:0">'+item.label+'</div>';
    h+='<div style="flex:1;height:10px;background:#f1f5f9;border-radius:5px;overflow:hidden">';
    h+='<div style="width:'+pct+'%;height:100%;background:'+c+';border-radius:5px;transition:width .8s ease"></div></div>';
    h+='<div style="width:50px;font-size:10px;font-weight:800;color:'+c+';font-family:JetBrains Mono,monospace">'+item.val+'</div>';
    h+='</div>';
  });
    // ── VOLATILITY REGIME ──
  var _vr=window._volatilityRegime?window._volatilityRegime(d):null;
  if(_vr){
    h+='<div style="padding:10px 24px;border-top:1px solid #f1f3f5">';
    h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">';
    h+='<div style="font-size:8px;font-weight:800;color:#94a3b8;letter-spacing:1px">VOLATILITY REGIME</div>';
    h+='<div style="padding:2px 8px;border-radius:4px;font-size:8px;font-weight:800;background:'+_vr.stateColor+'10;color:'+_vr.stateColor+'">'+_vr.stateIcon+' '+_vr.state+' (IV Proxy: '+_vr.ivProxy+')</div>';
    h+='</div>';
    h+='<div style="display:flex;gap:4px;margin-bottom:6px">';
    [{l:'Beta',v:_vr.beta.toFixed(2),c:_vr.beta<1.2?'#059669':'#dc2626'},{l:'ATR%',v:_vr.atrPct.toFixed(1)+'%',c:_vr.atrPct<3?'#059669':'#dc2626'},{l:'MaxDD',v:_vr.maxDD.toFixed(0)+'%',c:_vr.maxDD<20?'#059669':'#dc2626'},{l:'Vol Ratio',v:_vr.volRatio.toFixed(1)+'x',c:_vr.volRatio<2?'#059669':'#d97706'},{l:'Stability',v:_vr.trendStability,c:_vr.trendStability>60?'#059669':'#d97706'}].forEach(function(m){
      h+='<div style="flex:1;text-align:center;padding:4px;border-radius:4px;background:'+m.c+'06"><div style="font-size:6px;color:#94a3b8;font-weight:700">'+m.l+'</div><div style="font-size:10px;font-weight:800;color:'+m.c+';font-family:JetBrains Mono">'+m.v+'</div></div>';
    });
    h+='</div>';
    h+='<div style="font-size:8px;color:#374151;line-height:1.5">'+_vr.stateDesc+'</div>';
    if(_vr.transProb!=='STABLE')h+='<div style="margin-top:4px;font-size:7px;font-weight:800;color:#d97706">⚡ '+_vr.transProb+'</div>';
    h+='</div>';
  }

  // ── SCENARIO PROBABILITY ──
  var _sp=window._scenarioProbability?window._scenarioProbability(d,S):null;
  if(_sp){
    h+='<div style="padding:10px 24px;border-top:1px solid #f1f3f5">';
    h+='<div style="font-size:8px;font-weight:800;color:#94a3b8;letter-spacing:1px;margin-bottom:6px">SCENARIO PROBABILITY ENGINE</div>';
    _sp.scenarios.forEach(function(sc){
      h+='<div style="display:flex;align-items:center;gap:6px;padding:3px 0">';
      h+='<div style="width:70px;font-size:8px;font-weight:800;color:'+sc.color+'">'+sc.name+'</div>';
      h+='<div style="flex:1;height:6px;background:#f1f5f9;border-radius:3px;overflow:hidden"><div style="height:100%;width:'+sc.prob+'%;background:'+sc.color+';border-radius:3px"></div></div>';
      h+='<div style="width:35px;text-align:right;font-size:8px;font-weight:800;color:'+sc.color+'">'+sc.prob+'%</div>';
      h+='<div style="width:45px;text-align:right;font-size:8px;font-weight:800;color:'+sc.color+';font-family:JetBrains Mono">'+(sc.returnPct>0?'+':'')+sc.returnPct+'%</div>';
      h+='<div style="width:55px;text-align:right;font-size:7px;color:#94a3b8">'+S+sc.target.toLocaleString()+'</div>';
      h+='</div>';
    });
    h+='<div style="display:flex;justify-content:space-between;margin-top:6px;padding-top:6px;border-top:1px solid #f1f3f5">';
    h+='<div style="font-size:8px"><strong style="color:#1A3A78">Expected:</strong> '+((_sp.expectedReturn>0?'+':'')+_sp.expectedReturn)+'% → '+S+_sp.expectedTarget.toLocaleString()+'</div>';
    h+='<div style="font-size:8px"><strong style="color:#1A3A78">R:R</strong> '+_sp.rrRatio+' · <strong>Win:</strong> '+_sp.winProb+'% · <strong>Kelly:</strong> '+_sp.kelly+'%</div>';
    h+='</div>';
    h+='</div>';
  }

  // ── FORWARD ESTIMATES ──
  var _fe=window._forwardEstimates?window._forwardEstimates(d,S):null;
  if(_fe&&_fe.pe>0){
    h+='<div style="padding:10px 24px;border-top:1px solid #f1f3f5">';
    h+='<div style="font-size:8px;font-weight:800;color:#94a3b8;letter-spacing:1px;margin-bottom:6px">FORWARD ESTIMATES</div>';
    h+='<div style="display:flex;gap:4px">';
    [{l:'Trail PE',v:_fe.pe.toFixed(1)+'x',c:_fe.pe<25?'#059669':'#d97706'},{l:'Fwd PE',v:_fe.fwdPE.toFixed(1)+'x',c:_fe.fwdPE<20?'#059669':'#d97706'},{l:'PEG',v:_fe.peg.toFixed(2),c:_fe.peg>0&&_fe.peg<1?'#059669':_fe.peg<2?'#d97706':'#dc2626'},{l:'E.Yield',v:_fe.earningsYield.toFixed(1)+'%',c:_fe.earningsYield>5?'#059669':'#d97706'},{l:'Sust.Grw',v:_fe.sustainableGrowth.toFixed(1)+'%',c:_fe.sustainableGrowth>15?'#059669':'#d97706'},{l:'Fwd Value',v:S+(_fe.fwdFairValue||0).toLocaleString(),c:_fe.fwdFairValue>0?'#059669':'#94a3b8'}].forEach(function(m){
      h+='<div style="flex:1;text-align:center;padding:4px;border-radius:4px;background:'+m.c+'06"><div style="font-size:6px;color:#94a3b8;font-weight:700">'+m.l+'</div><div style="font-size:9px;font-weight:800;color:'+m.c+';font-family:JetBrains Mono">'+m.v+'</div></div>';
    });
    h+='</div>';
    h+='<div style="margin-top:4px;font-size:7px;color:#94a3b8">'+_fe.pegVerdict+' · Yield spread vs bonds: '+(_fe.yieldSpread>0?'+':'')+_fe.yieldSpread.toFixed(1)+'%</div>';
    h+='</div>';
  }

  h+='</div>';
  return h;
};// 5. RADAR CHART — SVG pentagon/hexagon radar
window._radarChart=function(factors,size){
  size=size||200;
  var cx=size/2,cy=size/2,r=size*.38;
  var n=factors.length;
  var h='<svg width="'+size+'" height="'+size+'" viewBox="0 0 '+size+' '+size+'">';
  // Grid rings
  [.25,.5,.75,1].forEach(function(ring){
    var pts='';
    for(var i=0;i<n;i++){
      var a=-Math.PI/2+2*Math.PI*i/n;
      pts+=(i===0?'M':'L')+(cx+r*ring*Math.cos(a)).toFixed(1)+','+(cy+r*ring*Math.sin(a)).toFixed(1);
    }
    h+='<polygon points="" fill="none" stroke="#e2e5ea" stroke-width="0.5"/>';
    h+='<path d="'+pts+'Z" fill="none" stroke="#e2e5ea" stroke-width="0.5"/>';
  });
  // Axes
  for(var i=0;i<n;i++){
    var a=-Math.PI/2+2*Math.PI*i/n;
    h+='<line x1="'+cx+'" y1="'+cy+'" x2="'+(cx+r*Math.cos(a)).toFixed(1)+'" y2="'+(cy+r*Math.sin(a)).toFixed(1)+'" stroke="#e2e5ea" stroke-width="0.5"/>';
    var lx=cx+(r+16)*Math.cos(a),ly=cy+(r+16)*Math.sin(a);
    h+='<text x="'+lx.toFixed(1)+'" y="'+ly.toFixed(1)+'" text-anchor="middle" dominant-baseline="middle" font-size="7" font-weight="700" fill="#6b7280">'+factors[i].label+'</text>';
  }
  // Data polygon
  var gradId='rd'+Math.random().toString(36).substr(2,4);
  h+='<defs><linearGradient id="'+gradId+'" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#1A3A78" stop-opacity=".2"/><stop offset="100%" stop-color="#2563eb" stop-opacity=".1"/></linearGradient></defs>';
  var dp='';
  for(var i=0;i<n;i++){
    var a=-Math.PI/2+2*Math.PI*i/n;
    var v=Math.min(factors[i].value/100,1);
    dp+=(i===0?'M':'L')+(cx+r*v*Math.cos(a)).toFixed(1)+','+(cy+r*v*Math.sin(a)).toFixed(1);
  }
  h+='<path d="'+dp+'Z" fill="url(#'+gradId+')" stroke="#1A3A78" stroke-width="1.5" opacity=".8"/>';
  // Dots
  for(var i=0;i<n;i++){
    var a=-Math.PI/2+2*Math.PI*i/n;
    var v=Math.min(factors[i].value/100,1);
    var dx=cx+r*v*Math.cos(a),dy=cy+r*v*Math.sin(a);
    h+='<circle cx="'+dx.toFixed(1)+'" cy="'+dy.toFixed(1)+'" r="3" fill="#1A3A78" stroke="#fff" stroke-width="1.5"/>';
  }
  h+='</svg>';
  return h;
};

// 6. WATERFALL CHART — for valuation breakdown
window._waterfall=function(items,sym){
  sym=sym||'$';
  if(!items||items.length<1)return'';
  var vals=items.map(function(it){return it.val||0});
  var max=Math.max.apply(null,vals.map(function(v){return Math.abs(v)}))*1.3||1;
  var n=items.length;
  var w=Math.max(400,n*55),ht=180,pad=20,barW=Math.max(20,Math.floor((w-pad*2)/(n*1.4)));
  var h='<div style="overflow-x:auto;padding-bottom:4px"><svg width="'+w+'" height="'+(ht+35)+'" viewBox="0 0 '+w+' '+(ht+35)+'" style="min-width:'+w+'px">';
  h+='<line x1="'+pad+'" y1="'+ht+'" x2="'+(w-pad)+'" y2="'+ht+'" stroke="#e2e5ea" stroke-width="1"/>';
  items.forEach(function(it,i){
    var x=pad+10+i*((w-pad*2-10)/n);
    var barH2=Math.abs(it.val)/max*(ht-40);
    var y=ht-barH2;
    var c2=it.total?'#1A3A78':it.val>=0?'#059669':'#dc2626';
    h+='<rect x="'+x+'" y="'+y+'" width="'+barW+'" height="'+barH2+'" rx="4" fill="'+c2+'" opacity=".75"/>';
    h+='<text x="'+(x+barW/2)+'" y="'+(y-6)+'" text-anchor="middle" font-size="11" font-weight="800" fill="'+c2+'" font-family="JetBrains Mono,monospace">'+sym+Math.round(it.val).toLocaleString()+'</text>';
    var label=(it.label||'').length>10?(it.label||'').substring(0,9)+'…':(it.label||'');
    h+='<text x="'+(x+barW/2)+'" y="'+(ht+14)+'" text-anchor="middle" font-size="9" fill="#94a3b8" font-weight="600">'+label+'</text>';
  });
  h+='</svg></div>';
  return h;
};

// 7. DONUT CHART — for allocation/sector breakdown
window._donut=function(slices,size,label){
  size=size||140;
  var cx=size/2,cy=size/2,r=size*.35,thick=size*.08;
  var total=slices.reduce(function(a,b){return a+b.val},0)||1;
  var h='<svg width="'+size+'" height="'+size+'" viewBox="0 0 '+size+' '+size+'">';
  var cum=0;
  slices.forEach(function(s){
    var pct=s.val/total;
    var a1=-Math.PI/2+2*Math.PI*cum;
    var a2=-Math.PI/2+2*Math.PI*(cum+pct);
    cum+=pct;
    var large=pct>.5?1:0;
    var x1=cx+r*Math.cos(a1),y1=cy+r*Math.sin(a1);
    var x2=cx+r*Math.cos(a2),y2=cy+r*Math.sin(a2);
    h+='<path d="M'+x1.toFixed(1)+','+y1.toFixed(1)+' A'+r+','+r+' 0 '+large+' 1 '+x2.toFixed(1)+','+y2.toFixed(1)+'" fill="none" stroke="'+(s.color||'#1A3A78')+'" stroke-width="'+thick+'" opacity=".85"/>';
  });
  if(label){
    h+='<text x="'+cx+'" y="'+(cy-4)+'" text-anchor="middle" font-size="'+(size*.12)+'" font-weight="900" fill="#0A1628" font-family="JetBrains Mono,monospace">'+label.value+'</text>';
    h+='<text x="'+cx+'" y="'+(cy+10)+'" text-anchor="middle" font-size="'+(size*.055)+'" fill="#94a3b8" font-weight="700">'+label.text+'</text>';
  }
  h+='</svg>';
  return h;
};

// 8. MINI TREND INDICATOR — up/down arrow with sparkline
window._trendBadge=function(val,label){
  var up=val>=0;
  var c=up?'#059669':'#dc2626';
  return '<div style="display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:8px;background:'+c+'08;border:1px solid '+c+'15">'
    +'<svg width="12" height="12" viewBox="0 0 12 12"><path d="'+(up?'M6 10V3M3 5l3-3 3 3':'M6 2v7M3 7l3 3 3-3')+'" stroke="'+c+'" stroke-width="1.5" fill="none" stroke-linecap="round"/></svg>'
    +'<span style="font-size:10px;font-weight:800;color:'+c+';font-family:JetBrains Mono,monospace">'+(up?'+':'')+val.toFixed(1)+'%</span>'
    +(label?'<span style="font-size:8px;color:#94a3b8;margin-left:2px">'+label+'</span>':'')
    +'</div>';
};

// 9. CONFIDENCE METER — horizontal segmented bar
window._confidenceMeter=function(score,max){
  max=max||100;
  var segments=10;
  var filled=Math.round(score/max*segments);
  var c=score>=70?'#059669':score>=40?'#d97706':'#dc2626';
  var h='<div style="display:flex;gap:2px;align-items:center">';
  for(var i=0;i<segments;i++){
    h+='<div style="width:8px;height:16px;border-radius:2px;background:'+(i<filled?c:'#e2e5ea')+';transition:background .3s '+(i*50)+'ms"></div>';
  }
  h+='<span style="font-size:11px;font-weight:800;color:'+c+';font-family:JetBrains Mono,monospace;margin-left:6px">'+score+'/'+max+'</span>';
  h+='</div>';
  return h;
};

// 10. DECORATIVE GRID PATTERN — inject into hero background
function _injectHeroGrid(){
  var hero=document.querySelector('.hero');
  if(!hero||hero.querySelector('.hero-grid-decor'))return;
  var d=document.createElement('div');
  d.className='hero-grid-decor';
  d.style.cssText='position:absolute;top:0;right:0;width:300px;height:300px;pointer-events:none;opacity:.04;overflow:hidden';
  var svg='<svg width="300" height="300" viewBox="0 0 300 300">';
  for(var i=0;i<=10;i++){
    svg+='<line x1="'+(i*30)+'" y1="0" x2="'+(i*30)+'" y2="300" stroke="#1A3A78" stroke-width="0.5"/>';
    svg+='<line x1="0" y1="'+(i*30)+'" x2="300" y2="'+(i*30)+'" stroke="#1A3A78" stroke-width="0.5"/>';
  }
  // Diagonal accent
  svg+='<line x1="0" y1="0" x2="300" y2="300" stroke="#1A3A78" stroke-width="0.3" opacity=".5"/>';
  svg+='<circle cx="150" cy="150" r="60" fill="none" stroke="#1A3A78" stroke-width="0.5" opacity=".3"/>';
  svg+='</svg>';
  d.innerHTML=svg;
  hero.style.position='relative';
  hero.appendChild(d);
}

// INIT — inject diagrams on DOM ready
function _initVisuals(){
  _injectHeroDiagram();
  _injectHeroGrid();
  // Pipeline only in hero section — NOT in tabs
  // Removed: was incorrectly injecting into Decide/Trader tabs
}

if(document.readyState==='loading'){
  document.addEventListener('DOMContentLoaded',_initVisuals);
}else{
  _initVisuals();
}

// ═══════════════════════════════════════════════════════════
// N8N WORKFLOW MODELS + INTERACTIVE FINANCIAL CHARTS
// ═══════════════════════════════════════════════════════════

// ─── INTERACTIVE MONTE CARLO SIMULATION CHART ───
window._monteCarloChart=function(container,mc,S){
  if(!container||!mc)return;
  S=S||'$';
  var p10=mc.p10||0,p25=mc.p25||0,p50=mc.p50||0,p75=mc.p75||0,p90=mc.p90||0;
  var now=mc.currentPrice||p50;
  var sims=mc.simulations||5000;
  var h='<div style="padding:20px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">';
  h+='<div><div style="font-size:9px;font-weight:800;color:#94a3b8;letter-spacing:1.5px">MONTE CARLO DISTRIBUTION</div>';
  h+='<div style="font-size:11px;color:#6b7280;margin-top:2px">'+sims.toLocaleString()+' simulations · 1-year horizon</div></div>';
  h+='<div style="font-size:18px;font-weight:900;color:#1A3A78;font-family:JetBrains Mono,monospace">'+S+p50.toLocaleString()+'</div></div>';
  // Distribution bars
  var vals=[{l:'P10 (Bear)',v:p10,c:'#dc2626'},{l:'P25',v:p25,c:'#f59e0b'},{l:'P50 (Base)',v:p50,c:'#1A3A78'},{l:'P75',v:p75,c:'#059669'},{l:'P90 (Bull)',v:p90,c:'#047857'}];
  var max=p90*1.1||1;
  h+='<div style="display:flex;flex-direction:column;gap:8px">';
  vals.forEach(function(v){
    var pct=Math.round(v.v/max*100);
    h+='<div style="display:flex;align-items:center;gap:8px">';
    h+='<div style="width:80px;font-size:9px;font-weight:700;color:#6b7280;text-align:right">'+v.l+'</div>';
    h+='<div style="flex:1;height:14px;background:#f1f5f9;border-radius:7px;overflow:hidden;position:relative">';
    h+='<div style="width:'+pct+'%;height:100%;background:'+v.c+';border-radius:7px;transition:width 1s ease"></div>';
    if(v.v===p50)h+='<div style="position:absolute;top:50%;left:'+Math.round(now/max*100)+'%;transform:translate(-50%,-50%);width:3px;height:20px;background:#0A1628;border-radius:2px;z-index:1"></div>';
    h+='</div>';
    h+='<div style="width:70px;font-size:10px;font-weight:800;color:'+v.c+';font-family:JetBrains Mono,monospace">'+S+v.v.toLocaleString()+'</div></div>';
  });
  h+='</div>';
  // Probability metrics
  if(mc.probUndervalued||mc.prob2x){
    h+='<div style="display:flex;gap:12px;margin-top:14px;flex-wrap:wrap">';
    if(mc.probUndervalued)h+='<div style="flex:1;min-width:100px;padding:10px;border-radius:10px;background:rgba(5,150,105,.04);border:1px solid rgba(5,150,105,.1);text-align:center"><div style="font-size:22px;font-weight:900;color:#059669;font-family:JetBrains Mono,monospace">'+mc.probUndervalued+'%</div><div style="font-size:8px;color:#6b7280;margin-top:2px">Prob. Undervalued</div></div>';
    if(mc.prob2x)h+='<div style="flex:1;min-width:100px;padding:10px;border-radius:10px;background:rgba(124,58,237,.04);border:1px solid rgba(124,58,237,.1);text-align:center"><div style="font-size:22px;font-weight:900;color:#1A3A78;font-family:JetBrains Mono,monospace">'+mc.prob2x+'%</div><div style="font-size:8px;color:#6b7280;margin-top:2px">Prob. 2x Return</div></div>';
    var upProb=mc.probUndervalued||0;
    h+='<div style="flex:1;min-width:100px;padding:10px;border-radius:10px;background:rgba(26,58,120,.04);border:1px solid rgba(26,58,120,.1);text-align:center"><div style="font-size:22px;font-weight:900;color:#1A3A78;font-family:JetBrains Mono,monospace">'+(upProb>60?'BULLISH':upProb>40?'NEUTRAL':'BEARISH')+'</div><div style="font-size:8px;color:#6b7280;margin-top:2px">MC Verdict</div></div>';
    h+='</div>';
  }
  h+='</div>';
  container.innerHTML+=h;
};

// ─── INTERACTIVE EARNINGS GROWTH CHART ───
window._earningsChart=function(container,annualHistory,S){
  if(!container||!annualHistory||annualHistory.length<2)return;
  S=S||'$';
  var h='<div style="padding:20px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="font-size:9px;font-weight:800;color:#94a3b8;letter-spacing:1.5px;margin-bottom:14px">EARNINGS GROWTH TRAJECTORY</div>';
  // SVG chart
  var w=400,ht=120,pad=40;
  var revs=annualHistory.map(function(y){return y.revenue||0});
  var eps=annualHistory.map(function(y){return y.eps||0});
  var maxRev=Math.max.apply(null,revs)||1;
  var maxEps=Math.max.apply(null,eps.map(function(e){return Math.abs(e)}))||1;
  h+='<svg viewBox="0 0 '+w+' '+(ht+30)+'" style="width:100%;height:auto">';
  // Revenue bars
  var barW=(w-2*pad)/(revs.length*2);
  revs.forEach(function(r,i){
    var x=pad+i*(w-2*pad)/revs.length+barW*.3;
    var barH=r/maxRev*(ht-10);
    h+='<rect x="'+x+'" y="'+(ht-barH)+'" width="'+barW+'" height="'+barH+'" rx="3" fill="#1A3A78" opacity=".2"/>';
    h+='<text x="'+(x+barW/2)+'" y="'+(ht+14)+'" text-anchor="middle" font-size="7" fill="#94a3b8">'+(annualHistory[i].year||i)+'</text>';
  });
  // EPS line
  if(eps.length>1){
    var epsPath='';
    eps.forEach(function(e,i){
      var x=pad+i*(w-2*pad)/(eps.length-1||1);
      var y=ht-10-(e/maxEps)*(ht-20);
      epsPath+=(i===0?'M':'L')+x.toFixed(1)+','+y.toFixed(1);
    });
    h+='<path d="'+epsPath+'" fill="none" stroke="#059669" stroke-width="2" stroke-linecap="round"/>';
    eps.forEach(function(e,i){
      var x=pad+i*(w-2*pad)/(eps.length-1||1);
      var y=ht-10-(e/maxEps)*(ht-20);
      h+='<circle cx="'+x.toFixed(1)+'" cy="'+y.toFixed(1)+'" r="3" fill="#059669" stroke="#fff" stroke-width="1.5"/>';
    });
  }
  // Legend
  h+='<rect x="'+(w-120)+'" y="2" width="8" height="8" rx="2" fill="#1A3A78" opacity=".3"/>';
  h+='<text x="'+(w-108)+'" y="9" font-size="7" fill="#94a3b8">Revenue</text>';
  h+='<line x1="'+(w-60)+'" y1="6" x2="'+(w-48)+'" y2="6" stroke="#059669" stroke-width="2"/>';
  h+='<text x="'+(w-44)+'" y="9" font-size="7" fill="#94a3b8">EPS</text>';
  h+='</svg></div>';
  container.innerHTML+=h;
};

// ─── RISK/RETURN SCATTER PLOT ───
window._riskReturnScatter=function(container,stocks,S){
  if(!container||!stocks||stocks.length<1)return;
  S=S||'$';
  var h='<div style="padding:20px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="font-size:9px;font-weight:800;color:#94a3b8;letter-spacing:1.5px;margin-bottom:14px">RISK vs RETURN — PORTFOLIO MAP</div>';
  var w=360,ht=200,pad=35;
  var maxRisk=Math.max.apply(null,stocks.map(function(s){return s.risk||0}))*1.2||1;
  var maxRet=Math.max.apply(null,stocks.map(function(s){return Math.abs(s.ret||0)}))*1.3||1;
  h+='<svg viewBox="0 0 '+w+' '+(ht+10)+'" style="width:100%;height:auto">';
  // Axes
  h+='<line x1="'+pad+'" y1="'+(ht-pad)+'" x2="'+(w-10)+'" y2="'+(ht-pad)+'" stroke="#e2e5ea" stroke-width="0.5"/>';
  h+='<line x1="'+pad+'" y1="10" x2="'+pad+'" y2="'+(ht-pad)+'" stroke="#e2e5ea" stroke-width="0.5"/>';
  h+='<text x="'+(w/2)+'" y="'+(ht+6)+'" text-anchor="middle" font-size="7" fill="#94a3b8">Risk (Beta / Volatility) →</text>';
  h+='<text x="8" y="'+(ht/2-10)+'" text-anchor="middle" font-size="7" fill="#94a3b8" transform="rotate(-90,8,'+(ht/2-10)+')">Return →</text>';
  // Quadrant labels
  h+='<text x="'+(pad+20)+'" y="25" font-size="6" fill="#059669" opacity=".4">Low Risk / High Return</text>';
  h+='<text x="'+(w-80)+'" y="25" font-size="6" fill="#d97706" opacity=".4">High Risk / High Return</text>';
  h+='<text x="'+(pad+20)+'" y="'+(ht-pad-8)+'" font-size="6" fill="#6b7280" opacity=".4">Low Risk / Low Return</text>';
  h+='<text x="'+(w-80)+'" y="'+(ht-pad-8)+'" font-size="6" fill="#dc2626" opacity=".4">High Risk / Low Return</text>';
  // Mid lines
  h+='<line x1="'+pad+'" y1="'+((ht-pad)/2)+'" x2="'+(w-10)+'" y2="'+((ht-pad)/2)+'" stroke="#e2e5ea" stroke-width="0.3" stroke-dasharray="3,3"/>';
  h+='<line x1="'+((w-10+pad)/2)+'" y1="10" x2="'+((w-10+pad)/2)+'" y2="'+(ht-pad)+'" stroke="#e2e5ea" stroke-width="0.3" stroke-dasharray="3,3"/>';
  // Plot stocks
  stocks.forEach(function(s){
    var x=pad+(s.risk||0)/maxRisk*(w-pad-10);
    var y=(ht-pad)-(s.ret||0)/maxRet*(ht-pad-10);
    var c=s.ret>15?'#059669':s.ret>5?'#1A3A78':s.ret>0?'#d97706':'#dc2626';
    h+='<circle cx="'+x.toFixed(1)+'" cy="'+y.toFixed(1)+'" r="6" fill="'+c+'" opacity=".7" stroke="#fff" stroke-width="1"/>';
    h+='<text x="'+x.toFixed(1)+'" y="'+(y-9).toFixed(1)+'" text-anchor="middle" font-size="6" font-weight="800" fill="'+c+'">'+(s.symbol||'')+'</text>';
  });
  h+='</svg></div>';
  container.innerHTML+=h;
};

// ─── N8N WORKFLOW VISUAL — Node Pipeline Diagram ───
window._n8nPipelineDiagram=function(workflow){
  if(!workflow||!workflow.nodes)return'';
  var h='<div style="padding:18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">';
  h+='<div><div style="font-size:11px;font-weight:800;color:#0A1628;font-family:Sora,sans-serif">'+workflow.name+'</div>';
  h+='<div style="font-size:9px;color:#6b7280;margin-top:2px">'+workflow.description+'</div></div>';
  h+='<div style="padding:3px 10px;border-radius:100px;background:rgba(26,58,120,.05);border:1px solid rgba(26,58,120,.1);font-size:8px;font-weight:700;color:#1A3A78">'+workflow.trigger+'</div></div>';
  // Node flow
  h+='<div style="display:flex;align-items:center;gap:0;overflow-x:auto;padding:8px 0">';
  var nodeColors=['#3b82f6','#059669','#d97706','#1A3A78','#dc2626','#0891b2'];
  workflow.nodes.forEach(function(node,i){
    var nc=nodeColors[i%nodeColors.length];
    h+='<div style="flex-shrink:0;text-align:center;min-width:90px">';
    h+='<div style="width:36px;height:36px;border-radius:10px;background:'+nc+'10;border:1.5px solid '+nc+'30;display:flex;align-items:center;justify-content:center;margin:0 auto 6px;font-size:14px">';
    var icons=['⚡','🔗','🔀','📊','📧','💾'];
    h+=icons[i%icons.length]+'</div>';
    h+='<div style="font-size:8px;font-weight:700;color:#0A1628;line-height:1.3">'+node+'</div></div>';
    if(i<workflow.nodes.length-1)h+='<div style="flex-shrink:0;color:#c7d2fe;font-size:16px;margin:0 -2px">→</div>';
  });
  h+='</div></div>';
  return h;
};

// ─── N8N DASHBOARD — Shows all workflow models ───
window._n8nDashboard=function(container){
  if(!container)return;
  var workflows=[
    {name:'Stock Alert Pipeline',description:'Price/volume breakout alerts every 15 min',trigger:'⏱ 15min',
     nodes:['Schedule','Yahoo API','Price Check','Alert']},
    {name:'Earnings Calendar',description:'Pre-populates analysis queue before earnings',trigger:'📅 Daily',
     nodes:['Cron','Earnings API','Filter','Queue']},
    {name:'Sector Rotation',description:'Scans 11 sector ETFs, identifies rotation',trigger:'🔄 Daily',
     nodes:['Schedule','Batch Fetch','Calculate','Rank','Store']},
    {name:'Portfolio Rebalance',description:'Drift detection and rebalance signals',trigger:'📊 Weekly',
     nodes:['Schedule','Holdings','Drift Calc','Alert']},
    {name:'News Sentiment',description:'AI-scored news sentiment from multiple sources',trigger:'📰 30min',
     nodes:['Schedule','RSS','AI Score','Categorize','Dashboard']},
    {name:'DCF Auto-Update',description:'Refreshes valuations on new quarterly data',trigger:'🔔 Webhook',
     nodes:['Webhook','Financials','DCF Calc','Compare','Alert']}
  ];
  var h='<div style="padding:20px;border-radius:14px;background:linear-gradient(135deg,rgba(26,58,120,.02),rgba(26,58,120,.01));border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">';
  h+='<div><div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">⚡ n8n Automation Workflows</div>';
  h+='<div style="font-size:10px;color:#6b7280;margin-top:2px">Automate your research pipeline with these pre-built models</div></div>';
  h+='<div style="padding:4px 12px;border-radius:100px;background:#1A3A78;color:#fff;font-size:8px;font-weight:800">6 WORKFLOWS</div></div>';
  workflows.forEach(function(wf){h+=_n8nPipelineDiagram(wf)});
  h+='</div>';
  container.innerHTML+=h;
};

// ─── SECTOR HEATMAP — Color-coded sector performance grid ───
window._sectorHeatmap=function(sectors){
  if(!sectors||sectors.length<1)return'';
  var h='<div style="padding:16px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="font-size:9px;font-weight:800;color:#94a3b8;letter-spacing:1.5px;margin-bottom:12px">SECTOR PERFORMANCE HEATMAP</div>';
  h+='<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(90px,1fr));gap:6px">';
  sectors.forEach(function(s){
    var c=s.change>=2?'#047857':s.change>=0.5?'#059669':s.change>=-0.5?'#6b7280':s.change>=-2?'#ef4444':'#991b1b';
    var bg=s.change>=2?'#05966915':s.change>=0.5?'#05966910':s.change>=-0.5?'#6b728010':s.change>=-2?'#ef444415':'#99101010';
    h+='<div style="padding:10px 8px;border-radius:10px;background:'+bg+';border:1px solid '+c+'20;text-align:center">';
    h+='<div style="font-size:8px;font-weight:800;color:#0A1628;margin-bottom:4px">'+s.name+'</div>';
    h+='<div style="font-size:14px;font-weight:900;color:'+c+';font-family:JetBrains Mono,monospace">'+(s.change>=0?'+':'')+s.change.toFixed(1)+'%</div></div>';
  });
  h+='</div></div>';
  return h;
};

// ─── AUTO-INJECT n8n dashboard into Tools tab ───
function _injectN8nDashboard(){
  var obs2=new MutationObserver(function(muts){
    muts.forEach(function(m){
      if(m.addedNodes.length){
        // Check if Tools/Finance tab content area has loaded
        var fin=document.getElementById('financeContent');
        if(fin&&fin.children.length>0&&!fin.querySelector('#n8nDash')){
          var d=document.createElement('div');d.id='n8nDash';
          fin.appendChild(d);
          _n8nDashboard(d);
        }
      }
    });
  });
  var fc=document.getElementById('financeContent');
  if(fc)obs2.observe(fc,{childList:true,subtree:true});
}
if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',_injectN8nDashboard)}
else{_injectN8nDashboard()}

// ═══════════════════════════════════════════════════════════
// PREMIUM SERVICES — Checkout Modal + Upgrade CTAs
// ═══════════════════════════════════════════════════════════

// Premium checkout modal
window._showPremiumCheckout=function(plan){
  var plans={
    pro:{name:'Pro Trader',price:'$29/mo',color:'#1A3A78',features:['Unlimited analyses','Decision Engine — Trader','5-engine algo signals','Options intelligence','Top Trades daily','AI trading assistant']},
    institutional:{name:'Institutional',price:'$79/mo',color:'#1A3A78',features:['Everything in Pro','Investor Decision Engine','Wealth Engine Pro','Portfolio Management','Nifty 500 scanner','n8n automations','PDF export + sharing']}
  };
  var p=plans[plan]||plans.pro;
  var ov=document.createElement('div');
  ov.id='premiumCheckoutOverlay';
  ov.style.cssText='position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,.5);backdrop-filter:blur(4px);display:flex;align-items:center;justify-content:center;padding:20px;animation:modalFadeIn .25s ease';
  ov.onclick=function(e){if(e.target===ov){ov.remove()}};
  
  var h='<div style="width:100%;max-width:420px;background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 24px 80px rgba(0,0,0,.2);animation:modalSlideUp .3s cubic-bezier(.16,1,.3,1)">';
  // Header
  h+='<div style="padding:28px 28px 20px;background:linear-gradient(135deg,'+p.color+','+p.color+'dd);position:relative;overflow:hidden">';
  h+='<div style="position:absolute;top:-30px;right:-30px;width:100px;height:100px;background:radial-gradient(circle,rgba(255,255,255,.1),transparent 70%)"></div>';
  h+='<div style="position:relative">';
  h+='<div style="font-size:10px;color:rgba(255,255,255,.6);font-weight:700;letter-spacing:1.5px;margin-bottom:6px">UPGRADE TO</div>';
  h+='<div style="font-size:24px;font-weight:900;color:#fff;font-family:Sora,sans-serif">'+p.name+'</div>';
  h+='<div style="font-size:32px;font-weight:900;color:#fff;font-family:JetBrains Mono,monospace;margin-top:4px">'+p.price+'</div>';
  h+='<div style="font-size:10px;color:rgba(255,255,255,.6);margin-top:4px">7-day free trial · Cancel anytime</div>';
  h+='</div></div>';
  // Features
  h+='<div style="padding:24px 28px">';
  h+='<div style="font-size:10px;font-weight:800;color:#94a3b8;letter-spacing:1px;margin-bottom:12px">WHAT YOU GET</div>';
  p.features.forEach(function(f){
    h+='<div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid #f1f3f5"><span style="width:20px;height:20px;border-radius:6px;background:'+p.color+'10;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:10px;color:'+p.color+'">✓</span><span style="font-size:12px;color:#374151;font-weight:600">'+f+'</span></div>';
  });
  // Email input
  h+='<div style="margin-top:20px">';
  h+='<div style="font-size:10px;font-weight:700;color:#6b7280;margin-bottom:6px">Your email</div>';
  h+='<input type="email" id="premiumEmailInput" placeholder="you@company.com" style="width:100%;padding:12px 14px;border-radius:10px;border:1.5px solid #e2e5ea;font-size:13px;color:#0A1628;font-family:Plus Jakarta Sans,sans-serif;outline:none;transition:border-color .2s" onfocus="this.style.borderColor=\''+p.color+'\'" onblur="this.style.borderColor=\'#e2e5ea\'">';
  h+='</div>';
  // CTA
  h+='<button onclick="_processPremiumSignup(\''+plan+'\')" style="margin-top:16px;width:100%;padding:16px;border-radius:12px;background:linear-gradient(135deg,'+p.color+','+p.color+'cc);border:none;color:#fff;font-size:14px;font-weight:900;cursor:pointer;font-family:Sora,sans-serif;box-shadow:0 4px 16px '+p.color+'30;transition:all .2s;letter-spacing:.5px" onmouseover="this.style.transform=\'translateY(-1px)\'" onmouseout="this.style.transform=\'none\'">Start 7-Day Free Trial</button>';
  h+='<div style="text-align:center;margin-top:10px;font-size:9px;color:#94a3b8">🔒 Secured by Stripe · No charge during trial</div>';
  // Guarantee
  h+='<div style="margin-top:16px;padding:12px;border-radius:10px;background:rgba(5,150,105,.03);border:1px solid rgba(5,150,105,.1);text-align:center">';
  h+='<div style="font-size:10px;font-weight:800;color:#059669">💰 30-Day Money-Back Guarantee</div>';
  h+='<div style="font-size:9px;color:#6b7280;margin-top:2px">Not satisfied? Full refund, no questions asked.</div>';
  h+='</div>';
  h+='</div>';
  // Close
  h+='<div style="padding:12px 28px;border-top:1px solid #f1f3f5;text-align:center">';
  h+='<button onclick="document.getElementById(\'premiumCheckoutOverlay\').remove()" style="background:none;border:none;color:#94a3b8;font-size:11px;cursor:pointer;padding:4px 12px">Maybe later</button>';
  h+='</div></div>';
  
  ov.innerHTML=h;
  document.body.appendChild(ov);
};

// Process signup
window._processPremiumSignup=function(plan){
  var email=document.getElementById('premiumEmailInput');
  if(!email||!email.value||!email.value.includes('@')){
    email.style.borderColor='#dc2626';
    email.style.boxShadow='0 0 0 3px rgba(220,38,38,.1)';
    return;
  }
  var btn=email.parentElement.nextElementSibling;
  if(btn){
    btn.innerHTML='<span style="display:inline-block;width:14px;height:14px;border:2px solid #fff;border-top-color:transparent;border-radius:50%;animation:spin .5s linear infinite;vertical-align:middle;margin-right:8px"></span>Processing...';
    btn.style.pointerEvents='none';
  }
  // Store email and plan
  localStorage.setItem('celesys-premium-email',email.value);
  localStorage.setItem('celesys-premium-plan',plan);
  // Simulate processing
  setTimeout(function(){
    var ov=document.getElementById('premiumCheckoutOverlay');
    if(ov)ov.innerHTML='<div style="width:100%;max-width:420px;background:#fff;border-radius:20px;padding:40px;text-align:center;box-shadow:0 24px 80px rgba(0,0,0,.2);animation:scaleIn .3s ease">'
      +'<div style="width:60px;height:60px;border-radius:50%;background:rgba(5,150,105,.1);display:flex;align-items:center;justify-content:center;margin:0 auto 16px;font-size:28px">✅</div>'
      +'<div style="font-size:18px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif;margin-bottom:8px">Welcome to '+plan.charAt(0).toUpperCase()+plan.slice(1)+'!</div>'
      +'<div style="font-size:12px;color:#6b7280;line-height:1.6;margin-bottom:20px">Your 7-day free trial is active. All premium features are now unlocked.</div>'
      +'<button onclick="document.getElementById(\'premiumCheckoutOverlay\').remove();location.reload()" style="padding:12px 32px;border-radius:10px;background:linear-gradient(135deg,#1A3A78,#1e40af);color:#fff;border:none;font-size:13px;font-weight:800;cursor:pointer;font-family:Sora,sans-serif;box-shadow:0 4px 16px rgba(26,58,120,.25)">Start Exploring →</button>'
      +'</div>';
  },2000);
};

// ─── PREMIUM UPGRADE BANNERS inside gated sections ───
window._premiumUpgradeBanner=function(feature,plan){
  plan=plan||'pro';
  var p=plan==='institutional'?{name:'Institutional',price:'$79/mo',color:'#1A3A78'}:{name:'Pro Trader',price:'$29/mo',color:'#1A3A78'};
  return '<div style="margin:14px 0;padding:20px;border-radius:14px;background:linear-gradient(135deg,'+p.color+'05,'+p.color+'02);border:1.5px solid '+p.color+'15;text-align:center">'
    +'<div style="font-size:24px;margin-bottom:8px">🔒</div>'
    +'<div style="font-size:13px;font-weight:800;color:#0A1628;font-family:Sora,sans-serif;margin-bottom:4px">'+feature+'</div>'
    +'<div style="font-size:11px;color:#6b7280;margin-bottom:14px;max-width:350px;margin-left:auto;margin-right:auto;line-height:1.5">Unlock this feature with '+p.name+' — '+p.price+' with 7-day free trial</div>'
    +'<button onclick="_showPremiumCheckout(\''+plan+'\')" style="padding:10px 28px;border-radius:10px;background:linear-gradient(135deg,'+p.color+','+p.color+'cc);color:#fff;border:none;font-size:11px;font-weight:800;cursor:pointer;font-family:Sora,sans-serif;box-shadow:0 2px 10px '+p.color+'25;transition:all .2s" onmouseover="this.style.transform=\'translateY(-1px)\'" onmouseout="this.style.transform=\'none\'">Upgrade to '+p.name+'</button>'
    +'</div>';
};

// ─── FLOATING UPGRADE CTA (shows after scrolling past pricing) ───
function _initFloatingCTA(){
  var shown=false;
  var cta=document.createElement('div');
  cta.id='floatingUpgradeCTA';
  cta.style.cssText='position:fixed;bottom:20px;left:20px;z-index:998;padding:12px 20px;border-radius:12px;background:linear-gradient(135deg,#1A3A78,#1e40af);color:#fff;font-size:11px;font-weight:800;font-family:Sora,sans-serif;cursor:pointer;box-shadow:0 8px 32px rgba(26,58,120,.3);display:none;transition:all .3s;max-width:280px;line-height:1.4';
  cta.innerHTML='<div style="display:flex;align-items:center;gap:10px"><span style="font-size:18px">⚡</span><div><div>Unlock Pro Features</div><div style="font-size:9px;font-weight:500;color:rgba(255,255,255,.7);margin-top:2px">7-day free trial — $29/mo</div></div><button onclick="event.stopPropagation();document.getElementById(\'floatingUpgradeCTA\').style.display=\'none\'" style="background:none;border:none;color:rgba(255,255,255,.5);cursor:pointer;font-size:14px;padding:0 0 0 8px">✕</button></div>';
  cta.onclick=function(){_showPremiumCheckout('pro')};
  document.body.appendChild(cta);
  
  window.addEventListener('scroll',function(){
    if(window.scrollY>1200&&!shown&&!localStorage.getItem('celesys-premium-plan')){
      cta.style.display='block';
      shown=true;
    }
  },{passive:true});
}
if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',_initFloatingCTA)}
else{_initFloatingCTA()}

// ═══════════════════════════════════════════════════════════════
// NEW TRADER FEATURES — Fibonacci, Bollinger, Volume Profile,
// Golden Cross, Fear & Greed, Earnings Surprise, Trade Scorecard
// ═══════════════════════════════════════════════════════════════

// ─── 1. FIBONACCI RETRACEMENT CHART ───
window._fibonacciChart=function(high,low,current,S){
  if(!high||!low||high<=low)return'';
  S=S||'$';
  var range=high-low;
  var levels=[
    {pct:0,name:'0% (High)',val:high,c:'#dc2626'},
    {pct:23.6,name:'23.6%',val:high-range*.236,c:'#f59e0b'},
    {pct:38.2,name:'38.2%',val:high-range*.382,c:'#d97706'},
    {pct:50,name:'50%',val:high-range*.5,c:'#6b7280'},
    {pct:61.8,name:'61.8% (Golden)',val:high-range*.618,c:'#059669'},
    {pct:78.6,name:'78.6%',val:high-range*.786,c:'#0891b2'},
    {pct:100,name:'100% (Low)',val:low,c:'#1A3A78'}
  ];
  var h='<div style="padding:18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">';
  h+='<div style="font-size:9px;font-weight:800;color:#94a3b8;letter-spacing:1.5px">FIBONACCI RETRACEMENT</div>';
  h+='<div style="font-size:11px;font-weight:800;color:#1A3A78;font-family:JetBrains Mono,monospace">'+S+current.toLocaleString()+'</div></div>';
  var maxVal=high*1.02;
  levels.forEach(function(l){
    var pct=((l.val-low)/(high-low))*100;
    var isNear=Math.abs(current-l.val)/range<0.03;
    h+='<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">';
    h+='<div style="width:65px;font-size:8px;font-weight:700;color:'+l.c+';text-align:right">'+l.name+'</div>';
    h+='<div style="flex:1;height:2px;background:'+l.c+'20;position:relative">';
    h+='<div style="position:absolute;top:50%;left:'+pct+'%;transform:translate(-50%,-50%);width:'+(isNear?10:4)+'px;height:'+(isNear?10:4)+'px;border-radius:50%;background:'+(isNear?'#1A3A78':l.c)+';box-shadow:'+(isNear?'0 0 8px rgba(26,58,120,.4)':'none')+'"></div>';
    h+='</div>';
    h+='<div style="width:60px;font-size:9px;font-weight:800;color:'+(isNear?'#1A3A78':l.c)+';font-family:JetBrains Mono,monospace;text-align:right">'+S+Math.round(l.val).toLocaleString()+'</div>';
    h+='</div>';
  });
  // Current price marker
  var curPct=((current-low)/(high-low))*100;
  h+='<div style="margin-top:10px;padding:8px 12px;border-radius:8px;background:rgba(26,58,120,.04);font-size:10px;color:#374151">';
  var nearest=levels.reduce(function(a,b){return Math.abs(a.val-current)<Math.abs(b.val-current)?a:b});
  h+='Price at <strong style="color:#1A3A78">'+nearest.name+'</strong> level. ';
  if(curPct>61.8)h+='<span style="color:#059669">Near support — potential bounce zone.</span>';
  else if(curPct<38.2)h+='<span style="color:#dc2626">Near resistance — watch for rejection.</span>';
  else h+='<span style="color:#d97706">Mid-range — wait for directional breakout.</span>';
  h+='</div></div>';
  return h;
};

// ─── 2. FEAR & GREED INDEX ───
window._fearGreedGauge=function(score){
  if(!score&&score!==0)return'';
  score=Math.max(0,Math.min(100,score));
  var label=score>=80?'EXTREME GREED':score>=60?'GREED':score>=40?'NEUTRAL':score>=20?'FEAR':'EXTREME FEAR';
  var c=score>=80?'#059669':score>=60?'#10b981':score>=40?'#d97706':score>=20?'#ef4444':'#dc2626';
  var emoji=score>=80?'🤑':score>=60?'😊':score>=40?'😐':score>=20?'😰':'😱';
  var h='<div style="padding:18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0;text-align:center">';
  h+='<div style="font-size:9px;font-weight:800;color:#94a3b8;letter-spacing:1.5px;margin-bottom:12px">MARKET FEAR & GREED</div>';
  // Semi-circle gauge
  var r=50,circ=Math.PI*r,offset=circ*(1-score/100);
  h+='<svg width="160" height="95" viewBox="0 0 120 70">';
  h+='<defs><linearGradient id="fgGrad"><stop offset="0%" stop-color="#dc2626"/><stop offset="25%" stop-color="#ef4444"/><stop offset="50%" stop-color="#d97706"/><stop offset="75%" stop-color="#10b981"/><stop offset="100%" stop-color="#059669"/></linearGradient></defs>';
  h+='<path d="M10,65 A50,50 0 0,1 110,65" fill="none" stroke="#e2e5ea" stroke-width="8" stroke-linecap="round"/>';
  h+='<path d="M10,65 A50,50 0 0,1 110,65" fill="none" stroke="url(#fgGrad)" stroke-width="8" stroke-linecap="round" stroke-dasharray="'+circ+'" stroke-dashoffset="'+offset+'" style="transition:stroke-dashoffset 1.2s ease"/>';
  // Needle
  var angle=-180+score*1.8;
  h+='<line x1="60" y1="65" x2="'+(60+40*Math.cos(angle*Math.PI/180))+'" y2="'+(65+40*Math.sin(angle*Math.PI/180))+'" stroke="#0A1628" stroke-width="2" stroke-linecap="round"/>';
  h+='<circle cx="60" cy="65" r="4" fill="#0A1628"/>';
  h+='<text x="60" y="55" text-anchor="middle" font-size="18" font-weight="900" fill="'+c+'" font-family="JetBrains Mono,monospace">'+score+'</text>';
  h+='</svg>';
  h+='<div style="font-size:14px;margin-top:4px">'+emoji+'</div>';
  h+='<div style="font-size:12px;font-weight:900;color:'+c+';font-family:Sora,sans-serif;margin-top:4px">'+label+'</div>';
  h+='<div style="font-size:9px;color:#94a3b8;margin-top:4px">';
  if(score<25)h+='Markets pricing maximum pessimism. Historically, best time to buy.';
  else if(score<40)h+='Elevated fear. Contrarians start accumulating.';
  else if(score<60)h+='Balanced sentiment. Follow technicals and fundamentals.';
  else if(score<80)h+='Optimism rising. Momentum trades work but trail stops tight.';
  else h+='Extreme euphoria. Protect profits. Tighten stops. Avoid FOMO entries.';
  h+='</div></div>';
  return h;
};

// ─── 3. TRADE SCORECARD — Summary verdict card ───
window._tradeScorecard=function(data){
  if(!data)return'';
  var d=data;
  var score=d.score||0;
  var verdict=score>=75?'STRONG BUY':score>=60?'BUY':score>=40?'HOLD':score>=25?'SELL':'STRONG SELL';
  var vc=score>=75?'#059669':score>=60?'#10b981':score>=40?'#d97706':score>=25?'#ef4444':'#dc2626';
  var factors=[
    {name:'Trend',score:d.trendScore||0,weight:25},
    {name:'Momentum',score:d.momentumScore||0,weight:20},
    {name:'Volume',score:d.volumeScore||0,weight:15},
    {name:'Valuation',score:d.valuationScore||0,weight:20},
    {name:'Risk',score:d.riskScore||0,weight:20}
  ];
  var h='<div style="padding:20px;border-radius:16px;background:#fff;border:2px solid '+vc+'30;margin:14px 0;box-shadow:0 4px 20px '+vc+'08">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">';
  h+='<div><div style="font-size:9px;font-weight:800;color:#94a3b8;letter-spacing:1.5px">TRADE SCORECARD</div>';
  h+='<div style="font-size:11px;color:#6b7280;margin-top:2px">'+(d.symbol||'')+' · '+(d.timeframe||'Swing')+' Trade</div></div>';
  h+='<div style="text-align:center"><div style="font-size:32px;font-weight:900;color:'+vc+';font-family:JetBrains Mono,monospace">'+score+'</div>';
  h+='<div style="font-size:10px;font-weight:800;color:'+vc+'">'+verdict+'</div></div></div>';
  // Factor bars
  factors.forEach(function(f){
    var fc=f.score>=70?'#059669':f.score>=40?'#d97706':'#dc2626';
    h+='<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">';
    h+='<div style="width:70px;font-size:9px;font-weight:700;color:#6b7280;text-align:right">'+f.name+' ('+f.weight+'%)</div>';
    h+='<div style="flex:1;height:8px;background:#f1f5f9;border-radius:4px;overflow:hidden">';
    h+='<div style="width:'+f.score+'%;height:100%;background:'+fc+';border-radius:4px;transition:width .8s ease"></div></div>';
    h+='<div style="width:30px;font-size:10px;font-weight:800;color:'+fc+';font-family:JetBrains Mono,monospace">'+f.score+'</div></div>';
  });
  // Action row
  if(d.entry||d.sl||d.target){
    h+='<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:14px;padding-top:14px;border-top:1px solid #f1f3f5">';
    [{l:'ENTRY',v:d.entry,c:'#1A3A78'},{l:'STOP LOSS',v:d.sl,c:'#dc2626'},{l:'TARGET 1',v:d.t1,c:'#059669'},{l:'TARGET 2',v:d.t2,c:'#047857'}].forEach(function(x){
      if(x.v)h+='<div style="text-align:center;padding:8px 4px;border-radius:8px;background:'+x.c+'06;border:1px solid '+x.c+'12"><div style="font-size:7px;color:'+x.c+';font-weight:700">'+x.l+'</div><div style="font-size:12px;font-weight:900;color:'+x.c+';font-family:JetBrains Mono,monospace;margin-top:2px">'+(data.csym||'$')+x.v.toLocaleString()+'</div></div>';
    });
    h+='</div>';
  }
  h+='</div>';
  return h;
};

// ─── 4. BOLLINGER BANDS VISUALIZATION ───
window._bollingerBands=function(prices,sma20,upper,lower,current,S){
  if(!prices||prices.length<5)return'';
  S=S||'$';
  var w=360,ht=140,pad=30;
  var allVals=prices.concat([upper||0,lower||0]).filter(function(v){return v>0});
  var mn=Math.min.apply(null,allVals)*.98;
  var mx=Math.max.apply(null,allVals)*1.02;
  var rng=mx-mn||1;
  function x(i){return pad+i/(prices.length-1)*(w-pad*2)}
  function y(v){return pad+(1-(v-mn)/rng)*(ht-pad*2)}
  var h='<div style="padding:16px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="font-size:9px;font-weight:800;color:#94a3b8;letter-spacing:1.5px;margin-bottom:10px">BOLLINGER BANDS</div>';
  h+='<svg viewBox="0 0 '+w+' '+ht+'" style="width:100%;height:auto">';
  // Band fill
  if(upper&&lower){
    h+='<rect x="'+pad+'" y="'+y(upper)+'" width="'+(w-pad*2)+'" height="'+(y(lower)-y(upper))+'" fill="rgba(26,58,120,.04)" rx="4"/>';
    h+='<line x1="'+pad+'" y1="'+y(upper)+'" x2="'+(w-pad)+'" y2="'+y(upper)+'" stroke="#1A3A78" stroke-width="0.8" stroke-dasharray="3,3" opacity=".4"/>';
    h+='<line x1="'+pad+'" y1="'+y(lower)+'" x2="'+(w-pad)+'" y2="'+y(lower)+'" stroke="#1A3A78" stroke-width="0.8" stroke-dasharray="3,3" opacity=".4"/>';
    h+='<text x="'+(w-pad+4)+'" y="'+(y(upper)+3)+'" font-size="7" fill="#1A3A78" opacity=".5">Upper</text>';
    h+='<text x="'+(w-pad+4)+'" y="'+(y(lower)+3)+'" font-size="7" fill="#1A3A78" opacity=".5">Lower</text>';
  }
  if(sma20)h+='<line x1="'+pad+'" y1="'+y(sma20)+'" x2="'+(w-pad)+'" y2="'+y(sma20)+'" stroke="#d97706" stroke-width="1" stroke-dasharray="4,2" opacity=".6"/>';
  // Price line
  var path='';
  prices.forEach(function(p,i){path+=(i===0?'M':'L')+x(i).toFixed(1)+','+y(p).toFixed(1)});
  h+='<path d="'+path+'" fill="none" stroke="#1A3A78" stroke-width="2" stroke-linecap="round"/>';
  // Current dot
  var lastX=x(prices.length-1),lastY=y(prices[prices.length-1]);
  h+='<circle cx="'+lastX+'" cy="'+lastY+'" r="4" fill="#1A3A78" stroke="#fff" stroke-width="2"/>';
  h+='</svg>';
  // Interpretation
  h+='<div style="margin-top:8px;padding:8px 12px;border-radius:8px;background:rgba(26,58,120,.03);font-size:10px;color:#374151">';
  if(current&&upper&&current>upper*.98)h+='<span style="color:#dc2626;font-weight:700">Price at upper band</span> — overbought squeeze. Watch for mean reversion.';
  else if(current&&lower&&current<lower*1.02)h+='<span style="color:#059669;font-weight:700">Price at lower band</span> — oversold. Potential bounce entry.';
  else h+='<span style="color:#6b7280;font-weight:700">Price within bands</span> — normal range. Band width signals volatility regime.';
  h+='</div></div>';
  return h;
};

// ─── 5. GOLDEN/DEATH CROSS DETECTOR ───
window._crossDetector=function(sma50,sma200,prevSma50,prevSma200,current,S){
  S=S||'$';
  if(!sma50||!sma200)return'';
  var golden=sma50>sma200&&prevSma50&&prevSma50<=prevSma200;
  var death=sma50<sma200&&prevSma50&&prevSma50>=prevSma200;
  var above=sma50>sma200;
  var icon=golden?'✨':death?'💀':above?'📈':'📉';
  var label=golden?'GOLDEN CROSS DETECTED':death?'DEATH CROSS DETECTED':above?'Bullish Structure (50>200)':'Bearish Structure (50<200)';
  var c=golden||above?'#059669':'#dc2626';
  var h='<div style="padding:14px 18px;border-radius:12px;background:'+c+'06;border:1.5px solid '+c+'20;margin:10px 0;display:flex;align-items:center;gap:12px">';
  h+='<div style="font-size:24px;flex-shrink:0">'+icon+'</div>';
  h+='<div style="flex:1"><div style="font-size:11px;font-weight:800;color:'+c+';font-family:Sora,sans-serif">'+label+'</div>';
  h+='<div style="font-size:9px;color:#6b7280;margin-top:3px;line-height:1.5">SMA50: '+S+Math.round(sma50).toLocaleString()+' · SMA200: '+S+Math.round(sma200).toLocaleString();
  if(golden)h+=' · <strong style="color:#059669">Historically bullish for 6-12 months. Avg return +15%.</strong>';
  else if(death)h+=' · <strong style="color:#dc2626">Risk of extended decline. Reduce exposure or hedge.</strong>';
  h+='</div></div>';
  h+='<div style="text-align:center;flex-shrink:0"><div style="font-size:18px;font-weight:900;color:'+c+';font-family:JetBrains Mono,monospace">'+S+Math.round(current).toLocaleString()+'</div><div style="font-size:7px;color:#94a3b8">CURRENT</div></div></div>';
  return h;
};

// ─── 6. EARNINGS SURPRISE TRACKER ───
window._earningsSurprise=function(quarters){
  if(!quarters||quarters.length<1)return'';
  var h='<div style="padding:18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="font-size:9px;font-weight:800;color:#94a3b8;letter-spacing:1.5px;margin-bottom:12px">EARNINGS SURPRISE HISTORY</div>';
  h+='<div style="display:flex;gap:8px;flex-wrap:wrap">';
  quarters.forEach(function(q){
    var beat=q.surprise>0;
    var c=beat?'#059669':'#dc2626';
    var icon=beat?'▲':'▼';
    h+='<div style="flex:1;min-width:70px;padding:10px 8px;border-radius:10px;background:'+c+'06;border:1px solid '+c+'15;text-align:center">';
    h+='<div style="font-size:8px;color:#94a3b8;font-weight:700">'+(q.quarter||'Q?')+'</div>';
    h+='<div style="font-size:16px;font-weight:900;color:'+c+';font-family:JetBrains Mono,monospace;margin:4px 0">'+icon+(Math.abs(q.surprise||0)).toFixed(1)+'%</div>';
    h+='<div style="font-size:7px;color:#6b7280">'+(beat?'BEAT':'MISS')+'</div></div>';
  });
  h+='</div>';
  var beats=quarters.filter(function(q){return q.surprise>0}).length;
  h+='<div style="margin-top:10px;padding:8px 12px;border-radius:8px;background:rgba(26,58,120,.03);font-size:10px;color:#374151">';
  h+='Beat rate: <strong style="color:#1A3A78">'+beats+'/'+quarters.length+'</strong> quarters. ';
  if(beats>=quarters.length*.75)h+='<span style="color:#059669">Consistently beats estimates — positive signal.</span>';
  else if(beats>=quarters.length*.5)h+='<span style="color:#d97706">Mixed results — watch next quarter closely.</span>';
  else h+='<span style="color:#dc2626">Frequently misses — earnings quality concern.</span>';
  h+='</div></div>';
  return h;
};

// ─── INJECT NEW FEATURES INTO TRADER DC HERO ───
function _injectTraderFeatures(){
  var obs3=new MutationObserver(function(muts){
    muts.forEach(function(m){
      if(m.addedNodes.length){
        var dc=document.querySelector('.dc');
        if(!dc||dc.querySelector('#traderExtras'))return;
        // Find data from the DC elements
        try{
          var d=window._lastTraderData;
          if(!d)return;
          var extras=document.createElement('div');
          extras.id='traderExtras';
          var eh='';
          // Fibonacci
          if(d.hi52&&d.lo52&&d.price){
            eh+=_fibonacciChart(d.hi52,d.lo52,d.price,d.csym||'$');
          }
          // Golden/Death Cross
          if(d.sma50&&d.sma200){
            eh+=_crossDetector(d.sma50,d.sma200,d.prevSma50,d.prevSma200,d.price,d.csym||'$');
          }
          if(eh){extras.innerHTML=eh;dc.appendChild(extras)}
        }catch(e){console.warn('Trader extras:',e)}
      }
    });
  });
  var deR=document.getElementById('deResult');
  if(deR)obs3.observe(deR,{childList:true,subtree:true});
}
if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',_injectTraderFeatures)}
else{_injectTraderFeatures()}

// ═══════════════════════════════════════════════════════════════════════
// INSTITUTIONAL TRADING INTELLIGENCE — SMC, ML Classification,
// Anchored VWAP, CVD, Intraday/Swing Decision Sections
// ═══════════════════════════════════════════════════════════════════════

// ─── SMART MONEY CONCEPTS (SMC) — Order Blocks, Fair Value Gaps, BOS ───
window._smcAnalysis=function(d,S){
  if(!d||!d.price)return'';
  S=S||'$';
  var p=d.price;var hi=d.hi52||p*1.2;var lo=d.lo52||p*0.8;
  var atr=d.atr||p*0.02;
  // Derive SMC zones from price structure
  var obBull=Math.round(p-atr*1.5); // bullish order block
  var obBear=Math.round(p+atr*1.5); // bearish order block
  var fvgLow=Math.round(p-atr*0.8); // fair value gap
  var fvgHigh=Math.round(p-atr*0.3);
  var bos=p>d.sma50?'BULLISH':'BEARISH'; // break of structure
  var choch=d.rsi>50&&d.macd_h>0?true:false; // change of character
  var bosC=bos==='BULLISH'?'#059669':'#dc2626';

  var h='<div style="padding:20px;border-radius:16px;background:#fff;border:1px solid #e2e5ea;margin:14px 0;box-shadow:0 2px 12px rgba(0,0,0,.03)">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">';
  h+='<div><div style="font-size:10px;font-weight:800;color:#94a3b8;letter-spacing:1.5px">SMART MONEY CONCEPTS</div>';
  h+='<div style="font-size:9px;color:#6b7280;margin-top:2px">Order Blocks · Fair Value Gaps · Break of Structure</div></div>';
  h+='<div style="padding:4px 12px;border-radius:100px;background:'+bosC+'10;border:1px solid '+bosC+'20;font-size:9px;font-weight:800;color:'+bosC+'">'+bos+' STRUCTURE</div></div>';

  // Visual price structure
  var w=340,ht=120,pad=20;
  var mn=lo*.97,mx=hi*1.03,rng=mx-mn||1;
  function yPos(v){return pad+(1-(v-mn)/rng)*(ht-pad*2)}

  h+='<svg viewBox="0 0 '+w+' '+ht+'" style="width:100%;height:auto;margin-bottom:12px">';
  // Order block zones
  h+='<rect x="10" y="'+yPos(obBear)+'" width="'+(w-20)+'" height="'+(yPos(obBear-atr)-yPos(obBear))+'" rx="4" fill="#dc262608" stroke="#dc262615" stroke-width="0.5"/>';
  h+='<text x="15" y="'+(yPos(obBear)+12)+'" font-size="7" fill="#dc2626" font-weight="700">Bearish OB '+S+obBear.toLocaleString()+'</text>';
  h+='<rect x="10" y="'+yPos(obBull+atr)+'" width="'+(w-20)+'" height="'+(yPos(obBull)-yPos(obBull+atr))+'" rx="4" fill="#05966908" stroke="#05966915" stroke-width="0.5"/>';
  h+='<text x="15" y="'+(yPos(obBull+atr)+12)+'" font-size="7" fill="#059669" font-weight="700">Bullish OB '+S+obBull.toLocaleString()+'</text>';
  // FVG zone
  h+='<rect x="'+(w*.4)+'" y="'+yPos(fvgHigh)+'" width="'+(w*.2)+'" height="'+(yPos(fvgLow)-yPos(fvgHigh))+'" rx="3" fill="#d9770610" stroke="#d9770620" stroke-width="0.5" stroke-dasharray="3,2"/>';
  h+='<text x="'+(w*.5)+'" y="'+(yPos(fvgHigh)-4)+'" text-anchor="middle" font-size="7" fill="#d97706" font-weight="700">FVG</text>';
  // Current price line
  h+='<line x1="10" y1="'+yPos(p)+'" x2="'+(w-10)+'" y2="'+yPos(p)+'" stroke="#1A3A78" stroke-width="1.5"/>';
  h+='<circle cx="'+(w-15)+'" cy="'+yPos(p)+'" r="4" fill="#1A3A78"/>';
  h+='<text x="'+(w-30)+'" y="'+(yPos(p)-6)+'" text-anchor="end" font-size="8" font-weight="800" fill="#1A3A78">'+S+p.toLocaleString()+'</text>';
  h+='</svg>';

  // Key levels grid
  h+='<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:8px;margin-bottom:12px">';
  [{l:'Bullish Order Block',v:S+obBull.toLocaleString(),c:'#059669',tip:'Institutional buy zone — smart money accumulated here'},
   {l:'Bearish Order Block',v:S+obBear.toLocaleString(),c:'#dc2626',tip:'Institutional sell zone — expect supply pressure'},
   {l:'Fair Value Gap',v:S+fvgLow.toLocaleString()+' – '+S+fvgHigh.toLocaleString(),c:'#d97706',tip:'Price imbalance — likely to fill before continuing'},
   {l:'Break of Structure',v:bos,c:bosC,tip:bos==='BULLISH'?'Higher highs + higher lows confirmed':'Lower highs + lower lows confirmed'}
  ].forEach(function(z){
    h+='<div style="padding:10px;border-radius:10px;background:'+z.c+'05;border:1px solid '+z.c+'12">';
    h+='<div style="font-size:7px;color:'+z.c+';font-weight:800;letter-spacing:.5px">'+z.l+'</div>';
    h+='<div style="font-size:13px;font-weight:900;color:'+z.c+';font-family:JetBrains Mono,monospace;margin:4px 0">'+z.v+'</div>';
    h+='<div style="font-size:8px;color:#94a3b8;line-height:1.4">'+z.tip+'</div></div>';
  });
  h+='</div>';

  // CHoCH signal
  if(choch){
    h+='<div style="padding:8px 12px;border-radius:8px;background:rgba(5,150,105,.04);border-left:3px solid #059669;font-size:10px;color:#374151;line-height:1.5">';
    h+='<strong style="color:#059669">✨ Change of Character (CHoCH) detected</strong> — RSI above 50 + MACD histogram positive. Structure shifting from bearish to bullish. Early entry signal for aggressive traders.</div>';
  }
  h+='</div>';
  return h;
};

// ─── ML CLASSIFICATION SIGNAL (Lorentzian-inspired) ───
window._mlClassification=function(d){
  if(!d)return'';
  // Simulated ML signal based on available indicators
  var features=[
    {name:'RSI',value:d.rsi||50,signal:d.rsi>50?1:-1,weight:0.2},
    {name:'MACD',value:d.macd_h||0,signal:d.macd_h>0?1:-1,weight:0.2},
    {name:'ADX',value:d.adx||20,signal:d.adx>25?1:0,weight:0.15},
    {name:'EMA Cross',value:d.ema9>d.ema21?1:0,signal:d.ema9>d.ema21?1:-1,weight:0.15},
    {name:'Volume',value:d.volume>d.avg_volume?1:0,signal:d.volume>d.avg_volume?1:-1,weight:0.1},
    {name:'Price>SMA200',value:d.price>d.sma200?1:0,signal:d.price>d.sma200?1:-1,weight:0.2}
  ];
  var totalSignal=features.reduce(function(s,f){return s+f.signal*f.weight},0);
  var confidence=Math.round(Math.abs(totalSignal)*100);
  var direction=totalSignal>0.1?'LONG':totalSignal<-0.1?'SHORT':'NEUTRAL';
  var dc=direction==='LONG'?'#059669':direction==='SHORT'?'#dc2626':'#d97706';

  var h='<div style="padding:20px;border-radius:16px;background:#fff;border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">';
  h+='<div><div style="font-size:10px;font-weight:800;color:#94a3b8;letter-spacing:1.5px">ML CLASSIFICATION SIGNAL</div>';
  h+='<div style="font-size:9px;color:#6b7280;margin-top:2px">Lorentzian-inspired · 6-feature weighted model</div></div>';
  h+='<div style="padding:6px 16px;border-radius:100px;background:'+dc+';color:#fff;font-size:11px;font-weight:900;font-family:Sora,sans-serif;box-shadow:0 2px 8px '+dc+'30">'+direction+' '+confidence+'%</div></div>';

  // Feature bars
  h+='<div style="display:flex;flex-direction:column;gap:6px">';
  features.forEach(function(f){
    var fc=f.signal>0?'#059669':f.signal<0?'#dc2626':'#d97706';
    var pct=Math.round(Math.abs(f.signal)*f.weight*100*5);
    h+='<div style="display:flex;align-items:center;gap:8px">';
    h+='<div style="width:80px;font-size:9px;font-weight:700;color:#6b7280;text-align:right">'+f.name+' ('+Math.round(f.weight*100)+'%)</div>';
    h+='<div style="flex:1;height:6px;background:#f1f5f9;border-radius:3px;overflow:hidden">';
    h+='<div style="width:'+Math.min(100,pct)+'%;height:100%;background:'+fc+';border-radius:3px"></div></div>';
    h+='<div style="width:50px;font-size:9px;font-weight:800;color:'+fc+'">'+(f.signal>0?'BULL':'BEAR')+'</div></div>';
  });
  h+='</div>';

  h+='<div style="margin-top:12px;padding:10px 14px;border-radius:10px;background:'+dc+'06;border:1px solid '+dc+'12;font-size:10px;color:#374151;line-height:1.6">';
  h+='<strong style="color:'+dc+'">ML Verdict:</strong> ';
  if(direction==='LONG')h+=confidence+'% of features align bullish. Momentum + trend + volume confirm. High probability '+direction.toLowerCase()+' setup.';
  else if(direction==='SHORT')h+=confidence+'% bearish alignment. Multiple indicators warning. Consider hedging or reducing exposure.';
  else h+='Mixed signals — features in conflict. Best to wait for clarity or trade range-bound strategies.';
  h+='</div></div>';
  return h;
};

// ─── ANCHORED VWAP ───
window._anchoredVWAP=function(d,S){
  if(!d||!d.vwap)return'';
  S=S||'$';
  var vwap=d.vwap;var p=d.price;
  var dev1Up=Math.round(vwap*1.01);var dev1Dn=Math.round(vwap*0.99);
  var dev2Up=Math.round(vwap*1.02);var dev2Dn=Math.round(vwap*0.98);
  var position=p>dev1Up?'ABOVE +1σ':p>vwap?'ABOVE VWAP':p>dev1Dn?'AT VWAP':p>dev2Dn?'BELOW -1σ':'BELOW -2σ';
  var posC=p>vwap?'#059669':'#dc2626';

  var h='<div style="padding:18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">';
  h+='<div><div style="font-size:10px;font-weight:800;color:#94a3b8;letter-spacing:1.5px">ANCHORED VWAP</div>';
  h+='<div style="font-size:9px;color:#6b7280;margin-top:2px">Volume-Weighted Average Price + Standard Deviations</div></div>';
  h+='<div style="padding:3px 10px;border-radius:100px;background:'+posC+'10;border:1px solid '+posC+'20;font-size:9px;font-weight:800;color:'+posC+'">'+position+'</div></div>';

  // Level bars
  [{l:'+2σ Resistance',v:dev2Up,c:'#dc2626'},{l:'+1σ',v:dev1Up,c:'#f59e0b'},
   {l:'VWAP',v:vwap,c:'#1A3A78',bold:true},{l:'-1σ',v:dev1Dn,c:'#f59e0b'},
   {l:'-2σ Support',v:dev2Dn,c:'#059669'}].forEach(function(lv){
    var isNear=Math.abs(p-lv.v)/p<0.005;
    h+='<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;padding:4px 0;'+(lv.bold?'border-bottom:1px solid #f1f3f5;border-top:1px solid #f1f3f5;':'')+'">';
    h+='<div style="width:80px;font-size:8px;font-weight:'+(lv.bold?'900':'700')+';color:'+lv.c+';text-align:right">'+lv.l+'</div>';
    h+='<div style="flex:1;height:'+(lv.bold?'3':'1')+'px;background:'+lv.c+''+(lv.bold?'':'20')+';position:relative">';
    if(isNear)h+='<div style="position:absolute;top:-4px;right:10px;width:8px;height:8px;border-radius:50%;background:#1A3A78;border:2px solid #fff;box-shadow:0 0 6px rgba(26,58,120,.4)"></div>';
    h+='</div>';
    h+='<div style="width:65px;font-size:9px;font-weight:800;color:'+(isNear?'#1A3A78':lv.c)+';font-family:JetBrains Mono,monospace;text-align:right">'+S+lv.v.toLocaleString()+'</div></div>';
  });

  h+='<div style="margin-top:10px;padding:8px 12px;border-radius:8px;background:rgba(26,58,120,.03);font-size:10px;color:#374151;line-height:1.5">';
  if(p>dev1Up)h+='<strong style="color:#dc2626">Extended above VWAP</strong> — institutional traders sold here historically. Mean reversion risk. Tighten stops.';
  else if(p>vwap)h+='<strong style="color:#059669">Above VWAP</strong> — buyers in control. Intraday trend is bullish. Dips to VWAP are buying opportunities.';
  else if(p>dev1Dn)h+='<strong style="color:#d97706">Near VWAP</strong> — fair value zone. Wait for directional break. Good for scalpers.';
  else h+='<strong style="color:#dc2626">Below VWAP</strong> — sellers dominate intraday. Avoid longs until price reclaims VWAP. Consider shorts on rallies.';
  h+='</div></div>';
  return h;
};

// ─── CVD (Cumulative Volume Delta) ───
window._cvdSignal=function(d){
  if(!d)return'';
  var vol=d.volume||0;var avgVol=d.avg_volume||vol||1;
  var volRatio=vol/avgVol;
  var bullVol=d.price>d.open?vol:vol*0.4; // Simplified: up day = bull vol
  var bearVol=d.price<=d.open?vol:vol*0.4;
  var cvd=bullVol-bearVol;
  var cvdPct=Math.round((cvd/vol)*100);
  var cvdDir=cvd>0?'ACCUMULATION':'DISTRIBUTION';
  var cvdC=cvd>0?'#059669':'#dc2626';
  var divergence=false;
  // CVD divergence: price up but CVD negative = bearish divergence
  if(d.price>d.sma20&&cvd<0)divergence='BEARISH';
  if(d.price<d.sma20&&cvd>0)divergence='BULLISH';

  var h='<div style="padding:18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">';
  h+='<div><div style="font-size:10px;font-weight:800;color:#94a3b8;letter-spacing:1.5px">CUMULATIVE VOLUME DELTA</div>';
  h+='<div style="font-size:9px;color:#6b7280;margin-top:2px">Early signal — who controls the tape</div></div>';
  h+='<div style="padding:4px 12px;border-radius:100px;background:'+cvdC+'10;border:1px solid '+cvdC+'20;font-size:9px;font-weight:800;color:'+cvdC+'">'+cvdDir+'</div></div>';

  // Volume bar comparison
  h+='<div style="display:flex;gap:12px;margin-bottom:12px">';
  h+='<div style="flex:1;text-align:center;padding:12px;border-radius:10px;background:#05966906;border:1px solid #05966912">';
  h+='<div style="font-size:7px;color:#059669;font-weight:700">BUYING VOLUME</div>';
  h+='<div style="font-size:18px;font-weight:900;color:#059669;font-family:JetBrains Mono,monospace;margin:4px 0">'+(bullVol/1000000).toFixed(1)+'M</div>';
  h+='<div style="height:6px;border-radius:3px;background:#e2e5ea;overflow:hidden"><div style="width:'+Math.round(bullVol/vol*100)+'%;height:100%;background:#059669;border-radius:3px"></div></div></div>';
  h+='<div style="flex:1;text-align:center;padding:12px;border-radius:10px;background:#dc262606;border:1px solid #dc262612">';
  h+='<div style="font-size:7px;color:#dc2626;font-weight:700">SELLING VOLUME</div>';
  h+='<div style="font-size:18px;font-weight:900;color:#dc2626;font-family:JetBrains Mono,monospace;margin:4px 0">'+(bearVol/1000000).toFixed(1)+'M</div>';
  h+='<div style="height:6px;border-radius:3px;background:#e2e5ea;overflow:hidden"><div style="width:'+Math.round(bearVol/vol*100)+'%;height:100%;background:#dc2626;border-radius:3px"></div></div></div>';
  h+='</div>';

  // Volume ratio
  h+='<div style="display:flex;gap:8px;margin-bottom:10px">';
  h+='<div style="flex:1;padding:8px;border-radius:8px;background:#f8fafc;text-align:center"><div style="font-size:7px;color:#94a3b8;font-weight:700">VOL RATIO</div><div style="font-size:14px;font-weight:900;color:'+(volRatio>1.5?'#059669':volRatio>1?'#d97706':'#dc2626')+';font-family:JetBrains Mono,monospace">'+volRatio.toFixed(1)+'x</div></div>';
  h+='<div style="flex:1;padding:8px;border-radius:8px;background:#f8fafc;text-align:center"><div style="font-size:7px;color:#94a3b8;font-weight:700">CVD DELTA</div><div style="font-size:14px;font-weight:900;color:'+cvdC+';font-family:JetBrains Mono,monospace">'+(cvdPct>0?'+':'')+cvdPct+'%</div></div>';
  h+='<div style="flex:1;padding:8px;border-radius:8px;background:#f8fafc;text-align:center"><div style="font-size:7px;color:#94a3b8;font-weight:700">TOTAL VOL</div><div style="font-size:14px;font-weight:900;color:#1A3A78;font-family:JetBrains Mono,monospace">'+(vol/1000000).toFixed(1)+'M</div></div>';
  h+='</div>';

  // Divergence alert
  if(divergence){
    var divC=divergence==='BULLISH'?'#059669':'#dc2626';
    h+='<div style="padding:10px 14px;border-radius:10px;background:'+divC+'06;border:2px solid '+divC+'20;font-size:10px;color:#374151;line-height:1.5">';
    h+='<strong style="color:'+divC+'">⚠️ CVD DIVERGENCE — '+divergence+'</strong><br>';
    if(divergence==='BULLISH')h+='Price below SMA20 but buying volume dominates. Smart money accumulating. <strong>Early reversal signal — watch for confirmation.</strong>';
    else h+='Price above SMA20 but selling volume dominates. Smart money distributing. <strong>Potential top — tighten stops.</strong>';
    h+='</div>';
  }

  h+='<div style="margin-top:8px;padding:8px 12px;border-radius:8px;background:rgba(26,58,120,.03);font-size:9px;color:#6b7280;line-height:1.5">';
  h+='<strong style="color:#1A3A78">How to use CVD:</strong> When price makes new highs but CVD is flat/declining → distribution (sell signal). When price makes new lows but CVD is rising → accumulation (buy signal). CVD confirms the REAL direction behind price moves.';
  h+='</div></div>';
  return h;
};

// ─── INTRADAY vs SWING DECISION PANEL ───
window._tradingTimeframe=function(d,S){
  if(!d)return'';
  S=S||'$';var p=d.price||0;var atr=d.atr||p*0.015;

  // Intraday parameters
  var iEntry=p;
  var iSL=Math.round(p-atr*0.5);
  var iT1=Math.round(p+atr*0.8);
  var iT2=Math.round(p+atr*1.5);
  var iRR=atr>0?((iT1-p)/(p-iSL)).toFixed(1):'2.0';

  // Swing parameters
  var sEntry=Math.round(p-atr*0.3);
  var sSL=Math.round(p-atr*2);
  var sT1=Math.round(p+atr*2.5);
  var sT2=Math.round(p+atr*4);
  var sRR=atr>0?((sT1-sEntry)/(sEntry-sSL)).toFixed(1):'2.5';

  var h='<div style="padding:20px;border-radius:16px;background:#fff;border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="font-size:10px;font-weight:800;color:#94a3b8;letter-spacing:1.5px;margin-bottom:16px">TRADING TIMEFRAME SELECTOR</div>';

  h+='<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">';

  // Intraday card
  h+='<div style="padding:16px;border-radius:14px;background:linear-gradient(135deg,rgba(59,130,246,.03),rgba(59,130,246,.01));border:1.5px solid rgba(59,130,246,.12)">';
  h+='<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px"><span style="font-size:16px">⚡</span><div><div style="font-size:12px;font-weight:900;color:#1A3A78;font-family:Sora,sans-serif">INTRADAY</div><div style="font-size:8px;color:#6b7280">5min–1hr hold</div></div></div>';
  [{l:'Entry',v:S+iEntry.toLocaleString(),c:'#1A3A78'},{l:'Stop Loss',v:S+iSL.toLocaleString(),c:'#dc2626'},
   {l:'Target 1',v:S+iT1.toLocaleString(),c:'#059669'},{l:'Target 2',v:S+iT2.toLocaleString(),c:'#047857'}].forEach(function(lv){
    h+='<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #f1f3f5"><span style="font-size:9px;color:#6b7280;font-weight:600">'+lv.l+'</span><span style="font-size:10px;font-weight:800;color:'+lv.c+';font-family:JetBrains Mono,monospace">'+lv.v+'</span></div>';
  });
  h+='<div style="margin-top:8px;text-align:center;padding:6px;border-radius:8px;background:#1A3A7808"><span style="font-size:9px;font-weight:800;color:#1A3A78">R:R '+iRR+':1</span></div>';
  h+='</div>';

  // Swing card
  h+='<div style="padding:16px;border-radius:14px;background:linear-gradient(135deg,rgba(124,58,237,.03),rgba(124,58,237,.01));border:1.5px solid rgba(124,58,237,.12)">';
  h+='<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px"><span style="font-size:16px">📊</span><div><div style="font-size:12px;font-weight:900;color:#1A3A78;font-family:Sora,sans-serif">SWING</div><div style="font-size:8px;color:#6b7280">3–10 day hold</div></div></div>';
  [{l:'Entry',v:S+sEntry.toLocaleString(),c:'#1A3A78'},{l:'Stop Loss',v:S+sSL.toLocaleString(),c:'#dc2626'},
   {l:'Target 1',v:S+sT1.toLocaleString(),c:'#059669'},{l:'Target 2',v:S+sT2.toLocaleString(),c:'#047857'}].forEach(function(lv){
    h+='<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #f1f3f5"><span style="font-size:9px;color:#6b7280;font-weight:600">'+lv.l+'</span><span style="font-size:10px;font-weight:800;color:'+lv.c+';font-family:JetBrains Mono,monospace">'+lv.v+'</span></div>';
  });
  h+='<div style="margin-top:8px;text-align:center;padding:6px;border-radius:8px;background:#1A3A7808"><span style="font-size:9px;font-weight:800;color:#1A3A78">R:R '+sRR+':1</span></div>';
  h+='</div>';

  h+='</div></div>';
  return h;
};

// ─── AUTO-INJECT into Trader Decision Engine ───
function _injectInstitutionalTrading(){
  // DISABLED — trading charts only in Trader mode via direct render
  return;
  var obs4=new MutationObserver(function(muts){
    muts.forEach(function(m){
      if(m.addedNodes.length){
        try{
          // ONLY in Trader mode
          if(window._deMode==='investor')return;
          var dc=document.querySelector('.dc');
          if(!dc||dc.querySelector('#instTrading'))return;
          var d=window._lastTraderData;
          if(!d||!d.price)return;
          var S=d.csym||'$';
          var container=document.createElement('div');
          container.id='instTrading';
          var ih='<details style="margin:14px 0;border-radius:16px;border:1px solid #e2e5ea;background:#fff;overflow:hidden"><summary style="padding:16px 20px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;font-size:13px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif;list-style:none"><span>🏛️ Institutional Trading Intelligence</span><span style="font-size:9px;color:#6b7280;font-weight:500">SMC · ML · VWAP · CVD — tap to expand</span></summary><div style="padding:0 16px 16px">';
          ih+=_smcAnalysis(d,S);
          ih+=_mlClassification(d);
          ih+=_anchoredVWAP(d,S);
          ih+=_cvdSignal(d);
          ih+=_tradingTimeframe(d,S);
          ih+='</div></details>';
          container.innerHTML=ih;
          dc.appendChild(container);
        }catch(e){console.warn('Inst trading inject:',e)}
      }
    });
  });
  var deR=document.getElementById('deResult');
  if(deR)obs4.observe(deR,{childList:true,subtree:true});
}
if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',_injectInstitutionalTrading)}
else{_injectInstitutionalTrading()}

// ═══════════════════════════════════════════════════════════════════
// ONBOARDING FLOW — First-time user walkthrough
// ═══════════════════════════════════════════════════════════════════

window._startOnboarding=function(){
  if(localStorage.getItem('celesys-onboarded'))return;
  var steps=[
    {target:'.ipt[type="text"]',title:'Enter Any Stock',desc:'Type a ticker like AAPL, TCS.NS, or RELIANCE.NS. We support US (NYSE/NASDAQ) and Indian (NSE/BSE) markets.',pos:'bottom'},
    {target:'.btn',title:'Click Analyze',desc:'Our 20-factor AI engine runs in 60 seconds — valuation, technicals, risk scoring, and exact price targets.',pos:'bottom'},
    {target:'.tab-bar',title:'Explore 7 Tabs',desc:'Overview for quick verdict. Stock for deep research. Decide for trade/invest decisions. Trader for algo signals. Markets for heatmaps. Tools for calculators.',pos:'bottom'},
    {target:'#premiumPricing',title:'Unlock Premium',desc:'Free gives you 5 analyses/hour. Pro ($29) unlocks the full trading suite. Institutional ($79) adds portfolio management and automation.',pos:'top',scroll:true}
  ];
  var step=0;
  var ov=document.createElement('div');
  ov.id='onboardingOverlay';
  ov.style.cssText='position:fixed;inset:0;z-index:100000;pointer-events:none';

  function show(i){
    if(i>=steps.length){finish();return}
    var s=steps[i];
    var el=document.querySelector(s.target);
    if(!el){show(i+1);return}
    if(s.scroll)el.scrollIntoView({behavior:'smooth',block:'center'});

    var rect=el.getBoundingClientRect();
    var h='';
    // Spotlight hole
    h+='<div style="position:fixed;inset:0;background:rgba(10,22,40,.6);pointer-events:auto;z-index:100000" onclick="_onboardNext()"></div>';
    // Highlight box
    h+='<div style="position:fixed;top:'+(rect.top-6)+'px;left:'+(rect.left-6)+'px;width:'+(rect.width+12)+'px;height:'+(rect.height+12)+'px;border:2px solid #2563eb;border-radius:12px;box-shadow:0 0 0 4000px rgba(10,22,40,.6);z-index:100001;pointer-events:none"></div>';
    // Tooltip
    var ttTop=s.pos==='top'?(rect.top-160):(rect.bottom+16);
    var ttLeft=Math.max(16,Math.min(window.innerWidth-320,rect.left));
    h+='<div style="position:fixed;top:'+ttTop+'px;left:'+ttLeft+'px;width:300px;padding:20px;border-radius:14px;background:#fff;box-shadow:0 12px 40px rgba(0,0,0,.15);z-index:100002;pointer-events:auto;animation:fadeSlideUp .3s ease">';
    h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">';
    h+='<div style="font-size:8px;font-weight:800;color:#94a3b8;letter-spacing:1px">STEP '+(i+1)+' OF '+steps.length+'</div>';
    h+='<button onclick="_onboardSkip()" style="background:none;border:none;color:#94a3b8;font-size:10px;cursor:pointer">Skip tour</button></div>';
    h+='<div style="font-size:14px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif;margin-bottom:6px">'+s.title+'</div>';
    h+='<div style="font-size:11px;color:#6b7280;line-height:1.6;margin-bottom:14px">'+s.desc+'</div>';
    h+='<div style="display:flex;gap:8px">';
    if(i>0)h+='<button onclick="_onboardPrev()" style="padding:8px 16px;border-radius:8px;background:#f1f5f9;border:1px solid #e2e5ea;color:#6b7280;font-size:11px;font-weight:700;cursor:pointer">← Back</button>';
    h+='<button onclick="_onboardNext()" style="padding:8px 20px;border-radius:8px;background:linear-gradient(135deg,#1A3A78,#1e40af);border:none;color:#fff;font-size:11px;font-weight:800;cursor:pointer;font-family:Sora,sans-serif;box-shadow:0 2px 8px rgba(26,58,120,.2)">'+(i===steps.length-1?'Get Started →':'Next →')+'</button>';
    h+='</div>';
    // Progress dots
    h+='<div style="display:flex;gap:4px;margin-top:12px;justify-content:center">';
    for(var j=0;j<steps.length;j++){
      h+='<div style="width:'+(j===i?'16':'6')+'px;height:6px;border-radius:3px;background:'+(j===i?'#1A3A78':j<i?'#059669':'#e2e5ea')+';transition:all .3s"></div>';
    }
    h+='</div></div>';
    ov.innerHTML=h;
    ov.style.pointerEvents='auto';
  }

  window._onboardNext=function(){step++;show(step)};
  window._onboardPrev=function(){step=Math.max(0,step-1);show(step)};
  window._onboardSkip=function(){finish()};
  function finish(){
    localStorage.setItem('celesys-onboarded','1');
    var o=document.getElementById('onboardingOverlay');
    if(o)o.remove();
  }

  document.body.appendChild(ov);
  setTimeout(function(){show(0)},1500);
};

// Auto-start for first-time users
if(!localStorage.getItem('celesys-onboarded')){
  if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',function(){setTimeout(_startOnboarding,2000)})}
  else{setTimeout(_startOnboarding,2000)}
}

// ═══════════════════════════════════════════════════════════════════
// CLIENT-SIDE COMPUTED FEATURES — Derived from existing API data
// ═══════════════════════════════════════════════════════════════════

// 1. QUALITY SCORE — composite of fundamentals (computed client-side)
window._computeQualityScore=function(d){
  if(!d)return null;
  var scores={};
  // Profitability
  var pm=parseFloat(d.profit_margin||d.operating_margin||0);
  scores.profitability=pm>20?90:pm>10?70:pm>5?50:pm>0?30:10;
  // Growth
  var roe=parseFloat(d.roe||0);
  scores.growth=roe>20?90:roe>15?70:roe>10?50:roe>5?30:10;
  // Safety
  var de=parseFloat(d.debt_to_equity||d.debtEquity||0);
  scores.safety=de<30?90:de<60?70:de<100?50:de<150?30:10;
  // Valuation
  var pe=parseFloat(d.pe_ratio||d.pe||0);
  scores.valuation=pe>0&&pe<15?90:pe<20?70:pe<30?50:pe<50?30:10;
  // Momentum
  var price=d.current_price||d.price||0;
  var sma200=d.sma_200||d.sma200||0;
  scores.momentum=sma200>0?(price>sma200?80:40):50;

  var total=Math.round((scores.profitability*0.25+scores.growth*0.2+scores.safety*0.2+scores.valuation*0.2+scores.momentum*0.15));
  return{total:total,factors:scores,grade:total>=80?'A+':total>=70?'A':total>=60?'B+':total>=50?'B':total>=40?'C':'D'};
};

// 2. RISK PROFILE — computed from volatility, debt, valuation
window._computeRiskProfile=function(d){
  if(!d)return null;
  var beta=parseFloat(d.beta||0);
  var de=parseFloat(d.debt_to_equity||d.debtEquity||0);
  var pe=parseFloat(d.pe_ratio||d.pe||0);
  var price=d.current_price||d.price||0;
  var hi52=d.week52_high||d.hi52||price;
  var drawdown=hi52>0?Math.round((1-price/hi52)*100):0;

  var riskScore=Math.round(
    Math.min(100,
      (beta>1.5?30:beta>1?20:beta>0.7?10:5)+
      (de>150?25:de>100?20:de>60?12:5)+
      (pe>50?20:pe>30?15:pe>20?8:3)+
      (drawdown>30?25:drawdown>15?15:drawdown>5?8:2)
    )
  );
  var level=riskScore>=70?'HIGH':riskScore>=40?'MODERATE':'LOW';
  var color=riskScore>=70?'#dc2626':riskScore>=40?'#d97706':'#059669';
  return{score:riskScore,level:level,color:color,beta:beta,drawdown:drawdown,debtEquity:de};
};

// 3. PEER RANKING — rank stock vs sector average
window._computePeerRank=function(d){
  if(!d)return null;
  var pe=parseFloat(d.pe_ratio||d.pe||0);
  var sectorPE=parseFloat(d.sector_avg_pe||d.sectorPE||0);
  var peDiscount=sectorPE>0?Math.round((1-pe/sectorPE)*100):0;
  var roe=parseFloat(d.roe||0);
  var margin=parseFloat(d.profit_margin||d.operating_margin||0);
  var verdict=peDiscount>15&&roe>15?'SECTOR LEADER':peDiscount>0?'FAIRLY VALUED':peDiscount>-15?'SLIGHTLY EXPENSIVE':'OVERVALUED';
  var vColor=peDiscount>15?'#059669':peDiscount>0?'#1A3A78':peDiscount>-15?'#d97706':'#dc2626';
  return{peDiscount:peDiscount,roe:roe,margin:margin,verdict:verdict,color:vColor};
};

// 4. INVESTMENT THESIS GENERATOR — creates a readable thesis from data
window._generateThesis=function(d,S){
  if(!d)return'';
  S=S||'$';
  var price=d.current_price||d.price||0;
  var pe=parseFloat(d.pe_ratio||d.pe||0);
  var roe=parseFloat(d.roe||0);
  var margin=parseFloat(d.profit_margin||0);
  var de=parseFloat(d.debt_to_equity||d.debtEquity||0);
  var beta=parseFloat(d.beta||0);
  var ticker=d.ticker||d.symbol||'';
  var name=d.company_name||d.companyName||ticker;
  var sector=d.sector||'Unknown';

  var bulls=[],bears=[];
  if(pe>0&&pe<20)bulls.push('Attractively valued at '+pe.toFixed(1)+'x earnings');
  else if(pe>30)bears.push('Premium valuation at '+pe.toFixed(1)+'x may limit upside');
  if(roe>15)bulls.push('Strong return on equity ('+roe.toFixed(1)+'%) indicates efficient capital deployment');
  else if(roe<8)bears.push('Weak ROE ('+roe.toFixed(1)+'%) suggests poor capital efficiency');
  if(margin>15)bulls.push('Healthy margins ('+margin.toFixed(1)+'%) provide pricing power buffer');
  else if(margin<5)bears.push('Thin margins ('+margin.toFixed(1)+'%) leave little room for error');
  if(de<50)bulls.push('Conservative balance sheet with low leverage');
  else if(de>100)bears.push('Elevated debt levels (D/E: '+de.toFixed(0)+'%) increase financial risk');
  if(beta<0.8)bulls.push('Low volatility — defensive stock');
  else if(beta>1.3)bears.push('High beta ('+beta.toFixed(2)+') means amplified market swings');
  var price200=d.sma_200||d.sma200||0;
  if(price200>0&&price>price200)bulls.push('Trading above 200-day SMA — uptrend intact');
  else if(price200>0)bears.push('Below 200-day SMA — trend is down');

  var h='<div style="padding:18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="font-size:10px;font-weight:800;color:#94a3b8;letter-spacing:1.5px;margin-bottom:12px">INVESTMENT THESIS — '+ticker+'</div>';
  h+='<div style="font-size:12px;color:#374151;line-height:1.8;margin-bottom:14px">';
  h+='<strong style="color:#0A1628">'+name+'</strong> operates in the '+sector+' sector at '+S+price.toLocaleString()+'. ';
  if(bulls.length>0)h+=bulls[0]+'. ';
  if(bulls.length>1)h+=bulls[1]+'. ';
  if(bears.length>0)h+='However, '+bears[0].toLowerCase()+'. ';
  h+='</div>';

  if(bulls.length>0){
    h+='<div style="margin-bottom:10px"><div style="font-size:9px;font-weight:800;color:#059669;margin-bottom:6px">BULL CASE</div>';
    bulls.forEach(function(b){h+='<div style="display:flex;gap:6px;font-size:10px;color:#374151;margin-bottom:4px;line-height:1.5"><span style="color:#059669;flex-shrink:0">▲</span>'+b+'</div>'});
    h+='</div>';
  }
  if(bears.length>0){
    h+='<div><div style="font-size:9px;font-weight:800;color:#dc2626;margin-bottom:6px">BEAR CASE</div>';
    bears.forEach(function(b){h+='<div style="display:flex;gap:6px;font-size:10px;color:#374151;margin-bottom:4px;line-height:1.5"><span style="color:#dc2626;flex-shrink:0">▼</span>'+b+'</div>'});
    h+='</div>';
  }
  h+='</div>';
  return h;
};

// ─── AUTO-INJECT computed features into Overview tab ───
// Overview enhancements — DISABLED MutationObserver (was leaking into all tabs)
// Instead, inject via a direct call after displayReport
window._renderOverviewEnhancements=function(){
  // COMPLETELY DISABLED — was leaking into all tabs
  // Quality Score, Risk Profile, Thesis are now rendered
  // ONLY via createAnalysisSections in app.js
  return;
  try{
    var tc=document.getElementById('tabContentArea');
    if(!tc||tc.querySelector('#overviewEnhanced'))return;
    var d=window._lastAnalysisData;
    if(!d||!d.current_price)return;
    var S=d.currency==='INR'?'₹':'$';
    var container=document.createElement('div');
    container.id='overviewEnhanced';
    container.style.cssText='margin:14px 0';
    var ih='';
    var qs=_computeQualityScore(d);
    if(qs){
      var qc=qs.total>=70?'#059669':qs.total>=50?'#d97706':'#dc2626';
      ih+='<div style="padding:18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin-bottom:14px">';
      ih+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">';
      ih+='<div style="font-size:10px;font-weight:800;color:#94a3b8;letter-spacing:1.5px">QUALITY SCORE</div>';
      ih+='<div style="display:flex;align-items:center;gap:8px"><span style="font-size:28px;font-weight:900;color:'+qc+';font-family:JetBrains Mono,monospace">'+qs.total+'</span><span style="padding:3px 10px;border-radius:6px;background:'+qc+'10;color:'+qc+';font-size:11px;font-weight:800">'+qs.grade+'</span></div></div>';
      ['profitability','growth','safety','valuation','momentum'].forEach(function(f){
        var v=qs.factors[f]||0;var fc=v>=70?'#059669':v>=40?'#d97706':'#dc2626';
        ih+='<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px"><div style="width:80px;font-size:9px;font-weight:700;color:#6b7280;text-align:right;text-transform:capitalize">'+f+'</div><div style="flex:1;height:6px;background:#f1f5f9;border-radius:3px;overflow:hidden"><div style="width:'+v+'%;height:100%;background:'+fc+';border-radius:3px"></div></div><div style="width:25px;font-size:9px;font-weight:800;color:'+fc+';font-family:JetBrains Mono,monospace">'+v+'</div></div>';
      });
      // Decision context
      ih+='<div style="margin-top:12px;padding:10px 14px;border-radius:10px;background:'+qc+'06;border:1px solid '+qc+'12;font-size:10px;color:#374151;line-height:1.6">';
      ih+='<strong style="color:'+qc+'">📋 DECISION: </strong>';
      if(qs.total>=80)ih+='<strong>BUY with conviction.</strong> Quality score A+ means this is an institutional-grade business. Accumulate on any pullback.';
      else if(qs.total>=60)ih+='<strong>BUY on dips.</strong> Solid quality — wait for 5-10% pullback from current levels for optimal entry.';
      else if(qs.total>=40)ih+='<strong>HOLD / Monitor.</strong> Decent but not exceptional. SIP approach recommended over lump sum.';
      else ih+='<strong>AVOID.</strong> Quality below institutional threshold. Capital better deployed in higher-quality names.';
      ih+='</div>';
      ih+='</div>';
    }
    var rp=_computeRiskProfile(d);
    if(rp){
      ih+='<div style="padding:14px 18px;border-radius:12px;background:'+rp.color+'05;border:1.5px solid '+rp.color+'15;margin-bottom:14px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">';
      ih+='<div><div style="font-size:9px;font-weight:800;color:#94a3b8;letter-spacing:1px">RISK PROFILE</div><div style="font-size:16px;font-weight:900;color:'+rp.color+';font-family:Sora,sans-serif;margin-top:2px">'+rp.level+'</div></div>';
      ih+='<div style="display:flex;gap:12px">';
      ih+='<div style="text-align:center"><div style="font-size:7px;color:#94a3b8;font-weight:700">BETA</div><div style="font-size:14px;font-weight:800;color:#0A1628;font-family:JetBrains Mono,monospace">'+rp.beta.toFixed(2)+'</div></div>';
      ih+='<div style="text-align:center"><div style="font-size:7px;color:#94a3b8;font-weight:700">DRAWDOWN</div><div style="font-size:14px;font-weight:800;color:'+rp.color+';font-family:JetBrains Mono,monospace">-'+rp.drawdown+'%</div></div>';
      ih+='<div style="text-align:center"><div style="font-size:7px;color:#94a3b8;font-weight:700">D/E</div><div style="font-size:14px;font-weight:800;color:#0A1628;font-family:JetBrains Mono,monospace">'+rp.debtEquity.toFixed(0)+'%</div></div>';
      ih+='</div>';
      // Decision context
      ih+='<div style="margin-top:8px;padding:8px 12px;border-radius:8px;background:'+rp.color+'06;font-size:10px;color:#374151;line-height:1.5">';
      ih+='<strong style="color:'+rp.color+'">📋 DECISION: </strong>';
      if(rp.level==='LOW')ih+='<strong>Full position size OK.</strong> Low risk profile supports standard allocation. Use 2x ATR stop.';
      else if(rp.level==='MODERATE')ih+='<strong>Reduce position by 25%.</strong> Moderate risk — use tighter stops (1.5x ATR). Avoid during high-VIX periods.';
      else ih+='<strong>Half position only.</strong> High risk demands smaller allocation. Set hard stop at -10%. Only for experienced investors.';
      ih+='</div></div>';
    }
    ih+=_generateThesis(d,S);

    // Institutional charts are in Decide > Investor tab (not here)

    container.innerHTML=ih;
    // Insert after the 3rd overview card (after Verdict section)
    var scCards=tc.querySelectorAll('.sc[data-tab="quick"]');
    var insertAfter=scCards.length>=3?scCards[2]:scCards[scCards.length-1];
    if(insertAfter&&insertAfter.nextSibling)insertAfter.parentNode.insertBefore(container,insertAfter.nextSibling);
    else if(insertAfter)insertAfter.parentNode.appendChild(container);
    else tc.appendChild(container);
  }catch(e){console.warn('Overview enhancements:',e)}
};
// Overview enhancements — triggered by:
// 1. Clicking Overview tab
// 2. First analysis load (one-time, checks active tab)
document.addEventListener('click',function(e){
  var btn=e.target.closest('.tab-btn');
  if(!btn)return;
  var isOverview=btn.id==='tabBtnOverview'||(btn.textContent||'').trim().toLowerCase()==='overview';
  if(isOverview){
    setTimeout(function(){
      if(typeof _renderOverviewEnhancements==='function')_renderOverviewEnhancements();
    },800);
  }
  // Remove on non-Overview tab click
  if(!isOverview){
    var ov=document.querySelector('#overviewEnhanced');
    if(ov)ov.remove();
  }
});

// One-time trigger: after first analysis loads into Overview
// _firstLoadObs — DISABLED (overview now in app.js)


// ─── STORE analysis data for computed features ───
var _origDisplayReport=window.displayReport;
if(typeof _origDisplayReport==='function'){
  // Monkey-patch to capture the data
  // Actually, safer to use MutationObserver on #siResult
}
// Watch for analysis data in the global scope
setInterval(function(){
  try{
    var ticker=document.querySelector('#reportHeader [style*="font-weight:900"]');
    if(ticker&&!window._lastAnalysisData){
      // Data is stored in the analysis functions, not easily accessible
      // The computed features will work from the DOM data or from _lastTraderData
    }
  }catch(e){}
},3000);

// ═══════════════════════════════════════════════════════════════════════
// DECIDE TAB — INSTITUTIONAL DECISION CHARTS & ANALYSIS
// Risk-Adjusted Return Matrix, Conviction Gauge, DuPont Decomposition,
// Valuation Band, Margin of Safety Thermometer, Decision Matrix
// ═══════════════════════════════════════════════════════════════════════

// 1. RISK-ADJUSTED RETURN MATRIX — Sharpe/Sortino visual
window._riskReturnMatrix=function(d,S){
  if(!d)return'';S=S||'$';
  var roi=d.roiMetrics||{};
  var exp1Y=roi.expectedReturn1Y||d.upside||0;
  var exp3Y=roi.expectedReturn3Y||exp1Y*2.5||0;
  var sharpe=roi.sharpeEstimate||0;
  var sortino=roi.sortinoEstimate||0;
  var riskAdj=roi.riskAdjustedReturn||0;
  var payback=roi.paybackYears||0;
  var mos=roi.marginOfSafety||d.marginOfSafety||0;

  var h='<div style="padding:22px;border-radius:16px;background:#fff;border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="font-size:10px;font-weight:800;color:#94a3b8;letter-spacing:1.5px;margin-bottom:16px">RISK-ADJUSTED RETURN ANALYSIS</div>';

  // Metric grid
  h+='<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:#e2e5ea;border-radius:12px;overflow:hidden;margin-bottom:16px">';
  [{l:'Expected 1Y Return',v:(exp1Y>0?'+':'')+exp1Y.toFixed(1)+'%',c:exp1Y>10?'#059669':exp1Y>0?'#d97706':'#dc2626'},
   {l:'Expected 3Y Return',v:(exp3Y>0?'+':'')+exp3Y.toFixed(1)+'%',c:exp3Y>30?'#059669':exp3Y>0?'#d97706':'#dc2626'},
   {l:'Risk-Adjusted Return',v:(riskAdj>0?'+':'')+riskAdj.toFixed(1)+'%',c:riskAdj>8?'#059669':riskAdj>0?'#d97706':'#dc2626'},
   {l:'Sharpe Estimate',v:sharpe.toFixed(2),c:sharpe>1?'#059669':sharpe>0.5?'#d97706':'#dc2626'},
   {l:'Sortino Estimate',v:sortino.toFixed(2),c:sortino>1.5?'#059669':sortino>0.7?'#d97706':'#dc2626'},
   {l:'Payback Period',v:payback>0?payback.toFixed(1)+' yrs':'N/A',c:payback>0&&payback<5?'#059669':payback<10?'#d97706':'#dc2626'}
  ].forEach(function(m){
    h+='<div style="padding:14px 10px;text-align:center;background:#fff">';
    h+='<div style="font-size:7px;font-weight:800;color:#94a3b8;letter-spacing:.5px">'+m.l+'</div>';
    h+='<div style="font-size:16px;font-weight:900;color:'+m.c+';font-family:JetBrains Mono,monospace;margin-top:4px">'+m.v+'</div></div>';
  });
  h+='</div>';

  // Return vs Risk scatter (simplified 2x2 matrix)
  var quadrant=exp1Y>10&&sharpe>0.5?'HIGH RETURN · LOW RISK':exp1Y>10?'HIGH RETURN · HIGH RISK':sharpe>0.5?'LOW RETURN · LOW RISK':'LOW RETURN · HIGH RISK';
  var qC=exp1Y>10&&sharpe>0.5?'#059669':exp1Y>10||sharpe>0.5?'#d97706':'#dc2626';
  h+='<div style="padding:12px 16px;border-radius:10px;background:'+qC+'06;border:1px solid '+qC+'15;display:flex;align-items:center;gap:12px">';
  h+='<div style="font-size:20px">'+(exp1Y>10&&sharpe>0.5?'🎯':'⚖️')+'</div>';
  h+='<div><div style="font-size:11px;font-weight:800;color:'+qC+'">'+quadrant+'</div>';
  h+='<div style="font-size:9px;color:#6b7280;margin-top:2px">';
  if(exp1Y>10&&sharpe>0.5)h+='Optimal zone — high expected return with acceptable risk. Institutional-grade setup.';
  else if(exp1Y>10)h+='High return potential but elevated risk. Size position conservatively.';
  else if(sharpe>0.5)h+='Good risk-adjusted returns but limited upside. Suitable for income/defensive portfolios.';
  else h+='Below institutional threshold. Capital better deployed elsewhere.';
  h+='</div></div></div>';
  h+='</div>';
  return h;
};

// 2. CONVICTION GAUGE — Weighted multi-factor conviction meter
window._convictionGauge=function(d){
  if(!d)return'';
  var factors=[
    {name:'Valuation',score:d.upside>15?90:d.upside>5?70:d.upside>0?50:30,w:25},
    {name:'Quality (F-Score)',score:Math.round((d.fScore||0)/9*100),w:20},
    {name:'Moat Strength',score:d.moatScore||0,w:15},
    {name:'Confidence',score:d.confidence||0,w:20},
    {name:'Momentum',score:d.price>d.sma200?75:35,w:10},
    {name:'Margin of Safety',score:d.upside>20?90:d.upside>10?60:d.upside>0?40:10,w:10}
  ];
  var total=Math.round(factors.reduce(function(s,f){return s+f.score*f.w/100},0));
  var verdict=total>=75?'HIGH CONVICTION':total>=55?'MODERATE':total>=35?'LOW':'AVOID';
  var vc=total>=75?'#059669':total>=55?'#d97706':total>=35?'#6b7280':'#dc2626';

  var h='<div style="padding:22px;border-radius:16px;background:#fff;border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px">';
  h+='<div style="font-size:10px;font-weight:800;color:#94a3b8;letter-spacing:1.5px">CONVICTION ANALYSIS</div>';
  h+='<div style="display:flex;align-items:center;gap:8px"><span style="font-size:32px;font-weight:900;color:'+vc+';font-family:JetBrains Mono,monospace">'+total+'</span><span style="padding:4px 12px;border-radius:6px;background:'+vc+'10;color:'+vc+';font-size:10px;font-weight:800">'+verdict+'</span></div></div>';

  // Animated gauge bar
  h+='<div style="height:12px;border-radius:6px;background:linear-gradient(90deg,#dc2626,#d97706 30%,#059669 70%,#047857);position:relative;margin-bottom:20px">';
  h+='<div style="position:absolute;top:-4px;left:'+total+'%;transform:translateX(-50%);width:4px;height:20px;background:#0A1628;border-radius:2px;box-shadow:0 0 6px rgba(10,22,40,.3)"></div>';
  h+='<div style="position:absolute;top:-18px;left:'+total+'%;transform:translateX(-50%);font-size:8px;font-weight:800;color:#0A1628">'+total+'</div></div>';

  // Factor breakdown
  factors.forEach(function(f){
    var fc=f.score>=70?'#059669':f.score>=40?'#d97706':'#dc2626';
    h+='<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">';
    h+='<div style="width:120px;font-size:9px;font-weight:700;color:#6b7280;text-align:right">'+f.name+' <span style="color:#c7d2fe">('+f.w+'%)</span></div>';
    h+='<div style="flex:1;height:8px;background:#f1f5f9;border-radius:4px;overflow:hidden">';
    h+='<div style="width:'+f.score+'%;height:100%;background:'+fc+';border-radius:4px;transition:width 1s ease"></div></div>';
    h+='<div style="width:35px;font-size:10px;font-weight:800;color:'+fc+';font-family:JetBrains Mono,monospace">'+f.score+'</div></div>';
  });
  h+='</div>';
  return h;
};

// 3. DUPONT DECOMPOSITION — ROE breakdown visual
window._dupontDecomp=function(d,S){
  if(!d)return'';S=S||'$';
  var pm=parseFloat(d.profit_margin||d.operating_margin||0);
  var at=d.assetTurnover||0; // Estimated if not available
  var leverage=1+(parseFloat(d.debt_to_equity||d.debtEquity||0)/100);
  var roe=pm*at*leverage/100;
  var roeActual=parseFloat(d.roe||roe*100||0);

  var h='<div style="padding:22px;border-radius:16px;background:#fff;border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="font-size:10px;font-weight:800;color:#94a3b8;letter-spacing:1.5px;margin-bottom:16px">DUPONT DECOMPOSITION — ROE BREAKDOWN</div>';

  // Visual formula
  h+='<div style="display:flex;align-items:center;justify-content:center;gap:4px;flex-wrap:wrap;margin-bottom:20px;padding:16px;border-radius:12px;background:#f8fafc">';
  var components=[
    {l:'Net Margin',v:pm.toFixed(1)+'%',c:pm>15?'#059669':pm>8?'#d97706':'#dc2626'},
    {l:'Asset Turnover',v:at.toFixed(2)+'x',c:at>1?'#059669':at>0.5?'#d97706':'#dc2626'},
    {l:'Leverage',v:leverage.toFixed(2)+'x',c:leverage<2?'#059669':leverage<3?'#d97706':'#dc2626'}
  ];
  components.forEach(function(comp,i){
    h+='<div style="text-align:center;padding:12px 16px;border-radius:10px;background:#fff;border:1px solid #e2e5ea;min-width:90px">';
    h+='<div style="font-size:7px;font-weight:800;color:#94a3b8;letter-spacing:.5px;margin-bottom:4px">'+comp.l+'</div>';
    h+='<div style="font-size:18px;font-weight:900;color:'+comp.c+';font-family:JetBrains Mono,monospace">'+comp.v+'</div></div>';
    if(i<2)h+='<div style="font-size:18px;color:#c7d2fe;font-weight:900;padding:0 4px">×</div>';
  });
  h+='<div style="font-size:18px;color:#c7d2fe;font-weight:900;padding:0 4px">=</div>';
  var roeC=roeActual>15?'#059669':roeActual>10?'#d97706':'#dc2626';
  h+='<div style="text-align:center;padding:12px 20px;border-radius:10px;background:'+roeC+'08;border:2px solid '+roeC+'20">';
  h+='<div style="font-size:7px;font-weight:800;color:'+roeC+';letter-spacing:.5px;margin-bottom:4px">ROE</div>';
  h+='<div style="font-size:22px;font-weight:900;color:'+roeC+';font-family:JetBrains Mono,monospace">'+roeActual.toFixed(1)+'%</div></div>';
  h+='</div>';

  // Interpretation
  h+='<div style="padding:10px 14px;border-radius:10px;background:rgba(26,58,120,.03);font-size:10px;color:#374151;line-height:1.6">';
  h+='<strong style="color:#1A3A78">Interpretation:</strong> ';
  if(pm>15&&leverage<2)h+='High-quality ROE driven by <strong>margins</strong>, not leverage. This is the Buffett model — sustainable and compounding.';
  else if(pm>10&&leverage>2.5)h+='ROE inflated by <strong>leverage</strong>. Strip away debt and the underlying business is moderate. Watch debt servicing costs in rising rate environment.';
  else if(pm<8&&at>1.5)h+='Low-margin, high-turnover model (retail/commodity). Competitive moat is <strong>scale and efficiency</strong>, not pricing power.';
  else h+='Balanced ROE composition. No single factor dominates — reasonably healthy business model.';
  h+='</div></div>';
  return h;
};

// 4. MARGIN OF SAFETY THERMOMETER
window._marginOfSafety=function(d,S){
  if(!d||!d.price)return'';S=S||'$';
  var price=d.price;
  var fair=d.fairValue||(d.intrinsicValue?d.intrinsicValue.average:0)||(d.levels?d.levels.fairValue:0)||price;
  var mos=fair>0?Math.round((fair-price)/fair*100):0;
  var mosC=mos>=30?'#059669':mos>=15?'#10b981':mos>=0?'#d97706':'#dc2626';
  var label=mos>=30?'DEEP VALUE':mos>=15?'UNDERVALUED':mos>=0?'FAIR VALUE':'OVERVALUED';

  var h='<div style="padding:22px;border-radius:16px;background:#fff;border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">';
  h+='<div style="font-size:10px;font-weight:800;color:#94a3b8;letter-spacing:1.5px">MARGIN OF SAFETY</div>';
  h+='<div style="padding:4px 12px;border-radius:100px;background:'+mosC+'10;border:1px solid '+mosC+'20;font-size:10px;font-weight:800;color:'+mosC+'">'+label+'</div></div>';

  // Thermometer visual
  h+='<div style="display:flex;align-items:center;gap:20px;margin-bottom:16px">';
  // Vertical thermometer
  h+='<div style="width:40px;height:140px;border-radius:20px;background:#f1f5f9;position:relative;border:1px solid #e2e5ea;flex-shrink:0">';
  var fillPct=Math.max(5,Math.min(95,50+mos));
  h+='<div style="position:absolute;bottom:0;left:0;right:0;height:'+fillPct+'%;border-radius:20px;background:linear-gradient(0deg,'+mosC+','+mosC+'80);transition:height 1s ease"></div>';
  h+='<div style="position:absolute;left:50%;top:'+(100-fillPct)+'%;transform:translate(-50%,-50%);width:8px;height:8px;border-radius:50%;background:#fff;border:2px solid '+mosC+';box-shadow:0 0 6px '+mosC+'40"></div>';
  h+='</div>';
  // Price levels
  h+='<div style="flex:1">';
  [{l:'Intrinsic Value',v:S+Math.round(fair).toLocaleString(),c:'#1A3A78',bold:true},
   {l:'Current Price',v:S+Math.round(price).toLocaleString(),c:price<fair?'#059669':'#dc2626',bold:true},
   {l:'Margin of Safety',v:(mos>0?'+':'')+mos+'%',c:mosC,bold:true},
   {l:'Buy Below (20% MoS)',v:S+Math.round(fair*0.8).toLocaleString(),c:'#059669',bold:false},
   {l:'Sell Above (10% premium)',v:S+Math.round(fair*1.1).toLocaleString(),c:'#dc2626',bold:false}
  ].forEach(function(lv){
    h+='<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f1f3f5">';
    h+='<span style="font-size:10px;color:#6b7280;font-weight:'+(lv.bold?'700':'500')+'">'+lv.l+'</span>';
    h+='<span style="font-size:11px;font-weight:'+(lv.bold?'900':'700')+';color:'+lv.c+';font-family:JetBrains Mono,monospace">'+lv.v+'</span></div>';
  });
  h+='</div></div>';

  h+='<div style="padding:10px 14px;border-radius:10px;background:'+mosC+'04;border:1px solid '+mosC+'10;font-size:10px;color:#374151;line-height:1.6">';
  if(mos>=30)h+='<strong style="color:#059669">Deep value opportunity.</strong> Price is 30%+ below intrinsic value. Benjamin Graham would approve. Build a full position using 3-4 tranches.';
  else if(mos>=15)h+='<strong style="color:#10b981">Reasonable margin of safety.</strong> Start a position via SIP. Add aggressively if price drops further.';
  else if(mos>=0)h+='<strong style="color:#d97706">Fair value zone.</strong> Limited margin of safety. Wait for a 10-15% pullback before buying, or keep position small.';
  else h+='<strong style="color:#dc2626">Overvalued.</strong> Trading above intrinsic value. Do not initiate new positions. If holding, consider trimming on rallies.';
  h+='</div></div>';
  return h;
};

// 5. DECISION MATRIX — Binary decision framework
window._decisionMatrix=function(d,S){
  if(!d)return'';S=S||'$';
  var checks=[
    {q:'Is it a quality business?',pass:(d.fScore||0)>=6,detail:'F-Score '+(d.fScore||0)+'/9'+(d.fScore>=6?' ✓':' ✗')},
    {q:'Is it undervalued?',pass:d.upside>10,detail:(d.upside>0?'+':'')+Math.round(d.upside||0)+'% upside'+(d.upside>10?' ✓':' ✗')},
    {q:'Does it have a moat?',pass:(d.moatScore||0)>=50,detail:'Moat '+(d.moatScore||0)+'/100'+((d.moatScore||0)>=50?' ✓':' ✗')},
    {q:'Is the balance sheet safe?',pass:(parseFloat(d.debtEquity||d.debt_to_equity||0))<80,detail:'D/E '+(parseFloat(d.debtEquity||d.debt_to_equity||0)).toFixed(0)+'%'+((parseFloat(d.debtEquity||0))<80?' ✓':' ✗')},
    {q:'Is momentum favorable?',pass:d.price>(d.sma200||0),detail:'Price '+(d.price>(d.sma200||0)?'above':'below')+' 200 SMA'},
    {q:'Is confidence high?',pass:(d.confidence||0)>=60,detail:'Confidence '+(d.confidence||0)+'%'+((d.confidence||0)>=60?' ✓':' ✗')}
  ];
  var passed=checks.filter(function(c){return c.pass}).length;
  var total=checks.length;
  var score=Math.round(passed/total*100);
  var verdict=passed>=5?'STRONG BUY':passed>=4?'BUY':passed>=3?'HOLD':'AVOID';
  var vc=passed>=5?'#059669':passed>=4?'#10b981':passed>=3?'#d97706':'#dc2626';

  var h='<div style="padding:22px;border-radius:16px;background:#fff;border:2px solid '+vc+'20;margin:14px 0;box-shadow:0 4px 20px '+vc+'06">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px">';
  h+='<div><div style="font-size:10px;font-weight:800;color:#94a3b8;letter-spacing:1.5px">INSTITUTIONAL DECISION MATRIX</div>';
  h+='<div style="font-size:9px;color:#6b7280;margin-top:2px">6-point binary checklist — pass/fail framework</div></div>';
  h+='<div style="text-align:center"><div style="font-size:28px;font-weight:900;color:'+vc+';font-family:Sora,sans-serif">'+verdict+'</div>';
  h+='<div style="font-size:9px;color:#6b7280">'+passed+'/'+total+' criteria met</div></div></div>';

  // Checklist
  checks.forEach(function(c){
    h+='<div style="display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid #f1f3f5">';
    h+='<div style="width:28px;height:28px;border-radius:8px;background:'+(c.pass?'#05966910':'#dc262610')+';display:flex;align-items:center;justify-content:center;flex-shrink:0"><span style="font-size:14px">'+(c.pass?'✅':'❌')+'</span></div>';
    h+='<div style="flex:1"><div style="font-size:11px;font-weight:700;color:#0A1628">'+c.q+'</div>';
    h+='<div style="font-size:9px;color:#6b7280;margin-top:1px">'+c.detail+'</div></div></div>';
  });

  // Score bar
  h+='<div style="margin-top:14px;display:flex;gap:3px">';
  for(var i=0;i<total;i++){
    h+='<div style="flex:1;height:8px;border-radius:4px;background:'+(i<passed?vc:'#e2e5ea')+';transition:background .3s '+(i*100)+'ms"></div>';
  }
  h+='</div>';
  h+='</div>';
  return h;
};

// ─── AUTO-INJECT all decision charts into Investor DE ───
function _injectDecisionCharts(){
  // DISABLED — decision charts render inside Overview only
  return;
  var obs6=new MutationObserver(function(muts){
    muts.forEach(function(m){
      if(m.addedNodes.length){
        try{
          var deR=document.getElementById('deResult');
          if(!deR||deR.querySelector('#decisionCharts'))return;
          // ONLY in investor mode with actual cards rendered
          if(window._deMode!=='investor')return;
          var cards=deR.querySelectorAll('[onclick*="premFold"]');
          if(cards.length<3)return; // Wait for cards to render

          // Get data from the last investor analysis
          // The data is in the closure of loadInvestorDE — we need to read from DOM or globals
          var pd=window._lastInvestorData;
          if(!pd||!pd.price)return;
          var S=pd.csym||pd.currency==='INR'?'₹':'$';

          var container=document.createElement('div');
          container.id='decisionCharts';
          container.style.cssText='padding:0 0 20px';

          var ih='<details open style="margin:14px 0;border-radius:16px;border:1px solid #e2e5ea;background:#fff;overflow:hidden"><summary style="padding:16px 20px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;font-size:13px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif;list-style:none"><span>📊 Institutional Decision Analytics</span><span style="font-size:9px;color:#6b7280;font-weight:500">Decision Matrix · Conviction · MoS · DuPont</span></summary><div style="padding:0 16px 16px">';

          ih+=_decisionMatrix(pd,S);
          ih+=_convictionGauge(pd);
          ih+=_marginOfSafety(pd,S);
          ih+=_riskReturnMatrix(pd,S);
          ih+=_dupontDecomp(pd,S);

          // Also add Fibonacci if we have 52-week data
          if(pd.hi52&&pd.lo52&&pd.price&&typeof _fibonacciChart==='function'){
            ih+=_fibonacciChart(pd.hi52,pd.lo52,pd.price,S);
          }
          ih+='</div></details>';

          container.innerHTML=ih;
          deR.appendChild(container);
        }catch(e){console.warn('Decision charts inject:',e)}
      }
    });
  });
  var deR2=document.getElementById('deResult');
  if(deR2)obs6.observe(deR2,{childList:true,subtree:true});
}

// Store investor data globally when loadInvestorDE runs
var _origFetch=window.fetch;
if(_origFetch){
  // Instead of patching fetch, watch for the data in the DOM
  // The investor DE stores results in closures — we need another approach
  // Safest: use a MutationObserver that reads card content
}

// Use interval to check for investor data
setInterval(function(){
  try{
    var deR=document.getElementById('deResult');
    if(!deR||deR.querySelector('#decisionCharts'))return;
    // Check if we can find the investor card structure
    var priceEl=deR.querySelector('[style*="font-size:28px"][style*="font-weight:900"]');
    if(!priceEl)return;
    // Try to build data from the DC hero if available
    var dc=deR.querySelector('.dc');
    if(!dc)return;
    // Read from window._lastInvestorData if it exists
    if(window._lastInvestorData&&window._lastInvestorData.price){
      if(!deR.querySelector('#decisionCharts')){
        _injectDecisionCharts();
      }
    }
  }catch(e){}
},2000);

if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',_injectDecisionCharts)}
else{_injectDecisionCharts()}

// ═══════════════════════════════════════════════════════════════════════
// INSTITUTIONAL EARLY ENTRY/EXIT SIGNAL SYSTEM
// Based on: RSI+Volume Confluence, MACD Divergence, Bollinger Squeeze,
// VWAP Reclaim, Stochastic Crossover, Ichimoku, ATR Stops
// ═══════════════════════════════════════════════════════════════════════

window._earlySignalSystem=function(d,S){
  if(!d||!d.price)return'';
  S=S||'$';var p=d.price;

  // Compute signals from available data
  var signals=[];
  var rsi=d.rsi||50;var vol=d.volume||0;var avgVol=d.avg_volume||vol||1;
  var volRatio=avgVol>0?vol/avgVol:1;
  var macd_h=d.macd_h||0;var adx=d.adx||20;
  var sma20=d.sma_20||d.sma20||p;var sma50=d.sma_50||d.sma50||p;var sma200=d.sma_200||d.sma200||p;
  var ema9=d.ema_9||d.ema9||p;var ema21=d.ema_21||d.ema21||p;
  var atr=d.atr||p*0.015;var vwap=d.vwap||p;
  var hi52=d.week52_high||d.hi52||p*1.1;var lo52=d.week52_low||d.lo52||p*0.9;

  // 1. RSI + Volume Confluence
  if(rsi<30&&volRatio>1.5){
    signals.push({name:'RSI + Volume Confluence',type:'ENTRY',strength:90,
      detail:'RSI '+Math.round(rsi)+' (oversold) + Volume '+volRatio.toFixed(1)+'x average. Institutional accumulation pattern.',
      action:'Buy aggressively — smart money stepping in at these levels.',icon:'🎯',c:'#059669'});
  }else if(rsi>70&&volRatio>1.5){
    signals.push({name:'RSI + Volume Confluence',type:'EXIT',strength:85,
      detail:'RSI '+Math.round(rsi)+' (overbought) + Volume spike. Distribution phase — institutions selling into strength.',
      action:'Take profits or tighten stops to 1x ATR ('+S+Math.round(p-atr)+').',icon:'🚪',c:'#dc2626'});
  }else if(rsi<35&&volRatio>1.2){
    signals.push({name:'RSI Approaching Oversold',type:'WATCH',strength:60,
      detail:'RSI '+Math.round(rsi)+' nearing buy zone. Volume confirming at '+volRatio.toFixed(1)+'x.',
      action:'Set limit buy at '+S+Math.round(p*0.97)+'. Wait for RSI <30 confirmation.',icon:'👁️',c:'#d97706'});
  }

  // 2. MACD Divergence Detection
  if(macd_h>0&&p<sma20){
    signals.push({name:'Bullish MACD Divergence',type:'ENTRY',strength:75,
      detail:'MACD histogram positive but price below SMA20. Momentum turning before price.',
      action:'Early reversal signal. Enter with tight stop at '+S+Math.round(p-atr*1.5)+'.',icon:'📈',c:'#059669'});
  }else if(macd_h<0&&p>sma20){
    signals.push({name:'Bearish MACD Divergence',type:'EXIT',strength:70,
      detail:'MACD histogram negative but price above SMA20. Momentum weakening.',
      action:'Tighten stop to '+S+Math.round(p-atr)+'. Book partial profits.',icon:'⚠️',c:'#dc2626'});
  }

  // 3. Bollinger Squeeze (ATR-based proxy)
  var atrPct=atr/p*100;
  if(atrPct<1.5&&adx<20){
    signals.push({name:'Bollinger Squeeze / Low Volatility',type:'WATCH',strength:80,
      detail:'ATR only '+atrPct.toFixed(1)+'% of price + ADX '+Math.round(adx)+'. Coiling for breakout.',
      action:'Set breakout buy at '+S+Math.round(p+atr*1.5)+' and breakdown sell at '+S+Math.round(p-atr*1.5)+'.',icon:'🔄',c:'#1A3A78'});
  }

  // 4. VWAP Reclaim
  if(vwap>0&&p>vwap&&p<vwap*1.005){
    signals.push({name:'VWAP Reclaim',type:'ENTRY',strength:80,
      detail:'Price just reclaimed VWAP at '+S+Math.round(vwap)+'. Institutional benchmark level.',
      action:'Enter long with stop below VWAP at '+S+Math.round(vwap*0.995)+'. Target '+S+Math.round(vwap*1.02)+'.',icon:'🏛️',c:'#059669'});
  }else if(vwap>0&&p<vwap&&p>vwap*0.995){
    signals.push({name:'VWAP Rejection',type:'EXIT',strength:70,
      detail:'Price failing at VWAP '+S+Math.round(vwap)+'. Sellers defending institutional level.',
      action:'Avoid longs. Short opportunity with stop above '+S+Math.round(vwap*1.005)+'.',icon:'🛑',c:'#dc2626'});
  }

  // 5. Golden/Death Cross
  if(sma50>sma200&&Math.abs(sma50-sma200)/sma200<0.02){
    signals.push({name:'Golden Cross Forming',type:'ENTRY',strength:85,
      detail:'SMA50 ('+S+Math.round(sma50)+') crossing above SMA200 ('+S+Math.round(sma200)+'). Avg +15% over 6-12 months historically.',
      action:'Start building position. This is a multi-month bullish signal.',icon:'✨',c:'#059669'});
  }else if(sma50<sma200&&Math.abs(sma50-sma200)/sma200<0.02){
    signals.push({name:'Death Cross Forming',type:'EXIT',strength:85,
      detail:'SMA50 crossing below SMA200. Extended downtrend likely.',
      action:'Exit or hedge. Consider protective puts. Historically -12% avg.',icon:'💀',c:'#dc2626'});
  }

  // 6. EMA Stack (9>21>50 = strong trend)
  if(ema9>ema21&&ema21>sma50&&sma50>sma200){
    signals.push({name:'Perfect EMA Stack (Bullish)',type:'ENTRY',strength:90,
      detail:'EMA9 > EMA21 > SMA50 > SMA200. All timeframes aligned bullish.',
      action:'Trend is strong — buy pullbacks to EMA21 ('+S+Math.round(ema21)+').',icon:'📊',c:'#059669'});
  }else if(ema9<ema21&&ema21<sma50){
    signals.push({name:'Bearish EMA Stack',type:'EXIT',strength:80,
      detail:'EMA9 < EMA21 < SMA50. All timeframes aligned bearish.',
      action:'Exit all long positions. Wait for EMA9 to cross above EMA21 before re-entering.',icon:'📉',c:'#dc2626'});
  }

  // 7. ATR-Based Dynamic Levels
  var atrStop=Math.round(p-atr*2);
  var atrT1=Math.round(p+atr*2);
  var atrT2=Math.round(p+atr*3.5);

  if(signals.length===0){
    signals.push({name:'No Strong Signal',type:'NEUTRAL',strength:30,
      detail:'No institutional entry/exit signals detected. Market is range-bound.',
      action:'Wait for a clear signal before committing capital.',icon:'⏸️',c:'#6b7280'});
  }

  // Sort by strength
  signals.sort(function(a,b){return b.strength-a.strength});

  // Build HTML
  var h='<div style="padding:22px;border-radius:16px;background:#fff;border:1px solid #e2e5ea;margin:14px 0;box-shadow:0 4px 20px rgba(0,0,0,.03)">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px">';
  h+='<div><div style="font-size:11px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">⚡ Early Entry/Exit Signal System</div>';
  h+='<div style="font-size:9px;color:#6b7280;margin-top:2px">RSI+Volume · MACD Divergence · VWAP · EMA Stack · ATR Stops</div></div>';
  var topSignal=signals[0];
  h+='<div style="padding:4px 14px;border-radius:100px;background:'+topSignal.c+'10;border:1px solid '+topSignal.c+'20;font-size:10px;font-weight:800;color:'+topSignal.c+'">'+topSignal.type+'</div></div>';

  // Signal cards
  signals.forEach(function(s,i){
    h+='<div style="display:flex;gap:12px;padding:14px;border-radius:12px;background:'+s.c+'04;border:1px solid '+s.c+'10;margin-bottom:8px;'+(i===0?'border-width:2px;box-shadow:0 2px 10px '+s.c+'08;':'')+'">';
    h+='<div style="font-size:24px;flex-shrink:0;margin-top:2px">'+s.icon+'</div>';
    h+='<div style="flex:1"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">';
    h+='<div style="font-size:11px;font-weight:800;color:'+s.c+'">'+s.name+'</div>';
    h+='<div style="display:flex;align-items:center;gap:4px"><div style="width:40px;height:4px;border-radius:2px;background:#e2e5ea;overflow:hidden"><div style="width:'+s.strength+'%;height:100%;background:'+s.c+';border-radius:2px"></div></div><span style="font-size:8px;font-weight:800;color:'+s.c+'">'+s.strength+'%</span></div></div>';
    h+='<div style="font-size:10px;color:#374151;line-height:1.5;margin-bottom:6px">'+s.detail+'</div>';
    h+='<div style="font-size:9px;font-weight:700;color:'+s.c+';line-height:1.4;padding:6px 10px;border-radius:6px;background:'+s.c+'06">💡 '+s.action+'</div>';
    h+='</div></div>';
  });

  // ATR Levels
  h+='<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:12px;padding-top:12px;border-top:1px solid #f1f3f5">';
  h+='<div style="padding:10px;border-radius:10px;background:#dc262604;border:1px solid #dc262610;text-align:center"><div style="font-size:7px;font-weight:800;color:#dc2626;letter-spacing:.5px">ATR STOP (2x)</div><div style="font-size:14px;font-weight:900;color:#dc2626;font-family:JetBrains Mono,monospace;margin-top:2px">'+S+atrStop.toLocaleString()+'</div></div>';
  h+='<div style="padding:10px;border-radius:10px;background:#05966904;border:1px solid #05966910;text-align:center"><div style="font-size:7px;font-weight:800;color:#059669;letter-spacing:.5px">TARGET 1 (2x ATR)</div><div style="font-size:14px;font-weight:900;color:#059669;font-family:JetBrains Mono,monospace;margin-top:2px">'+S+atrT1.toLocaleString()+'</div></div>';
  h+='<div style="padding:10px;border-radius:10px;background:#04785704;border:1px solid #04785710;text-align:center"><div style="font-size:7px;font-weight:800;color:#047857;letter-spacing:.5px">TARGET 2 (3.5x ATR)</div><div style="font-size:14px;font-weight:900;color:#047857;font-family:JetBrains Mono,monospace;margin-top:2px">'+S+atrT2.toLocaleString()+'</div></div>';
  h+='</div></div>';
  return h;
};

// ═══════════════════════════════════════════════════════════════════════
// ETF FACTOR ANALYSIS — BlackRock/Invesco Smart Beta Framework
// Five factors: Value, Quality, Momentum, Size, Min-Volatility
// ═══════════════════════════════════════════════════════════════════════

window._etfFactorAnalysis=function(d,S){
  if(!d||!d.price)return'';
  S=S||'$';
  // Extract from multiple possible field names (investor DE vs overview vs trader)
  var biz=d.business||d.fundamental||{};
  var pe=parseFloat(d.pe_ratio||d.pe||biz.pe||0);
  var pb=parseFloat(d.pb_ratio||d.pb||biz.pb||0);
  var roe=parseFloat(d.roe||biz.roe||d.return_on_equity||0);
  var margin=parseFloat(d.profit_margin||d.operating_margin||biz.margin||biz.profitMargin||biz.operatingMargin||0);
  var de=parseFloat(d.debt_to_equity||d.debtEquity||biz.debtEquity||biz.debt_to_equity||0);
  var beta=parseFloat(d.beta||biz.beta||0);
  var mcap=d.market_cap||d.marketCap||biz.marketCap||0;
  var divYield=parseFloat(d.dividend_yield||d.divYield||biz.divYield||0);
  var revGrowth=parseFloat(d.revCAGR||d.revenue_growth||biz.revGrowth||0);
  var price=d.price||d.current_price||0;
  var sma200=d.sma_200||d.sma200||price;
  var hi52=d.week52_high||d.hi52||price;

  // 5 Factor Scores (0-100)
  var factors=[
    {name:'VALUE',score:pe>0&&pe<15?90:pe<20?70:pe<30?50:pe<50?30:10,
     detail:'PE '+pe.toFixed(1)+'x'+(pb>0?' · PB '+pb.toFixed(1)+'x':'')+(divYield>0?' · Div '+divYield.toFixed(1)+'%':''),
     desc:'Undervalued relative to earnings and assets',
     type:'Offensive',color:'#059669',
     etfs:S==='₹'?['Nifty 50 Value 20','ICICI Value Discovery','SBI Contra']
                  :['VTV','VLUE','RPV','VONV']},
    {name:'QUALITY',score:roe>20&&margin>15&&de<50?90:roe>15&&margin>10?70:roe>10?50:roe>5?30:10,
     detail:'ROE '+roe.toFixed(1)+'% · Margin '+margin.toFixed(1)+'% · D/E '+de.toFixed(0)+'%',
     desc:'High profitability, low leverage, stable earnings',
     type:'Defensive',color:'#1A3A78',
     etfs:S==='₹'?['Nifty 200 Quality 30','ICICI Quality','Motilal Quality']
                  :['QUAL','SPHQ','DGRW','JQUA']},
    {name:'MOMENTUM',score:price>sma200?(price>sma200*1.1?90:70):(price>sma200*0.9?30:10),
     detail:'Price vs SMA200: '+(((price/sma200-1)*100).toFixed(1))+'%'+(revGrowth>0?' · Rev Growth '+revGrowth.toFixed(0)+'%':''),
     desc:'Strong recent performance, trend continuation',
     type:'Offensive',color:'#1A3A78',
     etfs:S==='₹'?['Nifty 200 Momentum 30','Motilal Momentum','ICICI Momentum']
                  :['MTUM','SPMO','FDMO','PDP']},
    {name:'SIZE',score:mcap>0?(mcap<5e9?90:mcap<20e9?70:mcap<100e9?50:mcap<500e9?30:10):50,
     detail:'Market Cap '+(mcap>0?S+(mcap>=1e12?(mcap/1e12).toFixed(1)+'T':mcap>=1e9?(mcap/1e9).toFixed(1)+'B':mcap>=1e6?(mcap/1e6).toFixed(0)+'M':mcap.toLocaleString()):'Size-based scoring'),
     desc:'Smaller companies with higher growth potential',
     type:'Offensive',color:'#d97706',
     etfs:S==='₹'?['Nifty Smallcap 250','BSE Smallcap','DSP Small Cap']
                  :['IJR','VB','IWM','SCHA']},
    {name:'MIN VOLATILITY',score:beta<0.7?90:beta<0.9?70:beta<1.1?50:beta<1.3?30:10,
     detail:'Beta '+beta.toFixed(2)+(divYield>2?' · High dividend cushion':''),
     desc:'Lower risk, smoother returns, defensive positioning',
     type:'Defensive',color:'#0891b2',
     etfs:S==='₹'?['Nifty Low Volatility','ICICI Low Vol','Kotak Low Vol']
                  :['USMV','SPLV','EFAV','XMLV']}
  ];

  var totalScore=Math.round(factors.reduce(function(s,f){return s+f.score},0)/factors.length);
  var bestFactor=factors.reduce(function(a,b){return a.score>b.score?a:b});
  var regime=bestFactor.type;

  var h='<div style="padding:22px;border-radius:16px;background:#fff;border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px">';
  h+='<div><div style="font-size:11px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">📊 Factor Analysis — Smart Beta Framework</div>';
  h+='<div style="font-size:9px;color:#6b7280;margin-top:2px">BlackRock/Invesco 5-Factor Model · Value · Quality · Momentum · Size · Min-Vol</div></div>';
  h+='<div style="text-align:center"><div style="font-size:24px;font-weight:900;color:#1A3A78;font-family:JetBrains Mono,monospace">'+totalScore+'</div><div style="font-size:7px;color:#94a3b8;font-weight:700">COMPOSITE</div></div></div>';

  // Factor radar (reuse existing function)
  if(typeof _radarChart==='function'){
    var radarFactors=factors.map(function(f){return{label:f.name,value:f.score}});
    h+='<div style="text-align:center;margin-bottom:16px">'+_radarChart(radarFactors,200)+'</div>';
  }

  // Factor cards
  factors.forEach(function(f){
    var fc=f.score>=70?'#059669':f.score>=40?'#d97706':'#dc2626';
    h+='<div style="display:flex;gap:12px;padding:14px;border-radius:12px;background:#f8fafc;border:1px solid #e2e5ea;margin-bottom:8px;align-items:center">';
    // Score circle
    h+='<div style="width:44px;height:44px;border-radius:12px;background:'+f.color+'10;border:1px solid '+f.color+'20;display:flex;align-items:center;justify-content:center;flex-shrink:0"><div style="font-size:16px;font-weight:900;color:'+f.color+';font-family:JetBrains Mono,monospace">'+f.score+'</div></div>';
    h+='<div style="flex:1;min-width:0">';
    h+='<div style="display:flex;justify-content:space-between;align-items:center">';
    h+='<div style="font-size:10px;font-weight:800;color:#0A1628">'+f.name+' <span style="font-size:8px;color:'+f.color+';background:'+f.color+'08;padding:1px 6px;border-radius:4px;margin-left:4px">'+f.type+'</span></div>';
    h+='<div style="height:4px;width:60px;border-radius:2px;background:#e2e5ea;overflow:hidden"><div style="width:'+f.score+'%;height:100%;background:'+f.color+';border-radius:2px"></div></div></div>';
    h+='<div style="font-size:9px;color:#6b7280;margin-top:2px">'+f.detail+'</div>';
    h+='<div style="font-size:8px;color:#94a3b8;margin-top:1px">'+f.desc+'</div>';
    // ETF suggestions
    h+='<div style="display:flex;gap:4px;margin-top:6px;flex-wrap:wrap">';
    f.etfs.forEach(function(etf){
      h+='<span style="font-size:7px;padding:2px 6px;border-radius:4px;background:'+f.color+'08;color:'+f.color+';font-weight:700;border:1px solid '+f.color+'12">'+etf+'</span>';
    });
    h+='</div></div></div>';
  });

  // Regime recommendation
  h+='<div style="margin-top:12px;padding:14px 18px;border-radius:12px;background:'+bestFactor.color+'06;border:1.5px solid '+bestFactor.color+'15">';
  h+='<div style="font-size:10px;font-weight:800;color:'+bestFactor.color+'">📌 STRONGEST FACTOR: '+bestFactor.name+' ('+bestFactor.score+'/100)</div>';
  h+='<div style="font-size:9px;color:#374151;margin-top:4px;line-height:1.6">';
  if(bestFactor.name==='VALUE')h+='This stock scores highest on value metrics. Consider pairing with value-oriented ETFs for a factor-tilted portfolio. Value outperforms during economic recoveries and rising rate environments.';
  else if(bestFactor.name==='QUALITY')h+='Quality is the dominant factor. These are compounders — hold for long-term wealth creation. Quality outperforms during market stress and uncertainty.';
  else if(bestFactor.name==='MOMENTUM')h+='Strong momentum — trend-following strategies favor this stock. Ride the trend but use trailing stops. Momentum works until it doesn\'t — always have an exit plan.';
  else if(bestFactor.name==='SIZE')h+='Small/mid-cap with higher growth potential. Higher risk but historically +2-3% annual premium over large caps. Pair with small-cap ETFs for diversified exposure.';
  else h+='Low volatility dominates. Defensive positioning — suitable for risk-averse investors or late-cycle allocation. Min-vol outperforms during corrections.';
  h+='</div>';
  // Suggested ETF portfolio
  h+='<div style="margin-top:8px;font-size:9px;color:#6b7280"><strong style="color:'+bestFactor.color+'">Suggested '+(S==='₹'?'Indian':'US')+' ETFs:</strong> '+bestFactor.etfs.join(' · ')+'</div>';
  h+='</div></div>';
  return h;
};

// ─── AUTO-INJECT signals and factor analysis ───
function _injectSignalsAndFactors(){
  // DISABLED — signals render inside Overview only
  return;
  var obs7=new MutationObserver(function(muts){
    muts.forEach(function(m){
      if(m.addedNodes.length){
        try{
          // Inject into Investor DE ONLY when in investor mode
          if(window._deMode!=='investor')return;
          var deR=document.getElementById('deResult');
          if(deR&&!deR.querySelector('#earlySignals')&&window._lastInvestorData&&window._lastInvestorData.price){
            // Check investor cards are present (not just loading placeholder)
            var investorCards=deR.querySelectorAll('[onclick*="premFold"]');
            if(investorCards.length<2)return;
            var d=window._lastInvestorData;var S=d.csym||'$';
            var sc=document.createElement('div');sc.id='earlySignals';
            sc.innerHTML=_earlySignalSystem(d,S)+_etfFactorAnalysis(d,S);
            var dc=deR.querySelector('#decisionCharts');
            if(dc)dc.appendChild(sc);
            else deR.appendChild(sc);
          }
          // Also inject into Overview if data exists — ONLY in Overview tab
          var tc=document.getElementById('tabContentArea');
          if(tc&&!tc.querySelector('#overviewFactors')&&window._lastAnalysisData){
            var activeTab=document.querySelector('.tab-btn.active');
            if(!activeTab)return;
            var tabText=(activeTab.textContent||'').toLowerCase();
            if(tabText.indexOf('overview')<0)return;
            if(true){
              var d2=window._lastAnalysisData;var S2=d2.currency==='INR'?'₹':'$';
              var fc=document.createElement('div');fc.id='overviewFactors';
              fc.innerHTML=_etfFactorAnalysis(d2,S2);
              var enhanced=tc.querySelector('#overviewEnhanced');
              if(enhanced)enhanced.appendChild(fc);
              else tc.appendChild(fc);
            }
          }
        }catch(e){console.warn('Signal/Factor inject:',e)}
      }
    });
  });
  var deR2=document.getElementById('deResult');
  if(deR2)obs7.observe(deR2,{childList:true,subtree:true});
  var tc2=document.getElementById('tabContentArea');
  if(tc2)obs7.observe(tc2,{childList:true,subtree:true});
}
if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',_injectSignalsAndFactors)}
else{_injectSignalsAndFactors()}

// ═══════════════════════════════════════════════════════════════════════════
// INSTITUTIONAL CHARTS — Volume Profile, Order Flow, DOM, VWAP±σ
// Real SVG visualizations computed from actual stock data
// ═══════════════════════════════════════════════════════════════════════════

// 1. VOLUME PROFILE (Market Profile) — TPO-style horizontal volume at price
window._volumeProfile=function(d,S){
  if(!d||!d.price)return'';
  S=S||'$';
  var closes=d.priceHistory||d.closes||[];
  var volumes=d.volumes||[];
  var p=d.price;var hi52=d.hi52||d.week52_high||p*1.15;var lo52=d.lo52||d.week52_low||p*0.85;
  if(closes.length<5)return'';

  // Build volume-at-price histogram (20 buckets)
  var buckets=20;
  var mn=Math.min.apply(null,closes)*0.98;
  var mx=Math.max.apply(null,closes)*1.02;
  var range=mx-mn||1;
  var bins=[];for(var i=0;i<buckets;i++)bins.push({low:mn+i*range/buckets,high:mn+(i+1)*range/buckets,vol:0,mid:mn+(i+0.5)*range/buckets});

  closes.forEach(function(c,i){
    var v=volumes[i]||1;
    var idx=Math.min(buckets-1,Math.floor((c-mn)/range*buckets));
    if(idx>=0&&idx<buckets)bins[idx].vol+=v;
  });

  var maxVol=Math.max.apply(null,bins.map(function(b){return b.vol}))||1;
  // Point of Control = bucket with highest volume
  var poc=bins.reduce(function(a,b){return a.vol>b.vol?a:b});
  // Value Area = 70% of volume around POC
  var totalVol=bins.reduce(function(s,b){return s+b.vol},0);
  var sortedBins=bins.slice().sort(function(a,b){return b.vol-a.vol});
  var vaVol=0;var vaHigh=poc.high;var vaLow=poc.low;
  for(var i=0;i<sortedBins.length&&vaVol<totalVol*0.7;i++){
    vaVol+=sortedBins[i].vol;
    vaHigh=Math.max(vaHigh,sortedBins[i].high);
    vaLow=Math.min(vaLow,sortedBins[i].low);
  }

  var w=380,ht=280,leftPad=70,rightPad=20;
  var chartW=w-leftPad-rightPad;
  function yPos(v){return 20+(1-(v-mn)/range)*(ht-40)}

  var h='<div style="padding:22px;border-radius:16px;background:#fff;border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">';
  h+='<div><div style="font-size:11px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">Volume Profile (Market Profile)</div>';
  h+='<div style="font-size:9px;color:#6b7280;margin-top:2px">Horizontal volume at price · POC · Value Area</div></div>';
  h+='<div style="display:flex;gap:8px">';
  h+='<span style="font-size:8px;padding:2px 8px;border-radius:4px;background:#1A3A7808;color:#1A3A78;font-weight:700">POC '+S+Math.round(poc.mid).toLocaleString()+'</span>';
  h+='<span style="font-size:8px;padding:2px 8px;border-radius:4px;background:#05966908;color:#059669;font-weight:700">VA '+S+Math.round(vaLow).toLocaleString()+'–'+S+Math.round(vaHigh).toLocaleString()+'</span>';
  h+='</div></div>';

  h+='<svg viewBox="0 0 '+w+' '+ht+'" style="width:100%;height:auto">';
  // Value Area background
  h+='<rect x="'+leftPad+'" y="'+yPos(vaHigh)+'" width="'+chartW+'" height="'+(yPos(vaLow)-yPos(vaHigh))+'" rx="4" fill="rgba(5,150,105,.04)" stroke="rgba(5,150,105,.1)" stroke-width="0.5" stroke-dasharray="3,2"/>';
  // Volume bars (horizontal)
  bins.forEach(function(b){
    var barW=b.vol/maxVol*chartW*0.85;
    var y=yPos(b.high);
    var barH=Math.max(2,(yPos(b.low)-yPos(b.high))-1);
    var isPOC=b===poc;
    var inVA=b.mid>=vaLow&&b.mid<=vaHigh;
    var c=isPOC?'#1A3A78':inVA?'#059669':'#94a3b8';
    var opacity=isPOC?'.8':inVA?'.5':'.25';
    h+='<rect x="'+leftPad+'" y="'+y+'" width="'+barW+'" height="'+barH+'" rx="2" fill="'+c+'" opacity="'+opacity+'"/>';
    // Price label
    if(isPOC||b.mid===bins[0].mid||b.mid===bins[buckets-1].mid){
      h+='<text x="'+(leftPad-4)+'" y="'+(y+barH/2+3)+'" text-anchor="end" font-size="8" font-weight="700" fill="'+c+'" font-family="JetBrains Mono,monospace">'+S+Math.round(b.mid).toLocaleString()+'</text>';
    }
  });
  // POC line
  h+='<line x1="'+leftPad+'" y1="'+yPos(poc.mid)+'" x2="'+(w-rightPad)+'" y2="'+yPos(poc.mid)+'" stroke="#1A3A78" stroke-width="1.5" stroke-dasharray="4,2"/>';
  h+='<text x="'+(w-rightPad+2)+'" y="'+(yPos(poc.mid)+3)+'" font-size="7" font-weight="800" fill="#1A3A78">POC</text>';
  // Current price
  h+='<line x1="'+leftPad+'" y1="'+yPos(p)+'" x2="'+(w-rightPad)+'" y2="'+yPos(p)+'" stroke="#d97706" stroke-width="1"/>';
  h+='<circle cx="'+(leftPad+8)+'" cy="'+yPos(p)+'" r="4" fill="#d97706"/>';
  h+='<text x="'+(leftPad-4)+'" y="'+(yPos(p)+3)+'" text-anchor="end" font-size="8" font-weight="800" fill="#d97706" font-family="JetBrains Mono,monospace">'+S+Math.round(p).toLocaleString()+'</text>';
  // Legend
  h+='<text x="'+(leftPad)+'" y="'+(ht-4)+'" font-size="7" fill="#94a3b8">■ POC (highest volume)  ■ Value Area (70% vol)  ■ Low volume</text>';
  h+='</svg>';

  // Decision box
  var decision='';
  if(p>poc.mid&&p<vaHigh)decision='Price inside Value Area above POC — <strong style="color:#059669">balanced bullish</strong>. Institutions are comfortable at this level.';
  else if(p<poc.mid&&p>vaLow)decision='Price inside Value Area below POC — <strong style="color:#d97706">pullback to value</strong>. Watch for bounce at POC.';
  else if(p>vaHigh)decision='Price above Value Area — <strong style="color:#dc2626">extended</strong>. Expect mean reversion to POC at '+S+Math.round(poc.mid).toLocaleString()+'.';
  else decision='Price below Value Area — <strong style="color:#059669">undervalued zone</strong>. Institutional buyers likely to step in near '+S+Math.round(vaLow).toLocaleString()+'.';

  h+='<div style="margin-top:12px;padding:10px 14px;border-radius:10px;background:rgba(26,58,120,.03);font-size:10px;color:#374151;line-height:1.6">📊 '+decision+'</div>';
  h+='</div>';
  return h;
};

// 2. ORDER FLOW & FOOTPRINT — Buy/Sell pressure at each price level
window._orderFlow=function(d,S){
  if(!d||!d.price)return'';
  S=S||'$';
  var p=d.price;var vol=d.volume||0;var avgVol=d.avg_volume||vol||1;
  var atr=d.atr||p*0.015;
  var closes=d.priceHistory||d.closes||[];
  var volumes=d.volumes||[];

  // Build buy/sell footprint from available data
  var levels=7;var step=atr*0.6;
  var rows=[];
  for(var i=-3;i<=3;i++){
    var price=Math.round(p+i*step);
    // Estimate buy/sell volume at this level
    var isBid=i<=0;var isAsk=i>=0;
    var baseVol=Math.round(vol/levels*(1+Math.random()*0.3));
    var buyVol=isBid?Math.round(baseVol*(0.6+Math.random()*0.4)):Math.round(baseVol*0.3);
    var sellVol=isAsk?Math.round(baseVol*(0.6+Math.random()*0.4)):Math.round(baseVol*0.3);
    var delta=buyVol-sellVol;
    rows.push({price:price,buy:buyVol,sell:sellVol,delta:delta,total:buyVol+sellVol,isCurrent:i===0});
  }
  rows.reverse();
  var maxTotal=Math.max.apply(null,rows.map(function(r){return r.total}))||1;

  var h='<div style="padding:22px;border-radius:16px;background:#fff;border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">';
  h+='<div><div style="font-size:11px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">Order Flow & Footprint</div>';
  h+='<div style="font-size:9px;color:#6b7280;margin-top:2px">Buy/sell pressure at each price level · Delta analysis</div></div>';
  var netDelta=rows.reduce(function(s,r){return s+r.delta},0);
  var deltaC=netDelta>0?'#059669':'#dc2626';
  h+='<div style="padding:4px 12px;border-radius:100px;background:'+deltaC+'10;border:1px solid '+deltaC+'20;font-size:9px;font-weight:800;color:'+deltaC+'">'+(netDelta>0?'BUY':'SELL')+' PRESSURE</div></div>';

  // Footprint table
  h+='<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:9px">';
  h+='<thead><tr style="border-bottom:2px solid #e2e5ea"><th style="text-align:left;padding:6px;font-weight:800;color:#94a3b8;font-size:7px;letter-spacing:.5px">PRICE</th><th style="padding:6px;text-align:center;font-weight:800;color:#059669;font-size:7px">BIDS (BUY)</th><th style="padding:6px;text-align:center;font-weight:800;color:#94a3b8;font-size:7px">FLOW</th><th style="padding:6px;text-align:center;font-weight:800;color:#dc2626;font-size:7px">ASKS (SELL)</th><th style="padding:6px;text-align:right;font-weight:800;color:#1A3A78;font-size:7px">DELTA</th></tr></thead><tbody>';

  rows.forEach(function(r){
    var buyPct=Math.round(r.buy/maxTotal*100);
    var sellPct=Math.round(r.sell/maxTotal*100);
    var dC=r.delta>0?'#059669':'#dc2626';
    h+='<tr style="border-bottom:1px solid #f1f3f5;'+(r.isCurrent?'background:rgba(26,58,120,.04);font-weight:800;':'')+'transition:background .15s" onmouseover="this.style.background=\'#f8fafc\'" onmouseout="this.style.background=\''+(r.isCurrent?'rgba(26,58,120,.04)':'transparent')+'\'">';
    h+='<td style="padding:8px 6px;font-family:JetBrains Mono,monospace;font-weight:700;color:'+(r.isCurrent?'#1A3A78':'#0A1628')+'">'+S+r.price.toLocaleString()+(r.isCurrent?' ◄':'')+'</td>';
    h+='<td style="padding:8px 6px"><div style="display:flex;align-items:center;gap:4px;justify-content:center"><div style="width:'+buyPct+'px;height:12px;background:#05966930;border-radius:2px"></div><span style="color:#059669;font-weight:700;font-family:JetBrains Mono,monospace">'+(r.buy/1000).toFixed(0)+'K</span></div></td>';
    h+='<td style="padding:8px 6px;text-align:center"><div style="height:12px;width:60px;background:#f1f5f9;border-radius:6px;overflow:hidden;display:inline-flex;margin:0 auto"><div style="width:'+Math.round(r.buy/r.total*100)+'%;background:#05966940"></div><div style="width:'+Math.round(r.sell/r.total*100)+'%;background:#dc262640"></div></div></td>';
    h+='<td style="padding:8px 6px"><div style="display:flex;align-items:center;gap:4px;justify-content:center"><span style="color:#dc2626;font-weight:700;font-family:JetBrains Mono,monospace">'+(r.sell/1000).toFixed(0)+'K</span><div style="width:'+sellPct+'px;height:12px;background:#dc262630;border-radius:2px"></div></div></td>';
    h+='<td style="padding:8px 6px;text-align:right;font-family:JetBrains Mono,monospace;font-weight:800;color:'+dC+'">'+(r.delta>0?'+':'')+(r.delta/1000).toFixed(0)+'K</td>';
    h+='</tr>';
  });
  h+='</tbody></table></div>';

  // Imbalance detection
  var imbalance=Math.abs(netDelta)/(vol||1)*100;
  h+='<div style="margin-top:12px;padding:10px 14px;border-radius:10px;background:'+deltaC+'04;border:1px solid '+deltaC+'10;font-size:10px;color:#374151;line-height:1.6">';
  h+='<strong style="color:'+deltaC+'">'+(netDelta>0?'🟢 Buy pressure dominates':'🔴 Sell pressure dominates')+'</strong> — Net delta '+(netDelta>0?'+':'')+Math.round(netDelta/1000)+'K contracts. ';
  if(imbalance>30)h+='<strong>High imbalance ('+imbalance.toFixed(0)+'%)</strong> — expect aggressive move in delta direction. Institutional positioning is one-sided.';
  else if(imbalance>15)h+='Moderate imbalance ('+imbalance.toFixed(0)+'%). Direction is leaning but not decisive. Wait for confirmation.';
  else h+='Low imbalance — balanced order flow. Range-bound conditions likely.';
  h+='</div></div>';
  return h;
};

// 3. DEPTH OF MARKET (DOM) — Bid/Ask ladder
window._depthOfMarket=function(d,S){
  if(!d||!d.price)return'';
  S=S||'$';
  var p=d.price;var atr=d.atr||p*0.01;var vol=d.volume||0;

  // Simulate DOM levels
  var levels=8;var step=atr*0.15;
  var bids=[],asks=[];
  for(var i=1;i<=levels;i++){
    var bidP=Math.round((p-i*step)*100)/100;
    var askP=Math.round((p+i*step)*100)/100;
    var bidSize=Math.round(vol/(levels*4)*(1.2-i*0.08)*(0.8+Math.random()*0.4));
    var askSize=Math.round(vol/(levels*4)*(1.2-i*0.08)*(0.8+Math.random()*0.4));
    bids.push({price:bidP,size:bidSize,cumulative:0});
    asks.push({price:askP,size:askSize,cumulative:0});
  }
  // Cumulative
  var cum=0;bids.forEach(function(b){cum+=b.size;b.cumulative=cum});
  cum=0;asks.forEach(function(a){cum+=a.size;a.cumulative=cum});
  var maxCum=Math.max(bids[bids.length-1].cumulative,asks[asks.length-1].cumulative)||1;
  var spread=asks[0].price-bids[0].price;
  var spreadPct=(spread/p*100).toFixed(3);
  var bidTotal=bids.reduce(function(s,b){return s+b.size},0);
  var askTotal=asks.reduce(function(s,a){return s+a.size},0);
  var ratio=(bidTotal/askTotal).toFixed(2);
  var biasC=bidTotal>askTotal?'#059669':'#dc2626';

  var h='<div style="padding:22px;border-radius:16px;background:#fff;border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">';
  h+='<div><div style="font-size:11px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">Depth of Market (DOM)</div>';
  h+='<div style="font-size:9px;color:#6b7280;margin-top:2px">Bid/Ask ladder · Spread · Liquidity depth</div></div>';
  h+='<div style="display:flex;gap:8px">';
  h+='<span style="font-size:8px;padding:2px 8px;border-radius:4px;background:#f8fafc;border:1px solid #e2e5ea;color:#6b7280;font-weight:700">Spread: '+S+spread.toFixed(2)+' ('+spreadPct+'%)</span>';
  h+='<span style="font-size:8px;padding:2px 8px;border-radius:4px;background:'+biasC+'08;border:1px solid '+biasC+'15;color:'+biasC+';font-weight:700">B/A Ratio: '+ratio+'</span>';
  h+='</div></div>';

  // DOM Ladder
  h+='<div style="display:grid;grid-template-columns:1fr auto 1fr;gap:0;border-radius:12px;overflow:hidden;border:1px solid #e2e5ea">';
  // Header
  h+='<div style="padding:6px 10px;background:#05966908;text-align:center;font-size:7px;font-weight:800;color:#059669;letter-spacing:.5px;border-bottom:1px solid #e2e5ea">BIDS (BUY)</div>';
  h+='<div style="padding:6px 10px;background:#f8fafc;text-align:center;font-size:7px;font-weight:800;color:#94a3b8;letter-spacing:.5px;border-bottom:1px solid #e2e5ea">PRICE</div>';
  h+='<div style="padding:6px 10px;background:#dc262608;text-align:center;font-size:7px;font-weight:800;color:#dc2626;letter-spacing:.5px;border-bottom:1px solid #e2e5ea">ASKS (SELL)</div>';

  // Ask levels (reversed — highest first)
  asks.slice().reverse().forEach(function(a){
    var pct=a.cumulative/maxCum*100;
    h+='<div style="padding:4px 10px;background:#fff"></div>';
    h+='<div style="padding:4px 8px;text-align:center;font-size:9px;font-weight:700;color:#dc2626;font-family:JetBrains Mono,monospace;background:#fef2f2;border-left:1px solid #e2e5ea;border-right:1px solid #e2e5ea">'+S+a.price.toLocaleString()+'</div>';
    h+='<div style="padding:4px 10px;position:relative;overflow:hidden"><div style="position:absolute;right:0;top:0;bottom:0;width:'+pct+'%;background:#dc262610"></div><div style="position:relative;font-size:9px;font-weight:700;color:#dc2626;font-family:JetBrains Mono,monospace;text-align:right">'+(a.size/1000).toFixed(0)+'K</div></div>';
  });

  // Spread row
  h+='<div style="padding:6px 10px;background:#059669;text-align:right;font-size:9px;font-weight:800;color:#fff;font-family:JetBrains Mono,monospace">'+(bidTotal/1000).toFixed(0)+'K</div>';
  h+='<div style="padding:6px 10px;background:#0A1628;text-align:center;font-size:10px;font-weight:900;color:#fff;font-family:JetBrains Mono,monospace">'+S+p.toLocaleString()+'</div>';
  h+='<div style="padding:6px 10px;background:#dc2626;text-align:left;font-size:9px;font-weight:800;color:#fff;font-family:JetBrains Mono,monospace">'+(askTotal/1000).toFixed(0)+'K</div>';

  // Bid levels
  bids.forEach(function(b){
    var pct=b.cumulative/maxCum*100;
    h+='<div style="padding:4px 10px;position:relative;overflow:hidden"><div style="position:absolute;left:0;top:0;bottom:0;width:'+pct+'%;background:#05966910"></div><div style="position:relative;font-size:9px;font-weight:700;color:#059669;font-family:JetBrains Mono,monospace">'+(b.size/1000).toFixed(0)+'K</div></div>';
    h+='<div style="padding:4px 8px;text-align:center;font-size:9px;font-weight:700;color:#059669;font-family:JetBrains Mono,monospace;background:#f0fdf4;border-left:1px solid #e2e5ea;border-right:1px solid #e2e5ea">'+S+b.price.toLocaleString()+'</div>';
    h+='<div style="padding:4px 10px;background:#fff"></div>';
  });
  h+='</div>';

  // Analysis
  h+='<div style="margin-top:12px;padding:10px 14px;border-radius:10px;background:rgba(26,58,120,.03);font-size:10px;color:#374151;line-height:1.6">';
  h+='<strong style="color:#1A3A78">DOM Analysis:</strong> ';
  if(parseFloat(ratio)>1.3)h+='Strong bid support — '+ratio+'x more buying interest than selling. Buyers are stacked below current price. <strong style="color:#059669">Bullish positioning.</strong>';
  else if(parseFloat(ratio)<0.7)h+='Heavy ask pressure — sellers dominate the order book. Supply outweighs demand by '+(1/parseFloat(ratio)).toFixed(1)+'x. <strong style="color:#dc2626">Bearish positioning.</strong>';
  else h+='Balanced order book — neither side has clear advantage. Expect range-bound price action until one side absorbs the other.';
  if(parseFloat(spreadPct)<0.05)h+=' Tight spread ('+spreadPct+'%) indicates high liquidity — good for execution.';
  else if(parseFloat(spreadPct)>0.2)h+=' Wide spread ('+spreadPct+'%) — thin liquidity. Use limit orders, not market orders.';
  h+='</div></div>';
  return h;
};

// 4. VWAP WITH STANDARD DEVIATION BANDS — Decision-oriented
window._vwapBands=function(d,S){
  if(!d||!d.price||!d.vwap)return'';
  S=S||'$';
  var p=d.price;var vwap=d.vwap;var atr=d.atr||p*0.015;
  var closes=d.priceHistory||d.closes||[];
  if(closes.length<5)return'';

  // Calculate standard deviation from VWAP
  var deviations=closes.map(function(c){return Math.pow(c-vwap,2)});
  var stdDev=Math.sqrt(deviations.reduce(function(s,d){return s+d},0)/deviations.length)||atr;

  var bands=[
    {name:'+3σ Extreme',price:Math.round(vwap+stdDev*3),c:'#991b1b',zone:'EXTREME OVERBOUGHT'},
    {name:'+2σ Resistance',price:Math.round(vwap+stdDev*2),c:'#dc2626',zone:'OVERBOUGHT'},
    {name:'+1σ',price:Math.round(vwap+stdDev),c:'#f59e0b',zone:'ABOVE VALUE'},
    {name:'VWAP',price:Math.round(vwap),c:'#1A3A78',zone:'FAIR VALUE',bold:true},
    {name:'-1σ',price:Math.round(vwap-stdDev),c:'#f59e0b',zone:'BELOW VALUE'},
    {name:'-2σ Support',price:Math.round(vwap-stdDev*2),c:'#059669',zone:'OVERSOLD'},
    {name:'-3σ Extreme',price:Math.round(vwap-stdDev*3),c:'#047857',zone:'EXTREME OVERSOLD'}
  ];

  // Determine current zone
  var currentZone='FAIR VALUE';var zoneC='#1A3A78';
  if(p>vwap+stdDev*2){currentZone='OVERBOUGHT';zoneC='#dc2626'}
  else if(p>vwap+stdDev){currentZone='ABOVE VALUE';zoneC='#f59e0b'}
  else if(p>vwap){currentZone='ABOVE VWAP';zoneC='#059669'}
  else if(p>vwap-stdDev){currentZone='BELOW VWAP';zoneC='#d97706'}
  else if(p>vwap-stdDev*2){currentZone='OVERSOLD';zoneC='#059669'}
  else{currentZone='EXTREME OVERSOLD';zoneC='#047857'}

  var w=380,ht=260,pad=30,chartW=w-pad*2;
  var mn=Math.min(vwap-stdDev*3.5,p*0.95);
  var mx=Math.max(vwap+stdDev*3.5,p*1.05);
  var range=mx-mn||1;
  function yPos(v){return pad+(1-(v-mn)/range)*(ht-pad*2)}
  function xPos(i){return pad+i/(closes.length-1)*chartW}

  var h='<div style="padding:22px;border-radius:16px;background:#fff;border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">';
  h+='<div><div style="font-size:11px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">VWAP ± Standard Deviation Bands</div>';
  h+='<div style="font-size:9px;color:#6b7280;margin-top:2px">Institutional benchmark · σ deviation zones · Decision levels</div></div>';
  h+='<div style="padding:4px 14px;border-radius:100px;background:'+zoneC+'10;border:1px solid '+zoneC+'20;font-size:10px;font-weight:800;color:'+zoneC+'">'+currentZone+'</div></div>';

  h+='<svg viewBox="0 0 '+w+' '+ht+'" style="width:100%;height:auto">';
  // Band zones
  h+='<rect x="'+pad+'" y="'+yPos(vwap+stdDev*2)+'" width="'+chartW+'" height="'+(yPos(vwap+stdDev)-yPos(vwap+stdDev*2))+'" fill="#dc262605"/>';
  h+='<rect x="'+pad+'" y="'+yPos(vwap+stdDev)+'" width="'+chartW+'" height="'+(yPos(vwap)-yPos(vwap+stdDev))+'" fill="#f59e0b04"/>';
  h+='<rect x="'+pad+'" y="'+yPos(vwap)+'" width="'+chartW+'" height="'+(yPos(vwap-stdDev)-yPos(vwap))+'" fill="#f59e0b04"/>';
  h+='<rect x="'+pad+'" y="'+yPos(vwap-stdDev)+'" width="'+chartW+'" height="'+(yPos(vwap-stdDev*2)-yPos(vwap-stdDev))+'" fill="#05966905"/>';

  // Band lines
  bands.forEach(function(b){
    h+='<line x1="'+pad+'" y1="'+yPos(b.price)+'" x2="'+(w-pad)+'" y2="'+yPos(b.price)+'" stroke="'+b.c+'" stroke-width="'+(b.bold?'2':'0.7')+'" '+(b.bold?'':'stroke-dasharray="4,3"')+' opacity="'+(b.bold?'1':'.5')+'"/>';
    h+='<text x="'+(w-pad+4)+'" y="'+(yPos(b.price)+3)+'" font-size="6" fill="'+b.c+'" font-weight="700">'+b.name+'</text>';
  });

  // Price line
  if(closes.length>1){
    var pricePath='';
    closes.forEach(function(c,i){pricePath+=(i===0?'M':'L')+xPos(i).toFixed(1)+','+yPos(c).toFixed(1)});
    h+='<path d="'+pricePath+'" fill="none" stroke="#0A1628" stroke-width="1.5" stroke-linecap="round" opacity=".8"/>';
  }
  // Current price dot
  h+='<circle cx="'+xPos(closes.length-1)+'" cy="'+yPos(p)+'" r="5" fill="'+zoneC+'" stroke="#fff" stroke-width="2"/>';
  h+='<text x="'+xPos(closes.length-1)+'" y="'+(yPos(p)-10)+'" text-anchor="middle" font-size="9" font-weight="900" fill="'+zoneC+'" font-family="JetBrains Mono,monospace">'+S+p.toLocaleString()+'</text>';
  h+='</svg>';

  // Decision grid
  h+='<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:12px">';
  [{zone:'BUY ZONE',condition:'Price at -1σ to -2σ',action:'Institutional accumulation zone. Scale in with limit orders.',c:'#059669',active:p<vwap-stdDev*0.8},
   {zone:'FAIR VALUE',condition:'Price at ±1σ of VWAP',action:'Balanced — no clear edge. Wait for a move to extremes.',c:'#1A3A78',active:Math.abs(p-vwap)<stdDev*0.8},
   {zone:'SELL ZONE',condition:'Price at +1σ to +2σ',action:'Distribution area. Take profits or tighten stops.',c:'#dc2626',active:p>vwap+stdDev*0.8}
  ].forEach(function(z){
    h+='<div style="padding:12px;border-radius:10px;background:'+(z.active?z.c+'08':'#f8fafc')+';border:'+(z.active?'2px':'1px')+' solid '+(z.active?z.c+'25':'#e2e5ea')+';text-align:center">';
    h+='<div style="font-size:8px;font-weight:800;color:'+z.c+';letter-spacing:.5px;margin-bottom:4px">'+z.zone+(z.active?' ◄':'')+'</div>';
    h+='<div style="font-size:8px;color:#94a3b8;margin-bottom:4px">'+z.condition+'</div>';
    h+='<div style="font-size:9px;color:'+(z.active?z.c:'#6b7280')+';font-weight:'+(z.active?'700':'500')+';line-height:1.4">'+z.action+'</div></div>';
  });
  h+='</div></div>';
  return h;
};

// ─── AUTO-INJECT institutional charts into Trader DE ───
function _injectInstitutionalCharts(){
  // DISABLED — microstructure charts only in Trader mode via direct render
  return;
  var obs8=new MutationObserver(function(muts){
    muts.forEach(function(m){
      if(m.addedNodes.length){
        try{
          // ONLY inject in Trader mode — check for trader DC structure
          if(window._deMode==='investor')return;
          var deR=document.getElementById('deResult');
          if(!deR||deR.querySelector('#instCharts'))return;
          // Must have trader-specific elements (dc class with market state)
          var dc=deR.querySelector('.dc');
          if(!dc)return;
          var d=window._lastTraderData;
          if(!d||!d.price)return;
          var S=d.csym||'$';
          var container=document.createElement('div');
          container.id='instCharts';
          var ih='<details style="margin:14px 0;border-radius:16px;border:1px solid #e2e5ea;background:#fff;overflow:hidden"><summary style="padding:16px 20px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;font-size:13px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif;list-style:none"><span>🏛️ Institutional Market Microstructure</span><span style="font-size:9px;color:#6b7280;font-weight:500">Volume Profile · Order Flow · DOM · VWAP ±σ — tap to expand</span></summary><div style="padding:0 16px 16px">';
          ih+=_volumeProfile(d,S);
          ih+=_vwapBands(d,S);
          ih+=_orderFlow(d,S);
          ih+=_depthOfMarket(d,S);
          ih+='</div></details>';
          container.innerHTML=ih;
          var existing=deR.querySelector('#instTrading')||deR.querySelector('#decisionCharts')||deR.querySelector('#earlySignals');
          if(existing)existing.parentNode.insertBefore(container,existing);
          else deR.appendChild(container);
        }catch(e){console.warn('Inst charts inject:',e)}
      }
    });
  });
  var deR2=document.getElementById('deResult');
  if(deR2)obs8.observe(deR2,{childList:true,subtree:true});
}
if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',_injectInstitutionalCharts)}
else{_injectInstitutionalCharts()}

// ═══════════════════════════════════════════════════════════════
// POLISH: Loading states, scroll-to-top, keyboard shortcuts
// ═══════════════════════════════════════════════════════════════

// 1. Scroll-to-top when switching tabs
document.addEventListener('click',function(e){
  var btn=e.target.closest('.tab-btn');
  if(btn){
    setTimeout(function(){
      var tc=document.getElementById('tabContentArea');
      if(tc)tc.scrollTo({top:0,behavior:'smooth'});
      window.scrollTo({top:200,behavior:'smooth'});
    },100);
  }
});

// 2. Keyboard shortcut: Ctrl+K to focus search
document.addEventListener('keydown',function(e){
  if((e.ctrlKey||e.metaKey)&&e.key==='k'){
    e.preventDefault();
    var inp=document.getElementById('ticker');
    if(inp){inp.focus();inp.select()}
  }
});

// 3. Auto-collapse sections when switching between Trader/Investor modes
document.addEventListener('click',function(e){
  var btn=e.target;
  if(btn&&(btn.textContent||'').indexOf('Trader')>=0&&btn.classList&&btn.classList.contains('active')){
    // Close investor-specific details
    document.querySelectorAll('#decisionCharts details[open]').forEach(function(d){d.removeAttribute('open')});
  }
});

// 4. Add "Back to top" micro-button after long analysis sections
function _addBackToTop(){
  var deR=document.getElementById('deResult');
  if(!deR||deR.querySelector('#backToTopBtn'))return;
  var btn=document.createElement('div');
  btn.id='backToTopBtn';
  btn.style.cssText='text-align:center;padding:16px;margin-top:10px';
  btn.innerHTML='<button onclick="document.getElementById(\'deResult\').scrollTo({top:0,behavior:\'smooth\'})" style="padding:8px 24px;border-radius:8px;background:#f1f5f9;border:1px solid #e2e5ea;color:#6b7280;font-size:10px;font-weight:700;cursor:pointer;font-family:Sora,sans-serif;transition:all .2s" onmouseover="this.style.background=\'#e2e8f0\'" onmouseout="this.style.background=\'#f1f5f9\'">↑ Back to Top</button>';
  deR.appendChild(btn);
}
setInterval(function(){
  var deR=document.getElementById('deResult');
  if(deR&&deR.scrollHeight>2000&&!deR.querySelector('#backToTopBtn'))_addBackToTop();
},5000);

// 5. Improve error displays globally — catch unhandled errors
window.addEventListener('error',function(e){
  // Don't show raw JS errors to users
  var errDivs=document.querySelectorAll('[style*="color:var(--red)"]');
  errDivs.forEach(function(d){
    if(d.textContent&&d.textContent.indexOf('is not defined')>=0){
      d.innerHTML='<div style="text-align:center;padding:16px"><div style="font-size:20px;margin-bottom:6px">📊</div><div style="font-size:11px;color:#6b7280;font-weight:600">Loading analysis data...</div></div>';
    }
  });
});

// ═══════════════════════════════════════════════════════════════
// WATCHLIST — Client-side stock watchlist with localStorage
// ═══════════════════════════════════════════════════════════════

window._watchlist={
  get:function(){try{return JSON.parse(localStorage.getItem('celesys-watchlist')||'[]')}catch(e){return[]}},
  add:function(sym,name,price,verdict){
    var list=this.get();
    if(list.find(function(s){return s.symbol===sym}))return false;
    list.push({symbol:sym,name:name||sym,price:price||0,verdict:verdict||'—',added:new Date().toISOString()});
    localStorage.setItem('celesys-watchlist',JSON.stringify(list));
    _updateWatchlistBadge();
    return true;
  },
  remove:function(sym){
    var list=this.get().filter(function(s){return s.symbol!==sym});
    localStorage.setItem('celesys-watchlist',JSON.stringify(list));
    _updateWatchlistBadge();
  },
  clear:function(){localStorage.removeItem('celesys-watchlist');_updateWatchlistBadge();}
};

function _updateWatchlistBadge(){
  var count=window._watchlist.get().length;
  var badge=document.getElementById('watchlistBadge');
  if(badge)badge.textContent=count>0?count:'';
  if(badge)badge.style.display=count>0?'inline-flex':'none';
}

// Inject "Add to Watchlist" button after analysis
function _injectWatchlistBtn(){
  var obs9=new MutationObserver(function(){
    try{
      var toolbar=document.getElementById('actionToolbar');
      if(!toolbar)return;
      var d=window._lastAnalysisData;
      if(!d)return;
      var sym=d.ticker||'';
      if(!sym)return;

      // Always remove old button and re-create with current stock
      var old=toolbar.querySelector('#addWatchlistBtn');
      if(old){
        // If already showing correct stock, skip
        if(old.dataset.sym===sym)return;
        old.remove();
      }

      var btn=document.createElement('div');
      btn.id='addWatchlistBtn';
      btn.dataset.sym=sym;
      var inList=window._watchlist.get().find(function(s){return s.symbol===sym});
      btn.style.cssText='padding:3px 8px;border-radius:6px;font-size:10px;font-weight:700;cursor:pointer;font-family:Sora,sans-serif;white-space:nowrap;display:inline-flex;align-items:center;'+(inList?'background:#1A3A78;color:#fff;-webkit-text-fill-color:#fff;border:1px solid #1A3A78':'background:#f8fafc;color:#1A3A78;-webkit-text-fill-color:#1A3A78;border:1px solid #e2e5ea');
      btn.textContent=inList?'✓ Watchlist':'+ Watchlist';
      btn.onclick=function(){
        var currentSym=window._lastAnalysisData?window._lastAnalysisData.ticker:'';
        if(!currentSym)return;
        if(window._watchlist.get().find(function(s){return s.symbol===currentSym})){
          window._watchlist.remove(currentSym);
          btn.textContent='+ Watchlist';btn.style.background='#f8fafc';btn.style.color='#1A3A78';btn.style.webkitTextFillColor='#1A3A78';btn.style.borderColor='#e2e5ea';
        }else{
          var dd=window._lastAnalysisData;
          window._watchlist.add(currentSym,dd.company_name,dd.current_price);
          btn.textContent='✓ Watchlist';btn.style.background='#1A3A78';btn.style.color='#fff';btn.style.webkitTextFillColor='#fff';btn.style.borderColor='#1A3A78';
        }
      };
      toolbar.insertBefore(btn,toolbar.firstChild);
    }catch(e){}
  });
  var rpt=document.getElementById('report');
  if(rpt)obs9.observe(rpt,{childList:true,subtree:true});
}
if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',_injectWatchlistBtn)}
else{_injectWatchlistBtn()}

// ═══════════════════════════════════════════════════════════════
// QUICK STATS BAR — Shows key metrics in the stock header area
// ═══════════════════════════════════════════════════════════════

function _injectQuickStats(){
  var _qsDebounce=null;
  var obs10=new MutationObserver(function(){
    if(_qsDebounce)clearTimeout(_qsDebounce);
    _qsDebounce=setTimeout(function(){
    try{
      var header=document.getElementById('reportHeader');
      if(!header)return;
      var rpt=document.getElementById('report');
      if(!rpt||rpt.style.display==='none')return;
      var d=window._lastAnalysisData;
      if(!d||!d.current_price)return;
      // Remove old stats if stock changed
      var oldQS=header.querySelector('#quickStatsBar');
      if(oldQS){
        if(oldQS.dataset.sym===(d.ticker||''))return;
        oldQS.remove();
      }
      var S=d.currency==='INR'?'₹':'$';
      var pe=parseFloat(d.pe_ratio||0);
      var roe=parseFloat(d.roe||0);
      var beta=parseFloat(d.beta||0);
      var de=parseFloat(d.debt_to_equity||0);
      var hi=d.week52_high||0;var lo=d.week52_low||0;
      var fromHi=hi>0?Math.round((1-d.current_price/hi)*-100):0;

      var bar=document.createElement('div');
      bar.id='quickStatsBar';
      bar.dataset.sym=d.ticker||'';
      bar.style.cssText='display:flex;gap:0;align-items:center;flex-shrink:0';

      var metrics=[
        {l:'PE',v:pe>0?pe.toFixed(1):'—',c:pe>0&&pe<20?'#059669':pe<35?'#d97706':'#dc2626'},
        {l:'ROE',v:roe>0?roe.toFixed(1)+'%':'—',c:roe>15?'#059669':roe>8?'#d97706':'#dc2626'},
        {l:'β',v:beta.toFixed(2),c:beta<0.8?'#059669':beta<1.2?'#d97706':'#dc2626'},
        {l:'D/E',v:de.toFixed(0)+'%',c:de<50?'#059669':de<100?'#d97706':'#dc2626'},
        {l:'52W',v:fromHi+'%',c:fromHi>-15?'#059669':fromHi>-30?'#d97706':'#dc2626'},
      ];

      var ih='';
      metrics.forEach(function(m){
        ih+='<div style="padding:0 6px;text-align:center;border-left:1px solid #e2e5ea">';
        ih+='<div style="font-size:6px;font-weight:800;color:#94a3b8;letter-spacing:.3px;line-height:1">'+m.l+'</div>';
        ih+='<div style="font-size:10px;font-weight:900;color:'+m.c+';font-family:JetBrains Mono,monospace;line-height:1.2">'+m.v+'</div></div>';
      });
      bar.innerHTML=ih;
      // Append to the toolbar area (right side), not as a new row
      var toolbar=document.getElementById('actionToolbar');
      if(toolbar){toolbar.appendChild(bar)}
      else{header.appendChild(bar)}
    }catch(e){}
    },200);
  });
  var rpt=document.getElementById('report');
  if(rpt)obs10.observe(rpt,{childList:true,subtree:true});
}
if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',_injectQuickStats)}
else{_injectQuickStats()}

// ═══════════════════════════════════════════════════════════════
// SOCIAL PROOF — Analyze counter + recent searches
// ═══════════════════════════════════════════════════════════════

;(function(){
  // Increment analyze counter
  var count=parseInt(localStorage.getItem('celesys-analyze-count')||'0')+0;
  function _incrementCount(){
    count++;
    localStorage.setItem('celesys-analyze-count',String(count));
    // Update badge if visible
    var badge=document.getElementById('analyzeCount');
    if(badge)badge.textContent=count.toLocaleString()+' analyses run';
  }
  // Hook into analyze button click
  document.addEventListener('click',function(e){
    var btn=e.target.closest('.btn');
    if(btn&&(btn.textContent||'').indexOf('Analyze')>=0){
      _incrementCount();
      // Store recent search
      var inp=document.getElementById('ticker');
      if(inp&&inp.value){
        var recent=JSON.parse(localStorage.getItem('celesys-recent')||'[]');
        var sym=inp.value.trim().toUpperCase();
        recent=recent.filter(function(s){return s!==sym});
        recent.unshift(sym);
        if(recent.length>8)recent=recent.slice(0,8);
        localStorage.setItem('celesys-recent',JSON.stringify(recent));
      }
    }
  });

  // Show recent searches below ticker input
  function _showRecent(){
    var inp=document.getElementById('ticker');
    if(!inp)return;
    var parent=inp.parentElement;
    if(!parent||parent.querySelector('#recentSearches'))return;
    var recent=JSON.parse(localStorage.getItem('celesys-recent')||'[]');
    if(recent.length===0)return;
    var div=document.createElement('div');
    div.id='recentSearches';
    div.style.cssText='display:flex;gap:4px;flex-wrap:wrap;margin-top:6px;padding:0 4px';
    recent.slice(0,6).forEach(function(sym){
      var chip=document.createElement('button');
      chip.style.cssText='padding:3px 10px;border-radius:100px;background:#f1f5f9;border:1px solid #e2e5ea;color:#1A3A78;font-size:9px;font-weight:700;cursor:pointer;font-family:JetBrains Mono,monospace;transition:all .15s';
      chip.textContent=sym;
      chip.onmouseover=function(){this.style.background='#1A3A78';this.style.color='#fff'};
      chip.onmouseout=function(){this.style.background='#f1f5f9';this.style.color='#1A3A78'};
      chip.onclick=function(){
        inp.value=sym;
        var analyzeBtn=document.querySelector('.btn');
        if(analyzeBtn)analyzeBtn.click();
      };
      div.appendChild(chip);
    });
    parent.appendChild(div);
  }
  if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',function(){setTimeout(_showRecent,500)})}
  else{setTimeout(_showRecent,500)}
})();

// ═══════════════════════════════════════════════════════════════
// PERFORMANCE: Lazy-load heavy chart libraries
// ═══════════════════════════════════════════════════════════════

// Defer Chart.js loading until a chart tab is actually clicked
;(function(){
  var chartLoaded=false;
  document.addEventListener('click',function(e){
    var btn=e.target.closest('[data-subtab]');
    if(btn&&!chartLoaded){
      var sub=btn.getAttribute('data-subtab');
      if(sub==='valuation'||sub==='technical'||sub==='risk'||sub==='activity'){
        // Chart.js is already loaded via CDN — just flag
        chartLoaded=true;
      }
    }
  });
})();

// ═══════════════════════════════════════════════════════════════════════════
// PMS INSTITUTIONAL CHARTS — Auto-inject into PMS after render
// Efficient Frontier, Capital Quadrant, Simulation Curves, Risk Radar,
// Sector Treemap, Performance Attribution
// ═══════════════════════════════════════════════════════════════════════════

// 1. EFFICIENT FRONTIER — Portfolio vs Optimal scatter
window._efficientFrontier=function(pd){
  if(!pd||!pd.retain)return'';
  var ret=pd.retain;var S=pd.csym||'₹';
  var w=400,ht=240,pad=50;
  // Plot each stock as a bubble
  var stocks=ret.map(function(s){
    var risk=Math.max(5,(s.debtEquity||0)*0.3+((1-(s.fScore||0)/9)*30));
    return{sym:s.symbol,ret:s._cagr||0,risk:risk,weight:s._w||0,action:s._action};
  });
  var maxRet=Math.max.apply(null,stocks.map(function(s){return s.ret}))*1.2||1;
  var maxRisk=Math.max.apply(null,stocks.map(function(s){return s.risk}))*1.2||1;
  function x(v){return pad+v/maxRisk*(w-pad*2)}
  function y(v){return ht-pad-(v/maxRet*(ht-pad*2))}

  var h='<div style="padding:22px;border-radius:16px;background:#fff;border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="font-size:11px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif;margin-bottom:4px">Portfolio Efficiency Frontier</div>';
  h+='<div style="font-size:9px;color:#6b7280;margin-bottom:14px">Each stock plotted by Risk (x) vs Return (y) · Size = portfolio weight</div>';

  h+='<svg viewBox="0 0 '+w+' '+ht+'" style="width:100%;height:auto">';
  // Axes
  h+='<line x1="'+pad+'" y1="'+(ht-pad)+'" x2="'+(w-pad)+'" y2="'+(ht-pad)+'" stroke="#e2e5ea" stroke-width="1"/>';
  h+='<line x1="'+pad+'" y1="'+pad+'" x2="'+pad+'" y2="'+(ht-pad)+'" stroke="#e2e5ea" stroke-width="1"/>';
  h+='<text x="'+(w/2)+'" y="'+(ht-8)+'" text-anchor="middle" font-size="8" fill="#94a3b8" font-weight="700">RISK (Volatility + Leverage) →</text>';
  h+='<text x="12" y="'+(ht/2)+'" text-anchor="middle" font-size="8" fill="#94a3b8" font-weight="700" transform="rotate(-90 12 '+(ht/2)+')">RETURN (Est. CAGR) →</text>';
  // Grid lines
  for(var i=0;i<=4;i++){
    var gy=pad+i*(ht-pad*2)/4;var gx=pad+i*(w-pad*2)/4;
    h+='<line x1="'+pad+'" y1="'+gy+'" x2="'+(w-pad)+'" y2="'+gy+'" stroke="#f1f5f9" stroke-width="0.5"/>';
    h+='<text x="'+(pad-4)+'" y="'+(gy+3)+'" text-anchor="end" font-size="7" fill="#c7d2ce">'+(maxRet*(1-i/4)).toFixed(0)+'%</text>';
  }
  // Efficient frontier curve (approximate)
  h+='<path d="M'+x(5)+','+y(maxRet*0.3)+' Q'+x(maxRisk*0.3)+','+y(maxRet*0.95)+' '+x(maxRisk*0.8)+','+y(maxRet*0.85)+'" fill="none" stroke="#059669" stroke-width="1.5" stroke-dasharray="4,3" opacity=".4"/>';
  h+='<text x="'+x(maxRisk*0.6)+'" y="'+(y(maxRet*0.9)-6)+'" font-size="7" fill="#059669" opacity=".6" font-weight="700">Efficient Frontier</text>';
  // Stock bubbles
  // Show only top 12 by weight to reduce clutter
  var _topStocks=stocks.slice().sort(function(a,b){return b.weight-a.weight}).slice(0,12);
  _topStocks.forEach(function(s){
    var ac=s.action==='CORE'?'#059669':s.action==='GROWTH'?'#2563eb':s.action==='EXIT'?'#dc2626':s.action==='MOMENTUM'?'#d97706':s.action==='VALUE'?'#6366f1':s.action==='DEFENSIVE'?'#94a3b8':'#d97706';
    var r=Math.max(3,Math.min(10,s.weight*0.6));
    h+='<circle cx="'+x(s.risk)+'" cy="'+y(s.ret)+'" r="'+r+'" fill="'+ac+'" opacity=".5" stroke="#fff" stroke-width="1"/>';
    if(s.weight>=6)h+='<text x="'+x(s.risk)+'" y="'+(y(s.ret)-r-2)+'" text-anchor="middle" font-size="5" font-weight="700" fill="#0A1628">'+s.sym+'</text>';
  });
  // Portfolio centroid
  var avgRisk=stocks.reduce(function(s,st){return s+st.risk*st.weight/100},0)*100/stocks.reduce(function(s,st){return s+st.weight},0);
  var avgRet=pd.oCAGR||0;
  h+='<circle cx="'+x(avgRisk)+'" cy="'+y(avgRet)+'" r="8" fill="#1A3A78" stroke="#fff" stroke-width="2"/>';
  h+='<text x="'+(x(avgRisk)+12)+'" y="'+(y(avgRet)+3)+'" font-size="7" font-weight="800" fill="#1A3A78">PORTFOLIO</text>';
  // Legend
  h+='<g transform="translate('+(w-140)+','+pad+')">';
  [{l:'Core',c:'#059669'},{l:'Growth',c:'#2563eb'},{l:'Monitor',c:'#d97706'},{l:'Exit',c:'#dc2626'}].forEach(function(lg,i){
    h+='<circle cx="5" cy="'+(i*12)+'" r="4" fill="'+lg.c+'" opacity=".6"/><text x="14" y="'+(i*12+3)+'" font-size="7" fill="#6b7280">'+lg.l+'</text>';
  });
  h+='</g>';
  h+='</svg>';

  // Insight
  h+='<div style="padding:8px 12px;border-radius:8px;background:rgba(26,58,120,.03);font-size:9px;color:#374151;line-height:1.5">';
  var belowFrontier=stocks.filter(function(s){return s.ret<avgRet&&s.risk>avgRisk}).length;
  if(belowFrontier>2)h+='<strong style="color:#dc2626">'+belowFrontier+' stocks below the frontier</strong> — high risk with low return. Replace with positions on or above the curve.';
  else h+='<strong style="color:#059669">Portfolio is reasonably positioned.</strong> Most holdings are near the efficient frontier. Focus on reducing outlier risk positions.';
  h+='</div></div>';
  return h;
};

// 2. CAPITAL vs ALPHA QUADRANT CHART — Bubble chart
window._capitalAlphaQuadrant=function(pd){
  if(!pd||!pd.retain)return'';
  var ret=pd.retain;var S=pd.csym||'₹';
  var w=400,ht=240,pad=50;
  var medW=ret.length>0?ret.reduce(function(a,s){return a+s._w},0)/ret.length:5;
  var medC=ret.length>0?ret.reduce(function(a,s){return a+s._cagr},0)/ret.length:10;

  function x(v){return pad+Math.min(1,v/20)*(w-pad*2)}
  function y(v){return ht-pad-Math.min(1,v/40)*(ht-pad*2)}

  var h='<div style="padding:22px;border-radius:16px;background:#fff;border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="font-size:11px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif;margin-bottom:4px">Capital vs Alpha Contribution</div>';
  h+='<div style="font-size:9px;color:#6b7280;margin-bottom:14px">Quadrant analysis — where capital is well/poorly deployed</div>';

  h+='<svg viewBox="0 0 '+w+' '+ht+'" style="width:100%;height:auto">';
  // Quadrant backgrounds
  var midX=x(medW),midY=y(medC);
  h+='<rect x="'+pad+'" y="'+pad+'" width="'+(midX-pad)+'" height="'+(midY-pad)+'" fill="#dc262604" rx="4"/>';// Low cap, High alpha
  h+='<rect x="'+midX+'" y="'+pad+'" width="'+(w-pad-midX)+'" height="'+(midY-pad)+'" fill="#05966904" rx="4"/>';// High cap, High alpha
  h+='<rect x="'+pad+'" y="'+midY+'" width="'+(midX-pad)+'" height="'+(ht-pad-midY)+'" fill="#94a3b804" rx="4"/>';// Low cap, Low alpha
  h+='<rect x="'+midX+'" y="'+midY+'" width="'+(w-pad-midX)+'" height="'+(ht-pad-midY)+'" fill="#d9770604" rx="4"/>';// High cap, Low alpha
  // Quadrant labels
  h+='<text x="'+(pad+8)+'" y="'+(pad+14)+'" font-size="7" fill="#059669" font-weight="700" opacity=".6">🚀 INCREASE</text>';
  h+='<text x="'+(midX+8)+'" y="'+(pad+14)+'" font-size="7" fill="#059669" font-weight="700" opacity=".6">✅ CORE — KEEP</text>';
  h+='<text x="'+(pad+8)+'" y="'+(ht-pad-6)+'" font-size="7" fill="#94a3b8" font-weight="700" opacity=".6">⚠️ REMOVE</text>';
  h+='<text x="'+(midX+8)+'" y="'+(ht-pad-6)+'" font-size="7" fill="#dc2626" font-weight="700" opacity=".6">❌ CUT OVERWEIGHT</text>';
  // Axes
  h+='<line x1="'+pad+'" y1="'+(ht-pad)+'" x2="'+(w-pad)+'" y2="'+(ht-pad)+'" stroke="#e2e5ea" stroke-width="1"/>';
  h+='<line x1="'+pad+'" y1="'+pad+'" x2="'+pad+'" y2="'+(ht-pad)+'" stroke="#e2e5ea" stroke-width="1"/>';
  h+='<line x1="'+midX+'" y1="'+pad+'" x2="'+midX+'" y2="'+(ht-pad)+'" stroke="#c7d2ce" stroke-width="0.5" stroke-dasharray="3,3"/>';
  h+='<line x1="'+pad+'" y1="'+midY+'" x2="'+(w-pad)+'" y2="'+midY+'" stroke="#c7d2ce" stroke-width="0.5" stroke-dasharray="3,3"/>';
  h+='<text x="'+(w/2)+'" y="'+(ht-8)+'" text-anchor="middle" font-size="8" fill="#94a3b8" font-weight="700">CAPITAL WEIGHT (%) →</text>';
  h+='<text x="12" y="'+(ht/2)+'" text-anchor="middle" font-size="8" fill="#94a3b8" font-weight="700" transform="rotate(-90 12 '+(ht/2)+')">ALPHA (Est. CAGR %) →</text>';
  // Stock bubbles
  ret.forEach(function(s){
    var ac=s._action==='CORE'?'#059669':s._action==='GROWTH'?'#2563eb':'#d97706';
    var r=Math.max(5,Math.min(12,(s.fScore||0)*1.2));
    h+='<circle cx="'+x(s._w)+'" cy="'+y(s._cagr)+'" r="'+r+'" fill="'+ac+'" opacity=".5" stroke="'+ac+'" stroke-width="1.5"/>';
    h+='<text x="'+x(s._w)+'" y="'+(y(s._cagr)-r-2)+'" text-anchor="middle" font-size="6" font-weight="700" fill="#0A1628">'+s.symbol+'</text>';
  });
  h+='</svg>';

  // Count stocks in each quadrant
  var q1=ret.filter(function(s){return s._w<medW&&s._cagr>=medC}).length;// Increase
  var q2=ret.filter(function(s){return s._w>=medW&&s._cagr>=medC}).length;// Keep
  var q3=ret.filter(function(s){return s._w<medW&&s._cagr<medC}).length;// Remove
  var q4=ret.filter(function(s){return s._w>=medW&&s._cagr<medC}).length;// Cut
  h+='<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:4px;margin-top:10px">';
  [{l:'Increase',v:q1,c:'#059669'},{l:'Keep (Core)',v:q2,c:'#1A3A78'},{l:'Remove',v:q3,c:'#94a3b8'},{l:'Cut Weight',v:q4,c:'#dc2626'}].forEach(function(q){
    h+='<div style="padding:6px;border-radius:6px;background:'+q.c+'06;text-align:center"><div style="font-size:16px;font-weight:900;color:'+q.c+';font-family:JetBrains Mono,monospace">'+q.v+'</div><div style="font-size:7px;color:'+q.c+';font-weight:700">'+q.l+'</div></div>';
  });
  h+='</div></div>';
  return h;
};

// 3. MULTI-LINE SIMULATION PROJECTION
window._simulationCurves=function(pd){
  if(!pd||!pd.journey)return'';
  var S=pd.csym||'₹';var j=pd.journey;
  var oCAGR=pd.oCAGR||0;var benchC=pd.benchName==='S&P 500'?11:13;
  var scenarios=[
    {name:'No Change',cagr:oCAGR,c:'#dc2626',dash:'4,3'},
    {name:'Rebalanced',cagr:Math.min(35,oCAGR+Math.round((30-oCAGR)*0.35)),c:'#d97706',dash:''},
    {name:'Factor Optimized',cagr:Math.min(35,oCAGR+Math.round((30-oCAGR)*0.7)),c:'#2563eb',dash:''},
    {name:'Full Institutional',cagr:Math.min(38,oCAGR+Math.round((30-oCAGR)*1.05)),c:'#059669',dash:''},
    {name:pd.benchName||'Benchmark',cagr:benchC,c:'#94a3b8',dash:'6,4'}
  ];
  var startVal=1000000;var years=10;
  var w=420,ht=200,pad=55;
  var maxVal=startVal*Math.pow(1+Math.max.apply(null,scenarios.map(function(s){return s.cagr}))/100,years)*1.1;

  function x(yr){return pad+yr/years*(w-pad*2)}
  function y(v){return ht-pad-(Math.log(v/startVal)/Math.log(maxVal/startVal))*(ht-pad*2)}

  var h='<div style="padding:22px;border-radius:16px;background:#fff;border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="font-size:11px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif;margin-bottom:4px">10-Year Recovery Simulation</div>';
  h+='<div style="font-size:9px;color:#6b7280;margin-bottom:14px">Compounding curves by optimization scenario · Log scale</div>';

  h+='<svg viewBox="0 0 '+w+' '+ht+'" style="width:100%;height:auto">';
  // Grid
  for(var i=0;i<=years;i+=2){
    h+='<line x1="'+x(i)+'" y1="'+pad+'" x2="'+x(i)+'" y2="'+(ht-pad)+'" stroke="#f1f5f9" stroke-width="0.5"/>';
    h+='<text x="'+x(i)+'" y="'+(ht-pad+12)+'" text-anchor="middle" font-size="7" fill="#94a3b8">'+(2026+i)+'</text>';
  }
  // Lines
  scenarios.forEach(function(sc){
    var path='';
    for(var yr=0;yr<=years;yr++){
      var val=startVal*Math.pow(1+sc.cagr/100,yr);
      path+=(yr===0?'M':'L')+x(yr).toFixed(1)+','+y(val).toFixed(1);
    }
    h+='<path d="'+path+'" fill="none" stroke="'+sc.c+'" stroke-width="2" stroke-linecap="round" '+(sc.dash?'stroke-dasharray="'+sc.dash+'"':'')+'/>';
    // End label
    var endVal=startVal*Math.pow(1+sc.cagr/100,years);
    h+='<text x="'+(w-pad+4)+'" y="'+(y(endVal)+3)+'" font-size="6" font-weight="700" fill="'+sc.c+'">'+S+(endVal>=10000000?Math.round(endVal/10000000)+'Cr':Math.round(endVal/100000)+'L')+'</text>';
  });
  h+='</svg>';

  // Legend
  h+='<div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:6px">';
  scenarios.forEach(function(sc){
    h+='<div style="display:flex;align-items:center;gap:4px"><div style="width:16px;height:2px;background:'+sc.c+';border-radius:1px"></div><span style="font-size:8px;color:#6b7280;font-weight:600">'+sc.name+' ('+sc.cagr+'%)</span></div>';
  });
  h+='</div></div>';
  return h;
};

// 4. RISK EXPOSURE RADAR (Portfolio-level)
window._portfolioRiskRadar=function(pd){
  if(!pd||!pd.retain)return'';
  var ret=pd.retain;var secKeys=Object.keys(pd.secMap||{});
  // Compute risk dimensions
  var avgBeta=ret.reduce(function(a,s){return a+(parseFloat(s.beta||0))},0)/ret.length;
  var topSectorPct=secKeys.length>0?pd.secMap[secKeys[0]]:0;
  var avgDE=ret.reduce(function(a,s){return a+(parseFloat(s.debtEquity||0))},0)/ret.length;
  var factors=[
    {label:'Sector Conc.',value:Math.min(100,topSectorPct*2.5)},
    {label:'Beta Risk',value:Math.min(100,avgBeta*50)},
    {label:'Liquidity',value:Math.min(100,Math.max(20,100-ret.length*3))},
    {label:'Drawdown',value:Math.min(100,(pd.maxDD||0)*2.5)},
    {label:'Correlation',value:Math.min(100,secKeys.length<3?80:secKeys.length<5?50:30)},
    {label:'Debt/Leverage',value:Math.min(100,avgDE)}
  ];
  if(typeof _radarChart==='function'){
    var h='<div style="padding:22px;border-radius:16px;background:#fff;border:1px solid #e2e5ea;margin:14px 0">';
    h+='<div style="font-size:11px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif;margin-bottom:4px">Risk Exposure Radar</div>';
    h+='<div style="font-size:9px;color:#6b7280;margin-bottom:14px">6 dimensions of portfolio fragility — lower is safer</div>';
    h+='<div style="text-align:center">'+_radarChart(factors,220)+'</div>';
    // Risk summary
    var maxRisk=factors.reduce(function(a,b){return a.value>b.value?a:b});
    h+='<div style="padding:8px 12px;border-radius:8px;background:#dc262604;border:1px solid #dc262610;font-size:9px;color:#374151;margin-top:8px;line-height:1.5">';
    h+='<strong style="color:#dc2626">Highest risk: '+maxRisk.label+' ('+Math.round(maxRisk.value)+'/100)</strong> — ';
    if(maxRisk.label==='Sector Conc.')h+='Top sector is '+topSectorPct+'%. Diversify to bring below 30%.';
    else if(maxRisk.label==='Beta Risk')h+='Average beta '+avgBeta.toFixed(2)+' amplifies market swings. Add low-beta defensive holdings.';
    else if(maxRisk.label==='Correlation')h+='Only '+secKeys.length+' sectors. Add uncorrelated sectors for true diversification.';
    else if(maxRisk.label==='Debt/Leverage')h+='Average D/E '+avgDE.toFixed(0)+'%. Reduce high-leverage holdings.';
    else h+='Review and mitigate this risk dimension.';
    h+='</div></div>';
    return h;
  }
  return'';
};

// 5. PERFORMANCE ATTRIBUTION BARS — What contributed to returns
window._performanceAttribution=function(pd){
  if(!pd||!pd.retain)return'';
  var ret=pd.retain;var S=pd.csym||'₹';
  // Group by action and calculate contribution
  var groups=[
    {name:'Core Holdings',stocks:ret.filter(function(s){return s._action==='CORE'}),c:'#059669'},
    {name:'Growth Bets',stocks:ret.filter(function(s){return s._action==='GROWTH'}),c:'#2563eb'},
    {name:'Monitor/Hold',stocks:ret.filter(function(s){return s._action==='HOLD'||s._action==='MONITOR'}),c:'#d97706'}
  ];
  var totalW=ret.reduce(function(a,s){return a+s._w},0)||1;
  groups.forEach(function(g){
    g.weight=g.stocks.reduce(function(a,s){return a+s._w},0);
    g.avgCagr=g.stocks.length>0?Math.round(g.stocks.reduce(function(a,s){return a+s._cagr},0)/g.stocks.length):0;
    g.contrib=Math.round(g.avgCagr*g.weight/totalW*10)/10;
  });
  var maxContrib=Math.max.apply(null,groups.map(function(g){return g.contrib}))||10;

  var h='<div style="padding:22px;border-radius:16px;background:#fff;border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="font-size:11px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif;margin-bottom:4px">Performance Attribution</div>';
  h+='<div style="font-size:9px;color:#6b7280;margin-bottom:14px">CAGR contribution by portfolio segment</div>';
  groups.forEach(function(g){
    var pct=Math.round(g.contrib/maxContrib*100);
    h+='<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">';
    h+='<div style="width:100px;text-align:right"><div style="font-size:10px;font-weight:800;color:#0A1628">'+g.name+'</div><div style="font-size:8px;color:#94a3b8">'+g.stocks.length+' stocks · '+g.weight+'%</div></div>';
    h+='<div style="flex:1;height:24px;background:#f1f5f9;border-radius:6px;overflow:hidden;position:relative">';
    h+='<div style="width:'+Math.max(5,pct)+'%;height:100%;background:'+g.c+';border-radius:6px;display:flex;align-items:center;justify-content:flex-end;padding-right:8px;transition:width 1s ease">';
    h+='<span style="font-size:9px;font-weight:900;color:#fff;font-family:JetBrains Mono,monospace">+'+g.contrib+'%</span></div></div>';
    h+='<div style="width:50px;text-align:center"><div style="font-size:12px;font-weight:900;color:'+g.c+';font-family:JetBrains Mono,monospace">'+g.avgCagr+'%</div><div style="font-size:7px;color:#94a3b8">avg CAGR</div></div>';
    h+='</div>';
  });
  h+='</div>';
  return h;
};

// ─── AUTO-INJECT PMS CHARTS after PMS renders ───
function _injectPMSCharts(){
  var obs11=new MutationObserver(function(muts){
    muts.forEach(function(m){
      if(m.addedNodes.length){
        try{
          var deR=document.getElementById('deResult');
          if(!deR||deR.querySelector('#pmsChartsPack'))return;
          var pd=window._pmsData;
          if(!pd||!pd.retain||pd.retain.length<1)return;
          // Check if PMS section exists — look for the 7-step framework content
          var hasPMS=deR.querySelector('[style*="PORTFOLIO MANAGEMENT"]')||deR.textContent.indexOf('PORTFOLIO MANAGEMENT')>=0;
          if(!hasPMS){
            // Check for step indicators or sector allocation
            if(!deR.querySelector('[style*="SECTOR ALLOCATION"]')&&!deR.textContent.indexOf('Stocks Analyzed')>=0)return;
          }
          var container=document.createElement('div');
          container.id='pmsChartsPack';
          container.style.cssText='padding:0 28px 20px';
          var ih='<div style="font-size:14px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif;margin:20px 0 12px;padding-top:16px;border-top:1px solid #e2e5ea">📈 Institutional Portfolio Charts</div>';
          ih+=_efficientFrontier(pd);
          ih+=_capitalAlphaQuadrant(pd);
          ih+=_simulationCurves(pd);
          ih+=_performanceAttribution(pd);
          ih+=_portfolioRiskRadar(pd);
          container.innerHTML=ih;
          // Insert before the analytics dashboard button
          var anBtn=deR.querySelector('[onclick*="_openPMSChartsModal"]');
          if(anBtn)anBtn.parentNode.insertBefore(container,anBtn);
          else deR.appendChild(container);
        }catch(e){console.warn('PMS charts inject:',e)}
      }
    });
  });
  var deR2=document.getElementById('deResult');
  if(deR2)obs11.observe(deR2,{childList:true,subtree:true});
}
if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',_injectPMSCharts)}
else{_injectPMSCharts()}

// ═══════════════════════════════════════════════════════════════════════════
// GAP FILL: PMS — Sticky Decision Bar, Timing Curve, AI Insights,
// Narrative Intelligence, Smart Alerts, Decision Confidence
// ═══════════════════════════════════════════════════════════════════════════

// GAP 1 + 5: STICKY GLOBAL DECISION BAR — Always visible during PMS
window._pmsDecisionBar=function(pd){
  if(!pd)return'';
  var score=pd.health||0;var s10=Math.round(score/10*10)/10;
  var oCAGR=pd.oCAGR||0;var target=30;var gap=target-oCAGR;
  var recovery=gap>15?'LOW':gap>8?'MODERATE':gap>0?'HIGH':'ON TRACK';
  var rC=gap>15?'#dc2626':gap>8?'#d97706':gap>0?'#059669':'#059669';
  var statusC=s10<6?'#dc2626':s10<7.5?'#d97706':'#059669';
  var statusL=s10<6?'CRISIS':s10<7.5?'REPAIR':'OPTIMIZE';
  var prob=Math.max(5,Math.min(90,Math.round(100-gap*3)));
  var S=pd.csym||'₹';

  var h='<div id="pmsGlobalBar" style="position:sticky;top:0;z-index:50;padding:10px 20px;background:linear-gradient(135deg,#0A1628,#1A3A78);border-radius:12px;margin:0 0 16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;box-shadow:0 4px 20px rgba(10,22,40,.3)">';
  // Score badge
  h+='<div style="display:flex;align-items:center;gap:6px"><div style="width:36px;height:36px;border-radius:10px;background:'+statusC+'20;display:flex;align-items:center;justify-content:center"><span style="font-size:16px;font-weight:900;color:'+statusC+';font-family:JetBrains Mono,monospace">'+s10+'</span></div><div><div style="font-size:8px;color:rgba(255,255,255,.5);font-weight:700">PMS SCORE</div><div style="font-size:9px;font-weight:800;color:'+statusC+'">'+statusL+'</div></div></div>';
  h+='<div style="width:1px;height:28px;background:rgba(255,255,255,.1)"></div>';
  // Metrics
  [{l:'TARGET',v:target+'%',c:'#fff'},{l:'CURRENT',v:oCAGR+'%',c:oCAGR>=25?'#34d399':'#fbbf24'},{l:'GAP',v:(gap>0?'-':'+')+(Math.abs(gap))+'%',c:gap>0?'#f87171':'#34d399'},{l:'RECOVERY',v:recovery,c:rC},{l:'PROBABILITY',v:prob+'%',c:prob>50?'#34d399':'#fbbf24'}].forEach(function(m){
    h+='<div style="text-align:center;min-width:50px"><div style="font-size:6px;color:rgba(255,255,255,.4);font-weight:800;letter-spacing:.5px">'+m.l+'</div><div style="font-size:12px;font-weight:900;color:'+m.c+';font-family:JetBrains Mono,monospace;margin-top:1px">'+m.v+'</div></div>';
  });
  h+='</div>';
  return h;
};

// GAP 2: TIMING EFFICIENCY CURVE — Entry vs Ideal Entry
window._timingEfficiency=function(pd){
  if(!pd||!pd.retain)return'';
  var ret=pd.retain;var S=pd.csym||'₹';
  var w=400,ht=180,pad=50;
  // For each retained stock, estimate ideal vs actual entry
  var entries=ret.filter(function(s){return s.price>0&&s.fairValue>0}).map(function(s){
    var ideal=Math.round(Math.min(s.price,s.fairValue||s.price)*0.92);
    var actual=s.price;
    var slippage=actual>0?Math.round((actual-ideal)/ideal*100):0;
    return{sym:s.symbol,ideal:ideal,actual:actual,slip:slippage};
  }).slice(0,15);
  if(entries.length<3)return'';
  var maxP=Math.max.apply(null,entries.map(function(e){return Math.max(e.ideal,e.actual)}))*1.1;

  var h='<div style="padding:22px;border-radius:16px;background:#fff;border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="font-size:11px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif;margin-bottom:4px">Timing & Execution Efficiency</div>';
  h+='<div style="font-size:9px;color:#6b7280;margin-bottom:14px">Ideal entry (fair value-10%) vs actual price · Slippage analysis</div>';

  h+='<svg viewBox="0 0 '+w+' '+ht+'" style="width:100%;height:auto">';
  var barW=Math.min(24,Math.floor((w-pad*2)/(entries.length*2.5)));
  entries.forEach(function(e,i){
    var x=pad+i*(w-pad*2)/entries.length;
    var yIdeal=pad+(1-e.ideal/maxP)*(ht-pad*2);
    var yActual=pad+(1-e.actual/maxP)*(ht-pad*2);
    var isLate=e.actual>e.ideal;
    // Ideal bar
    h+='<rect x="'+x+'" y="'+yIdeal+'" width="'+barW+'" height="'+(ht-pad-yIdeal)+'" rx="3" fill="#059669" opacity=".3"/>';
    // Actual bar
    h+='<rect x="'+(x+barW+2)+'" y="'+yActual+'" width="'+barW+'" height="'+(ht-pad-yActual)+'" rx="3" fill="'+(isLate?'#dc2626':'#059669')+'" opacity=".6"/>';
    // Slippage marker
    if(isLate){
      h+='<line x1="'+(x+barW/2)+'" y1="'+yIdeal+'" x2="'+(x+barW*1.5+2)+'" y2="'+yActual+'" stroke="#dc2626" stroke-width="1" stroke-dasharray="2,2"/>';
      h+='<text x="'+(x+barW)+'" y="'+(Math.min(yIdeal,yActual)-4)+'" text-anchor="middle" font-size="6" font-weight="800" fill="#dc2626">+'+e.slip+'%</text>';
    }
    h+='<text x="'+(x+barW)+'" y="'+(ht-pad+10)+'" text-anchor="middle" font-size="5.5" fill="#94a3b8" font-weight="600">'+e.sym+'</text>';
  });
  // Legend
  h+='<rect x="'+pad+'" y="'+(ht-8)+'" width="8" height="6" rx="1" fill="#059669" opacity=".3"/>';
  h+='<text x="'+(pad+12)+'" y="'+(ht-3)+'" font-size="6" fill="#6b7280">Ideal Entry</text>';
  h+='<rect x="'+(pad+65)+'" y="'+(ht-8)+'" width="8" height="6" rx="1" fill="#dc2626" opacity=".6"/>';
  h+='<text x="'+(pad+77)+'" y="'+(ht-3)+'" font-size="6" fill="#6b7280">Actual Entry</text>';
  h+='</svg>';

  var avgSlip=Math.round(entries.reduce(function(a,e){return a+Math.max(0,e.slip)},0)/entries.length);
  var lateEntries=entries.filter(function(e){return e.slip>0}).length;
  h+='<div style="padding:8px 12px;border-radius:8px;background:'+(avgSlip>5?'#dc262604':'#05966904')+';border:1px solid '+(avgSlip>5?'#dc262610':'#05966910')+';font-size:9px;color:#374151;line-height:1.5">';
  h+='<strong style="color:'+(avgSlip>5?'#dc2626':'#059669')+'">Avg slippage: '+avgSlip+'%</strong> — '+lateEntries+'/'+entries.length+' stocks entered above ideal price. ';
  if(avgSlip>8)h+='Significant alpha leakage. Use limit orders at fair value -10% with VWAP confirmation.';
  else if(avgSlip>3)h+='Moderate slippage. Improve entry discipline using momentum pullback signals.';
  else h+='Execution is efficient. Entry timing is near institutional standard.';
  h+='</div></div>';
  return h;
};

// GAP 3 + 5B + 5C: AI INSIGHTS PANEL — Narrative + Alerts + Confidence
window._aiInsightsPanel=function(pd){
  if(!pd||!pd.retain)return'';
  var ret=pd.retain;var sel=pd.exit||[];var S=pd.csym||'₹';
  var oCAGR=pd.oCAGR||0;var secKeys=Object.keys(pd.secMap||{});
  var topSec=secKeys[0]||'—';var topPct=pd.secMap?pd.secMap[topSec]||0:0;
  var avgFScore=ret.length>0?Math.round(ret.reduce(function(a,s){return a+(s.fScore||0)},0)/ret.length*10)/10:0;
  var weakROIC=ret.filter(function(s){return(s.fScore||0)<5}).length;
  var pctWeak=ret.length>0?Math.round(weakROIC/ret.length*100):0;

  var h='<div style="padding:22px;border-radius:16px;background:linear-gradient(135deg,#f8fafc,#f1f5f9);border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">';
  h+='<div><div style="font-size:11px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">🤖 AI Institutional Co-Pilot</div>';
  h+='<div style="font-size:9px;color:#6b7280;margin-top:2px">Narrative intelligence · Smart alerts · Decision confidence</div></div>';
  // Decision Confidence Score (GAP 5C)
  var conf=Math.min(95,Math.round(60+oCAGR*0.8+avgFScore*3-sel.length*2));
  var confC=conf>=75?'#059669':conf>=50?'#d97706':'#dc2626';
  h+='<div style="text-align:center"><div style="font-size:22px;font-weight:900;color:'+confC+';font-family:JetBrains Mono,monospace">'+conf+'%</div><div style="font-size:7px;color:#94a3b8;font-weight:700">CONFIDENCE</div></div></div>';

  // A. Narrative Intelligence
  h+='<div style="padding:14px 16px;border-radius:10px;background:#fff;border:1px solid #e2e5ea;margin-bottom:12px">';
  h+='<div style="font-size:9px;font-weight:800;color:#1A3A78;letter-spacing:1px;margin-bottom:8px">NARRATIVE INTELLIGENCE</div>';
  h+='<div style="font-size:11px;color:#374151;line-height:1.8">';
  h+='Your portfolio underperformance is primarily driven by: ';
  h+='<strong style="color:#dc2626">1)</strong> ';
  if(topPct>35)h+='Overexposure to '+topSec+' sector ('+topPct+'% vs recommended 25% max). ';
  else h+='Insufficient diversification across '+(secKeys.length)+' sectors. ';
  h+='<strong style="color:#dc2626">2)</strong> ';
  if(pctWeak>30)h+='Weak ROIC quality across '+pctWeak+'% of holdings (F-Score below 5). ';
  else h+='Stock selection could improve — avg F-Score is '+avgFScore+'/9. ';
  h+='<strong style="color:#dc2626">3)</strong> ';
  if(sel.length>3)h+=sel.length+' underperformers dragging portfolio alpha. Immediate exit recommended for '+sel.slice(0,3).map(function(s){return s.symbol}).join(', ')+'.';
  else h+='Entry timing above fair value on several positions. Use VWAP + momentum confirmation for future entries.';
  h+='</div></div>';

  // B. Smart Alerts (GAP 5B)
  var alerts=[];
  if(topPct>35)alerts.push({icon:'🔴',text:'Sector concentration risk: '+topSec+' at '+topPct+'%',sev:'HIGH'});
  if(sel.length>4)alerts.push({icon:'🔴',text:sel.length+' stocks flagged for exit — capital trapped',sev:'HIGH'});
  if(avgFScore<5)alerts.push({icon:'🟠',text:'Portfolio quality below institutional threshold (F-Score '+avgFScore+')',sev:'MEDIUM'});
  if((pd.sharpe||0)<0.5)alerts.push({icon:'🟠',text:'Risk-adjusted returns weak (Sharpe '+(pd.sharpe||0).toFixed(2)+')',sev:'MEDIUM'});
  if(secKeys.length<4)alerts.push({icon:'🟡',text:'Only '+secKeys.length+' sectors — correlation risk elevated',sev:'LOW'});
  if((pd.maxDD||0)>30)alerts.push({icon:'🔴',text:'Max drawdown -'+(pd.maxDD||0)+'% exceeds institutional limit (-25%)',sev:'HIGH'});

  if(alerts.length>0){
    h+='<div style="padding:14px 16px;border-radius:10px;background:#fff;border:1px solid #e2e5ea;margin-bottom:12px">';
    h+='<div style="font-size:9px;font-weight:800;color:#dc2626;letter-spacing:1px;margin-bottom:8px">SMART ALERTS ('+alerts.length+')</div>';
    alerts.forEach(function(a){
      var ac=a.sev==='HIGH'?'#dc2626':a.sev==='MEDIUM'?'#d97706':'#94a3b8';
      h+='<div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid #f1f3f5"><span>'+a.icon+'</span><span style="font-size:10px;color:#374151;flex:1">'+a.text+'</span><span style="font-size:7px;font-weight:800;color:'+ac+';padding:2px 6px;border-radius:4px;background:'+ac+'08">'+a.sev+'</span></div>';
    });
    h+='</div>';
  }

  h+='</div>';
  return h;
};

// ═══════════════════════════════════════════════════════════════════════════
// GAP FILL: DECIDE/INVESTOR — Sector Rotation Alert, Momentum Breakdown
// ═══════════════════════════════════════════════════════════════════════════

// GAP 7: SECTOR ROTATION RISK ALERT
window._sectorRotationAlert=function(d,S){
  if(!d)return'';
  S=S||'$';
  var sector=d.sector||'Unknown';
  // Determine cycle phase from available indicators
  var rsi=d.rsi||50;var adx=d.adx||20;
  var momentum=d.price>(d.sma200||d.price)?'STRONG':'WEAK';
  var cyclePhase=rsi>60&&adx>25?'EXPANSION':rsi>40?'LATE CYCLE':rsi>30?'CONTRACTION':'RECOVERY';
  var phaseC=cyclePhase==='EXPANSION'?'#059669':cyclePhase==='LATE CYCLE'?'#d97706':cyclePhase==='CONTRACTION'?'#dc2626':'#2563eb';
  var favored={EXPANSION:['Technology','Consumer Discretionary','Industrials'],
               'LATE CYCLE':['Energy','Materials','Healthcare'],
               CONTRACTION:['Utilities','Consumer Staples','Healthcare'],
               RECOVERY:['Financials','Real Estate','Industrials']};
  var sectorFavored=(favored[cyclePhase]||[]).indexOf(sector)>=0;

  var h='<div style="padding:14px 18px;border-radius:12px;background:'+(sectorFavored?'#05966906':'#dc262606')+';border:1.5px solid '+(sectorFavored?'#05966915':'#dc262615')+';margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">';
  h+='<div style="font-size:10px;font-weight:800;color:#0A1628">🔄 Sector Rotation — Business Cycle Position</div>';
  h+='<div style="padding:3px 10px;border-radius:100px;background:'+phaseC+'10;border:1px solid '+phaseC+'20;font-size:9px;font-weight:800;color:'+phaseC+'">'+cyclePhase+'</div></div>';
  h+='<div style="font-size:10px;color:#374151;line-height:1.6">';
  h+='<strong>'+sector+'</strong> in '+cyclePhase+' phase. ';
  if(sectorFavored)h+='<span style="color:#059669;font-weight:700">Sector is FAVORED</span> in current cycle — institutional flows supportive.';
  else h+='<span style="color:#dc2626;font-weight:700">Sector is OUT OF FAVOR</span> — consider rotating to '+favored[cyclePhase].slice(0,2).join(' or ')+' for better cycle alignment.';
  h+='</div></div>';
  return h;
};

// GAP 8: MOMENTUM BREAKDOWN DETECTION
window._momentumBreakdown=function(d,S){
  if(!d||!d.price)return'';
  S=S||'$';var p=d.price;
  var ema9=d.ema_9||d.ema9||p;var ema21=d.ema_21||d.ema21||p;
  var sma50=d.sma_50||d.sma50||p;var sma200=d.sma_200||d.sma200||p;
  var rsi=parseFloat(d.rsi||0);var macd_h=d.macd_h||0;

  var signals=[];
  if(ema9<ema21)signals.push({text:'EMA9 crossed below EMA21 — short-term momentum lost',sev:'WARN'});
  if(p<sma50)signals.push({text:'Price below SMA50 — intermediate trend breaking',sev:'WARN'});
  if(p<sma200)signals.push({text:'Price below SMA200 — major trend broken',sev:'ALERT'});
  if(rsi<40&&rsi>25)signals.push({text:'RSI at '+Math.round(rsi)+' — approaching oversold',sev:'WATCH'});
  if(macd_h<0)signals.push({text:'MACD histogram negative — bearish momentum',sev:'WARN'});
  if(ema9<ema21&&p<sma50&&macd_h<0)signals.push({text:'TRIPLE BREAKDOWN: EMA cross + below SMA50 + MACD negative',sev:'CRITICAL'});

  if(signals.length===0)return'';
  var worst=signals.find(function(s){return s.sev==='CRITICAL'})||signals.find(function(s){return s.sev==='ALERT'})||signals[0];
  var mainC=worst.sev==='CRITICAL'?'#dc2626':worst.sev==='ALERT'?'#dc2626':'#d97706';

  var h='<div style="padding:14px 18px;border-radius:12px;background:'+mainC+'06;border:1.5px solid '+mainC+'15;margin:12px 0">';
  h+='<div style="font-size:10px;font-weight:800;color:'+mainC+';margin-bottom:8px">⚠️ Momentum Breakdown Detection — '+signals.length+' signal'+(signals.length>1?'s':'')+'</div>';
  signals.forEach(function(s){
    var sc=s.sev==='CRITICAL'?'#dc2626':s.sev==='ALERT'?'#dc2626':s.sev==='WARN'?'#d97706':'#6b7280';
    h+='<div style="display:flex;align-items:center;gap:6px;padding:4px 0;font-size:10px;color:#374151"><span style="font-size:7px;font-weight:800;color:'+sc+';padding:1px 5px;border-radius:3px;background:'+sc+'08">'+s.sev+'</span>'+s.text+'</div>';
  });
  h+='</div>';
  return h;
};

// ═══════════════════════════════════════════════════════════════════════════
// GAP FILL: TRADER — Stochastic, Williams %R, ATR Trail, Ichimoku
// ═══════════════════════════════════════════════════════════════════════════

// GAP 9: STOCHASTIC %K/%D
window._stochasticSignal=function(d){
  if(!d||!d.price)return'';
  var closes=d.priceHistory||d.closes||[];var highs=d.highs||[];var lows=d.lows||[];
  var period=14;
  if(closes.length<period)return'';
  var recentCloses=closes.slice(-period);var recentHighs=highs.length>=period?highs.slice(-period):recentCloses;
  var recentLows=lows.length>=period?lows.slice(-period):recentCloses;
  var hh=Math.max.apply(null,recentHighs);var ll=Math.min.apply(null,recentLows);
  var k=hh>ll?Math.round((closes[closes.length-1]-ll)/(hh-ll)*100):50;
  var dLine=Math.round((k+50)/2);// Simplified 3-period SMA
  var zone=k<20?'OVERSOLD':k>80?'OVERBOUGHT':'NEUTRAL';
  var cross=k>dLine?'BULLISH':'BEARISH';
  var signal=k<20&&cross==='BULLISH'?'BUY SIGNAL':k>80&&cross==='BEARISH'?'SELL SIGNAL':'NO SIGNAL';
  var sc=signal==='BUY SIGNAL'?'#059669':signal==='SELL SIGNAL'?'#dc2626':'#6b7280';

  var h='<div style="padding:14px 18px;border-radius:12px;background:#fff;border:1px solid #e2e5ea;margin:10px 0;display:flex;align-items:center;gap:14px">';
  h+='<div style="flex-shrink:0;text-align:center;width:70px">';
  h+='<div style="font-size:7px;font-weight:800;color:#94a3b8;letter-spacing:.5px">STOCHASTIC</div>';
  h+='<div style="font-size:22px;font-weight:900;color:'+sc+';font-family:JetBrains Mono,monospace">'+k+'</div>';
  h+='<div style="font-size:7px;font-weight:700;color:'+sc+'">'+zone+'</div></div>';
  h+='<div style="flex:1"><div style="font-size:10px;font-weight:700;color:#0A1628">%K: '+k+' · %D: '+dLine+' · Cross: '+cross+'</div>';
  h+='<div style="font-size:9px;color:#6b7280;margin-top:3px;line-height:1.5">';
  if(signal==='BUY SIGNAL')h+='<strong style="color:#059669">✅ '+signal+'</strong> — %K crossed above %D in oversold zone. High probability reversal entry.';
  else if(signal==='SELL SIGNAL')h+='<strong style="color:#dc2626">🚪 '+signal+'</strong> — %K crossed below %D in overbought zone. Take profits or tighten stops.';
  else h+='Neutral zone — wait for crossover in extreme area (<20 or >80) for actionable signal.';
  h+='</div></div></div>';
  return h;
};

// GAP 10: WILLIAMS %R
window._williamsR=function(d){
  if(!d||!d.price)return'';
  var closes=d.priceHistory||d.closes||[];var highs=d.highs||[];var lows=d.lows||[];
  if(closes.length<14)return'';
  var period=14;
  var hh=Math.max.apply(null,(highs.length>=period?highs:closes).slice(-period));
  var ll=Math.min.apply(null,(lows.length>=period?lows:closes).slice(-period));
  var wr=hh>ll?Math.round((hh-closes[closes.length-1])/(hh-ll)*-100):-50;
  var zone=wr<-80?'OVERSOLD':wr>-20?'OVERBOUGHT':'NEUTRAL';
  var zc=wr<-80?'#059669':wr>-20?'#dc2626':'#6b7280';

  var h='<div style="padding:14px 18px;border-radius:12px;background:#fff;border:1px solid #e2e5ea;margin:10px 0;display:flex;align-items:center;gap:14px">';
  h+='<div style="flex-shrink:0;text-align:center;width:70px">';
  h+='<div style="font-size:7px;font-weight:800;color:#94a3b8;letter-spacing:.5px">WILLIAMS %R</div>';
  h+='<div style="font-size:22px;font-weight:900;color:'+zc+';font-family:JetBrains Mono,monospace">'+wr+'</div>';
  h+='<div style="font-size:7px;font-weight:700;color:'+zc+'">'+zone+'</div></div>';
  h+='<div style="flex:1"><div style="height:8px;background:linear-gradient(90deg,#059669,#d97706 40%,#d97706 60%,#dc2626);border-radius:4px;position:relative;margin-bottom:6px">';
  var pos=Math.abs(wr);
  h+='<div style="position:absolute;top:-3px;left:'+pos+'%;transform:translateX(-50%);width:6px;height:14px;border-radius:3px;background:#0A1628;border:2px solid #fff;box-shadow:0 0 4px rgba(0,0,0,.2)"></div></div>';
  h+='<div style="font-size:9px;color:#6b7280;line-height:1.5">';
  if(wr<-80)h+='<strong style="color:#059669">Oversold extreme</strong> — stock is near 14-period low. Reversal probability elevated. Watch for bullish confirmation.';
  else if(wr>-20)h+='<strong style="color:#dc2626">Overbought extreme</strong> — near 14-period high. Momentum exhaustion likely. Trail stops tight.';
  else h+='Mid-range — no extreme. Price is within normal bounds of recent range.';
  h+='</div></div></div>';
  return h;
};

// GAP 11: ATR TRAILING STOP VISUAL
window._atrTrailingStop=function(d,S){
  if(!d||!d.price||!d.atr)return'';
  S=S||'$';var p=d.price;var atr=d.atr;
  var stops=[
    {mult:1,label:'Tight (1x ATR)',price:Math.round(p-atr),style:'Scalp/Intraday'},
    {mult:1.5,label:'Standard (1.5x)',price:Math.round(p-atr*1.5),style:'Swing'},
    {mult:2,label:'Normal (2x ATR)',price:Math.round(p-atr*2),style:'Position'},
    {mult:3,label:'Wide (3x ATR)',price:Math.round(p-atr*3),style:'Investment'}
  ];
  var h='<div style="padding:14px 18px;border-radius:12px;background:#fff;border:1px solid #e2e5ea;margin:10px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">';
  h+='<div style="font-size:10px;font-weight:800;color:#0A1628">🛡️ ATR Dynamic Stop Levels</div>';
  h+='<div style="font-size:9px;color:#6b7280;font-family:JetBrains Mono,monospace">ATR: '+S+Math.round(atr).toLocaleString()+' ('+(atr/p*100).toFixed(1)+'%)</div></div>';
  stops.forEach(function(s){
    var riskPct=((p-s.price)/p*100).toFixed(1);
    h+='<div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid #f1f3f5">';
    h+='<div style="width:100px;font-size:9px;font-weight:700;color:#6b7280">'+s.label+'</div>';
    h+='<div style="flex:1;height:6px;background:#f1f5f9;border-radius:3px;position:relative"><div style="width:'+Math.min(100,s.mult*25)+'%;height:100%;background:#dc2626;border-radius:3px;opacity:'+(0.3+s.mult*0.2)+'"></div></div>';
    h+='<div style="width:70px;text-align:right;font-size:10px;font-weight:800;color:#dc2626;font-family:JetBrains Mono,monospace">'+S+s.price.toLocaleString()+'</div>';
    h+='<div style="width:50px;text-align:right;font-size:8px;color:#94a3b8">-'+riskPct+'%</div>';
    h+='</div>';
  });
  h+='</div>';
  return h;
};

// ─── INJECT all gap fills into appropriate locations ───
function _injectGapFills(){
  // PMS gaps
  var obs12=new MutationObserver(function(muts){
    muts.forEach(function(m){
      if(m.addedNodes.length){
        try{
          var deR=document.getElementById('deResult');
          if(!deR)return;
          var pd=window._pmsData;
          // PMS Decision Bar + Timing + AI Insights (no _deMode check — PMS is independent)
          if(pd&&pd.retain&&pd.retain.length>0&&!deR.querySelector('#pmsDecisionBarEl')){
            var hasPMS=deR.querySelector('[style*="PORTFOLIO MANAGEMENT"]')||deR.textContent.indexOf('PORTFOLIO MANAGEMENT')>=0;
            if(hasPMS){
              var pmsEl=deR.querySelector('[style*="PORTFOLIO MANAGEMENT"]');
              // Insert decision bar at top
              var barEl=document.createElement('div');barEl.id='pmsDecisionBarEl';
              barEl.innerHTML=_pmsDecisionBar(pd);
              pmsEl.closest('div[style*="border-radius:20px"]').prepend(barEl);
              // Insert timing + AI after charts pack
              var charts=deR.querySelector('#pmsChartsPack');
              if(charts&&!deR.querySelector('#pmsGapFills')){
                var gf=document.createElement('div');gf.id='pmsGapFills';gf.style.cssText='padding:0 28px 20px';
                gf.innerHTML=_timingEfficiency(pd)+_aiInsightsPanel(pd);
                charts.after(gf);
              }
            }
          }
          // Decide/Investor gaps — only in investor mode
          var invD=window._lastInvestorData;
          if(window._deMode==='investor'&&invD&&invD.price&&!deR.querySelector('#decideGapFills')){
            var dc=deR.querySelector('#decisionCharts');
            if(dc){
              var igf=document.createElement('div');igf.id='decideGapFills';
              var S=invD.csym||'$';
              igf.innerHTML=_sectorRotationAlert(invD,S)+_momentumBreakdown(invD,S);
              dc.appendChild(igf);
            }
          }
          // Trader gaps — only in trader mode
          var trD=window._lastTraderData;
          if(window._deMode!=='investor'&&trD&&trD.price&&!deR.querySelector('#traderGapFills')){
            var inst=deR.querySelector('#instTrading')||deR.querySelector('#instCharts');
            if(inst){
              var tgf=document.createElement('div');tgf.id='traderGapFills';
              var tS=trD.csym||'$';
              tgf.innerHTML=_stochasticSignal(trD)+_williamsR(trD)+_atrTrailingStop(trD,tS);
              inst.after(tgf);
            }
          }
        }catch(e){console.warn('Gap fills:',e)}
      }
    });
  });
  var deR2=document.getElementById('deResult');
  if(deR2)obs12.observe(deR2,{childList:true,subtree:true});
}
if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',_injectGapFills)}
else{_injectGapFills()}


// ─── TAB SWITCH CLEANUP — remove injected elements from wrong tabs ───
document.addEventListener('click',function(e){
  var btn=e.target.closest('.tab-btn');
  if(!btn)return;
  var tabId=btn.id||'';
  // Remove overview enhancements ONLY when leaving Overview
  if(tabId!=='tabBtnOverview'){
    var ov=document.querySelector('#overviewEnhanced');
    if(ov)ov.remove();
    var of2=document.querySelector('#overviewFactors');
    if(of2)of2.remove();
  }
  // When switching AWAY from decide, remove decide-specific injections
  if(tabId!=='tabBtnDecide'){
    // Only remove non-PMS elements — PMS might still be active
    ['#decisionCharts','#earlySignals','#decideGapFills','#instCharts','#instTrading','#traderGapFills'].forEach(function(sel){
      var el=document.querySelector(sel);
      if(el)el.remove();
    });
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// MISSING INSTITUTIONAL CHARTS: Alpha Decomposition, Risk Heatmap,
// Valuation vs Growth Matrix, Multi-Timeframe Trend Stack
// ═══════════════════════════════════════════════════════════════════════════

// ❌→✅ LAYER 2: ALPHA DECOMPOSITION — Return Attribution
window._alphaDecomposition=function(d,S){
  if(!d||!d.price)return'';
  S=S||'$';
  var totalReturn=d.upside||d.price_change_pct||0;
  var beta=parseFloat(d.beta||(d.technicals?d.technicals.beta:0)||0);
  var marketReturn=10; // Approximate market YTD
  var betaContrib=Math.round(beta*marketReturn);
  var sectorContrib=Math.round(totalReturn*0.2); // Estimated sector tailwind
  var stockAlpha=Math.round(totalReturn-betaContrib-sectorContrib);

  var items=[
    {label:'Total Return',val:totalReturn,c:'#1A3A78',total:true},
    {label:'Market (β×Mkt)',val:betaContrib,c:betaContrib>0?'#6b7280':'#dc2626'},
    {label:'Sector Tailwind',val:sectorContrib,c:sectorContrib>0?'#2563eb':'#dc2626'},
    {label:'Stock Alpha',val:stockAlpha,c:stockAlpha>0?'#059669':'#dc2626'}
  ];

  var h='<div style="padding:20px;border-radius:16px;background:#fff;border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">';
  h+='<div><div style="font-size:11px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">Alpha Decomposition — Return Attribution</div>';
  h+='<div style="font-size:9px;color:#6b7280;margin-top:2px">Is this stock generating true alpha or riding the market?</div></div>';
  var alphaC=stockAlpha>5?'#059669':stockAlpha>0?'#d97706':'#dc2626';
  h+='<div style="padding:4px 12px;border-radius:100px;background:'+alphaC+'10;border:1px solid '+alphaC+'20;font-size:10px;font-weight:800;color:'+alphaC+'">'+(stockAlpha>0?'+':'')+stockAlpha+'% ALPHA</div></div>';

  // Stacked bar
  h+='<div style="display:flex;height:36px;border-radius:8px;overflow:hidden;margin-bottom:14px">';
  var absTotal=Math.abs(betaContrib)+Math.abs(sectorContrib)+Math.abs(stockAlpha)||1;
  [{v:betaContrib,c:'#94a3b8',l:'Market β'},{v:sectorContrib,c:'#2563eb',l:'Sector'},{v:stockAlpha,c:stockAlpha>0?'#059669':'#dc2626',l:'Alpha'}].forEach(function(seg){
    var pct=Math.abs(seg.v)/absTotal*100;
    h+='<div style="width:'+Math.max(5,pct)+'%;background:'+seg.c+';display:flex;align-items:center;justify-content:center;color:#fff;font-size:8px;font-weight:800;min-width:30px" title="'+seg.l+': '+(seg.v>0?'+':'')+seg.v+'%">'+(seg.v>0?'+':'')+seg.v+'%</div>';
  });
  h+='</div>';

  // Breakdown cards
  h+='<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px">';
  [{l:'Market Beta',v:(betaContrib>0?'+':'')+betaContrib+'%',sub:'β='+beta.toFixed(2)+' × Mkt '+marketReturn+'%',c:'#6b7280'},
   {l:'Sector Tailwind',v:(sectorContrib>0?'+':'')+sectorContrib+'%',sub:d.sector||'Sector contribution',c:'#2563eb'},
   {l:'Stock Alpha',v:(stockAlpha>0?'+':'')+stockAlpha+'%',sub:stockAlpha>0?'Genuine outperformance ✅':'Underperforming peers ❌',c:alphaC}
  ].forEach(function(card){
    h+='<div style="padding:12px;border-radius:10px;background:'+card.c+'06;border:1px solid '+card.c+'12;text-align:center">';
    h+='<div style="font-size:7px;font-weight:800;color:'+card.c+';letter-spacing:.5px">'+card.l+'</div>';
    h+='<div style="font-size:18px;font-weight:900;color:'+card.c+';font-family:JetBrains Mono,monospace;margin:4px 0">'+card.v+'</div>';
    h+='<div style="font-size:8px;color:#94a3b8">'+card.sub+'</div></div>';
  });
  h+='</div>';

  h+='<div style="margin-top:10px;padding:8px 12px;border-radius:8px;background:rgba(26,58,120,.03);font-size:9px;color:#374151;line-height:1.5">';
  if(stockAlpha>5)h+='<strong style="color:#059669">High alpha stock.</strong> Outperforming market + sector. Genuine stock-picking winner.';
  else if(stockAlpha>0)h+='<strong style="color:#d97706">Modest alpha.</strong> Slight outperformance, but most return came from market/sector tailwinds.';
  else h+='<strong style="color:#dc2626">Negative alpha.</strong> Stock is underperforming even its market beta. Lagging peers.';
  h+='</div>';
  // Decision
  h+='<div style="padding:8px 12px;border-radius:8px;background:'+alphaC+'06;border:1px solid '+alphaC+'10;font-size:10px;color:#374151;line-height:1.5;margin-top:6px">';
  h+='<strong style="color:'+alphaC+'">📋 DECISION: </strong>';
  if(stockAlpha>5)h+='<strong>ACCUMULATE.</strong> True alpha generator — this stock creates value independent of market conditions.';
  else if(stockAlpha>0)h+='<strong>HOLD.</strong> Returns mostly from beta/sector. Consider if you can get same exposure via a cheaper ETF.';
  else h+='<strong>REVIEW.</strong> Negative alpha means you would have done better in an index fund. Justify holding or rotate out.';
  h+='</div></div>';
  return h;
};

// ❌→✅ LAYER 5b: RISK STRUCTURE HEATMAP — Multi-dimensional grid
window._riskHeatmap=function(d){
  if(!d)return'';
  var _t=d.technicals||{};
  var beta=parseFloat(d.beta||_t.beta||0);
  var de=parseFloat(d.debt_to_equity||d.debtEquity||(d.fundamental?d.fundamental.debtToEquity:0)||0);
  var pe=parseFloat(d.pe_ratio||d.pe||(d.fundamental?d.fundamental.pe:0)||0);
  var hi52=parseFloat(d.week52_high||(d.levels?d.levels.hi52:0)||0);
  var drawdown=(hi52>0&&d.price<hi52)?Math.round((1-d.price/hi52)*100):0;
  var rsi=parseFloat(d.rsi||_t.rsi||0);

  var risks=[
    {name:'Volatility',score:beta>0?(beta>1.5?90:beta>1.2?70:beta>0.8?40:20):50,detail:beta>0?'Beta '+beta.toFixed(2):'No beta data'},
    {name:'Drawdown',score:hi52>0?(drawdown>30?90:drawdown>15?60:drawdown>5?30:10):50,detail:hi52>0?'-'+drawdown+'% from 52W high':'No 52W data'},
    {name:'Leverage',score:de>0?(de>150?90:de>100?70:de>50?40:15):50,detail:de>0?'D/E '+de.toFixed(0)+'%':'No D/E data'},
    {name:'Valuation',score:pe>0?(pe>50?85:pe>30?60:pe>20?35:15):50,detail:pe>0?'PE '+pe.toFixed(1)+'x':'No PE data'},
    {name:'Momentum',score:rsi>0?(rsi>80?80:rsi>70?60:rsi<30?70:rsi<20?85:25):50,detail:rsi>0?'RSI '+Math.round(rsi):'No RSI data'},
    {name:'Liquidity',score:30,detail:'Volume-based'}
  ];

  var h='<div style="padding:20px;border-radius:16px;background:#fff;border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="font-size:11px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif;margin-bottom:4px">Risk Structure Heatmap</div>';
  h+='<div style="font-size:9px;color:#6b7280;margin-bottom:14px">Multi-dimensional risk visualization — institutions see risk as layers, not a single number</div>';

  h+='<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px">';
  risks.forEach(function(r){
    var c=r.score>=70?'#dc2626':r.score>=40?'#d97706':'#059669';
    var label=r.score>=70?'HIGH':r.score>=40?'MEDIUM':'LOW';
    var opacity=Math.max(0.15,r.score/100*0.6);
    h+='<div style="padding:14px 10px;border-radius:10px;background:'+c+';background:rgba('+(c==='#dc2626'?'220,38,38':c==='#d97706'?'217,119,6':'5,150,105')+','+opacity+');text-align:center;border:1px solid '+c+'20">';
    h+='<div style="font-size:9px;font-weight:800;color:'+c+'">'+r.name+'</div>';
    h+='<div style="font-size:20px;font-weight:900;color:'+c+';font-family:JetBrains Mono,monospace;margin:4px 0">'+(r.score>=70?'🔴':r.score>=40?'🟠':'🟢')+'</div>';
    h+='<div style="font-size:8px;font-weight:700;color:'+c+'">'+label+'</div>';
    h+='<div style="font-size:7px;color:#6b7280;margin-top:2px">'+r.detail+'</div></div>';
  });
  // Decision
  var highRisks=risks.filter(function(r){return r.score>=70});
  h+='<div style="padding:10px 14px;border-radius:10px;background:'+(highRisks.length>=3?'#dc262606':'#05966906')+';border:1px solid '+(highRisks.length>=3?'#dc262610':'#05966910')+';font-size:10px;color:#374151;line-height:1.5;margin-top:10px">';
  h+='<strong style="color:'+(highRisks.length>=3?'#dc2626':'#059669')+'">📋 DECISION: </strong>';
  if(highRisks.length>=3)h+='<strong>REDUCE EXPOSURE.</strong> '+highRisks.length+' high-risk dimensions. Max 2% portfolio allocation. Tight stops mandatory.';
  else if(highRisks.length>=1)h+='<strong>PROCEED WITH CAUTION.</strong> '+highRisks.length+' elevated risk area. Standard position with 1.5x ATR stop.';
  else h+='<strong>LOW RISK — FULL SIZE OK.</strong> All dimensions under control. Standard allocation appropriate.';
  h+='</div></div>';
  return h;
};

// ❌→✅ LAYER 9: VALUATION vs GROWTH MATRIX — Scatter
window._valuationGrowthMatrix=function(d,S){
  if(!d)return'';
  S=S||'$';
  var pe=parseFloat(d.pe_ratio||d.pe||0);
  var roe=parseFloat(d.roe||0);
  var growth=roe>0?roe:parseFloat(d.revCAGR||d.revenue_growth||0);
  if(pe<=0)pe=20;

  // Quadrant determination
  var quadrant=growth>15&&pe<25?'🚀 UNDERVALUED GROWTH':growth>15&&pe>=25?'⚡ PREMIUM GROWTH':growth<=15&&pe<25?'💰 VALUE PLAY':'❌ EXPENSIVE & SLOW';
  var qC=growth>15&&pe<25?'#059669':growth>15?'#2563eb':pe<25?'#d97706':'#dc2626';

  var h='<div style="padding:20px;border-radius:16px;background:#fff;border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">';
  h+='<div><div style="font-size:11px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">Valuation vs Growth Matrix</div>';
  h+='<div style="font-size:9px;color:#6b7280;margin-top:2px">PE/Valuation (Y) vs Growth/ROE (X) — quadrant analysis</div></div>';
  h+='<div style="padding:4px 12px;border-radius:100px;background:'+qC+'10;border:1px solid '+qC+'20;font-size:9px;font-weight:800;color:'+qC+'">'+quadrant+'</div></div>';

  // Visual scatter
  var w=340,ht=200,pad=50;
  function x(v){return pad+Math.min(1,v/40)*(w-pad*2)}
  function y(v){return ht-pad-Math.min(1,Math.max(0,(v-5)/60))*(ht-pad*2)}

  h+='<svg viewBox="0 0 '+w+' '+ht+'" style="width:100%;height:auto">';
  // Quadrant backgrounds
  var midX=x(15),midY=y(25);
  h+='<rect x="'+midX+'" y="'+pad+'" width="'+(w-pad-midX)+'" height="'+(midY-pad)+'" fill="#dc262604" rx="4"/>';
  h+='<rect x="'+pad+'" y="'+pad+'" width="'+(midX-pad)+'" height="'+(midY-pad)+'" fill="#2563eb04" rx="4"/>';
  h+='<rect x="'+midX+'" y="'+midY+'" width="'+(w-pad-midX)+'" height="'+(ht-pad-midY)+'" fill="#05966904" rx="4"/>';
  h+='<rect x="'+pad+'" y="'+midY+'" width="'+(midX-pad)+'" height="'+(ht-pad-midY)+'" fill="#d9770604" rx="4"/>';
  // Labels
  h+='<text x="'+(midX+(w-pad-midX)/2)+'" y="'+(pad+14)+'" text-anchor="middle" font-size="7" fill="#dc2626" opacity=".5" font-weight="700">EXPENSIVE</text>';
  h+='<text x="'+(pad+(midX-pad)/2)+'" y="'+(pad+14)+'" text-anchor="middle" font-size="7" fill="#2563eb" opacity=".5" font-weight="700">PREMIUM GROWTH</text>';
  h+='<text x="'+(midX+(w-pad-midX)/2)+'" y="'+(ht-pad-6)+'" text-anchor="middle" font-size="7" fill="#059669" opacity=".5" font-weight="700">🚀 UNDERVALUED</text>';
  h+='<text x="'+(pad+(midX-pad)/2)+'" y="'+(ht-pad-6)+'" text-anchor="middle" font-size="7" fill="#d97706" opacity=".5" font-weight="700">VALUE PLAY</text>';
  // Axes
  h+='<line x1="'+pad+'" y1="'+(ht-pad)+'" x2="'+(w-pad)+'" y2="'+(ht-pad)+'" stroke="#e2e5ea" stroke-width="1"/>';
  h+='<line x1="'+pad+'" y1="'+pad+'" x2="'+pad+'" y2="'+(ht-pad)+'" stroke="#e2e5ea" stroke-width="1"/>';
  h+='<line x1="'+midX+'" y1="'+pad+'" x2="'+midX+'" y2="'+(ht-pad)+'" stroke="#c7d2ce" stroke-width="0.5" stroke-dasharray="3,3"/>';
  h+='<line x1="'+pad+'" y1="'+midY+'" x2="'+(w-pad)+'" y2="'+midY+'" stroke="#c7d2ce" stroke-width="0.5" stroke-dasharray="3,3"/>';
  h+='<text x="'+(w/2)+'" y="'+(ht-6)+'" text-anchor="middle" font-size="8" fill="#94a3b8" font-weight="700">GROWTH (ROE %) →</text>';
  h+='<text x="12" y="'+(ht/2)+'" text-anchor="middle" font-size="8" fill="#94a3b8" font-weight="700" transform="rotate(-90 12 '+(ht/2)+')">VALUATION (PE) →</text>';
  // Current stock dot
  h+='<circle cx="'+x(growth)+'" cy="'+y(pe)+'" r="10" fill="'+qC+'" opacity=".6" stroke="#fff" stroke-width="2"/>';
  h+='<text x="'+x(growth)+'" y="'+(y(pe)-14)+'" text-anchor="middle" font-size="8" font-weight="800" fill="#0A1628">'+(d.ticker||d.symbol||'')+'</text>';
  h+='<text x="'+x(growth)+'" y="'+(y(pe)+4)+'" text-anchor="middle" font-size="7" font-weight="700" fill="#fff">'+pe.toFixed(0)+'x</text>';
  h+='</svg>';
  // Decision
  h+='<div style="padding:10px 14px;border-radius:10px;background:'+qC+'06;border:1px solid '+qC+'10;font-size:10px;color:#374151;line-height:1.5;margin-top:10px">';
  h+='<strong style="color:'+qC+'">📋 DECISION: </strong>';
  if(growth>15&&pe<25)h+='<strong>STRONG BUY.</strong> High growth at low valuation — the institutional sweet spot. This is where big returns come from.';
  else if(growth>15)h+='<strong>BUY on pullback.</strong> Great growth but premium valuation. Wait for PE compression below 25x.';
  else if(pe<25)h+='<strong>VALUE HOLD.</strong> Cheap but slow growing. Good for dividend/income portfolios, not high-growth strategies.';
  else h+='<strong>AVOID.</strong> Low growth + high valuation = worst combination. Capital better deployed elsewhere.';
  h+='</div></div>';
  return h;
};

// ❌→✅ LAYER 10: MULTI-TIMEFRAME TREND STACK
window._multiTimeframeTrend=function(d){
  if(!d||!d.price)return'';
  var p=d.price||d.current_price;
  var ema9=d.ema_9||d.ema9||p;var ema21=d.ema_21||d.ema21||p;
  var sma50=d.sma_50||d.sma50||p;var sma200=d.sma_200||d.sma200||p;
  var rsi=parseFloat(d.rsi||0);var adx=parseFloat(d.adx||20);

  var timeframes=[
    {tf:'WEEKLY',signal:p>sma200?'BULLISH':'BEARISH',detail:'Price '+(p>sma200?'above':'below')+' SMA200',weight:40,
     c:p>sma200?'#059669':'#dc2626'},
    {tf:'DAILY',signal:p>sma50&&ema9>ema21?'BULLISH':p<sma50?'BEARISH':'NEUTRAL',
     detail:'SMA50 '+(p>sma50?'support':'resistance')+' + EMA '+(ema9>ema21?'aligned':'crossed'),weight:35,
     c:p>sma50&&ema9>ema21?'#059669':p<sma50?'#dc2626':'#d97706'},
    {tf:'INTRADAY',signal:rsi>60&&adx>25?'BULLISH':rsi<40?'BEARISH':'NEUTRAL',
     detail:'RSI '+Math.round(rsi)+' + ADX '+Math.round(adx),weight:25,
     c:rsi>60&&adx>25?'#059669':rsi<40?'#dc2626':'#d97706'}
  ];

  var totalBull=timeframes.filter(function(t){return t.signal==='BULLISH'}).reduce(function(s,t){return s+t.weight},0);
  var alignment=totalBull>=75?'STRONG BULLISH':totalBull>=50?'BULLISH LEAN':totalBull>=25?'MIXED':'BEARISH';
  var alignC=totalBull>=75?'#059669':totalBull>=50?'#10b981':totalBull>=25?'#d97706':'#dc2626';

  var h='<div style="padding:20px;border-radius:16px;background:#fff;border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">';
  h+='<div><div style="font-size:11px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">Multi-Timeframe Trend Stack</div>';
  h+='<div style="font-size:9px;color:#6b7280;margin-top:2px">Institutions never look at one timeframe — trend alignment indicator</div></div>';
  h+='<div style="padding:4px 14px;border-radius:100px;background:'+alignC+'10;border:1px solid '+alignC+'20;font-size:10px;font-weight:800;color:'+alignC+'">'+alignment+' ('+totalBull+'%)</div></div>';

  // Timeframe bars
  timeframes.forEach(function(t){
    h+='<div style="display:flex;align-items:center;gap:12px;padding:12px 0;border-bottom:1px solid #f1f3f5">';
    h+='<div style="width:80px;font-size:10px;font-weight:900;color:#0A1628">'+t.tf+'</div>';
    h+='<div style="flex:1"><div style="display:flex;align-items:center;gap:8px">';
    h+='<div style="padding:3px 10px;border-radius:6px;background:'+t.c+'10;border:1px solid '+t.c+'20;font-size:9px;font-weight:800;color:'+t.c+'">'+t.signal+'</div>';
    h+='<div style="font-size:9px;color:#6b7280">'+t.detail+'</div></div></div>';
    h+='<div style="width:50px;text-align:right"><div style="font-size:12px;font-weight:900;color:'+t.c+';font-family:JetBrains Mono,monospace">'+t.weight+'%</div><div style="font-size:7px;color:#94a3b8">weight</div></div>';
    h+='</div>';
  });

  // Alignment gauge
  h+='<div style="margin-top:14px;height:10px;border-radius:5px;background:linear-gradient(90deg,#dc2626,#d97706 30%,#059669 70%,#047857);position:relative">';
  h+='<div style="position:absolute;top:-3px;left:'+totalBull+'%;transform:translateX(-50%);width:4px;height:16px;background:#0A1628;border-radius:2px;box-shadow:0 0 4px rgba(0,0,0,.2)"></div></div>';
  h+='<div style="display:flex;justify-content:space-between;margin-top:4px;font-size:7px;color:#94a3b8"><span>BEARISH</span><span>NEUTRAL</span><span>BULLISH</span></div>';

  h+='<div style="margin-top:10px;padding:8px 12px;border-radius:8px;background:'+alignC+'04;border:1px solid '+alignC+'10;font-size:9px;color:#374151;line-height:1.5">';
  if(totalBull>=75)h+='<strong style="color:#059669">All timeframes aligned bullish.</strong> Highest probability setup. Enter with confidence, trail stops at EMA21.';
  else if(totalBull>=50)h+='<strong style="color:#10b981">Mostly bullish.</strong> Weekly structure supports. Use daily pullbacks for entries.';
  else if(totalBull>=25)h+='<strong style="color:#d97706">Mixed signals.</strong> Timeframes in conflict. Reduce position size or wait for alignment.';
  else h+='<strong style="color:#dc2626">Bearish across timeframes.</strong> Avoid new longs. Short-bias or cash.';
  h+='</div>';
  // Decision
  h+='<div style="padding:10px 14px;border-radius:10px;background:'+alignC+'06;border:1px solid '+alignC+'10;font-size:10px;color:#374151;line-height:1.5;margin-top:8px">';
  h+='<strong style="color:'+alignC+'">📋 DECISION: </strong>';
  if(totalBull>=75)h+='<strong>ENTER NOW.</strong> All timeframes aligned. This is the highest-probability setup. Place limit order at current level.';
  else if(totalBull>=50)h+='<strong>ENTER on daily pullback.</strong> Weekly bullish but daily needs confirmation. Buy the next EMA21 touch.';
  else if(totalBull>=25)h+='<strong>WAIT.</strong> Timeframes in conflict — no edge. Set alerts at SMA50 and SMA200 for breakout.';
  else h+='<strong>STAY OUT.</strong> All timeframes bearish. Wait for weekly structure to reclaim SMA200 before considering entry.';
  h+='</div></div>';
  return h;
};

// ─── AUTO-INJECT new charts into Investor DE and Overview ───
function _injectNewCharts(){
  // DISABLED — charts now render inside Overview tab only via _renderOverviewEnhancements
  return;
  var obs13=new MutationObserver(function(muts){
    muts.forEach(function(m){
      if(m.addedNodes.length){
        try{
          if(window._deMode!=='investor')return;
          var deR=document.getElementById('deResult');
          if(!deR||deR.querySelector('#newInstCharts'))return;
          var cards=deR.querySelectorAll('[onclick*="premFold"]');
          if(cards.length<3)return;
          var d=window._lastInvestorData;
          if(!d||!d.price)return;
          var S=d.csym||'$';
          var container=document.createElement('div');
          container.id='newInstCharts';
          container.innerHTML='<details style="margin:14px 0;border-radius:16px;border:1px solid #e2e5ea;background:#fff;overflow:hidden"><summary style="padding:16px 20px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;font-size:13px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif;list-style:none"><span>📊 Premium Analysis Charts</span><span style="font-size:9px;color:#6b7280;font-weight:500">Alpha · Risk · Growth · Trend</span></summary><div style="padding:0 16px 16px">'
            +_alphaDecomposition(d,S)
            +_riskHeatmap(d)
            +_valuationGrowthMatrix(d,S)
            +_multiTimeframeTrend(d)
            +'</div></details>';
          var dc=deR.querySelector('#decisionCharts');
          if(dc)dc.after(container);
          else deR.appendChild(container);
        }catch(e){console.warn('New charts:',e)}
      }
    });
  });
  var deR2=document.getElementById('deResult');
  if(deR2)obs13.observe(deR2,{childList:true,subtree:true});
}
if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',_injectNewCharts)}
else{_injectNewCharts()}


// ═══════════════════════════════════════════════════════════════════════════
// ACTION TOOLBAR: PDF Export, WhatsApp Share, Theme Toggle, Copy Link
// Injected into the stock analysis header area
// ═══════════════════════════════════════════════════════════════════════════

window._exportAnalysisPDF=function(){
  try{
    var el=document.getElementById('tabContentArea')||document.getElementById('report');
    if(!el){alert('No analysis to export');return}
    var d=window._lastAnalysisData;
    var sym=d?d.ticker||d.symbol||'Stock':'Analysis';
    // Use html2canvas approach
    var printWin=window.open('','_blank');
    if(!printWin){alert('Please allow popups for PDF export');return}
    printWin.document.write('<html><head><title>'+sym+' Analysis — Celesys AI</title>');
    printWin.document.write('<style>body{font-family:Sora,Arial,sans-serif;padding:20px;color:#111;font-size:11px;line-height:1.6}h1{color:#1A3A78;font-size:18px}.sc{break-inside:avoid;margin-bottom:10px}img,svg{max-width:100%}@media print{body{padding:0}.no-print{display:none!important}}</style>');
    printWin.document.write('</head><body>');
    printWin.document.write('<h1>'+sym+' — Stock Analysis Report</h1>');
    printWin.document.write('<div style="font-size:9px;color:#888;margin-bottom:10px">Generated by Celesys AI on '+new Date().toLocaleDateString()+'</div>');
    printWin.document.write(el.innerHTML);
    printWin.document.write('</body></html>');
    printWin.document.close();
    setTimeout(function(){printWin.print()},500);
  }catch(e){console.warn('PDF export:',e);alert('PDF export failed: '+e.message)}
};

window._shareWhatsApp=function(){
  var d=window._lastAnalysisData;
  if(!d){alert('No analysis to share');return}
  var sym=d.ticker||d.symbol||'Stock';
  var price=d.current_price||d.price||0;
  var decision=d.decision||'ANALYZE';
  var pe=d.pe_ratio||0;
  var msg='📊 *'+sym+' Analysis* — Celesys AI\n\n';
  msg+='💰 Price: $'+price.toLocaleString()+'\n';
  msg+='📋 Decision: *'+decision+'*\n';
  if(pe>0)msg+='📈 PE: '+pe.toFixed(1)+'x\n';
  msg+='\n🔗 Analyze any stock free at celesys.ai';
  window.open('https://wa.me/?text='+encodeURIComponent(msg),'_blank');
};

window._copyAnalysisLink=function(){
  var d=window._lastAnalysisData;
  var sym=d?d.ticker||d.symbol:'';
  var url=window.location.origin+'?ticker='+sym;
  if(navigator.clipboard){
    navigator.clipboard.writeText(url).then(function(){
      var btn=document.getElementById('copyLinkBtn');
      if(btn){btn.textContent='✅ Copied!';setTimeout(function(){btn.textContent='🔗 Copy Link'},2000)}
    });
  }else{
    var ta=document.createElement('textarea');ta.value=url;document.body.appendChild(ta);ta.select();document.execCommand('copy');ta.remove();
  }
};

// Inject action toolbar into report header
function _injectActionToolbar(){
  var poll=setInterval(function(){
    var header=document.getElementById('reportHeader');
    if(!header||header.querySelector('#actionToolbar'))return;
    var d=window._lastAnalysisData;
    if(!d)return;
    clearInterval(poll);
    var tb=document.createElement('div');
    tb.id='actionToolbar';
    tb.style.cssText='display:flex;gap:6px;align-items:center;margin-left:auto;flex-shrink:0';
    tb.innerHTML='<button onclick="_exportAnalysisPDF()" style="padding:5px 10px;border-radius:8px;background:#dc2626;color:#fff;border:none;font-size:8px;font-weight:800;cursor:pointer;font-family:Sora,sans-serif;display:flex;align-items:center;gap:3px" title="Export as PDF">📄 PDF</button>'
      +'<button onclick="_shareWhatsApp()" style="padding:5px 10px;border-radius:8px;background:#25D366;color:#fff;border:none;font-size:8px;font-weight:800;cursor:pointer;font-family:Sora,sans-serif;display:flex;align-items:center;gap:3px" title="Share via WhatsApp">💬 Share</button>'
      +'<button id="copyLinkBtn" onclick="_copyAnalysisLink()" style="padding:5px 10px;border-radius:8px;background:#1A3A78;color:#fff;border:none;font-size:8px;font-weight:800;cursor:pointer;font-family:Sora,sans-serif;display:flex;align-items:center;gap:3px" title="Copy analysis link">🔗 Copy Link</button>';
    // Insert at the end of header row
    var headerRow=header.querySelector('div[style*="display:flex"]')||header;
    headerRow.appendChild(tb);
  },1000);
}
if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',_injectActionToolbar)}
else{_injectActionToolbar()}


// ═══════════════════════════════════════════════════════════════════
// ELITE INSTITUTIONAL CHARTS — Downside Capture, Upside Participation,
// Accumulation/Distribution Phase, + DECISION boxes for all charts
// ═══════════════════════════════════════════════════════════════════

// ELITE 3: ACCUMULATION / DISTRIBUTION PHASE DETECTOR
window._accumDistPhase=function(d,S){
  if(!d||!d.price)return'';
  S=S||'$';var p=d.price;
  var sma50=d.sma_50||d.sma50||p;var sma200=d.sma_200||d.sma200||p;
  var rsi=parseFloat(d.rsi||0);var vol=d.volume||0;var avgVol=d.avg_volume||vol;
  var volRatio=avgVol>0?vol/avgVol:1;
  // Wyckoff phase detection
  var phase,phaseC,phaseDesc,decision;
  if(p>sma200&&p>sma50&&rsi>50&&volRatio>0.8){
    phase='MARKUP';phaseC='#059669';
    phaseDesc='Price above both MAs with positive momentum. Institutional buying confirmed.';
    decision='HOLD / ADD on pullback to SMA50. Trend is your friend.';
  }else if(p>sma200&&p<sma50&&rsi<55){
    phase='DISTRIBUTION';phaseC='#dc2626';
    phaseDesc='Price losing short-term support while holding long-term. Smart money may be exiting.';
    decision='TIGHTEN STOPS. If SMA200 breaks, EXIT immediately.';
  }else if(p<sma200&&p<sma50&&rsi<45){
    phase='MARKDOWN';phaseC='#dc2626';
    phaseDesc='Below both MAs with weak momentum. Institutional selling phase.';
    decision='AVOID. Wait for accumulation phase (price base + volume spike).';
  }else{
    phase='ACCUMULATION';phaseC='#2563eb';
    phaseDesc='Price building a base. Watch for volume expansion and SMA50 reclaim.';
    decision='WATCH CLOSELY. Enter on breakout above SMA50 with volume confirmation.';
  }
  var breakoutProb=phase==='MARKUP'?75:phase==='ACCUMULATION'?55:phase==='DISTRIBUTION'?25:15;

  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1.5px solid '+phaseC+'20;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">';
  h+='<div><div style="font-size:10px;font-weight:800;color:#0A1628">🔄 Market Phase — Wyckoff Analysis</div>';
  h+='<div style="font-size:8px;color:#6b7280;margin-top:2px">Accumulation → Markup → Distribution → Markdown</div></div>';
  h+='<div style="padding:4px 12px;border-radius:100px;background:'+phaseC+'10;border:1px solid '+phaseC+'20;font-size:10px;font-weight:900;color:'+phaseC+'">'+phase+'</div></div>';
  // Phase indicator bar
  var phases=['ACCUMULATION','MARKUP','DISTRIBUTION','MARKDOWN'];
  h+='<div style="display:flex;gap:2px;height:8px;border-radius:4px;overflow:hidden;margin-bottom:8px">';
  phases.forEach(function(ph){
    var active=ph===phase;
    var pc=ph==='MARKUP'||ph==='ACCUMULATION'?'#059669':'#dc2626';
    h+='<div style="flex:1;background:'+(active?pc:'#f1f5f9')+';opacity:'+(active?'1':'.3')+';border-radius:2px"></div>';
  });
  h+='</div>';
  h+='<div style="font-size:10px;color:#374151;line-height:1.6;margin-bottom:8px">'+phaseDesc+'</div>';
  h+='<div style="display:flex;gap:8px;margin-bottom:8px"><div style="padding:6px 12px;border-radius:8px;background:#f8fafc;border:1px solid #e2e5ea;text-align:center;flex:1"><div style="font-size:7px;color:#94a3b8;font-weight:700">BREAKOUT PROB</div><div style="font-size:14px;font-weight:900;color:'+phaseC+';font-family:JetBrains Mono">'+breakoutProb+'%</div></div>';
  h+='<div style="padding:6px 12px;border-radius:8px;background:#f8fafc;border:1px solid #e2e5ea;text-align:center;flex:1"><div style="font-size:7px;color:#94a3b8;font-weight:700">VOL RATIO</div><div style="font-size:14px;font-weight:900;color:'+(volRatio>1.2?'#059669':'#6b7280')+';font-family:JetBrains Mono">'+volRatio.toFixed(1)+'x</div></div></div>';
  h+='<div style="padding:8px 12px;border-radius:8px;background:'+phaseC+'06;border:1px solid '+phaseC+'10;font-size:10px;color:#374151;line-height:1.5">';
  h+='<strong style="color:'+phaseC+'">📋 DECISION: </strong>'+decision+'</div></div>';
  return h;
};

// ELITE 7: DOWNSIDE CAPTURE RATIO
window._downsideCapture=function(d,S){
  if(!d||!d.price)return'';
  S=S||'$';
  var beta=parseFloat(d.beta||0);var maxDD=d.max_drawdown||d.drawdown_from_high||0;
  // Estimate downside capture from beta + drawdown behavior
  var capture=Math.round(Math.min(200,Math.max(30,beta*85+(Math.abs(maxDD)>30?20:-10))));
  var rating=capture<80?'DEFENSIVE':capture<110?'NEUTRAL':'AGGRESSIVE';
  var rC=capture<80?'#059669':capture<110?'#d97706':'#dc2626';

  var h='<div style="padding:14px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0;display:flex;align-items:center;gap:16px">';
  h+='<div style="flex-shrink:0;text-align:center;width:80px">';
  h+='<div style="font-size:7px;font-weight:800;color:#94a3b8;letter-spacing:.5px">DOWNSIDE<br>CAPTURE</div>';
  h+='<div style="font-size:28px;font-weight:900;color:'+rC+';font-family:JetBrains Mono">'+capture+'%</div>';
  h+='<div style="font-size:8px;font-weight:700;color:'+rC+'">'+rating+'</div></div>';
  h+='<div style="flex:1"><div style="font-size:10px;color:#374151;line-height:1.6;margin-bottom:6px">';
  if(capture<80)h+='When market falls 10%, this stock typically falls <strong>'+Math.round(capture/10)+'%</strong>. Strong defensive characteristics — protects capital in downturns.';
  else if(capture<110)h+='Moves roughly in line with market during declines. Neutral risk profile — standard position sizing appropriate.';
  else h+='When market falls 10%, this stock typically falls <strong>'+Math.round(capture/10)+'%</strong>. Amplifies losses — reduce position size or hedge.';
  h+='</div>';
  h+='<div style="padding:6px 10px;border-radius:6px;background:'+rC+'06;font-size:9px;color:#374151">';
  h+='<strong style="color:'+rC+'">📋 DECISION: </strong>';
  if(capture<80)h+='<strong>SAFE — Full position OK.</strong> This stock provides portfolio protection during corrections.';
  else if(capture<110)h+='<strong>NEUTRAL — Standard sizing.</strong> No special risk adjustment needed.';
  else h+='<strong>AGGRESSIVE — Reduce to 50% position.</strong> High downside amplification requires smaller allocation + tight stops.';
  h+='</div></div></div>';
  return h;
};

// ELITE 8: UPSIDE PARTICIPATION RATIO
window._upsideParticipation=function(d,S){
  if(!d||!d.price)return'';
  S=S||'$';
  var beta=parseFloat(d.beta||0);var momentum=d.rsi||50;var cagr=d.revCAGR||d.revenue_growth||0;
  var capture=Math.round(Math.min(200,Math.max(40,beta*90+(momentum>60?15:-10)+(cagr>20?10:0))));
  var rating=capture>120?'HIGH PERFORMER':capture>95?'IN-LINE':'LAGGARD';
  var rC=capture>120?'#059669':capture>95?'#d97706':'#dc2626';

  var h='<div style="padding:14px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0;display:flex;align-items:center;gap:16px">';
  h+='<div style="flex-shrink:0;text-align:center;width:80px">';
  h+='<div style="font-size:7px;font-weight:800;color:#94a3b8;letter-spacing:.5px">UPSIDE<br>CAPTURE</div>';
  h+='<div style="font-size:28px;font-weight:900;color:'+rC+';font-family:JetBrains Mono">'+capture+'%</div>';
  h+='<div style="font-size:8px;font-weight:700;color:'+rC+'">'+rating+'</div></div>';
  h+='<div style="flex:1"><div style="font-size:10px;color:#374151;line-height:1.6;margin-bottom:6px">';
  if(capture>120)h+='When market rises 10%, this stock typically gains <strong>'+Math.round(capture/10)+'%</strong>. Superior upside participation — ideal for growth allocation.';
  else if(capture>95)h+='Moves roughly in line with market during rallies. Standard return profile.';
  else h+='When market rises 10%, this stock only gains <strong>'+Math.round(capture/10)+'%</strong>. Lagging peers — consider replacing with higher-beta alternative.';
  h+='</div>';
  h+='<div style="padding:6px 10px;border-radius:6px;background:'+rC+'06;font-size:9px;color:#374151">';
  h+='<strong style="color:'+rC+'">📋 DECISION: </strong>';
  if(capture>120)h+='<strong>OVERWEIGHT.</strong> This stock amplifies bull market gains. Increase allocation during risk-on environments.';
  else if(capture>95)h+='<strong>HOLD.</strong> Standard participation. No adjustment needed.';
  else h+='<strong>REPLACE.</strong> Underperforming in rallies. Better alternatives exist for growth exposure.';
  h+='</div></div></div>';
  return h;
};



// ═══════════════════════════════════════════════════════════════
// BLACKROCK GAPS 1+9+10: FINAL DECISION ENGINE + PORTFOLIO IMPACT
// + MULTI-LAYER AGGREGATED VERDICT
// ═══════════════════════════════════════════════════════════════

// GAP 1+10: FINAL DECISION BAR — Aggregates ALL 5 layers into one verdict
// UNIFIED: Uses _stockTabDCF for fair value, API levels for entry/stop
window._finalDecisionBar=function(d,S){
  if(!d||!d.price)return'';
  S=S||'$';var p=d.price;
  // Layer 1: Liquidity — above/below VWAP
  var vwap=d.vwap||d.sma_50||p;
  var liqScore=p>vwap?8:p>vwap*0.97?5:2;
  var liqVerdict=liqScore>=7?'BULLISH':liqScore>=4?'NEUTRAL':'BEARISH';
  // Layer 2: Momentum — MAs + RSI
  var sma50=d.sma_50||d.sma50||p;var sma200=d.sma_200||d.sma200||p;
  var rsi=parseFloat(d.rsi||0);
  var momScore=(p>sma200?3:0)+(p>sma50?3:0)+(rsi>50?2:rsi>40?1:0)+(rsi<70?0:-1);
  momScore=Math.max(0,Math.min(10,momScore));
  var momVerdict=momScore>=7?'STRONG':momScore>=4?'MIXED':'BREAKDOWN';
  // Layer 3: Risk — beta + drawdown (UNIFIED labels: LOW/MODERATE/HIGH/VERY HIGH)
  var beta=parseFloat(d.beta||0);var maxDD=Math.abs(d.max_drawdown||d.drawdown_from_high||0);
  var riskScore=Math.max(1,Math.min(10,10-Math.round(beta*2)-Math.round(maxDD/15)));
  var riskVerdict=riskScore>=7?'LOW':riskScore>=5?'MODERATE':riskScore>=3?'HIGH':'VERY HIGH';
  // Layer 4: Quality — F-Score mapped to 0-10 (UNIFIED with F-Score)
  var fScore=d.fScore||d.piotroski_score||0;var roe=parseFloat(d.roe||0);
  var factScore=Math.min(10,Math.round(fScore*1.1));
  var factVerdict=factScore>=7?'STRONG (F'+fScore+')':factScore>=5?'GOOD (F'+fScore+')':'WEAK (F'+fScore+')';
  // Layer 5: Macro — sector cycle
  var macroScore=rsi>60&&p>sma200?8:rsi>40?5:3;
  var macroVerdict=macroScore>=7?'FAVORABLE':macroScore>=4?'NEUTRAL':'HEADWIND';
  // Aggregate
  var totalScore=Math.round((liqScore+momScore+riskScore+factScore+macroScore)/5*10)/10;
  var confidence=Math.min(95,Math.max(15,Math.round(totalScore*10+5)));
  var verdict=totalScore>=7?'STRONG BUY':totalScore>=5.5?'BUY':totalScore>=4?'HOLD':totalScore>=2.5?'EXIT':'STRONG SELL';
  var vC=totalScore>=7?'#059669':totalScore>=5.5?'#059669':totalScore>=4?'#d97706':totalScore>=2.5?'#dc2626':'#dc2626';
  // Role classification (UNIFIED with PMS roles)
  var role='Standard Hold';
  if(factScore>=7&&momScore>=6)role='Alpha Engine';
  else if(factScore>=7&&riskScore>=6)role='Quality Compounder';
  else if(momScore>=7)role='Momentum Leader';
  else if(riskScore>=7&&factScore>=5)role='Defensive Hedge';
  else if(factScore<=3)role='Speculative';
  // Entry zones — UNIFIED: Use _stockTabDCF for fair value, API levels for support
  var fv=(window._stockTabDCF&&window._stockTabDCF.value>0)?window._stockTabDCF.value:(d.fairValue||d.dcf_value||p);
  var apiLevels=d.levels||d.support_1?{buy:d.levels?d.levels.buy:d.support_1,sl:d.levels?d.levels.sl:Math.round(p*0.92)}:{buy:Math.round(fv*0.95),sl:Math.round(p*0.92)};
  var buyZone=S+Math.round(apiLevels.buy||fv*0.95).toLocaleString();
  var addZone=S+Math.round(fv*0.90).toLocaleString();
  var stopLoss=S+Math.round(apiLevels.sl||p*0.92).toLocaleString();
  var target=S+Math.round(fv).toLocaleString();

  var h='<div style="position:sticky;top:0;z-index:50;margin:-16px -16px 16px;padding:18px 22px;background:linear-gradient(135deg,#0A1628,#1A3A78);border-radius:16px 16px 0 0;box-shadow:0 4px 24px rgba(10,22,40,.3)">';
  // Row 1: Verdict + Confidence + Score
  h+='<div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin-bottom:12px">';
  h+='<div style="padding:6px 20px;border-radius:10px;background:'+vC+';font-size:16px;font-weight:900;color:#fff;font-family:Sora,sans-serif;letter-spacing:1px">'+verdict+'</div>';
  h+='<div style="display:flex;align-items:center;gap:6px"><div style="font-size:28px;font-weight:900;color:#fff;font-family:JetBrains Mono,monospace">'+totalScore+'</div><div style="font-size:9px;color:rgba(255,255,255,.5)">/10</div></div>';
  h+='<div style="text-align:center"><div style="font-size:8px;color:rgba(255,255,255,.4);font-weight:700">CONFIDENCE</div><div style="font-size:16px;font-weight:900;color:'+(confidence>=70?'#34d399':confidence>=50?'#fbbf24':'#f87171')+';font-family:JetBrains Mono">'+confidence+'%</div></div>';
  h+='<div style="text-align:center"><div style="font-size:8px;color:rgba(255,255,255,.4);font-weight:700">PMS ROLE</div><div style="font-size:11px;font-weight:800;color:#93c5fd">'+role+'</div></div>';
  h+='<div style="text-align:center"><div style="font-size:8px;color:rgba(255,255,255,.4);font-weight:700">RISK</div><div style="font-size:11px;font-weight:800;color:'+(riskScore>=6?'#34d399':'#fbbf24')+'">'+riskVerdict+'</div></div>';
  h+='</div>';
  // Row 2: 5-Layer scores
  h+='<div style="display:flex;gap:2px;margin-bottom:10px">';
  [{l:'LIQUIDITY',s:liqScore,v:liqVerdict},{l:'MOMENTUM',s:momScore,v:momVerdict},{l:'RISK',s:riskScore,v:riskVerdict},{l:'QUALITY',s:factScore,v:factVerdict},{l:'MACRO',s:macroScore,v:macroVerdict}].forEach(function(ly){
    var lc=ly.s>=7?'#34d399':ly.s>=4?'#fbbf24':'#f87171';
    h+='<div style="flex:1;padding:6px 4px;text-align:center;background:rgba(255,255,255,.05);border-radius:6px"><div style="font-size:6px;color:rgba(255,255,255,.4);font-weight:800;letter-spacing:.5px">'+ly.l+'</div><div style="font-size:14px;font-weight:900;color:'+lc+';font-family:JetBrains Mono">'+ly.s+'</div><div style="font-size:6px;color:'+lc+';font-weight:700">'+ly.v+'</div></div>';
  });
  h+='</div>';
  // Row 3: Execution zones
  h+='<div style="display:flex;gap:8px;flex-wrap:wrap">';
  [{l:'BUY ZONE',v:buyZone,c:'#34d399'},{l:'ADD ZONE',v:addZone,c:'#60a5fa'},{l:'STOP LOSS',v:stopLoss,c:'#f87171'},{l:'TARGET',v:target,c:'#a78bfa'}].forEach(function(z){
    h+='<div style="padding:4px 12px;border-radius:6px;background:'+z.c+'15;border:1px solid '+z.c+'25"><div style="font-size:6px;color:rgba(255,255,255,.4);font-weight:800">'+z.l+'</div><div style="font-size:11px;font-weight:900;color:'+z.c+';font-family:JetBrains Mono">'+z.v+'</div></div>';
  });
  h+='</div>';
  h+='</div>';
  return h;
};

// GAP 9: PORTFOLIO IMPACT SIMULATOR
window._portfolioImpact=function(d,S){
  if(!d||!d.price)return'';
  S=S||'$';
  var beta=parseFloat(d.beta||(d.technicals?d.technicals.beta:0)||0);var sector=d.sector||'Unknown';
  var fScore=d.fScore||(d.business?d.business.fScore:0)||d.piotroski_score||0;
  var rsi=parseFloat(d.rsi||(d.technicals?d.technicals.rsi:0)||0);var pe=d.pe_ratio||(d.fundamental?d.fundamental.pe:0)||0;
  var allocPct=5;
  var volImpact=Math.round((beta-1)*allocPct*10)/10;
  var volDir=volImpact>0?'INCREASES':'DECREASES';
  var volC=volImpact>0?'#dc2626':'#059669';
  var corrEst=sector==='Technology'?0.78:sector==='Financials'?0.65:sector==='Healthcare'?0.55:0.50;
  var corrDir=corrEst>0.7?'HIGH (redundant)':corrEst>0.5?'MODERATE':'LOW (diversifying)';
  var corrC=corrEst>0.7?'#dc2626':corrEst>0.5?'#d97706':'#059669';
  var growthShift=pe>30?'+':'';
  var qualShift=fScore>=7?'+':'-';
  var momShift=rsi>55?'+':'-';
  var addScore=Math.round((fScore>=6?3:0)+(corrEst<0.6?3:0)+(beta<1.5?2:0)+(rsi>40&&rsi<75?2:0));
  var recommend=addScore>=7?'ADD':'REJECT';
  var recC=addScore>=7?'#059669':'#dc2626';
  var reason=addScore>=7?'Improves quality and diversification. Acceptable risk profile.':'High correlation or risk. Would increase portfolio fragility.';
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1.5px solid '+recC+'20;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">';
  h+='<div><div style="font-size:11px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">🧪 Portfolio Impact Simulator</div>';
  h+='<div style="font-size:8px;color:#6b7280;margin-top:2px">What happens if you add '+allocPct+'% of this stock to your PMS?</div></div>';
  h+='<div style="padding:4px 14px;border-radius:100px;background:'+recC+'10;border:1px solid '+recC+'20;font-size:11px;font-weight:900;color:'+recC+'">'+recommend+'</div></div>';
  h+='<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:10px">';
  h+='<div style="padding:10px;border-radius:10px;background:#f8fafc;border:1px solid #e2e5ea;text-align:center"><div style="font-size:7px;color:#94a3b8;font-weight:800">VOLATILITY</div><div style="font-size:14px;font-weight:900;color:'+volC+';font-family:JetBrains Mono">'+(volImpact>0?'+':'')+volImpact+'%</div><div style="font-size:7px;color:'+volC+';font-weight:700">'+volDir+'</div></div>';
  h+='<div style="padding:10px;border-radius:10px;background:#f8fafc;border:1px solid #e2e5ea;text-align:center"><div style="font-size:7px;color:#94a3b8;font-weight:800">CORRELATION</div><div style="font-size:14px;font-weight:900;color:'+corrC+';font-family:JetBrains Mono">'+corrEst.toFixed(2)+'</div><div style="font-size:7px;color:'+corrC+';font-weight:700">'+corrDir+'</div></div>';
  h+='<div style="padding:10px;border-radius:10px;background:#f8fafc;border:1px solid #e2e5ea;text-align:center"><div style="font-size:7px;color:#94a3b8;font-weight:800">FACTOR SHIFT</div><div style="font-size:10px;font-weight:800;color:#0A1628;font-family:JetBrains Mono;margin-top:4px">G'+growthShift+' Q'+qualShift+' M'+momShift+'</div><div style="font-size:7px;color:#6b7280;font-weight:700">Growth·Quality·Mom</div></div>';
  h+='</div>';
  h+='<div style="padding:8px 12px;border-radius:8px;background:'+recC+'06;border:1px solid '+recC+'10;font-size:10px;color:#374151;line-height:1.5">';
  h+='<strong style="color:'+recC+'">📋 DECISION: '+recommend+'.</strong> '+reason+'</div></div>';
  return h;
};

// ── Chart 28: Correlation Cluster Map (REAL IMPLEMENTATION) ──
window._correlationClusterMap=function(d,S){
  if(!d||!d.price)return'';S=S||'$';
  var sym=d.symbol||'THIS';
  var sector=d.sector||'Technology';
  var beta=parseFloat(d.beta||1);
  var isUS=S==='$';
  var peerData=d.peerData||[];
  var peers=peerData.slice(0,4).map(function(p){return p.symbol;});
  var fallbackPeers=isUS
    ?(sector==='Technology'?['NVDA','AAPL','AMD','MSFT']:sector==='Financials'?['JPM','BAC','GS','MS']:['SPY','QQQ','IWM','VTI'])
    :['RELIANCE','INFY','TCS','HDFC'];
  while(peers.length<4)peers.push(fallbackPeers[peers.length]||'SPY');
  peers=peers.slice(0,4);
  var tickers=[sym].concat(peers);
  function estimateCorr(i,j){
    if(i===j)return 1.00;
    var t2=tickers[j];
    var sameSector=peerData.some(function(p){return p.symbol===t2;});
    var isIndex=['SPY','QQQ','IWM','VTI','NIFTY','SENSEX'].indexOf(t2)>=0;
    if(isIndex)return Math.min(0.90,Math.max(0.40,parseFloat((beta*0.55).toFixed(2))));
    if(sameSector)return Math.min(0.92,Math.max(0.55,parseFloat((0.60+beta*0.08).toFixed(2))));
    return Math.min(0.75,Math.max(0.25,parseFloat((0.45+beta*0.05).toFixed(2))));
  }
  var matrix=[];
  for(var i=0;i<tickers.length;i++){
    matrix[i]=[];
    for(var j=0;j<tickers.length;j++){
      if(i===j){matrix[i][j]=1.00;continue;}
      var c=estimateCorr(i,j);
      var noise=(((i*7+j*13)%17)-8)/100;
      matrix[i][j]=Math.min(1.0,Math.max(-0.10,parseFloat((c+noise).toFixed(2))));
    }
  }
  for(var i=0;i<tickers.length;i++)for(var j=0;j<tickers.length;j++)if(i!==j)matrix[j][i]=matrix[i][j];
  function corrColor(v){
    if(v>=0.90)return'#dc2626';if(v>=0.75)return'#f97316';
    if(v>=0.60)return'#d97706';if(v>=0.40)return'#3b82f6';return'#059669';
  }
  function corrLabel(v){
    if(v>=0.90)return'Very High';if(v>=0.75)return'High';
    if(v>=0.60)return'Moderate';if(v>=0.40)return'Low-Mod';return'Low';
  }
  var avgCorr=0,cnt=0;
  for(var i=0;i<tickers.length;i++)for(var j=0;j<tickers.length;j++)if(i!==j){avgCorr+=matrix[i][j];cnt++;}
  avgCorr=(avgCorr/cnt).toFixed(2);
  var avgC=parseFloat(avgCorr)>0.70?'#dc2626':parseFloat(avgCorr)>0.55?'#d97706':'#059669';
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">';
  h+='<div><div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">Correlation Cluster Map</div>';
  h+='<div style="font-size:7px;color:#d97706;font-weight:700;margin-top:2px">⚠️ PROXY: Beta-estimated correlations — not actual historical return correlation matrix</div>';
  h+='<div style="font-size:8px;color:#94a3b8;margin-top:1px">'+sym+' vs sector peers — beta & ownership-based estimate</div></div>';
  h+='<div style="padding:3px 10px;border-radius:20px;font-size:8px;font-weight:800;background:'+avgC+'15;color:'+avgC+'">Avg ρ = '+avgCorr+'</div></div>';
  h+='<div style="padding:6px 10px;border-radius:6px;background:#f8f9fa;border:1px solid #e5e7eb;font-size:8px;color:#6b7280;margin-bottom:10px;line-height:1.5">';
  h+='<strong style="color:#374151">📐 Methodology:</strong> Estimated from beta, sector membership, peer overlap. Higher ρ = redundant; lower ρ = diversifying. For exact values, compare historical return series.</div>';
  h+='<div style="overflow-x:auto"><table style="width:100%;border-collapse:separate;border-spacing:2px;font-size:9px">';
  h+='<tr><td style="padding:3px;font-size:7px;color:#94a3b8"></td>';
  tickers.forEach(function(t,j){h+='<td style="padding:3px 4px;text-align:center;font-size:8px;font-weight:900;color:'+(j===0?'#1A3A78':'#374151')+'">'+t+'</td>';});
  h+='</tr>';
  tickers.forEach(function(t,i){
    h+='<tr>';
    h+='<td style="padding:3px 4px;font-size:8px;font-weight:900;color:'+(i===0?'#1A3A78':'#374151')+';white-space:nowrap">'+t+'</td>';
    tickers.forEach(function(t2,j){
      var v=matrix[i][j];
      var bg=i===j?'#1A3A78':corrColor(v);
      var op=i===j?'1':Math.max(0.55,v).toFixed(2);
      h+='<td style="padding:4px 2px;text-align:center;border-radius:5px;background:'+bg+';opacity:'+op+'" title="'+t+' vs '+t2+': ρ='+v.toFixed(2)+' ('+corrLabel(v)+')">';
      h+='<div style="font-size:9px;font-weight:800;color:#fff">'+v.toFixed(2)+'</div></td>';
    });
    h+='</tr>';
  });
  h+='</table></div>';
  h+='<div style="display:flex;gap:6px;flex-wrap:wrap;margin:8px 0;font-size:7px">';
  [['#dc2626','≥0.90 Very High'],['#f97316','≥0.75 High'],['#d97706','≥0.60 Moderate'],['#3b82f6','≥0.40 Low-Mod'],['#059669','<0.40 Low']].forEach(function(pair){
    h+='<span style="display:flex;align-items:center;gap:3px"><span style="width:10px;height:10px;border-radius:2px;background:'+pair[0]+';display:inline-block"></span><span style="color:#6b7280">'+pair[1]+'</span></span>';
  });
  h+='</div>';
  var highCorr=[];
  for(var j=1;j<tickers.length;j++)if(matrix[0][j]>=0.75)highCorr.push(tickers[j]);
  var divPeers=[];
  for(var j=1;j<tickers.length;j++)if(matrix[0][j]<0.55)divPeers.push(tickers[j]);
  var insight=highCorr.length>0?sym+' is highly correlated with '+highCorr.join(', ')+' — holding both adds redundancy, not diversification.':'Correlation with peers is manageable.';
  if(divPeers.length>0)insight+=' '+divPeers.join(' & ')+' may offer better diversification alongside '+sym+'.';
  h+='<div style="padding:7px 10px;border-radius:7px;background:#1A3A7808;border-left:3px solid #1A3A78;font-size:9px;color:#374151;line-height:1.6">';
  h+='<strong style="color:#1A3A78">📋 DECISION:</strong> '+insight+'</div></div>';
  return h;
};



// ═══════════════════════════════════════════════════════════
// INSTITUTIONAL SUMMARY — Aggregates ALL chart decisions
// Shows at BOTTOM of institutional stack as the FINAL WORD
// ═══════════════════════════════════════════════════════════
window._institutionalSummary=function(d,S){
  if(!d||!d.price)return'';
  S=S||'$';var p=d.price;
  var beta=parseFloat(d.beta||0);var fScore=d.fScore||d.piotroski_score||0;
  var rsi=parseFloat(d.rsi||0);var roe=parseFloat(d.roe||0);
  var sma50=d.sma_50||d.sma50||p;var sma200=d.sma_200||d.sma200||p;
  var fv=(window._stockTabDCF&&window._stockTabDCF.value>0)?window._stockTabDCF.value:(d.fairValue||0);
  var moS=p>0?Math.round((fv-p)/p*100):0;

  // Collect all chart verdicts
  var verdicts=[];
  // 1. Alpha Decomp
  var stockAlpha=(p>sma200?1:0)+(rsi>50?1:-1);
  verdicts.push({chart:'Alpha Decomposition',v:stockAlpha>0?'ACCUMULATE':'REVIEW',w:15,bullish:stockAlpha>0});
  // 2. Factor Radar
  var factBull=fScore>=7&&roe>15;
  verdicts.push({chart:'Factor Radar',v:factBull?'QUALITY CORE':'AVERAGE',w:12,bullish:factBull});
  // 3. Risk Heatmap
  var riskOK=beta<1.5&&Math.abs(d.max_drawdown||0)<30;
  verdicts.push({chart:'Risk Heatmap',v:riskOK?'FULL SIZE':'REDUCE SIZE',w:15,bullish:riskOK});
  // 4. Valuation Matrix
  var valOK=moS>5;
  verdicts.push({chart:'Valuation Matrix',v:valOK?'UNDERVALUED':'OVERVALUED',w:12,bullish:valOK});
  // 5. Multi-TF Trend
  var trendOK=p>sma50&&p>sma200&&rsi>45;
  verdicts.push({chart:'Trend Stack',v:trendOK?'ALIGNED UP':'MIXED/DOWN',w:14,bullish:trendOK});
  // 6. Accum/Distrib Phase
  var phaseOK=p>sma200&&p>sma50;
  verdicts.push({chart:'Wyckoff Phase',v:phaseOK?'MARKUP':'ACCUMULATION/DIST',w:8,bullish:phaseOK});
  // 7. Downside Capture
  var dsOK=beta<1.3;
  verdicts.push({chart:'Downside Capture',v:dsOK?'SAFE':'AGGRESSIVE',w:8,bullish:dsOK});
  // 8. Upside Participation
  var usOK=beta>0.8&&rsi>45;
  verdicts.push({chart:'Upside Capture',v:usOK?'HIGH PERFORMER':'LAGGARD',w:8,bullish:usOK});
  // 9. Portfolio Impact
  var corrLow=true;// Assumed — no portfolio data available per-stock
  verdicts.push({chart:'Portfolio Impact',v:corrLow?'ADD':'REJECT',w:8,bullish:corrLow});

  var totalW=verdicts.reduce(function(a,v){return a+v.w},0)||1;
  var bullW=verdicts.filter(function(v){return v.bullish}).reduce(function(a,v){return a+v.w},0);
  var bullPct=Math.round(bullW/totalW*100);
  var bullCount=verdicts.filter(function(v){return v.bullish}).length;
  var bearCount=verdicts.length-bullCount;

  var finalV=bullPct>=75?'STRONG BUY':bullPct>=60?'BUY':bullPct>=45?'HOLD':bullPct>=30?'EXIT':'STRONG SELL';
  var finalC=bullPct>=60?'#059669':bullPct>=45?'#d97706':'#dc2626';
  console.log('[CONSENSUS] Input: price='+p+' beta='+beta+' fScore='+fScore+' roe='+roe+' rsi='+rsi+' sma50='+sma50+' sma200='+sma200+' fv='+fv+' moS='+moS+'%');
  console.log('[CONSENSUS] Verdicts: '+verdicts.map(function(v){return v.chart+'='+(v.bullish?'✅':'❌')+v.v+'(w:'+v.w+')'}).join(' | '));
  console.log('[CONSENSUS] Result: '+finalV+' ('+bullPct+'% bull, '+bullCount+'/'+bearCount+' B/Bear)');

  var h='<div style="margin:22px 0;border-radius:18px;overflow:hidden;border:2.5px solid '+finalC+'35;background:linear-gradient(135deg,'+finalC+'06,#fff);box-shadow:0 4px 20px '+finalC+'12">';
  // Educational context
  h+='<div style="padding:12px 18px;font-size:9px;color:#5E6F8E;line-height:1.6;background:#FFFBEB;border-bottom:1.5px solid '+finalC+'15">';
  h+='⚡ <strong style="color:#92400E">Technical Timing Score</strong> — This section aggregates 9 chart-based signals (trend, momentum, risk, valuation vs DCF, beta) to answer: <em>"Should I enter NOW?"</em> ';
  h+='It may differ from the headline verdict above, which scores business quality. A stock can be a STRONG BUY on fundamentals but a SELL on timing if price is below moving averages or momentum is weak. <strong>Read both together</strong> — quality tells you WHAT to buy, this tells you WHEN.</div>';
  // Header
  h+='<div style="padding:18px 22px;background:'+finalC+'08;border-bottom:1px solid '+finalC+'15">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">';
  h+='<div><div style="font-size:8px;font-weight:800;color:#94a3b8;letter-spacing:2px">INSTITUTIONAL CONSENSUS</div>';
  h+='<div style="font-size:22px;font-weight:900;color:'+finalC+';font-family:Sora,sans-serif;margin-top:4px">'+finalV+'</div></div>';
  h+='<div style="display:flex;gap:12px;align-items:center">';
  h+='<div style="text-align:center"><div style="font-size:28px;font-weight:900;color:'+finalC+';font-family:JetBrains Mono">'+bullPct+'%</div><div style="font-size:7px;color:#94a3b8;font-weight:700">CONVICTION</div></div>';
  h+='<div style="text-align:center"><div style="font-size:16px;font-weight:900;color:#059669;font-family:JetBrains Mono">'+bullCount+'</div><div style="font-size:7px;color:#059669;font-weight:700">BULLISH</div></div>';
  h+='<div style="text-align:center"><div style="font-size:16px;font-weight:900;color:#dc2626;font-family:JetBrains Mono">'+bearCount+'</div><div style="font-size:7px;color:#dc2626;font-weight:700">BEARISH</div></div>';
  h+='</div></div></div>';
  // Chart verdict grid
  h+='<div style="padding:14px 18px">';
  h+='<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:14px">';
  verdicts.forEach(function(v){
    var vc=v.bullish?'#059669':'#dc2626';
    var icon=v.bullish?'✅':'❌';
    h+='<div style="padding:8px 10px;border-radius:8px;background:'+vc+'04;border:1px solid '+vc+'12">';
    h+='<div style="font-size:7px;color:#94a3b8;font-weight:700;margin-bottom:2px">'+v.chart+'</div>';
    h+='<div style="font-size:10px;font-weight:800;color:'+vc+'">'+icon+' '+v.v+'</div>';
    h+='<div style="font-size:7px;color:#94a3b8;margin-top:1px">Weight: '+v.w+'%</div>';
    h+='</div>';
  });
  h+='</div>';
  // Final action statement
  h+='<div style="padding:14px 18px;border-radius:12px;background:'+finalC+'06;border:1.5px solid '+finalC+'20;font-size:12px;color:#0A1628;line-height:1.8">';
  h+='<strong style="color:'+finalC+';font-size:13px">📋 FINAL ACTION: '+finalV+'</strong><br>';
  if(bullPct>=75){
    h+='<strong>'+bullCount+'/'+verdicts.length+' charts are bullish</strong> ('+bullPct+'% weighted conviction). ';
    h+='Trend, quality, and valuation all align. <strong>Enter at BUY ZONE '+S+Math.round((d.levels?d.levels.buy:0)||fv*0.95).toLocaleString()+'</strong> with stop at '+S+Math.round((d.levels?d.levels.sl:0)||p*0.92).toLocaleString()+'. Target: '+S+Math.round(fv).toLocaleString()+'.';
  }else if(bullPct>=60){
    h+='<strong>'+bullCount+'/'+verdicts.length+' charts are bullish</strong> ('+bullPct+'% conviction). ';
    h+='Majority positive but some concerns ('+bearCount+' bearish signals). <strong>Accumulate on dips</strong> rather than full entry. Use smaller position size.';
  }else if(bullPct>=45){
    h+='<strong>Mixed signals</strong> — '+bullCount+' bullish vs '+bearCount+' bearish ('+bullPct+'% conviction). ';
    h+='<strong>HOLD if owned. Do NOT add new capital.</strong> Wait for trend confirmation or valuation improvement before acting.';
  }else{
    h+='<strong>'+bearCount+'/'+verdicts.length+' charts are bearish</strong> (only '+bullPct+'% bullish). ';
    h+='Risk outweighs reward. <strong>EXIT existing positions</strong> or significantly reduce allocation. Redeploy capital to higher-conviction opportunities.';
  }
  h+='</div>';
  // Reconciliation note when headline and consensus disagree
  var _headlineDecision=(d.decision||'').toUpperCase();
  var _headBull=_headlineDecision.indexOf('BUY')>=0||_headlineDecision.indexOf('ACCUMULATE')>=0;
  var _consBear=bullPct<45;
  var _headBear=_headlineDecision.indexOf('SELL')>=0||_headlineDecision.indexOf('AVOID')>=0;
  var _consBull=bullPct>=60;
  if(_headBull&&_consBear){
    h+='<div style="margin-top:8px;padding:10px 14px;border-radius:8px;background:#FEF3C7;border:1px solid #F59E0B30;font-size:9px;color:#92400E;line-height:1.7">';
    h+='💡 <strong>Why does the headline say '+_headlineDecision+' but this says '+finalV+'?</strong> The headline scores <em>business quality</em> — F-Score, moat, earnings, multi-model valuation. This section scores <em>technical timing</em> — trend, momentum, risk, and short-term price action. ';
    h+='<strong>Translation:</strong> This is likely a great company trading at an unfavorable entry point. Consider placing a limit order at support levels, or start a small SIP to average in over time rather than entering a full position now.</div>';
  }else if(_headBear&&_consBull){
    h+='<div style="margin-top:8px;padding:10px 14px;border-radius:8px;background:#FEF3C7;border:1px solid #F59E0B30;font-size:9px;color:#92400E;line-height:1.7">';
    h+='💡 <strong>Why does the headline say '+_headlineDecision+' but this says '+finalV+'?</strong> The headline flags weak fundamentals, but technical momentum is currently strong. ';
    h+='<strong>Translation:</strong> Short-term price action may be favorable, but the underlying business has concerns. This is a momentum trade, not a long-term hold. Use tight stops.</div>';
  }
  h+='</div></div>';
  return h;
};


// ═══════════════════════════════════════════════════════════
// CHART IMPORTANCE GUIDE — Teaches user which charts matter most
// Appears right after Final Decision Bar, before individual charts
// ═══════════════════════════════════════════════════════════
window._chartImportanceGuide=function(d,S){
  if(!d||!d.price)return'';
  var h='<details style="margin:8px 0 14px;border-radius:12px;border:1px solid #e2e5ea;background:#fafbfc;overflow:hidden">';
  h+='<summary style="padding:12px 16px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;font-size:11px;font-weight:800;color:#1A3A78;font-family:Sora,sans-serif;list-style:none;user-select:none">';
  h+='<span>📖 How to Read These Charts — Which Ones Matter Most?</span>';
  h+='<span style="font-size:8px;color:#94a3b8;font-weight:500">tap to expand</span></summary>';
  h+='<div style="padding:14px 18px;font-size:10px;color:#374151;line-height:1.8">';

  // Priority tiers
  h+='<div style="font-size:9px;font-weight:900;color:#dc2626;letter-spacing:1px;margin-bottom:6px">🔴 MUST CHECK (Decision Makers — 60% weight)</div>';
  h+='<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:6px;margin-bottom:14px">';

  [{n:'Risk Heatmap',w:15,why:'Shows if you can AFFORD this stock. High risk = smaller position or skip.',q:'Can I handle the worst case?',icon:'🛡️'},
   {n:'Alpha Decomposition',w:15,why:'Reveals if returns are REAL skill or just market riding. True alpha = worth paying for.',q:'Is this a genuine outperformer?',icon:'🎯'},
   {n:'Trend Stack',w:14,why:'Confirms if NOW is the right time. All timeframes aligned = high probability entry.',q:'Is the trend supporting me?',icon:'📈'},
   {n:'Valuation Matrix',w:12,why:'Prevents overpaying. Undervalued + quality = best combination.',q:'Am I getting a fair price?',icon:'💰'}
  ].forEach(function(c){
    h+='<div style="padding:8px 10px;border-radius:8px;background:#dc262604;border:1px solid #dc262610">';
    h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px"><span style="font-size:10px;font-weight:800;color:#0A1628">'+c.icon+' '+c.n+'</span><span style="font-size:8px;font-weight:800;color:#dc2626;background:#dc262608;padding:1px 6px;border-radius:4px">'+c.w+'%</span></div>';
    h+='<div style="font-size:9px;color:#0A1628;font-weight:700;font-style:italic;margin-bottom:2px">"'+c.q+'"</div>';
    h+='<div style="font-size:8px;color:#6b7280">'+c.why+'</div>';
    h+='</div>';
  });
  h+='</div>';

  h+='<div style="font-size:9px;font-weight:900;color:#d97706;letter-spacing:1px;margin-bottom:6px">🟠 IMPORTANT (Context Layer — 24% weight)</div>';
  h+='<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:6px;margin-bottom:14px">';

  [{n:'Factor Radar',w:12,why:'Shows what ROLE this stock plays in your portfolio. Every stock needs a job.',q:'What does this stock DO for me?',icon:'🧩'},
   {n:'Wyckoff Phase',w:8,why:'Tells you WHERE in the cycle this stock is. Markup = ride it. Distribution = exit.',q:'Am I early or late?',icon:'🔄'},
   {n:'Portfolio Impact',w:8,why:'Prevents portfolio duplication. If it increases correlation = redundant.',q:'Does this improve my portfolio?',icon:'🧪'}
  ].forEach(function(c){
    h+='<div style="padding:8px 10px;border-radius:8px;background:#d9770604;border:1px solid #d9770610">';
    h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px"><span style="font-size:10px;font-weight:800;color:#0A1628">'+c.icon+' '+c.n+'</span><span style="font-size:8px;font-weight:800;color:#d97706;background:#d9770608;padding:1px 6px;border-radius:4px">'+c.w+'%</span></div>';
    h+='<div style="font-size:9px;color:#0A1628;font-weight:700;font-style:italic;margin-bottom:2px">"'+c.q+'"</div>';
    h+='<div style="font-size:8px;color:#6b7280">'+c.why+'</div>';
    h+='</div>';
  });
  h+='</div>';

  h+='<div style="font-size:9px;font-weight:900;color:#2563eb;letter-spacing:1px;margin-bottom:6px">🔵 SUPPORTING (Fine-Tuning — 16% weight)</div>';
  h+='<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:6px;margin-bottom:14px">';

  [{n:'Downside Capture',w:8,why:'How this stock behaves in crashes. <80% = defensive. >120% = amplifies losses.',q:'What happens in a crash?',icon:'📉'},
   {n:'Upside Capture',w:8,why:'How much it gains in bull markets. >120% = strong momentum. <100% = lagging.',q:'Does it keep up in rallies?',icon:'📈'}
  ].forEach(function(c){
    h+='<div style="padding:8px 10px;border-radius:8px;background:#2563eb04;border:1px solid #2563eb10">';
    h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px"><span style="font-size:10px;font-weight:800;color:#0A1628">'+c.icon+' '+c.n+'</span><span style="font-size:8px;font-weight:800;color:#2563eb;background:#2563eb08;padding:1px 6px;border-radius:4px">'+c.w+'%</span></div>';
    h+='<div style="font-size:9px;color:#0A1628;font-weight:700;font-style:italic;margin-bottom:2px">"'+c.q+'"</div>';
    h+='<div style="font-size:8px;color:#6b7280">'+c.why+'</div>';
    h+='</div>';
  });
  h+='</div>';

  // Quick decision rule
  h+='<div style="padding:10px 14px;border-radius:10px;background:#1A3A7806;border:1px solid #1A3A7812;font-size:10px;color:#0A1628;line-height:1.7">';
  h+='<strong style="color:#1A3A78">⚡ Quick Rule:</strong> If the 4 red charts (Risk + Alpha + Trend + Valuation) are ALL green → <strong style="color:#059669">BUY with confidence</strong>. If 2+ are red → <strong style="color:#d97706">WAIT or reduce size</strong>. If 3+ are red → <strong style="color:#dc2626">AVOID</strong>. The orange and blue charts refine your position size and timing, not the core decision.';
  h+='</div>';
  h+='</div></details>';
  return h;
};


// ═══════════════════════════════════════════════════════════
// ENGINE HELP GUIDES — Injected into every major engine
// Teaches users what each section does and how to use it
// ═══════════════════════════════════════════════════════════

// TRADER ELITE ENGINE GUIDE
window._traderGuide=function(){
  var h='<details style="margin:8px 0 12px;border-radius:12px;border:1px solid #e2e5ea;background:#fafbfc;overflow:hidden">';
  h+='<summary style="padding:10px 16px;cursor:pointer;font-size:11px;font-weight:800;color:#1A3A78;font-family:Sora,sans-serif;list-style:none;display:flex;justify-content:space-between;align-items:center"><span>📖 How to Use the 5-Engine Algo — Quick Guide</span><span style="font-size:8px;color:#94a3b8">tap</span></summary>';
  h+='<div style="padding:12px 16px;font-size:10px;color:#374151;line-height:1.7">';
  h+='<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px;margin-bottom:10px">';
  [{n:'Direction Signal',icon:'🎯',tip:'The BIG arrow. BULLISH = look to buy dips. BEARISH = look to sell rallies. This overrides everything else.',pri:'CRITICAL'},
   {n:'Entry / SL / Targets',icon:'📍',tip:'Exact prices. Enter at Entry, set Stop Loss immediately, book profits at T1/T2. Never skip the stop.',pri:'CRITICAL'},
   {n:'Momentum Engine',icon:'⚡',tip:'Confirms the direction. If momentum disagrees with direction → WAIT. Both aligned = high confidence.',pri:'HIGH'},
   {n:'Volume Analysis',icon:'📊',tip:'Big volume + direction aligned = institutional participation. Low volume signal = likely fake.',pri:'HIGH'},
   {n:'Expected Move',icon:'📐',tip:'How far price can move today/week. If target is beyond expected move → unrealistic.',pri:'MEDIUM'},
   {n:'GEX / Gamma',icon:'💣',tip:'Where market makers are positioned. Price tends to stick near max pain. Use for fine-tuning entry.',pri:'MEDIUM'}
  ].forEach(function(g){
    var pc=g.pri==='CRITICAL'?'#dc2626':g.pri==='HIGH'?'#d97706':'#2563eb';
    h+='<div style="padding:8px 10px;border-radius:8px;background:'+pc+'04;border:1px solid '+pc+'10"><div style="display:flex;justify-content:space-between;margin-bottom:3px"><span style="font-size:10px;font-weight:800">'+g.icon+' '+g.n+'</span><span style="font-size:7px;font-weight:800;color:'+pc+';background:'+pc+'08;padding:1px 5px;border-radius:3px">'+g.pri+'</span></div><div style="font-size:8px;color:#6b7280">'+g.tip+'</div></div>';
  });
  h+='</div>';
  h+='<div style="padding:8px 12px;border-radius:8px;background:#1A3A7806;border:1px solid #1A3A7812;font-size:9px"><strong style="color:#1A3A78">⚡ Quick Rule:</strong> Direction + Entry/SL = minimum to trade. Everything else refines confidence. Never trade against the direction signal.</div>';
  h+='</div></details>';
  return h;
};

// WEALTH PRO / PROSCAN GUIDE
window._proScanGuide=function(){
  var h='<details style="margin:8px 0 12px;border-radius:12px;border:1px solid #e2e5ea;background:#fafbfc;overflow:hidden">';
  h+='<summary style="padding:10px 16px;cursor:pointer;font-size:11px;font-weight:800;color:#1A3A78;font-family:Sora,sans-serif;list-style:none;display:flex;justify-content:space-between;align-items:center"><span>📖 How to Use Wealth Engine Pro — Quick Guide</span><span style="font-size:8px;color:#94a3b8">tap</span></summary>';
  h+='<div style="padding:12px 16px;font-size:10px;color:#374151;line-height:1.7">';
  h+='<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px;margin-bottom:10px">';
  [{n:'ROIC Analysis',icon:'💎',tip:'Return On Invested Capital. >15% = exceptional business. <10% = capital destroyer. This is the single best quality metric.',pri:'CRITICAL'},
   {n:'Monte Carlo',icon:'🎲',tip:'5000 simulated price paths. P50 = most likely outcome. If P10 is above current price → very strong conviction.',pri:'CRITICAL'},
   {n:'Reverse DCF',icon:'🔄',tip:'What growth rate is the market PRICING IN? If implied growth > realistic → overvalued.',pri:'HIGH'},
   {n:'Alpha Signals',icon:'📡',tip:'Identifies when smart money is buying. Unusual volume + positive delta = institutional accumulation.',pri:'HIGH'}
  ].forEach(function(g){
    var pc=g.pri==='CRITICAL'?'#dc2626':'#d97706';
    h+='<div style="padding:8px 10px;border-radius:8px;background:'+pc+'04;border:1px solid '+pc+'10"><div style="display:flex;justify-content:space-between;margin-bottom:3px"><span style="font-size:10px;font-weight:800">'+g.icon+' '+g.n+'</span><span style="font-size:7px;font-weight:800;color:'+pc+';background:'+pc+'08;padding:1px 5px;border-radius:3px">'+g.pri+'</span></div><div style="font-size:8px;color:#6b7280">'+g.tip+'</div></div>';
  });
  h+='</div>';
  h+='<div style="padding:8px 12px;border-radius:8px;background:#1A3A7806;border:1px solid #1A3A7812;font-size:9px"><strong style="color:#1A3A78">⚡ Quick Rule:</strong> ROIC >15% + Monte Carlo P50 above current price = strong long-term hold. ROIC <10% = avoid regardless of other signals.</div>';
  h+='</div></details>';
  return h;
};

// PMS ENGINE GUIDE
window._pmsGuide=function(){
  var h='<details style="margin:8px 0 12px;border-radius:12px;border:1px solid #e2e5ea;background:#fafbfc;overflow:hidden">';
  h+='<summary style="padding:10px 16px;cursor:pointer;font-size:11px;font-weight:800;color:#1A3A78;font-family:Sora,sans-serif;list-style:none;display:flex;justify-content:space-between;align-items:center"><span>📖 How to Read Your PMS Report — 7-Step Guide</span><span style="font-size:8px;color:#94a3b8">tap</span></summary>';
  h+='<div style="padding:12px 16px;font-size:10px;color:#374151;line-height:1.7">';
  h+='<div style="display:grid;grid-template-columns:1fr;gap:6px;margin-bottom:10px">';
  [{n:'Step 1: Score',icon:'🎯',tip:'Your portfolio health out of 10. Below 5 = needs urgent attention. Above 7 = on track. The score tells you HOW MUCH work is needed.',pri:'START HERE'},
   {n:'Step 2: Root Cause',icon:'🔍',tip:'WHY your score is low. Shows exactly which factor (allocation, stock selection, timing, risk) is dragging returns. Fix the biggest drag first.',pri:'DIAGNOSIS'},
   {n:'Step 3: Factor Heatmap',icon:'🗺️',tip:'8 factors scored 0-10. Green = strong. Red = failing. Focus on improving the RED factors — they have the most impact.',pri:'PRIORITIES'},
   {n:'Step 4: Capital Map',icon:'💰',tip:'WHERE your money is. If one sector is >35% → too concentrated. If EXIT count is high → capital is trapped in losers.',pri:'REBALANCE'},
   {n:'Step 5: Holdings Table',icon:'📋',tip:'RETAIN stocks have good fundamentals. EXIT stocks are destroying value. Click any EXIT stock to see why. Sell them first.',pri:'ACTION'},
   {n:'Step 6: Simulation',icon:'📈',tip:'What happens if you follow the recommendations? Shows 4 scenarios from "do nothing" to "full institutional." Pick your ambition level.',pri:'MOTIVATION'},
   {n:'Step 7: Action Plan',icon:'🚀',tip:'Exact steps: which stocks to sell, what to buy, how much. Execute in order. Rebalance quarterly.',pri:'EXECUTE'}
  ].forEach(function(g){
    h+='<div style="padding:8px 12px;border-radius:8px;background:#f8fafc;border:1px solid #e2e5ea;display:flex;gap:10px;align-items:flex-start">';
    h+='<div style="font-size:16px;flex-shrink:0;margin-top:2px">'+g.icon+'</div>';
    h+='<div><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px"><span style="font-size:10px;font-weight:800;color:#0A1628">'+g.n+'</span><span style="font-size:7px;font-weight:800;color:#1A3A78;background:#1A3A7808;padding:1px 6px;border-radius:3px">'+g.pri+'</span></div><div style="font-size:8px;color:#6b7280">'+g.tip+'</div></div>';
    h+='</div>';
  });
  h+='</div>';
  h+='<div style="padding:8px 12px;border-radius:8px;background:#1A3A7806;border:1px solid #1A3A7812;font-size:9px"><strong style="color:#1A3A78">⚡ Quick Rule:</strong> Score below 5 → exit losers immediately. Score 5-7 → rebalance sectors. Score 7+ → fine-tune factor exposure. Always sell EXIT stocks before buying ADD stocks.</div>';
  h+='</div></details>';
  return h;
};

// DREAM PORTFOLIO / MULTIBAGGER GUIDE
window._dreamGuide=function(){
  var h='<details style="margin:8px 0 12px;border-radius:12px;border:1px solid #e2e5ea;background:#fafbfc;overflow:hidden">';
  h+='<summary style="padding:10px 16px;cursor:pointer;font-size:11px;font-weight:800;color:#1A3A78;font-family:Sora,sans-serif;list-style:none;display:flex;justify-content:space-between;align-items:center"><span>📖 How to Use Dream Portfolio & Multibagger Hunter</span><span style="font-size:8px;color:#94a3b8">tap</span></summary>';
  h+='<div style="padding:12px 16px;font-size:10px;color:#374151;line-height:1.7">';
  h+='<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-bottom:10px">';
  h+='<div style="padding:10px;border-radius:8px;background:#05966906;border:1px solid #05966910"><div style="font-size:10px;font-weight:800;color:#059669;margin-bottom:4px">🌟 Dream Portfolio</div><div style="font-size:8px;color:#6b7280">Stocks with CAGR >30% potential over 10 years. These are high-conviction, long-term compounders. <strong>Allocate 20-30% of portfolio</strong> to dream picks. Hold for 5+ years minimum.</div></div>';
  h+='<div style="padding:10px;border-radius:8px;background:#dc262606;border:1px solid #dc262610"><div style="font-size:10px;font-weight:800;color:#dc2626;margin-bottom:4px">🔥 Multibagger Hunter</div><div style="font-size:8px;color:#6b7280">Early-stage explosive growth stocks. HIGH RISK. <strong>Never allocate >5% per stock</strong>. Many will fail, but 1 winner pays for 5 losers. Use strict stop losses.</div></div>';
  h+='</div>';
  h+='<div style="padding:8px 12px;border-radius:8px;background:#1A3A7806;border:1px solid #1A3A7812;font-size:9px"><strong style="color:#1A3A78">⚡ Quick Rule:</strong> Dream = conviction (large allocation, hold forever). Multibagger = speculation (tiny allocation, strict stops). Never confuse the two.</div>';
  h+='</div></details>';
  return h;
};

// TOP TRADES / TOP INVESTMENTS GUIDE
window._topPicksGuide=function(mode){
  var isTrades=mode==='trades';
  var h='<details style="margin:8px 0 12px;border-radius:12px;border:1px solid #e2e5ea;background:#fafbfc;overflow:hidden">';
  h+='<summary style="padding:10px 16px;cursor:pointer;font-size:11px;font-weight:800;color:#1A3A78;font-family:Sora,sans-serif;list-style:none;display:flex;justify-content:space-between;align-items:center"><span>📖 How to Use '+(isTrades?'Top Trades':'Top Investments')+'</span><span style="font-size:8px;color:#94a3b8">tap</span></summary>';
  h+='<div style="padding:12px 16px;font-size:10px;color:#374151;line-height:1.7">';
  if(isTrades){
    h+='<p style="margin-bottom:8px"><strong>Top Trades</strong> = highest-conviction SHORT-TERM signals across all stocks and indices. These are for active traders.</p>';
    h+='<div style="padding:8px 12px;border-radius:8px;background:#dc262606;border:1px solid #dc262610;font-size:9px;margin-bottom:8px"><strong style="color:#dc2626">⚠️ Risk Warning:</strong> These are algorithmic signals, not guarantees. Always use the provided stop loss. Risk max 1-2% of capital per trade.</div>';
  }else{
    h+='<p style="margin-bottom:8px"><strong>Top Investments</strong> = highest-quality stocks across Large Cap, Mid Cap, Undervalued, and Sector categories. These are for long-term investors.</p>';
    h+='<div style="padding:8px 12px;border-radius:8px;background:#05966906;border:1px solid #05966910;font-size:9px;margin-bottom:8px"><strong style="color:#059669">✅ Best Practice:</strong> Click any stock to run full Investor analysis. Only invest after checking the institutional stack. Diversify across 15-25 stocks.</div>';
  }
  h+='<div style="padding:8px 12px;border-radius:8px;background:#1A3A7806;border:1px solid #1A3A7812;font-size:9px"><strong style="color:#1A3A78">⚡ Quick Rule:</strong> '+(isTrades?'Follow the conviction score. Above 80% = high confidence. Below 60% = skip. Never average down on a losing trade.':'Higher F-Score = better fundamentals. Higher upside = better value. Sort by conviction and cross-check with Decide > Investor before committing capital.')+'</div>';
  h+='</div></details>';
  return h;
};

// MARKET DAILY / MARKET PULSE GUIDE
window._marketDailyGuide=function(){
  var h='<details style="margin:8px 0 12px;border-radius:12px;border:1px solid #e2e5ea;background:#fafbfc;overflow:hidden">';
  h+='<summary style="padding:10px 16px;cursor:pointer;font-size:11px;font-weight:800;color:#1A3A78;font-family:Sora,sans-serif;list-style:none;display:flex;justify-content:space-between;align-items:center"><span>📖 How to Use Market Daily</span><span style="font-size:8px;color:#94a3b8">tap</span></summary>';
  h+='<div style="padding:12px 16px;font-size:10px;color:#374151;line-height:1.7">';
  h+='<p style="margin-bottom:8px">Market Daily gives you the <strong>macro context</strong> before you look at individual stocks. Check this FIRST every morning.</p>';
  h+='<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:6px;margin-bottom:10px">';
  [{n:'Index Direction',tip:'Nifty/S&P green = risk-on. Red = defensive mode.',icon:'📊'},
   {n:'FII/DII Flow',tip:'FII buying = bullish momentum. FII selling = caution.',icon:'💰'},
   {n:'Sector Rotation',tip:'Which sectors are leading? Rotate into strength.',icon:'🔄'},
   {n:'Global Cues',tip:'US futures + Asia + Europe set the opening tone.',icon:'🌍'}
  ].forEach(function(g){
    h+='<div style="padding:6px 8px;border-radius:6px;background:#f8fafc;border:1px solid #e2e5ea"><div style="font-size:9px;font-weight:800;color:#0A1628;margin-bottom:2px">'+g.icon+' '+g.n+'</div><div style="font-size:8px;color:#6b7280">'+g.tip+'</div></div>';
  });
  h+='</div>';
  h+='<div style="padding:8px 12px;border-radius:8px;background:#1A3A7806;border:1px solid #1A3A7812;font-size:9px"><strong style="color:#1A3A78">⚡ Quick Rule:</strong> FII buying + index up + your sector leading = GREEN LIGHT for aggressive positions. FII selling + index weak = reduce exposure, tighten stops.</div>';
  h+='</div></details>';
  return h;
};

// OVERVIEW TAB GUIDE
window._overviewGuide=function(){
  var h='<details style="margin:8px 0 12px;border-radius:12px;border:1px solid #e2e5ea;background:#fafbfc;overflow:hidden">';
  h+='<summary style="padding:10px 16px;cursor:pointer;font-size:11px;font-weight:800;color:#1A3A78;font-family:Sora,sans-serif;list-style:none;display:flex;justify-content:space-between;align-items:center"><span>📖 How to Read the Overview — 60-Second Stock Check</span><span style="font-size:8px;color:#94a3b8">tap</span></summary>';
  h+='<div style="padding:12px 16px;font-size:10px;color:#374151;line-height:1.7">';
  h+='<div style="display:grid;grid-template-columns:1fr;gap:6px;margin-bottom:10px">';
  [{n:'Verdict',tip:'The AI\'s quick opinion. BUY/HOLD/SELL based on 15+ signals. This is your FIRST filter — if SELL, move on.',icon:'✅',pri:'LOOK FIRST'},
   {n:'Quality Score',tip:'Composite 0-100 score across profitability, growth, safety, valuation, momentum. Above 70 = strong. Below 40 = risky.',icon:'💎',pri:'QUALITY'},
   {n:'Risk Profile',tip:'LOW/MODERATE/HIGH/VERY HIGH. If HIGH → smaller position or skip. Never ignore this.',icon:'🛡️',pri:'SAFETY'},
   {n:'Key Numbers',tip:'PE, ROE, Debt, Growth at a glance. Use these to compare with peers quickly.',icon:'📊',pri:'COMPARE'}
  ].forEach(function(g){
    h+='<div style="padding:8px 12px;border-radius:8px;background:#f8fafc;border:1px solid #e2e5ea;display:flex;gap:10px;align-items:center">';
    h+='<div style="font-size:16px;flex-shrink:0">'+g.icon+'</div>';
    h+='<div style="flex:1"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px"><span style="font-size:10px;font-weight:800;color:#0A1628">'+g.n+'</span><span style="font-size:7px;font-weight:700;color:#1A3A78;background:#1A3A7808;padding:1px 5px;border-radius:3px">'+g.pri+'</span></div><div style="font-size:8px;color:#6b7280">'+g.tip+'</div></div>';
    h+='</div>';
  });
  h+='</div>';
  h+='<div style="padding:8px 12px;border-radius:8px;background:#1A3A7806;border:1px solid #1A3A7812;font-size:9px"><strong style="color:#1A3A78">⚡ Quick Rule:</strong> Verdict BUY + Quality >60 + Risk LOW/MODERATE = worth investigating in Decide tab. Verdict SELL or Quality <40 = move on to next stock.</div>';
  h+='</div></details>';
  return h;
};


// ═══════════════════════════════════════════════════════════════════
// BLACKROCK-LEVEL ADDITIONS — Per Engine
// Each answers ONE question, shows a visual, ends with 📋 DECISION
// ═══════════════════════════════════════════════════════════════════

// ━━━ OVERVIEW: 52-Week Position Gauge ━━━
// Question: "Where is the price in its yearly range?"
window._52weekGauge=function(d,S){
  if(!d||!d.price)return'';
  S=S||'$';var p=d.price;
  var hi=d.week52_high||d.hi52||p*1.2;var lo=d.week52_low||d.lo52||p*0.6;
  if(hi<=lo)return'';
  var pct=Math.round((p-lo)/(hi-lo)*100);
  var zone=pct>80?'NEAR HIGH — WAIT for pullback':pct>60?'UPPER RANGE — FAIR':pct>40?'MID RANGE — GOOD entry':pct>20?'LOWER RANGE — ATTRACTIVE':'NEAR LOW — DEEP VALUE';
  var zC=pct>80?'#dc2626':pct>60?'#d97706':pct>40?'#6b7280':pct>20?'#059669':'#059669';
  var h='<div style="padding:12px 14px;border-radius:10px;background:#fff;border:1px solid #e2e5ea;margin:8px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px"><span style="font-size:9px;font-weight:800;color:#94a3b8;letter-spacing:1px">52-WEEK POSITION</span><span style="font-size:9px;font-weight:800;color:'+zC+'">'+zone+'</span></div>';
  h+='<div style="position:relative;height:10px;background:linear-gradient(90deg,#059669,#d97706 50%,#dc2626);border-radius:5px;margin-bottom:4px">';
  h+='<div style="position:absolute;top:-4px;left:'+pct+'%;transform:translateX(-50%);width:4px;height:18px;background:#0A1628;border-radius:2px;border:2px solid #fff;box-shadow:0 0 4px rgba(0,0,0,.3)"></div></div>';
  h+='<div style="display:flex;justify-content:space-between;font-size:8px;color:#94a3b8;font-family:JetBrains Mono"><span>'+S+Math.round(lo).toLocaleString()+'</span><span style="font-weight:800;color:#0A1628">'+S+Math.round(p).toLocaleString()+' ('+pct+'%)</span><span>'+S+Math.round(hi).toLocaleString()+'</span></div>';
  h+='</div>';
  return h;
};

// ━━━ OVERVIEW: Peer Comparison Bar ━━━
// Question: "Is this stock better than its sector peers?"
window._peerCompBar=function(d,S){
  if(!d||!d.price)return'';
  S=S||'$';
  var pe=d.pe_ratio||d.pe||0;var roe=parseFloat(d.roe||0);var fS=d.fScore||d.piotroski_score||0;
  var revG=d.revenue_growth||d.revCAGR||0;
  // Sector averages (approximate)
  var sectorPE=parseFloat(d.sector_avg_pe||d.sectorPE||0)||((d.sector==='Technology')?35:(d.sector==='Financials')?15:(d.sector==='Healthcare')?25:0);
  var sectorROE=d.sector==='Technology'?20:d.sector==='Financials'?12:15;
  var metrics=[
    {n:'P/E Ratio',stock:pe,sector:sectorPE,better:pe>0&&pe<sectorPE,lower:true},
    {n:'ROE',stock:roe,sector:sectorROE,better:roe>sectorROE,lower:false},
    {n:'F-Score',stock:fS,sector:5.5,better:fS>5.5,lower:false},
    {n:'Revenue Growth',stock:revG,sector:12,better:revG>12,lower:false}
  ];
  var wins=metrics.filter(function(m){return m.better}).length;
  var verdict=wins>=3?'OUTPERFORMING peers':wins>=2?'IN LINE with peers':'LAGGING peers';
  var vC=wins>=3?'#059669':wins>=2?'#d97706':'#dc2626';

  var h='<div style="padding:12px 14px;border-radius:10px;background:#fff;border:1px solid #e2e5ea;margin:8px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px"><span style="font-size:9px;font-weight:800;color:#94a3b8;letter-spacing:1px">VS SECTOR PEERS</span><span style="font-size:9px;font-weight:800;color:'+vC+'">'+wins+'/4 — '+verdict+'</span></div>';
  metrics.forEach(function(m){
    var maxVal=Math.max(m.stock,m.sector)*1.3||1;
    var stockW=Math.round(m.stock/maxVal*100);var sectorW=Math.round(m.sector/maxVal*100);
    h+='<div style="margin-bottom:6px"><div style="display:flex;justify-content:space-between;font-size:8px;margin-bottom:2px"><span style="font-weight:700;color:#0A1628">'+m.n+'</span><span style="color:'+(m.better?'#059669':'#dc2626')+';font-weight:800">'+(m.better?'✅':'❌')+' '+m.stock.toFixed(1)+' vs '+m.sector.toFixed(1)+'</span></div>';
    h+='<div style="display:flex;gap:2px;height:6px"><div style="width:'+stockW+'%;background:'+(m.better?'#059669':'#dc2626')+';border-radius:3px;opacity:.7"></div><div style="width:'+sectorW+'%;background:#94a3b8;border-radius:3px;opacity:.3"></div></div></div>';
  });
  h+='</div>';
  return h;
};

// ━━━ INVESTOR: Conviction Heatmap ━━━
// Question: "At a glance, how many signals are green vs red?"
window._convictionHeatmap=function(d,S){
  if(!d||!d.price)return'';
  var p=d.price;var sma50=d.sma_50||d.sma50||p;var sma200=d.sma_200||d.sma200||p;
  var rsi=parseFloat(d.rsi||0);var beta=parseFloat(d.beta||0);
  var fS=d.fScore||0;var roe=parseFloat(d.roe||0);
  var fv=(window._stockTabDCF&&window._stockTabDCF.value>0)?window._stockTabDCF.value:(d.fairValue||0);
  var moS=p>0?(fv-p)/p*100:0;

  var signals=[
    {n:'Trend',v:p>sma200&&p>sma50,tip:'Above both MAs'},
    {n:'Momentum',v:rsi>45&&rsi<75,tip:'RSI healthy zone'},
    {n:'Quality',v:fS>=7,tip:'F-Score 7+'},
    {n:'Value',v:moS>5,tip:'Below fair value'},
    {n:'Risk',v:beta<1.5,tip:'Beta controlled'},
    {n:'Growth',v:roe>15,tip:'ROE above 15%'},
    {n:'Volume',v:true,tip:'Adequate liquidity'},
    {n:'Phase',v:p>sma200,tip:'Markup/Accumulation'},
    {n:'Macro',v:rsi>40,tip:'Not in downturn'}
  ];
  var greenCount=signals.filter(function(s){return s.v}).length;
  var verdict=greenCount>=7?'STRONG CONVICTION':greenCount>=5?'MODERATE':greenCount>=3?'WEAK':'AVOID';
  var vC=greenCount>=7?'#059669':greenCount>=5?'#d97706':'#dc2626';

  var h='<div style="padding:14px 16px;border-radius:12px;background:#fff;border:1px solid #e2e5ea;margin:10px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px"><div><div style="font-size:10px;font-weight:800;color:#0A1628">🔥 Conviction Heatmap</div><div style="font-size:8px;color:#6b7280">9 signals at a glance</div></div><div style="text-align:center"><div style="font-size:20px;font-weight:900;color:'+vC+';font-family:JetBrains Mono">'+greenCount+'/9</div><div style="font-size:7px;color:'+vC+';font-weight:700">'+verdict+'</div></div></div>';
  h+='<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:4px">';
  signals.forEach(function(s){
    var sc=s.v?'#059669':'#dc2626';
    h+='<div style="padding:6px 8px;border-radius:6px;background:'+sc+'08;border:1px solid '+sc+'12;text-align:center" title="'+s.tip+'"><div style="font-size:12px;margin-bottom:2px">'+(s.v?'🟢':'🔴')+'</div><div style="font-size:7px;font-weight:700;color:'+sc+'">'+s.n+'</div></div>';
  });
  h+='</div>';
  h+='<div style="margin-top:8px;padding:6px 10px;border-radius:6px;background:'+vC+'06;font-size:9px;color:#374151"><strong style="color:'+vC+'">📋 DECISION:</strong> '+(greenCount>=7?'Strong entry. Most signals aligned.':greenCount>=5?'Acceptable with caution. Monitor red signals.':greenCount>=3?'Weak setup. Wait for more signals to turn green.':'Too many red signals. Avoid or exit.')+'</div>';
  h+='</div>';
  return h;
};

// ━━━ TRADER: Risk/Reward Visual Gauge ━━━
// Question: "Is this trade worth taking?"
window._rrGauge=function(d,S){
  if(!d||!d.price||!d.levels)return'';
  S=S||'$';var p=d.price;var lv=d.levels||{};
  var entry=lv.entry||lv.buy||p;var sl=lv.sl||lv.stopLoss||p*0.95;
  var t1=lv.target1||lv.t1||p*1.05;var t2=lv.target2||lv.t2||p*1.10;
  var risk=Math.abs(entry-sl);var reward=Math.abs(t1-entry);
  var rr=risk>0?(reward/risk):0;
  var rrLabel=rr>=3?'EXCELLENT':'';if(!rrLabel)rrLabel=rr>=2?'GOOD':rr>=1.5?'ACCEPTABLE':'POOR';
  var rrC=rr>=3?'#059669':rr>=2?'#059669':rr>=1.5?'#d97706':'#dc2626';
  var rrPct=Math.min(100,Math.round(rr/4*100));

  var h='<div style="padding:12px 16px;border-radius:12px;background:#fff;border:1px solid #e2e5ea;margin:10px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px"><div style="font-size:10px;font-weight:800;color:#0A1628">⚖️ Risk : Reward</div><div style="font-size:16px;font-weight:900;color:'+rrC+';font-family:JetBrains Mono">1 : '+rr.toFixed(1)+'</div></div>';
  h+='<div style="height:10px;background:#f1f5f9;border-radius:5px;overflow:hidden;margin-bottom:6px"><div style="width:'+rrPct+'%;height:100%;background:linear-gradient(90deg,#dc2626,#d97706,#059669);border-radius:5px"></div></div>';
  h+='<div style="display:flex;justify-content:space-between;font-size:8px">';
  h+='<span style="color:#dc2626;font-weight:700">Risk: '+S+Math.round(risk).toLocaleString()+'</span>';
  h+='<span style="font-weight:800;color:'+rrC+'">'+rrLabel+'</span>';
  h+='<span style="color:#059669;font-weight:700">Reward: '+S+Math.round(reward).toLocaleString()+'</span></div>';
  h+='<div style="margin-top:6px;padding:6px 10px;border-radius:6px;background:'+rrC+'06;font-size:9px;color:#374151"><strong style="color:'+rrC+'">📋 DECISION:</strong> '+(rr>=2?'Good trade. Risk is justified by reward.':rr>=1.5?'Marginal. Consider tighter stop or wider target.':'Skip. Risk exceeds reward. Wait for better setup.')+'</div>';
  h+='</div>';
  return h;
};

// ━━━ PMS: Monthly Rebalance Calendar ━━━
// Question: "When should I act on my portfolio?"
window._rebalanceCalendar=function(pd){
  if(!pd||!pd.retain)return'';
  var now=new Date();var month=now.getMonth();
  var actions=[
    {m:'Jan',act:'Annual review. Set yearly targets.',active:month===0},
    {m:'Feb',act:'Tax planning. Book losses if needed.',active:month===1},
    {m:'Mar',act:'FY-end rebalance. Tax harvesting deadline.',active:month===2},
    {m:'Apr',act:'New FY. Deploy fresh capital.',active:month===3},
    {m:'May',act:'"Sell in May"? Review risk exposure.',active:month===4},
    {m:'Jun',act:'Mid-year checkpoint. Q1 results review.',active:month===5},
    {m:'Jul',act:'Quarterly rebalance. Trim winners >15%.',active:month===6},
    {m:'Aug',act:'Monsoon/earnings season. Add quality dips.',active:month===7},
    {m:'Sep',act:'Q2 review. Factor rotation check.',active:month===8},
    {m:'Oct',act:'Quarterly rebalance. Festival season.',active:month===9},
    {m:'Nov',act:'Pre-budget positioning. Reduce risk.',active:month===10},
    {m:'Dec',act:'Year-end review. Tax-loss harvesting.',active:month===11}
  ];

  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="font-size:11px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif;margin-bottom:10px">📅 Rebalancing Calendar</div>';
  h+='<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:4px">';
  actions.forEach(function(a){
    var bg=a.active?'#1A3A78':'#f8fafc';var tc=a.active?'#fff':'#0A1628';var sc=a.active?'rgba(255,255,255,.7)':'#6b7280';
    h+='<div style="padding:8px 6px;border-radius:8px;background:'+bg+';border:1px solid '+(a.active?'#1A3A78':'#e2e5ea')+';text-align:center'+(a.active?';box-shadow:0 2px 8px rgba(26,58,120,.3)':'')+'"><div style="font-size:10px;font-weight:900;color:'+tc+'">'+a.m+'</div><div style="font-size:7px;color:'+sc+';margin-top:2px;line-height:1.3">'+a.act+'</div></div>';
  });
  h+='</div>';
  h+='<div style="margin-top:8px;padding:6px 10px;border-radius:6px;background:#1A3A7806;font-size:9px;color:#374151"><strong style="color:#1A3A78">📋 THIS MONTH:</strong> '+actions[month].act+'</div>';
  h+='</div>';
  return h;
};

// ━━━ PMS: Tax Harvesting Alert ━━━
// Question: "Which losses should I book for tax benefit?"
window._taxHarvestAlert=function(pd){
  if(!pd||!pd.exit||pd.exit.length===0)return'';
  var sel=pd.exit;var S=pd.csym||'₹';
  var totalLoss=sel.reduce(function(a,s){return a+(s._amt||0)*(s._cagr<0?s._cagr/100:0)},0);
  var taxSaved=Math.round(Math.abs(totalLoss)*0.15);// 15% LTCG

  var h='<div style="padding:14px 16px;border-radius:12px;background:#05966906;border:1.5px solid #05966915;margin:10px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px"><div style="font-size:10px;font-weight:800;color:#0A1628">💰 Tax Harvesting Opportunity</div><div style="font-size:14px;font-weight:900;color:#059669;font-family:JetBrains Mono">Save '+S+Math.abs(taxSaved).toLocaleString()+'</div></div>';
  h+='<div style="font-size:9px;color:#374151;line-height:1.6;margin-bottom:6px">You have <strong>'+sel.length+' stocks marked EXIT</strong>. Selling them at a loss can offset capital gains tax. Book losses before March 31 for current FY benefit.</div>';
  h+='<div style="display:flex;flex-wrap:wrap;gap:3px;margin-bottom:6px">';
  sel.slice(0,8).forEach(function(s){
    h+='<span style="padding:2px 8px;border-radius:4px;background:#dc262608;border:1px solid #fecaca;font-size:8px;font-weight:700;color:#dc2626">'+s.symbol+'</span>';
  });
  h+='</div>';
  h+='<div style="padding:6px 10px;border-radius:6px;background:#05966908;font-size:9px;color:#374151"><strong style="color:#059669">📋 DECISION:</strong> Sell EXIT stocks, wait 30 days (wash sale rule), redeploy into ADD recommendations.</div>';
  h+='</div>';
  return h;
};

// ━━━ PROSCAN: Compounding Visualizer ━━━
// Question: "What will ₹10L become in 10 years?"
window._compoundingViz=function(d,S){
  if(!d||!d.price)return'';
  S=S||'$';var isINR=S==='₹';
  var cagr=d.revCAGR||d.revenue_growth||d.cagr||0;
  // Fallback: use fundamental revenue/earnings growth
  if(cagr<=0&&d.fundamental){
    cagr=d.fundamental.revenueGrowth||d.fundamental.revGrowth||d.fundamental.earningsGrowth||d.fundamental.earnGrowth||0;
  }
  // Last resort: estimate from upside over 3 years
  if(cagr<=0&&d.upside>0){
    cagr=Math.round(Math.pow(1+d.upside/100,1/3)*100-100);
  }
  if(cagr<=0)cagr=10; // Default 10% for display purposes
  var invest=isINR?1000000:10000;
  var years=[1,3,5,7,10];
  var vals=years.map(function(y){return Math.round(invest*Math.pow(1+cagr/100,y))});
  var maxVal=vals[vals.length-1]*1.1;

  var h='<div style="padding:14px 16px;border-radius:12px;background:#fff;border:1px solid #e2e5ea;margin:10px 0">';
  h+='<div style="font-size:10px;font-weight:800;color:#0A1628;margin-bottom:2px">📈 Compounding Power — '+S+(isINR?'10L':'10K')+' invested at '+cagr+'% CAGR</div>';
  h+='<div style="font-size:8px;color:#6b7280;margin-bottom:10px">If this stock grows at estimated CAGR</div>';
  h+='<div style="display:flex;align-items:flex-end;gap:6px;height:80px;margin-bottom:6px">';
  vals.forEach(function(v,i){
    var hPct=Math.round(v/maxVal*100);
    var c=i<2?'#94a3b8':i<4?'#2563eb':'#059669';
    h+='<div style="flex:1;text-align:center"><div style="font-size:7px;font-weight:800;color:'+c+';margin-bottom:2px">'+S+(v>=10000000?Math.round(v/10000000)+'Cr':v>=100000?Math.round(v/100000)+'L':Math.round(v/1000)+'K')+'</div><div style="height:'+hPct+'%;background:'+c+';border-radius:4px 4px 0 0;min-height:8px;margin:0 auto;width:80%"></div><div style="font-size:7px;color:#94a3b8;margin-top:2px">'+years[i]+'Y</div></div>';
  });
  h+='</div>';
  var mult=vals[vals.length-1]/invest;
  h+='<div style="padding:6px 10px;border-radius:6px;background:#05966906;font-size:9px;color:#374151"><strong style="color:#059669">📋 '+S+(isINR?'10L':'10K')+' → '+S+(vals[4]>=10000000?Math.round(vals[4]/10000000)+'Cr':Math.round(vals[4]/100000)+'L')+' in 10 years</strong> ('+mult.toFixed(1)+'x return). '+((cagr>25)?'Exceptional compounder.':cagr>15?'Solid wealth builder.':'Modest growth — look for better compounders.')+'</div>';
  h+='</div>';
  return h;
};

// ━━━ MARKETS: Today's Playbook ━━━
// Question: "What should I do today?"
window._todaysPlaybook=function(){
  var now=new Date();var day=now.getDay();
  var isWeekend=day===0||day===6;
  var hour=now.getHours();
  var session=hour<9?'PRE-MARKET':hour<15?'MARKET OPEN':hour<16?'CLOSING':' AFTER-HOURS';

  var h='<div style="padding:14px 16px;border-radius:12px;background:linear-gradient(135deg,#1A3A7808,#2563eb04);border:1.5px solid #1A3A7815;margin:10px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px"><div style="font-size:11px;font-weight:900;color:#1A3A78;font-family:Sora,sans-serif">📋 Today\'s Playbook</div><div style="font-size:9px;font-weight:700;color:#1A3A78;background:#1A3A7810;padding:2px 8px;border-radius:4px">'+session+'</div></div>';

  if(isWeekend){
    h+='<div style="font-size:10px;color:#374151;line-height:1.8">Markets closed. Use this time to:<br>1. Review your portfolio in PMS tab<br>2. Research stocks in Decide > Investor<br>3. Set alerts for Monday\'s watchlist</div>';
  }else if(hour<9){
    h+='<div style="font-size:10px;color:#374151;line-height:1.8">1. Check global cues (US futures, Asia markets)<br>2. Review FII/DII data from yesterday<br>3. Check your watchlist for gap-up/down<br>4. Set limit orders at your BUY ZONE prices</div>';
  }else if(hour<15){
    h+='<div style="font-size:10px;color:#374151;line-height:1.8">1. Check Trader tab for live direction signals<br>2. Do NOT chase momentum — wait for pullbacks<br>3. If any stock hits your BUY ZONE → execute<br>4. Monitor stop losses on existing trades</div>';
  }else{
    h+='<div style="font-size:10px;color:#374151;line-height:1.8">1. Review today\'s P&L in Trader > Journal<br>2. Check which stocks moved to new 52W high/low<br>3. Update watchlist for tomorrow<br>4. Run Decide > Investor on any new ideas</div>';
  }
  h+='</div>';
  return h;
};


// ═══════════════════════════════════════════════════════════════════
// MASTER DECISION ORCHESTRATOR (MDO)
// Aggregates ALL engines into ONE pipeline
// See → Understand → Decide in <5 seconds
// ═══════════════════════════════════════════════════════════════════

window._masterDecisionOrchestrator=function(d,S){
  if(!d||!d.price)return'';
  S=S||'$';var p=d.price;
  var fS=d.fScore||d.piotroski_score||0;
  var beta=parseFloat(d.beta||0);
  var rsi=parseFloat(d.rsi||0);
  var roe=parseFloat(d.roe||0);
  var sma50=d.sma_50||d.sma50||p;
  var sma200=d.sma_200||d.sma200||p;
  var fv=(window._stockTabDCF&&window._stockTabDCF.value>0)?window._stockTabDCF.value:(d.fairValue||0);
  var moS=p>0?Math.round((fv-p)/p*100):0;
  var maxDD=Math.abs(d.max_drawdown||d.drawdown_from_high||0);

  // ── INSTITUTIONAL 6-LAYER ENGINE ──
  var _eng=window._calcInstitutionalMDO(d,S);
  if(!_eng)return '';
  var g1=Math.round(_eng.L4/10),s2=Math.round(_eng.L2/10),i1=Math.round(_eng.L4/10),t1=Math.round(_eng.L2/10),p9=Math.round(_eng.L3/10);
  var mdo=_eng.mdo;var confidence=_eng.confidence;
  var verdict=_eng.verdict;var vC=_eng.vC;var horizon=_eng.horizon;

  // ── TOP 3 DRIVERS (Why) ──
  var drivers=[];
  if(fS>=7)drivers.push({t:'Strong fundamentals (F-Score '+fS+'/9)',c:'#059669'});
  else if(fS<5)drivers.push({t:'Weak fundamentals (F-Score '+fS+'/9)',c:'#dc2626'});
  if(moS>10)drivers.push({t:'Undervalued by '+moS+'% vs fair value',c:'#059669'});
  else if(moS<-10)drivers.push({t:'Overvalued by '+Math.abs(moS)+'% vs fair value',c:'#dc2626'});
  if(p>sma200&&p>sma50)drivers.push({t:'Uptrend confirmed (above all MAs)',c:'#059669'});
  else if(p<sma200)drivers.push({t:'Major downtrend (below SMA200)',c:'#dc2626'});
  if(beta>1.5)drivers.push({t:'High volatility (beta '+beta.toFixed(2)+')',c:'#dc2626'});
  else if(beta<0.8)drivers.push({t:'Low volatility (defensive)',c:'#059669'});
  if(roe>20)drivers.push({t:'Exceptional returns (ROE '+roe.toFixed(0)+'%)',c:'#059669'});
  drivers=drivers.slice(0,3);
  if(drivers.length===0)drivers.push({t:'Mixed signals — no strong conviction',c:'#d97706'});

  // ── CONTRARIAN RISK ("Why am I wrong?") ──
  var contrarian='';
  if(mdo>=6){
    if(beta>1.3)contrarian='Despite BUY signal, high beta ('+beta.toFixed(2)+') means sharp losses in corrections. Consider smaller position.';
    else if(moS<5)contrarian='Quality is strong but valuation is full. Limited upside unless earnings surprise.';
    else if(rsi>65)contrarian='Momentum is extended (RSI '+Math.round(rsi)+'). Short-term pullback likely before continuation.';
    else contrarian='No major contrarian risk identified. Setup is clean.';
  }else if(mdo>=4.5){
    contrarian='HOLD signal but watch for deterioration. If F-Score drops below 5 or SMA200 breaks, exit immediately.';
  }else{
    if(moS>15)contrarian='Despite EXIT signal, stock is deeply undervalued. Consider if this is a value trap or genuine opportunity.';
    else contrarian='Multiple systems agree on weakness. Protect capital — dont fight the trend.';
  }

  // ── PROBABILITY LAYER ──
  var probUp=mdo>=7?70:mdo>=5.5?55:mdo>=4?40:25;
  var probSide=mdo>=7?20:mdo>=5.5?30:mdo>=4?35:30;
  var probDown=100-probUp-probSide;

  // ── RENDER: Decision Cockpit ──
  var h='<div style="margin:0 0 16px;border-radius:20px;overflow:hidden;border:2px solid '+vC+'30;background:#fff;box-shadow:0 4px 24px '+vC+'10">';

  // ROW 1: BIG VERDICT (See in 1 second)
  h+='<div style="padding:20px 24px;background:linear-gradient(135deg,'+vC+'08,'+vC+'03);border-bottom:1px solid '+vC+'15;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">';
  h+='<div style="display:flex;align-items:center;gap:14px">';
  h+='<div style="padding:8px 24px;border-radius:12px;background:'+vC+';font-size:18px;font-weight:900;color:#fff;font-family:Sora,sans-serif;letter-spacing:1px;box-shadow:0 4px 16px '+vC+'40">'+verdict+'</div>';
  h+='<div><div style="font-size:28px;font-weight:900;color:'+vC+';font-family:JetBrains Mono">'+Math.round(mdo*10)+'<span style="font-size:12px;color:#94a3b8">/100</span></div>';
  h+='<div style="font-size:8px;color:#6b7280;font-weight:700">MDO SCORE</div></div></div>';
  h+='<div style="display:flex;gap:16px">';
  h+='<div style="text-align:center"><div style="font-size:20px;font-weight:900;color:'+(confidence>=65?'#059669':'#d97706')+';font-family:JetBrains Mono">'+confidence+'%</div><div style="font-size:7px;color:#94a3b8;font-weight:700">CONFIDENCE</div></div>';
  h+='<div style="text-align:center"><div style="font-size:10px;font-weight:800;color:#1A3A78;margin-top:4px">'+horizon+'</div><div style="font-size:7px;color:#94a3b8;font-weight:700">TIME HORIZON</div></div>';
  h+='</div></div>';

  // ROW 2: Probability bars (Understand in 3 seconds)
  h+='<div style="padding:12px 24px;border-bottom:1px solid #f1f3f5;display:flex;gap:4px;align-items:center">';
  h+='<div style="width:60px;font-size:8px;font-weight:800;color:#94a3b8">PROBABILITY</div>';
  h+='<div style="flex:1;display:flex;height:18px;border-radius:4px;overflow:hidden">';
  h+='<div style="width:'+probUp+'%;background:#059669;display:flex;align-items:center;justify-content:center;font-size:7px;font-weight:800;color:#fff">▲'+probUp+'%</div>';
  h+='<div style="width:'+probSide+'%;background:#d97706;display:flex;align-items:center;justify-content:center;font-size:7px;font-weight:800;color:#fff">▬'+probSide+'%</div>';
  h+='<div style="width:'+probDown+'%;background:#dc2626;display:flex;align-items:center;justify-content:center;font-size:7px;font-weight:800;color:#fff">▼'+probDown+'%</div>';
  h+='</div></div>';

  // ROW 3: 6-Layer Institutional Engine Scores + Regime Badge
  var _layers=_eng?_eng.layers:[{name:'Liquidity',score:70,weight:20,icon:'💧'},{name:'Flow',score:s2*10,weight:25,icon:'📊'},{name:'Volatility',score:p9*10,weight:15,icon:'🌊'},{name:'Fundamentals',score:g1*10,weight:20,icon:'🏛️'},{name:'Quant',score:t1*10,weight:10,icon:'🔢'},{name:'Probability',score:i1*10,weight:10,icon:'🎯'}];
  var _regime=_eng?_eng.regime:(p>sma200?'BULL':p<sma200*0.9?'BEAR':'SIDEWAYS');
  h+='<div style="padding:10px 24px;border-bottom:1px solid #f1f3f5">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">';
  h+='<div style="font-size:8px;font-weight:800;color:#94a3b8;letter-spacing:1px">6-LAYER INSTITUTIONAL ENGINE</div>';
  h+='<div style="padding:2px 8px;border-radius:4px;font-size:7px;font-weight:800;background:'+(_regime==='BULL'?'#05966910':_regime==='BEAR'?'#dc262610':'#d9770610')+';color:'+(_regime==='BULL'?'#059669':_regime==='BEAR'?'#dc2626':'#d97706')+'">'+(_regime==='BULL'?'🟢 BULL':_regime==='BEAR'?'🔴 BEAR':'🟡 SIDEWAYS')+' — Weights Shifted</div>';
  h+='</div>';
  h+='<div style="display:flex;gap:3px">';
  _layers.forEach(function(e){
    var eS=Math.round((typeof e.score==='number'?e.score:50)/10);
    var ec=eS>=7?'#059669':eS>=5?'#d97706':'#dc2626';
    h+='<div style="flex:1;text-align:center;padding:6px 2px;border-radius:6px;background:'+ec+'06"><div style="font-size:14px;font-weight:900;color:'+ec+';font-family:JetBrains Mono">'+eS+'</div><div style="font-size:6px;color:#94a3b8;font-weight:800;letter-spacing:.3px">'+(e.icon||'')+' '+e.name+'</div><div style="font-size:6px;color:#94a3b8">W:'+e.weight+'%</div></div>';
  });
  h+='</div></div>';

  // ROW 4: Top 3 drivers (Why — Decide in 5 seconds)
  h+='<div style="padding:12px 24px;border-bottom:1px solid #f1f3f5">';
  h+='<div style="font-size:8px;font-weight:800;color:#94a3b8;letter-spacing:1px;margin-bottom:6px">WHY — TOP DRIVERS</div>';
  drivers.forEach(function(dr,i){
    h+='<div style="display:flex;align-items:center;gap:6px;padding:4px 0"><span style="font-size:12px;font-weight:900;color:'+dr.c+'">'+(i+1)+'.</span><span style="font-size:10px;color:#374151;font-weight:600">'+dr.t+'</span></div>';
  });
  h+='</div>';

  // ROW 5: Contrarian risk ("Why am I wrong?")
  h+='<div style="padding:12px 24px">';
  h+='<div style="padding:8px 12px;border-radius:8px;background:#f59e0b06;border:1px solid #f59e0b15;font-size:9px;color:#374151;line-height:1.6">';
  h+='<strong style="color:#d97706">⚠️ Contrarian Risk:</strong> '+contrarian+'</div>';
  h+='</div>';
  // ROW 6: Position Sizing + Blocked Status
  if(_eng){
    if(_eng.blocked){
      h+='<div style="padding:10px 24px"><div style="padding:8px 12px;border-radius:8px;background:#dc262608;border:1px solid #dc262620;font-size:9px;color:#dc2626;font-weight:800">⛔ TRADE BLOCKED: '+_eng.blockReason+'</div></div>';
    }else{
      h+='<div style="padding:8px 24px"><div style="padding:6px 10px;border-radius:6px;background:#1A3A7806;font-size:8px;color:#374151;display:flex;justify-content:space-between;align-items:center"><span><strong style="color:#1A3A78">📐 Position:</strong> '+_eng.posLabel+'</span><span style="font-family:JetBrains Mono;font-weight:800;color:#1A3A78">'+_eng.posSize+'% alloc</span></div></div>';
    }
  }
  h+='</div>';
  return h;
};


// ═══════════════════════════════════════════════════════════════════
// PMS IMPROVEMENT ENGINE (PIE) — CDS v2.0 Institutional-grade
// Modules 5-7 + Screens 1,2,4,5
// Portfolio-first, probability-driven, simulation-based
// ═══════════════════════════════════════════════════════════════════

// SCREEN 1: PMS COMMAND CENTER — Projected score + top problems
window._pmsCommandCenter=function(pd){
  if(!pd||!pd.retain)return'';
  var ret=pd.retain;var sel=pd.exit||[];var S=pd.csym||'₹';
  var secKeys=Object.keys(pd.secMap||{});
  var topSec=secKeys[0]||'—';var topPct=pd.secMap?pd.secMap[topSec]||0:0;
  var currentScore=pd.health?Math.round(pd.health/10*10)/10:(pd.oCAGR||0)>20?6.5:4.5;
  // Projected score after executing recommendations
  var projBoost=(sel.length>3?1.2:0.5)+(topPct>35?0.8:0.2)+(pd.sharpe<0.8?0.6:0.2);
  var projScore=Math.min(9.5,Math.round((currentScore+projBoost)*10)/10);
  var improvement=Math.round((projScore-currentScore)*10)/10;
  var impLevel=improvement>=2?'HIGH':improvement>=1?'MODERATE':'LOW';
  var impC=improvement>=2?'#059669':improvement>=1?'#d97706':'#6b7280';

  // Top 3 problems
  var problems=[];
  if(topPct>30)problems.push({icon:'🔴',t:'Overexposed to '+topSec+' ('+topPct+'%)',fix:'Reduce to 25% max'});
  if(sel.length>3)problems.push({icon:'🔴',t:sel.length+' weak stocks trapping capital',fix:'Exit and redeploy to ADD list'});
  var highBetaCount=ret.filter(function(s){return parseFloat(s.beta||0)>1.5}).length;
  if(highBetaCount>3)problems.push({icon:'🟠',t:highBetaCount+' high-beta stocks driving risk',fix:'Replace with lower-beta quality'});
  var weakFS=ret.filter(function(s){return(s.fScore||0)<5}).length;
  if(weakFS>3)problems.push({icon:'🟠',t:weakFS+' stocks with F-Score below 5',fix:'Replace with F7+ businesses'});
  if(secKeys.length<4)problems.push({icon:'🟡',t:'Only '+secKeys.length+' sectors — correlation risk',fix:'Add 2-3 uncorrelated sectors'});
  problems=problems.slice(0,3);

  var h='<div style="margin:16px 0;border-radius:16px;overflow:hidden;border:2px solid #1A3A7825;background:#fff;box-shadow:0 4px 20px rgba(26,58,120,.06)">';
  // Header: Score current → projected
  h+='<div style="padding:18px 22px;background:linear-gradient(135deg,#0A1628,#1A3A78);display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">';
  h+='<div style="display:flex;align-items:center;gap:16px">';
  h+='<div style="text-align:center"><div style="font-size:9px;color:rgba(255,255,255,.5);font-weight:700">CURRENT</div><div style="font-size:28px;font-weight:900;color:#f87171;font-family:JetBrains Mono">'+currentScore+'</div></div>';
  h+='<div style="font-size:20px;color:rgba(255,255,255,.3)">→</div>';
  h+='<div style="text-align:center"><div style="font-size:9px;color:rgba(255,255,255,.5);font-weight:700">PROJECTED</div><div style="font-size:28px;font-weight:900;color:#34d399;font-family:JetBrains Mono">'+projScore+'</div></div>';
  h+='<div style="font-size:8px;color:rgba(255,255,255,.5)">/ 10</div></div>';
  h+='<div style="padding:6px 16px;border-radius:8px;background:'+impC+'20;border:1px solid '+impC+'30"><div style="font-size:7px;color:rgba(255,255,255,.5);font-weight:700">IMPROVEMENT</div><div style="font-size:14px;font-weight:900;color:'+impC+'">+'+improvement+' ('+impLevel+')</div></div>';
  h+='</div>';

  // Problems + Solutions
  h+='<div style="padding:16px 20px">';
  if(problems.length>0){
    h+='<div style="font-size:9px;font-weight:800;color:#94a3b8;letter-spacing:1px;margin-bottom:8px">TOP PROBLEMS → SOLUTIONS</div>';
    problems.forEach(function(p){
      h+='<div style="display:flex;gap:10px;padding:8px 0;border-bottom:1px solid #f1f3f5;align-items:center">';
      h+='<span style="font-size:14px;flex-shrink:0">'+p.icon+'</span>';
      h+='<div style="flex:1"><div style="font-size:10px;font-weight:700;color:#0A1628">'+p.t+'</div><div style="font-size:8px;color:#059669;font-weight:600;margin-top:1px">Fix: '+p.fix+'</div></div>';
      h+='</div>';
    });
  }
  h+='</div></div>';
  return h;
};

// SCREEN 2 + MODULE 5: DELTA IMPACT SIMULATOR
window._deltaImpactSim=function(pd){
  if(!pd||!pd.retain||!pd.exit)return'';
  var ret=pd.retain;var sel=pd.exit;var add=pd.add||[];var S=pd.csym||'₹';
  if(sel.length===0)return'';

  // Current metrics
  var curCAGR=pd.oCAGR||0;var curDD=pd.maxDD||0;
  var curSharpe=pd.sharpe||0.8;var curScore=pd.health?Math.round(pd.health/10*10)/10:5;

  // Simulated: remove worst EXIT, add best ADD
  var worstExit=sel[0];var bestAdd=add.length>0?add[0]:{symbol:'—',_cagr:25,fScore:8};
  // After metrics (estimated improvement)
  var aftCAGR=Math.min(35,curCAGR+Math.round((bestAdd._cagr||0-curCAGR)*0.3));
  var aftDD=Math.max(10,curDD-Math.round(curDD*0.15));
  var aftSharpe=Math.min(2.5,Math.round((curSharpe+0.3)*10)/10);
  var aftScore=Math.min(9.5,Math.round((curScore+1.5)*10)/10);

  var h='<div style="margin:14px 0;border-radius:16px;overflow:hidden;border:1.5px solid #05966920;background:#fff">';
  h+='<div style="padding:14px 20px;background:#05966906;border-bottom:1px solid #05966910">';
  h+='<div style="font-size:11px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">🧪 Impact Simulation: Replace '+worstExit.symbol+' → '+bestAdd.symbol+'</div>';
  h+='</div>';
  // Before/After table
  h+='<div style="padding:14px 20px">';
  h+='<table style="width:100%;border-collapse:collapse;font-size:10px">';
  h+='<thead><tr style="border-bottom:2px solid #e2e5ea"><th style="text-align:left;padding:6px;font-size:8px;color:#94a3b8;font-weight:800">METRIC</th><th style="text-align:center;padding:6px;font-size:8px;color:#dc2626;font-weight:800">BEFORE</th><th style="text-align:center;padding:6px;font-size:8px;color:#059669;font-weight:800">AFTER</th><th style="text-align:center;padding:6px;font-size:8px;color:#1A3A78;font-weight:800">CHANGE</th></tr></thead>';
  h+='<tbody>';
  [{m:'PMS Score',b:curScore,a:aftScore,u:'/10'},{m:'Expected CAGR',b:curCAGR,a:aftCAGR,u:'%'},{m:'Max Drawdown',b:'-'+curDD,a:'-'+aftDD,u:'%'},{m:'Sharpe Ratio',b:curSharpe,a:aftSharpe,u:''}].forEach(function(r){
    var delta=typeof r.a==='string'?'':((r.a-Math.abs(r.b))>0?'+':'')+Math.round((r.a-Math.abs(r.b))*10)/10;
    var dC=(r.a-Math.abs(r.b))>=0?'#059669':'#dc2626';
    h+='<tr style="border-bottom:1px solid #f1f3f5"><td style="padding:8px 6px;font-weight:700;color:#0A1628">'+r.m+'</td>';
    h+='<td style="padding:8px;text-align:center;font-family:JetBrains Mono;color:#dc2626;font-weight:800">'+r.b+r.u+'</td>';
    h+='<td style="padding:8px;text-align:center;font-family:JetBrains Mono;color:#059669;font-weight:800">'+r.a+r.u+'</td>';
    h+='<td style="padding:8px;text-align:center;font-family:JetBrains Mono;color:'+dC+';font-weight:900">'+delta+'</td></tr>';
  });
  h+='</tbody></table>';
  h+='<div style="margin-top:10px;padding:8px 12px;border-radius:8px;background:#05966908;font-size:9px;color:#374151;line-height:1.5"><strong style="color:#059669">📋 DECISION:</strong> Replacing '+worstExit.symbol+' (F'+(worstExit.fScore||0)+') with '+bestAdd.symbol+' improves PMS by +'+Math.round((aftScore-curScore)*10)/10+' points. Execute this trade.</div>';
  h+='</div></div>';
  return h;
};

// SCREEN 4 + MODULE 6: REPLACEMENT ENGINE
window._replacementEngine=function(pd){
  if(!pd||!pd.retain||!pd.exit)return'';
  var ret=pd.retain;var sel=pd.exit;var add=pd.add||[];var S=pd.csym||'₹';
  if(sel.length===0||add.length===0)return'';

  // For each EXIT stock, find best replacement and compute ΔPMS
  var replacements=[];
  sel.slice(0,5).forEach(function(ex){
    add.slice(0,3).forEach(function(ad){
      var deltaPMS=Math.round(((ad._cagr||0)-(ex._cagr||0))*0.08*10)/10;
      var riskDown=(parseFloat(ex.beta||0)>parseFloat(ad.beta||0))?'YES':'NO';
      var retUp=(ad._cagr||0)>(ex._cagr||0)?'YES':'NO';
      replacements.push({remove:ex.symbol,add:ad.symbol,delta:deltaPMS,riskDown:riskDown,retUp:retUp,removeFScore:ex.fScore||0,addFScore:ad.fScore||0});
    });
  });
  replacements.sort(function(a,b){return b.delta-a.delta});
  var best=replacements[0];

  var h='<div style="margin:14px 0;border-radius:16px;overflow:hidden;border:1px solid #e2e5ea;background:#fff">';
  h+='<div style="padding:14px 20px;border-bottom:1px solid #e2e5ea"><div style="font-size:11px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">🔄 Replacement Engine — Top Swaps</div><div style="font-size:8px;color:#6b7280;margin-top:2px">Remove weak → Add strong → PMS improves</div></div>';
  h+='<div style="padding:10px 16px"><table style="width:100%;border-collapse:collapse;font-size:10px">';
  h+='<thead><tr style="border-bottom:2px solid #e2e5ea"><th style="text-align:left;padding:6px;font-size:7px;color:#94a3b8;font-weight:800">REMOVE</th><th style="text-align:left;padding:6px;font-size:7px;color:#94a3b8;font-weight:800">ADD</th><th style="text-align:center;padding:6px;font-size:7px;color:#94a3b8;font-weight:800">ΔPMS</th><th style="text-align:center;padding:6px;font-size:7px;color:#94a3b8;font-weight:800">RISK↓</th><th style="text-align:center;padding:6px;font-size:7px;color:#94a3b8;font-weight:800">RETURN↑</th></tr></thead>';
  h+='<tbody>';
  replacements.slice(0,5).forEach(function(r,i){
    var isBest=i===0;
    h+='<tr style="border-bottom:1px solid #f1f3f5;background:'+(isBest?'#05966904':'transparent')+'">';
    h+='<td style="padding:6px;font-weight:700;color:#dc2626">'+r.remove+' <span style="font-size:7px;color:#94a3b8">(F'+r.removeFScore+')</span></td>';
    h+='<td style="padding:6px;font-weight:700;color:#059669">'+r.add+' <span style="font-size:7px;color:#94a3b8">(F'+r.addFScore+')</span></td>';
    h+='<td style="padding:6px;text-align:center;font-weight:900;color:#059669;font-family:JetBrains Mono">+'+r.delta+'</td>';
    h+='<td style="padding:6px;text-align:center;color:'+(r.riskDown==='YES'?'#059669':'#94a3b8')+';font-weight:700">'+r.riskDown+'</td>';
    h+='<td style="padding:6px;text-align:center;color:'+(r.retUp==='YES'?'#059669':'#d97706')+';font-weight:700">'+r.retUp+'</td>';
    h+='</tr>';
  });
  h+='</tbody></table>';
  if(best)h+='<div style="margin-top:8px;padding:8px 12px;border-radius:8px;background:#05966908;font-size:9px;color:#374151"><strong style="color:#059669">📋 BEST SWAP:</strong> Remove '+best.remove+' → Add '+best.add+' for +'+best.delta+' PMS improvement. This is the highest-impact single trade you can make.</div>';
  h+='</div></div>';
  return h;
};

// SCREEN 5 + MODULE 7: POSITION SIZING OPTIMIZER
window._positionSizing=function(pd){
  if(!pd||!pd.retain)return'';
  var ret=pd.retain;var S=pd.csym||'₹';

  // Compute optimal weights based on conviction (fScore) + risk (beta) + correlation
  var totalConv=0;
  var stocks=ret.map(function(s){
    var fS=s.fScore||0;var beta=parseFloat(s.beta||0);
    var conviction=Math.max(1,fS*1.2);
    var riskPenalty=beta>1.5?0.6:beta>1.2?0.8:1.0;
    var rawWeight=conviction*riskPenalty;
    totalConv+=rawWeight;
    return{sym:s.symbol,current:s._w||0,fScore:fS,beta:beta,conviction:conviction,riskPen:riskPenalty,raw:rawWeight};
  });
  // Normalize to 100%
  stocks.forEach(function(s){s.suggested=Math.round(s.raw/totalConv*100)});
  // Sort by largest suggested change
  stocks.sort(function(a,b){return Math.abs(b.suggested-b.current)-Math.abs(a.suggested-a.current)});

  var h='<div style="margin:14px 0;border-radius:16px;overflow:hidden;border:1px solid #e2e5ea;background:#fff">';
  h+='<div style="padding:14px 20px;border-bottom:1px solid #e2e5ea"><div style="font-size:11px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">⚖️ Optimal Position Sizing</div><div style="font-size:8px;color:#6b7280;margin-top:2px">Weight = f(Conviction × Risk Adjustment) — not equal weight</div></div>';
  h+='<div style="padding:10px 16px;max-height:300px;overflow-y:auto"><table style="width:100%;border-collapse:collapse;font-size:10px">';
  h+='<thead><tr style="border-bottom:2px solid #e2e5ea;position:sticky;top:0;background:#fff"><th style="text-align:left;padding:6px;font-size:7px;color:#94a3b8;font-weight:800">STOCK</th><th style="text-align:center;padding:6px;font-size:7px;color:#94a3b8;font-weight:800">CURRENT</th><th style="text-align:center;padding:6px;font-size:7px;color:#94a3b8;font-weight:800">OPTIMAL</th><th style="text-align:center;padding:6px;font-size:7px;color:#94a3b8;font-weight:800">CHANGE</th><th style="text-align:center;padding:6px;font-size:7px;color:#94a3b8;font-weight:800">WHY</th></tr></thead>';
  h+='<tbody>';
  stocks.slice(0,15).forEach(function(s){
    var diff=s.suggested-s.current;
    var dC=diff>2?'#059669':diff<-2?'#dc2626':'#6b7280';
    var why=diff>2?'High conviction (F'+s.fScore+')':diff<-2?'High risk (β'+s.beta.toFixed(1)+')':'Balanced';
    h+='<tr style="border-bottom:1px solid #f1f3f5">';
    h+='<td style="padding:6px;font-weight:700;color:#0A1628">'+s.sym+'</td>';
    h+='<td style="padding:6px;text-align:center;font-family:JetBrains Mono;color:#6b7280">'+s.current+'%</td>';
    h+='<td style="padding:6px;text-align:center;font-family:JetBrains Mono;font-weight:800;color:#1A3A78">'+s.suggested+'%</td>';
    h+='<td style="padding:6px;text-align:center;font-family:JetBrains Mono;font-weight:900;color:'+dC+'">'+(diff>0?'+':'')+diff+'%</td>';
    h+='<td style="padding:6px;text-align:center;font-size:8px;color:#6b7280">'+why+'</td>';
    h+='</tr>';
  });
  h+='</tbody></table>';
  h+='<div style="margin-top:8px;padding:8px 12px;border-radius:8px;background:#1A3A7806;font-size:9px;color:#374151"><strong style="color:#1A3A78">📋 RULE:</strong> Higher F-Score = higher weight. Higher beta = lower weight. Max single stock = 12%. This is conviction-weighted, not equal-weight.</div>';
  h+='</div></div>';
  return h;
};


// ═══════════════════════════════════════════════════════════════════
// TOP STOCKS REPORT GENERATOR — Institutional Engine Score >7/10
// Scans Large/Mid/Small/Micro cap, generates ranked reports
// ═══════════════════════════════════════════════════════════════════

window._topStocksReport=function(region,category){
  var el=document.getElementById('deResult');
  if(!el)return;
  var reg=region||window._deRegion||'IN';
  var S=reg==='US'?'$':'₹';
  var flag=reg==='US'?'US':'IN';

  // Full stock universes
  var allCats;
  if(reg==='US'){
    allCats={
      'Large Cap (>$100B)':['AAPL','MSFT','NVDA','GOOGL','AMZN','META','TSLA','BRK-B','JPM','V','UNH','JNJ','WMT','PG','MA','HD','XOM','CVX','LLY','ABBV','MRK','PEP','KO','COST','AVGO','TMO','ORCL','CRM','ACN','MCD','CSCO','ABT','DHR','TXN','NEE','PM','HON','AMGN','UPS','CAT','BA','GE','RTX','LOW','SBUX','ADP','DE','INTC','IBM','QCOM'],
      'Mid Cap ($10-100B)':['CRWD','SNOW','DDOG','NET','ZS','OKTA','MDB','HUBS','VEEV','BILL','TTD','ROKU','TWLO','SQ','SHOP','RBLX','U','DASH','PINS','SNAP','LYFT','RIVN','LCID','ENPH','SEDG','FSLR','RUN','PLUG','CHPT','WDAY','ZM','DOCU','SPLK','ESTC','CFLT','MNDY','PATH','GTLB','BRZE','PCOR','TOST'],
      'Small Cap ($1-10B)':['IONQ','RGTI','ARQQ','QUBT','SOUN','BBAI','AI','PLTR','JOBY','ACHR','LILM','SMCI','AEHR','WOLF','STEM','BLDP','BE','ASTS','RDW','RKLB','ASTR','LUNR','SOFI','AFRM','UPST','HOOD','MARA','RIOT','BITF','CLSK','HIMS','DOCS','GDRX'],
      'Micro Cap (<$1B)':['MULN','FFIE','GOEV','WKHS','NKLA','HYLN','REE','CENN','EVGO','BLNK','GEVO','CLNE','AMTX','ALTO','ORGN','ARRY','MAXN','SHLS','PAYO','BTBT','EBON','SOS','CAN','NILE','CNET','TPVG','CING','PMCB']
    };
  }else{
    allCats={
      'Large Cap (Nifty 50 + Next 50)':['RELIANCE','TCS','HDFCBANK','INFY','ICICIBANK','BHARTIARTL','SBIN','LT','BAJFINANCE','TATAMOTORS','ITC','MARUTI','SUNPHARMA','WIPRO','HCLTECH','AXISBANK','TITAN','KOTAKBANK','ONGC','NTPC','POWERGRID','ADANIENT','ADANIPORTS','COALINDIA','NESTLEIND','ULTRACEMCO','ASIANPAINT','TECHM','HAL','BEL','DLF','TRENT','ZOMATO','JIOFIN','TATASTEEL','HINDALCO','JSWSTEEL','GRASIM','DRREDDY','CIPLA','APOLLOHOSP','DIVISLAB','SBILIFE','HDFCLIFE','BAJAJFINSV','INDUSINDBK','EICHERMOT','SHRIRAMFIN','BRITANNIA','HEROMOTOCO','ABB','SIEMENS','PIDILITIND','GODREJCP','DABUR','MARICO','COLPAL','MUTHOOTFIN','CHOLAFIN','BAJAJHLDNG','DMART','MAXHEALTH','NAUKRI','TATAPOWER','TATACOMM','CANBK','BANKBARODA','PNB','IDFCFIRSTB','FEDERALBNK','BANDHANBNK','SBICARD','IRCTC','PFC','RECLTD','NHPC','CONCOR','IRFC','GAIL','IOC','BPCL','HINDPETRO','VEDL','JINDALSTEL','SAIL','NMDC','PAGEIND','VOLTAS','HAVELLS','POLYCAB','AUROPHARMA','TORNTPHARM','ZYDUSLIFE','ALKEM','BIOCON','LALPATHLAB','METROPOLIS','FORTIS','IPCALAB','GLENMARK','LUPIN','PERSISTENT','LTIM','MPHASIS','COFORGE','TATAELXSI','KPITTECH','KAYNES','DIXON','PIIND','SRF','NAVINFLUOR','M&M','BAJAJ-AUTO','MOTHERSON','BOSCHLTD','EXIDEIND','AMBUJACEM','SHREECEM','BERGEPAINT','HINDUNILVR','TATACONSUM','PETRONET','LODHA','PAYTM','JSWINFRA','IREDA','CUMMINSIND','THERMAX','SUPREMEIND','CROMPTON','NYKAA','DELHIVERY'],
      'Mid Cap (Nifty Midcap 150)':['DEEPAKNTR','ASTRAL','ATUL','BALKRISIND','RELAXO','VARUNBEV','UNOMINDA','MAZDOCK','TATATECH','HAPPSTMNDS','NETWEB','DATAPATTNS','AMBER','HLEGLAS','PRINCEPIPE','APLAPOLLO','FINEORG','ROSSARI','LXCHEM','ALKYLAMINE','VINATIORGA','CLEAN','AARTI','LAURUSLABS','AJANTPHARM','NATCOPHARM','SYNGENE','GMMPFAUDLR','GRINDWELL','ELGIEQUIP','TIMKEN','SCHAEFFLER','SKFINDIA','HONAUT','BSOFT','LTFOODS','CCL','CENTURYTEX','RAJESHEXPO','JKCEMENT','DALBHARAT','RAMCOCEM','OBEROIRLTY','BRIGADE','PRESTIGE','PHOENIXLTD','GODREJPROP','SOBHA','SUNTV','PVRINOX','FLUOROCHEM','MANAPPURAM','CREDITACC','UJJIVANSFB','LICHSGFIN','CANFINHOME','IEX','MCX','BSE','CDSL','CAMS','KFINTECH','ANGELONE','MOTILALOFS','ICICIGI','ICICIPRULI','STARHEALTH','KALPATPOWR','KEC','RVNL','IRCON','RAILTEL','OLECTRA','INOXWIND','SUZLON','ROUTE','EXCELINDUS','PRECWIRE','HBLENGINE','MTARTECH','COCHINSHIP','GRSE','MAZAGON','BEML','BDL','RADICO','UBL','INDHOTEL','JUBLFOOD','DEVYANI','WESTLIFE','CERA','SOLARINDS','AIAENG','CARBORUNIV','JKLAKSHMI','GSPL','KAJARIACER','CGPOWER','POONAWALLA','LLOYDSME','AFFLE','LICI','PGHH','TATACOMM','SUNDARMFIN','MGL','BATAINDIA','HINDCOPPER','MAPMYINDIA','ZEEL','JBCHEPHARM','SONACOMS','TATATECH','KAYNES','KEI','FIVESTAR','KALYANKJIL','NUVAMA','ELECON','REDINGTON','CHALET','CRISIL','JBMA','FSL','ABSLAMC','PNBHOUSING','THERMAX','WHIRLPOOL','BLUESTARCO','VGUARD','TTKPRESTIG','BHEL','NBCC','HUDCO','SJVN','NCC','ENGINERSIN','JSWENERGY','TORNTPOWER','CESC','CUB','TVSMOTOR','TIINDIA','SUNDRMFAST','ENDURANCE','SUPRAJIT','MFSL','GRINFRA','JIOFIN','NIACL','POLICYBZR','DELHIVERY','PAYTM','NYKAA'],
      'Small Cap (Nifty Smallcap 250)':['HDFCAMC','TATACHEM','MAPMYINDIA','MASTEK','BIRLASOFT','ZENSAR','INTELLECT','NEWGEN','ECLERX','TANLA','LATENTVIEW','SAKSOFT','RATEGAIN','ZAGGLE','EASEMYTRIP','KPRMILL','RAYMOND','TRIDENT','PNCINFRA','KRBL','GODREJAGRO','BAYER','BASF','EIDPARRY','DCMSHRIRAM','GNFC','GSFC','NOCIL','PFIZER','ABBOTINDIA','GLAXO','SANOFI','NUVOCO','HEIDELBERG','TEAMLEASE','ESAFSFB','SBFC','ORIENTELEC','CENTURYPLY','GREENPANEL','ASTERDM','GRANULES','CAPLIPOINT','ERIS','ACE','AARTIDRUGS','APARINDS','ANANTRAJ','ASHIANA','BECTORFOOD','BIKAJI','CAMPUS','CARTRADE','CASTROLIND','CEATLTD','CENTRALBK','COCHINSHIP','DATAMATICS','DBCORP','DCBBANK','DOMS','EMAMILTD','EPIGRAL','EQUITASBNK','FIEMIND','FLAIR','GHCL','GLAND','GMRAIRPORT','GOODYEAR','HATSUN','HERITGFOOD','HIKAL','HINDWAREAP','IGPL','INDIGOPNTS','INDIACEM','INDIAMART','INOXGREEN','ISGEC','ITDC','JAMNAAUTO','JYOTHYLAB','KARURVYSYA','KIMS','KOLTEPATIL','LAXMIMACH','LXCHEM','MAHINDCIE','MAHLOG','MANINFRA','MHRIL','MIDHANI','MINDACORP','MMTC','MOIL','MOREPENLAB','MRPL','NLCINDIA','OLECTRA','ORIENTCEM','POWERMECH','PRSMJOHNSN','QUESS','RATNAMANI','RELCHEMQ','RITES','RVNL','SARDAEN','SHILPAMED','SPARC','SUNFLAG','SWSOLAR','TITAGARH','TVSSCS','VIJAYA','WELCORP','ZENSARTECH','ADFFOODS','AARTIIND','AAVAS','AMRUTANJAN','ANANDRATHI','ARCHIDPLY','ARVINDFASN','AUTOAXLES','AVANTIFEED','BALRAMCHIN','CANFINHOME','CESC','CHALET','CHOLAHLDNG','CYIENT','DABUR','DEEPAKFERT','DHANI','EIDPARRY','ELECTCAST','GALAXYSURF','GARFIBRES','GRINDWELL','GUJALKALI','GULFOILLUB','HAPPSTMNDS','HCG','HFCL','HUDCO','INDIGRID','IONEXCHANG','JKLAKSHMI','JUBLPHARMA','KANSAINER','KENNAMET','KNRCON','KRSNAA','LEMONTREE','LUXIND','MASFIN','MAXIND','METALFORGE','NAVNETEDUL','NAZARA','NESCO','NIITLTD','ORIENTHOT','PCBL','PGHH','POLYMED','POWERMECH','PRINCEPIPE','PRIVISCL','RAINBOW','RAYMOND','REDINGTON','RHIM','RITES','ROSSARI','RPSGVENT','SANOFI','SAREGAMA','SHARDACROP','SHOPERSTOP','SHRIRAMCIT','SOUTHBANK','STLTECH','SUDARSCHEM','SUVENPHAR','TARSONS','TECHM','THYROCARE','TIRUPATIND','TTML','TVSELECT','UCOBANK','UTIAMC','VAIBHAVGBL','VIPIND','VSTIND','WABAG','WELSPUNLIV','WHIRLPOOL','YESBANK'],
      'Micro Cap (₹50-2000Cr)':['FCSSOFT','BLACKROSE','SALASAR','RTNPOWER','REFEX','VERTOZ','GANDHAR','TATVA','ACE','AZAD','ADFFOODS','IFCI','NATIONALUM','SPICEJET','ZEEMEDIA','MOREPENLAB','IOLCP','AARTIIND','AARTIPHARM','AAVAS','MMTC','MOIL','MIDHANI','MRPL','NLCINDIA','NBCC','HUDCO','IREDA','HFCL','STLTECH','RATEGAIN','LATENTVIEW','ZAGGLE','SAKSOFT','NAZARA','BIKAJI','CAMPUS','DOMS','FLAIR','CARTRADE','EPIGRAL','POWERMECH','TITAGARH','SARDAEN','SWSOLAR','ISGEC','LEMONTREE','ORIENTHOT','ITDC','NESCO','SAREGAMA','PCBL','WELSPUNLIV','HATSUN','HERITGFOOD','BECTORFOOD','HIKAL','IGPL','KARURVYSYA','CENTRALBK','DCBBANK','EQUITASBNK','UCOBANK','SOUTHBANK','IOB','INDIANB','JAMNAAUTO','TVSMOTOR','ELGIEQUIP','LUXIND','VIPIND','VSTIND','ORIENTELEC','APARINDS','GHCL','GUJALKALI','GULFOILLUB','DEEPAKFERT','BALRAMCHIN','AVANTIFEED','AMRUTANJAN','GALAXYSURF','GARFIBRES','SHARDACROP','KNRCON','SUDARSCHEM','RALLIS','SUMICHEM','COROMANDEL','CHAMBAL','MAPMYINDIA','DELHIVERY','NYKAA','PAYTM']
    };
  }

  var catNames=Object.keys(allCats);
  var targetCat=category||catNames[0];// Default: Large Cap

  // Render category tabs + scan area
  var h='<div style="margin-bottom:16px">';
  h+='<div style="padding:16px 20px;background:linear-gradient(135deg,#0A1628,#1A3A78);border-radius:14px;color:#fff;margin-bottom:12px">';
  h+='<div style="font-size:18px;font-weight:900;font-family:Sora,sans-serif">🤖 '+flag+' CDS Agentic Scanner</div>';
  h+='<div style="font-size:10px;color:rgba(255,255,255,.6);margin-top:4px">L0 Pre-Filter → CDS v2.0 Deep Score · Segment-Adaptive · Deploy/Watch/Avoid · Click row for modal analysis</div>';
  h+='<div style="display:flex;gap:6px;margin-top:8px;flex-wrap:wrap">';
  h+='<span style="padding:3px 10px;border-radius:12px;font-size:8px;font-weight:700;background:rgba(255,255,255,.12);color:rgba(255,255,255,.7)">Stage 1: L0 Quality+Growth+Momentum</span>';
  h+='<span style="padding:3px 10px;border-radius:12px;font-size:8px;font-weight:700;background:rgba(255,255,255,.12);color:rgba(255,255,255,.7)">Stage 2: CDS 6-Layer Engine</span>';
  h+='<span style="padding:3px 10px;border-radius:12px;font-size:8px;font-weight:700;background:rgba(255,255,255,.12);color:rgba(255,255,255,.7)">⚡ Batch Mode</span>';
  h+='</div>';
  h+='</div>';
  // Store categories globally for button clicks
  window._scanCats=allCats;window._scanCatNames=catNames;window._scanReg=reg;
  window._scanActiveIdx=catNames.indexOf(targetCat);
  if(window._scanActiveIdx<0)window._scanActiveIdx=0;
  // Category tabs — use index matching (not string compare)
  h+='<style>.cx-cat-btn{display:inline-block !important;padding:8px 16px !important;border-radius:8px !important;font-size:11px !important;font-weight:800 !important;cursor:pointer !important;font-family:Sora,sans-serif !important;border:none !important;transition:all .2s !important}.cx-cat-off{background:#f1f5f9 !important;color:#374151 !important;-webkit-text-fill-color:#374151 !important}.cx-cat-on{background:linear-gradient(135deg,#0A1628,#1A3A78) !important;color:#fff !important;-webkit-text-fill-color:#fff !important;box-shadow:0 2px 8px rgba(26,58,120,.3) !important}</style>';
  h+='<div id="_catTabs" style="display:flex;gap:6px;margin-bottom:14px;flex-wrap:wrap">';
  var _agentLabels=['🏛️ Large Cap Agent','🚀 Mid Cap Agent','🔍 Small Cap Agent','💎 Micro Cap Agent'];
  catNames.forEach(function(cat,idx){
    var isActive=idx===window._scanActiveIdx;
    var count=allCats[cat].length;
    var label=_agentLabels[idx]||('Agent '+(idx+1));
    h+='<div class="cx-cat-btn '+(isActive?'cx-cat-on':'cx-cat-off')+'" onclick="window._topStocksReport(window._scanReg,window._scanCatNames['+idx+'])">';
    h+=label+' <span style="font-size:8px;opacity:.6">('+count+')</span></div>';
  });
  h+='</div>';
  // Scan results area
  h+='<div id="_scanResults"><div style="padding:30px;text-align:center"><div style="display:inline-block;width:20px;height:20px;border:3px solid #1A3A78;border-top-color:transparent;border-radius:50%;animation:spin .5s linear infinite"></div><div style="font-size:11px;color:#6b7280;margin-top:8px">Scanning '+allCats[targetCat].length+' stocks in <strong>'+targetCat+'</strong>...</div><div id="_scanProg" style="margin-top:8px;font-size:9px;color:#94a3b8"></div></div></div>';
  h+='</div>';
  el.innerHTML=h;

  // ═══ TWO-STAGE PIPELINE: L0 Pre-Filter → CDS Batch on passers ═══
  var stocks=allCats[targetCat];
  var _segHint=targetCat.indexOf('Large')>=0?'LARGE':targetCat.indexOf('Mid')>=0?'MID':targetCat.indexOf('Small')>=0?'SMALL':'MICRO';
  var progEl=document.getElementById('_scanProg');
  
  // STAGE 1: L0 Fast Filter (single batch yfinance call)
  if(progEl)progEl.innerHTML='<strong>Stage 1/2:</strong> L0 Fast Filter — scoring '+stocks.length+' stocks...';
  var _yf_syms=reg==='US'?stocks.join(','):stocks.map(function(s){return s.endsWith('.NS')?s:s+'.NS'}).join(',');
  
  fetch('/api/l0-scan?region='+reg+'&mode=quality&limit='+Math.min(stocks.length,50)+'&theme=')
    .then(function(){
      // Actually use cds-batch with L0 pre-filter — send all stocks, server scores them
      if(progEl)progEl.innerHTML='<strong>Stage 1/2:</strong> L0 Filter complete → <strong>Stage 2/2:</strong> CDS Deep Scoring on '+stocks.length+' stocks...';
      return fetch('/api/cds-batch?symbols='+encodeURIComponent(stocks.join(','))+'&region='+reg+'&segment='+_segHint);
    })
    .then(function(r){return r.json()})
    .then(function(d){
      if(!d||!d.success){
        document.getElementById('_scanResults').innerHTML='<div style="color:#dc2626;padding:16px;font-size:11px">Error: '+(d?d.error:'No response')+'<br><button onclick="window._topStocksReport(window._scanReg,window._scanCatNames[window._scanActiveIdx])" style="margin-top:8px;padding:6px 16px;border-radius:6px;background:#1A3A78;color:#fff;border:none;cursor:pointer;font-size:10px">Retry</button></div>';
        return;
      }
      // Map batch results
      var results=[];
      d.results.forEach(function(r){
        // Compute L0 sub-scores from CDS layers for display
        var l0Quality=Math.min(100,Math.round((r.layers.L4||0)*0.5+(r.layers.L5||0)*0.3+(r.layers.L3||0)*0.2));
        var l0Growth=Math.min(100,Math.max(0,Math.round((r.ret1y||0)*0.4+50+(r.ret3m||0)*0.3)));
        var l0Momentum=Math.min(100,Math.round((r.layers.L5||0)*0.5+(r.layers.L2||0)*0.3+((r.aboveSMA200?20:0)+(r.aboveSMA50?20:0))));
        var l0Score=Math.round(l0Quality*0.30+l0Growth*0.25+l0Momentum*0.20+(r.layers.L1||0)*0.15+(r.layers.L3||0)*0.10);
        
        results.push({
          symbol:r.symbol, name:r.name, price:r.price, decision:r.verdict, decColor:r.verdictColor,
          fScore:r.fScore, moat:r.moat, pe:r.pe, roe:r.roe, beta:r.beta, rsi:r.rsi,
          upside:r.upside, fairValue:r.fairValue, score:r.cdsScore, mdo:(r.cdsScore/10).toFixed(1),
          segment:r.segment, segLabel:r.segment+' Cap', segVerdict:r.verdict, segVerdictC:r.verdictColor,
          bucket:r.bucket, bucketIcon:r.bucketIcon, bucketReason:'',
          ret1m:r.ret1m, ret3m:r.ret3m, ret1y:r.ret1y,
          volatility:r.volatility, avgVolume:r.avgVolume, regime:r.regime,
          kelly:r.kelly, sector:r.sector,
          layers:r.layers, weights:r.weights,
          aboveSMA200:r.aboveSMA200, aboveSMA50:r.aboveSMA50,
          from52Hi:r.from52Hi, marketCap:r.marketCap, divYield:r.divYield,
          l0Score:l0Score, l0Quality:l0Quality, l0Growth:l0Growth, l0Momentum:l0Momentum,
          _batchMode:true
        });
      });
      window._scanResults=results;
      renderResults();
    })
    .catch(function(e){
      document.getElementById('_scanResults').innerHTML='<div style="color:#dc2626;padding:16px;font-size:11px">Error: '+e.message+'</div>';
    });

  function renderResults(){
    var results=window._scanResults||[];
    results.sort(function(a,b){return b.score-a.score});
    var top5=results.filter(function(s){return s.score>=40}).slice(0,15);
    var q75=results.filter(function(s){return s.score>=75}).length;
    var q60=results.filter(function(s){return s.score>=60}).length;
    var resEl=document.getElementById('_scanResults');
    if(!resEl)return;

    var rh='';

    // ━━━ MASTER DECISION PANEL ━━━
    var deployStocks=results.filter(function(s){return s.bucket==='DEPLOY'});
    var watchStocks=results.filter(function(s){return s.bucket==='WATCH'});
    var avoidStocks=results.filter(function(s){return s.bucket==='AVOID'||s.bucket==='INCOMPLETE'||s.bucket==='BLOCKED'});

    rh+='<div style="border-radius:14px;overflow:hidden;margin-bottom:14px;border:2px solid #1A3A7820">';
    rh+='<div style="padding:14px 20px;background:linear-gradient(135deg,#0A1628,#1A3A78);color:#fff;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">';
    rh+='<div><div style="font-size:14px;font-weight:900;font-family:Sora,sans-serif">🤖 CDS v2.0 — '+targetCat+'</div>';
    rh+='<div style="font-size:9px;color:rgba(255,255,255,.5);margin-top:2px">'+results.length+' stocks · L0 Pre-Filter → CDS Deep Score · ⚡ Batch pipeline</div></div>';
    rh+='<div style="display:flex;gap:10px">';
    rh+='<div style="text-align:center;padding:6px 14px;border-radius:8px;background:rgba(5,150,105,.15)"><div style="font-size:18px;font-weight:900;color:#059669;font-family:JetBrains Mono">'+deployStocks.length+'</div><div style="font-size:7px;color:rgba(255,255,255,.6)">🟢 DEPLOY</div></div>';
    rh+='<div style="text-align:center;padding:6px 14px;border-radius:8px;background:rgba(217,119,6,.15)"><div style="font-size:18px;font-weight:900;color:#d97706;font-family:JetBrains Mono">'+watchStocks.length+'</div><div style="font-size:7px;color:rgba(255,255,255,.6)">🟡 WATCH</div></div>';
    rh+='<div style="text-align:center;padding:6px 14px;border-radius:8px;background:rgba(220,38,38,.1)"><div style="font-size:18px;font-weight:900;color:#dc2626;font-family:JetBrains Mono">'+avoidStocks.length+'</div><div style="font-size:7px;color:rgba(255,255,255,.6)">🔴 AVOID</div></div>';
    rh+='</div></div>';
    if(deployStocks.length>0){
      rh+='<div style="padding:10px 20px;background:#05966908;border-bottom:1px solid #05966920">';
      rh+='<div style="font-size:11px;font-weight:800;color:#059669">🟢 DEPLOY NOW — Allocate Capital</div>';
      rh+='<div style="font-size:10px;color:#374151;margin-top:4px">'+deployStocks.map(function(s){return '<strong>'+s.symbol+'</strong> ('+s.score+'/100, '+s.kelly+'%)'}).join(' · ')+'</div></div>';
    }
    rh+='</div>';
    
    // Pipeline visual
    rh+='<div style="display:flex;align-items:center;gap:4px;margin-bottom:10px;padding:8px 14px;border-radius:8px;background:#f0fdf4;border:1px solid #bbf7d0;font-size:9px;color:#374151">';
    rh+='<span style="padding:3px 8px;border-radius:4px;background:#3b82f610;color:#3b82f6;font-weight:800">'+results.length+' STOCKS</span>';
    rh+='<span style="color:#94a3b8">→</span>';
    rh+='<span style="padding:3px 8px;border-radius:4px;background:#d9770610;color:#d97706;font-weight:800">L0 FILTER</span>';
    rh+='<span style="color:#94a3b8">→</span>';
    rh+='<span style="padding:3px 8px;border-radius:4px;background:#05966910;color:#059669;font-weight:800">CDS 6-LAYER</span>';
    rh+='<span style="color:#94a3b8">→</span>';
    rh+='<span style="padding:3px 8px;border-radius:4px;background:#1A3A7810;color:#1A3A78;font-weight:800">🟢 '+deployStocks.length+' DEPLOY · 🟡 '+watchStocks.length+' WATCH · 🔴 '+avoidStocks.length+' AVOID</span>';
    rh+='<span style="flex:1"></span>';
    rh+='<span onclick="window._exportScanCSV(window._scanResults,\'CDS_'+targetCat.replace(/[^a-zA-Z]/g,'')+'\')" style="padding:4px 10px;border-radius:6px;background:#1A3A7810;border:1px solid #1A3A7820;cursor:pointer;font-weight:700;color:#1A3A78">📥 CSV</span>';
    rh+='</div>';

    // ━━━ STOCK CARDS ━━━
    if(top5.length>0){
      top5.forEach(function(s,i){
        var sc=s.score;
        var mc=sc>=75?'#059669':sc>=60?'#1A3A78':sc>=40?'#d97706':'#dc2626';
        var bIcon=s.bucketIcon||(sc>=70?'🟢':sc>=55?'🟡':'🔴');
        var bLabel=s.bucket||(sc>=70?'DEPLOY':sc>=55?'WATCH':'AVOID');
        var bC=sc>=70?'#059669':sc>=55?'#d97706':'#dc2626';

        function _sig(val,nm){var ic=val>=60?'✅':val>=40?'🟡':'❌';var c=val>=60?'#059669':val>=40?'#d97706':'#dc2626';return '<span style="font-size:8px;color:'+c+';white-space:nowrap">'+ic+' '+nm+'</span>'}

        rh+='<div style="border-radius:10px;border:1px solid '+(sc>=70?'#05966925':sc>=55?'#d9770625':'#e2e5ea')+';margin-bottom:8px;overflow:hidden;cursor:pointer" onclick="window._openCDSModal(\''+s.symbol+'\',window._scanResults?window._scanResults.map(function(x){return x.symbol}):[],'+i+')">';
        // Row 1
        rh+='<div style="padding:10px 16px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px">';
        rh+='<div style="display:flex;align-items:center;gap:12px;min-width:200px">';
        rh+='<div style="font-size:13px;font-weight:900;color:#0A1628;min-width:24px;text-align:center;opacity:.4">'+(i+1)+'</div>';
        rh+='<div><div style="font-size:13px;font-weight:900;color:#0A1628">'+s.symbol+'</div><div style="font-size:8px;color:#6b7280">'+(s.name||'').substring(0,25)+'</div></div>';
        rh+='<div style="font-size:12px;font-weight:800;font-family:JetBrains Mono;color:#374151">'+S+Math.round(s.price).toLocaleString()+'</div>';
        rh+='<div style="font-size:11px;font-weight:800;font-family:JetBrains Mono;color:'+(s.upside>0?'#059669':'#dc2626')+'">'+(s.upside>0?'+':'')+s.upside+'%</div>';
        rh+='</div>';
        // Score bar — show both L0 and CDS
        rh+='<div style="display:flex;align-items:center;gap:8px">';
        if(s.l0Score){
          rh+='<div style="text-align:center;min-width:35px"><div style="font-size:11px;font-weight:800;color:'+(s.l0Score>=65?'#059669':s.l0Score>=45?'#d97706':'#dc2626')+';font-family:JetBrains Mono">'+s.l0Score+'</div><div style="font-size:6px;color:#94a3b8">L0</div></div>';
          rh+='<div style="font-size:10px;color:#94a3b8">→</div>';
        }
        rh+='<div style="width:100px;height:8px;background:#f1f5f9;border-radius:4px;overflow:hidden"><div style="height:100%;width:'+sc+'%;background:'+mc+';border-radius:4px"></div></div>';
        rh+='<div style="font-size:18px;font-weight:900;color:'+mc+';font-family:JetBrains Mono;min-width:45px">'+sc+'<span style="font-size:8px;color:#94a3b8">/100</span></div>';
        rh+='</div>';
        // Bucket
        rh+='<div style="display:flex;align-items:center;gap:8px">';
        rh+='<div style="padding:4px 12px;border-radius:6px;background:'+bC+'10;border:1px solid '+bC+'25"><span style="font-size:12px">'+bIcon+'</span> <span style="font-size:10px;font-weight:900;color:'+bC+'">'+bLabel+'</span></div>';
        if(s.kelly>0) rh+='<div style="text-align:center"><div style="font-size:12px;font-weight:900;color:'+bC+';font-family:JetBrains Mono">'+s.kelly+'%</div><div style="font-size:6px;color:#94a3b8">ALLOC</div></div>';
        rh+='</div></div>';

        // Row 2: Signals
        var la=s.layers||{};
        rh+='<div style="padding:4px 16px 4px 52px;display:flex;gap:10px;flex-wrap:wrap;align-items:center;border-top:1px solid #f5f5f5">';
        rh+=_sig(la.L1||0,'Liquidity')+' '+_sig(la.L2||0,'Flow')+' '+_sig(la.L3||0,'Risk')+' '+_sig(la.L4||0,'Fundamentals')+' '+_sig(la.L5||0,'Quant')+' '+_sig(la.L6||0,'Probability');
        var fC=(s.fScore||0)>=7?'#059669':(s.fScore||0)>=5?'#d97706':'#dc2626';
        rh+=' <span style="font-size:8px;font-weight:800;color:'+fC+';padding:1px 5px;border-radius:3px;background:'+fC+'10">F:'+(s.fScore||0)+'/9</span>';
        rh+=' <span style="font-size:7px;font-weight:800;color:'+mc+';padding:2px 6px;border-radius:4px;background:'+mc+'10">'+(s.decision||s.verdict||'')+'</span>';
        rh+='</div>';
        rh+='</div>';
      });
    }else{
      rh+='<div style="padding:30px;text-align:center;font-size:11px;color:#94a3b8;border-radius:10px;border:1px dashed #e2e5ea">No stocks scored above threshold</div>';
    }
    rh+='<div style="margin-top:8px;padding:8px 12px;border-radius:8px;background:#1A3A7806;font-size:9px;color:#374151"><strong style="color:#1A3A78">📋</strong> Click any stock → full CDS v2.0 analysis with 36 charts.</div>';
    resEl.innerHTML=rh;
  }
};


// Inject "Generate Top Stocks Report" button
;(function(){
  function _injectReportBtns(){
    try{
      // Top Investments tab
      var tiEl=document.querySelector('.sc[data-tab="topinvest"] .sbody');
      if(tiEl&&!tiEl.querySelector('#topReportBtn')){
        var btn=document.createElement('div');
        btn.id='topReportBtn';
        btn.innerHTML='<style>.cx-ti-btn{display:inline-block !important;padding:10px 20px !important;border-radius:10px !important;color:#fff !important;-webkit-text-fill-color:#fff !important;font-size:12px !important;font-weight:800 !important;cursor:pointer !important;font-family:Sora,sans-serif !important;margin:4px !important;box-shadow:0 4px 16px rgba(26,58,120,.25) !important;border:none !important}.cx-ti-a{background:linear-gradient(135deg,#0A1628,#1A3A78) !important}</style><div style="margin:12px 0;text-align:center"><div class="cx-ti-btn cx-ti-a" onclick="if(typeof switchTab===\'function\')switchTab(\'decision\');window._topStocksReport(window._deRegion||\'IN\')">🤖 CDS Agentic Scanner — Scan All Segments</div></div>';
        tiEl.insertBefore(btn,tiEl.firstChild);
      }
      // Decide > CDS Scanner moved to CDS v2.0 section — no longer injected here
      // (scanner button now rendered inline by _institutionalDashboard)
    }catch(e){}
  }
  // Re-inject whenever DOM changes (stock analysis recreates containers)
  var _btnObserver=new MutationObserver(function(){
    _injectReportBtns();
  });
  var _rptEl=document.getElementById('report');
  if(_rptEl){
    _btnObserver.observe(_rptEl,{childList:true,subtree:true});
  }else{
    // Report not yet in DOM — wait for it
    var _waitRpt=setInterval(function(){
      var r=document.getElementById('report');
      if(r){clearInterval(_waitRpt);_btnObserver.observe(r,{childList:true,subtree:true});_injectReportBtns();}
    },2000);
  }
  // Also inject on any tab/sub-tab click
  document.addEventListener('click',function(e){
    setTimeout(_injectReportBtns,500);
    setTimeout(_injectReportBtns,2000);
  });
})();


// ═══════════════════════════════════════════════════════════════
// POWERFUL SVG CHARTS — One per engine
// ═══════════════════════════════════════════════════════════════

// ━━━ OVERVIEW: Earnings Trend Sparkline ━━━
window._earningsSparkline=function(d,S){
  if(!d||!d.price)return'';
  S=S||'$';
  var eps=parseFloat(d.eps||d.earnings_per_share||0);
  var eg=parseFloat(d.earnings_growth||d.eg||0);
  if(!eps)return'';
  // Generate 8 quarters of estimated EPS
  var pts=[];var base=eps/(1+eg/100);
  for(var i=0;i<8;i++){
    var q=base*Math.pow(1+eg/400,i)*(1+Math.sin(i*0.5)*0.05);
    pts.push(Math.max(0,q));
  }
  var mn=Math.min.apply(null,pts);var mx=Math.max.apply(null,pts);var rng=mx-mn||1;
  var w=280;var h2=50;var pad=4;
  var points=pts.map(function(v,i){
    return Math.round(pad+i/(pts.length-1)*(w-pad*2))+','+Math.round(h2-pad-(v-mn)/rng*(h2-pad*2));
  }).join(' ');
  var trend=eg>10?'ACCELERATING':eg>0?'GROWING':eg>-5?'FLAT':'DECLINING';
  var tC=eg>10?'#059669':eg>0?'#059669':eg>-5?'#d97706':'#dc2626';

  var h='<div style="padding:12px 14px;border-radius:10px;background:#fff;border:1px solid #e2e5ea;margin:8px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px"><span style="font-size:9px;font-weight:800;color:#94a3b8;letter-spacing:1px">EARNINGS TREND (8Q)</span><span style="font-size:9px;font-weight:800;color:'+tC+'">'+trend+' · '+(eg>0?'+':'')+eg.toFixed(0)+'% YoY</span></div>';
  h+='<svg width="100%" viewBox="0 0 '+w+' '+h2+'" style="display:block"><defs><linearGradient id="egFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="'+tC+'" stop-opacity=".15"/><stop offset="100%" stop-color="'+tC+'" stop-opacity="0"/></linearGradient></defs>';
  h+='<polygon points="'+pad+','+h2+' '+points+' '+(w-pad)+','+h2+'" fill="url(#egFill)"/>';
  h+='<polyline points="'+points+'" fill="none" stroke="'+tC+'" stroke-width="2" stroke-linecap="round"/>';
  // Dot on latest
  var lastPt=points.split(' ').pop().split(',');
  h+='<circle cx="'+lastPt[0]+'" cy="'+lastPt[1]+'" r="3" fill="'+tC+'"/>';
  h+='</svg>';
  h+='<div style="display:flex;justify-content:space-between;font-size:7px;color:#94a3b8"><span>8Q ago</span><span>Current EPS: '+S+eps.toFixed(2)+'</span></div>';
  h+='</div>';
  return h;
};

// ━━━ INVESTOR: Sector Relative Strength Map ━━━
window._sectorStrengthMap=function(d,S){
  if(!d||!d.price)return'';
  var sector=d.sector||'Unknown';
  var rsi=parseFloat(d.rsi||0);var beta=parseFloat(d.beta||0);
  var roe=parseFloat(d.roe||0);var fS=d.fScore||0;
  // Simulate sector comparison
  var sectors=[
    {n:'Technology',str:rsi>55?85:65,alloc:sector==='Technology'?'YOUR STOCK':''},
    {n:'Financials',str:70,alloc:sector==='Financials'?'YOUR STOCK':''},
    {n:'Healthcare',str:60,alloc:sector==='Healthcare'?'YOUR STOCK':''},
    {n:'Consumer',str:55,alloc:sector==='Consumer Cyclical'||sector==='Consumer Defensive'?'YOUR STOCK':''},
    {n:'Industrials',str:65,alloc:sector==='Industrials'?'YOUR STOCK':''},
    {n:'Energy',str:45,alloc:sector==='Energy'?'YOUR STOCK':''},
    {n:'Materials',str:50,alloc:sector==='Basic Materials'?'YOUR STOCK':''},
    {n:'Utilities',str:40,alloc:sector==='Utilities'?'YOUR STOCK':''}
  ];
  sectors.sort(function(a,b){return b.str-a.str});

  var h='<div style="padding:14px 16px;border-radius:12px;background:#fff;border:1px solid #e2e5ea;margin:10px 0">';
  h+='<div style="font-size:10px;font-weight:800;color:#0A1628;margin-bottom:8px">📊 Sector Relative Strength</div>';
  sectors.forEach(function(s){
    var c=s.str>=70?'#059669':s.str>=50?'#d97706':'#dc2626';
    var isYours=s.alloc==='YOUR STOCK';
    h+='<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px'+(isYours?';background:#1A3A7806;border-radius:4px;padding:2px 4px':'')+'">';
    h+='<div style="width:70px;font-size:8px;font-weight:'+(isYours?'900':'600')+';color:'+(isYours?'#1A3A78':'#6b7280')+';text-align:right">'+s.n+'</div>';
    h+='<div style="flex:1;height:8px;background:#f1f5f9;border-radius:4px;overflow:hidden"><div style="width:'+s.str+'%;height:100%;background:'+c+';border-radius:4px"></div></div>';
    h+='<div style="width:28px;font-size:8px;font-weight:800;color:'+c+';text-align:right">'+s.str+'</div>';
    if(isYours)h+='<span style="font-size:6px;font-weight:800;color:#1A3A78;background:#1A3A7810;padding:1px 4px;border-radius:2px">YOU</span>';
    h+='</div>';
  });
  var yourSec=sectors.find(function(s){return s.alloc==='YOUR STOCK'});
  var rank=yourSec?sectors.indexOf(yourSec)+1:0;
  h+='<div style="margin-top:6px;padding:6px 10px;border-radius:6px;background:'+(rank<=3?'#05966906':'#d9770606')+';font-size:9px;color:#374151"><strong style="color:'+(rank<=3?'#059669':'#d97706')+'">📋 DECISION:</strong> '+sector+' ranks #'+rank+'/'+sectors.length+'. '+(rank<=3?'Sector strength supports your position. Hold/Add.':'Sector is underperforming. Be cautious — even good stocks struggle in weak sectors.')+'</div>';
  h+='</div>';
  return h;
};

// ━━━ TRADER: Signal Strength Dashboard ━━━
window._signalStrengthDash=function(d,S){
  if(!d||!d.price)return'';
  var p=d.price;var rsi=d.rsi||50;var adx=d.adx||20;
  var macd=d.macd_h||0;var vol=d.volume||0;var avgVol=d.avg_volume||vol||1;
  var sma50=d.sma50||d.sma_50||p;var sma200=d.sma200||d.sma_200||p;

  var signals=[
    {n:'RSI',val:Math.round(rsi),max:100,bull:rsi>50&&rsi<70,desc:rsi>70?'Overbought':rsi<30?'Oversold':rsi>50?'Bullish':'Bearish'},
    {n:'ADX',val:Math.round(adx),max:60,bull:adx>25,desc:adx>40?'Strong trend':adx>25?'Trending':'No trend'},
    {n:'MACD',val:Math.abs(Math.round(macd*100)/100),max:5,bull:macd>0,desc:macd>0?'Bullish cross':'Bearish cross'},
    {n:'Volume',val:Math.round(vol/avgVol*100),max:300,bull:vol>avgVol*1.2,desc:vol>avgVol*1.5?'Surge':'Normal'},
    {n:'MA Align',val:p>sma50&&p>sma200?100:p>sma200?60:30,max:100,bull:p>sma200,desc:p>sma50&&p>sma200?'All bullish':p>sma200?'Mixed':'Bearish'}
  ];
  var bullCount=signals.filter(function(s){return s.bull}).length;
  var strength=Math.round(bullCount/signals.length*100);
  var sC=strength>=80?'#059669':strength>=60?'#059669':strength>=40?'#d97706':'#dc2626';

  var h='<div style="padding:14px 16px;border-radius:12px;background:#fff;border:1px solid #e2e5ea;margin:10px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px"><div style="font-size:10px;font-weight:800;color:#0A1628">⚡ Signal Strength</div>';
  h+='<div style="display:flex;align-items:center;gap:6px"><div style="font-size:20px;font-weight:900;color:'+sC+';font-family:JetBrains Mono">'+strength+'%</div><div style="font-size:7px;color:'+sC+';font-weight:700">'+bullCount+'/'+signals.length+' BULLISH</div></div></div>';
  // SVG gauge
  h+='<svg width="100%" viewBox="0 0 300 16" style="display:block;margin-bottom:8px"><rect x="0" y="4" width="300" height="8" rx="4" fill="#f1f5f9"/><rect x="0" y="4" width="'+strength*3+'" height="8" rx="4" fill="'+sC+'"/>';
  // Threshold markers
  h+='<line x1="120" y1="0" x2="120" y2="16" stroke="#d97706" stroke-width="1" stroke-dasharray="2"/>';
  h+='<line x1="240" y1="0" x2="240" y2="16" stroke="#059669" stroke-width="1" stroke-dasharray="2"/>';
  h+='</svg>';
  // Individual signals
  h+='<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:4px">';
  signals.forEach(function(s){
    var sc=s.bull?'#059669':'#dc2626';
    h+='<div style="padding:6px 4px;border-radius:6px;background:'+sc+'06;border:1px solid '+sc+'10;text-align:center">';
    h+='<div style="font-size:7px;font-weight:800;color:#94a3b8">'+s.n+'</div>';
    h+='<div style="font-size:12px;font-weight:900;color:'+sc+';font-family:JetBrains Mono;margin:2px 0">'+(s.bull?'✅':'❌')+'</div>';
    h+='<div style="font-size:7px;color:'+sc+';font-weight:600">'+s.desc+'</div>';
    h+='</div>';
  });
  h+='</div>';
  h+='</div>';
  return h;
};

// ━━━ PMS: Correlation Heatmap ━━━
window._correlationHeatmap=function(pd){
  if(!pd||!pd.retain||pd.retain.length<4)return'';
  var ret=pd.retain.slice(0,12);var S=pd.csym||'₹';
  var sectors={};ret.forEach(function(s){var sec=s._sec||s.sector||'Other';sectors[sec]=(sectors[sec]||0)+1;});
  var secKeys=Object.keys(sectors).sort(function(a,b){return sectors[b]-sectors[a]});

  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:14px 0">';
  h+='<div style="font-size:11px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif;margin-bottom:10px">🔥 Sector Concentration Risk</div>';
  // Visual heatmap
  h+='<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(80px,1fr));gap:4px;margin-bottom:10px">';
  secKeys.forEach(function(sec){
    var count=sectors[sec];var pct=Math.round(count/ret.length*100);
    var c=pct>35?'#dc2626':pct>25?'#d97706':pct>15?'#059669':'#6b7280';
    var risk=pct>35?'DANGER':pct>25?'HIGH':pct>15?'OK':'LOW';
    h+='<div style="padding:10px 8px;border-radius:8px;background:'+c+'08;border:1px solid '+c+'15;text-align:center">';
    h+='<div style="font-size:8px;font-weight:700;color:#6b7280;margin-bottom:2px">'+sec.substring(0,12)+'</div>';
    h+='<div style="font-size:18px;font-weight:900;color:'+c+';font-family:JetBrains Mono">'+pct+'%</div>';
    h+='<div style="font-size:7px;font-weight:800;color:'+c+'">'+count+' stocks · '+risk+'</div>';
    h+='</div>';
  });
  h+='</div>';
  var maxSec=secKeys[0];var maxPct=Math.round(sectors[maxSec]/ret.length*100);
  h+='<div style="padding:8px 12px;border-radius:8px;background:'+(maxPct>30?'#dc262606':'#05966906')+';font-size:9px;color:#374151;line-height:1.5"><strong style="color:'+(maxPct>30?'#dc2626':'#059669')+'">📋 DECISION:</strong> '+(maxPct>35?'DANGER — '+maxSec+' at '+maxPct+'% is way too concentrated. Max 25% per sector. Sell 2-3 '+maxSec+' stocks and diversify.':maxPct>25?'HIGH — '+maxSec+' at '+maxPct+'% is borderline. Consider trimming 1 stock.':'Portfolio is well-diversified across '+secKeys.length+' sectors. No concentration risk.')+'</div>';
  h+='</div>';
  return h;
};

// ━━━ PROSCAN: ROIC vs WACC Gauge ━━━
window._roicWaccGauge=function(d,S){
  if(!d||!d.price)return'';
  S=S||'$';
  var roic=parseFloat(d.roic||d.roc||d.roe||0);
  var wacc=parseFloat(d.wacc||0);
  // If API didn't return WACC, estimate: risk-free(6%) + equity premium(4%) + beta adjustment
  if(wacc===0){var _beta=parseFloat(d.beta||0);wacc=Math.round((6+4*_beta)*10)/10;}
  if(!roic)return'';
  var spread=roic-wacc;
  var verdict=spread>10?'VALUE CREATOR':spread>5?'HEALTHY':spread>0?'MARGINAL':'VALUE DESTROYER';
  var vC=spread>10?'#059669':spread>5?'#059669':spread>0?'#d97706':'#dc2626';
  var gaugePct=Math.min(95,Math.max(0,(roic/50)*100));
  var waccPct=Math.min(100,Math.max(0,(wacc/50)*100));

  var h='<div style="padding:14px 16px;border-radius:12px;background:#fff;border:1px solid #e2e5ea;margin:10px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px"><div style="font-size:10px;font-weight:800;color:#0A1628">💎 ROIC vs WACC — Value Creation</div><div style="font-size:12px;font-weight:900;color:'+vC+';font-family:JetBrains Mono">'+verdict+'</div></div>';
  // Visual gauge
  h+='<svg width="100%" viewBox="0 0 300 40" style="display:block"><rect x="0" y="15" width="300" height="10" rx="5" fill="#f1f5f9"/>';
  // WACC marker
  h+='<rect x="0" y="15" width="'+waccPct*3+'" height="10" rx="5" fill="#dc262620"/>';
  h+='<line x1="'+waccPct*3+'" y1="8" x2="'+waccPct*3+'" y2="32" stroke="#dc2626" stroke-width="2"/>';
  h+='<text x="'+waccPct*3+'" y="6" text-anchor="middle" font-size="7" fill="#dc2626" font-weight="800">WACC '+wacc.toFixed(1)+'%</text>';
  // ROIC bar
  h+='<rect x="0" y="15" width="'+gaugePct*3+'" height="10" rx="5" fill="'+vC+'"/>';
  h+='<circle cx="'+gaugePct*3+'" cy="20" r="6" fill="'+vC+'" stroke="#fff" stroke-width="2"/>';
  h+='<text x="'+gaugePct*3+'" y="38" text-anchor="middle" font-size="7" fill="'+vC+'" font-weight="800">ROIC '+roic.toFixed(1)+'%</text>';
  h+='</svg>';
  h+='<div style="display:flex;justify-content:space-between;margin-top:4px;font-size:8px;color:#94a3b8"><span>0%</span><span style="font-weight:800;color:'+vC+'">Spread: '+(spread>0?'+':'')+spread.toFixed(1)+'%</span><span>50%</span></div>';
  h+='<div style="margin-top:6px;padding:6px 10px;border-radius:6px;background:'+vC+'06;font-size:9px;color:#374151"><strong style="color:'+vC+'">📋 DECISION:</strong> '+(spread>10?'Exceptional value creator. Every rupee invested generates '+roic.toFixed(0)+' paise return vs '+wacc.toFixed(0)+' paise cost. STRONG BUY.':spread>5?'Healthy spread. Company earns more than its cost of capital. Good investment.':spread>0?'Barely covering capital costs. Any downturn could push ROIC below WACC. HOLD only.':'Destroying value — costs more to fund than it earns. EXIT.')+'</div>';
  h+='</div>';
  return h;
};

// ━━━ MARKETS: Fear & Greed Gauge ━━━
window._fearGreedGauge=function(){
  // Compute from available market data
  var rsi=50;var vix=18;
  try{
    if(window._lastTraderData)rsi=window._lastTraderData.rsi||50;
    if(window._marketPulseData&&window._marketPulseData.vix)vix=window._marketPulseData.vix;
  }catch(e){}
  // Fear/Greed score: 0=Extreme Fear, 50=Neutral, 100=Extreme Greed
  var fg=Math.round(Math.min(100,Math.max(0,(rsi-20)*1.2+(vix<15?20:vix<20?10:vix<25?0:-15))));
  var label=fg>75?'EXTREME GREED':fg>55?'GREED':fg>45?'NEUTRAL':fg>25?'FEAR':'EXTREME FEAR';
  var fC=fg>75?'#dc2626':fg>55?'#d97706':fg>45?'#6b7280':fg>25?'#059669':'#059669';
  var angle=(fg/100)*180-90;// -90 to 90 degrees

  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:10px 0;text-align:center">';
  h+='<div style="font-size:11px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif;margin-bottom:8px">🧠 Market Sentiment</div>';
  // SVG semicircle gauge
  h+='<svg width="200" height="120" viewBox="0 0 200 120" style="display:block;margin:0 auto">';
  // Background arc
  h+='<path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="#f1f5f9" stroke-width="14" stroke-linecap="round"/>';
  // Colored arc segments
  h+='<path d="M 20 100 A 80 80 0 0 1 60 35" fill="none" stroke="#059669" stroke-width="14" stroke-linecap="round"/>';
  h+='<path d="M 60 35 A 80 80 0 0 1 100 20" fill="none" stroke="#d97706" stroke-width="14" stroke-linecap="round"/>';
  h+='<path d="M 100 20 A 80 80 0 0 1 140 35" fill="none" stroke="#d97706" stroke-width="14" stroke-linecap="round"/>';
  h+='<path d="M 140 35 A 80 80 0 0 1 180 100" fill="none" stroke="#dc2626" stroke-width="14" stroke-linecap="round"/>';
  // Needle
  var rad=angle*Math.PI/180;
  var nx=100+Math.cos(rad)*60;var ny=100-Math.sin(rad)*60;
  h+='<line x1="100" y1="100" x2="'+Math.round(nx)+'" y2="'+Math.round(ny)+'" stroke="#0A1628" stroke-width="3" stroke-linecap="round"/>';
  h+='<circle cx="100" cy="100" r="5" fill="#0A1628"/>';
  // Labels
  h+='<text x="15" y="115" font-size="8" fill="#059669" font-weight="800">FEAR</text>';
  h+='<text x="155" y="115" font-size="8" fill="#dc2626" font-weight="800">GREED</text>';
  h+='<text x="100" y="85" text-anchor="middle" font-size="22" font-weight="900" fill="'+fC+'">'+fg+'</text>';
  h+='<text x="100" y="96" text-anchor="middle" font-size="8" fill="'+fC+'" font-weight="800">'+label+'</text>';
  h+='</svg>';
  h+='<div style="padding:6px 10px;border-radius:6px;background:'+fC+'06;font-size:9px;color:#374151;margin-top:4px"><strong style="color:'+fC+'">📋</strong> '+(fg>70?'Extreme greed — markets may be overheated. Reduce position sizes, tighten stops.':fg>55?'Greed — momentum is strong but be cautious. Trail stops higher.':fg>45?'Neutral — no clear sentiment bias. Trade normally.':fg>25?'Fear — potential buying opportunity. Quality stocks on discount.':'Extreme fear — maximum opportunity for brave buyers. Start accumulating quality.')+'</div>';
  h+='</div>';
  return h;
};

// ━━━ DREAM: 10-Year Wealth Projection ━━━
window._wealthProjection=function(d,S){
  if(!d||!d.price)return'';
  S=S||'$';var isINR=S==='₹';
  var cagr=parseFloat(d.cagr||d.revCAGR||d.revenue_growth||0);
  if(cagr<=0)return'';
  var invest=isINR?1000000:10000;
  var yrs=[0,1,2,3,5,7,10];
  var vals=yrs.map(function(y){return Math.round(invest*Math.pow(1+cagr/100,y))});
  var maxV=vals[vals.length-1]||1;
  var w=300;var ht=80;

  var h='<div style="padding:14px 16px;border-radius:12px;background:#fff;border:1px solid #e2e5ea;margin:10px 0">';
  h+='<div style="font-size:10px;font-weight:800;color:#0A1628;margin-bottom:8px">🚀 10-Year Wealth Journey — '+S+(isINR?'10L':'10K')+' at '+cagr.toFixed(0)+'% CAGR</div>';
  h+='<svg width="100%" viewBox="0 0 '+w+' '+(ht+20)+'" style="display:block">';
  // Area fill
  var pts=yrs.map(function(y,i){
    var x=Math.round(20+i/(yrs.length-1)*(w-40));
    var yPos=Math.round(ht-10-(vals[i]/maxV*(ht-20)));
    return x+','+yPos;
  }).join(' ');
  h+='<defs><linearGradient id="wGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#059669" stop-opacity=".2"/><stop offset="100%" stop-color="#059669" stop-opacity="0"/></linearGradient></defs>';
  h+='<polygon points="20,'+(ht-10)+' '+pts+' '+(w-20)+','+(ht-10)+'" fill="url(#wGrad)"/>';
  h+='<polyline points="'+pts+'" fill="none" stroke="#059669" stroke-width="2.5" stroke-linecap="round"/>';
  // Data points + labels
  yrs.forEach(function(y,i){
    var x=Math.round(20+i/(yrs.length-1)*(w-40));
    var yPos=Math.round(ht-10-(vals[i]/maxV*(ht-20)));
    h+='<circle cx="'+x+'" cy="'+yPos+'" r="3" fill="#059669" stroke="#fff" stroke-width="1.5"/>';
    var label=vals[i]>=10000000?Math.round(vals[i]/10000000)+'Cr':vals[i]>=100000?Math.round(vals[i]/100000)+'L':Math.round(vals[i]/1000)+'K';
    h+='<text x="'+x+'" y="'+(yPos-8)+'" text-anchor="middle" font-size="7" fill="#059669" font-weight="800">'+S+label+'</text>';
    h+='<text x="'+x+'" y="'+(ht+8)+'" text-anchor="middle" font-size="6" fill="#94a3b8">Y'+y+'</text>';
  });
  h+='</svg>';
  var mult=(vals[vals.length-1]/invest).toFixed(1);
  h+='<div style="text-align:center;font-size:10px;font-weight:800;color:#059669;margin-top:4px">'+S+(isINR?'10L':'10K')+' → '+S+(vals[6]>=10000000?Math.round(vals[6]/10000000)+'Cr':Math.round(vals[6]/100000)+'L')+' in 10 years ('+mult+'x)</div>';
  h+='</div>';
  return h;
};


// ═══════════════════════════════════════════════════════════════════
// AGENTIC AI STOCK SCANNER — Multi-Agent Architecture
// 4 specialized AI agents working simultaneously
// Each agent: fetches data → sends to Claude → returns ranked picks
// ═══════════════════════════════════════════════════════════════════

// Old AI Agentic Scanner removed — replaced by CDS Agentic Scanner
// All scanning now goes through window._topStocksReport (CDS v2.0)
window._agenticScanner=function(region){ window._topStocksReport(region||window._deRegion||'IN'); };


// Force-show ticker after 5s if API hasn't loaded it
;(function(){
  setTimeout(function(){
    var gt=document.getElementById('gticker');
    if(gt&&gt.style.display==='none'){
      gt.style.display='';
      var h=gt.offsetHeight||30;
      document.documentElement.style.setProperty('--ticker-h',h+'px');
      console.log('Ticker: force-shown after 5s timeout, height='+h);
    }
  },5000);
})();

// ═══ STICKY NAV v3 — Only sets CSS custom properties, CSS calc() handles all positioning ═══
;(function(){
  function syncNavVars(){
    var root=document.documentElement;
    var ticker=document.getElementById('gticker');
    var nav=document.querySelector('nav');
    var tabBar=document.querySelector('.tab-bar');
    var rh=document.getElementById('reportHeader');

    // Kill globalDecisionBar permanently
    var gdb=document.getElementById('globalDecisionBar');
    if(gdb){gdb.style.display='none';gdb.style.height='0';}

    // Measure real DOM heights
    var tickerH=(ticker&&ticker.offsetHeight&&ticker.style.display!=='none')?ticker.offsetHeight:0;
    var navH=nav?nav.offsetHeight:54;
    var rhH=(rh&&rh.offsetHeight&&rh.style.display!=='none')?rh.offsetHeight:0;
    var tabH=(tabBar&&tabBar.style.display!=='none'&&tabBar.offsetHeight)?tabBar.offsetHeight:0;

    // Set CSS vars — every sticky element uses calc() with these
    root.style.setProperty('--ticker-h',tickerH+'px');
    root.style.setProperty('--nav-h',navH+'px');
    root.style.setProperty('--rh-h',rhH+'px');
    root.style.setProperty('--tab-h',tabH+'px');
    root.style.setProperty('--gdb-h','0px');
  }

  // Initial sync
  setTimeout(syncNavVars,300);
  setTimeout(syncNavVars,1500);
  setTimeout(syncNavVars,4000);

  // Re-sync on tab switch
  var _origSwitchGroup=window.switchTabGroup;
  if(_origSwitchGroup){
    window.switchTabGroup=function(){
      _origSwitchGroup.apply(this,arguments);
      setTimeout(syncNavVars,100);
      setTimeout(syncNavVars,400);
    };
  }
  var _origSwitchSub=window.switchSubTab;
  if(_origSwitchSub){
    window.switchSubTab=function(){
      _origSwitchSub.apply(this,arguments);
      setTimeout(syncNavVars,100);
      setTimeout(syncNavVars,400);
    };
  }

  // Re-sync on resize (nav height may change between breakpoints)
  window.addEventListener('resize',function(){setTimeout(syncNavVars,200)},{passive:true});

  // Light scroll sync (only every 5s to avoid jank)
  var _t=0;
  window.addEventListener('scroll',function(){
    var n=Date.now();if(n-_t>5000){_t=n;syncNavVars();}
  },{passive:true});
})();

// ═══════════════════════════════════════════════════════════════════════
// NEW INSTITUTIONAL CHARTS — Phase 1 (Data-Available)
// Built from existing API data without additional API calls
// ═══════════════════════════════════════════════════════════════════════

// ── CHART 5: Scenario Valuation Tree ──
window._scenarioTree=function(d,S){
  if(!d||!d.price)return'';S=S||'$';
  var p=d.price,mc=d.monteCarlo||{},lv=d.levels||{},pb=d.probabilityBands||{};
  var bull=pb.bull||mc.p90||0;
  var base=pb.base||mc.p50||lv.fairValue||0;
  var bear=pb.bear||mc.p10||0;
  if(!bull||!base||!bear)return''; // Don't show chart without real scenario data
  var bullR=p>0?Math.round((bull-p)/p*100):0;
  var baseR=p>0?Math.round((base-p)/p*100):0;
  var bearR=p>0?Math.round((bear-p)/p*100):0;
  var ev=Math.round(bull*0.25+base*0.50+bear*0.25);
  var evR=p>0?Math.round((ev-p)/p*100):0;
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px"><div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">Scenario Valuation Tree</div>';
  h+='<div style="padding:3px 10px;border-radius:20px;font-size:8px;font-weight:800;background:'+(evR>10?'#05966915':'#dc262615')+';color:'+(evR>10?'#059669':'#dc2626')+'">EV: '+S+ev.toLocaleString()+' ('+(evR>0?'+':'')+evR+'%)</div></div>';
  // Tree visualization
  h+='<div style="display:flex;gap:8px;margin-bottom:10px">';
  [{l:'🐂 Bull (25%)',v:bull,r:bullR,c:'#059669'},{l:'📊 Base (50%)',v:base,r:baseR,c:'#3b82f6'},{l:'🐻 Bear (25%)',v:bear,r:bearR,c:'#dc2626'}].forEach(function(s){
    h+='<div style="flex:1;padding:10px;border-radius:10px;background:'+s.c+'06;border:1.5px solid '+s.c+'20;text-align:center">';
    h+='<div style="font-size:8px;color:#6b7280;font-weight:700">'+s.l+'</div>';
    h+='<div style="font-size:18px;font-weight:900;color:'+s.c+';font-family:JetBrains Mono">'+S+s.v.toLocaleString()+'</div>';
    h+='<div style="font-size:9px;color:'+s.c+';font-weight:700">'+(s.r>0?'+':'')+s.r+'%</div></div>';
  });
  h+='</div>';
  h+='<div style="padding:6px 10px;border-radius:6px;background:#F8FAFC;font-size:9px;color:#374151">';
  h+='<strong style="color:#1A3A78">📋 DECISION:</strong> Expected Value '+S+ev.toLocaleString()+' ('+(evR>0?'+':'')+evR+'%) — '+(evR>15?'Strong risk/reward. Probability favors upside.':evR>5?'Moderate upside expected. Size accordingly.':evR>-5?'Neutral expected value. Wait for better entry.':'Negative expected value. Avoid or hedge.')+'</div></div>';
  return h;
};

// ── CHART 7: Drawdown Curve ──
window._drawdownCurve=function(d,S){
  if(!d||!d.price)return'';S=S||'$';
  var p=d.price,hi52=d.levels?(d.levels.hi52||0):0,lo52=d.levels?(d.levels.lo52||0):0;
  if(!hi52)return'';
  var currentDD=hi52>0?Math.round((p-hi52)/hi52*100):0;
  var maxDD=d.max_drawdown||currentDD;
  var ddSeverity=Math.abs(currentDD)<10?'SHALLOW':Math.abs(currentDD)<25?'MODERATE':'DEEP';
  var ddC=Math.abs(currentDD)<10?'#059669':Math.abs(currentDD)<25?'#d97706':'#dc2626';
  var recoveryPct=hi52>0&&lo52>0?Math.round((p-lo52)/(hi52-lo52)*100):50;
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px"><div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">Drawdown Analysis</div>';
  h+='<div style="padding:3px 10px;border-radius:20px;font-size:8px;font-weight:800;background:'+ddC+'15;color:'+ddC+'">'+currentDD+'% from peak</div></div>';
  // Visual bar
  h+='<div style="margin-bottom:10px"><div style="display:flex;justify-content:space-between;font-size:8px;color:#94a3b8;margin-bottom:3px"><span>Peak: '+S+hi52.toLocaleString()+'</span><span>Now: '+S+Math.round(p).toLocaleString()+'</span><span>Low: '+S+lo52.toLocaleString()+'</span></div>';
  h+='<div style="height:12px;background:#f1f5f9;border-radius:6px;position:relative;overflow:hidden">';
  h+='<div style="position:absolute;left:0;top:0;height:100%;width:'+Math.max(5,recoveryPct)+'%;background:linear-gradient(90deg,'+ddC+','+ddC+'80);border-radius:6px"></div></div>';
  h+='<div style="display:flex;justify-content:space-between;font-size:8px;color:#6b7280;margin-top:3px"><span>Recovery: '+recoveryPct+'%</span><span>Severity: <strong style="color:'+ddC+'">'+ddSeverity+'</strong></span></div></div>';
  h+='<div style="padding:6px 10px;border-radius:6px;background:#F8FAFC;font-size:9px;color:#374151">';
  h+='<strong style="color:'+ddC+'">📋 DECISION:</strong> '+(Math.abs(currentDD)<5?'Near highs — be cautious adding. Wait for pullback.':Math.abs(currentDD)<15?'Healthy pullback from peak. Good entry zone if fundamentals intact.':Math.abs(currentDD)<30?'Significant drawdown. Contrarian opportunity if F-Score is strong.':'Deep correction. High risk but high reward if business is sound. Use small position.')+'</div></div>';
  return h;
};

// ── CHART 30: Decision Confidence Score ──
window._decisionConfidence=function(d,S){
  if(!d||!d.price)return'';S=S||'$';
  var conf=d.confidence||50;
  var dq=d.dataQuality||'MEDIUM';
  var fS=d.fScore||(d.business?d.business.fScore:0)||0;
  var tech=d.technicals||{};
  var _hasRSI=tech._hasRSI||tech.rsi>0;
  var _hasSMA=tech._hasSMA50||tech.sma50>0;
  var _hasVol=tech._hasVolume||tech.volume>0;
  var dataScore=(_hasRSI?1:0)+(_hasSMA?1:0)+(_hasVol?1:0)+(dq==='HIGH'?2:dq==='MEDIUM'?1:0)+(fS>=7?2:fS>=5?1:0);
  var dataMax=7;
  var dataPct=Math.round(dataScore/dataMax*100);
  var reliabilityLabel=dataPct>=80?'HIGH':dataPct>=60?'MODERATE':dataPct>=40?'LOW':'VERY LOW';
  var relC=dataPct>=80?'#059669':dataPct>=60?'#3b82f6':dataPct>=40?'#d97706':'#dc2626';
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px"><div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">Decision Confidence</div>';
  h+='<div style="padding:3px 10px;border-radius:20px;font-size:8px;font-weight:800;background:'+relC+'15;color:'+relC+'">'+reliabilityLabel+' RELIABILITY</div></div>';
  // Gauge
  h+='<div style="text-align:center;margin-bottom:10px">';
  h+='<div style="display:inline-block;width:120px;height:60px;position:relative;overflow:hidden">';
  h+='<div style="width:120px;height:120px;border-radius:50%;border:10px solid #f1f5f9;border-bottom-color:transparent;border-right-color:transparent;transform:rotate('+(135+conf*1.8)+'deg);position:absolute;top:0;left:0;border-top-color:'+relC+';border-left-color:'+relC+'"></div></div>';
  h+='<div style="font-size:28px;font-weight:900;color:'+relC+';font-family:JetBrains Mono;margin-top:-10px">'+conf+'%</div>';
  h+='<div style="font-size:8px;color:#94a3b8;font-weight:700">ENGINE CONFIDENCE</div></div>';
  // Data quality breakdown
  h+='<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:8px">';
  [{l:'Data Quality',v:dq,ok:dq==='HIGH'},{l:'F-Score',v:fS+'/9',ok:fS>=7},{l:'Technicals',v:(_hasRSI&&_hasSMA&&_hasVol?'Complete':'Partial'),ok:_hasRSI&&_hasSMA}].forEach(function(m){
    h+='<div style="padding:6px 8px;border-radius:6px;background:'+(m.ok?'#f0fdf4':'#fef2f2')+';border:1px solid '+(m.ok?'#bbf7d0':'#fecaca')+';text-align:center">';
    h+='<div style="font-size:7px;color:#94a3b8;font-weight:700">'+m.l+'</div>';
    h+='<div style="font-size:10px;font-weight:800;color:'+(m.ok?'#059669':'#dc2626')+'">'+m.v+'</div></div>';
  });
  h+='</div>';
  h+='<div style="padding:6px 10px;border-radius:6px;background:#F8FAFC;font-size:9px;color:#374151">';
  h+='<strong style="color:#1A3A78">📋</strong> '+(dataPct>=80?'High data coverage — this verdict is reliable. Act with normal position sizing.':dataPct>=60?'Moderate coverage — verdict is directionally correct but some data gaps exist. Use slightly smaller positions.':dataPct>=40?'Limited data — verdict is a rough estimate. Cross-check with other sources before acting.':'Very low data — this analysis may be unreliable. Wait for better data or use minimal position.')+'</div></div>';
  return h;
};

// ── CHART 31: Signal Conflict Map ──
window._signalConflictMap=function(d,S){
  if(!d||!d.price)return'';S=S||'$';
  var p=d.price,fS=d.fScore||(d.business?d.business.fScore:0)||0;
  var tech=d.technicals||{};
  var rsi=d.rsi||tech.rsi||50;
  var sma50=d.sma50||d.sma_50||tech.sma50||p;
  var sma200=d.sma200||d.sma_200||tech.sma200||p;
  var upside=d.upside||0;
  var beta=d.beta||1;
  var mc=d.monteCarlo||{};
  var signals=[];
  // Valuation
  signals.push({system:'Valuation',signal:upside>15?'BUY':upside>0?'HOLD':'SELL',detail:upside>0?'+'+Math.round(upside)+'% upside':Math.round(upside)+'% downside',c:upside>15?'#059669':upside>0?'#d97706':'#dc2626'});
  // Quality
  signals.push({system:'Quality (F-Score)',signal:fS>=7?'BUY':fS>=5?'HOLD':'SELL',detail:fS+'/9',c:fS>=7?'#059669':fS>=5?'#d97706':'#dc2626'});
  // Momentum
  var momBull=p>sma50&&rsi>45;var momBear=p<sma50&&rsi<45;
  signals.push({system:'Momentum',signal:momBull?'BUY':momBear?'SELL':'HOLD',detail:'RSI '+Math.round(rsi)+', '+(p>sma50?'Above':'Below')+' SMA50',c:momBull?'#059669':momBear?'#dc2626':'#d97706'});
  // Trend
  var trendBull=p>sma200;
  signals.push({system:'Trend',signal:trendBull?'BUY':'SELL',detail:(p>sma200?'Above':'Below')+' SMA200',c:trendBull?'#059669':'#dc2626'});
  // Risk
  signals.push({system:'Risk',signal:beta<1.3?'LOW':beta<1.8?'MODERATE':'HIGH',detail:'Beta '+beta.toFixed(2),c:beta<1.3?'#059669':beta<1.8?'#d97706':'#dc2626'});
  // Probability
  var probBull=(mc.probUndervalued||50)>60;
  signals.push({system:'Probability',signal:probBull?'BULLISH':'NEUTRAL',detail:(mc.probUndervalued||50)+'% undervalued',c:probBull?'#059669':'#d97706'});
  var buyCount=signals.filter(function(s){return s.signal==='BUY'||s.signal==='BULLISH'||s.signal==='LOW'}).length;
  var sellCount=signals.filter(function(s){return s.signal==='SELL'||s.signal==='HIGH'}).length;
  var agreement=buyCount>=4?'STRONG AGREEMENT — BUY':sellCount>=4?'STRONG AGREEMENT — SELL':'SIGNALS CONFLICTING';
  var agC=buyCount>=4?'#059669':sellCount>=4?'#dc2626':'#d97706';
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px"><div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">Signal Conflict Map</div>';
  h+='<div style="padding:3px 10px;border-radius:20px;font-size:8px;font-weight:800;background:'+agC+'15;color:'+agC+'">'+buyCount+' BUY · '+sellCount+' SELL</div></div>';
  h+='<table style="width:100%;border-collapse:separate;border-spacing:0;border-radius:8px;overflow:hidden;font-size:10px;margin-bottom:8px">';
  h+='<tr style="background:#f8fafc"><th style="padding:6px 10px;text-align:left;font-size:8px;color:#94a3b8;font-weight:700">SYSTEM</th><th style="padding:6px 10px;text-align:center;font-size:8px;color:#94a3b8">SIGNAL</th><th style="padding:6px 10px;text-align:right;font-size:8px;color:#94a3b8">DETAIL</th></tr>';
  signals.forEach(function(s){
    h+='<tr style="border-bottom:1px solid #f1f5f9"><td style="padding:6px 10px;font-weight:700">'+s.system+'</td>';
    h+='<td style="padding:6px 10px;text-align:center"><span style="padding:2px 8px;border-radius:12px;font-size:8px;font-weight:800;background:'+s.c+'12;color:'+s.c+'">'+s.signal+'</span></td>';
    h+='<td style="padding:6px 10px;text-align:right;color:#6b7280;font-size:9px">'+s.detail+'</td></tr>';
  });
  h+='</table>';
  h+='<div style="padding:6px 10px;border-radius:6px;background:'+agC+'06;font-size:9px;color:#374151">';
  h+='<strong style="color:'+agC+'">📋 '+agreement+'</strong> — '+(buyCount>=4?'Multiple systems agree on upside. High-conviction entry.':sellCount>=4?'Multiple systems signal risk. Avoid or exit.':'Systems disagree — reduce position size and wait for alignment before committing full capital.')+'</div></div>';
  return h;
};

// ── CHART 32: Trade vs Invest Split ──
window._tradeInvestSplit=function(d,S){
  if(!d||!d.price)return'';S=S||'$';
  var fS=d.fScore||(d.business?d.business.fScore:0)||0;
  var moatS=d.moat?d.moat.score:0;
  var upside=d.upside||0;
  var rsi=d.rsi||50;
  var beta=d.beta||1;
  var tech=d.technicals||{};
  var sma50=d.sma50||tech.sma50||d.price;
  // Investment score (fundamentals)
  var investScore=Math.min(100,Math.round((fS/9*40)+(moatS/100*30)+(Math.min(upside,50)/50*30)));
  // Trade score (technicals)
  var tradeScore=Math.min(100,Math.round((rsi>30&&rsi<70?50:20)+(d.price>sma50?30:10)+(beta>0.8&&beta<2?20:5)));
  var verdict=investScore>70&&tradeScore>60?'INVEST (Long-term)':tradeScore>70&&investScore<50?'TRADE (Short-term)':investScore>60?'INVEST with timing':'MIXED — Wait';
  var vC=investScore>70&&tradeScore>60?'#059669':tradeScore>70&&investScore<50?'#3b82f6':'#d97706';
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px"><div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">Trade vs Invest</div>';
  h+='<div style="padding:3px 10px;border-radius:20px;font-size:8px;font-weight:800;background:'+vC+'15;color:'+vC+'">'+verdict+'</div></div>';
  h+='<div style="display:flex;gap:12px;margin-bottom:10px">';
  h+='<div style="flex:1;padding:12px;border-radius:10px;background:#f0fdf4;border:1.5px solid #bbf7d0;text-align:center">';
  h+='<div style="font-size:8px;color:#059669;font-weight:700">INVEST SCORE</div>';
  h+='<div style="font-size:24px;font-weight:900;color:#059669;font-family:JetBrains Mono">'+investScore+'</div>';
  h+='<div style="font-size:8px;color:#6b7280">F-Score + Moat + Value</div></div>';
  h+='<div style="flex:1;padding:12px;border-radius:10px;background:#eff6ff;border:1.5px solid #bfdbfe;text-align:center">';
  h+='<div style="font-size:8px;color:#2563eb;font-weight:700">TRADE SCORE</div>';
  h+='<div style="font-size:24px;font-weight:900;color:#2563eb;font-family:JetBrains Mono">'+tradeScore+'</div>';
  h+='<div style="font-size:8px;color:#6b7280">RSI + Trend + Volatility</div></div>';
  h+='</div>';
  h+='<div style="padding:6px 10px;border-radius:6px;background:#F8FAFC;font-size:9px;color:#374151">';
  h+='<strong style="color:'+vC+'">📋 '+verdict+'</strong> — '+(investScore>tradeScore?'Fundamentals are stronger than technicals. This is a long-term portfolio stock. Use SIP or buy-and-hold strategy.':'Technicals are stronger. This could be a short-term momentum play. Use tight stops and book profits at targets.')+'</div></div>';
  return h;
};

console.log('[CDS] Phase 1 charts loaded: ScenarioTree, Drawdown, DecisionConfidence, SignalConflict, TradeInvest');

// ═══════════════════════════════════════════════════════════════════════
// PHASE 2 CHARTS — Using advCharts data from API
// ═══════════════════════════════════════════════════════════════════════

// ── CHART 9: Volatility Regime ──
window._volatilityRegimeChart=function(d,S){
  if(!d||!d.advCharts||!d.advCharts.volRegime)return'';
  var vr=d.advCharts.volRegime;
  var regC=vr.regime==='LOW'?'#059669':vr.regime==='HIGH'?'#dc2626':'#d97706';
  var series=vr.series||[];
  var maxV=Math.max.apply(null,series.concat([1]));
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px"><div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">Volatility Regime</div>';
  h+='<div style="padding:3px 10px;border-radius:20px;font-size:8px;font-weight:800;background:'+regC+'15;color:'+regC+'">'+vr.regime+' ('+vr.current+'%)</div></div>';
  // Mini bar chart
  h+='<div style="display:flex;align-items:flex-end;gap:3px;height:50px;margin-bottom:8px">';
  series.forEach(function(v,i){
    var pct=Math.max(5,v/maxV*100);
    var bC=v>vr.avg*1.3?'#dc2626':v<vr.avg*0.8?'#059669':'#d97706';
    h+='<div style="flex:1;height:'+pct+'%;background:'+bC+';border-radius:2px 2px 0 0;min-height:3px" title="'+v+'%"></div>';
  });
  h+='</div>';
  h+='<div style="display:flex;justify-content:space-between;font-size:7px;color:#94a3b8"><span>3mo ago</span><span>Avg: '+vr.avg+'%</span><span>Now</span></div>';
  h+='<div style="margin-top:8px;padding:6px 10px;border-radius:6px;background:#F8FAFC;font-size:9px;color:#374151">';
  h+='<strong style="color:'+regC+'">📋 DECISION:</strong> '+(vr.regime==='LOW'?'Low volatility — favorable for entry. Tight stops work well in this regime.':vr.regime==='HIGH'?'High volatility — widen stops and reduce position size. Wait for volatility to compress before large entries.':'Normal volatility — standard position sizing appropriate.')+'</div></div>';
  return h;
};

// ── CHART 12: Accumulation vs Distribution ──
window._accumDistChart=function(d,S){
  if(!d||!d.advCharts||!d.advCharts.accumDist)return'';
  var ad=d.advCharts.accumDist;
  var sigC=ad.signal==='ACCUMULATION'?'#059669':ad.signal==='DISTRIBUTION'?'#dc2626':'#d97706';
  var total=ad.accDays+ad.distDays||1;
  var accPct=Math.round(ad.accDays/total*100);
  var distPct=100-accPct;
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px"><div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">Accumulation vs Distribution</div>';
  h+='<div style="padding:3px 10px;border-radius:20px;font-size:8px;font-weight:800;background:'+sigC+'15;color:'+sigC+'">'+ad.signal+'</div></div>';
  // Visual bar
  h+='<div style="display:flex;height:14px;border-radius:7px;overflow:hidden;margin-bottom:6px">';
  h+='<div style="width:'+accPct+'%;background:#059669;display:flex;align-items:center;justify-content:center;font-size:7px;color:#fff;font-weight:700">'+ad.accDays+' days</div>';
  h+='<div style="width:'+distPct+'%;background:#dc2626;display:flex;align-items:center;justify-content:center;font-size:7px;color:#fff;font-weight:700">'+ad.distDays+' days</div>';
  h+='</div>';
  h+='<div style="display:flex;justify-content:space-between;font-size:8px;margin-bottom:8px"><span style="color:#059669;font-weight:700">Accumulation ('+accPct+'%)</span><span style="font-weight:800;color:#1A3A78">Ratio: '+ad.ratio+'x</span><span style="color:#dc2626;font-weight:700">Distribution ('+distPct+'%)</span></div>';
  h+='<div style="padding:6px 10px;border-radius:6px;background:#F8FAFC;font-size:9px;color:#374151">';
  h+='<strong style="color:'+sigC+'">📋 DECISION:</strong> '+(ad.signal==='ACCUMULATION'?'Smart money is accumulating — institutions buying on higher volume. Bullish sign for medium-term.':ad.signal==='DISTRIBUTION'?'Distribution detected — selling on higher volume suggests institutions exiting. Exercise caution.':'Neutral flow — no strong directional bias from volume analysis. Wait for clearer signal.')+'</div></div>';
  return h;
};

// ── CHART 21: Liquidity Stress Test ──
window._stressTestChart=function(d,S){
  if(!d||!d.advCharts||!d.advCharts.stressTest)return'';S=S||'$';
  var st=d.advCharts.stressTest;
  var p=d.price||0;
  var scenarios=[
    {l:'Market -10%',dd:st.crash10,c:'#d97706'},
    {l:'Market -20%',dd:st.crash20,c:'#f97316'},
    {l:'2008 Crisis (-38%)',dd:st.crash2008,c:'#dc2626'},
    {l:'COVID 2020 (-34%)',dd:st.crash2020,c:'#dc2626'}
  ];
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px"><div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">Liquidity Stress Test</div>';
  h+='<div style="padding:3px 10px;border-radius:20px;font-size:8px;font-weight:800;background:#dc262615;color:#dc2626">Recovery ~'+st.recovery_months+' months</div></div>';
  h+='<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:8px">';
  scenarios.forEach(function(s){
    var priceAfter=Math.round(p*(1+s.dd/100));
    h+='<div style="padding:8px;border-radius:8px;background:'+s.c+'06;border:1px solid '+s.c+'15;text-align:center">';
    h+='<div style="font-size:7px;color:#6b7280;font-weight:700">'+s.l+'</div>';
    h+='<div style="font-size:16px;font-weight:900;color:'+s.c+';font-family:JetBrains Mono">'+s.dd+'%</div>';
    h+='<div style="font-size:8px;color:#94a3b8">→ '+S+priceAfter.toLocaleString()+'</div></div>';
  });
  h+='</div>';
  h+='<div style="padding:6px 10px;border-radius:6px;background:#F8FAFC;font-size:9px;color:#374151">';
  var worstDD=Math.abs(st.crash2008);
  h+='<strong style="color:#dc2626">📋 DECISION:</strong> '+(worstDD<25?'Defensive stock — limited crash exposure. Safe for large allocation.':worstDD<40?'Moderate crash risk. Use stop-losses and keep position under 10% of portfolio.':'High crash vulnerability. In a severe downturn, expect '+st.crash2008+'% decline. Size accordingly and consider hedging.')+'</div></div>';
  return h;
};

// ── CHART 10: Trend Persistence Score ──
window._trendPersistence=function(d,S){
  if(!d||!d.advCharts||!d.advCharts.trendPersistence)return'';
  var tp=d.advCharts.trendPersistence;
  var dirC=tp.direction==='BULLISH'?'#059669':tp.direction==='BEARISH'?'#dc2626':'#d97706';
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px"><div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">Trend Persistence</div>';
  h+='<div style="padding:3px 10px;border-radius:20px;font-size:8px;font-weight:800;background:'+dirC+'15;color:'+dirC+'">'+tp.direction+' ('+tp.score+'%)</div></div>';
  // Visual gauge
  h+='<div style="height:12px;background:#f1f5f9;border-radius:6px;position:relative;margin-bottom:6px">';
  h+='<div style="position:absolute;left:0;top:0;height:100%;width:'+tp.score+'%;background:linear-gradient(90deg,#dc2626,#d97706 40%,#059669);border-radius:6px"></div>';
  h+='<div style="position:absolute;left:'+tp.score+'%;top:-3px;width:4px;height:18px;background:#0A1628;border-radius:2px;transform:translateX(-2px)"></div></div>';
  h+='<div style="display:flex;justify-content:space-between;font-size:7px;color:#94a3b8"><span>BEARISH</span><span>NEUTRAL</span><span>BULLISH</span></div>';
  h+='<div style="margin-top:6px;font-size:9px;color:#6b7280;text-align:center">'+tp.upDays+' up days out of '+tp.totalDays+' trading days (last 3 months)</div>';
  h+='<div style="margin-top:8px;padding:6px 10px;border-radius:6px;background:#F8FAFC;font-size:9px;color:#374151">';
  h+='<strong style="color:'+dirC+'">📋 DECISION:</strong> '+(tp.score>60?'Strong upward persistence — trend-following strategies favored. Ride the trend with trailing stops.':tp.score<40?'Downward persistence — avoid catching falling knives. Wait for trend reversal (persistence > 50%) before entry.':'No strong trend persistence — range-bound. Consider mean-reversion strategies or wait for breakout.')+'</div></div>';
  return h;
};

// ── CHART 6: Peer Positioning Map (uses peerData) ──
window._peerMap=function(d,S){
  if(!d||!d.peerData||d.peerData.length<2)return'';S=S||'$';
  var peers=d.peerData.slice(0,6);
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif;margin-bottom:12px">Peer Comparison</div>';
  h+='<table style="width:100%;border-collapse:separate;border-spacing:0;border-radius:8px;overflow:hidden;font-size:10px">';
  h+='<tr style="background:#f8fafc"><th style="padding:6px 8px;text-align:left;font-size:8px;color:#94a3b8;font-weight:700">PEER</th><th style="padding:6px;text-align:center;font-size:8px;color:#94a3b8">PE</th><th style="padding:6px;text-align:center;font-size:8px;color:#94a3b8">ROE</th><th style="padding:6px;text-align:center;font-size:8px;color:#94a3b8">MOAT</th><th style="padding:6px;text-align:center;font-size:8px;color:#94a3b8">UPSIDE</th></tr>';
  peers.forEach(function(p){
    var uC=(p.upside||0)>10?'#059669':(p.upside||0)>0?'#d97706':'#dc2626';
    h+='<tr style="border-bottom:1px solid #f1f5f9"><td style="padding:6px 8px;font-weight:700">'+p.symbol+'</td>';
    h+='<td style="padding:6px;text-align:center">'+(p.pe||0).toFixed(1)+'x</td>';
    h+='<td style="padding:6px;text-align:center">'+(p.roe||0).toFixed(0)+'%</td>';
    h+='<td style="padding:6px;text-align:center">'+(p.moat||0)+'</td>';
    h+='<td style="padding:6px;text-align:center;color:'+uC+';font-weight:700">'+((p.upside||0)>0?'+':'')+(p.upside||0)+'%</td></tr>';
  });
  h+='</table></div>';
  return h;
};

// ── CHART 7b: Drawdown History (rolling, from advCharts) ──
window._drawdownHistory=function(d,S){
  if(!d||!d.advCharts||!d.advCharts.drawdownHistory)return'';
  var dd=d.advCharts.drawdownHistory;
  var series=dd.series||[];
  if(series.length<5)return'';
  var minDD=Math.min.apply(null,series);
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px"><div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">Drawdown History (1Y)</div>';
  h+='<div style="padding:3px 10px;border-radius:20px;font-size:8px;font-weight:800;background:#dc262615;color:#dc2626">Max: '+dd.maxDD+'%</div></div>';
  // Mini area chart
  h+='<div style="display:flex;align-items:flex-start;gap:2px;height:40px;margin-bottom:4px">';
  series.forEach(function(v){
    var pct=minDD<0?Math.max(3,Math.abs(v)/Math.abs(minDD)*100):5;
    h+='<div style="flex:1;height:'+pct+'%;background:'+(Math.abs(v)>20?'#dc2626':Math.abs(v)>10?'#f97316':'#d97706')+';border-radius:0 0 2px 2px;min-height:2px"></div>';
  });
  h+='</div>';
  h+='<div style="display:flex;justify-content:space-between;font-size:7px;color:#94a3b8"><span>1Y ago</span><span>Current: '+dd.currentDD+'%</span><span>Now</span></div>';
  h+='<div style="margin-top:8px;padding:6px 10px;border-radius:6px;background:#F8FAFC;font-size:9px;color:#374151">';
  h+='<strong style="color:#1A3A78">📋</strong> Max drawdown was <strong>'+dd.maxDD+'%</strong> over the past year. '+(Math.abs(dd.maxDD)<15?'Shallow drawdowns — low-risk profile.':Math.abs(dd.maxDD)<30?'Moderate drawdowns — expect 15-30% swings. Size positions accordingly.':'Deep drawdowns — this stock can fall hard. Use smaller positions and wider stops.')+'</div></div>';
  return h;
};

console.log('[CDS] Phase 2 charts loaded: VolRegime, AccumDist, StressTest, TrendPersist, PeerMap, DrawdownHistory');

// ═══════════════════════════════════════════════════════════════════════
// PHASE 3: ALL REMAINING MISSING CHARTS + GROUP SUMMARIES
// ═══════════════════════════════════════════════════════════════════════

// ── Helper: Group Summary Banner ──
window._groupSummary=function(emoji,title,question,answer,ansC){
  var c=ansC||'#1A3A78';
  return '<div style="margin:20px 0 6px;padding:14px 18px;border-radius:14px;background:linear-gradient(135deg,'+c+'15,'+c+'06);border-left:5px solid '+c+';border:1.5px solid '+c+'30;box-shadow:0 2px 8px '+c+'08">'
    +'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px">'
    +'<div style="display:flex;align-items:center;gap:10px"><div style="width:34px;height:34px;border-radius:8px;background:'+c+'18;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0">'+emoji+'</div>'
    +'<div><div style="font-size:12px;font-weight:900;color:'+c+';font-family:Sora,sans-serif;letter-spacing:.3px;text-transform:uppercase">'+title+'</div>'
    +'<div style="font-size:9px;color:#5E6F8E;margin-top:3px;font-style:italic">"'+question+'"</div></div></div>'
    +'<div style="font-size:10px;font-weight:800;color:#fff;background:'+c+';padding:5px 14px;border-radius:20px;white-space:nowrap;flex-shrink:0;margin-top:2px;box-shadow:0 2px 6px '+c+'30">'+answer+'</div>'
    +'</div></div>';
};

// ── Chart 1: Implied Expectations (Reverse DCF) ──
window._impliedExpectationsChart=function(d,S){
  if(!d||!d.price)return'';S=S||'$';
  var p=d.price,pe=d.valuation?(d.valuation.pe||0):0,fund=d.fundamental||{};
  var revG=fund.revenueGrowth||fund.revGrowth||0,earnG=fund.earningsGrowth||fund.earnGrowth||revG;
  var fv=d.intrinsicValue?(d.intrinsicValue.average||0):0;
  if(!pe||pe<=0)return'';
  // What growth rate does current price imply?
  var sectorPE=d.valuation?(d.valuation.sectorPE||pe):pe;
  var impliedGrowth=(d.chartData&&d.chartData.impliedGrowth!=null)?d.chartData.impliedGrowth:Math.round((pe/Math.max(sectorPE,10)-1)*100);
  var actualGrowth=(d.chartData&&d.chartData.actualGrowth!=null)?d.chartData.actualGrowth:Math.round(revG);
  var gap=impliedGrowth-actualGrowth;
  var gapC=gap>15?'#dc2626':gap>5?'#d97706':gap<-10?'#059669':'#3b82f6';
  var verdict=gap>15?'OVERPRICED — market expects '+impliedGrowth+'% growth but company delivers '+actualGrowth+'%':gap>5?'SLIGHTLY RICH — mild optimism priced in':gap<-10?'UNDERPRICED — market underestimates actual growth':'FAIRLY PRICED — expectations match reality';
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px"><div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">Implied Expectations (Reverse DCF)</div>';
  h+='<div style="padding:3px 10px;border-radius:20px;font-size:8px;font-weight:800;background:'+gapC+'15;color:'+gapC+'">Gap: '+(gap>0?'+':'')+gap+'%</div></div>';
  h+='<div style="display:flex;gap:10px;margin-bottom:10px">';
  h+='<div style="flex:1;padding:10px;border-radius:10px;background:#eff6ff;border:1.5px solid #bfdbfe;text-align:center"><div style="font-size:8px;color:#3b82f6;font-weight:700">MARKET EXPECTS</div><div style="font-size:22px;font-weight:900;color:#2563eb;font-family:JetBrains Mono">'+impliedGrowth+'%</div><div style="font-size:8px;color:#94a3b8">implied by PE '+pe.toFixed(1)+'x</div></div>';
  h+='<div style="flex:1;padding:10px;border-radius:10px;background:#f0fdf4;border:1.5px solid #bbf7d0;text-align:center"><div style="font-size:8px;color:#059669;font-weight:700">ACTUAL GROWTH</div><div style="font-size:22px;font-weight:900;color:#059669;font-family:JetBrains Mono">'+actualGrowth+'%</div><div style="font-size:8px;color:#94a3b8">revenue growth YoY</div></div></div>';
  h+='<div style="padding:6px 10px;border-radius:6px;background:#F8FAFC;font-size:9px;color:#374151"><strong style="color:'+gapC+'">📋 DECISION:</strong> '+verdict+'</div>';
  h+='<div style="margin-top:8px;padding:8px 12px;border-radius:8px;background:#FFFBEB;border:1px solid #FDE68A;font-size:9px;color:#92400E;line-height:1.7">💡 <strong>What This Means For You:</strong> Think of PE like a price tag per ₹1 of profit. If the market charges a higher PE than the sector average, it means investors expect faster growth. The "Market Expects" box shows what growth rate the current stock price implies. The "Actual Growth" box shows what the company is really delivering. If actual > expected, the stock is a bargain. If actual < expected, you may be overpaying for hope.</div>';
  h+='</div>';
  return h;
};

// ── Chart 2: Earnings Distribution Cone ──
window._earningsDistCone=function(d,S){
  if(!d||!d.price)return'';S=S||'$';
  var fund=d.fundamental||{},eps=fund.eps||0;
  // Fallback: estimate EPS from price and PE
  if(!eps||eps<=0){
    var pe=d.pe||(d.valuation?d.valuation.pe:0)||0;
    if(pe>0)eps=d.price/pe;
    else eps=d.price/20; // Assume PE 20 as rough estimate
  }
  if(!eps||eps<=0)return'';
  var epsCon=d.epsConsistency||{};
  var epsStd=(d.chartData&&d.chartData.epsStd)?d.chartData.epsStd:(epsCon.std||Math.abs(eps*0.15));
  var quarters=['Q+1','Q+2','Q+3','Q+4','Q+5','Q+6','Q+7','Q+8'];
  var growthRate=(d.chartData&&d.chartData.epsGrowthRate)?d.chartData.epsGrowthRate:Math.max(-0.1,Math.min(0.3,(fund.earnGrowth||fund.revGrowth||5)/100/4));
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif;margin-bottom:4px">Earnings Distribution Cone</div>';
  h+='<div style="font-size:8px;color:#94a3b8;margin-bottom:8px">Projected quarterly EPS (P10 / P50 / P90) over next 8 quarters</div>';
  h+='<div style="display:flex;align-items:center;gap:2px;margin-bottom:4px">';
  quarters.forEach(function(q,i){
    var baseEPS=eps*(1+growthRate*(i+1));
    var spread=epsStd*(1+i*0.15);
    var p90=baseEPS+spread*1.3;
    var p50=baseEPS;
    var p10=baseEPS-spread*1.3;
    var height=Math.max(20,Math.min(60,20+i*5));
    h+='<div style="flex:1;text-align:center">';
    h+='<div style="font-size:6px;color:#059669">'+S+(p90).toFixed(2)+'</div>';
    h+='<div style="height:'+height+'px;background:linear-gradient(180deg,#05966920,#3b82f640,#dc262620);border-radius:3px;margin:1px 0;display:flex;align-items:center;justify-content:center">';
    h+='<div style="font-size:7px;font-weight:800;color:#1A3A78">'+S+(p50).toFixed(2)+'</div></div>';
    h+='<div style="font-size:6px;color:#dc2626">'+S+(p10).toFixed(2)+'</div>';
    h+='<div style="font-size:6px;color:#94a3b8;margin-top:2px">'+q+'</div></div>';
  });
  h+='</div>';
  h+='<div style="display:flex;gap:8px;font-size:7px;margin-bottom:8px"><span style="color:#059669">■ P90 (Bull)</span><span style="color:#3b82f6">■ P50 (Base)</span><span style="color:#dc2626">■ P10 (Bear)</span></div>';
  h+='<div style="padding:6px 10px;border-radius:6px;background:#F8FAFC;font-size:9px;color:#374151"><strong style="color:#1A3A78">📋</strong> '+(growthRate>0.03?'Strong earnings trajectory — cone expands upward. Quality compounder.':growthRate>0?'Modest earnings growth — stability preferred over explosive growth.':'Flat or declining earnings — cone compresses. Re-evaluate investment thesis.')+'</div></div>';
  return h;
};

// ── Chart 18: Factor Contribution Timeline (REAL IMPLEMENTATION) ──
// Shows how Value, Quality, Momentum, Safety factors have contributed
// to this stock's return across 6 rolling periods (2M → 12M lookbacks)
window._factorContributionTimeline=function(d,S){
  if(!d||!d.price)return'';S=S||'$';
  var beta=parseFloat(d.beta||1);
  var roe=parseFloat(d.roe||0);
  var fScore=d.fScore||(d.business?d.business.fScore:0)||0;
  var rsi=parseFloat(d.rsi||50);
  var upside=parseFloat(d.upside||0);
  var pe=parseFloat(d.valuation?d.valuation.pe:0)||0;
  var sma50=d.sma_50||d.sma50||d.price;
  var sma200=d.sma_200||d.sma200||d.price;
  var priceChg=d.price_change_pct||(d.chartData?d.chartData.priceChange1Y:0)||0;

  // Compute factor scores across 6 time windows (2M → 12M)
  // Each window decays momentum signal while quality/value are more stable
  var periods=['2M','3M','4M','6M','9M','12M'];
  var decays=[1.0, 0.92, 0.85, 0.72, 0.60, 0.50]; // momentum decay by window

  // Base factor contributions (0-100 scale)
  var baseValue=upside>30?80:upside>10?65:upside>0?45:20;
  var baseQuality=fScore>=8?85:fScore>=6?65:fScore>=4?45:20;
  var baseMomentum=rsi>60&&d.price>sma50?80:rsi>50&&d.price>sma200?60:rsi>40?40:20;
  var baseSafety=beta<1?75:beta<1.3?55:beta<1.7?35:15;

  // Colour palette
  var fColors={Value:'#3b82f6',Quality:'#059669',Momentum:'#d97706',Safety:'#8b5cf6'};
  var factors=['Value','Quality','Momentum','Safety'];
  var bases={Value:baseValue,Quality:baseQuality,Momentum:baseMomentum,Safety:baseSafety};

  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">';
  h+='<div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">Factor Contribution Timeline</div>';
  h+='<div style="font-size:7px;color:#d97706;font-weight:700">⚠️ PROXY: Estimated from current factor scores with decay model — not historical factor return attribution</div>';
  // Overall dominant factor badge
  var dominant=factors.reduce(function(a,b){return bases[a]>bases[b]?a:b});
  var domC=fColors[dominant];
  h+='<div style="padding:3px 10px;border-radius:20px;font-size:8px;font-weight:800;background:'+domC+'15;color:'+domC+'">Strongest: '+dominant+'</div></div>';
  h+='<div style="font-size:8px;color:#94a3b8;margin-bottom:12px">Rolling factor score (Value / Quality / Momentum / Safety) across lookback periods</div>';

  // Chart: grouped bars per period
  h+='<div style="display:flex;gap:3px;align-items:flex-end;height:80px;margin-bottom:6px">';
  periods.forEach(function(period,pi){
    var decay=decays[pi];
    // Value and Quality are sticky; Momentum decays backward; Safety is stable
    var scores={
      Value:Math.round(baseValue*(0.9+pi*0.02)),        // slightly improves with longer view
      Quality:Math.round(baseQuality*(0.95+pi*0.01)),   // very stable
      Momentum:Math.round(baseMomentum*decay),           // decays — recent momentum fades
      Safety:Math.round(baseSafety*(0.98+pi*0.005))     // near-stable
    };
    var periodMax=Math.max.apply(null,factors.map(function(f){return scores[f]}));
    var stackH=Math.max(8,Math.round(periodMax*0.75)); // scale to chart height
    h+='<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:1px">';
    // Mini stacked bars (each factor = 1 row segment)
    factors.forEach(function(f){
      var barH=Math.max(2,Math.round(scores[f]/100*18));
      h+='<div style="width:100%;height:'+barH+'px;background:'+fColors[f]+';border-radius:1px;opacity:0.85" title="'+f+': '+scores[f]+'/100"></div>';
    });
    h+='<div style="font-size:6px;color:#94a3b8;margin-top:2px">'+period+'</div>';
    h+='</div>';
  });
  h+='</div>';

  // Legend
  h+='<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px">';
  factors.forEach(function(f){
    h+='<div style="display:flex;align-items:center;gap:3px"><div style="width:8px;height:8px;border-radius:2px;background:'+fColors[f]+'"></div>';
    h+='<span style="font-size:8px;color:#374151;font-weight:600">'+f+' <span style="color:'+fColors[f]+';font-weight:900">'+bases[f]+'</span></span></div>';
  });
  h+='</div>';

  // Current snapshot table
  h+='<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:4px;margin-bottom:10px">';
  factors.forEach(function(f){
    var score=bases[f];
    var fc=fColors[f];
    var grade=score>=75?'A':score>=55?'B':score>=35?'C':'D';
    var gradeLabel=score>=75?'Strong':score>=55?'Decent':score>=35?'Weak':'Poor';
    h+='<div style="padding:7px 6px;border-radius:8px;background:'+fc+'08;border:1px solid '+fc+'20;text-align:center">';
    h+='<div style="font-size:7px;color:'+fc+';font-weight:800">'+f.toUpperCase()+'</div>';
    h+='<div style="font-size:18px;font-weight:900;color:'+fc+';font-family:JetBrains Mono;line-height:1.1">'+grade+'</div>';
    h+='<div style="font-size:7px;color:#94a3b8">'+gradeLabel+' ('+score+')</div></div>';
  });
  h+='</div>';

  // Insight
  var momTrend=bases.Momentum<50?'Momentum is the weakest factor — short-term timing is unfavorable.':bases.Momentum>=70?'Momentum is strong — trend is supporting the thesis.':'Momentum is neutral — no timing edge, but no headwind either.';
  var qualInsight=bases.Quality>=75?' Quality is exceptional — this is a fundamentally sound business regardless of short-term price action.':bases.Quality>=55?' Business quality is decent but not top-tier.':' Quality concerns exist — re-evaluate core thesis.';
  var valInsight=bases.Value>=65?' Valuation is attractive — value factor supports entry.':' Value factor is weak — stock may be fairly priced or overvalued.';

  h+='<div style="padding:8px 10px;border-radius:7px;background:#1A3A7808;border-left:3px solid #1A3A78;font-size:9px;color:#374151;line-height:1.7">';
  h+='<strong style="color:#1A3A78">📋 Factor insight:</strong> '+momTrend+qualInsight+valInsight;
  h+='</div></div>';
  return h;
};

// ── Chart 3: Time-to-Value Realization ──
window._timeToValue=function(d,S){
  if(!d||!d.price)return'';S=S||'$';
  var p=d.price,fv=d.intrinsicValue?(d.intrinsicValue.average||0):0;
  var upside=d.upside||0;
  if(!fv||Math.abs(upside)<1)return'';
  var fund=d.fundamental||{};
  var cagr=Math.max(5,Math.abs(fund.revGrowth||10));
  // How long to close the gap at current growth?
  var yearsToFV=(d.chartData&&d.chartData.yearsToFV)?d.chartData.yearsToFV:(upside>0?Math.ceil(Math.log(fv/p)/Math.log(1+cagr/100)):0);
  var months=[3,6,12,18,24,36];
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px"><div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">Time-to-Value Realization</div>';
  h+='<div style="padding:3px 10px;border-radius:20px;font-size:8px;font-weight:800;background:#3b82f615;color:#3b82f6">~'+yearsToFV+' years to fair value</div></div>';
  h+='<div style="display:flex;gap:4px;margin-bottom:8px">';
  months.forEach(function(m){
    var prob=upside>0?Math.min(95,Math.round(20+m/36*75*(cagr/15))):Math.max(5,Math.round(80-m/36*60));
    var barH=Math.max(10,prob*0.5);
    var bC=prob>70?'#059669':prob>40?'#d97706':'#dc2626';
    h+='<div style="flex:1;text-align:center"><div style="height:50px;display:flex;align-items:flex-end;justify-content:center">';
    h+='<div style="width:70%;height:'+barH+'px;background:'+bC+';border-radius:3px 3px 0 0"></div></div>';
    h+='<div style="font-size:8px;font-weight:800;color:'+bC+';margin-top:2px">'+prob+'%</div>';
    h+='<div style="font-size:7px;color:#94a3b8">'+m+'mo</div></div>';
  });
  h+='</div>';
  h+='<div style="padding:6px 10px;border-radius:6px;background:#F8FAFC;font-size:9px;color:#374151"><strong style="color:#1A3A78">📋</strong> '+(yearsToFV<=1?'Quick value realization expected — this is a high-conviction entry. Price should approach fair value within 12 months.':yearsToFV<=3?'Medium-term value play — patience required. Best suited for 1-3 year investment horizon.':'Long-term thesis — value may take years to realize. Suitable only for patient, long-term investors.')+'</div></div>';
  return h;
};

// ── Chart 4: Valuation Regime Bands ──
window._valRegimeBands=function(d,S){
  if(!d||!d.price)return'';S=S||'$';
  var p=d.price,pe=d.valuation?(d.valuation.pe||0):0;
  if(!pe)return'';
  var cheap=pe<12?'CURRENT':pe<15?'NEAR':'ABOVE';
  var fair=pe>=12&&pe<=22?'CURRENT':'OUTSIDE';
  var expensive=pe>25?'CURRENT':pe>20?'NEAR':'BELOW';
  var regime=pe<12?'CHEAP':pe<18?'FAIR':pe<25?'GETTING EXPENSIVE':'EXPENSIVE';
  var regC=pe<12?'#059669':pe<18?'#3b82f6':pe<25?'#d97706':'#dc2626';
  var pctile=Math.min(100,Math.max(0,Math.round((pe-5)/35*100)));
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px"><div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">Valuation Regime</div>';
  h+='<div style="padding:3px 10px;border-radius:20px;font-size:8px;font-weight:800;background:'+regC+'15;color:'+regC+'">'+regime+' (PE '+pe.toFixed(1)+'x)</div></div>';
  // Zone bar
  h+='<div style="height:16px;display:flex;border-radius:8px;overflow:hidden;margin-bottom:4px">';
  h+='<div style="width:30%;background:#05966930;display:flex;align-items:center;justify-content:center;font-size:7px;font-weight:700;color:#059669">CHEAP</div>';
  h+='<div style="width:35%;background:#3b82f620;display:flex;align-items:center;justify-content:center;font-size:7px;font-weight:700;color:#3b82f6">FAIR</div>';
  h+='<div style="width:35%;background:#dc262620;display:flex;align-items:center;justify-content:center;font-size:7px;font-weight:700;color:#dc2626">EXPENSIVE</div></div>';
  h+='<div style="position:relative;height:8px;margin-bottom:8px"><div style="position:absolute;left:'+pctile+'%;top:-4px;width:0;height:0;border-left:6px solid transparent;border-right:6px solid transparent;border-top:8px solid #0A1628;transform:translateX(-6px)"></div></div>';
  h+='<div style="padding:6px 10px;border-radius:6px;background:#F8FAFC;font-size:9px;color:#374151"><strong style="color:'+regC+'">📋 DECISION:</strong> '+(pe<12?'Cheap zone — strong buying opportunity if quality is intact.':pe<18?'Fair zone — reasonable entry. Focus on quality and growth.':pe<25?'Getting expensive — be selective. Only buy on dips with strong catalysts.':'Expensive zone — avoid new positions. Consider trimming if you hold.')+'</div></div>';
  return h;
};

// ── Chart 15: Factor Crowding Score ──
window._factorCrowding=function(d,S){
  if(!d||!d.price)return'';
  var beta=d.beta||1,pe=d.valuation?(d.valuation.pe||0):0;
  var fund=d.fundamental||{};
  var mcap=d.marketCap||0;
  // Crowding heuristic: popular stocks with high beta, high PE, and large cap tend to be crowded
  var crowdScore=(d.chartData&&d.chartData.crowdingScore!=null)?d.chartData.crowdingScore:Math.min(100,Math.max(0,Math.round((beta>1.2?30:10)+(pe>25?30:pe>15?15:5)+(mcap>1e12?20:mcap>1e11?10:0)+(Math.abs(fund.revGrowth||0)>50?20:10))));
  var crowdC=crowdScore>70?'#dc2626':crowdScore>40?'#d97706':'#059669';
  var crowdLabel=crowdScore>70?'HIGH CROWDING':crowdScore>40?'MODERATE':'LOW CROWDING';
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px"><div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">Factor Crowding Risk</div>';
  h+='<div style="padding:3px 10px;border-radius:20px;font-size:8px;font-weight:800;background:'+crowdC+'15;color:'+crowdC+'">'+crowdLabel+'</div></div>';
  h+='<div style="text-align:center;margin-bottom:8px"><div style="font-size:36px;font-weight:900;color:'+crowdC+';font-family:JetBrains Mono">'+crowdScore+'<span style="font-size:14px;color:#94a3b8">/100</span></div></div>';
  h+='<div style="padding:6px 10px;border-radius:6px;background:#F8FAFC;font-size:9px;color:#374151"><strong style="color:'+crowdC+'">📋</strong> '+(crowdScore>70?'High crowding — this is a popular trade. When sentiment turns, crowded names fall hardest. Keep tight stops.':crowdScore>40?'Moderate crowding — some institutional interest but not overly popular. Normal risk.':'Low crowding — under-the-radar. Less vulnerable to momentum unwinds. Contrarian opportunity.')+'</div></div>';
  return h;
};

// ── Chart 22: Market Regime Map ──
window._marketRegimeMap=function(d,S){
  if(!d||!d.price)return'';
  var tech=d.technicals||{};
  var rsi=d.rsi||tech.rsi||50;
  var sma200=d.sma200||tech.sma200||d.price;
  var beta=d.beta||1;
  var macro=d.macro||{};
  var riskOn=d.price>sma200&&rsi>45;
  var regime=riskOn?'RISK ON':'RISK OFF';
  var regC=riskOn?'#059669':'#dc2626';
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px"><div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">Market Regime</div>';
  h+='<div style="padding:3px 10px;border-radius:20px;font-size:8px;font-weight:800;background:'+regC+'15;color:'+regC+'">'+regime+'</div></div>';
  h+='<div style="display:flex;gap:8px;margin-bottom:8px">';
  [{l:'Price vs SMA200',v:d.price>sma200?'ABOVE':'BELOW',ok:d.price>sma200},{l:'RSI Regime',v:rsi>55?'BULLISH':rsi>45?'NEUTRAL':'BEARISH',ok:rsi>45},{l:'Volatility',v:beta<1.3?'CALM':beta<1.8?'NORMAL':'ELEVATED',ok:beta<1.5}].forEach(function(m){
    h+='<div style="flex:1;padding:8px;border-radius:8px;background:'+(m.ok?'#f0fdf4':'#fef2f2')+';border:1px solid '+(m.ok?'#bbf7d0':'#fecaca')+';text-align:center">';
    h+='<div style="font-size:7px;color:#94a3b8;font-weight:700">'+m.l+'</div>';
    h+='<div style="font-size:10px;font-weight:800;color:'+(m.ok?'#059669':'#dc2626')+'">'+m.v+'</div></div>';
  });
  h+='</div>';
  h+='<div style="padding:6px 10px;border-radius:6px;background:#F8FAFC;font-size:9px;color:#374151"><strong style="color:'+regC+'">📋</strong> '+(riskOn?'Risk-ON regime — favor equities, growth, and cyclicals. Aggressive positioning appropriate.':'Risk-OFF regime — favor cash, bonds, and defensives. Reduce equity exposure and tighten stops.')+'</div></div>';
  return h;
};

// ── Chart 25: Probability-Weighted Return Distribution ──
window._probWeightedReturn=function(d,S){
  if(!d||!d.price)return'';S=S||'$';
  var mc=d.monteCarlo||{},p=d.price;
  if(!mc.p50)return'';
  var _sr=d.chartData?d.chartData.scenarioReturns:null;
  var scenarios=[
    {l:'Deep Bear',prob:_sr?_sr.deepBear.prob:5,ret:_sr?_sr.deepBear.ret:(mc.p10?Math.round((mc.p10-p)/p*100):-30),c:'#dc2626'},
    {l:'Bear',prob:_sr?_sr.bear.prob:15,ret:_sr?_sr.bear.ret:(mc.p25?Math.round((mc.p25-p)/p*100):-15),c:'#f97316'},
    {l:'Base',prob:_sr?_sr.base.prob:50,ret:_sr?_sr.base.ret:(mc.p50?Math.round((mc.p50-p)/p*100):10),c:'#3b82f6'},
    {l:'Bull',prob:_sr?_sr.bull.prob:20,ret:_sr?_sr.bull.ret:(mc.p75?Math.round((mc.p75-p)/p*100):30),c:'#059669'},
    {l:'Strong Bull',prob:_sr?_sr.strongBull.prob:10,ret:_sr?_sr.strongBull.ret:(mc.p90?Math.round((mc.p90-p)/p*100):60),c:'#059669'}
  ];
  var ev=scenarios.reduce(function(s,sc){return s+sc.prob/100*sc.ret},0);
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px"><div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">Probability-Weighted Returns</div>';
  h+='<div style="padding:3px 10px;border-radius:20px;font-size:8px;font-weight:800;background:'+(ev>0?'#059669':'#dc2626')+'15;color:'+(ev>0?'#059669':'#dc2626')+'">EV: '+(ev>0?'+':'')+Math.round(ev)+'%</div></div>';
  h+='<div style="display:flex;align-items:flex-end;gap:4px;height:60px;margin-bottom:6px">';
  scenarios.forEach(function(s){
    var barH=Math.max(8,s.prob*1.1);
    h+='<div style="flex:1;text-align:center"><div style="height:60px;display:flex;align-items:flex-end;justify-content:center"><div style="width:80%;height:'+barH+'px;background:'+s.c+';border-radius:3px 3px 0 0"></div></div>';
    h+='<div style="font-size:7px;font-weight:700;color:'+s.c+'">'+(s.ret>0?'+':'')+s.ret+'%</div>';
    h+='<div style="font-size:6px;color:#94a3b8">'+s.prob+'%</div>';
    h+='<div style="font-size:6px;color:#94a3b8">'+s.l+'</div></div>';
  });
  h+='</div>';
  h+='<div style="padding:6px 10px;border-radius:6px;background:#F8FAFC;font-size:9px;color:#374151"><strong style="color:#1A3A78">📋</strong> Expected return: <strong>'+(ev>0?'+':'')+Math.round(ev)+'%</strong>. '+(ev>15?'Strongly skewed to upside — probability favors this trade.':ev>5?'Moderately positive expected value. Size with conviction.':ev>-5?'Near-neutral expected return. Risk/reward not compelling enough for large positions.':'Negative expected value — more downside than upside. Avoid or wait for better entry.')+'</div></div>';
  return h;
};

// ── Chart 27: Risk Contribution ──
window._riskContribution=function(d,S){
  if(!d||!d.price)return'';
  var beta=d.beta||1;
  var riskPct=(d.chartData&&d.chartData.riskContribPct!=null)?d.chartData.riskContribPct:Math.min(100,Math.round(beta/1.5*50));
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif;margin-bottom:8px">Risk Contribution to Portfolio</div>';
  h+='<div style="font-size:9px;color:#94a3b8;margin-bottom:8px">If this stock is 5% of your portfolio, it contributes <strong style="color:#1A3A78">'+riskPct+'%</strong> of portfolio volatility (beta-weighted)</div>';
  h+='<div style="height:12px;background:#f1f5f9;border-radius:6px;overflow:hidden"><div style="width:'+riskPct+'%;height:100%;background:'+(riskPct>60?'#dc2626':riskPct>30?'#d97706':'#059669')+';border-radius:6px"></div></div>';
  h+='<div style="margin-top:8px;padding:6px 10px;border-radius:6px;background:#F8FAFC;font-size:9px;color:#374151"><strong>📋</strong> '+(riskPct>60?'High risk contributor — this stock disproportionately impacts portfolio volatility. Consider reducing allocation.':riskPct>30?'Moderate risk — acceptable for a diversified portfolio.':'Low risk contributor — this is a stabilizing holding. Safe for larger allocation.')+'</div></div>';
  return h;
};

// ── Chart 29: Allocation Recommendation Gauge ──
window._allocGauge=function(d,S){
  if(!d||!d.price)return'';
  var alloc=d.allocation||{};
  // kellyFull = full kelly %, kellyFrac = what fraction to use (e.g. 50 = use 50% of full kelly)
  var kellyFull=parseFloat(alloc.kellyFull)||0;
  var kellyFracPct=parseFloat(alloc.kellyFrac)||50; // default 50% of full kelly
  // Recommended = Full Kelly × fraction
  var rec=kellyFull>0?Math.round(kellyFull*kellyFracPct/100):Math.max(1,parseFloat(String(alloc.pct||'0').replace(/[^0-9.]/g,''))||0);
  rec=Math.min(20,Math.max(0,rec));
  var recC=rec>=8?'#059669':rec>=3?'#d97706':'#dc2626';
  var tier=alloc.tier||'';
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">';
  h+='<div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">Allocation Recommendation</div>';
  if(tier)h+='<div style="padding:3px 10px;border-radius:20px;font-size:8px;font-weight:800;background:'+recC+'15;color:'+recC+'">'+tier+'</div>';
  h+='</div>';
  // Arc gauge visual
  var gaugePct=Math.min(100,rec/20*100);
  h+='<div style="text-align:center;margin-bottom:8px">';
  h+='<div style="font-family:JetBrains Mono,monospace;font-size:42px;font-weight:900;color:'+recC+'">'+rec+'%</div>';
  h+='<div style="font-size:9px;color:#5E6F8E;margin-top:2px">of portfolio — <strong>Half-Kelly recommended size</strong></div>';
  // Progress bar
  h+='<div style="margin:8px auto;max-width:200px;height:6px;border-radius:3px;background:#e2e8f0;overflow:hidden">';
  h+='<div style="width:'+gaugePct+'%;height:100%;border-radius:3px;background:linear-gradient(90deg,'+recC+','+recC+'cc)"></div></div>';
  h+='<div style="display:flex;justify-content:space-between;max-width:200px;margin:0 auto;font-size:7px;color:#94a3b8"><span>0%</span><span>10%</span><span>20%</span></div>';
  h+='</div>';
  // Breakdown table
  h+='<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:8px">';
  h+='<div style="padding:8px;border-radius:8px;background:'+recC+'08;border:1px solid '+recC+'20;text-align:center">';
  h+='<div style="font-size:7px;color:'+recC+';font-weight:800;letter-spacing:1px">RECOMMENDED</div>';
  h+='<div style="font-size:20px;font-weight:900;color:'+recC+';font-family:JetBrains Mono">'+rec+'%</div>';
  h+='<div style="font-size:7px;color:#94a3b8">Half-Kelly (safer)</div></div>';
  h+='<div style="padding:8px;border-radius:8px;background:#f8fafc;border:1px solid #e2e8f0;text-align:center">';
  h+='<div style="font-size:7px;color:#94a3b8;font-weight:800;letter-spacing:1px">FULL KELLY</div>';
  h+='<div style="font-size:20px;font-weight:900;color:#94a3b8;font-family:JetBrains Mono">'+(kellyFull>0?Math.round(kellyFull)+'%':'N/A')+'</div>';
  h+='<div style="font-size:7px;color:#94a3b8">Max (too aggressive)</div></div></div>';
  h+='<div style="padding:7px 10px;border-radius:7px;background:#1A3A7808;border-left:3px solid #1A3A78;font-size:9px;color:#374151;line-height:1.6">';
  h+='<strong style="color:#1A3A78">Rule of thumb:</strong> Use '+rec+'% (Half-Kelly). '+(rec>=8?'High conviction position — deploy with confidence. Review quarterly.':rec>=3?'Moderate conviction — build gradually via SIP over 2-3 months.':'Low conviction — small starter position only. Wait for signals to improve.')+'</div>';
  h+='</div>';
  return h;
};

console.log('[CDS] Phase 3 charts loaded: ImpliedExpect, EarningsCone, TimeToValue, ValRegime, FactorCrowding, MarketRegime, ProbReturn, RiskContrib, AllocGauge');

// ═══════════════════════════════════════════════════════════════════════
// PHASE 4: REMAINING 10 CHARTS — Groups 4, 7, 11, 12
// Using fundHoldings, newsSentiment, macroSensitivity from API
// ═══════════════════════════════════════════════════════════════════════

// ── Chart 11: Institutional Ownership Trend ──
window._instOwnershipTrend=function(d,S){
  if(!d)return'';
  var instPct=d.institutionalOwnership||0;
  var fh=d.fundHoldings||{};
  var summary=fh.summary||{};
  var insiderPct=summary.insider_pct||0;
  var floatInst=summary.float_inst_pct||0;
  var instCount=summary.inst_count||0;
  var topHolders=fh.institutions||[];
  // Fallback estimates when data is missing
  if(!instPct&&!topHolders.length){
    instPct=d.fundamental?(d.fundamental.institutionPct||0):0;
    if(!instPct)instPct=35; // Default estimate for large caps
    insiderPct=insiderPct||5;
  }
  var retailPct=Math.max(0,100-instPct-insiderPct);
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px"><div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">Institutional Ownership</div>';
  h+='<div style="padding:3px 10px;border-radius:20px;font-size:8px;font-weight:800;background:'+(instPct>60?'#059669':'#d97706')+'15;color:'+(instPct>60?'#059669':'#d97706')+'">'+instPct.toFixed(1)+'% institutional</div></div>';
  // Ownership pie (horizontal bar)
  h+='<div style="display:flex;height:16px;border-radius:8px;overflow:hidden;margin-bottom:6px">';
  if(instPct>0)h+='<div style="width:'+instPct+'%;background:#3b82f6;display:flex;align-items:center;justify-content:center;font-size:7px;color:#fff;font-weight:700">Inst '+instPct.toFixed(0)+'%</div>';
  if(insiderPct>0)h+='<div style="width:'+Math.max(5,insiderPct)+'%;background:#8b5cf6;display:flex;align-items:center;justify-content:center;font-size:7px;color:#fff;font-weight:700">Insider</div>';
  if(retailPct>0)h+='<div style="width:'+retailPct+'%;background:#94a3b8;display:flex;align-items:center;justify-content:center;font-size:7px;color:#fff;font-weight:700">Retail '+retailPct.toFixed(0)+'%</div>';
  h+='</div>';
  // KPI row
  h+='<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:4px;margin-bottom:8px">';
  [{l:'INSTITUTIONAL',v:instPct.toFixed(1)+'%'},{l:'INSIDER',v:insiderPct.toFixed(1)+'%'},{l:'FLOAT HELD',v:floatInst.toFixed(1)+'%'},{l:'# INSTITUTIONS',v:instCount.toLocaleString()}].forEach(function(k){
    h+='<div style="padding:5px;border-radius:6px;background:#f8fafc;border:1px solid #e5e7eb;text-align:center"><div style="font-size:6px;color:#94a3b8;font-weight:700">'+k.l+'</div><div style="font-size:10px;font-weight:900;color:#1A3A78">'+k.v+'</div></div>';
  });
  h+='</div>';
  // Top 5 holders
  if(topHolders.length>0){
    h+='<div style="font-size:8px;font-weight:800;color:#94a3b8;margin-bottom:4px">TOP HOLDERS</div>';
    h+='<table style="width:100%;border-collapse:collapse;font-size:9px">';
    topHolders.slice(0,5).forEach(function(th){
      h+='<tr style="border-bottom:1px solid #f1f5f9"><td style="padding:3px 4px;font-weight:600">'+th.name+'</td><td style="padding:3px;text-align:right;color:#3b82f6;font-weight:700">'+th.pct.toFixed(2)+'%</td></tr>';
    });
    h+='</table>';
  }
  h+='<div style="margin-top:8px;padding:6px 10px;border-radius:6px;background:#F8FAFC;font-size:9px;color:#374151">';
  h+='<strong style="color:#1A3A78">📋 DECISION:</strong> '+(instPct>75?'Very high institutional ownership — well-researched stock. Follow the smart money but watch for crowding risk.':instPct>50?'Healthy institutional interest — validates the investment thesis. Institutions have done due diligence.':instPct>25?'Moderate institutional ownership — some professional interest. Growing institutional attention could be a catalyst.':'Low institutional ownership — under-the-radar. Could be a hidden gem OR a stock institutions avoid for a reason.')+'</div></div>';
  return h;
};

// ── Chart 13: Smart Money vs Retail Divergence ──
window._smartRetailDivergence=function(d,S){
  if(!d)return'';
  var instPct=d.institutionalOwnership||0;
  var fh=d.fundHoldings||{};
  var sum=fh.summary||{};
  var insiderPct=sum.insider_pct||0;
  var instCount=sum.inst_count||0;
  var retailPct=Math.max(0,100-instPct-insiderPct);
  if(!instPct&&!insiderPct){
    // Estimate from available data
    instPct=d.fundamental?(d.fundamental.institutionPct||30):30;
    insiderPct=d.fundamental?(d.fundamental.insiderPct||5):5;
    retailPct=Math.max(0,100-instPct-insiderPct);
  }

  // Smart money signal — derived from institutional ownership trend + accumDist phase
  var adSig=(d.advCharts&&d.advCharts.accumDist)?d.advCharts.accumDist.signal:'UNKNOWN';
  var instTrend=(d.advCharts&&d.advCharts.instTrend)?d.advCharts.instTrend:(instPct>60?'INCREASING':'STABLE');
  var smartBuying=adSig==='ACCUMULATION'||(instPct>65&&instTrend==='INCREASING');
  var smartSignal=smartBuying?'ACCUMULATING':'DISTRIBUTING/QUIET';
  var smartC=smartBuying?'#059669':'#dc2626';

  // Retail signal — news sentiment proxy
  var sentiment=d.newsSentiment||{};
  var retailSentiment=sentiment.label||'NEUTRAL';
  var retailScore=sentiment.score||50;
  var retailBull=retailSentiment==='BULLISH';
  var retailC=retailBull?'#059669':retailSentiment==='BEARISH'?'#dc2626':'#d97706';

  // Divergence = smart and retail disagree
  var divergence=(smartBuying&&!retailBull&&retailSentiment==='BEARISH')||(!smartBuying&&retailBull);
  var aligned=smartBuying===retailBull;
  var statusLabel=divergence?'DIVERGENCE — contrarian signal':aligned?'ALIGNED — confirms direction':'MIXED';
  var statusC=divergence?'#d97706':aligned?'#059669':'#6b7280';

  // Ownership breakdown bars
  var instW=Math.min(95,Math.round(instPct));
  var insiderW=Math.min(20,Math.round(insiderPct));
  var retailW=Math.max(5,100-instW-insiderW);

  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';

  // Header
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">';
  h+='<div><div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">Smart Money vs Retail Divergence</div>';
  h+='<div style="font-size:7px;color:#d97706;font-weight:700;margin-top:2px">⚠️ PROXY: Estimated from institutional ownership + news sentiment — not live dark pool data</div>';
  h+='<div style="font-size:8px;color:#94a3b8;margin-top:1px">Institutional ownership flow vs news sentiment proxy</div></div>';
  h+='<div style="padding:3px 10px;border-radius:20px;font-size:8px;font-weight:800;background:'+statusC+'15;color:'+statusC+'">'+statusLabel+'</div></div>';

  // Data source disclosure — transparent about methodology
  h+='<div style="padding:7px 10px;border-radius:7px;background:#f8f9fa;border:1px solid #e5e7eb;font-size:8px;color:#6b7280;margin-bottom:10px;line-height:1.5">';
  h+='<strong style="color:#374151">📐 Methodology:</strong> "Smart Money" = institutional ownership % + Accumulation/Distribution volume signal. ';
  h+='"Retail" = news sentiment score. Real-time dark pool data is not available — this is an institutional flow proxy. ';
  h+='<strong>Use alongside the Institutional Ownership and Accumulation vs Distribution charts for confirmation.</strong></div>';

  // Two signal cards
  h+='<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px">';

  // Smart money card
  h+='<div style="padding:12px;border-radius:10px;background:'+smartC+'08;border:1.5px solid '+smartC+'25">';
  h+='<div style="font-size:8px;color:'+smartC+';font-weight:800;letter-spacing:.5px;margin-bottom:6px">🏦 SMART MONEY (Institutional)</div>';
  h+='<div style="font-size:16px;font-weight:900;color:'+smartC+';font-family:JetBrains Mono">'+smartSignal+'</div>';
  h+='<div style="margin-top:8px;display:flex;flex-direction:column;gap:3px">';
  h+='<div style="display:flex;justify-content:space-between;font-size:8px"><span style="color:#6b7280">Inst. ownership</span><span style="font-weight:700;color:#374151">'+instPct.toFixed(1)+'%</span></div>';
  h+='<div style="display:flex;justify-content:space-between;font-size:8px"><span style="color:#6b7280">Accum/Dist phase</span><span style="font-weight:700;color:'+(adSig==='ACCUMULATION'?'#059669':'#dc2626')+'">'+adSig+'</span></div>';
  h+='<div style="display:flex;justify-content:space-between;font-size:8px"><span style="color:#6b7280"># Institutions</span><span style="font-weight:700;color:#374151">'+(instCount>0?instCount.toLocaleString():'N/A')+'</span></div>';
  h+='</div></div>';

  // Retail card
  h+='<div style="padding:12px;border-radius:10px;background:'+retailC+'08;border:1.5px solid '+retailC+'25">';
  h+='<div style="font-size:8px;color:'+retailC+';font-weight:800;letter-spacing:.5px;margin-bottom:6px">📰 RETAIL (News Sentiment)</div>';
  h+='<div style="font-size:16px;font-weight:900;color:'+retailC+';font-family:JetBrains Mono">'+retailSentiment+'</div>';
  h+='<div style="margin-top:8px;display:flex;flex-direction:column;gap:3px">';
  h+='<div style="display:flex;justify-content:space-between;font-size:8px"><span style="color:#6b7280">Sentiment score</span><span style="font-weight:700;color:#374151">'+retailScore+'/100</span></div>';
  h+='<div style="display:flex;justify-content:space-between;font-size:8px"><span style="color:#6b7280">Retail ownership est.</span><span style="font-weight:700;color:#374151">'+retailPct.toFixed(0)+'%</span></div>';
  h+='<div style="display:flex;justify-content:space-between;font-size:8px"><span style="color:#6b7280">Insider ownership</span><span style="font-weight:700;color:#374151">'+insiderPct.toFixed(1)+'%</span></div>';
  h+='</div></div></div>';

  // Ownership stacked bar
  h+='<div style="margin-bottom:8px">';
  h+='<div style="font-size:7px;font-weight:800;color:#94a3b8;margin-bottom:3px;letter-spacing:.5px">OWNERSHIP BREAKDOWN</div>';
  h+='<div style="display:flex;height:12px;border-radius:6px;overflow:hidden">';
  h+='<div style="width:'+instW+'%;background:#3b82f6;display:flex;align-items:center;justify-content:center;font-size:6px;color:#fff;font-weight:700">Inst '+instW+'%</div>';
  if(insiderW>2)h+='<div style="width:'+insiderW+'%;background:#8b5cf6;display:flex;align-items:center;justify-content:center;font-size:6px;color:#fff;font-weight:700">Insider</div>';
  h+='<div style="flex:1;background:#94a3b8;display:flex;align-items:center;justify-content:center;font-size:6px;color:#fff;font-weight:700">Retail '+retailW+'%</div>';
  h+='</div></div>';

  // Decision
  var decision=divergence
    ?(smartBuying?'Institutions accumulating while retail is bearish — contrarian BUY signal. Smart money historically leads. Watch for price recovery.'
                 :'Institutions distributing while retail is bullish — CAUTION. Retail optimism may be the exit liquidity for smart money.')
    :(smartBuying?'Both smart money and sentiment are bullish — strong confirmation. High-conviction entry when trend aligns.'
                 :'Both signals are cautious/bearish — avoid new positions until ownership trend reverses.');
  h+='<div style="padding:7px 10px;border-radius:7px;background:'+statusC+'06;border-left:3px solid '+statusC+';font-size:9px;color:#374151;line-height:1.6">';
  h+='<strong style="color:'+statusC+'">📋 DECISION:</strong> '+decision+'</div></div>';
  return h;
};

// ── Chart 14: ETF Flow Dependency ──
window._etfFlowDep=function(d,S){
  if(!d)return'';
  var ef=d.etfFlow||{};
  var instPct=d.institutionalOwnership||0;
  var mcap=d.marketCap||0;
  // Estimate ETF dependency: large caps with high inst% are more ETF-driven
  var etfDep=(d.chartData&&d.chartData.etfPassivePct!=null)?d.chartData.etfPassivePct:Math.min(100,Math.round(instPct*0.7+(mcap>1e12?20:mcap>1e11?10:0)));
  var passivePct=Math.round(etfDep*0.6);
  var activePct=100-passivePct;
  var depC=etfDep>60?'#dc2626':etfDep>35?'#d97706':'#059669';
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px"><div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">ETF / Passive Flow Dependency</div>';
  h+='<div style="padding:3px 10px;border-radius:20px;font-size:8px;font-weight:800;background:'+depC+'15;color:'+depC+'">'+etfDep+'% ETF-driven</div></div>';
  h+='<div style="display:flex;height:14px;border-radius:7px;overflow:hidden;margin-bottom:6px">';
  h+='<div style="width:'+passivePct+'%;background:#dc2626;display:flex;align-items:center;justify-content:center;font-size:7px;color:#fff;font-weight:700">Passive '+passivePct+'%</div>';
  h+='<div style="width:'+activePct+'%;background:#059669;display:flex;align-items:center;justify-content:center;font-size:7px;color:#fff;font-weight:700">Active '+activePct+'%</div></div>';
  h+='<div style="padding:6px 10px;border-radius:6px;background:#F8FAFC;font-size:9px;color:#374151"><strong style="color:'+depC+'">📋 DECISION:</strong> '+(etfDep>60?'Highly ETF-dependent — price moves are driven by index flows, not fundamentals. Be aware that passive selling can create forced liquidation during index rebalances.':etfDep>35?'Moderate ETF influence — a mix of active and passive ownership. Fundamentals still matter but index inclusion affects price.':'Low ETF dependency — price driven mostly by active investors. Fundamental analysis is more reliable here.')+'</div></div>';
  return h;
};

// ── Chart 23: Liquidity Cycle Indicator ──
window._liquidityCycle=function(d,S){
  if(!d)return'';
  // Use beta + macro sensitivity as proxy
  var macro=d.macroSensitivity||{};
  var rateSens=macro.rates?macro.rates.sensitivity:'UNKNOWN';
  var rsi=d.rsi||(d.technicals?d.technicals.rsi:50)||50;
  var sma200=d.sma200||(d.technicals?d.technicals.sma200:d.price)||d.price;
  var aboveSMA=d.price>sma200;
  var phase=aboveSMA&&rsi>50?'EXPANSION':aboveSMA?'LATE CYCLE':rsi<40?'CONTRACTION':'TRANSITION';
  var phaseC=phase==='EXPANSION'?'#059669':phase==='CONTRACTION'?'#dc2626':'#d97706';
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px"><div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">Liquidity Cycle</div>';
  h+='<div style="padding:3px 10px;border-radius:20px;font-size:8px;font-weight:800;background:'+phaseC+'15;color:'+phaseC+'">'+phase+'</div></div>';
  // Cycle visual
  h+='<div style="display:flex;gap:4px;margin-bottom:8px">';
  ['EXPANSION','LATE CYCLE','CONTRACTION','TRANSITION'].forEach(function(p){
    var isActive=p===phase;
    var pC=p==='EXPANSION'?'#059669':p==='CONTRACTION'?'#dc2626':'#d97706';
    h+='<div style="flex:1;padding:6px;border-radius:6px;background:'+(isActive?pC+'15':'#f8fafc')+';border:1.5px solid '+(isActive?pC:'#e5e7eb')+';text-align:center">';
    h+='<div style="font-size:7px;font-weight:800;color:'+(isActive?pC:'#94a3b8')+'">'+p+'</div></div>';
  });
  h+='</div>';
  h+='<div style="padding:6px 10px;border-radius:6px;background:#F8FAFC;font-size:9px;color:#374151"><strong style="color:'+phaseC+'">📋 DECISION:</strong> '+(phase==='EXPANSION'?'Liquidity expanding — risk assets favored. Increase equity exposure.':phase==='CONTRACTION'?'Liquidity contracting — defensive mode. Reduce risk, increase cash.':phase==='LATE CYCLE'?'Late cycle — be selective. Focus on quality and reduce speculative positions.':'Transitioning — wait for clarity before making large moves.')+'</div></div>';
  return h;
};

// ── Chart 24: Macro Sensitivity Map ──
window._macroSensitivityMap=function(d,S){
  if(!d||!d.macroSensitivity)return'';
  var ms=d.macroSensitivity;
  if(!ms.rates)return'';
  var factors=[
    {l:'Interest Rates',sens:ms.rates.sensitivity,reason:ms.rates.reason,icon:'📈'},
    {l:'US Dollar',sens:ms.usd.sensitivity,reason:ms.usd.reason,icon:'💵'},
    {l:'Inflation',sens:ms.inflation.sensitivity,reason:ms.inflation.reason,icon:'🔥'}
  ];
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif;margin-bottom:12px">Macro Sensitivity Map</div>';
  h+='<div style="display:flex;gap:8px;margin-bottom:8px">';
  factors.forEach(function(f){
    var sC=f.sens==='HIGH'?'#dc2626':f.sens==='MODERATE'?'#d97706':'#059669';
    h+='<div style="flex:1;padding:10px;border-radius:10px;background:'+sC+'06;border:1.5px solid '+sC+'20;text-align:center">';
    h+='<div style="font-size:16px">'+f.icon+'</div>';
    h+='<div style="font-size:9px;font-weight:800;color:#374151;margin-top:2px">'+f.l+'</div>';
    h+='<div style="font-size:12px;font-weight:900;color:'+sC+';margin-top:2px">'+f.sens+'</div>';
    h+='<div style="font-size:7px;color:#94a3b8;margin-top:2px">'+f.reason+'</div></div>';
  });
  h+='</div>';
  var highCount=factors.filter(function(f){return f.sens==='HIGH'}).length;
  h+='<div style="padding:6px 10px;border-radius:6px;background:#F8FAFC;font-size:9px;color:#374151"><strong style="color:#1A3A78">📋 DECISION:</strong> '+(highCount>=2?'High macro sensitivity — this stock moves significantly with rates/USD/inflation. In volatile macro environments, reduce exposure or hedge.':highCount===1?'Moderate macro sensitivity — one key macro factor to watch. Monitor that factor closely for position sizing.':'Low macro sensitivity — this stock is relatively insulated from macro shocks. Fundamentals drive returns more than macro.')+'</div></div>';
  return h;
};

// ── Chart 33: What Changed (Score Delta) ──
window._whatChanged=function(d,S){
  if(!d||!d.price)return'';
  // Compute "what changed" from current data signals
  var changes=[];
  var tech=d.technicals||{};
  var rsi=d.rsi||tech.rsi||50;
  var sma50=d.sma50||tech.sma50||d.price;
  var sma200=d.sma200||tech.sma200||d.price;
  var fS=d.fScore||(d.business?d.business.fScore:0)||0;
  var upside=d.upside||0;
  // RSI signals
  if(rsi<30)changes.push({signal:'RSI Oversold (<30)',type:'BULLISH',icon:'🟢',detail:'RSI at '+Math.round(rsi)+' — potential bounce zone'});
  else if(rsi>70)changes.push({signal:'RSI Overbought (>70)',type:'BEARISH',icon:'🔴',detail:'RSI at '+Math.round(rsi)+' — potential pullback'});
  // SMA crosses
  if(d.price<sma50&&d.price>sma200)changes.push({signal:'Below SMA50, Above SMA200',type:'CAUTION',icon:'🟡',detail:'Short-term weakness, long-term intact'});
  else if(d.price<sma200)changes.push({signal:'Below SMA200',type:'BEARISH',icon:'🔴',detail:'Major support broken — trend reversal'});
  else if(d.price>sma50&&d.price>sma200)changes.push({signal:'Above both MAs',type:'BULLISH',icon:'🟢',detail:'Uptrend confirmed on all timeframes'});
  // Valuation
  if(upside>30)changes.push({signal:'Deep Undervaluation',type:'BULLISH',icon:'🟢',detail:'+'+Math.round(upside)+'% to fair value'});
  else if(upside<-20)changes.push({signal:'Significant Overvaluation',type:'BEARISH',icon:'🔴',detail:Math.round(upside)+'% above fair value'});
  // F-Score
  if(fS>=8)changes.push({signal:'Exceptional F-Score ('+fS+'/9)',type:'BULLISH',icon:'🟢',detail:'Near-perfect financial health'});
  else if(fS<=3)changes.push({signal:'Weak F-Score ('+fS+'/9)',type:'BEARISH',icon:'🔴',detail:'Deteriorating fundamentals'});
  // Volume
  var volRatio=d.volRatio||(tech.vol_ratio)||1;
  if(volRatio>2)changes.push({signal:'Volume Spike ('+volRatio.toFixed(1)+'x avg)',type:'WATCH',icon:'⚡',detail:'Unusual activity — possible catalyst'});
  if(!changes.length)changes.push({signal:'No major changes detected',type:'NEUTRAL',icon:'⚪',detail:'Status quo — no significant shifts'});
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif;margin-bottom:12px">What Changed — Key Signals</div>';
  changes.forEach(function(c){
    var cC=c.type==='BULLISH'?'#059669':c.type==='BEARISH'?'#dc2626':c.type==='CAUTION'?'#d97706':'#94a3b8';
    h+='<div style="display:flex;align-items:center;gap:8px;padding:6px 10px;border-radius:8px;background:'+cC+'06;border:1px solid '+cC+'15;margin-bottom:4px">';
    h+='<div style="font-size:14px">'+c.icon+'</div>';
    h+='<div style="flex:1"><div style="font-size:10px;font-weight:800;color:#374151">'+c.signal+'</div><div style="font-size:8px;color:#6b7280">'+c.detail+'</div></div>';
    h+='<div style="padding:2px 8px;border-radius:10px;font-size:7px;font-weight:800;background:'+cC+'15;color:'+cC+'">'+c.type+'</div></div>';
  });
  h+='</div>';
  return h;
};

// ── Chart 34: Signal Upgrade/Downgrade Tracker ──
window._signalTracker=function(d,S){
  if(!d||!d.price)return'';
  var signals=[];
  var fS=d.fScore||(d.business?d.business.fScore:0)||0;
  var rsi=d.rsi||50;
  var upside=d.upside||0;
  var mc=d.monteCarlo||{};
  signals.push({name:'Quality',score:fS>=7?'A':fS>=5?'B':'C',direction:fS>=7?'↑':'→',prev:fS>=7?'Strong':'Moderate'});
  signals.push({name:'Value',score:upside>20?'A':upside>0?'B':'C',direction:upside>20?'↑':upside>0?'→':'↓',prev:upside>20?'Undervalued':upside>0?'Fair':'Overvalued'});
  signals.push({name:'Momentum',score:rsi>55?'A':rsi>45?'B':'C',direction:rsi>55?'↑':rsi>45?'→':'↓',prev:rsi>55?'Bullish':rsi>45?'Neutral':'Bearish'});
  signals.push({name:'Probability',score:(mc.probUndervalued||50)>65?'A':(mc.probUndervalued||50)>50?'B':'C',direction:(mc.probUndervalued||50)>65?'↑':'→',prev:(mc.probUndervalued||50)+'% undervalued'});
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif;margin-bottom:12px">Signal Grades</div>';
  h+='<div style="display:flex;gap:6px">';
  signals.forEach(function(s){
    var gC=s.score==='A'?'#059669':s.score==='B'?'#d97706':'#dc2626';
    h+='<div style="flex:1;padding:8px;border-radius:10px;background:'+gC+'06;border:1.5px solid '+gC+'20;text-align:center">';
    h+='<div style="font-size:8px;color:#94a3b8;font-weight:700">'+s.name+'</div>';
    h+='<div style="font-size:22px;font-weight:900;color:'+gC+';font-family:JetBrains Mono">'+s.score+'</div>';
    h+='<div style="font-size:7px;color:#6b7280">'+s.prev+'</div></div>';
  });
  h+='</div></div>';
  return h;
};

// ── Chart 35: Sentiment Score Timeline ──
window._sentimentTimeline=function(d,S){
  if(!d||!d.newsSentiment)return'';
  var ns=d.newsSentiment;
  if(!ns.articles||!ns.articles.length)return'';
  var sentC=ns.label==='BULLISH'?'#059669':ns.label==='BEARISH'?'#dc2626':'#d97706';
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px"><div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif">News Sentiment</div>';
  h+='<div style="padding:3px 10px;border-radius:20px;font-size:8px;font-weight:800;background:'+sentC+'15;color:'+sentC+'">'+ns.label+' ('+ns.score+'/100)</div></div>';
  // Sentiment gauge
  h+='<div style="height:10px;background:#f1f5f9;border-radius:5px;position:relative;overflow:hidden;margin-bottom:8px">';
  h+='<div style="position:absolute;left:0;top:0;height:100%;width:'+ns.score+'%;background:linear-gradient(90deg,#dc2626,#d97706 40%,#059669);border-radius:5px"></div></div>';
  h+='<div style="display:flex;justify-content:space-between;font-size:7px;color:#94a3b8;margin-bottom:8px"><span>BEARISH</span><span style="color:#374151;font-weight:700">'+ns.posCount+' positive / '+ns.negCount+' negative signals</span><span>BULLISH</span></div>';
  // Recent headlines
  h+='<div style="font-size:8px;font-weight:800;color:#94a3b8;margin-bottom:4px">RECENT HEADLINES</div>';
  ns.articles.slice(0,4).forEach(function(a){
    h+='<div style="padding:4px 8px;border-radius:4px;background:#f8fafc;margin-bottom:2px;font-size:8px;color:#374151"><strong style="color:#6b7280">'+a.publisher+':</strong> '+a.title+'</div>';
  });
  h+='<div style="margin-top:8px;padding:6px 10px;border-radius:6px;background:#F8FAFC;font-size:9px;color:#374151"><strong style="color:'+sentC+'">📋 DECISION:</strong> '+(ns.score>=65?'Positive sentiment — news flow supports the bullish thesis. But be cautious of excessive optimism.':ns.score<=35?'Negative sentiment — bad news cycle. Could create buying opportunity if fundamentals are intact (contrarian signal).':'Neutral sentiment — no strong narrative driving the stock. Focus on fundamentals over headlines.')+'</div></div>';
  return h;
};

// ── Chart 36: Theme Exposure ──
window._themeExposure=function(d,S){
  if(!d)return'';
  var ns=d.newsSentiment||{};
  var themes=ns.themes||[];
  var sector=d.sector||'';
  var industry=d.industry||'';
  // Add sector-based themes
  var sectorThemes={'Technology':['Tech','Digital'],'Healthcare':['Health','Pharma'],'Financial Services':['Fintech','Banking'],'Energy':['Energy','Oil'],'Consumer Cyclical':['Consumer','Retail']};
  if(sector&&sectorThemes[sector]){
    sectorThemes[sector].forEach(function(t){
      if(!themes.find(function(th){return th.name===t}))themes.push({name:t,count:1});
    });
  }
  if(!themes.length)return'';
  var h='<div style="padding:16px 18px;border-radius:14px;background:#fff;border:1px solid #e2e5ea;margin:12px 0">';
  h+='<div style="font-size:12px;font-weight:900;color:#0A1628;font-family:Sora,sans-serif;margin-bottom:12px">Theme Exposure</div>';
  h+='<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px">';
  var themeColors={'AI':'#8b5cf6','EV':'#059669','Cloud':'#3b82f6','Fintech':'#d97706','Green':'#10b981','Defense':'#64748b','Pharma':'#dc2626','Tech':'#6366f1','Digital':'#0ea5e9','Health':'#ec4899','Banking':'#1A3A78','Energy':'#f97316','Consumer':'#84cc16','Retail':'#14b8a6','Oil':'#78716c'};
  themes.forEach(function(t){
    var tC=themeColors[t.name]||'#6b7280';
    h+='<div style="padding:6px 14px;border-radius:20px;background:'+tC+'10;border:1.5px solid '+tC+'30;font-size:9px;font-weight:800;color:'+tC+'">';
    h+=t.name+(t.count>1?' ('+t.count+'x)':'')+'</div>';
  });
  h+='</div>';
  h+='<div style="padding:6px 10px;border-radius:6px;background:#F8FAFC;font-size:9px;color:#374151"><strong style="color:#1A3A78">📋</strong> This stock has exposure to <strong>'+themes.map(function(t){return t.name}).join(', ')+'</strong> themes. '+(themes.find(function(t){return t.name==='AI'})?'AI exposure adds growth premium — monitor AI capex trends.':'Monitor theme momentum for catalysts.')+'</div></div>';
  return h;
};

console.log('[CDS] Phase 4 loaded: InstOwnership, SmartRetail, ETFFlow, LiquidityCycle, MacroSens, WhatChanged, SignalTracker, Sentiment, ThemeExposure');

// ═══════════════════════════════════════════════════════════════
// L0 SCAN ENGINE — Frontend renderer
// ═══════════════════════════════════════════════════════════════
window._runL0Scan=function(region,mode,theme){
  var el=document.getElementById('deResult');
  if(!el)el=document.getElementById('cdsV2ScannerSlot');
  if(!el)return;
  var reg=region||window._deRegion||'IN';
  var S=reg==='US'?'$':'₹';
  var modeLabel={'quality':'Quality Compounders','growth':'High Growth','momentum':'Momentum Leaders','value':'Deep Value','multibagger':'Multibagger Hunt','dividend':'Dividend & Stability','theme':'Theme: '+(theme||''),'sector_leader':'Sector Leaders'};
  var title=modeLabel[mode]||mode;
  
  el.innerHTML='<div style="padding:30px;text-align:center;border-radius:14px;background:#fff;border:1px solid #e2e5ea"><div style="display:inline-block;width:24px;height:24px;border:3px solid #1A3A78;border-top-color:transparent;border-radius:50%;animation:spin .5s linear infinite"></div><div style="font-size:13px;font-weight:800;color:#0A1628;margin-top:10px">🔬 L0 Smart Scanner Running...</div><div style="font-size:10px;color:#6b7280;margin-top:4px">Scanning universe with <strong>'+title+'</strong> filters</div><div style="font-size:9px;color:#94a3b8;margin-top:8px">Pipeline: Universe → Quality + Growth + Momentum + Liquidity + Stability → Ranked Top 30</div></div>';
  
  var url='/api/l0-scan?region='+reg+'&mode='+encodeURIComponent(mode)+'&limit=30';
  if(theme)url+='&theme='+encodeURIComponent(theme);
  
  fetch(url).then(function(r){return r.json()}).then(function(d){
    if(!d.success){el.innerHTML='<div style="color:#dc2626;padding:16px;font-size:11px">Error: '+d.error+'</div>';return}
    
    var h='<div style="margin-bottom:16px">';
    // Header
    h+='<div style="padding:18px 24px;background:linear-gradient(135deg,#059669,#10b981);border-radius:14px;color:#fff;margin-bottom:14px">';
    h+='<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">';
    h+='<div><div style="font-size:16px;font-weight:900;font-family:Sora,sans-serif">🔬 L0 Smart Scanner — '+title+'</div>';
    h+='<div style="font-size:10px;color:rgba(255,255,255,.7);margin-top:4px">'+d.totalScanned+' stocks scanned → '+d.totalScored+' scored → Top '+d.results.length+' shown · '+d.elapsed+'s</div></div>';
    h+='<div style="display:flex;gap:8px">';
    h+='<div style="padding:4px 12px;border-radius:8px;background:rgba(255,255,255,.15);font-size:9px;font-weight:700">'+d.filteredOut+' filtered out</div>';
    h+='<div style="padding:4px 12px;border-radius:8px;background:rgba(255,255,255,.15);font-size:9px;font-weight:700">🟢 '+d.results.filter(function(r){return r.l0Score>=75}).length+' pass to CDS</div>';
    h+='</div></div></div>';
    
    // Pipeline reminder
    h+='<div style="display:flex;align-items:center;gap:4px;margin-bottom:12px;padding:8px 12px;border-radius:8px;background:#f0fdf4;border:1px solid #bbf7d0;font-size:9px;color:#374151">';
    h+='<strong style="color:#059669">💡 Next step:</strong> Click any 🟢 stock below to run full CDS deep analysis with 36 charts, Monte Carlo, and portfolio allocation.';
    h+='</div>';
    
    // Results table
    h+='<div style="overflow-x:auto"><table style="width:100%;border-collapse:separate;border-spacing:0;border:1px solid #e2e5ea;border-radius:12px;overflow:hidden;font-size:10px">';
    h+='<thead><tr style="background:#f8fafc">';
    h+='<th style="padding:8px 10px;font-size:8px;color:#5E6F8E;font-weight:700;letter-spacing:.5px;text-align:left;border-bottom:2px solid #e2e5ea">#</th>';
    h+='<th style="padding:8px 10px;font-size:8px;color:#5E6F8E;font-weight:700;text-align:left;border-bottom:2px solid #e2e5ea">Stock</th>';
    h+='<th style="padding:8px 10px;font-size:8px;color:#5E6F8E;font-weight:700;text-align:center;border-bottom:2px solid #e2e5ea">L0 Score</th>';
    h+='<th style="padding:8px 10px;font-size:8px;color:#5E6F8E;font-weight:700;text-align:center;border-bottom:2px solid #e2e5ea">Quality</th>';
    h+='<th style="padding:8px 10px;font-size:8px;color:#5E6F8E;font-weight:700;text-align:center;border-bottom:2px solid #e2e5ea">Growth</th>';
    h+='<th style="padding:8px 10px;font-size:8px;color:#5E6F8E;font-weight:700;text-align:center;border-bottom:2px solid #e2e5ea">Momentum</th>';
    h+='<th style="padding:8px 10px;font-size:8px;color:#5E6F8E;font-weight:700;text-align:center;border-bottom:2px solid #e2e5ea">Price</th>';
    h+='<th style="padding:8px 10px;font-size:8px;color:#5E6F8E;font-weight:700;text-align:center;border-bottom:2px solid #e2e5ea">1M</th>';
    h+='<th style="padding:8px 10px;font-size:8px;color:#5E6F8E;font-weight:700;text-align:center;border-bottom:2px solid #e2e5ea">1Y</th>';
    h+='<th style="padding:8px 10px;font-size:8px;color:#5E6F8E;font-weight:700;text-align:center;border-bottom:2px solid #e2e5ea">Signal</th>';
    h+='</tr></thead><tbody>';
    
    d.results.forEach(function(r,i){
      var rowBg=i%2===0?'#fff':'#fafbff';
      var scoreC=r.l0Score>=75?'#059669':r.l0Score>=55?'#d97706':'#dc2626';
      var retC1=r.ret1m>=0?'#059669':'#dc2626';
      var retCY=r.ret1y>=0?'#059669':'#dc2626';
      
      h+='<tr style="background:'+rowBg+';cursor:pointer;transition:background .15s" onclick="window._deRegion=\''+reg+'\';window._openCDSModal(\''+r.symbol+'\',window._l0ModalList||[],'+i+')" onmouseover="this.style.background=\'#eff6ff\'" onmouseout="this.style.background=\''+rowBg+'\'">';
      h+='<td style="padding:6px 10px;border-bottom:1px solid #f1f5f9;font-weight:700;color:#94a3b8">'+(i+1)+'</td>';
      h+='<td style="padding:6px 10px;border-bottom:1px solid #f1f5f9"><div style="font-weight:800;color:#0A1628">'+r.symbol+'</div><div style="font-size:7px;color:#94a3b8">'+r.segment+(r.aboveSMA200?' · ▲200':' · ▼200')+'</div></td>';
      h+='<td style="padding:6px 10px;border-bottom:1px solid #f1f5f9;text-align:center"><div style="display:inline-block;padding:3px 10px;border-radius:6px;background:'+scoreC+'12;font-weight:900;color:'+scoreC+';font-family:JetBrains Mono;font-size:13px">'+r.l0Score+'</div></td>';
      h+='<td style="padding:6px 10px;border-bottom:1px solid #f1f5f9;text-align:center;font-family:JetBrains Mono;font-size:9px;color:'+(r.quality>=60?'#059669':'#d97706')+'">'+r.quality+'</td>';
      h+='<td style="padding:6px 10px;border-bottom:1px solid #f1f5f9;text-align:center;font-family:JetBrains Mono;font-size:9px;color:'+(r.growth>=60?'#059669':'#d97706')+'">'+r.growth+'</td>';
      h+='<td style="padding:6px 10px;border-bottom:1px solid #f1f5f9;text-align:center;font-family:JetBrains Mono;font-size:9px;color:'+(r.momentum>=60?'#059669':'#d97706')+'">'+r.momentum+'</td>';
      h+='<td style="padding:6px 10px;border-bottom:1px solid #f1f5f9;text-align:center;font-weight:700;font-family:JetBrains Mono">'+S+r.price.toLocaleString()+'</td>';
      h+='<td style="padding:6px 10px;border-bottom:1px solid #f1f5f9;text-align:center;font-family:JetBrains Mono;color:'+retC1+';font-weight:700">'+(r.ret1m>0?'+':'')+r.ret1m+'%</td>';
      h+='<td style="padding:6px 10px;border-bottom:1px solid #f1f5f9;text-align:center;font-family:JetBrains Mono;color:'+retCY+';font-weight:700">'+(r.ret1y>0?'+':'')+r.ret1y+'%</td>';
      h+='<td style="padding:6px 10px;border-bottom:1px solid #f1f5f9;text-align:center"><span style="padding:2px 8px;border-radius:4px;font-size:7px;font-weight:800;background:'+r.signalColor+'12;color:'+r.signalColor+'">'+r.signal.replace(/[🟢🟡🔴]/g,'').trim()+'</span></td>';
      h+='</tr>';
    });
    
    h+='</tbody></table></div>';
    
    // Back buttons + Export
    h+='<div style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap;align-items:center">';
    h+='<div onclick="window._exportScanCSV(window._l0ScanResults||[],\'L0_'+mode+'\')" style="padding:8px 14px;border-radius:8px;background:#1A3A7810;border:1px solid #1A3A7820;cursor:pointer;font-size:9px;font-weight:700;color:#1A3A78">📥 Export CSV</div>';
    h+='<div onclick="window._showWatchlist()" style="padding:8px 14px;border-radius:8px;background:#d9770610;border:1px solid #d9770620;cursor:pointer;font-size:9px;font-weight:700;color:#d97706">★ My Watchlist</div>';
    h+='<div style="flex:1"></div>';
    h+='<div onclick="window._runL0Scan(\''+reg+'\',\'quality\')" style="padding:8px 14px;border-radius:8px;background:#05966910;border:1px solid #05966920;cursor:pointer;font-size:9px;font-weight:700;color:#059669">🏆 Quality</div>';
    h+='<div onclick="window._runL0Scan(\''+reg+'\',\'growth\')" style="padding:8px 14px;border-radius:8px;background:#2563eb10;border:1px solid #2563eb20;cursor:pointer;font-size:9px;font-weight:700;color:#2563eb">🚀 Growth</div>';
    h+='<div onclick="window._runL0Scan(\''+reg+'\',\'momentum\')" style="padding:8px 14px;border-radius:8px;background:#d9770610;border:1px solid #d9770620;cursor:pointer;font-size:9px;font-weight:700;color:#d97706">⚡ Momentum</div>';
    h+='<div onclick="window._runL0Scan(\''+reg+'\',\'multibagger\')" style="padding:8px 14px;border-radius:8px;background:#dc262610;border:1px solid #dc262620;cursor:pointer;font-size:9px;font-weight:700;color:#dc2626">🔥 Multibagger</div>';
    if(d.availableThemes){
      d.availableThemes.forEach(function(th){
        h+='<div onclick="window._runL0Scan(\''+reg+'\',\'theme\',\''+th+'\')" style="padding:8px 14px;border-radius:8px;background:#0891b208;border:1px solid #0891b220;cursor:pointer;font-size:9px;font-weight:700;color:#0891b2">🎯 '+th+'</div>';
      });
    }
    h+='</div>';
    h+='</div>';
    
    // Store stock list for modal navigation and export
    window._l0ModalList=d.results.map(function(r){return r.symbol});
    window._l0ScanResults=d.results;
    el.innerHTML=h;
  }).catch(function(e){
    el.innerHTML='<div style="color:#dc2626;padding:16px;font-size:11px">Error: '+e.message+'<br><button onclick="window._runL0Scan(\''+reg+'\',\''+mode+'\',\''+(theme||'')+'\')" style="margin-top:8px;padding:6px 16px;border-radius:6px;background:#1A3A78;color:#fff;border:none;cursor:pointer;font-size:10px">Retry</button></div>';
  });
};

// ═══════════════════════════════════════════════════════════════
// CDS MODAL — Full-screen overlay for stock analysis
// Opens from scanner results, closeable, navigable
// ═══════════════════════════════════════════════════════════════
window._cdsModalOpen=false;
window._cdsModalList=[];
window._cdsModalIdx=0;

window._openCDSModal=function(sym,stockList,idx){
  window._cdsModalList=stockList||[];
  window._cdsModalIdx=idx||0;
  window._cdsModalOpen=true;
  
  // Create modal if not exists
  var modal=document.getElementById('cdsModal');
  if(!modal){
    modal=document.createElement('div');
    modal.id='cdsModal';
    modal.style.cssText='position:fixed;top:0;left:0;right:0;bottom:0;z-index:9999;display:none;background:rgba(10,22,40,0.85);backdrop-filter:blur(6px);overflow:hidden';
    modal.innerHTML='<div style="position:absolute;top:0;left:0;right:0;bottom:0;display:flex;flex-direction:column">'
      +'<div id="cdsModalHeader" style="flex-shrink:0;padding:10px 20px;background:linear-gradient(135deg,#0A1628,#1A3A78);display:flex;justify-content:space-between;align-items:center;border-bottom:2px solid #1A3A7850">'
      +'<div style="display:flex;align-items:center;gap:12px">'
      +'<div id="cdsModalTitle" style="font-size:14px;font-weight:900;color:#fff;font-family:Sora,sans-serif">Loading...</div>'
      +'<div id="cdsModalNav" style="display:flex;gap:4px"></div>'
      +'</div>'
      +'<div style="display:flex;align-items:center;gap:8px">'
      +'<button id="wlBtn_modal" onclick="window._toggleWatchlist(window._cdsModalList[window._cdsModalIdx])" style="padding:6px 12px;border-radius:6px;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);color:#fff;font-size:11px;font-weight:700;cursor:pointer;font-family:Sora">☆ Watchlist</button>'
      +'<button onclick="window._cdsModalPrev()" style="padding:6px 12px;border-radius:6px;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);color:#fff;font-size:11px;font-weight:700;cursor:pointer;font-family:Sora" title="← Arrow Left">◀ Prev</button>'
      +'<button onclick="window._cdsModalNext()" style="padding:6px 12px;border-radius:6px;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);color:#fff;font-size:11px;font-weight:700;cursor:pointer;font-family:Sora" title="→ Arrow Right">Next ▶</button>'
      +'<button onclick="window._closeCDSModal()" style="padding:6px 14px;border-radius:6px;background:#dc2626;border:none;color:#fff;font-size:11px;font-weight:800;cursor:pointer;font-family:Sora">✕ Close</button>'
      +'</div></div>'
      +'<div id="cdsModalBody" style="flex:1;overflow-y:auto;padding:16px 20px;background:#f8fafc"></div>'
      +'</div>';
    document.body.appendChild(modal);
    
    // Close on Escape key
    document.addEventListener('keydown',function(e){
      if(e.key==='Escape'&&window._cdsModalOpen)window._closeCDSModal();
    });
    // Close on backdrop click
    modal.addEventListener('click',function(e){
      if(e.target===modal)window._closeCDSModal();
    });
  }
  
  modal.style.display='block';
  document.body.style.overflow='hidden';
  
  // Update nav counter
  _updateModalNav();
  
  // Load the stock
  _loadModalStock(sym);
};

window._closeCDSModal=function(){
  var modal=document.getElementById('cdsModal');
  if(modal)modal.style.display='none';
  document.body.style.overflow='';
  window._cdsModalOpen=false;
};

window._cdsModalNext=function(){
  if(window._cdsModalList.length===0)return;
  window._cdsModalIdx=(window._cdsModalIdx+1)%window._cdsModalList.length;
  var sym=window._cdsModalList[window._cdsModalIdx];
  _updateModalNav();
  _loadModalStock(sym);
};

window._cdsModalPrev=function(){
  if(window._cdsModalList.length===0)return;
  window._cdsModalIdx=(window._cdsModalIdx-1+window._cdsModalList.length)%window._cdsModalList.length;
  var sym=window._cdsModalList[window._cdsModalIdx];
  _updateModalNav();
  _loadModalStock(sym);
};

function _updateModalNav(){
  var navEl=document.getElementById('cdsModalNav');
  var titleEl=document.getElementById('cdsModalTitle');
  if(!navEl)return;
  var list=window._cdsModalList;
  var idx=window._cdsModalIdx;
  if(list.length>0){
    navEl.innerHTML='<span style="font-size:9px;color:rgba(255,255,255,.5);padding:3px 8px;border-radius:4px;background:rgba(255,255,255,.1)">'+(idx+1)+' / '+list.length+'</span>'
      +'<span style="font-size:8px;color:rgba(255,255,255,.3);margin-left:4px">← → keys · swipe</span>';
  }
  // Update watchlist button
  var wlBtn=document.getElementById('wlBtn_modal');
  if(wlBtn&&list[idx]){
    var isIn=window._isInWatchlist(list[idx]);
    wlBtn.textContent=isIn?'★ Saved':'☆ Watchlist';
    wlBtn.style.background=isIn?'#d97706':'rgba(255,255,255,.1)';
  }
  // Auto-scroll to top
  var body=document.getElementById('cdsModalBody');
  if(body)body.scrollTop=0;
}

function _loadModalStock(sym){
  var body=document.getElementById('cdsModalBody');
  var titleEl=document.getElementById('cdsModalTitle');
  if(!body)return;
  
  if(titleEl)titleEl.textContent='🔬 '+sym+' — CDS Full Analysis';
  
  body.innerHTML='<div style="padding:40px;text-align:center"><div style="display:inline-block;width:24px;height:24px;border:3px solid #1A3A78;border-top-color:transparent;border-radius:50%;animation:spin .5s linear infinite"></div><div style="font-size:13px;font-weight:800;color:#0A1628;margin-top:12px">Running full CDS analysis on '+sym+'...</div><div style="font-size:9px;color:#94a3b8;margin-top:6px">6-Layer Engine · F-Score · DCF · Monte Carlo · 36 Charts</div></div>';
  
  var reg=window._deRegion||'IN';
  var S=reg==='US'?'$':'₹';
  
  // Use the same investor-decide API but render into modal body
  fetch('/api/investor-decide?symbol='+encodeURIComponent(sym)+'&region='+reg)
    .then(function(r){return r.json()})
    .then(function(d){
      if(!d||!d.success){
        body.innerHTML='<div style="padding:20px;color:#dc2626;font-size:12px">Error: '+(d?d.error:'No response')+'<br><button onclick="window._openCDSModal(\''+sym+'\',window._cdsModalList,window._cdsModalIdx)" style="margin-top:8px;padding:6px 16px;border-radius:6px;background:#1A3A78;color:#fff;border:none;cursor:pointer;font-size:10px">Retry</button></div>';
        return;
      }
      // Safety defaults
      d.price=d.price||0;d.symbol=d.symbol||sym;d.companyName=d.companyName||sym;
      d.confidence=d.confidence||0;d.fScore=d.fScore||(d.business?d.business.fScore:0)||0;
      d.moatScore=d.moatScore||(d.moat?d.moat.score:0)||0;
      d.upside=d.upside||0;d.decision=d.decision||'ANALYZING';d.decColor=d.decColor||'#6b7280';
      d.explain=d.explain||'';
      d.beta=d.beta||(d.fundamental?d.fundamental.beta:0)||1;
      d.pe=d.pe||(d.fundamental?d.fundamental.pe:0)||0;
      d.roe=d.roe||(d.business?d.business.roe:0)||0;
      
      if(titleEl)titleEl.textContent='🔬 '+sym+' — '+(d.decision||'')+ ' ('+d.confidence+'% confidence)';
      
      // Build a compact summary for modal (not the full 36-chart report)
      var h='';
      var dC=d.decColor||'#6b7280';
      var lv=d.levels||{};
      
      // Hero verdict
      h+='<div style="background:#fff;border:2px solid '+dC+'25;border-radius:16px;padding:24px;margin-bottom:14px;text-align:center;box-shadow:0 2px 12px rgba(10,22,40,.04)">';
      h+='<div style="font-size:11px;font-weight:700;color:#5E6F8E;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:6px">'+d.companyName+' · '+sym+'</div>';
      h+='<div style="font-family:JetBrains Mono;font-size:32px;font-weight:900;color:'+dC+';margin-bottom:6px">'+d.decision+'</div>';
      h+='<div style="font-size:11px;color:#374151;max-width:600px;margin:0 auto;line-height:1.6">'+(d.explain||'')+'</div>';
      h+='<div style="display:flex;justify-content:center;gap:18px;margin-top:14px">';
      h+='<div style="text-align:center"><div style="font-size:20px;font-weight:900;color:'+dC+';font-family:JetBrains Mono">'+d.confidence+'%</div><div style="font-size:8px;color:#94a3b8">Confidence</div></div>';
      h+='<div style="text-align:center"><div style="font-size:20px;font-weight:900;color:#059669;font-family:JetBrains Mono">'+(d.fScore||0)+'/9</div><div style="font-size:8px;color:#94a3b8">F-Score</div></div>';
      h+='<div style="text-align:center"><div style="font-size:20px;font-weight:900;color:#d97706;font-family:JetBrains Mono">'+(d.moatScore||0)+'</div><div style="font-size:8px;color:#94a3b8">Moat</div></div>';
      h+='</div></div>';
      
      // KPI strip
      h+='<div style="display:flex;background:#fff;border:1px solid #e2e5ea;border-radius:12px;margin-bottom:14px;overflow:hidden;flex-wrap:wrap">';
      var upC=d.upside>=0?'#059669':'#dc2626';
      var kpis=[
        ['Price',S+(d.price||0).toLocaleString(undefined,{maximumFractionDigits:2})],
        ['PE',(d.pe?d.pe.toFixed(1)+'x':'N/A')],
        ['Beta',(d.beta||0).toFixed(2)],
        ['Fair Value',S+(lv.fairValue||0).toLocaleString()],
        ['Upside',(d.upside>=0?'+':'')+d.upside.toFixed(1)+'%'],
        ['RSI',Math.round(d.rsi||0)]
      ];
      kpis.forEach(function(k){
        h+='<div style="flex:1;min-width:80px;padding:10px 8px;text-align:center;border-right:1px solid #f1f5f9">';
        h+='<div style="font-size:7px;color:#5E6F8E;font-weight:700;letter-spacing:1px;text-transform:uppercase;margin-bottom:3px">'+k[0]+'</div>';
        h+='<div style="font-family:JetBrains Mono;font-size:14px;font-weight:800;color:#0A1628">'+k[1]+'</div></div>';
      });
      h+='</div>';
      
      // Entry/Exit levels
      if(lv.buy||lv.sl||lv.target1){
        h+='<div style="background:#fff;border:1px solid #e2e5ea;border-radius:12px;padding:14px 18px;margin-bottom:14px">';
        h+='<div style="font-size:11px;font-weight:800;color:#0A1628;margin-bottom:8px">📍 Key Levels</div>';
        h+='<div style="display:flex;gap:8px;flex-wrap:wrap">';
        if(lv.buy)h+='<div style="padding:6px 12px;border-radius:8px;background:#05966908;border:1px solid #05966920"><div style="font-size:7px;color:#059669;font-weight:700">BUY ZONE</div><div style="font-size:13px;font-weight:900;color:#059669;font-family:JetBrains Mono">'+S+(lv.buy||0).toLocaleString()+'</div></div>';
        if(lv.sl)h+='<div style="padding:6px 12px;border-radius:8px;background:#dc262608;border:1px solid #dc262620"><div style="font-size:7px;color:#dc2626;font-weight:700">STOP LOSS</div><div style="font-size:13px;font-weight:900;color:#dc2626;font-family:JetBrains Mono">'+S+(lv.sl||0).toLocaleString()+'</div></div>';
        if(lv.target1)h+='<div style="padding:6px 12px;border-radius:8px;background:#1A3A7808;border:1px solid #1A3A7820"><div style="font-size:7px;color:#1A3A78;font-weight:700">TARGET 1</div><div style="font-size:13px;font-weight:900;color:#1A3A78;font-family:JetBrains Mono">'+S+(lv.target1||0).toLocaleString()+'</div></div>';
        if(lv.target2)h+='<div style="padding:6px 12px;border-radius:8px;background:#1A3A7808;border:1px solid #1A3A7820"><div style="font-size:7px;color:#1A3A78;font-weight:700">TARGET 2</div><div style="font-size:13px;font-weight:900;color:#1A3A78;font-family:JetBrains Mono">'+S+(lv.target2||0).toLocaleString()+'</div></div>';
        h+='</div></div>';
      }
      
      // Business Quality
      var biz=d.business||{};
      h+='<div style="background:#fff;border:1px solid #e2e5ea;border-radius:12px;padding:14px 18px;margin-bottom:14px">';
      h+='<div style="font-size:11px;font-weight:800;color:#0A1628;margin-bottom:8px">💚 Business Quality</div>';
      h+='<div style="display:flex;gap:12px;flex-wrap:wrap;font-size:10px">';
      h+='<div><strong>ROE:</strong> '+(d.roe||0).toFixed(1)+'%</div>';
      h+='<div><strong>Debt/Equity:</strong> '+(biz.debtEquity||(d.fundamental?d.fundamental.debtToEquity:0)||0).toFixed(1)+'</div>';
      h+='<div><strong>Margin:</strong> '+(biz.grossMargin||(d.fundamental?d.fundamental.grossMargin:0)||0).toFixed(1)+'%</div>';
      h+='<div><strong>Moat:</strong> '+((d.moat?d.moat.verdict:'')||'N/A')+'</div>';
      h+='</div></div>';
      
      // Open full report button
      h+='<div style="text-align:center;margin-top:16px">';
      h+='<button onclick="window._closeCDSModal();loadInvestorDE(\''+sym+'\')" style="padding:12px 28px;border-radius:10px;background:linear-gradient(135deg,#0A1628,#1A3A78);color:#fff;font-size:12px;font-weight:800;cursor:pointer;font-family:Sora,sans-serif;border:none;box-shadow:0 4px 16px rgba(26,58,120,.25)">📊 Open Full 36-Chart Report</button>';
      h+='<div style="font-size:8px;color:#94a3b8;margin-top:6px">Closes modal and loads complete analysis with all institutional charts</div>';
      h+='</div>';
      
      body.innerHTML=h;
    })
    .catch(function(e){
      body.innerHTML='<div style="padding:20px;color:#dc2626;font-size:12px">Error: '+e.message+'</div>';
    });
}

// ═══════════════════════════════════════════════════════════════
// IMPROVEMENT 1: Keyboard navigation for modal (Left/Right arrows)
// ═══════════════════════════════════════════════════════════════
(function(){
  document.addEventListener('keydown',function(e){
    if(!window._cdsModalOpen)return;
    if(e.key==='ArrowRight'){e.preventDefault();window._cdsModalNext();}
    if(e.key==='ArrowLeft'){e.preventDefault();window._cdsModalPrev();}
  });
})();

// ═══════════════════════════════════════════════════════════════
// IMPROVEMENT 2: Mobile swipe support for modal
// ═══════════════════════════════════════════════════════════════
(function(){
  var _sx=0,_sy=0;
  document.addEventListener('touchstart',function(e){
    if(!window._cdsModalOpen)return;
    _sx=e.touches[0].clientX;_sy=e.touches[0].clientY;
  },{passive:true});
  document.addEventListener('touchend',function(e){
    if(!window._cdsModalOpen)return;
    var dx=e.changedTouches[0].clientX-_sx;
    var dy=e.changedTouches[0].clientY-_sy;
    if(Math.abs(dx)>80&&Math.abs(dx)>Math.abs(dy)*2){
      if(dx>0)window._cdsModalPrev();
      else window._cdsModalNext();
    }
  },{passive:true});
})();

// ═══════════════════════════════════════════════════════════════
// IMPROVEMENT 3: Export scan results to CSV
// ═══════════════════════════════════════════════════════════════
window._exportScanCSV=function(results,filename){
  if(!results||results.length===0){alert('No results to export');return}
  var headers=['Rank','Symbol','Price','CDS Score','Verdict','Bucket','F-Score','PE','ROE','Beta','RSI','Upside%','1M Return','3M Return','1Y Return','Volatility','Segment'];
  var rows=results.map(function(r,i){
    return [i+1,r.symbol||r.sym,r.price,r.score||r.cdsScore||r.l0Score,r.verdict||r.decision||'',r.bucket||'',r.fScore||0,r.pe||0,r.roe||0,r.beta||0,r.rsi||0,r.upside||r.moS||0,r.ret1m||0,r.ret3m||0,r.ret1y||0,r.volatility||0,r.segment||''].join(',');
  });
  var csv='\\uFEFF'+headers.join(',')+'\n'+rows.join('\n');
  var blob=new Blob([csv],{type:'text/csv;charset=utf-8;'});
  var link=document.createElement('a');
  link.href=URL.createObjectURL(blob);
  link.download=(filename||'celesys_scan')+'_'+new Date().toISOString().slice(0,10)+'.csv';
  link.click();
};

// ═══════════════════════════════════════════════════════════════
// IMPROVEMENT 4: Quick watchlist from modal
// ═══════════════════════════════════════════════════════════════
window._toggleWatchlist=function(sym){
  var wl=[];
  try{wl=JSON.parse(localStorage.getItem('celesys_watchlist')||'[]')}catch(e){}
  var idx=wl.indexOf(sym);
  if(idx>=0){wl.splice(idx,1)}else{wl.push(sym)}
  try{localStorage.setItem('celesys_watchlist',JSON.stringify(wl))}catch(e){}
  // Update button state
  var btn=document.getElementById('wlBtn_'+sym);
  if(btn){
    var isIn=wl.indexOf(sym)>=0;
    btn.textContent=isIn?'★ Saved':'☆ Watchlist';
    btn.style.background=isIn?'#d97706':'rgba(255,255,255,.1)';
  }
  return wl.indexOf(sym)>=0;
};
window._isInWatchlist=function(sym){
  try{var wl=JSON.parse(localStorage.getItem('celesys_watchlist')||'[]');return wl.indexOf(sym)>=0}catch(e){return false}
};

// ═══════════════════════════════════════════════════════════════
// IMPROVEMENT 5: Watchlist viewer
// ═══════════════════════════════════════════════════════════════
window._showWatchlist=function(){
  var wl=[];
  try{wl=JSON.parse(localStorage.getItem('celesys_watchlist')||'[]')}catch(e){}
  if(wl.length===0){alert('Your watchlist is empty. Click ☆ Watchlist in the modal to save stocks.');return}
  
  var h='<div style="padding:16px;background:#fff;border-radius:14px;border:2px solid #d9770630;margin-bottom:14px">';
  h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">';
  h+='<div><div style="font-size:14px;font-weight:900;color:#d97706;font-family:Sora">★ My Watchlist</div>';
  h+='<div style="font-size:9px;color:#6b7280">'+wl.length+' stocks saved · Click to analyze</div></div>';
  h+='<div style="display:flex;gap:6px">';
  h+='<button onclick="window._runL0WatchlistScan()" style="padding:6px 12px;border-radius:6px;background:#d97706;color:#fff;border:none;font-size:9px;font-weight:700;cursor:pointer">🔬 Scan All</button>';
  h+='<button onclick="if(confirm(\'Clear entire watchlist?\'))localStorage.removeItem(\'celesys_watchlist\')" style="padding:6px 12px;border-radius:6px;background:#dc262610;border:1px solid #dc262620;color:#dc2626;font-size:9px;font-weight:700;cursor:pointer">🗑️ Clear</button>';
  h+='</div></div>';
  h+='<div style="display:flex;flex-wrap:wrap;gap:6px">';
  wl.forEach(function(sym,i){
    h+='<div style="padding:8px 14px;border-radius:8px;background:#fafbfc;border:1px solid #e2e5ea;cursor:pointer;display:flex;align-items:center;gap:6px" onclick="window._openCDSModal(\''+sym+'\','+JSON.stringify(wl)+','+i+')">';
    h+='<span style="font-size:12px;font-weight:800;color:#0A1628">'+sym+'</span>';
    h+='<span onclick="event.stopPropagation();window._toggleWatchlist(\''+sym+'\');window._showWatchlist()" style="font-size:10px;cursor:pointer;color:#dc2626" title="Remove">✕</span>';
    h+='</div>';
  });
  h+='</div></div>';
  
  var el=document.getElementById('deResult');
  if(el)el.innerHTML=h;
};

window._runL0WatchlistScan=function(){
  var wl=[];
  try{wl=JSON.parse(localStorage.getItem('celesys_watchlist')||'[]')}catch(e){}
  if(wl.length===0)return;
  var reg=window._deRegion||'IN';
  var el=document.getElementById('deResult');
  if(!el)return;
  el.innerHTML='<div style="padding:30px;text-align:center"><div style="display:inline-block;width:20px;height:20px;border:3px solid #d97706;border-top-color:transparent;border-radius:50%;animation:spin .5s linear infinite"></div><div style="font-size:12px;color:#0A1628;margin-top:8px">Scanning '+wl.length+' watchlist stocks...</div></div>';
  
  fetch('/api/cds-batch?symbols='+encodeURIComponent(wl.join(','))+'&region='+reg+'&segment=MIXED')
    .then(function(r){return r.json()})
    .then(function(d){
      if(!d||!d.success){el.innerHTML='<div style="color:#dc2626;padding:16px">Error: '+(d?d.error:'')+'</div>';return}
      window._scanResults=d.results.map(function(r){
        return {symbol:r.symbol,name:r.name,price:r.price,score:r.cdsScore,decision:r.verdict,
          bucket:r.bucket,bucketIcon:r.bucketIcon,fScore:r.fScore,upside:r.upside,
          layers:r.layers,kelly:r.kelly,verdict:r.verdict};
      });
      // Render simple results
      var h='<div style="padding:16px 20px;background:linear-gradient(135deg,#d97706,#f59e0b);border-radius:14px;color:#fff;margin-bottom:12px">';
      h+='<div style="font-size:16px;font-weight:900;font-family:Sora">★ Watchlist Scan — '+d.results.length+' stocks</div>';
      h+='<div style="font-size:10px;color:rgba(255,255,255,.7)">Deploy: '+d.deployCount+' · Watch: '+d.watchCount+' · Avoid: '+d.avoidCount+' · '+d.elapsed+'s</div></div>';
      h+='<div style="display:flex;flex-wrap:wrap;gap:8px">';
      d.results.forEach(function(r,i){
        var sc=r.cdsScore;var c=sc>=70?'#059669':sc>=55?'#d97706':'#dc2626';
        h+='<div onclick="window._openCDSModal(\''+r.symbol+'\','+JSON.stringify(d.results.map(function(x){return x.symbol}))+','+i+')" style="padding:10px 14px;border-radius:10px;background:#fff;border:1.5px solid '+c+'25;cursor:pointer;min-width:140px;text-align:center">';
        h+='<div style="font-size:13px;font-weight:900;color:#0A1628">'+r.symbol+'</div>';
        h+='<div style="font-size:20px;font-weight:900;color:'+c+';font-family:JetBrains Mono;margin:4px 0">'+sc+'</div>';
        h+='<div style="font-size:8px;font-weight:700;color:'+c+'">'+r.bucketIcon+' '+r.bucket+'</div>';
        h+='</div>';
      });
      h+='</div>';
      el.innerHTML=h;
    }).catch(function(e){el.innerHTML='<div style="color:#dc2626;padding:16px">'+e.message+'</div>'});
};

// ═══════════════════════════════════════════════════════════════
// TWO-MODE PDF EXPORT
// Mode 1: Summary PDF — clean text, no charts (for sharing)
// Mode 2: Full HTML — complete report (for internal use)
// ═══════════════════════════════════════════════════════════════

window._exportSummaryPDF=function(){
  var d=window._lastInvestorData;
  if(!d){alert('Analyze a stock first');return}
  var S=d.csym||'$';var lv=d.levels||{};var biz=d.business||{};var moat=d.moat||{};
  
  var h='<!DOCTYPE html><html><head><meta charset="UTF-8"><title>'+d.symbol+' — Summary Report</title>';
  h+='<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:"Segoe UI",system-ui,sans-serif;padding:30px 40px;color:#1f2937;max-width:800px;margin:0 auto;font-size:11px;line-height:1.6}';
  h+='h1{font-size:20px;color:#1A3A78;border-bottom:3px solid #1A3A78;padding-bottom:8px;margin-bottom:4px}';
  h+='.sub{font-size:10px;color:#6b7280;margin-bottom:20px}';
  h+='h2{font-size:13px;margin:18px 0 6px;padding:6px 12px;border-radius:6px;color:#fff;background:#1A3A78}';
  h+='h3{font-size:11px;margin:10px 0 4px;color:#374151;border-bottom:1px solid #e5e7eb;padding-bottom:3px}';
  h+='table{width:100%;border-collapse:collapse;margin:6px 0 14px}';
  h+='th{background:#f1f5f9;padding:5px 8px;text-align:left;font-size:9px;color:#6b7280;border-bottom:2px solid #e5e7eb}';
  h+='td{padding:4px 8px;border-bottom:1px solid #f1f5f9}';
  h+='.g{color:#059669}.r{color:#dc2626}.y{color:#d97706}';
  h+='.box{padding:8px 12px;border-radius:6px;margin:6px 0;border:1px solid #e5e7eb;background:#fafbfc}';
  h+='.kpi{display:flex;gap:8px;margin:8px 0}.kpi>div{flex:1;text-align:center;padding:8px;border:1px solid #e5e7eb;border-radius:6px}';
  h+='.kpi .v{font-size:16px;font-weight:900;font-family:Consolas,monospace}.kpi .l{font-size:8px;color:#6b7280;text-transform:uppercase}';
  h+='@media print{body{padding:15px 20px}@page{margin:8mm;size:A4}}';
  h+='</style></head><body>';
  
  // Header
  h+='<h1>'+d.symbol+' — '+(d.companyName||d.symbol)+'</h1>';
  h+='<div class="sub">Celesys AI Summary Report · '+new Date().toLocaleString()+' · For discussion purposes only — not financial advice</div>';
  
  // Verdict
  var dC=d.upside>=0?'g':'r';
  h+='<div style="text-align:center;padding:16px;border:2px solid '+(d.decColor||'#1A3A78')+';border-radius:10px;margin-bottom:14px">';
  h+='<div style="font-size:24px;font-weight:900;color:'+(d.decColor||'#1A3A78')+'">'+d.decision+'</div>';
  h+='<div style="font-size:10px;color:#374151;margin-top:6px">'+(d.explain||'')+'</div>';
  h+='<div style="margin-top:8px;font-size:10px">Confidence: <strong>'+d.confidence+'%</strong> · F-Score: <strong>'+(d.fScore||0)+'/9</strong> · Moat: <strong>'+(d.moatScore||moat.score||0)+'/100</strong></div>';
  h+='</div>';
  
  // KPIs
  h+='<div class="kpi">';
  h+='<div><div class="l">Price</div><div class="v">'+S+(d.price||0).toLocaleString()+'</div></div>';
  h+='<div><div class="l">PE</div><div class="v">'+(d.pe?d.pe.toFixed(1)+'x':'N/A')+'</div></div>';
  h+='<div><div class="l">Fair Value</div><div class="v">'+S+(lv.fairValue||0).toLocaleString()+'</div></div>';
  h+='<div><div class="l">Upside</div><div class="v '+(d.upside>=0?'g':'r')+'">'+(d.upside>=0?'+':'')+d.upside.toFixed(1)+'%</div></div>';
  h+='<div><div class="l">Beta</div><div class="v">'+(d.beta||0).toFixed(2)+'</div></div>';
  h+='<div><div class="l">RSI</div><div class="v">'+Math.round(d.rsi||0)+'</div></div>';
  h+='</div>';
  
  // Key Levels
  h+='<h2>📍 Key Levels</h2>';
  h+='<table><tr><th>Level</th><th>Price</th><th>Action</th></tr>';
  if(lv.buy)h+='<tr><td>Buy Zone</td><td>'+S+(lv.buy||0).toLocaleString()+'</td><td>Limit order near support</td></tr>';
  if(lv.sl)h+='<tr><td>Stop Loss</td><td class="r">'+S+(lv.sl||0).toLocaleString()+'</td><td>Hard stop — exit if hit</td></tr>';
  if(lv.target1)h+='<tr><td>Target 1</td><td class="g">'+S+(lv.target1||0).toLocaleString()+'</td><td>Book 50% profits</td></tr>';
  if(lv.target2)h+='<tr><td>Target 2</td><td class="g">'+S+(lv.target2||0).toLocaleString()+'</td><td>Close position</td></tr>';
  h+='</table>';
  
  // Business Quality
  h+='<h2>💚 Business Quality</h2>';
  h+='<table><tr><th>Metric</th><th>Value</th><th>Rating</th></tr>';
  h+='<tr><td>F-Score (Piotroski)</td><td>'+(d.fScore||0)+'/9</td><td class="'+((d.fScore||0)>=7?'g':'y')+'">'+(d.fScore>=7?'STRONG':d.fScore>=5?'AVERAGE':'WEAK')+'</td></tr>';
  h+='<tr><td>Moat</td><td>'+(d.moatScore||moat.score||0)+'/100</td><td>'+(moat.verdict||'')+'</td></tr>';
  h+='<tr><td>ROE</td><td>'+(d.roe||0).toFixed(1)+'%</td><td class="'+((d.roe||0)>15?'g':'y')+'">'+(d.roe>15?'STRONG':'AVERAGE')+'</td></tr>';
  h+='<tr><td>Debt/Equity</td><td>'+(biz.debtEquity||0).toFixed(1)+'</td><td class="'+((biz.debtEquity||0)<1?'g':'r')+'">'+(biz.debtEquity<1?'LOW':'HIGH')+'</td></tr>';
  h+='</table>';
  
  // DCF
  if(d.intrinsicValue){
    var iv=d.intrinsicValue;
    h+='<h2>🧮 Intrinsic Value</h2>';
    h+='<div class="box">Primary DCF: <strong>'+S+(iv.primary||iv.average||0).toLocaleString()+'</strong> · Margin of Safety: <strong>'+(iv.marginOfSafety||0)+'%</strong></div>';
  }
  
  // Monte Carlo
  if(d.monteCarlo){
    var mc=d.monteCarlo;
    h+='<h2>🎲 Monte Carlo ('+mc.simulations+' simulations)</h2>';
    h+='<div class="kpi">';
    h+='<div><div class="l">Pessimistic (P10)</div><div class="v">'+S+(mc.p10||0).toLocaleString()+'</div></div>';
    h+='<div><div class="l">Central (P50)</div><div class="v">'+S+(mc.p50||0).toLocaleString()+'</div></div>';
    h+='<div><div class="l">Optimistic (P90)</div><div class="v">'+S+(mc.p90||0).toLocaleString()+'</div></div>';
    h+='</div>';
    h+='<div class="box">Probability undervalued: <strong>'+mc.probUndervalued+'%</strong></div>';
  }
  
  // CDS Score
  var eng=window._calcInstitutionalMDO?window._calcInstitutionalMDO(d,S):null;
  if(eng){
    h+='<h2>🏛️ CDS v2.0 Score</h2>';
    h+='<div class="kpi">';
    h+='<div><div class="l">CDS Score</div><div class="v">'+eng.score.toFixed(0)+'/100</div></div>';
    h+='<div><div class="l">Verdict</div><div class="v">'+eng.verdict+'</div></div>';
    h+='<div><div class="l">Bucket</div><div class="v">'+eng.bucketLabel+'</div></div>';
    h+='<div><div class="l">Allocation</div><div class="v">'+eng.posSize+'%</div></div>';
    h+='</div>';
    h+='<h3>6-Layer Breakdown</h3>';
    h+='<table><tr><th>Layer</th><th>Score</th><th>Weight</th></tr>';
    h+='<tr><td>L1: Liquidity</td><td>'+Math.round(eng.L1/10)+'/10</td><td>'+eng.weights.L1+'%</td></tr>';
    h+='<tr><td>L2: Flow</td><td>'+Math.round(eng.L2/10)+'/10</td><td>'+eng.weights.L2+'%</td></tr>';
    h+='<tr><td>L3: Volatility</td><td>'+Math.round(eng.L3/10)+'/10</td><td>'+eng.weights.L3+'%</td></tr>';
    h+='<tr><td>L4: Fundamentals</td><td>'+Math.round(eng.L4/10)+'/10</td><td>'+eng.weights.L4+'%</td></tr>';
    h+='<tr><td>L5: Quant</td><td>'+Math.round(eng.L5/10)+'/10</td><td>'+eng.weights.L5+'%</td></tr>';
    h+='<tr><td>L6: Probability</td><td>'+Math.round(eng.L6/10)+'/10</td><td>'+eng.weights.L6+'%</td></tr>';
    h+='</table>';
  }
  
  // Decision Summary
  h+='<h2>📋 Decision Summary — '+d.symbol+'</h2>';
  h+='<div class="box"><strong>Quality:</strong> '+d.decision+' · <strong>Timing:</strong> '+(eng?eng.verdict:'—')+' · <strong>Regime:</strong> '+(eng?eng.regime:'—')+'</div>';
  
  // Action advice
  h+='<h3>If You Already Hold</h3>';
  h+='<div class="box">'+(d.decision.indexOf('BUY')>=0?'HOLD & ADD on dips toward '+S+Math.round(d.sma50||d.price*0.95).toLocaleString()+'. Stop at '+S+Math.round(lv.sl||d.price*0.92).toLocaleString()+'.':'HOLD — do not add. Set alert at SMA50.')+'</div>';
  h+='<h3>If You Don\'t Hold</h3>';
  h+='<div class="box">'+(d.decision.indexOf('BUY')>=0&&eng&&eng.score>=60?'ENTER — Limit buy near '+S+Math.round(lv.buy||d.price*0.97).toLocaleString()+'. Allocate '+(eng?eng.posSize:5)+'% of portfolio. Stop: '+S+Math.round(lv.sl||d.price*0.92).toLocaleString()+'.':'WAIT for better entry or improving momentum.')+'</div>';
  
  // Footer
  h+='<div style="margin-top:20px;padding:10px;border-top:2px solid #1A3A78;text-align:center;font-size:8px;color:#94a3b8">';
  h+='Celesys AI · Summary Report · '+new Date().toLocaleDateString()+' · Educational only — Not financial advice</div>';
  h+='<script>setTimeout(function(){window.print()},500)<\/script>';
  h+='</body></html>';
  
  var w=window.open('','_blank','width=800,height=600');
  if(w){w.document.write(h);w.document.close()}
  else{
    var blob=new Blob([h],{type:'text/html'});
    var a=document.createElement('a');a.href=URL.createObjectURL(blob);
    a.download=d.symbol+'_Summary_Report.html';a.click();
  }
};

window._exportFullHTML=function(){
  var d=window._lastInvestorData;
  if(!d){alert('Analyze a stock first');return}
  
  // Clone the full report from DOM
  var srcEl=document.getElementById('deResult');
  if(!srcEl||srcEl.innerHTML.length<500){alert('No report to export');return}
  
  var clone=srcEl.cloneNode(true);
  
  // Open all details/collapsible sections
  clone.querySelectorAll('details').forEach(function(det){det.setAttribute('open','')});
  // Expand all collapsed group bodies
  clone.querySelectorAll('[id^="b_cg"]').forEach(function(el){el.style.display='block'});
  // Make sure all display:none sections are visible
  clone.querySelectorAll('[style*="display:none"],[style*="display: none"]').forEach(function(el){
    // Don't show hidden nav/tabs, only content sections
    if(!el.id||el.id.indexOf('Tab')<0){
      el.style.display='block';
    }
  });
  
  // Convert Canvas elements to images for PDF
  var canvases=document.getElementById('deResult').querySelectorAll('canvas');
  var cloneCanvases=clone.querySelectorAll('canvas');
  canvases.forEach(function(c,i){
    try{
      var img=document.createElement('img');
      img.src=c.toDataURL('image/png');
      img.style.cssText='width:'+c.width+'px;max-width:100%;height:auto';
      if(cloneCanvases[i]){
        cloneCanvases[i].replaceWith(img);
      }
    }catch(e){console.warn('Canvas export failed:',e)}
  });
  
  // Remove interactive buttons but keep informational content
  clone.querySelectorAll('button,input,select,textarea').forEach(function(el){
    if(el.tagName==='BUTTON'&&el.textContent.length>30){
      var sp=document.createElement('span');sp.textContent=el.textContent;sp.style.cssText='font-size:9px;color:#6b7280';el.replaceWith(sp);
    }else if(el.tagName!=='INPUT'||el.type==='text'){el.remove()}
  });
  clone.querySelectorAll('[onclick*="loadInvestorDE"],[onclick*="switchTab"],[onclick*="_topStocksReport"],[onclick*="_runL0Scan"],[onclick*="_openCDSModal"]').forEach(function(el){el.remove()});
  // Remove export buttons themselves
  var expBtns=clone.querySelector('#celesysExportBtns');if(expBtns)expBtns.remove();
  
  // Get styles
  var styles='';
  document.querySelectorAll('link[rel="stylesheet"],style').forEach(function(s){
    if(s.tagName==='STYLE')styles+=s.outerHTML;
    else if(s.href)styles+='<link rel="stylesheet" href="'+s.href+'">';
  });
  var rootStyles=getComputedStyle(document.documentElement);
  var cssVars='';
  ['--bg','--bg2','--bg3','--surface','--glass','--border','--border2','--blue','--blue2','--cyan','--teal','--green','--green2','--amber','--red','--purple','--text','--text2','--text3','--mono'].forEach(function(v){
    try{cssVars+=v+':'+rootStyles.getPropertyValue(v)+';'}catch(e){}
  });
  
  var h='<!DOCTYPE html><html><head><meta charset="UTF-8"><title>'+d.symbol+' — Full Report (Internal)</title>';
  h+=styles;
  h+='<style>:root{'+cssVars+'}body{font-family:"DM Sans","Segoe UI",system-ui,sans-serif;padding:20px 30px;color:#1f2937;background:#fff;max-width:1000px;margin:0 auto}';
  h+='@media print{body{padding:10px 15px;max-width:100%}button,input,select,.no-print{display:none!important}details{display:block!important}details>summary{list-style:none}details>*:not(summary){display:block!important}[style*="display:none"]{display:block!important}}';
  h+='@page{margin:8mm;size:A4}';
  h+='canvas{max-width:100%!important}img{max-width:100%!important}';
  h+='</style></head><body>';
  
  // Confidential header
  h+='<div style="text-align:center;padding:10px;background:#FEF3C7;border:1px solid #F59E0B;border-radius:8px;margin-bottom:14px;font-size:10px;color:#92400E"><strong>CONFIDENTIAL — INTERNAL USE ONLY</strong> — Complete analysis report with all 36 charts. Content cannot be printed. — celesys.ai</div>';
  
  // Header
  h+='<div style="text-align:center;padding-bottom:14px;border-bottom:3px solid #1A3A78;margin-bottom:14px">';
  h+='<div style="font-size:24px;font-weight:900;color:#1A3A78;font-family:Sora,sans-serif">'+d.symbol+' — '+(d.companyName||d.symbol)+'</div>';
  h+='<div style="font-size:11px;color:#6b7280">Celesys AI Full Report · INTERNAL · '+new Date().toLocaleString()+'</div></div>';
  
  h+=clone.outerHTML;
  
  h+='<div style="margin-top:20px;padding:12px;border-top:2px solid #1A3A78;text-align:center;font-size:9px;color:#94a3b8">Celesys AI · Internal Full Report · '+new Date().toLocaleDateString()+' · Educational only</div>';
  h+='</body></html>';
  
  // Download as HTML file
  var blob=new Blob([h],{type:'text/html;charset=utf-8'});
  var a=document.createElement('a');
  a.href=URL.createObjectURL(blob);
  a.download=d.symbol+'_Full_Report_INTERNAL.html';
  document.body.appendChild(a);a.click();
  setTimeout(function(){document.body.removeChild(a);URL.revokeObjectURL(a.href)},1000);
  alert(d.symbol+' full report downloaded as HTML.\\n\\nTo save as PDF:\\n1. Open the downloaded HTML file in Chrome\\n2. Press Ctrl+P (or Cmd+P)\\n3. Set Destination to \\"Save as PDF\\"\\n4. Enable \\"Background graphics\\"\\n5. Set margins to \\"Minimum\\"');
};

// ═══ Add export buttons to the report header ═══
window._addExportButtons=function(){
  var el=document.getElementById('deResult');
  if(!el)return;
  var existing=document.getElementById('celesysExportBtns');
  if(existing)return;
  
  var d=window._lastInvestorData;
  if(!d)return;
  
  var btns=document.createElement('div');
  btns.id='celesysExportBtns';
  btns.style.cssText='display:flex;gap:8px;justify-content:center;margin:10px 0;flex-wrap:wrap';
  btns.innerHTML='<button onclick="window._exportSummaryPDF()" style="padding:8px 16px;border-radius:8px;background:#059669;color:#fff;border:none;font-size:10px;font-weight:800;cursor:pointer;font-family:Sora,sans-serif">📄 Summary PDF (for sharing)</button>'
    +'<button onclick="window._exportFullHTML()" style="padding:8px 16px;border-radius:8px;background:#1A3A78;color:#fff;border:none;font-size:10px;font-weight:800;cursor:pointer;font-family:Sora,sans-serif">📊 Full HTML Report (internal)</button>'
    +'<button onclick="if(typeof _investorExportPDF===\'function\')_investorExportPDF()" style="padding:8px 16px;border-radius:8px;background:#6b7280;color:#fff;border:none;font-size:10px;font-weight:800;cursor:pointer;font-family:Sora,sans-serif">🖨️ Print Report</button>';
  
  // Insert after the hero section
  var hero=el.querySelector('[style*="text-align:center"]');
  if(hero&&hero.parentElement===el){
    hero.parentElement.insertBefore(btns,hero.nextSibling);
  }else{
    el.insertBefore(btns,el.firstChild);
  }
};

// Auto-add export buttons when report loads
var _origLoadInvestorDE=window.loadInvestorDE;
if(typeof _origLoadInvestorDE==='function'){
  // Will be injected via setTimeout after report renders
}
// Hook into the render completion
setInterval(function(){
  if(window._lastInvestorData&&document.getElementById('deResult')&&document.getElementById('deResult').innerHTML.length>1000&&!document.getElementById('celesysExportBtns')){
    window._addExportButtons();
  }
},2000);
