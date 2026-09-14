const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '..', 'app.js'), 'utf8');
function load(name, globals = {}) {
  const start = source.indexOf(`function ${name}(`);
  assert.ok(start >= 0);
  const end = source.indexOf('\n}', start) + 2;
  const context = vm.createContext(globals);
  vm.runInContext(source.slice(start, end), context);
  return context[name];
}
const tier = load('getMatchTier', { hasEnteredGradesBelowPass: () => false });
test('missing requirements cannot claim eligibility despite high inferred scores', () => {
  assert.equal(tier({ academic: 100 }, { total: 5, missing: [], score: 100 }, { requirementEvidenceAvailable: false }, { failures: [] }), 'explore');
});
test('captured requirements and passing grades permit a qualified result', () => {
  assert.equal(tier({ academic: 90 }, { total: 5, missing: [], score: 100 }, { requirementEvidenceAvailable: true }, { failures: [] }), 'qualified');
});
test('failing mandatory subject blocks an otherwise high scoring result', () => {
  assert.equal(tier({ academic: 90 }, { total: 5, missing: [], score: 100 }, { requirementEvidenceAvailable: true }, { failures: [{}] }), 'blocked');
});
test('no parsed rules cannot produce qualified status', () => {
  assert.equal(tier({ academic: 90 }, { total: 0 }, { dataConfidence: 90, requirementEvidenceAvailable: true }, { failures: [] }), 'almost');
});
test('document percentage measures checklist coverage, with zero for an empty checklist', () => {
  assert.equal(load('getDocumentReadinessScore', { getFundingDocumentChecklist: () => [{complete:true},{complete:false}] })(), 50);
  assert.equal(load('getDocumentReadinessScore', { getFundingDocumentChecklist: () => [] })(), 0);
});
