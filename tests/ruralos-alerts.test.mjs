import test from 'node:test';
import assert from 'node:assert/strict';
import {freshness} from '../ruralos/alerts.js';
const checked='2026-09-28T20:00:00Z',review='2026-09-28T21:00:00Z';
test('observed travel and research have distinct fresh labels',()=>{assert.equal(freshness(checked,review,'travel_deal',Date.parse(checked)),'Fare snapshot');assert.equal(freshness(checked,review,'stock_research',Date.parse(checked)),'Research lead')});
test('expiry changes at exact deadline and stays expired',()=>{for(const now of [Date.parse(review),Date.parse(review)+86400000])assert.equal(freshness(checked,review,'travel_deal',now),'Needs recheck')});
test('invalid and future timestamps cannot claim freshness',()=>{for(const [c,r,n] of [['bad',review,Date.parse(checked)],[checked,'bad',Date.parse(checked)],[review,checked,Date.parse(review)],[checked,review,NaN],[checked,review,Date.parse(checked)-600000]])assert.equal(freshness(c,r,'business_research',n),'Needs recheck')});
