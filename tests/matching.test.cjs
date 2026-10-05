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
test('only upfront unscoped charges are institution-wide fee evidence', () => {
  const isUpfrontInstitutionFee = load('isUpfrontInstitutionFee');
  const getInstitutionWideFeeItems = load('getInstitutionWideFeeItems', {
    getInstitutionFeeSchedules: () => [{
      items: [
        { name: 'Application fee' },
        { name: 'Transcript' },
        { programmeGroup: 'Diploma in Other Studies', name: 'Tuition' }
      ]
    }],
    isUpfrontInstitutionFee
  });
  assert.deepEqual(
    getInstitutionWideFeeItems('Example University').map((item) => item.name),
    ['Application fee']
  );
});
test('programme fee evidence requires a matched charge or its own supporting note', () => {
  const withoutMatches = load('hasProgrammeFeeEvidence', { getProgrammeFeeMatches: () => [] });
  const withMatches = load('hasProgrammeFeeEvidence', { getProgrammeFeeMatches: () => [{ name: 'Tuition' }] });
  assert.equal(withoutMatches({ institution: 'Example University' }), false);
  assert.equal(withoutMatches({ feeNote: 'Confirm with the institution.' }), true);
  assert.equal(withMatches({ institution: 'Example University' }), true);
});
test('unclassified application status is never promoted to a verified deadline', () => {
  const normalizeDeadlineStatus = load('normalizeDeadlineStatus');
  const plainStatus = normalizeDeadlineStatus('Admissions information has been captured.');
  const datedStatus = normalizeDeadlineStatus('Applications close 30 November 2026.');
  assert.equal(plainStatus.label, 'Status needs verification');
  assert.equal(plainStatus.tone, 'amber');
  assert.equal(plainStatus.isVerified, false);
  assert.equal(datedStatus.label, 'Verified deadline');
  assert.equal(datedStatus.isVerified, true);
});
