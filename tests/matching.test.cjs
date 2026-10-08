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
test('application fee summaries do not borrow another course tuition', () => {
  const getApplicationFeeSummary = load('getApplicationFeeSummary', {
    getInstitutionFeeSchedules: () => [{ items: [] }],
    getProgrammeFeeMatches: (programme) => programme.id === 'matching' ? [{ id: 'tuition', programmeGroup: 'Matching course', name: 'Tuition', amount: 1234 }] : [],
    unique: (items) => [...new Set(items)],
    getEvidenceFileLabel: () => '',
    formatFeeItem: (item) => `${item.programmeGroup}: ${item.amount}`,
    getSafeExternalUrl: () => ''
  });
  const summary = getApplicationFeeSummary('Example University', [{ id: 'unmatched', title: 'Unmatched course' }]);
  const matchedSummary = getApplicationFeeSummary('Example University', [{ id: 'matching', title: 'Matching course' }]);
  assert.equal(summary.label, 'Fees under review');
  assert.deepEqual(summary.lines, []);
  assert.deepEqual(matchedSummary.lines, ['Matching course: 1234']);
});
test('only captured application routes are presented as application links', () => {
  const getApplicationLinkPack = load('getApplicationLinkPack', {
    getInstitutionExplorerLinks: () => ({
      application: { label: 'Official university website', url: 'https://example.edu', kind: 'source' },
      allLinks: []
    }),
    dedupeLinks: (links) => links.filter((link) => link.url),
    getMatchProgrammeTitle: (programme) => programme.title || 'Programme',
    unique: (items) => [...new Set(items)],
    getEvidenceFileLabel: () => '',
    isProspectusLike: () => false
  });
  const sourceOnly = getApplicationLinkPack('Example University', []);
  const withApplication = getApplicationLinkPack('Example University', [{ title: 'Example Degree', applicationUrl: 'https://example.edu/apply' }]);
  assert.equal(sourceOnly.applicationLink, null);
  assert.equal(sourceOnly.fallbackLink.label, 'Official university website');
  assert.equal(withApplication.applicationLink.url, 'https://example.edu/apply');
});
test('institution application routes retain their application classification', () => {
  const getInstitutionApplicationLink = load('getInstitutionApplicationLink', {
    institutionApplicationLinks: [
      { pattern: /example university/i, label: 'Example application portal', url: 'https://example.edu/apply', kind: 'application' }
    ]
  });
  const route = getInstitutionApplicationLink('Example University');
  assert.equal(route.kind, 'application');
  assert.equal(route.url, 'https://example.edu/apply');
});
test('institution source labels preserve their stated authority', () => {
  const getInstitutionSourcesForExplorer = load('getInstitutionSourcesForExplorer', {
    sources: [{ name: 'Example University', type: 'Third-party profile', status: 'reference', url: 'https://example.edu/profile', tags: [] }],
    adminSources: []
  });
  assert.equal(getInstitutionSourcesForExplorer('Example University')[0].label, 'Third-party profile');
});
test('application details stay incomplete until route, timing, and documents are captured', () => {
  const getProgrammeApplicationDetails = load('getProgrammeApplicationDetails', {
    parseListText: () => [],
    getSafeExternalUrl: (value) => /^https?:\/\//.test(value || '') ? value : ''
  });
  const partial = getProgrammeApplicationDetails({ applicationUrl: 'https://example.edu/apply' });
  const complete = getProgrammeApplicationDetails({
    applicationUrl: 'https://example.edu/apply',
    applicationDeadline: '31 October 2026',
    applicationDocuments: ['Results certificate']
  });
  assert.equal(partial.readyCount, 1);
  assert.equal(partial.complete, false);
  assert.equal(complete.complete, true);
});
test('application detail filters identify the specific missing field', () => {
  const isApplicationDetailMissing = load('isApplicationDetailMissing', {
    getApplicationDetailCheck: (programme, key) => ({
      route: { ready: Boolean(programme.applicationUrl) },
      timing: { ready: Boolean(programme.applicationDeadline) },
      documents: { ready: Boolean(programme.applicationDocuments?.length) }
    })[key] || null
  });
  const partial = { applicationUrl: 'https://example.edu/apply' };
  assert.equal(isApplicationDetailMissing(partial, 'route'), false);
  assert.equal(isApplicationDetailMissing(partial, 'timing'), true);
  assert.equal(isApplicationDetailMissing(partial, 'documents'), true);
});
test('source review can only be recorded when a safe source trace exists', () => {
  const getProgrammeReviewableSources = load('getProgrammeReviewableSources', {
    getSafeExternalUrl: (value) => /^https?:\/\//.test(value || '') ? value : '',
    getEvidenceFileLabel: (value) => (!/^https?:\/\//.test(value || '') && !/under review/i.test(value || '') ? value : '')
  });
  const hasProgrammeReviewableSource = load('hasProgrammeReviewableSource', { getProgrammeReviewableSources });
  assert.equal(hasProgrammeReviewableSource({ sourceUrl: 'https://institution.example/prospectus' }), true);
  assert.equal(hasProgrammeReviewableSource({ supportingSourcePath: 'data/institution-prospectus.pdf' }), true);
  assert.equal(hasProgrammeReviewableSource({ sourceUrl: 'javascript:alert(1)' }), false);
  assert.equal(hasProgrammeReviewableSource({ sourceUrl: 'Source under review' }), false);
  assert.equal(hasProgrammeReviewableSource({ sourceNote: 'Someone said this is current.' }), false);
});
test('source freshness separates missing, unreviewed, due, overdue, and current evidence', () => {
  const now = new Date('2026-10-08T00:00:00Z').getTime();
  const getProgrammeSourceReviewState = load('getProgrammeSourceReviewState', {
    hasProgrammeReviewableSource: (programme) => Boolean(programme.sourceUrl),
    programmeFreshnessThresholds: { currentDays: 180, reviewSoonDays: 365 }
  });
  assert.equal(getProgrammeSourceReviewState({}, now), 'missing_source');
  assert.equal(getProgrammeSourceReviewState({ sourceUrl: 'https://institution.example' }, now), 'unreviewed');
  assert.equal(getProgrammeSourceReviewState({ sourceUrl: 'https://institution.example', reviewedAt: '2026-01-01T00:00:00Z' }, now), 'due');
  assert.equal(getProgrammeSourceReviewState({ sourceUrl: 'https://institution.example', reviewedAt: '2025-01-01T00:00:00Z' }, now), 'overdue');
  assert.equal(getProgrammeSourceReviewState({ sourceUrl: 'https://institution.example', reviewedAt: '2026-09-30T00:00:00Z' }, now), 'current');
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
