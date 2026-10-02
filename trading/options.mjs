// Contract evidence is supplied only by the read-only server adapter.
export function optionView(result, now = Date.now()/1000) {
  const c = result?.candidate;
  const valid = ['BUY_CALL_CANDIDATE','BUY_PUT_CANDIDATE'].includes(result?.status) &&
    c && Number.isFinite(c.expires_at) && now < c.expires_at &&
    [c.bid_time,c.ask_time].every(t => Number.isFinite(t) && now>=t && now-t<=300);
  return {valid:!!valid, title: valid ? result.status.replaceAll('_',' ') : 'WAIT — no options trade',
    direction:result?.direction ? result.direction+' direction under review' : 'No confirmed direction',
    reason:c && !valid ? 'Option evidence expired. Wait for the next scan.' :
      result?.reason || 'Run research to check CALL / PUT readiness.'};
}
