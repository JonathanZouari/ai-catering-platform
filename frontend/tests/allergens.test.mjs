import {test} from 'node:test';
import assert from 'node:assert/strict';
import {allergenStatus, allergenSummary} from '../js/customer/allergens.js';
test('missing, null and empty legacy information never imply allergen-free',()=>{
  for(const dish of [{},{allergens:null},{allergens:[]}]) {
    assert.equal(allergenStatus(dish,'milk'),'unknown');
    assert.equal(allergenSummary(dish).incomplete,true);
  }
});
test('contains, free and unknown are separate per-allergen states',()=>{
  const dish={allergenStatuses:[{name:'milk',status:'free'},{name:'nuts',status:'contains'},{name:'eggs',status:'unknown'}]};
  assert.equal(allergenStatus(dish,'milk'),'free');
  assert.equal(allergenStatus(dish,'nuts'),'contains');
  assert.equal(allergenStatus(dish,'eggs'),'unknown');
  assert.equal(allergenStatus(dish,'sesame'),'unknown');
  assert.deepEqual(allergenSummary(dish),{contains:['nuts'],free:['milk'],unknown:['eggs'],incomplete:true});
});
