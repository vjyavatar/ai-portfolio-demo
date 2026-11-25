import { classify } from "./decision-state.mjs";
export function notificationCenter(getReport, isSample) {
  const $ = id => document.getElementById(id);
  let inbox = [], audio = null, enabled = false, storageOK = true;
  try {
    const stored = JSON.parse(localStorage.getItem("celesys.alerts.v1") || "[]");
    if (Array.isArray(stored)) inbox = stored.filter(x => x && typeof x.id === "string" && Number.isFinite(x.expires)).slice(0, 100);
  } catch { storageOK = false; }
  // Only issue a directional option alert when underlying + verified option
  // contract agree. Every other case is explicitly WAIT / NO TRADE.
  function decision(report, options, closed=false) {
    if (!report || isSample() || report.mode==="SAMPLE") return null;
    const now=Date.now()/1000;
    const d=classify({report,options,region:report.region,symbol:report.symbol,closed,now});
    if(d.state==="SAMPLE")return null;
    const contract=d.contract;
    const expiry=contract?Math.min(contract.expires_at,report.quote_time+300,report.bar_close_time+300,report.session_end):now+300;
    return {symbol:report.symbol,region:report.region,verdict:d.title,reason:d.reason,
      sourceTime:Number.isFinite(report.quote_time)?report.quote_time:now,
      created:now,expires:expiry,contract:contract?.contract||null};
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
    process(report, options, closed=false) {
      if (isSample()) return;
      const d=decision(report,options,closed);
      if (!d) return;
      // Send on every material decision/contract change, or a 15-minute
      // periodic check-in. Never repeat faster than that for an unchanged state.
      const fingerprint=[d.region,d.symbol,d.verdict,d.contract].join(":");
      const latest=inbox.find(x=>x.region===d.region && x.symbol===d.symbol);
      const now=Date.now()/1000;
      const change=!latest || latest.fingerprint!==fingerprint;
      if (!change && now-latest.created<900 && now<latest.expires) return;
      for (const item of inbox) {
        if(item.region===d.region && item.symbol===d.symbol && !item.invalidated && item.contract) {
          item.invalidated=true;
          item.invalidationReason="Superseded by latest scan: "+d.verdict;
        }
      }
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
