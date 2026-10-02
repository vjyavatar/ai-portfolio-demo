import test from 'node:test';
import assert from 'node:assert/strict';
import {optionView} from '../trading/options.mjs';
test('CALL/PUT cards expire, reject future quotes and never infer a contract',()=>{
  for(const side of ['CALL','PUT']) {
    const r={status:`BUY_${side}_CANDIDATE`,candidate:{expires_at:1300,bid_time:1000,ask_time:1000}};
    assert.equal(optionView(r,1001).valid,true);
    assert.equal(optionView(r,1300).valid,false);
    assert.equal(optionView(r,999).valid,false);
  }
  assert.equal(optionView({direction:'CALL',status:'WAIT'},1001).valid,false);
  assert.equal(optionView(null,1001).valid,false);
});
