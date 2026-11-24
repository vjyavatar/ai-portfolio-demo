import { fresh } from "./paper.mjs";
import { optionView } from "./options.mjs";
export function notificationCenter(getReport, isSample) {
  const $ = id => document.getElementById(id);
  let inbox = [], audio = null, enabled = false, storageOK = true;
  try {
    const stored = JSON.parse(localStorage.getItem("celesys.alerts.v1") || "[]");
    if (Array.isArray(stored)) inbox = stored.filter(x => x && typeof x.id === "string" && Number.isFinite(x.expires)).slice(0, 100);
  } catch { storageOK = false; }
  // Only issue a directional option alert when underlying + verified option
  // contract agree. Every other case is explicitly WAIT / NO TRADE.
  function decision(report, options) {
    if (!report || isSample() || report.mode === "SAMPLE") return null;
    const now=Date.now()/1000;
    const validUnderlying=fresh(report,now) && report.market_status==="OPEN" &&
      Number.isFinite(report.session_start) && Number.isFinite(report.session_end) &&
      report.session_start<=now && now<report.session_end &&
      Array.isArray(report.stages) && report.stages.length>0 &&
      !report.stages.some(s=>s.status==="blocked") && !report.stale_cache;
    const validContract=validUnderlying && optionView(options,now).valid &&
      report.region==="US" && ["SPY","QQQ"].includes(report.symbol);
    let verdict="NO TRADE", why=options?.reason || report.reason || "Insufficient verified evidence.";
    let contract=null;
    if (validContract && report.verdict==="LONG_RESEARCH" && options.status==="BUY_CALL_CANDIDATE") {
      verdict="REVIEW CE BUY"; contract=options.candidate;
    } else if (validContract && report.verdict==="BEARISH_RESEARCH" && options.status==="BUY_PUT_CANDIDATE") {
      verdict="REVIEW PE BUY"; contract=options.candidate;
    } else if (validUnderlying && ["LONG_RESEARCH","BEARISH_RESEARCH"].includes(report.verdict)) {
      verdict="WAIT"; why="Directional underlying research exists, but the complete option contract and chain/risk validation has not passed. " + why;
    }
    if (contract) why=`Verify with broker: ${contract.contract}, expiry ${contract.expiry}, bid ${contract.bid}, ask ${contract.ask}, delta ${contract.delta}, OI ${contract.open_interest}. Premium exposure per contract up to ${contract.premium_at_risk} plus fees. No guaranteed fill. ${options.reason || ""}`;
    if (!validUnderlying) why="Missing, closed, stale or incomplete underlying evidence. No trade. " + (report.reason || "");
    return {symbol:report.symbol,region:report.region,verdict,reason:why,
      sourceTime:Number.isFinite(report.quote_time)?report.quote_time:now,
      created:now,expires:Math.min(now+900,Number.isFinite(report.session_end)?report.session_end:now+900),
      contract:contract?.contract || null};
  }
  function render() {
    $("delivery-status").textContent = "Browser alerts: " + (enabled ? "enabled for this session" : "off") +
      " · Sound: " + (audio?.state === "running" ? "enabled" : "off") +
      " · Inbox: " + (storageOK ? "stored on this browser" : "memory only; storage unavailable");
    $("alert-inbox").replaceChildren();
    if (!inbox.length) $("alert-inbox").textContent = "No qualifying research alerts. Sample exercises never trigger market notifications.";
    for (const item of inbox) {
      const row = document.createElement("div"), body = document.createElement("div");
      const title = document.createElement("strong"), detail = document.createElement("p");
      title.textContent = item.symbol + " · " + item.verdict.replaceAll("_", " ") +
        (item.invalidated ? " · INVALIDATED" : Date.now() / 1000 >= item.expires ? " · EXPIRED" : " · RECENT EVIDENCE");
      detail.textContent = new Date(item.sourceTime * 1000).toLocaleString() + " · " + item.reason + " · Research only; not an order.";
      if (item.invalidated) detail.textContent += " Latest scan: " + item.invalidationReason;
      body.append(title, detail); row.append(body); $("alert-inbox").append(row);
    }
  }
  function persist() {
    try { localStorage.setItem("celesys.alerts.v1", JSON.stringify(inbox)); } catch { storageOK = false; }
  }
  function beep() {
    if (audio?.state !== "running") return;
    const oscillator = audio.createOscillator(), gain = audio.createGain();
    oscillator.connect(gain); gain.connect(audio.destination);
    oscillator.frequency.value = 660; gain.gain.setValueAtTime(0.08, audio.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + 0.3);
    oscillator.start(); oscillator.stop(audio.currentTime + 0.3);
  }
  $("enable-alerts").onclick = async () => {
    try {
      if (!("Notification" in window)) throw Error("Browser notifications are unavailable here.");
      if (enabled) { enabled = false; render(); $("enable-alerts").textContent = "Enable browser alerts"; return; }
      enabled = (await Notification.requestPermission()) === "granted";
      render();
      if (!enabled) $("delivery-status").textContent += " · Permission not granted; use the inbox.";
    } catch (e) { $("delivery-status").textContent = e.message; }
    $("enable-alerts").textContent = enabled ? "Disable browser alerts" : "Enable browser alerts";
  };
  $("enable-sound").onclick = async () => {
    try {
      if (audio?.state === "running") { await audio.suspend(); }
      else { audio ||= new (window.AudioContext || window.webkitAudioContext)(); await audio.resume(); beep(); }
      $("enable-sound").textContent = audio.state === "running" ? "Disable sound" : "Enable & test sound";
      render();
    } catch { $("delivery-status").textContent = "Sound is unavailable. Alerts remain visible in the inbox."; }
  };
  $("clear-alerts").onclick = () => { inbox = []; persist(); render(); };
  $("export-evidence").onclick = () => {
    const report = getReport();
    if (!report) { $("delivery-status").textContent = "Run research before exporting evidence."; return; }
    const blob = new Blob([JSON.stringify({ exportedAt: new Date().toISOString(), sample: isSample(), report }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob), a = document.createElement("a");
    a.href = url; a.download = "celesys-research-evidence.json"; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  render(); setInterval(render, 30000);
  return {
    process(report, options) {
      if (isSample()) return;
      const d=decision(report,options);
      if (!d) return;
      // Send on every material decision/contract change, or a 15-minute
      // periodic check-in. Never repeat faster than that for an unchanged state.
      const fingerprint=[d.region,d.symbol,d.verdict,d.contract].join(":");
      const latest=inbox.find(x=>x.region===d.region && x.symbol===d.symbol);
      const now=Date.now()/1000;
      const change=!latest || latest.fingerprint!==fingerprint;
      if (!change && now-latest.created<900) return;
      const alert={...d,id:fingerprint+":"+Math.floor(now),fingerprint,
        invalidated:false};
      inbox=[alert,...inbox].slice(0,100);
      persist(); render(); beep();
      if (enabled && Notification.permission==="granted") {
        try { new Notification("Celesys · "+d.symbol+" · "+d.verdict,
          {body:d.reason.slice(0,230)+" · Research only, not an order.",tag:fingerprint}); }
        catch { $("delivery-status").textContent+=" · OS notification unavailable; check inbox."; }
      }
    },
  };
}
