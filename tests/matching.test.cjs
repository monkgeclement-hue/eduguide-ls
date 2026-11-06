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
function loadAsync(name, globals) {
  const start = source.indexOf(`async function ${name}(`);
  assert.ok(start >= 0);
  const end = source.indexOf('\n}', start) + 2;
  const context = vm.createContext(globals);
  vm.runInContext(source.slice(start, end), context);
  return context;
}
function chatResetContext(fetchImpl) {
  const controls = Object.fromEntries(['#ai-clear-button', '#ai-guidance-button', '#ai-compare-button', '#ai-guidance-status', '#ai-question'].map((key) => [key, { disabled: false, textContent: '', value: 'Question' }]));
  const context = loadAsync('resetAiChatMessages', {
    qs: (selector) => controls[selector],
    fetch: fetchImpl,
    getAuthHeaders: () => ({}),
    getInitialAiChatMessage: () => ({ id: 'ai-welcome', role: 'assistant', content: 'Welcome' }),
    renderInterviewControls: () => {},
    saveAiChatMessages: () => {},
    renderAiChatMessages: () => {},
    authToken: 'session',
    serverDatabaseAvailable: true,
    aiChatResetVersion: 0,
    aiChatLoadedFromServer: true,
    aiInterviewState: { active: true },
    aiChatMessages: [{ id: 'old', role: 'user', content: 'Question' }]
  });
  return { context, controls };
}
test('chat reset waits for server confirmation before clearing the device copy', async () => {
  let resolveRequest;
  const { context, controls } = chatResetContext(() => new Promise((resolve) => { resolveRequest = resolve; }));
  const pending = context.resetAiChatMessages();
  assert.equal(context.aiChatMessages[0].id, 'old');
  assert.equal(controls['#ai-clear-button'].disabled, true);
  resolveRequest({ ok: true, json: async () => ({ ok: true }) });
  await pending;
  assert.equal(context.aiChatMessages[0].id, 'ai-welcome');
  assert.equal(context.aiChatResetVersion, 1);
  assert.equal(controls['#ai-clear-button'].disabled, false);
});
test('failed chat reset keeps the existing conversation and allows retry', async () => {
  for (const response of [{ ok: false, json: async () => ({ ok: false }) }, { ok: true, json: async () => ({ ok: false }) }]) {
    const { context, controls } = chatResetContext(async () => response);
    await context.resetAiChatMessages();
    assert.equal(context.aiChatMessages[0].id, 'old');
    assert.equal(context.aiChatResetVersion, 0);
    assert.match(controls['#ai-guidance-status'].textContent, /not cleared/);
    assert.equal(controls['#ai-clear-button'].disabled, false);
  }
});
test('AI guidance labels account sync failures without hiding the answer', () => {
  const status = load('getAiGuidanceStatus');
  assert.match(status('gemini', 'test', false), /could not fully sync/);
  assert.match(status('gemini', 'test', true), /Conversation context is active/);
  assert.match(status('local_fallback', null, false), /could not fully sync/);
});
test('failed account history load is shown and can retry', async () => {
  const status = { textContent: '' };
  const context = loadAsync('loadServerAiChatMessages', {
    authToken: 'session',
    serverDatabaseAvailable: true,
    aiChatLoadedFromServer: false,
    aiChatResetVersion: 0,
    getAuthHeaders: () => ({}),
    fetch: async () => ({ ok: false, json: async () => ({ detail: 'Storage unavailable' }) }),
    qs: () => status
  });
  await context.loadServerAiChatMessages();
  assert.equal(context.aiChatLoadedFromServer, false);
  assert.match(status.textContent, /could not load/);
});
test('server reply ID keeps a saved AI answer from appearing twice', () => {
  const normalizeAiChatMessage = load('normalizeAiChatMessage');
  const mergeAiChatMessages = load('mergeAiChatMessages', { normalizeAiChatMessage, maxAiChatMessages: 24 });
  const context = vm.createContext({
    normalizeAiChatMessage,
    aiChatMessages: [],
    maxAiChatMessages: 24,
    saveAiChatMessages: () => {},
    renderAiChatMessages: () => {}
  });
  const start = source.indexOf('function appendAiChatMessage(');
  const end = source.indexOf('\n}', start) + 2;
  vm.runInContext(source.slice(start, end), context);
  context.appendAiChatMessage('assistant', 'Detailed answer', '<p>Detailed answer</p>', 'server-reply');
  const combined = mergeAiChatMessages(context.aiChatMessages, [{ id: 'server-reply', role: 'assistant', content: 'Short answer' }]);
  assert.equal(combined.length, 1);
  assert.equal(combined[0].html, '<p>Detailed answer</p>');
});
function aiRequestContext(fetchImpl) {
  const controls = Object.fromEntries(['#ai-clear-button', '#ai-guidance-button', '#ai-compare-button', '#ai-guidance-status', '#ai-question', '#ai-language'].map((key) => [key, { disabled: false, textContent: '', value: '' }]));
  controls['#ai-question'].value = 'What can I study?';
  controls['#ai-language'].value = 'st';
  const context = loadAsync('requestAiGuidance', {
    qs: (selector) => controls[selector],
    getSelectedAiLanguage: () => controls['#ai-language'].value,
    fetch: fetchImpl,
    getAuthHeaders: () => ({}),
    getAiRequestErrorMessage: load('getAiRequestErrorMessage', { navigator: { onLine: true } }),
    getInitialAiChatMessage: () => ({ id: 'ai-welcome', role: 'assistant', content: 'Welcome' }),
    renderAiChatMessages: () => {},
    saveAiChatMessages: () => {},
    getAiProfilePayload: () => ({}),
    getNmdsReadiness: () => ({}),
    getAiMatchPayload: () => [{ id: 'course' }],
    getAiBlockedPayload: () => [],
    renderAiGuidance: () => { controls['#ai-guidance-status'].textContent = 'Answer shown'; },
    recordCurrentUserActivity: () => {},
    currentUser: { documents: [] },
    latestMatches: [{ id: 'course' }],
    aiInterviewState: { active: false },
    aiChatMessages: [{ id: 'ai-welcome', role: 'assistant', content: 'Welcome' }]
  });
  let nextId = 0;
  context.appendAiChatMessage = (role, content) => {
    const message = { id: `pending-${++nextId}`, role, content };
    context.aiChatMessages = [...context.aiChatMessages.filter((item) => item.id !== 'ai-welcome'), message];
    return message;
  };
  context.getAiConversationPayload = () => context.aiChatMessages.filter((item) => item.id !== 'ai-welcome');
  return { context, controls };
}
test('AI request sends the selected reply language without losing the question', async () => {
  let sent;
  const { context, controls } = aiRequestContext(async (_url, options) => {
    sent = JSON.parse(options.body);
    return { ok: true, json: async () => ({ guidance: {}, mode: 'gemini', model: 'test', language: 'st' }) };
  });
  await context.requestAiGuidance();
  assert.equal(sent.language, 'st');
  assert.equal(sent.question, 'What can I study?');
  assert.equal(controls['#ai-language'].disabled, false);
});
test('AI reply preference is scoped to the signed-in user and allowlisted', () => {
  const storageKey = load('getAiLanguageStorageKey', { aiLanguageStoragePrefix: 'language-v1', currentUser: { id: 'student-a' } });
  assert.equal(storageKey(), 'language-v1:student-a');
  const selected = { value: 'st' };
  const language = load('getSelectedAiLanguage', { qs: () => selected });
  assert.equal(language(), 'st');
  selected.value = 'unsupported';
  assert.equal(language(), 'en');
});
test('AI chat renders only the direct answer, not the old report sections', () => {
  let rendered = '';
  const controls = { '#ai-guidance-status': { textContent: '' } };
  const render = load('renderAiGuidance', {
    aiChatMessages: [{ id: 'ai-welcome', role: 'assistant', content: 'Welcome' }],
    escapeHtml: load('escapeHtml'),
    guidanceToConversationText: load('guidanceToConversationText'),
    appendAiChatMessage: (_role, _content, html) => { rendered = html; },
    qs: (selector) => controls[selector],
    getAiGuidanceStatus: () => 'Ready'
  });
  render({ summary: 'Long summary', direct_answer: 'Lumela! Nka u thusa joang?', document_checklist: ['Upload a transcript'], scholarship_note: 'Funding note' }, 'gemini', 'test', null, true, 'st');
  assert.match(rendered, /lang="st"/);
  assert.match(rendered, /Lumela! Nka u thusa joang\?/);
  assert.doesNotMatch(rendered, /Long summary|Upload a transcript|Funding note/);
});
test('follow-up actions offer the five requested topics', () => {
  const suggestions = load('getAiFollowupSuggestions')('st');
  assert.deepEqual(Array.from(suggestions, (item) => item.key), ['summary', 'answer', 'blockers', 'missing', 'study']);
  assert.equal(suggestions[0].label, 'Kakaretso');
});
test('fresh profile completion credits only information the student entered', () => {
  const completion = load('calculateProfileCompletion');
  assert.equal(completion({}), 0);
  assert.equal(completion({ name: 'Student', district: 'Maseru', grades: {}, interests: [] }), 10);
  assert.equal(completion({ name: 'Student', district: 'Maseru', leavingYear: '2026', stream: 'General', grades: { ENG: 'C' }, interests: [] }), 27);
});

test('fresh student dashboard asks for grades before documents', () => {
  const snapshot = load('getStudentDashboardSnapshot', {
    getProfileCompletion: () => 5,
    gradeState: {},
    interestState: new Set(),
    latestMatches: [],
    currentUser: { shortlist: [], documents: [] },
    qs: (selector) => ({ value: selector === '#full-name' ? 'Fresh Student' : '' })
  })();
  assert.equal(snapshot.nextActionLabel, 'Add grades');
  assert.match(snapshot.nextActions[0], /Add your subject grades/);
  assert.ok(snapshot.nextActions.every((action) => !/documents|interest/i.test(action)));
});
test('General stream is neutral when no interest was selected', () => {
  const getInterestScore = load('getInterestScore', { interestState: new Set(), getPreferenceScore: () => 0, clamp: (value) => value });
  assert.equal(getInterestScore({ interests: ['Technology & IT'] }), 50);
  assert.equal(getInterestScore({ interests: ['Arts & Design'] }), 50);
});
test('unentered strict grades are unknown, not failed', () => {
  const evaluate = load('evaluateStrictGates', {
    getStrictGateRules: () => [{ codes: ['MATH'], minGrade: 'C' }],
    gradeMeets: () => false,
    getGradeForSubject: () => '',
    getSubjectLabel: (code) => code
  });
  const result = evaluate({});
  assert.equal(result.failures.length, 0);
  assert.equal(result.unknown.length, 1);
  assert.equal(result.passed, false);
});
test('failed AI request keeps the draft and removes the pending chat turn', async () => {
  const { context, controls } = aiRequestContext(async () => ({ ok: false, status: 429 }));
  await context.requestAiGuidance();
  assert.equal(controls['#ai-question'].value, 'What can I study?');
  assert.equal(controls['#ai-question'].disabled, false);
  assert.equal(context.aiChatMessages.length, 1);
  assert.equal(context.aiChatMessages[0].id, 'ai-welcome');
  assert.match(controls['#ai-guidance-status'].textContent, /Too many AI requests/);
  assert.equal(controls['#ai-guidance-button'].disabled, false);
});
test('retry after an AI failure submits the question only once', async () => {
  let attempts = 0;
  const { context, controls } = aiRequestContext(async () => {
    attempts += 1;
    return attempts === 1
      ? { ok: false, status: 503 }
      : { ok: true, json: async () => ({ mode: 'gemini', model: 'test', guidance: {} }) };
  });
  await context.requestAiGuidance();
  await context.requestAiGuidance();
  assert.equal(attempts, 2);
  assert.equal(context.aiChatMessages.filter((item) => item.role === 'user').length, 1);
  assert.equal(controls['#ai-question'].value, '');
});
test('activity logging failure does not discard a delivered AI answer', async () => {
  const { context, controls } = aiRequestContext(async () => ({ ok: true, json: async () => ({ mode: 'gemini', model: 'test', guidance: {} }) }));
  context.recordCurrentUserActivity = () => { throw new Error('activity storage unavailable'); };
  await context.requestAiGuidance();
  assert.equal(controls['#ai-guidance-status'].textContent, 'Answer shown');
  assert.equal(controls['#ai-question'].value, '');
  assert.equal(context.aiChatMessages.filter((item) => item.role === 'user').length, 1);
});
test('AI request errors distinguish session, rate limit, service, and offline failures', () => {
  const online = load('getAiRequestErrorMessage', { navigator: { onLine: true } });
  const offline = load('getAiRequestErrorMessage', { navigator: { onLine: false } });
  assert.match(online({ status: 401 }), /Sign in again/);
  assert.match(online({ status: 429 }), /Too many AI requests/);
  assert.match(online({ status: 503 }), /temporarily unavailable/);
  assert.match(offline({}), /offline/);
});
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
test('programme fee evidence requires a course amount, not a source note or an application fee', () => {
  const hasFeeItemAmount = load('hasFeeItemAmount');
  const withoutMatches = load('hasProgrammeFeeEvidence', { getProgrammeFeeMatches: () => [], hasFeeItemAmount });
  const withApplicationFee = load('hasProgrammeFeeEvidence', {
    getProgrammeFeeMatches: () => [{ name: 'Application fee', amount: 450 }],
    hasFeeItemAmount
  });
  const withTuition = load('hasProgrammeFeeEvidence', {
    getProgrammeFeeMatches: () => [{ programmeGroup: 'Diploma in Nursing', name: 'Tuition', amount: 12000 }],
    hasFeeItemAmount
  });
  assert.equal(withoutMatches({ institution: 'Example University' }), false);
  assert.equal(withoutMatches({ feeNote: 'Confirm with the institution.' }), false);
  assert.equal(withoutMatches({ feeNote: 'Fee schedule available: 2024/25. Confirm the amount.' }), false);
  assert.equal(withoutMatches({ supportingFeeSourcePath: '/fees.pdf' }), false);
  assert.equal(withoutMatches({ feeNote: 'Tuition is LSL 15,640 per year.' }), true);
  assert.equal(withoutMatches({ feeNote: 'Tuition is M15,640 per year.' }), true);
  assert.equal(withApplicationFee({ institution: 'Example University' }), false);
  assert.equal(withTuition({ institution: 'Example University' }), true);
});
test('fee matches do not borrow another course tuition from the same faculty', () => {
  const normalizeFeeText = load('normalizeFeeText');
  const hasFeeTextOverlap = load('hasFeeTextOverlap', { normalizeFeeText });
  const getProgrammeDisplayName = load('getProgrammeDisplayName');
  const scoreFeeItemForProgramme = load('scoreFeeItemForProgramme', { hasFeeTextOverlap, getProgrammeDisplayName });
  const isProgrammeFeeGroupMatch = load('isProgrammeFeeGroupMatch', { normalizeFeeText, getProgrammeDisplayName });
  const getProgrammeFeeMatches = load('getProgrammeFeeMatches', {
    getInstitutionFeeSchedules: () => [{ items: [
      { programmeGroup: 'Diploma in Nursing', faculty: 'Health', name: 'Tuition', amount: 12000 },
      { programmeGroup: 'Diploma in Pharmacy', faculty: 'Health', name: 'Tuition', amount: 18000 },
      { programmeGroup: 'Diploma in Information Technology', faculty: 'Health', name: 'Tuition', amount: 107036 }
    ] }],
    getInstitutionWideFeeItems: () => [{ name: 'Application fee', amount: 450 }],
    scoreFeeItemForProgramme,
    getProgrammeDisplayName,
    hasFeeTextOverlap,
    isProgrammeFeeGroupMatch
  });
  assert.deepEqual(
    Array.from(getProgrammeFeeMatches({ institution: 'Example University', name: 'Diploma in Nursing', faculty: 'Health' }), (item) => item.programmeGroup || item.name),
    ['Diploma in Nursing', 'Application fee']
  );
  assert.deepEqual(
    Array.from(getProgrammeFeeMatches({ institution: 'Example University', name: 'BSc in Business Information Technology', faculty: 'Health' }), (item) => item.programmeGroup || item.name),
    ['Application fee']
  );
  assert.equal(isProgrammeFeeGroupMatch({ name: 'BSc in Consumer Science' }, 'BSc Consumer Science'), true);
});
test('Limkokwing captured amounts apply only to the three supplied courses', () => {
  const context = { window: {} };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '..', 'data', 'admin-catalog.js'), 'utf8'), context);
  const { programmes, fees } = context.window.EDUGUIDE_ADMIN_DATA;
  const getInstitutionFeeSchedules = load('getInstitutionFeeSchedules', { adminFees: fees });
  const isUpfrontInstitutionFee = load('isUpfrontInstitutionFee');
  const getInstitutionWideFeeItems = load('getInstitutionWideFeeItems', { getInstitutionFeeSchedules, isUpfrontInstitutionFee });
  const normalizeFeeText = load('normalizeFeeText');
  const hasFeeTextOverlap = load('hasFeeTextOverlap', { normalizeFeeText });
  const getProgrammeDisplayName = load('getProgrammeDisplayName');
  const scoreFeeItemForProgramme = load('scoreFeeItemForProgramme', { hasFeeTextOverlap, getProgrammeDisplayName });
  const isProgrammeFeeGroupMatch = load('isProgrammeFeeGroupMatch', { normalizeFeeText, getProgrammeDisplayName });
  const getProgrammeFeeMatches = load('getProgrammeFeeMatches', {
    getInstitutionFeeSchedules, getInstitutionWideFeeItems, scoreFeeItemForProgramme,
    getProgrammeDisplayName, hasFeeTextOverlap, isProgrammeFeeGroupMatch
  });
  const hasFeeItemAmount = load('hasFeeItemAmount');
  const hasProgrammeFeeEvidence = load('hasProgrammeFeeEvidence', { getProgrammeFeeMatches, hasFeeItemAmount });
  const limkokwing = programmes.filter((item) => item.institution === 'Limkokwing University Lesotho');
  assert.deepEqual(
    Array.from(limkokwing.filter(hasProgrammeFeeEvidence), (item) => item.name).sort(),
    ['Diploma in Broadcasting Radio & TV', 'Diploma in Events Management', 'Diploma in Information Technology']
  );
  assert.equal(getProgrammeFeeMatches(limkokwing.find((item) => item.name === 'Diploma in Information Technology'))[0].amount, 107036);
  assert.equal(getProgrammeFeeMatches(limkokwing.find((item) => item.name === 'BSc in Information Technology')).length, 0);
});
test('application fee summaries do not borrow another course tuition', () => {
  const hasFeeItemAmount = load('hasFeeItemAmount');
  const feeMatches = (programme) => programme.id === 'matching'
    ? [{ id: 'tuition', programmeGroup: 'Matching course', name: 'Tuition', amount: 1234 }]
    : programme.id === 'application' ? [{ id: 'application', name: 'Application fee', amount: 450 }] : [];
  const hasProgrammeFeeEvidence = load('hasProgrammeFeeEvidence', { getProgrammeFeeMatches: feeMatches, hasFeeItemAmount });
  const getApplicationFeeSummary = load('getApplicationFeeSummary', {
    getInstitutionFeeSchedules: () => [{ items: [] }],
    getProgrammeFeeMatches: feeMatches,
    hasProgrammeFeeEvidence,
    hasFeeItemAmount,
    unique: (items) => [...new Set(items)],
    getEvidenceFileLabel: () => '',
    formatFeeItem: (item) => `${item.programmeGroup}: ${item.amount}`,
    getSafeExternalUrl: () => ''
  });
  const summary = getApplicationFeeSummary('Example University', [{ id: 'unmatched', title: 'Unmatched course' }]);
  const matchedSummary = getApplicationFeeSummary('Example University', [{ id: 'matching', title: 'Matching course' }]);
  const noteOnly = getApplicationFeeSummary('Example University', [{ id: 'unmatched', feeNote: 'Confirm the current fees.' }]);
  const applicationOnly = getApplicationFeeSummary('Example University', [{ id: 'application' }]);
  assert.equal(summary.label, 'Fees under review');
  assert.deepEqual(summary.lines, []);
  assert.equal(noteOnly.label, 'Fees under review');
  assert.equal(applicationOnly.label, 'Other charges captured');
  assert.equal(matchedSummary.label, 'Course fees captured');
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
  assert.equal(hasProgrammeReviewableSource({ sourceFile: 'siac-prospectus-2025-2026.pdf' }), true);
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
  assert.equal(getProgrammeSourceReviewState({ sourceUrl: 'https://institution.example', reviewedAt: '2025-01-01T00:00:00Z', sourceCheckedAt: '2026-09-30T00:00:00Z' }, now), 'current');
});
test('application packs warn before students act on stale or unchecked source details', () => {
  const getApplicationSourceConfidence = load('getApplicationSourceConfidence', {
    getSourceFreshnessMeta: (programme) => programme.sourceMeta
  });
  const current = getApplicationSourceConfidence([
    { sourceMeta: { tone: 'green', label: 'Source checked recently' } },
    { sourceMeta: { tone: 'green', label: 'Source checked recently' } }
  ]);
  const due = getApplicationSourceConfidence([
    { sourceMeta: { tone: 'green', label: 'Source checked recently' } },
    { sourceMeta: { tone: 'amber', label: 'Source review due' } }
  ]);
  const overdue = getApplicationSourceConfidence([
    { sourceMeta: { tone: 'red', label: 'Source review overdue' } }
  ]);
  assert.equal(current.label, 'Sources checked recently');
  assert.equal(current.tone, 'green');
  assert.equal(due.label, 'Confirm latest details');
  assert.match(due.detail, /before you apply or pay/);
  assert.equal(overdue.label, 'Confirm before acting');
  assert.match(overdue.detail, /fees, deadlines, requirements, and application routes/);
});
test('application packs contain only qualified and almost-qualified programmes', () => {
  const groups = [
    { institution: 'Mixed College', programmes: [
      { id: 'qualified', match: { tier: 'qualified' } },
      { id: 'explore', match: { tier: 'explore' } },
      { id: 'almost', match: { tier: 'almost' } }
    ] },
    { institution: 'Explore College', programmes: [{ id: 'explore-only', match: { tier: 'explore' } }] }
  ];
  const all = load('getApplicationMatchGroups', {
    applicationSavedOnly: false,
    currentUser: { shortlist: ['almost'] },
    matchesApplicationFilters: () => true
  });
  const saved = load('getApplicationMatchGroups', {
    applicationSavedOnly: true,
    currentUser: { shortlist: ['almost'] },
    matchesApplicationFilters: () => true
  });
  assert.deepEqual(all(groups).map((group) => [group.institution, group.programmes.map((item) => item.id)]),
    [['Mixed College', ['qualified', 'almost']]]);
  assert.deepEqual(saved(groups).map((group) => group.programmes.map((item) => item.id)), [['almost']]);
});
test('explore-only matches never produce an application pack', () => {
  const explore = { id: 'explore-only', match: { tier: 'explore' } };
  const groups = [{ institution: 'Explore College', programmes: [explore] }];
  const getApplicationMatchGroups = load('getApplicationMatchGroups', {
    applicationSavedOnly: false,
    currentUser: { shortlist: [] },
    matchesApplicationFilters: () => true
  });
  const renderApplicationAssistant = load('renderApplicationAssistant', {
    getApplicationMatchGroups,
    getInstitutionMatchGroups: () => groups,
    getUniqueApplicationProgrammes: (items) => items,
    applicationSavedOnly: false,
    applicationFiltersActive: () => false,
    latestMatches: [explore]
  });
  const markup = renderApplicationAssistant();
  assert.match(markup, /Explore-only paths are for discovery/);
  assert.doesNotMatch(markup, /application-card-list/);
});
test('results tabs keep selection, focus order, and visible panel in sync', () => {
  function makeElement(id, tabName) {
    const classes = new Set();
    return {
      id, dataset: { resultsTab: tabName }, classes, attributes: {}, tabIndex: -1, focused: false,
      classList: { toggle(name, active) { if (active) classes.add(name); else classes.delete(name); } },
      setAttribute(name, value) { this.attributes[name] = value; },
      focus() { this.focused = true; }
    };
  }
  const tabs = [makeElement('results-tab-programmes', 'programmes'), makeElement('results-tab-applications', 'applications')];
  const panels = [makeElement('tab-programmes'), makeElement('tab-applications')];
  const setResultsTab = load('setResultsTab', {
    qsa: (selector) => selector === '[data-results-tab]' ? tabs : panels
  });
  setResultsTab('applications', { focus: true });
  assert.equal(tabs[0].attributes['aria-selected'], 'false');
  assert.equal(tabs[0].tabIndex, -1);
  assert.equal(tabs[1].attributes['aria-selected'], 'true');
  assert.equal(tabs[1].tabIndex, 0);
  assert.equal(tabs[1].focused, true);
  assert.equal(panels[0].classes.has('active'), false);
  assert.equal(panels[1].classes.has('active'), true);
});
test('changing a linked source gives a programme a new source fingerprint', () => {
  const getProgrammeSourceFingerprint = load('getProgrammeSourceFingerprint');
  const original = getProgrammeSourceFingerprint({
    sourceUrl: 'https://institution.example/prospectus-2025.pdf',
    supportingFeeSourcePath: '/source-documents/fees-2025.pdf'
  });
  const changed = getProgrammeSourceFingerprint({
    sourceUrl: 'https://institution.example/prospectus-2026.pdf',
    supportingFeeSourcePath: '/source-documents/fees-2025.pdf'
  });
  assert.notEqual(changed, original);
});
test('college discovery leads stay unverified until a recent official source check exists', () => {
  const getCollegeResearchLeadEvidence = load('getCollegeResearchLeadEvidence', {
    getSafeExternalUrl: (value) => /^https?:\/\//.test(value || '') ? value : '',
    programmeFreshnessThresholds: { currentDays: 180 }
  });
  assert.equal(getCollegeResearchLeadEvidence({ leadSourceUrl: 'https://facebook.example/college' }).ready, false);
  assert.equal(
    getCollegeResearchLeadEvidence({ officialSourceUrl: 'https://college.example/prospectus', sourceCheckedAt: new Date().toISOString() }).ready,
    true
  );
  assert.equal(
    getCollegeResearchLeadEvidence({ officialSourceUrl: 'https://college.example/prospectus', sourceCheckedAt: '2025-01-01T00:00:00Z' }).ready,
    false
  );
});
test('official directory starters omit institutions already queued for research', () => {
  const getAvailableCollegeResearchStarters = load('getAvailableCollegeResearchStarters', {
    officialCollegeResearchStarters: [
      { id: 'one', institution: 'College One' },
      { id: 'two', institution: 'College Two' }
    ],
    collegeResearchLeads: []
  });
  assert.deepEqual(
    getAvailableCollegeResearchStarters([{ institution: 'college one' }]).map((starter) => starter.id),
    ['two']
  );
});
test('official research starters keep regulator audit leads in the checking workflow', () => {
  const source = require('node:fs').readFileSync('app.js', 'utf8');
  assert.match(source, /Lesotho China Fellowship Collegiate/);
  assert.match(source, /Machabeng College/);
  assert.match(source, /CHE's institutional audit register/);
  assert.match(source, /status: "checking"/);
});
test('source review groups only records with the exact same linked source', () => {
  const getProgrammeSourceReviewGroup = load('getProgrammeSourceReviewGroup', {
    adminProgrammes: [
      { id: 'one', sourceUrl: 'https://institution.example/programmes' },
      { id: 'two', sourceUrl: 'https://institution.example/programmes' },
      { id: 'three', sourceUrl: 'https://institution.example/other-programmes' }
    ],
    getProgrammeReviewableSources: (programme) => programme.sourceUrl ? [programme.sourceUrl] : []
  });
  assert.deepEqual(
    Array.from(getProgrammeSourceReviewGroup({ id: 'one', sourceUrl: 'https://institution.example/programmes' })).map((item) => item.id),
    ['one', 'two']
  );
});
test('source report queues separate active triage from resolved history', () => {
  const getSourceReportQueueGroups = load('getSourceReportQueueGroups');
  const groups = getSourceReportQueueGroups([
    { id: 'open', status: 'open' },
    { id: 'progress', status: 'in_progress' },
    { id: 'resolved', status: 'resolved' }
  ]);
  assert.deepEqual(groups.active.map((report) => report.id), ['open', 'progress']);
  assert.deepEqual(groups.resolved.map((report) => report.id), ['resolved']);
});
test('supplied prospectuses need a current official URL before they can be approved', () => {
  const requiresCurrentCandidateEvidence = load('requiresCurrentCandidateEvidence', {
    currentEvidenceCandidateSourceTypes: new Set([
      'official_regulator_historical_pdf',
      'supplied_institution_prospectus_pdf',
      'manual_user_confirmation_prospectus_pdf'
    ])
  });
  const getCandidateEvidenceStatus = load('getCandidateEvidenceStatus', {
    requiresCurrentCandidateEvidence,
    getSafeExternalUrl: (value) => /^https?:\/\//.test(value || '') ? value : '',
    programmeFreshnessThresholds: { currentDays: 180 }
  });
  const getProgrammeApprovalBlocker = load('getProgrammeApprovalBlocker', { getCandidateEvidenceStatus });
  const candidate = {
    sourceType: 'supplied_institution_prospectus_pdf',
    sourceUrl: '/source-documents/siac-prospectus-2025-2026.pdf',
    duration: '3 years'
  };
  assert.equal(getCandidateEvidenceStatus(candidate).candidateLabel, 'Supplied prospectus candidate');
  assert.match(getProgrammeApprovalBlocker(candidate), /current official source URL/);
  const currentSource = { ...candidate, sourceUrl: 'https://institution.example/current-prospectus' };
  assert.match(getProgrammeApprovalBlocker(currentSource), /checked today/);
  assert.equal(getProgrammeApprovalBlocker({ ...currentSource, sourceCheckedAt: new Date().toISOString() }), '');
  assert.match(
    getProgrammeApprovalBlocker({ ...currentSource, sourceCheckedAt: '2025-01-01T00:00:00Z' }),
    /checked today/
  );
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
