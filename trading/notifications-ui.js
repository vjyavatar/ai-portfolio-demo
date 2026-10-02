import { enqueue } from "./notifications.mjs";
export function notificationCenter(getReport, isSample) {
  const $ = id => document.getElementById(id);
  let inbox = [], audio = null, enabled = false, storageOK = true;
  try {
    const stored = JSON.parse(localStorage.getItem("celesys.alerts.v1") || "[]");
    if (Array.isArray(stored)) inbox = stored.filter(x => x && typeof x.id === "string" && Number.isFinite(x.expires)).slice(0, 100);
  } catch { storageOK = false; }
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
    process(report) {
      if (isSample()) return;
      const result = enqueue(inbox, report); inbox = result.inbox;
      persist(); render();
      if (!result.alert) return;
      beep();
      if (enabled && Notification.permission === "granted") {
        try { new Notification("Celesys · " + result.alert.symbol + " research", { body: "Underlying setup passed automated checks. Review evidence and unverified risks in the desk. Not an order.", tag: result.alert.id }); }
        catch { $("delivery-status").textContent += " · OS notification unavailable; alert saved in inbox."; }
      }
    },
  };
}
