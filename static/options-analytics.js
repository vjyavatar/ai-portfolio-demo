/*
 * PCR aggregation and max-pain payout loop adapted from Indian-Option-MCP:
 * https://github.com/devag7/Indian-Option-MCP/tree/a00d3eacc181c8994335127fc294133cf3681d7b
 * src/engine/pcr.ts and src/engine/max-pain.ts
 * Copyright (c) 2024 Indian Option MCP Contributors. MIT License.
 * Full license: docs/vendor/Indian-Option-MCP-LICENSE.txt
 * Celesys changes: normalized row adapter; missing/invalid data checks; ties;
 * bounded computation; no direction inference, forecasts or strategy changes.
 */
(function (root) {
  'use strict';
  const valid = value => typeof value === 'number' && Number.isFinite(value) && value >= 0;
  function analyze(input) {
    const rows = Array.isArray(input) ? input : [];
    const result = {
      pcr: {oi: null, volume: null},
      maxPain: {strike: null, strikes: [], status: 'INSUFFICIENT_DATA'},
      coverage: {scope: 'RETURNED_ROWS_ONLY', rows: rows.length, oiPairs: 0, volumePairs: 0},
      notes: ['Returned rows only; coverage of the full expiry is not established.',
        'PCR and minimum-payout strike are descriptive, not a direction signal, price target or success probability.']
    };
    if (!Array.isArray(input) || !rows.length) return result;
    // Bound the quadratic upstream max-pain loop and reject duplicate identities.
    if (rows.length > 1000 || rows.some(r => !r || !valid(r.strike) || r.strike === 0) ||
        new Set(rows.map(r => r.strike)).size !== rows.length) {
      result.notes.push('Invalid, duplicate or oversized strike set; analytics withheld.');
      return result;
    }
    for (const field of ['oi', 'volume']) {
      const pairs = rows.filter(r => r.call && r.put && valid(r.call[field]) && valid(r.put[field]));
      result.coverage[field === 'oi' ? 'oiPairs' : 'volumePairs'] = pairs.length;
      if (pairs.length !== rows.length) continue;
      let totalCall = 0, totalPut = 0;
      for (const row of pairs) { totalCall += row.call[field]; totalPut += row.put[field]; }
      const ratio = totalCall > 0 ? totalPut / totalCall : null;
      result.pcr[field] = ratio !== null && Number.isFinite(totalCall) && Number.isFinite(totalPut) && Number.isFinite(ratio) ? ratio : null;
    }
    if (result.coverage.oiPairs !== rows.length || rows.length < 2) {
      result.notes.push('Minimum-payout strike needs at least two strikes with complete call and put OI.');
      return result;
    }
    const lots = rows.flatMap(r => [r.call.lot_size, r.put.lot_size]);
    const suppliedLots = lots.filter(x => x !== undefined && x !== null);
    if (suppliedLots.length && (suppliedLots.length !== lots.length || suppliedLots.some(x => !valid(x) || x === 0) || new Set(suppliedLots).size !== 1)) {
      result.notes.push('Inconsistent or incomplete contract multipliers; minimum-payout strike withheld.');
      return result;
    }
    // A common multiplier does not change the minimizing strike. Do not expose
    // monetary payout values without verified provider OI units/multipliers.
    const sortedData = [...rows].sort((a, b) => a.strike - b.strike);
    const activeStrikes = sortedData.filter(d => d.call.oi > 0 || d.put.oi > 0);
    if (!activeStrikes.length) {
      result.notes.push('All supplied OI is zero; no meaningful minimum-payout strike.');
      return result;
    }
    let minPain = Infinity;
    for (const settlementData of sortedData) {
      const S = settlementData.strike;
      let totalCallPain = 0, totalPutPain = 0;
      for (const strikeData of activeStrikes) {
        const K = strikeData.strike;
        if (S > K) totalCallPain += (S - K) * strikeData.call.oi;
        if (S < K) totalPutPain += (K - S) * strikeData.put.oi;
      }
      const totalPain = totalCallPain + totalPutPain;
      if (!Number.isFinite(totalPain)) {
        result.maxPain.strikes = [];
        result.notes.push('Numeric overflow; minimum-payout strike withheld.');
        return result;
      }
      if (totalPain < minPain) { minPain = totalPain; result.maxPain.strikes = [S]; }
      else if (totalPain === minPain) result.maxPain.strikes.push(S);
    }
    result.maxPain.status = result.maxPain.strikes.length === 1 ? 'RETURNED_ROWS_ESTIMATE' : 'TIED_RETURNED_ROWS_ESTIMATE';
    result.maxPain.strike = result.maxPain.strikes.length === 1 ? result.maxPain.strikes[0] : null;
    result.notes.push('Minimum payout ignores premiums and does not predict where price will settle.');
    return result;
  }
  root.CelesysOptionsAnalytics = Object.freeze({analyze, version: '1.0.0'});
})(typeof window !== 'undefined' ? window : globalThis);
