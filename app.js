const catalog = window.EDUGUIDE_DATA;
const { subjects, interests, sources, programmes, labourNotes } = catalog;
const adminData = window.EDUGUIDE_ADMIN_DATA || {
  summary: {},
  institutions: [],
  programmes: [],
  fees: [],
  dataGaps: [],
  sources: []
};

const gradeValues = ["", "A*", "A", "B", "C", "D", "E", "F", "G", "X", "Z"];
const gradePoints = { "A*": 8, A: 7, B: 6, C: 5, D: 4, E: 3, F: 2, G: 1, X: 0, Z: 0 };
const defaultCreditGrade = "C";
const defaultPassGrade = "D";
const tierMeta = {
  qualified: { label: "Qualified", badge: "green", rank: 0 },
  almost: { label: "Almost", badge: "amber", rank: 1 },
  explore: { label: "Explore", badge: "blue", rank: 2 },
  blocked: { label: "Not eligible yet", badge: "red", rank: 3 }
};
const gradeState = {};
const interestState = new Set(["Technology & IT", "Natural Sciences"]);
let latestMatches = [];
let latestBlockedMatches = [];
let selectedResultInstitution = null;
let adminProgrammes = structuredClone(adminData.programmes || []);
let adminGaps = structuredClone(adminData.dataGaps || []);
let adminFees = structuredClone(adminData.fees || []);
let adminSources = structuredClone(adminData.sources || []);
let adminState = {
  tab: "catalogue",
  search: "",
  institution: "all",
  status: "all",
  selectedProgrammeId: adminProgrammes[0]?.id || null,
  selectedUserId: null,
  editingProgrammeId: null
};

const persistenceKey = "eduguide-admin-review-state-v1";
const authUsersKey = "eduguide-auth-users-v1";
const authSessionKey = "eduguide-auth-session-v1";
const authTokenKey = "eduguide-auth-token-v1";
const aiChatStoragePrefix = "eduguide-ai-chat-v1";
const legacyDemoEmails = new Set();
const legacyDemoIds = new Set(["demo-student", "demo-admin"]);
const defaultUsers = [];
const adminRoles = new Set(["owner", "admin"]);
const maxActivityItems = 45;
const maxAiChatMessages = 24;
const calibrationProfiles = {
  arts: {
    label: "Arts / no science",
    stream: "General",
    grades: { ENG: "C", SES: "B", HIST: "C", REL: "B" },
    interests: ["Law & Government", "Social Work", "Arts & Design"],
    incomeBand: "mid",
    needSignals: [],
    preferenceText: "I enjoy reading, writing, helping people, public issues, and humanities. I do not have Mathematics or science results captured yet."
  },
  mathTech: {
    label: "Math + tech interest",
    stream: "Science",
    grades: { MATH: "B", ENG: "C", SES: "C", CSK: "B" },
    interests: ["Technology & IT", "Business & Finance"],
    incomeBand: "mid",
    needSignals: [],
    preferenceText: "I like computers and business systems. I have Mathematics, but no Physical Science captured yet."
  },
  stem: {
    label: "STEM ready",
    stream: "Science",
    grades: { MATH: "B", ENG: "C", PSCI: "B", CSK: "B", BIO: "C" },
    interests: ["Technology & IT", "Engineering", "Natural Sciences"],
    incomeBand: "mid",
    needSignals: [],
    preferenceText: "I want technology, engineering, architecture, or science options and I have Mathematics plus Physical Science."
  },
  health: {
    label: "Nursing / health",
    stream: "Science",
    grades: { ENG: "C", MATH: "D", BIO: "C", PSCI: "C", FNU: "C" },
    interests: ["Health & Medicine", "Social Work"],
    incomeBand: "low",
    needSignals: ["rural_remote"],
    preferenceText: "I want nursing, midwifery, health information, or another health pathway."
  },
  business: {
    label: "Business / accounting",
    stream: "Commercial",
    grades: { ENG: "C", MATH: "C", ACC: "B", ECON: "C", SES: "C" },
    interests: ["Business & Finance"],
    incomeBand: "mid",
    needSignals: [],
    preferenceText: "I like accounting, business, finance, management, and entrepreneurship."
  },
  agriculture: {
    label: "Agriculture / food",
    stream: "Agriculture",
    grades: { ENG: "D", AGR: "B", BIO: "C", FNU: "C", MATH: "D" },
    interests: ["Agriculture", "Natural Sciences"],
    incomeBand: "low",
    needSignals: ["rural_remote", "low_support"],
    preferenceText: "I am interested in farming, food, nutrition, agribusiness, animals, crops, and community agriculture work."
  }
};

let authUsers = structuredClone(defaultUsers);
let currentUser = null;
let authToken = localStorage.getItem(authTokenKey) || null;
let authMode = "login";
let deferredInstallPrompt = null;
const supabaseConfig = window.EDUGUIDE_SUPABASE_CONFIG || {};
const supabaseClient =
  supabaseConfig.url && supabaseConfig.anonKey && window.supabase
    ? window.supabase.createClient(supabaseConfig.url, supabaseConfig.anonKey)
    : null;
let persistenceMode = supabaseClient ? "supabase" : "local";
let lastPersistenceMessage = supabaseClient ? "Supabase sync ready" : "Local prototype mode";
let serverDatabaseAvailable = false;
let databaseLoadedAuthUsers = false;
let databaseLoadedReviewState = false;

const titles = {
  student: "Student Dashboard",
  results: "Recommendation Results",
  ai: "EduGuide AI",
  admin: "Admin Dashboard",
  sources: "Data Sources"
};

const subjectAliasRules = [
  { code: "MATH", label: "Mathematics", patterns: ["mathematics", "maths", "math", "statistics"] },
  { code: "ENG", label: "English", patterns: ["english", "english language"] },
  { code: "SES", label: "Sesotho", patterns: ["sesotho"] },
  { code: "PSCI", label: "Physical Science", patterns: ["physical science", "physical sciences", "double science", "double sciences", "physics and chemistry"] },
  { code: "CSK", label: "Computer Skills", patterns: ["computer skills", "computer studies", "computer literacy", "computer applications", "ict skills", "information and communication technology"] },
  { code: "PHY", label: "Physics", patterns: ["physics", "physical science", "physical sciences"] },
  { code: "CHEM", label: "Chemistry", patterns: ["chemistry", "chemical science"] },
  { code: "BIO", label: "Biology", patterns: ["biology", "life science", "health science"] },
  { code: "ACC", label: "Accounting", patterns: ["accounting", "accounts", "audit", "auditing"] },
  { code: "ECON", label: "Economics", patterns: ["economics", "economy"] },
  { code: "LIT", label: "English Literature", patterns: ["literature", "english literature"] },
  { code: "FNU", label: "Food & Nutrition", patterns: ["food and nutrition", "food & nutrition", "food nutrition", "nutrition", "food studies", "home economics", "consumer science"] },
  { code: "REL", label: "Religious Knowledge", patterns: ["religious knowledge", "religion", "religious education", "divinity", "bible knowledge"] },
  { code: "HIST", label: "History", patterns: ["history", "government", "law", "legal"] },
  { code: "GEO", label: "Geography", patterns: ["geography", "planning", "environment", "urban"] },
  { code: "AGR", label: "Agriculture", patterns: ["agriculture", "crop", "animal", "soil", "farm"] }
];

const domainProfiles = [
  {
    key: "technology",
    keywords: ["computer", "software", "information technology", "ict", "data", "network", "cyber", "multimedia", "web", "digital"],
    interests: ["Technology & IT", "Natural Sciences"],
    subjects: ["MATH", "ENG", "PSCI", "CSK"],
    careers: ["Software Developer", "Systems Analyst", "IT Support Specialist", "Data Analyst"],
    skills: ["Programming", "Database management", "Networking", "Problem solving"],
    sector: "Information & Communications Technology",
    priority: 86
  },
  {
    key: "health",
    keywords: ["nursing", "midwifery", "health", "medical", "pharmacy", "clinical", "nutrition", "dietetics"],
    interests: ["Health & Medicine", "Social Work"],
    subjects: ["ENG", "BIO", "PSCI", "FNU", "MATH"],
    careers: ["Nurse", "Community Health Worker", "Clinic Officer", "Health Programme Assistant"],
    skills: ["Patient care", "Biology", "Communication", "Record keeping"],
    sector: "Health & Social Services",
    priority: 88
  },
  {
    key: "engineering",
    keywords: ["engineering", "electrical", "civil", "mechanical", "architecture", "construction", "survey", "built environment"],
    interests: ["Engineering", "Natural Sciences"],
    subjects: ["MATH", "ENG", "PSCI"],
    careers: ["Engineer", "Technician", "Project Officer", "Construction Supervisor"],
    skills: ["Technical drawing", "Mathematics", "Project planning", "Problem solving"],
    sector: "Engineering & Construction",
    priority: 87
  },
  {
    key: "business",
    keywords: ["accounting", "finance", "business", "commerce", "management", "entrepreneurship", "marketing", "economics", "procurement"],
    interests: ["Business & Finance"],
    subjects: ["MATH", "ENG", "ACC", "ECON"],
    careers: ["Accountant", "Financial Analyst", "Business Manager", "Entrepreneur"],
    skills: ["Financial reporting", "Business planning", "Data analysis", "Ethics"],
    sector: "Financial Services",
    priority: 74
  },
  {
    key: "agriculture",
    keywords: ["agriculture", "crop", "animal", "soil", "horticulture", "farm", "agribusiness", "food", "consumer science"],
    interests: ["Agriculture", "Natural Sciences"],
    subjects: ["ENG", "BIO", "PSCI", "AGR", "FNU"],
    careers: ["Agricultural Extension Officer", "Farm Manager", "Agribusiness Officer", "Field Technician"],
    skills: ["Crop production", "Soil management", "Field research", "Agribusiness"],
    sector: "Agriculture",
    priority: 82
  },
  {
    key: "education",
    keywords: ["education", "teaching", "teacher", "pedagogy", "early childhood", "primary", "secondary"],
    interests: ["Education & Teaching", "Social Work"],
    subjects: ["ENG", "SES", "MATH", "REL"],
    careers: ["Teacher", "Education Officer", "Curriculum Assistant", "Training Facilitator"],
    skills: ["Lesson planning", "Communication", "Assessment", "Classroom management"],
    sector: "Education",
    priority: 78
  },
  {
    key: "law",
    keywords: ["law", "legal", "governance", "public administration", "political", "policing"],
    interests: ["Law & Government", "Social Work"],
    subjects: ["ENG", "HIST", "SES", "REL"],
    careers: ["Legal Assistant", "Policy Officer", "Public Administrator", "Compliance Officer"],
    skills: ["Research", "Writing", "Advocacy", "Critical thinking"],
    sector: "Public Administration & Law",
    priority: 70
  },
  {
    key: "creative",
    keywords: ["design", "fashion", "media", "arts", "film", "communication", "broadcast", "journalism", "animation"],
    interests: ["Arts & Design", "Technology & IT"],
    subjects: ["ENG", "LIT"],
    careers: ["Designer", "Media Producer", "Content Creator", "Communications Officer"],
    skills: ["Creativity", "Digital production", "Communication", "Portfolio development"],
    sector: "Creative & Media",
    priority: 64
  },
  {
    key: "social",
    keywords: ["social", "psychology", "sociology", "development", "community", "humanities"],
    interests: ["Social Work", "Law & Government"],
    subjects: ["ENG", "SES", "HIST", "REL"],
    careers: ["Social Worker", "Community Development Officer", "Research Assistant", "NGO Programme Officer"],
    skills: ["Case work", "Research", "Communication", "Community engagement"],
    sector: "Health & Social Services",
    priority: 72
  }
];

const fundingNeedSignals = {
  low_support: { label: "Limited family support", points: 10 },
  rural_remote: { label: "Rural or remote area", points: 7 },
  orphan_vulnerable: { label: "Orphan or vulnerable background", points: 12 },
  disability_health: { label: "Disability or health support need", points: 8 }
};

const fundingDocumentChecks = [
  { key: "results", label: "Certificates, results slip, or transcript" },
  { key: "identity", label: "National ID, passport, or birth certificate" },
  { key: "applicationEvidence", label: "Admission, application, or registration evidence" },
  { key: "bankDetails", label: "Bank account confirmation" },
  { key: "residenceGuarantor", label: "Residence/chief letter or guarantor evidence" },
  { key: "conditionalEvidence", label: "Prior NMDS, CHE evaluation, CV, or study leave if applicable" }
];

function qs(selector) {
  return document.querySelector(selector);
}

function qsa(selector) {
  return Array.from(document.querySelectorAll(selector));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatStatus(value) {
  return (value || "unknown").replaceAll("_", " ");
}

function formatMoney(value, currency = "LSL") {
  if (value === null || value === undefined || value === "") return "Amount missing";
  return `${currency} ${Number(value).toLocaleString("en-LS")}`;
}

function shortText(value, fallback = "Not captured") {
  return value ? escapeHtml(value) : `<span class="muted-inline">${fallback}</span>`;
}

function makeSlug(value) {
  return String(value || "record")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

function parseListText(value) {
  return String(value || "")
    .split(/[\n,;]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function formatListText(values = []) {
  return (values || []).join("\n");
}

function normalizeEmail(value) {
  return String(value || "").trim().toLowerCase();
}

function generateUserId(prefix = "user") {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
}

function getInitials(name, email = "") {
  const source = String(name || email || "Student").trim();
  const parts = source.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  return source.slice(0, 2).toUpperCase();
}

function isLegacyDemoUser(user = {}) {
  return legacyDemoIds.has(user.id) || legacyDemoEmails.has(normalizeEmail(user.email));
}

function isAdminRole(role) {
  return adminRoles.has(role);
}

function isAdmin(user = currentUser) {
  return isAdminRole(user?.role);
}

function isOwner(user = currentUser) {
  return user?.role === "owner";
}

function getUserRoleLabel(user = {}) {
  if (user.role === "owner") return "System Admin";
  if (user.role === "admin") return "Admin";
  return "Student";
}

function getVisibleUsers() {
  return authUsers.filter((user) => !isLegacyDemoUser(user));
}

function hasAdminUser(users = authUsers) {
  return users.some((user) => isAdmin(user) && user.status !== "suspended" && !isLegacyDemoUser(user));
}

function getAuthHeaders(extra = {}) {
  return authToken ? { ...extra, Authorization: `Bearer ${authToken}` } : extra;
}

function normalizeUser(user = {}) {
  if (!user?.email || isLegacyDemoUser(user)) return null;
  const createdAt = user.createdAt || user.registeredAt || new Date().toISOString();
  const activity = Array.isArray(user.activity) ? user.activity.slice(0, maxActivityItems) : [];
  return {
    id: user.id || generateUserId("user"),
    name: String(user.name || user.email || "Student").trim(),
    email: normalizeEmail(user.email),
    password: String(user.password || ""),
    role: isAdminRole(user.role) ? user.role : "student",
    status: user.status || "active",
    district: user.district || "",
    stream: user.stream || "",
    leavingYear: user.leavingYear || "",
    incomeBand: user.incomeBand || "mid",
    needSignals: Array.isArray(user.needSignals) ? user.needSignals : [],
    preferenceText: user.preferenceText || "",
    grades: user.grades || {},
    documents: Array.isArray(user.documents) ? user.documents : [],
    shortlist: Array.isArray(user.shortlist) ? user.shortlist : [],
    createdAt,
    reviewedAt: user.reviewedAt || (isAdminRole(user.role) ? createdAt : null),
    lastActiveAt: user.lastActiveAt || user.lastLoginAt || createdAt,
    lastActivity: user.lastActivity || (activity[0]?.label ?? "Account created"),
    activity
  };
}

function mergeAuthUsers(users = []) {
  const merged = [];
  users.forEach((user) => {
    const normalized = normalizeUser(user);
    if (!normalized) return;
    const existing = merged.find((item) => item.email === normalized.email || item.id === normalized.id);
    if (existing) Object.assign(existing, normalized);
    else merged.push(normalized);
  });
  authUsers = merged;
  if (!hasAdminUser(authUsers) && authUsers.length) {
    authUsers[0].role = "owner";
    authUsers[0].reviewedAt ||= authUsers[0].createdAt;
  }
  if (currentUser && isLegacyDemoUser(currentUser)) currentUser = null;
}

function mergeAuthUsersInMemory(existingUsers = [], incomingUsers = []) {
  const merged = [...existingUsers].filter(Boolean);
  incomingUsers.forEach((user) => {
    const normalized = normalizeUser(user);
    if (!normalized) return;
    const index = merged.findIndex((item) => item.id === normalized.id || item.email === normalized.email);
    if (index >= 0) merged[index] = { ...merged[index], ...normalized };
    else merged.push(normalized);
  });
  return merged;
}

function loadAuthUsers() {
  if (databaseLoadedAuthUsers) return;
  try {
    const saved = JSON.parse(localStorage.getItem(authUsersKey) || "[]");
    mergeAuthUsers(saved);
  } catch (error) {
    authUsers = structuredClone(defaultUsers);
  }
}

async function saveServerState(stateKey, payload) {
  if (!serverDatabaseAvailable) return;
  try {
    const response = await fetch(`/api/db/state/${encodeURIComponent(stateKey)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ payload })
    });
    if (!response.ok) throw new Error(`Database returned ${response.status}`);
    lastPersistenceMessage = persistenceMode === "server-supabase" ? "Saved to Supabase" : "Saved to database";
  } catch (error) {
    serverDatabaseAvailable = false;
    persistenceMode = supabaseClient ? "supabase" : "local";
    lastPersistenceMessage = `Database save failed: ${error.message || "offline"}`;
  }
}

function getCurrentUserPayload() {
  if (!currentUser) return null;
  return {
    name: currentUser.name || "",
    district: currentUser.district || "",
    stream: currentUser.stream || "",
    leavingYear: currentUser.leavingYear || "",
    incomeBand: currentUser.incomeBand || "mid",
    needSignals: currentUser.needSignals || [],
    preferenceText: currentUser.preferenceText || "",
    grades: currentUser.grades || {},
    documents: currentUser.documents || [],
    shortlist: currentUser.shortlist || []
  };
}

function syncCurrentUserToServer() {
  if (!authToken || !currentUser) return;
  const payload = getCurrentUserPayload();
  if (!payload) return;
  fetch("/api/auth/me", {
    method: "PUT",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload)
  })
    .then((response) => response.ok ? response.json() : null)
    .then((data) => {
      if (!data?.user) return;
      const updated = normalizeUser(data.user);
      if (!updated) return;
      currentUser = updated;
      authUsers = mergeAuthUsersInMemory(authUsers, [updated]);
      localStorage.setItem(authUsersKey, JSON.stringify(authUsers));
    })
    .catch(() => {});
}

function saveAuthUsers() {
  localStorage.setItem(authUsersKey, JSON.stringify(authUsers.map((user) => {
    const safe = { ...user };
    delete safe.password;
    delete safe.passwordHash;
    delete safe.passwordSalt;
    return safe;
  })));
  syncCurrentUserToServer();
}

function saveAuthSession() {
  if (currentUser) localStorage.setItem(authSessionKey, currentUser.id);
  else localStorage.removeItem(authSessionKey);
  if (authToken) localStorage.setItem(authTokenKey, authToken);
  else localStorage.removeItem(authTokenKey);
}

function formatDateTime(value) {
  if (!value) return "Not recorded";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not recorded";
  return date.toLocaleString("en-LS", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function addActivityToUser(user, type, label, metadata = {}, options = {}) {
  if (!user) return false;
  const now = new Date().toISOString();
  const throttleMs = options.throttleMs || 0;
  if (throttleMs && user.activity?.[0]?.type === type) {
    const lastTime = new Date(user.activity[0].at || 0).getTime();
    if (Date.now() - lastTime < throttleMs) {
      user.lastActiveAt = now;
      user.lastActivity = label;
      return false;
    }
  }
  user.activity ||= [];
  user.activity.unshift({
    id: generateUserId("act"),
    type,
    label,
    at: now,
    actorId: currentUser?.id || user.id,
    actorName: currentUser?.name || user.name || "System",
    metadata
  });
  user.activity = user.activity.slice(0, maxActivityItems);
  user.lastActiveAt = now;
  user.lastActivity = label;
  return true;
}

function recordCurrentUserActivity(type, label, metadata = {}, options = {}) {
  if (!currentUser) return;
  const changed = addActivityToUser(currentUser, type, label, metadata, options);
  if (changed || options.saveEvenWhenThrottled) saveAuthUsers();
}

function recordTargetUserActivity(user, type, label, metadata = {}) {
  const changed = addActivityToUser(user, type, label, metadata);
  if (changed) saveAuthUsers();
}

function setAuthMessage(message, tone = "neutral") {
  const messageEl = qs("#auth-message");
  if (!messageEl) return;
  messageEl.textContent = message;
  messageEl.dataset.tone = tone;
}

function isStandaloneApp() {
  return Boolean(window.matchMedia?.("(display-mode: standalone)").matches || window.navigator.standalone);
}

function updateInstallButtons() {
  const canInstall = Boolean(deferredInstallPrompt) && !isStandaloneApp();
  qsa("[data-install-app]").forEach((button) => {
    button.hidden = !canInstall;
  });
}

async function promptInstallApp() {
  if (!deferredInstallPrompt) return;
  deferredInstallPrompt.prompt();
  const choice = await deferredInstallPrompt.userChoice.catch(() => null);
  if (!choice || choice.outcome !== "dismissed") deferredInstallPrompt = null;
  updateInstallButtons();
}

function bindInstallPrompt() {
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredInstallPrompt = event;
    updateInstallButtons();
  });
  window.addEventListener("appinstalled", () => {
    deferredInstallPrompt = null;
    updateInstallButtons();
  });
  qsa("[data-install-app]").forEach((button) => button.addEventListener("click", promptInstallApp));
  updateInstallButtons();
}

function updateAuthContext() {
  const context = qs("#auth-context");
  const registerLabel = qs("#register-submit-label");
  if (context) {
    context.textContent = "Public registration creates student accounts only. Admin access is controlled privately by the system owner.";
  }
  if (registerLabel) registerLabel.textContent = "Create Student Account";
}

function setAuthMode(mode) {
  authMode = mode;
  qsa("[data-auth-mode]").forEach((button) => button.classList.toggle("active", button.dataset.authMode === mode));
  qsa(".auth-form").forEach((form) => form.classList.toggle("active", form.id === `${mode}-form`));
  updateAuthContext();
  setAuthMessage(
    mode === "login"
      ? "Use your registered account. Your dashboard opens according to your role."
      : "Create a student account. Admins can grant elevated access later."
  );
}

function updateUserShell() {
  const appShell = qs("#app-shell");
  const authScreen = qs("#auth-screen");
  if (appShell) appShell.classList.toggle("is-auth-hidden", !currentUser);
  if (authScreen) authScreen.classList.toggle("is-auth-hidden", Boolean(currentUser));
  qsa("[data-admin-only]").forEach((element) => {
    element.hidden = !isAdmin();
    if ("disabled" in element) element.disabled = !isAdmin();
  });
  if (!currentUser) return;
  qs("#user-avatar").textContent = getInitials(currentUser.name, currentUser.email);
  qs("#user-chip-name").textContent = `${currentUser.name} - ${getUserRoleLabel(currentUser)}`;
  qs("#full-name").value = currentUser.name || "";
  if (currentUser.district) qs("#district").value = currentUser.district;
  if (currentUser.stream) qs("#stream").value = currentUser.stream;
  if (currentUser.leavingYear) qs("#leaving-year").value = currentUser.leavingYear;
  if (currentUser.incomeBand) qs("#income-band").value = currentUser.incomeBand;
  setNeedSignalInputs(currentUser.needSignals || []);
  if (qs("#preference-text")) qs("#preference-text").value = currentUser.preferenceText || "";
}

function setCurrentUser(user, preferredView = "student") {
  currentUser = user;
  if (currentUser) {
    currentUser.documents ||= [];
    currentUser.shortlist ||= [];
    currentUser.grades ||= {};
    currentUser.needSignals ||= [];
    currentUser.incomeBand ||= qs("#income-band")?.value || "mid";
    if (Object.keys(currentUser.grades).length) {
      Object.keys(gradeState).forEach((key) => delete gradeState[key]);
      Object.assign(gradeState, currentUser.grades);
      renderGrades();
    } else {
      currentUser.grades = { ...gradeState };
    }
  }
  saveAuthSession();
  loadAiChatMessages();
  updateUserShell();
  renderAiChatMessages();
  renderStudentDashboard();
  renderAdminUsers();
  calculateMatches();
  setView(isAdmin() && preferredView === "admin" ? "admin" : "student");
  loadCurrentUserDocuments();
}

function signOut() {
  if (authToken) {
    fetch("/api/auth/logout", { method: "POST", headers: getAuthHeaders() }).catch(() => {});
  }
  currentUser = null;
  authToken = null;
  aiChatMessages = [];
  saveAuthSession();
  updateUserShell();
  setAuthMode("login");
  setAuthMessage("Signed out. Login again to continue.", "success");
}

async function loginWithCredentials(email, password, preferredView = "student") {
  try {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) throw new Error(data.detail || "Email or password is not correct.");
    authToken = data.token;
    const user = normalizeUser(data.user);
    authUsers = mergeAuthUsersInMemory(authUsers, [user]);
    saveAuthUsers();
    setCurrentUser(user, isAdmin(user) ? "admin" : preferredView);
    return true;
  } catch (error) {
    setAuthMessage(error.message || "Email or password is not correct.", "error");
    return false;
  }
}

async function registerUser(name, email, password, district) {
  const normalized = normalizeEmail(email);
  const cleanName = name.trim();
  if (!cleanName || !normalized || !password) {
    setAuthMessage("Please fill in your name, email, and password.", "error");
    return false;
  }
  try {
    const response = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: cleanName, email: normalized, password, district })
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) throw new Error(data.detail || "Registration failed.");
    authToken = data.token;
    const user = normalizeUser(data.user);
    authUsers = mergeAuthUsersInMemory(authUsers, [user]);
    saveAuthUsers();
    setCurrentUser(user, "student");
    setAuthMessage("Student account created. Admins can review and grant roles later.", "success");
    return true;
  } catch (error) {
    setAuthMessage(error.message || "Registration failed.", "error");
    return false;
  }
}

async function restoreAuthSession() {
  if (authToken) {
    try {
      const response = await fetch("/api/auth/me", { headers: getAuthHeaders({ Accept: "application/json" }) });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok || !data.user) throw new Error(data.detail || "Session expired");
      const user = normalizeUser(data.user);
      authUsers = mergeAuthUsersInMemory(authUsers, [user]);
      saveAuthUsers();
      setCurrentUser(user, isAdmin(user) ? "admin" : "student");
      return true;
    } catch (error) {
      authToken = null;
      currentUser = null;
      saveAuthSession();
      setAuthMessage("Session expired. Login again to continue.", "error");
    }
  }
  updateUserShell();
  setAuthMode("login");
  return false;
}
const programmePersistFields = [
  "institution",
  "name",
  "code",
  "category",
  "faculty",
  "level",
  "duration",
  "deliveryMode",
  "requirementsSummary",
  "overview",
  "careers",
  "sourceUrl",
  "sourcePath",
  "supportingSourcePath",
  "supportingFeeSourcePath",
  "sourceType",
  "extractionMethod",
  "sourceNote",
  "feeNote",
  "reviewStatus"
];

function getProgrammePersistPayload(programme) {
  return Object.fromEntries(programmePersistFields.map((field) => [field, programme[field] ?? null]));
}

function isCustomAdminProgramme(programme) {
  return programme?.id?.startsWith("manual-") || programme?.sourceType === "manual_admin_entry";
}

function isCustomAdminGap(gap) {
  return gap?.id?.startsWith("gap-manual-");
}

function applyCustomProgrammes(customProgrammes = []) {
  customProgrammes.forEach((customProgramme) => {
    if (!customProgramme?.id || !customProgramme.name) return;
    const existing = adminProgrammes.find((programme) => programme.id === customProgramme.id);
    if (existing) Object.assign(existing, customProgramme);
    else adminProgrammes.unshift(customProgramme);
  });
}

function applyCustomGaps(customGaps = []) {
  customGaps.forEach((customGap) => {
    if (!customGap?.id || !customGap.title) return;
    const existing = adminGaps.find((gap) => gap.id === customGap.id);
    if (existing) Object.assign(existing, customGap);
    else adminGaps.unshift(customGap);
  });
}

function getReviewStateSnapshot() {
  return {
    customProgrammes: adminProgrammes.filter(isCustomAdminProgramme).map((programme) => ({ ...programme })),
    programmeStatuses: Object.fromEntries(adminProgrammes.map((programme) => [programme.id, programme.reviewStatus])),
    programmeEdits: Object.fromEntries(
      adminProgrammes.map((programme) => [
        programme.id,
        getProgrammePersistPayload(programme)
      ])
    ),
    customGaps: adminGaps.filter(isCustomAdminGap).map((gap) => ({ ...gap })),
    gapStatuses: Object.fromEntries(adminGaps.map((gap) => [gap.id, gap.status])),
    savedAt: new Date().toISOString()
  };
}

function applyReviewState(snapshot) {
  if (!snapshot) return;
  applyCustomProgrammes(snapshot.customProgrammes || []);
  applyCustomGaps(snapshot.customGaps || []);
  const programmeStatuses = snapshot.programmeStatuses || {};
  const programmeEdits = snapshot.programmeEdits || {};
  const gapStatuses = snapshot.gapStatuses || {};
  adminProgrammes.forEach((programme) => {
    if (programmeStatuses[programme.id]) programme.reviewStatus = programmeStatuses[programme.id];
    if (programmeEdits[programme.id]) Object.assign(programme, programmeEdits[programme.id]);
  });
  adminGaps.forEach((gap) => {
    if (gapStatuses[gap.id]) gap.status = gapStatuses[gap.id];
  });
}

async function loadServerDatabaseState() {
  try {
    const response = await fetch("/api/db/state", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`Database returned ${response.status}`);
    const data = await response.json();
    serverDatabaseAvailable = Boolean(data.ok);
    if (!serverDatabaseAvailable) return;
    persistenceMode = data.database === "supabase" ? "server-supabase" : "server-db";
    lastPersistenceMessage = data.database === "supabase" ? "Supabase database ready" : "Server database ready";

    const users = data.state?.auth_users?.users;
    if (Array.isArray(users)) {
      mergeAuthUsers(users);
      databaseLoadedAuthUsers = true;
    }

    const reviewState = data.state?.review_state;
    if (reviewState) {
      applyReviewState(reviewState);
      databaseLoadedReviewState = true;
    }
  } catch (error) {
    serverDatabaseAvailable = false;
    persistenceMode = supabaseClient ? "supabase" : "local";
    lastPersistenceMessage = supabaseClient ? "Supabase sync ready" : "Local prototype mode";
  }
}

function seedServerDatabaseState() {
  if (!serverDatabaseAvailable) return;
  saveServerState("auth_users", { users: authUsers });
  saveServerState("review_state", getReviewStateSnapshot());
}

function loadLocalReviewState() {
  if (databaseLoadedReviewState) return;
  try {
    const raw = localStorage.getItem(persistenceKey);
    if (!raw) return;
    applyReviewState(JSON.parse(raw));
    lastPersistenceMessage = "Loaded local review state";
  } catch (error) {
    lastPersistenceMessage = "Local review state could not be loaded";
  }
}

function saveLocalReviewState() {
  try {
    const snapshot = getReviewStateSnapshot();
    localStorage.setItem(persistenceKey, JSON.stringify(snapshot));
    saveServerState("review_state", snapshot);
    if (serverDatabaseAvailable) lastPersistenceMessage = persistenceMode === "server-supabase" ? "Saving to Supabase" : "Saving to database";
    else if (!supabaseClient) lastPersistenceMessage = "Saved locally";
  } catch (error) {
    lastPersistenceMessage = "Local save failed";
  }
}

async function recordReviewEvent(entityTable, entityId, action, notes, payload = {}) {
  if (!supabaseClient) return;
  await supabaseClient.from("review_events").insert({
    entity_table: entityTable,
    entity_id: null,
    action,
    notes,
    new_payload: {
      external_key: entityId,
      ...payload
    }
  });
}

async function persistProgrammeStatus(programme, status) {
  saveLocalReviewState();
  if (!supabaseClient) return;
  if (isCustomAdminProgramme(programme)) {
    await recordReviewEvent("programmes", programme.id, status === "approved" ? "approved" : status === "rejected" ? "rejected" : "flagged", `Admin marked manual programme ${formatStatus(status)}.`, {
      programme_name: programme.name,
      institution: programme.institution,
      review_status: status
    });
    return;
  }
  const { error } = await supabaseClient
    .from("programmes")
    .update({ review_status: status, updated_at: new Date().toISOString() })
    .eq("external_key", programme.id);
  if (error) throw error;
  await recordReviewEvent("programmes", programme.id, status === "approved" ? "approved" : status === "rejected" ? "rejected" : "flagged", `Admin marked programme ${formatStatus(status)}.`, {
    programme_name: programme.name,
    institution: programme.institution,
    review_status: status
  });
}

async function persistProgrammeEdit(programme, changes) {
  saveLocalReviewState();
  if (!supabaseClient) return;
  if (isCustomAdminProgramme(programme)) {
    await recordReviewEvent("programmes", programme.id, "created_or_updated", "Admin saved a manual programme record.", {
      programme_name: programme.name,
      institution: programme.institution,
      changes
    });
    return;
  }
  const updatePayload = {
    name: programme.name,
    code: programme.code || null,
    category: programme.category || null,
    qualification_level: programme.level || null,
    duration_text: programme.duration || null,
    delivery_mode: programme.deliveryMode || null,
    overview: programme.overview || null,
    raw_payload: {
      ...programme,
      admin_edit: {
        changed_fields: Object.keys(changes),
        edited_at: new Date().toISOString()
      }
    },
    updated_at: new Date().toISOString()
  };
  const { data, error } = await supabaseClient
    .from("programmes")
    .update(updatePayload)
    .eq("external_key", programme.id)
    .select("id")
    .single();
  if (error) throw error;

  if (programme.requirementsSummary && data?.id) {
    const { error: requirementError } = await supabaseClient.from("programme_requirement_sets").upsert(
      {
        programme_id: data.id,
        route_name: "General entry",
        requirement_summary: programme.requirementsSummary,
        review_status: "needs_admin_review",
        raw_payload: {
          source_field: "admin_edit",
          edited_at: new Date().toISOString()
        }
      },
      { onConflict: "programme_id,route_name" }
    );
    if (requirementError) throw requirementError;
  }

  await recordReviewEvent("programmes", programme.id, "updated", "Admin edited programme details.", {
    programme_name: programme.name,
    institution: programme.institution,
    changes
  });
}

async function persistGapStatus(gap, status) {
  saveLocalReviewState();
  if (!supabaseClient) return;
  if (isCustomAdminGap(gap)) {
    await recordReviewEvent("data_gaps", gap.id, status === "resolved" ? "approved" : "updated", `Admin marked manual data gap ${formatStatus(status)}.`, {
      gap_type: gap.type,
      title: gap.title,
      status
    });
    return;
  }
  const updatePayload = {
    status,
    resolved_at: status === "resolved" ? new Date().toISOString() : null
  };
  const { error } = await supabaseClient.from("data_gaps").update(updatePayload).eq("external_key", gap.id);
  if (error) throw error;
  await recordReviewEvent("data_gaps", gap.id, status === "resolved" ? "approved" : "updated", `Admin marked data gap ${formatStatus(status)}.`, {
    gap_type: gap.type,
    title: gap.title,
    status
  });
}

function getProgrammeEditPayload() {
  const form = qs("#admin-edit-form");
  const values = new FormData(form);
  return {
    name: values.get("name")?.trim(),
    institution: values.get("institution")?.trim() || "Institution under review",
    code: values.get("code")?.trim() || null,
    category: values.get("category")?.trim() || null,
    faculty: values.get("faculty")?.trim() || null,
    level: values.get("level")?.trim() || null,
    duration: values.get("duration")?.trim() || null,
    deliveryMode: values.get("deliveryMode")?.trim() || null,
    requirementsSummary: values.get("requirementsSummary")?.trim() || null,
    overview: values.get("overview")?.trim() || null,
    careers: parseListText(values.get("careers")),
    sourceUrl: values.get("sourceUrl")?.trim() || null,
    supportingSourcePath: values.get("supportingSourcePath")?.trim() || null,
    supportingFeeSourcePath: values.get("supportingFeeSourcePath")?.trim() || null,
    sourceNote: values.get("sourceNote")?.trim() || null,
    feeNote: values.get("feeNote")?.trim() || null
  };
}

function startProgrammeEdit(id) {
  adminState.selectedProgrammeId = id;
  adminState.editingProgrammeId = id;
  renderAdmin();
}

function cancelProgrammeEdit() {
  adminState.editingProgrammeId = null;
  renderAdmin();
}

function valuesAreEqual(previous, next) {
  if (Array.isArray(previous) || Array.isArray(next)) {
    return JSON.stringify(previous || []) === JSON.stringify(next || []);
  }
  return (previous || null) === (next || null);
}

function getManualProgrammeGaps(programme) {
  const gapBase = `gap-${programme.id}`;
  return [
    {
      id: `${gapBase}-duration`,
      type: "duration_missing",
      priority: "medium",
      status: programme.duration ? "resolved" : "open",
      institution: programme.institution,
      programmeId: programme.id,
      programmeName: programme.name,
      title: "Missing duration",
      description: "Add the programme duration once confirmed from a prospectus, handbook, or official page."
    },
    {
      id: `${gapBase}-requirements`,
      type: "requirements_missing",
      priority: "high",
      status: programme.requirementsSummary ? "resolved" : "open",
      institution: programme.institution,
      programmeId: programme.id,
      programmeName: programme.name,
      title: "Missing entry requirements",
      description: "Add the minimum entry requirements so matching can be more accurate."
    },
    {
      id: `${gapBase}-source`,
      type: "source_missing",
      priority: "high",
      status: programme.sourceUrl || programme.supportingSourcePath ? "resolved" : "open",
      institution: programme.institution,
      programmeId: programme.id,
      programmeName: programme.name,
      title: "Missing source link",
      description: "Attach the official page, PDF, or local evidence used for this programme."
    },
    {
      id: `${gapBase}-fee`,
      type: "fee_missing",
      priority: "medium",
      status: programme.supportingFeeSourcePath || programme.feeNote ? "resolved" : "open",
      institution: programme.institution,
      programmeId: programme.id,
      programmeName: programme.name,
      title: "Missing fee evidence",
      description: "Add fee notes or the source that confirms application, tuition, or other fees."
    }
  ];
}

function syncProgrammeGaps(programme) {
  adminGaps
    .filter((gap) => gap.programmeId === programme.id)
    .forEach((gap) => {
      gap.institution = programme.institution;
      gap.programmeName = programme.name;
    });
}

function createAdminProgramme() {
  const timestamp = Date.now();
  const programme = {
    id: `manual-${timestamp}`,
    institution: "Institution under review",
    name: "New programme",
    code: null,
    category: "Manual entry",
    faculty: "Faculty under review",
    level: "Level under review",
    duration: null,
    deliveryMode: "Full-time",
    overview: "Manual admin entry. Replace this with the official programme description when confirmed.",
    requirementsSummary: null,
    careers: [],
    sourceUrl: null,
    sourcePath: null,
    supportingSourcePath: null,
    supportingFeeSourcePath: null,
    sourceType: "manual_admin_entry",
    extractionMethod: "admin_dashboard",
    reviewStatus: "needs_admin_review",
    sourceNote: "Created manually in the admin dashboard.",
    feeNote: null
  };
  adminProgrammes.unshift(programme);
  adminGaps.unshift(...getManualProgrammeGaps(programme));
  adminState.selectedProgrammeId = programme.id;
  adminState.editingProgrammeId = programme.id;
  adminState.tab = "catalogue";
  adminState.institution = "all";
  adminState.status = "all";
  lastPersistenceMessage = "New programme draft created";
  recordCurrentUserActivity("admin_programme_created", "Created a programme draft", { programmeId: programme.id, programmeName: programme.name });
  saveLocalReviewState();
  renderAdmin();
  updateCounts();
  calculateMatches();
}

async function saveProgrammeEdit(id) {
  const programme = adminProgrammes.find((item) => item.id === id);
  if (!programme) return;
  const previousProgramme = structuredClone(programme);
  const previousGaps = structuredClone(adminGaps);
  const payload = getProgrammeEditPayload();
  const changes = {};

  Object.entries(payload).forEach(([key, value]) => {
    if (!valuesAreEqual(programme[key], value)) {
      changes[key] = { from: programme[key] || null, to: value || null };
      programme[key] = value;
    }
  });

  if (!programme.name) programme.name = "Programme under review";
  if (!programme.institution) programme.institution = "Institution under review";
  syncProgrammeGaps(programme);

  if (!Object.keys(changes).length) {
    adminState.editingProgrammeId = null;
    renderAdmin();
    return;
  }

  const autoResolvedGaps = [];
  if (programme.duration) {
    adminGaps
      .filter((gap) => gap.programmeId === programme.id && gap.type === "duration_missing" && gap.status === "open")
      .forEach((gap) => {
        gap.status = "resolved";
        autoResolvedGaps.push(gap);
      });
  }
  if (programme.requirementsSummary) {
    adminGaps
      .filter((gap) => gap.programmeId === programme.id && gap.type === "requirements_missing" && gap.status === "open")
      .forEach((gap) => {
        gap.status = "resolved";
        autoResolvedGaps.push(gap);
      });
  }
  if (programme.sourceUrl || programme.supportingSourcePath) {
    adminGaps
      .filter((gap) => gap.programmeId === programme.id && gap.type === "source_missing" && gap.status === "open")
      .forEach((gap) => {
        gap.status = "resolved";
        autoResolvedGaps.push(gap);
      });
  }
  if (programme.supportingFeeSourcePath || programme.feeNote) {
    adminGaps
      .filter((gap) => gap.programmeId === programme.id && gap.type === "fee_missing" && gap.status === "open")
      .forEach((gap) => {
        gap.status = "resolved";
        autoResolvedGaps.push(gap);
      });
  }

  adminState.editingProgrammeId = null;
  adminState.selectedProgrammeId = id;
  lastPersistenceMessage = supabaseClient ? "Saving edit..." : "Saved locally";
  saveLocalReviewState();
  renderAdmin();

  try {
    await persistProgrammeEdit(programme, changes);
    for (const gap of autoResolvedGaps) {
      await persistGapStatus(gap, "resolved");
    }
    lastPersistenceMessage = supabaseClient ? "Synced programme edit" : "Saved locally";
    recordCurrentUserActivity("admin_programme_edited", "Edited programme record", { programmeId: programme.id, programmeName: programme.name, changedFields: Object.keys(changes) });
  } catch (error) {
    Object.assign(programme, previousProgramme);
    adminGaps = previousGaps;
    saveLocalReviewState();
    lastPersistenceMessage = `Sync failed: ${error.message || "programme edit"}`;
  }
  renderAdmin();
  updateCounts();
  calculateMatches();
}

function resetLocalReviewState() {
  localStorage.removeItem(persistenceKey);
  adminProgrammes = structuredClone(adminData.programmes || []);
  adminGaps = structuredClone(adminData.dataGaps || []);
  adminState.selectedProgrammeId = adminProgrammes[0]?.id || null;
  adminState.editingProgrammeId = null;
  saveServerState("review_state", getReviewStateSnapshot());
  lastPersistenceMessage = serverDatabaseAvailable ? "Database review state reset" : "Local state reset";
  recordCurrentUserActivity("admin_review_reset", "Reset catalogue review state");
  renderAdmin();
  updateCounts();
  calculateMatches();
}

function setView(viewName) {
  if (!currentUser) {
    updateUserShell();
    return;
  }
  if (viewName === "admin" && !isAdmin()) {
    setView("student");
    return;
  }
  qsa(".view").forEach((view) => view.classList.toggle("active", view.id === `view-${viewName}`));
  qsa(".side-link").forEach((link) => link.classList.toggle("active", link.dataset.view === viewName));
  qs("#page-title").textContent = titles[viewName];
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function renderGrades() {
  qs("#grade-grid").innerHTML = subjects
    .map((subject) => {
      const grade = gradeState[subject.code] || "";
      const gradeClass = grade ? grade.toLowerCase().replace("*", "star") : "";
      return `
        <label class="grade-card ${grade ? "selected" : ""}">
          <span class="grade-subject">${subject.name}</span>
          <select class="grade-select grade-value ${gradeClass}" data-subject="${subject.code}" aria-label="${subject.name} grade">
            ${gradeValues.map((value) => `<option value="${value}" ${value === grade ? "selected" : ""}>${value || "Blank"}</option>`).join("")}
          </select>
        </label>
      `;
    })
    .join("");
}

function renderInterests() {
  qs("#interest-grid").innerHTML = interests
    .map((interest) => `
      <button class="chip ${interestState.has(interest) ? "active" : ""}" type="button" data-interest="${interest}">
        ${interest}
      </button>
    `)
    .join("");
  qs("#interest-count").textContent = `${interestState.size} selected`;
}

function clamp(value, min = 0, max = 100) {
  return Math.max(min, Math.min(max, value));
}

function unique(values) {
  return Array.from(new Set(values.filter(Boolean)));
}

function getSubjectLabel(code) {
  return subjectAliasRules.find((subject) => subject.code === code)?.label || code;
}

function findSubjectCodes(text) {
  const haystack = String(text || "").toLowerCase();
  return subjectAliasRules
    .filter((subject) => subject.patterns.some((pattern) => haystack.includes(pattern)))
    .map((subject) => subject.code);
}

function getProgrammeText(programme) {
  return [
    programme.name,
    programme.title,
    programme.category,
    programme.faculty,
    programme.level,
    programme.overview,
    programme.requirementsSummary,
    programme.sourceNote,
    programme.feeNote,
    ...(programme.careers || [])
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function getDomainProfile(programme) {
  const text = getProgrammeText(programme);
  return domainProfiles.find((profile) => profile.keywords.some((keyword) => text.includes(keyword))) || {
    key: "general",
    interests: ["Natural Sciences"],
    subjects: ["ENG", "MATH"],
    careers: ["Programme Officer", "Administrator", "Research Assistant"],
    skills: ["Communication", "Research", "Problem solving"],
    sector: "General Employment",
    priority: 66
  };
}

function getInstitutionShortName(institution) {
  const known = {
    "National University of Lesotho": "NUL",
    "NUL Institute of Extra Mural Studies (IEMS)": "IEMS",
    "Limkokwing University Lesotho": "LUCT",
    "Botho University Lesotho": "Botho",
    "Lerotholi Polytechnic": "LP",
    "Lesotho Agricultural College": "LAC",
    "Lesotho College of Education": "LCE",
    "Centre for Accounting Studies": "CAS",
    "Roma College of Nursing": "RCN",
    "Paray School of Nursing": "Paray",
    "Imperial Business College": "IBC"
  };
  if (known[institution]) return known[institution];
  return String(institution || "Institution")
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 5)
    .toUpperCase();
}

function splitRequirementSummary(summary) {
  return String(summary || "")
    .replace(/\s+/g, " ")
    .split(/(?<=\.)\s+|;\s+|\n+/)
    .map((item) => item.trim())
    .filter((item) => item.length > 8)
    .slice(0, 5);
}

function numberFromText(value) {
  const words = {
    one: 1,
    two: 2,
    three: 3,
    four: 4,
    five: 5,
    six: 6,
    seven: 7,
    eight: 8,
    nine: 9,
    ten: 10
  };
  const normalized = String(value || "").toLowerCase();
  const digit = normalized.match(/\d+/);
  return digit ? Number(digit[0]) : words[normalized] || 0;
}

function normaliseGrade(value, fallback = defaultPassGrade) {
  const grade = String(value || fallback).toUpperCase().replace(/\s+/g, "");
  return gradePoints[grade] !== undefined ? grade : fallback;
}

function addRequirementRule(rules, rule) {
  if (rule) rules.push(rule);
}

function addGradeCountRule(rules, minimum, minGrade, text) {
  const count = Number(minimum || 0);
  if (!count) return;
  const grade = normaliseGrade(minGrade);
  addRequirementRule(rules, {
    type: "grade-count",
    minimum: count,
    minGrade: grade,
    text: text || `At least ${count} subjects at ${grade} or better`
  });
}

function addSubjectRule(rules, codes, minGrade, text) {
  const cleanedCodes = unique(codes);
  if (!cleanedCodes.length) return;
  const grade = normaliseGrade(minGrade);
  addRequirementRule(rules, {
    type: "subject",
    codes: cleanedCodes,
    minGrade: grade,
    text: text || `${cleanedCodes.map(getSubjectLabel).join(" or ")} ${grade} or better`
  });
}

function addSubjectRulesFromPhrase(rules, phrase, minGrade, sourceText) {
  const text = String(phrase || "").toLowerCase();
  const grade = normaliseGrade(minGrade);
  const textPrefix = sourceText || phrase;
  if (/english/.test(text)) addSubjectRule(rules, ["ENG"], grade, `English ${grade} or better`);
  if (/mathematics|maths|statistics/.test(text)) addSubjectRule(rules, ["MATH"], grade, `Mathematics ${grade} or better`);
  if (/sesotho/.test(text)) addSubjectRule(rules, ["SES"], grade, `Sesotho ${grade} or better`);
  if (/computer skills|computer studies|computer literacy|ict|information and communication technology/.test(text)) addSubjectRule(rules, ["CSK"], grade, `Computer Skills ${grade} or better`);
  if (/account/.test(text)) addSubjectRule(rules, ["ACC"], grade, `Accounting ${grade} or better`);
  if (/agriculture/.test(text)) addSubjectRule(rules, ["AGR"], grade, `Agriculture ${grade} or better`);
  if (/food\s*(?:and|&)?\s*nutrition|nutrition|food studies|home economics|consumer science/.test(text)) addSubjectRule(rules, ["FNU"], grade, `Food & Nutrition ${grade} or better`);
  if (/economics?/.test(text)) addSubjectRule(rules, ["ECON"], grade, `Economics ${grade} or better`);
  if (/literature/.test(text)) addSubjectRule(rules, ["LIT"], grade, `English Literature ${grade} or better`);
  if (/religious knowledge|religion|religious education|divinity|bible knowledge/.test(text)) addSubjectRule(rules, ["REL"], grade, `Religious Knowledge ${grade} or better`);
  if (/history/.test(text)) addSubjectRule(rules, ["HIST"], grade, `History ${grade} or better`);
  if (/geography/.test(text)) addSubjectRule(rules, ["GEO"], grade, `Geography ${grade} or better`);

  const scienceCodes = [];
  if (/biology/.test(text)) scienceCodes.push("BIO");
  if (/physical science|physical sciences|double science|double sciences|science|physics|chemistry/.test(text)) scienceCodes.push("PSCI");
  if (/physics/.test(text)) scienceCodes.push("PHY");
  if (/chemistry/.test(text)) scienceCodes.push("CHEM");
  if (scienceCodes.length) addSubjectRule(rules, scienceCodes, grade, `${unique(scienceCodes).map(getSubjectLabel).join(" or ")} ${grade} or better`);

  const genericCodes = findSubjectCodes(textPrefix);
  if (!rules.some((rule) => rule.type === "subject" && genericCodes.some((code) => rule.codes?.includes(code)))) {
    addSubjectRule(rules, genericCodes, grade);
  }
}

function parseRequirementRules(summary) {
  const text = String(summary || "");
  const rules = [];

  if (/successful completion|bachelor'?s degree|first degree|recognised degree|recognized degree|degree in a related/i.test(text)) {
    rules.push({
      type: "prior-qualification",
      text: "Prior tertiary qualification required"
    });
  }

  const countPatterns = [
    /minimum of\s+(one|two|three|four|five|six|seven|eight|nine|ten|\d+)(?:\s+\(\d+\))?\s+subjects/i,
    /at least\s+(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+subjects/i,
    /sat for\s+(?:a\s+)?minimum of\s+(one|two|three|four|five|six|seven|eight|nine|ten|\d+)(?:\s+\(\d+\))?\s+subjects/i
  ];
  countPatterns.forEach((pattern) => {
    const match = text.match(pattern);
    if (match) {
      const minimum = numberFromText(match[1]);
      if (minimum) rules.push({ type: "count", minimum, text: `At least ${minimum} captured subjects` });
    }
  });

  const subjectGradeComboPattern = /(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+subjects?\s+with\s+(?:a\s+)?(?:grade\s+of\s+)?(A\*|[A-G])\s+or\s+better\s+and\s+(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+subjects?\s+with\s+(?:a\s+)?(?:grade\s+of\s+)?(A\*|[A-G])\s+or\s+better/gi;
  let comboMatch = subjectGradeComboPattern.exec(text);
  while (comboMatch) {
    const firstCount = numberFromText(comboMatch[1]);
    const secondCount = numberFromText(comboMatch[3]);
    const firstGrade = normaliseGrade(comboMatch[2]);
    const secondGrade = normaliseGrade(comboMatch[4]);
    addGradeCountRule(rules, firstCount, firstGrade, `At least ${firstCount} subjects at ${firstGrade} or better`);
    addGradeCountRule(rules, firstCount + secondCount, secondGrade, `At least ${firstCount + secondCount} subjects at ${secondGrade} or better`);
    comboMatch = subjectGradeComboPattern.exec(text);
  }

  const creditPassComboPattern = /(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+credits?\s+and\s+(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+passes?/gi;
  comboMatch = creditPassComboPattern.exec(text);
  while (comboMatch) {
    const creditCount = numberFromText(comboMatch[1]);
    const passCount = numberFromText(comboMatch[2]);
    addGradeCountRule(rules, creditCount, defaultCreditGrade, `At least ${creditCount} credits`);
    addGradeCountRule(rules, creditCount + passCount, defaultPassGrade, `At least ${creditCount + passCount} passes`);
    comboMatch = creditPassComboPattern.exec(text);
  }

  const aggregatePatterns = [
    {
      pattern: /(?:at least\s+)?(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+subjects?\s+with\s+(?:a\s+)?(?:grade\s+of\s+)?(A\*|[A-G])\s+or\s+better/gi,
      grade: (match) => match[2],
      label: (match) => `At least ${numberFromText(match[1])} subjects at ${normaliseGrade(match[2])} or better`
    },
    {
      pattern: /(?:with\s+)?(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+credits?/gi,
      grade: () => defaultCreditGrade,
      label: (match) => `At least ${numberFromText(match[1])} credits`
    },
    {
      pattern: /(?:with\s+)?(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+passes?/gi,
      grade: () => defaultPassGrade,
      label: (match) => `At least ${numberFromText(match[1])} passes`
    }
  ];

  aggregatePatterns.forEach(({ pattern, grade, label }) => {
    let match = pattern.exec(text);
    while (match) {
      addGradeCountRule(rules, numberFromText(match[1]), grade(match), label(match));
      match = pattern.exec(text);
    }
  });

  const gradePatterns = [
    /(?:obtained\s+)?(?:an?\s+)?(A\*|[A-GXZ])\s+grade\s+or\s+better\s+in\s+([^.;]+)/gi,
    /(?:obtained\s+)?(?:an?\s+)?(A\*|[A-GXZ])\s+or\s+better\s+in\s+([^.;]+)/gi,
    /([A-Za-z/& ]+)\s+A\*?-([A-GXZ])/gi
  ];

  gradePatterns.forEach((pattern) => {
    let match = pattern.exec(text);
    while (match) {
      const minGrade = pattern === gradePatterns[2] ? match[2] : match[1];
      const subjectText = pattern === gradePatterns[2] ? match[1] : match[2];
      if (!/other|remaining|any/i.test(subjectText)) {
        const codes = findSubjectCodes(subjectText);
        if (codes.length) addSubjectRule(rules, codes, minGrade, `${codes.map(getSubjectLabel).join(" or ")} ${normaliseGrade(minGrade)} or better`);
      }
      match = pattern.exec(text);
    }
  });

  const subjectRequirementPatterns = [
    { pattern: /credit\s+in\s+([^.;]+)/gi, grade: defaultCreditGrade },
    { pattern: /pass\s+in\s+([^.;]+)/gi, grade: defaultPassGrade },
    { pattern: /including\s+([^.;]+)/gi, grade: defaultPassGrade }
  ];
  subjectRequirementPatterns.forEach(({ pattern, grade }) => {
    let match = pattern.exec(text);
    while (match) {
      addSubjectRulesFromPhrase(rules, match[1], grade, match[0]);
      match = pattern.exec(text);
    }
  });

  const strongestGradeCounts = new Map();
  rules
    .filter((rule) => rule.type === "grade-count")
    .forEach((rule) => {
      const key = rule.minGrade;
      const current = strongestGradeCounts.get(key);
      if (!current || rule.minimum > current.minimum) strongestGradeCounts.set(key, rule);
    });

  const strongestSubjectRules = new Map();
  rules
    .filter((rule) => rule.type === "subject")
    .forEach((rule) => {
      const key = rule.codes.join("/");
      const current = strongestSubjectRules.get(key);
      if (!current || (gradePoints[rule.minGrade] || 0) > (gradePoints[current.minGrade] || 0)) strongestSubjectRules.set(key, rule);
    });

  const seen = new Set();
  return rules
    .filter((rule) => rule.type !== "grade-count" || strongestGradeCounts.get(rule.minGrade) === rule)
    .filter((rule) => rule.type !== "subject" || strongestSubjectRules.get(rule.codes.join("/")) === rule)
    .filter((rule) => {
      const key =
        rule.type === "count"
          ? `count-${rule.minimum}`
          : rule.type === "grade-count"
            ? `grade-count-${rule.minimum}-${rule.minGrade}`
            : rule.type === "prior-qualification"
              ? `prior-${rule.text}`
              : `${rule.codes.join("/")}-${rule.minGrade}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

function getGradeForSubject(code) {
  if (gradeState[code]) return gradeState[code];
  if ((code === "PHY" || code === "CHEM") && gradeState.PSCI) return gradeState.PSCI;
  if (code === "PSCI") return gradeState.PSCI || gradeState.PHY || gradeState.CHEM || "";
  return "";
}

function gradeMeets(studentGrade, minGrade) {
  if (!studentGrade || !minGrade) return false;
  return (gradePoints[studentGrade] || 0) >= (gradePoints[minGrade] || 0);
}

function getEnteredGrades() {
  return Object.values(gradeState).filter(Boolean);
}

function getUsableGradeCount() {
  return getEnteredGrades().filter((grade) => (gradePoints[grade] || 0) > 0).length;
}

function countGradesAtLeast(minGrade) {
  return getEnteredGrades().filter((grade) => gradeMeets(grade, minGrade)).length;
}

function getRequirementDetailScore(detail) {
  if (detail.met) return 1;
  if (detail.type === "prior-qualification") return 0.18;
  if (detail.type === "grade-count" || detail.type === "count") {
    return clamp(detail.actual / detail.minimum, 0, 0.72);
  }
  if (detail.studentGrade && detail.studentGrade !== "missing") {
    const gap = (gradePoints[detail.minGrade] || 0) - (gradePoints[detail.studentGrade] || 0);
    return gap <= 1 ? 0.65 : 0.38;
  }
  return Object.keys(gradeState).length < 5 ? 0.35 : 0.12;
}

function evaluateRequirementRules(rules) {
  const selectedCount = Object.keys(gradeState).length;
  const usableCount = getUsableGradeCount();
  const details = rules.map((rule) => {
    if (rule.type === "prior-qualification") {
      return {
        ...rule,
        actual: 0,
        met: false,
        partial: false,
        near: false,
        studentGrade: "not captured"
      };
    }
    if (rule.type === "count") {
      const actual = usableCount;
      return {
        ...rule,
        actual,
        met: actual >= rule.minimum,
        partial: actual > 0 && actual < rule.minimum,
        near: actual > 0 && rule.minimum - actual <= 1,
        studentGrade: `${actual} captured`
      };
    }
    if (rule.type === "grade-count") {
      const actual = countGradesAtLeast(rule.minGrade);
      return {
        ...rule,
        actual,
        met: actual >= rule.minimum,
        partial: actual > 0 && actual < rule.minimum,
        near: actual > 0 && rule.minimum - actual <= 1,
        studentGrade: `${actual} at ${rule.minGrade}+`
      };
    }
    const passingCode = rule.codes.find((code) => gradeMeets(getGradeForSubject(code), rule.minGrade));
    const bestCode = passingCode || rule.codes.find((code) => getGradeForSubject(code)) || rule.codes[0];
    const studentGrade = getGradeForSubject(bestCode);
    const near = studentGrade && !passingCode && (gradePoints[rule.minGrade] || 0) - (gradePoints[studentGrade] || 0) <= 1;
    return {
      ...rule,
      met: Boolean(passingCode),
      partial: Boolean(studentGrade) && !passingCode,
      near,
      studentGrade: studentGrade || "missing",
      subjectLabel: rule.codes.map(getSubjectLabel).join(" or ")
    };
  });
  const total = details.length;
  const met = details.filter((detail) => detail.met).length;
  const partial = details.filter((detail) => detail.partial).length;
  const scoreParts = details.map(getRequirementDetailScore);
  return {
    total,
    met,
    partial,
    score: total ? Math.round((scoreParts.reduce((sum, value) => sum + value, 0) / total) * 100) : 62,
    missing: details.filter((detail) => !detail.met),
    nearMisses: details.filter((detail) => !detail.met && detail.near),
    selectedCount,
    usableCount,
    details
  };
}

const coreScienceCodes = ["PSCI", "PHY", "CHEM", "BIO"];

function isLowerQualification(programme) {
  const text = `${programme.level || ""} ${programme.title || ""}`.toLowerCase();
  return /certificate|diploma/.test(text) && !/degree|bachelor|bsc/.test(text);
}

function getGateGrade(programme, degreeGrade = "C", diplomaGrade = "D") {
  return isLowerQualification(programme) ? diplomaGrade : degreeGrade;
}

function addStrictGateRule(rules, codes, minGrade, text, source = "inferred") {
  const cleanedCodes = unique(codes);
  if (!cleanedCodes.length) return;
  rules.push({
    type: "strict-gate",
    codes: cleanedCodes,
    minGrade: normaliseGrade(minGrade),
    text: text || `${cleanedCodes.map(getSubjectLabel).join(" or ")} ${normaliseGrade(minGrade)} or better`,
    source
  });
}

function dedupeStrictGateRules(rules) {
  const strongest = new Map();
  rules.forEach((rule) => {
    const key = rule.codes.join("/");
    const current = strongest.get(key);
    if (!current || (gradePoints[rule.minGrade] || 0) > (gradePoints[current.minGrade] || 0)) {
      strongest.set(key, rule);
    }
  });
  return Array.from(strongest.values());
}

function getStrictGateRules(programme) {
  const text = getProgrammeText(programme);
  const institution = String(programme.institution || "").toLowerCase();
  const title = String(programme.title || programme.name || "").toLowerCase();
  const faculty = String(programme.faculty || programme.category || "").toLowerCase();
  const summary = String(programme.requirementsSummary || programme.requirements?.join(". ") || "").toLowerCase();
  const rules = [];
  const mathGrade = getGateGrade(programme, "C", "D");
  const scienceGrade = getGateGrade(programme, "C", "D");
  const isLuct = institution.includes("limkokwing");
  const isBotho = institution.includes("botho");
  const technologyPath =
    /information technology|business information technology|\bbit\b|software|computing|computer science|computer forensics|cyber|network|data science|data analytics|information systems|\bict\b|artificial intelligence|machine learning|database|web programming/.test(text) ||
    /technology|information & communication/.test(faculty);
  const architectureOrEngineeringPath =
    /architecture|built environment|engineering|electrical|civil|mechanical|electronics|construction|survey|quantity survey|chemical technology/.test(text);
  const naturalSciencePath =
    /(bsc|bachelor of science|chemical technology|electronics|statistics|physical geography|environmental health|pharmacy|laboratory|biology|chemistry|physics)/.test(text) &&
    !/social sciences|political science|library and information/.test(text);
  const healthPath = /nursing|midwifery|pharmacy|clinical|medical|health information|environmental health/.test(text);
  const agriculturePath = /agriculture|crop|animal science|soil science|horticulture|agribusiness|consumer science|food science/.test(text);

  if (technologyPath || ((isLuct || isBotho) && /technology|software|comput|information|architecture/.test(text))) {
    addStrictGateRule(rules, ["MATH"], mathGrade, `Mathematics ${mathGrade} or better is required for technology pathways.`);
  }

  if (architectureOrEngineeringPath) {
    addStrictGateRule(rules, ["MATH"], mathGrade, `Mathematics ${mathGrade} or better is required for engineering, architecture, and built-environment pathways.`);
    addStrictGateRule(rules, ["PSCI", "PHY", "CHEM"], scienceGrade, `Physical Science, Physics, or Chemistry ${scienceGrade} or better is required for engineering, architecture, and built-environment pathways.`);
  }

  if (naturalSciencePath) {
    addStrictGateRule(rules, ["MATH"], mathGrade, `Mathematics ${mathGrade} or better is required for science pathways.`);
    addStrictGateRule(rules, coreScienceCodes, scienceGrade, `A science subject ${scienceGrade} or better is required for science pathways.`);
  }

  if (healthPath) {
    addStrictGateRule(rules, ["MATH"], getGateGrade(programme, "D", "D"), "Mathematics D or better is required for direct health-science entry in this prototype.");
    addStrictGateRule(rules, coreScienceCodes, getGateGrade(programme, "D", "D"), "Biology, Physical Science, Physics, or Chemistry D or better is required for health-science pathways.");
  }

  if (agriculturePath) {
    addStrictGateRule(rules, ["AGR", "BIO", "PSCI", "FNU"], getGateGrade(programme, "D", "D"), "Agriculture, Biology, Physical Science, or Food & Nutrition D or better is required for agriculture and food-science pathways.");
  }

  if (/including\s+english\s+and\s+mathematics|credit\s+in\s+mathematics|pass\s+in\s+mathematics/.test(summary)) {
    addStrictGateRule(rules, ["MATH"], getGateGrade(programme, "D", "D"), "Mathematics is explicitly listed in the entry requirements.", "captured");
  }

  if (/physical science|double science|physics|chemistry/.test(summary) && (architectureOrEngineeringPath || naturalSciencePath || healthPath)) {
    addStrictGateRule(rules, ["PSCI", "PHY", "CHEM"], getGateGrade(programme, "D", "D"), "Physical Science, Physics, or Chemistry is explicitly listed in the entry requirements.", "captured");
  }

  if (/biology/.test(summary) && (healthPath || agriculturePath || naturalSciencePath)) {
    addStrictGateRule(rules, ["BIO", "PSCI"], getGateGrade(programme, "D", "D"), "Biology or a recognised science subject is explicitly listed in the entry requirements.", "captured");
  }

  return dedupeStrictGateRules(rules);
}

function evaluateStrictGates(programme) {
  const rules = getStrictGateRules(programme);
  const failures = rules
    .map((rule) => {
      const passingCode = rule.codes.find((code) => gradeMeets(getGradeForSubject(code), rule.minGrade));
      if (passingCode) {
        return { ...rule, met: true, passingCode, studentGrade: getGradeForSubject(passingCode), subjectLabel: rule.codes.map(getSubjectLabel).join(" or ") };
      }
      const bestCode = rule.codes.find((code) => getGradeForSubject(code)) || rule.codes[0];
      return {
        ...rule,
        met: false,
        studentGrade: getGradeForSubject(bestCode) || "missing",
        subjectLabel: rule.codes.map(getSubjectLabel).join(" or ")
      };
    })
    .filter((rule) => !rule.met);

  return {
    total: rules.length,
    passed: failures.length === 0,
    rules,
    failures
  };
}

function formatStrictGateFailure(failure) {
  if (failure.studentGrade === "missing") {
    return `${failure.subjectLabel}: no grade entered; needs ${failure.minGrade} or better.`;
  }
  return `${failure.subjectLabel}: entered ${failure.studentGrade}; needs ${failure.minGrade} or better.`;
}

function scoreRelevantSubjects(subjects) {
  const relevantSubjects = subjects?.length ? subjects : ["ENG", "MATH"];
  const scores = relevantSubjects.map((code) => getGradeForSubject(code)).filter(Boolean).map((grade) => gradePoints[grade] || 0);
  if (scores.length) return Math.round((scores.reduce((total, value) => total + value, 0) / (scores.length * 8)) * 100);
  const enteredScores = Object.values(gradeState).map((grade) => gradePoints[grade] || 0);
  if (enteredScores.length) return Math.round((enteredScores.reduce((total, value) => total + value, 0) / (enteredScores.length * 8)) * 100);
  return 58;
}

function getAcademicScore(programme) {
  if (!Object.keys(gradeState).length) return 58;
  const subjectScore = scoreRelevantSubjects(programme.subjects);
  const eligibility = evaluateRequirementRules(programme.requirementRules || []);
  return eligibility.total ? Math.round(subjectScore * 0.45 + eligibility.score * 0.55) : subjectScore;
}

function getPreferenceText() {
  return (qs("#preference-text")?.value || currentUser?.preferenceText || "").toLowerCase();
}

function getPreferenceScore(programme) {
  const preference = getPreferenceText();
  if (!preference.trim()) return 0;
  const profile = getDomainProfile(programme);
  const keywordHits = (profile.keywords || []).filter((keyword) => preference.includes(keyword)).length;
  const interestHits = (programme.interests || []).filter((interest) => preference.includes(interest.toLowerCase().replace("&", "and"))).length;
  return clamp(keywordHits * 18 + interestHits * 16, 0, 28);
}

function getInterestScore(programme) {
  const programmeInterests = programme.interests || [];
  const overlap = programmeInterests.filter((interest) => interestState.has(interest)).length;
  const stream = qs("#stream")?.value || "";
  const streamBonus =
    (stream === "Science" && programmeInterests.some((interest) => ["Technology & IT", "Health & Medicine", "Engineering", "Natural Sciences", "Agriculture"].includes(interest))) ||
    (stream === "Commercial" && programmeInterests.includes("Business & Finance")) ||
    (stream === "Agriculture" && programmeInterests.includes("Agriculture")) ||
    (stream === "General" && programmeInterests.some((interest) => ["Education & Teaching", "Law & Government", "Social Work", "Arts & Design"].includes(interest)))
      ? 12
      : 0;
  const base = interestState.size ? 42 : 46;
  return clamp(base + overlap * 24 + streamBonus + getPreferenceScore(programme));
}

function getSelectedNeedSignals() {
  return qsa("[data-need-signal]:checked").map((input) => input.value).filter(Boolean);
}

function setNeedSignalInputs(values = []) {
  const selected = new Set(values);
  qsa("[data-need-signal]").forEach((input) => {
    input.checked = selected.has(input.value);
  });
}

function getNeedScore() {
  const income = qs("#income-band")?.value || "mid";
  const base = income === "low" ? 72 : income === "mid" ? 54 : 32;
  const signalBonus = getSelectedNeedSignals().reduce((total, signal) => total + (fundingNeedSignals[signal]?.points || 0), 0);
  return clamp(base + signalBonus);
}

function getIncomeBandLabel() {
  const income = qs("#income-band")?.value || "mid";
  if (income === "low") return "Below LSL 2,500";
  if (income === "high") return "Above LSL 7,500";
  return "LSL 2,500 - 7,500";
}

function getUploadedDocumentSignals() {
  const documents = currentUser?.documents || [];
  const text = documents.map((documentItem) => `${documentItem.name} ${documentItem.status} ${documentItem.extractedTextPreview || ""}`.toLowerCase()).join(" ");
  return {
    total: documents.length,
    hasResults: /result|transcript|grade|certificate|lgcse|cosc/.test(text),
    hasIdentity: /\bid\b|identity|passport|birth|national id/.test(text),
    hasNeedEvidence: /income|salary|payslip|support|guardian|parent|household|orphan|sponsor|affidavit/.test(text),
    hasApplicationEvidence: /admission|offer|acceptance|application|registration|student number/.test(text),
    hasBankDetails: /bank|account confirmation|banking details|account number/.test(text),
    hasResidenceGuarantor: /chief|residence|village|guarantor|guardian|spouse|parent|family/.test(text),
    hasConditionalEvidence: /nmds|loan bursary|loan statement|proof of payment|council on higher education|\bche\b|evaluation|curriculum vitae|\bcv\b|study leave|employment letter/.test(text),
    extractedGradeCount: documents.reduce((total, item) => total + (item.extractedGrades?.length || 0), 0)
  };
}

function getFundingDocumentChecklist(signals = getUploadedDocumentSignals()) {
  return fundingDocumentChecks.map((item) => {
    const complete =
      (item.key === "results" && (signals.hasResults || signals.extractedGradeCount > 0)) ||
      (item.key === "identity" && signals.hasIdentity) ||
      (item.key === "needEvidence" && signals.hasNeedEvidence) ||
      (item.key === "applicationEvidence" && signals.hasApplicationEvidence) ||
      (item.key === "bankDetails" && signals.hasBankDetails) ||
      (item.key === "residenceGuarantor" && signals.hasResidenceGuarantor) ||
      (item.key === "conditionalEvidence" && signals.hasConditionalEvidence);
    return { ...item, complete };
  });
}

function getDocumentReadinessScore() {
  const signals = getUploadedDocumentSignals();
  let score = 10;
  if (signals.hasResults) score += 26;
  else if (signals.extractedGradeCount) score += 22;
  if (signals.hasIdentity) score += 18;
  if (signals.hasApplicationEvidence) score += 16;
  if (signals.hasBankDetails) score += 10;
  if (signals.hasResidenceGuarantor) score += 8;
  if (signals.hasNeedEvidence) score += 8;
  if (signals.hasConditionalEvidence) score += 6;
  score += Math.min(signals.total, 3) * 4;
  return clamp(score);
}

function getFundingBreakdown(programme) {
  const academic = getAcademicScore(programme);
  const need = getNeedScore();
  const priority = programme.nmdsPriority || 60;
  const documents = getDocumentReadinessScore();
  const confidence = programme.dataConfidence || 60;
  const total = Math.round(academic * 0.32 + need * 0.27 + priority * 0.23 + documents * 0.13 + confidence * 0.05);
  return {
    academic,
    need,
    priority,
    documents,
    confidence,
    total,
    selectedNeedSignals: getSelectedNeedSignals(),
    documentChecklist: getFundingDocumentChecklist(),
    estimateOnly: true
  };
}

function getDataConfidence(programme) {
  let score = 42;
  if (programme.duration && !/under review/i.test(programme.duration)) score += 16;
  if (programme.requirementsSummary || programme.requirements?.length) score += 20;
  if (programme.sourceUrl || programme.source || programme.sourcePath || programme.supportingSourcePath) score += 10;
  if (programme.supportingFeeSourcePath || programme.feeNote) score += 4;
  if (programme.reviewStatus === "approved" || programme.status === "approved") score += 12;
  if (programme.reviewStatus === "flagged") score -= 12;
  return clamp(score);
}

function getRequirementsForProgramme(programme, subjects) {
  if (programme.requirements?.length) return programme.requirements;
  const fromSummary = splitRequirementSummary(programme.requirementsSummary);
  if (fromSummary.length) return fromSummary;
  return subjects.slice(0, 3).map((code) => `${getSubjectLabel(code)} requirement needs admin confirmation`);
}

function requiresPriorQualification(programme) {
  const level = String(programme.level || "").toLowerCase();
  const title = String(programme.name || programme.title || "").toLowerCase();
  return /master|msc|m\.sc|phd|doctor|postgraduate|post-graduate|honours/.test(`${level} ${title}`);
}

function getMatchingProgrammeFromAdmin(programme) {
  const profile = getDomainProfile(programme);
  const inferredSubjects = unique([...profile.subjects, ...findSubjectCodes(programme.requirementsSummary), ...findSubjectCodes(getProgrammeText(programme))]).slice(0, 5);
  const requirements = getRequirementsForProgramme(programme, inferredSubjects);
  const requirementRules = parseRequirementRules(programme.requirementsSummary || "");
  if (requiresPriorQualification(programme)) {
    requirementRules.push({ type: "prior-qualification", text: "Prior tertiary qualification required" });
  }
  return {
    id: programme.id,
    title: programme.name,
    institution: programme.institution,
    shortInstitution: getInstitutionShortName(programme.institution),
    faculty: programme.faculty || programme.category || "Faculty under review",
    category: programme.category || profile.key,
    level: programme.level || "Level under review",
    duration: programme.duration || "Duration under review",
    status: programme.reviewStatus === "approved" ? "approved" : "review",
    reviewStatus: programme.reviewStatus,
    source: programme.sourceUrl || programme.sourcePath || programme.supportingSourcePath || "Source under review",
    subjects: inferredSubjects.length ? inferredSubjects : profile.subjects,
    interests: unique(profile.interests),
    requirements,
    requirementRules,
    careers: programme.careers?.length ? programme.careers : profile.careers,
    skills: profile.skills,
    labourSector: profile.sector,
    nmdsPriority: profile.priority,
    dataConfidence: getDataConfidence(programme),
    sourceType: programme.sourceType || "catalogue"
  };
}

function getMatchingProgrammeFromSeed(programme) {
  const requirementRules = parseRequirementRules((programme.requirements || []).join(". "));
  return {
    ...programme,
    requirementRules,
    reviewStatus: programme.status,
    dataConfidence: 92
  };
}

function getMatchingCatalogue() {
  const realProgrammes = adminProgrammes
    .filter((programme) => programme.reviewStatus !== "rejected")
    .map(getMatchingProgrammeFromAdmin);
  return realProgrammes.length ? realProgrammes : programmes.filter((programme) => programme.status === "approved").map(getMatchingProgrammeFromSeed);
}

function getFundingScore(programme) {
  return getFundingBreakdown(programme).total;
}

function formatRequirementGap(detail) {
  if (detail.type === "prior-qualification") {
    return "Requires a prior tertiary qualification or advanced standing, not only high-school results.";
  }
  if (detail.type === "grade-count") {
    const missing = Math.max(0, detail.minimum - detail.actual);
    return missing
      ? `Needs ${missing} more subject${missing === 1 ? "" : "s"} at ${detail.minGrade} or better.`
      : detail.text;
  }
  if (detail.type === "count") {
    const missing = Math.max(0, detail.minimum - detail.actual);
    return missing
      ? `Needs ${missing} more captured subject${missing === 1 ? "" : "s"}.`
      : detail.text;
  }
  if (detail.studentGrade === "missing") return `${detail.subjectLabel}: no grade entered yet; needs ${detail.minGrade} or better.`;
  return `${detail.subjectLabel}: entered ${detail.studentGrade}, needs ${detail.minGrade} or better.`;
}

function getMatchTier(scores, evaluation, programme, strictGateEvaluation) {
  if (strictGateEvaluation?.failures?.length) return "blocked";
  if (!evaluation.total) return programme.dataConfidence >= 75 && scores.academic >= 65 ? "almost" : "explore";
  if (evaluation.missing.some((detail) => detail.type === "prior-qualification")) return "explore";
  if (evaluation.missing.length === 0 && scores.academic >= 52) return "qualified";
  if (evaluation.score >= 62 || (evaluation.nearMisses.length && evaluation.score >= 55) || (scores.academic >= 66 && evaluation.score >= 45)) return "almost";
  return "explore";
}

function getTierRank(tier) {
  return tierMeta[tier]?.rank ?? tierMeta.explore.rank;
}

function getMatchTierCounts(matches = latestMatches) {
  return matches.reduce(
    (counts, programme) => {
      const tier = programme.match?.tier || "explore";
      counts[tier] = (counts[tier] || 0) + 1;
      return counts;
    },
    { qualified: 0, almost: 0, explore: 0 }
  );
}

function getMatchExplanations(programme, scores, evaluation, tier, strictGateEvaluation) {
  const reasons = [];
  const cautions = [];
  const matchingInterests = (programme.interests || []).filter((interest) => interestState.has(interest));
  const tierLabel = tierMeta[tier]?.label || "Explore";
  reasons.push(`${tierLabel} pathway based on current marks and captured requirements.`);
  if (matchingInterests.length) reasons.push(`Interest fit: ${matchingInterests.slice(0, 2).join(", ")}`);
  if (scores.academic >= 70) reasons.push("Your selected grades are strong for the inferred subject profile.");
  if (scores.funding >= 78) reasons.push("Funding readiness is promising for this pathway.");
  if (programme.nmdsPriority >= 82) reasons.push("This sits in a high-priority development area.");
  if (!reasons.length) reasons.push("This is a possible exploratory match, but it needs closer checking.");

  const strictGateGaps = (strictGateEvaluation?.failures || []).map(formatStrictGateFailure);
  const requirementGaps = evaluation.missing.map(formatRequirementGap).slice(0, 3);
  if (strictGateGaps.length) cautions.push(...strictGateGaps.slice(0, 2));
  if (tier !== "qualified" && requirementGaps.length) cautions.push(...requirementGaps.slice(0, 2));
  if (tier === "almost" && !requirementGaps.length) cautions.push("This is close, but final entry rules should be confirmed before applying.");
  if (tier === "explore") cautions.push("Treat this as an exploration path unless more grades or confirmed requirements improve the match.");
  if (tier === "blocked") cautions.push("This pathway is not shown as a recommendation because a hard subject requirement is missing.");
  if (programme.dataConfidence < 70) cautions.push("Some catalogue fields are still incomplete or awaiting admin review.");
  if (/under review/i.test(programme.duration)) cautions.push("Duration is not confirmed yet.");
  return { reasons: reasons.slice(0, 3), cautions: unique(cautions).slice(0, 3), requirementGaps: unique([...strictGateGaps, ...requirementGaps]) };
}

function getProgrammeMatch(programme) {
  const academic = getAcademicScore(programme);
  const interest = getInterestScore(programme);
  const evaluation = evaluateRequirementRules(programme.requirementRules || []);
  const strictGateEvaluation = evaluateStrictGates(programme);
  const eligibility = evaluation.score;
  const fundingBreakdown = getFundingBreakdown(programme);
  const funding = fundingBreakdown.total;
  const confidence = programme.dataConfidence || 60;
  const priority = programme.nmdsPriority || 60;
  const preTierOverall = Math.round(academic * 0.36 + interest * 0.24 + eligibility * 0.18 + funding * 0.14 + confidence * 0.08);
  const scores = {
    academic,
    interests: interest,
    interest,
    eligibility,
    funding,
    fundingBreakdown,
    confidence,
    priority,
    overall: preTierOverall
  };
  const tier = getMatchTier(scores, evaluation, programme, strictGateEvaluation);
  const tierPenalty = tier === "qualified" ? 0 : tier === "almost" ? 4 : tier === "blocked" ? 44 : 12;
  const overall = tier === "blocked" ? clamp(preTierOverall - tierPenalty, 0, 38) : clamp(preTierOverall - tierPenalty);
  const strictGateFailures = strictGateEvaluation.failures.map(formatStrictGateFailure);
  return {
    ...scores,
    overall,
    tier,
    tierLabel: tierMeta[tier]?.label || "Explore",
    hardGatePassed: strictGateEvaluation.passed,
    hardGateFailures: strictGateFailures,
    requirementGaps: unique([...strictGateFailures, ...evaluation.missing.map(formatRequirementGap)]),
    requirementDetails: evaluation.details,
    ...getMatchExplanations(programme, { ...scores, overall }, evaluation, tier, strictGateEvaluation)
  };
}
function getNmdsReadiness() {
  const matches = getMatchingCatalogue().map((programme) => ({ ...programme, match: getProgrammeMatch(programme) }));
  const rankedMatches = matches
    .filter((programme) => programme.match.tier !== "blocked")
    .sort((a, b) => getTierRank(a.match.tier) - getTierRank(b.match.tier) || b.match.overall - a.match.overall)
    .slice(0, 12);
  const signals = getUploadedDocumentSignals();
  const documentChecklist = getFundingDocumentChecklist(signals);
  const selectedNeedSignals = getSelectedNeedSignals();
  if (!rankedMatches.length) {
    return {
      academic: 0,
      need: getNeedScore(),
      priority: 0,
      documents: getDocumentReadinessScore(),
      confidence: 0,
      readiness: 0,
      label: "Estimate only",
      incomeBand: getIncomeBandLabel(),
      selectedNeedSignals,
      signals,
      documentChecklist,
      notes: ["No programme matches are available yet."]
    };
  }
  const academic = Math.round(rankedMatches.reduce((sum, item) => sum + item.match.academic, 0) / rankedMatches.length);
  const priority = Math.round(rankedMatches.reduce((sum, item) => sum + item.match.priority, 0) / rankedMatches.length);
  const confidence = Math.round(rankedMatches.reduce((sum, item) => sum + item.match.confidence, 0) / rankedMatches.length);
  const need = getNeedScore();
  const documents = getDocumentReadinessScore();
  const readiness = Math.round(academic * 0.34 + need * 0.25 + priority * 0.22 + documents * 0.14 + confidence * 0.05);
  const notes = [];
  const missingDocuments = documentChecklist.filter((item) => !item.complete).map((item) => item.label);
  if (missingDocuments.length) notes.push(`Missing/unclear documents: ${missingDocuments.slice(0, 3).join(", ")}.`);
  if (!selectedNeedSignals.length && need < 70) notes.push("Add background indicators only when they truly apply; they affect the need estimate.");
  if (confidence < 70) notes.push("Some programme data is still under review, so verify requirements before applying.");
  if (rankedMatches.some((item) => item.match.tier === "qualified")) notes.push("At least one matched programme appears academically reachable from the current profile.");
  notes.push("Estimate only: NMDS or any sponsor can request different evidence and make the final decision.");
  return {
    academic,
    need,
    priority,
    documents,
    confidence,
    readiness,
    label: readiness >= 78 ? "Strong estimate" : readiness >= 62 ? "Moderate estimate" : "Needs preparation",
    incomeBand: getIncomeBandLabel(),
    selectedNeedSignals,
    signals,
    documentChecklist,
    notes
  };
}

function updateReadiness() {
  const readiness = getNmdsReadiness();
  qs("#academic-fit").textContent = `${readiness.academic}%`;
  qs("#need-fit").textContent = `${readiness.need}%`;
  qs("#priority-fit").textContent = `${readiness.priority}%`;
  qs("#document-fit").textContent = `${readiness.documents}%`;
  qs("#nmds-estimate-label").textContent = readiness.label;
  qs("#nmds-income-label").textContent = readiness.incomeBand;
  qs("#nmds-score").textContent = `${readiness.readiness}%`;
  qs("#nmds-bar").style.width = `${readiness.readiness}%`;
  const notesEl = qs("#nmds-notes");
  if (notesEl) {
    notesEl.innerHTML = readiness.notes.map((note) => `<li>${escapeHtml(note)}</li>`).join("");
  }
  const checklistEl = qs("#nmds-document-checklist");
  if (checklistEl) {
    checklistEl.innerHTML = readiness.documentChecklist
      .map(
        (item) => `
          <div class="${item.complete ? "complete" : ""}">
            <i data-lucide="${item.complete ? "check-circle-2" : "circle"}"></i>
            <span>${escapeHtml(item.label)}</span>
          </div>
        `
      )
      .join("");
  }
}

function syncCurrentUserProfile() {
  if (!currentUser) return;
  currentUser.name = qs("#full-name").value.trim() || currentUser.name;
  currentUser.district = qs("#district").value;
  currentUser.stream = qs("#stream").value;
  currentUser.leavingYear = qs("#leaving-year").value;
  currentUser.incomeBand = qs("#income-band")?.value || "mid";
  currentUser.needSignals = getSelectedNeedSignals();
  currentUser.preferenceText = qs("#preference-text")?.value.trim() || "";
  currentUser.grades = { ...gradeState };
  addActivityToUser(currentUser, "profile_updated", "Updated student profile", {}, { throttleMs: 120000 });
  saveAuthUsers();
  updateUserShell();
}

function getProfileCompletion() {
  const filledCore = [qs("#full-name").value, qs("#district").value, qs("#leaving-year").value, qs("#stream").value].filter(Boolean).length;
  const gradeCount = Object.keys(gradeState).length;
  const interestCount = interestState.size;
  const documentCount = currentUser?.documents?.length || 0;
  const preferenceBonus = getPreferenceText().trim().length > 20 ? 8 : 0;
  const score = filledCore * 12 + Math.min(gradeCount, 6) * 5 + Math.min(interestCount, 4) * 6 + Math.min(documentCount, 2) * 8 + preferenceBonus;
  return Math.min(100, score);
}

function formatFileSize(size) {
  const bytes = Number(size || 0);
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

function normalizeDocumentItem(documentItem) {
  return {
    id: documentItem.id || `doc-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    name: documentItem.name || documentItem.originalName || "Document",
    size: Number(documentItem.size || documentItem.sizeBytes || 0),
    status: documentItem.status || "Uploaded - OCR pending",
    uploadedAt: documentItem.uploadedAt || new Date().toISOString(),
    url: documentItem.url || null,
    contentType: documentItem.contentType || null,
    extractionStatus: documentItem.extractionStatus || "pending",
    extractedGrades: Array.isArray(documentItem.extractedGrades) ? documentItem.extractedGrades : [],
    extractedTextPreview: documentItem.extractedTextPreview || "",
    extractionError: documentItem.extractionError || null,
    extractedAt: documentItem.extractedAt || null
  };
}

function mergeDocuments(existing = [], incoming = []) {
  const merged = new Map();
  [...existing, ...incoming].map(normalizeDocumentItem).forEach((documentItem) => {
    merged.set(documentItem.id, documentItem);
  });
  return Array.from(merged.values()).sort((a, b) => String(b.uploadedAt || "").localeCompare(String(a.uploadedAt || "")));
}

function renderExtractedGrades(documentItem) {
  const grades = documentItem.extractedGrades || [];
  if (grades.length) {
    return `
      <div class="extracted-grade-list">
        ${grades
          .map(
            (item) => `
              <span class="extracted-grade">
                ${escapeHtml(item.subject || item.code)} <strong>${escapeHtml(item.grade)}</strong>
              </span>
            `
          )
          .join("")}
      </div>
      <button class="secondary-action compact-action" type="button" data-apply-document-grades="${escapeHtml(documentItem.id)}">
        Apply detected grades
      </button>
    `;
  }
  if (documentItem.extractionStatus === "failed") {
    return `<small class="document-warning">${escapeHtml(documentItem.extractionError || "OCR extraction failed.")}</small>`;
  }
  if (documentItem.extractionStatus === "no_grades") {
    return `<small class="document-warning">Text was read, but no matching grades were detected.</small>`;
  }
  if (documentItem.extractionStatus === "no_text") {
    return `<small class="document-warning">No readable text was detected.</small>`;
  }
  return "";
}

function renderDocumentList() {
  const list = qs("#document-list");
  const documents = currentUser?.documents || [];
  qs("#document-count").textContent = documents.length;
  if (!documents.length) {
    list.innerHTML = `
      <article>
        <i data-lucide="file-text"></i>
        <div>
          <strong>Transcript or results slip</strong>
          <span>Waiting for upload</span>
        </div>
      </article>
      <article>
        <i data-lucide="badge-check"></i>
        <div>
          <strong>National ID or passport</strong>
          <span>Waiting for upload</span>
        </div>
      </article>
    `;
    return;
  }
  list.innerHTML = documents
    .map((documentItem) => `
      <article>
        <i data-lucide="file-check-2"></i>
        <div class="document-meta">
          <strong>${escapeHtml(documentItem.name)}</strong>
          <span>${escapeHtml(documentItem.status)} - ${formatFileSize(documentItem.size)}</span>
          ${documentItem.url ? `<a href="${escapeHtml(documentItem.url)}" target="_blank" rel="noreferrer">Open file</a>` : ""}
          ${renderExtractedGrades(documentItem)}
        </div>
        ${
          documentItem.url
            ? `<button class="icon-button soft" type="button" title="Rerun OCR" data-rerun-document-ocr="${escapeHtml(documentItem.id)}">
                <i data-lucide="scan-text"></i>
              </button>`
            : ""
        }
        <button class="icon-button soft" type="button" title="Remove document" data-delete-document="${escapeHtml(documentItem.id)}">
          <i data-lucide="trash-2"></i>
        </button>
      </article>
    `)
    .join("");
}

function renderStudentDashboard() {
  if (!qs("#profile-completion")) return;
  const completion = getProfileCompletion();
  const shortlistCount = currentUser?.shortlist?.length || 0;
  const documentCount = currentUser?.documents?.length || 0;
  qs("#profile-completion").textContent = `${completion}%`;
  qs("#shortlist-count").textContent = shortlistCount;
  qs("#next-action-label").textContent = documentCount < 2 ? "Add documents" : shortlistCount ? "Compare saved" : "Save matches";
  renderDocumentList();
  if (window.lucide) window.lucide.createIcons();
}

async function uploadDocumentsToServer(files) {
  const formData = new FormData();
  formData.append("user_id", currentUser.id);
  Array.from(files).forEach((file) => formData.append("files", file));
  const response = await fetch("/api/documents/upload", {
    method: "POST",
    body: formData
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.ok) throw new Error(data.detail || data.error || `Upload failed with ${response.status}`);
  return data.documents || [];
}

async function loadCurrentUserDocuments() {
  if (!serverDatabaseAvailable || !currentUser?.id) return;
  try {
    const response = await fetch(`/api/documents/user/${encodeURIComponent(currentUser.id)}`, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`Document list returned ${response.status}`);
    const data = await response.json();
    if (!Array.isArray(data.documents)) return;
    currentUser.documents = mergeDocuments(currentUser.documents || [], data.documents);
    saveAuthUsers();
    renderStudentDashboard();
  } catch (error) {
    qs("#dropzone-text").textContent = "Documents are stored locally until the upload service is reachable";
  }
}

function persistCurrentGrades() {
  if (!currentUser) return;
  currentUser.grades = { ...gradeState };
  addActivityToUser(currentUser, "grades_updated", "Updated grades", { subjects: Object.keys(gradeState).length }, { throttleMs: 60000 });
  saveAuthUsers();
}

function applyExtractedGrades(documentId) {
  if (!currentUser) return;
  const documentItem = (currentUser.documents || []).find((item) => item.id === documentId);
  const grades = documentItem?.extractedGrades || [];
  if (!grades.length) {
    qs("#dropzone-text").textContent = "No detected grades to apply";
    return;
  }
  grades.forEach((item) => {
    if (item.code && gradePoints[item.grade] !== undefined) gradeState[item.code] = item.grade;
  });
  persistCurrentGrades();
  renderGrades();
  calculateMatches();
  renderStudentDashboard();
  recordCurrentUserActivity("document_grades_applied", "Applied detected document grades", { count: grades.length });
  qs("#dropzone-text").textContent = `${grades.length} detected grade(s) applied`;
}

async function rerunDocumentOcr(documentId) {
  if (!serverDatabaseAvailable || !currentUser) return;
  qs("#dropzone-text").textContent = "Rerunning OCR...";
  try {
    const response = await fetch(`/api/documents/${encodeURIComponent(documentId)}/extract`, { method: "POST" });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) throw new Error(data.detail || data.error || `OCR returned ${response.status}`);
    currentUser.documents = mergeDocuments(
      (currentUser.documents || []).filter((item) => item.id !== documentId),
      [data.document]
    );
    addActivityToUser(currentUser, "document_ocr", "Reran document OCR", { document: data.document.name || documentId });
    saveAuthUsers();
    renderStudentDashboard();
    qs("#dropzone-text").textContent = `${data.document.extractedGrades?.length || 0} grade suggestion(s) detected`;
  } catch (error) {
    qs("#dropzone-text").textContent = "OCR rerun failed";
  }
}

async function addDocuments(files) {
  if (!currentUser) return;
  const selectedFiles = Array.from(files || []);
  if (!selectedFiles.length) return;
  const dropzoneText = qs("#dropzone-text");
  dropzoneText.textContent = `Uploading ${selectedFiles.length} file(s)...`;
  let incoming = [];
  try {
    incoming =
      serverDatabaseAvailable && window.FormData
        ? await uploadDocumentsToServer(selectedFiles)
        : selectedFiles.map((file) => ({
            name: file.name,
            size: file.size || 0,
            status: "Stored locally - OCR pending"
          }));
    dropzoneText.textContent =
      serverDatabaseAvailable && incoming.some((documentItem) => documentItem.url)
        ? `${incoming.length} file(s) uploaded - ${incoming.reduce((total, item) => total + (item.extractedGrades?.length || 0), 0)} grade suggestion(s) detected`
        : `${incoming.length} file(s) stored locally - OCR pending`;
  } catch (error) {
    incoming = selectedFiles.map((file) => ({
      name: file.name,
      size: file.size || 0,
      status: "Stored locally - upload retry needed"
    }));
    dropzoneText.textContent = "Upload failed; saved document names locally";
  }
  currentUser.documents = mergeDocuments(currentUser.documents || [], incoming);
  addActivityToUser(currentUser, "document_upload", "Uploaded document(s)", { count: incoming.length });
  saveAuthUsers();
  renderStudentDashboard();
}

async function removeDocument(documentId) {
  if (!currentUser || !documentId) return;
  const documentItem = (currentUser.documents || []).find((item) => item.id === documentId);
  try {
    if (serverDatabaseAvailable && documentItem?.url) {
      const response = await fetch(`/api/documents/${encodeURIComponent(documentId)}`, { method: "DELETE" });
      if (!response.ok) throw new Error(`Document delete returned ${response.status}`);
    }
    currentUser.documents = (currentUser.documents || []).filter((item) => item.id !== documentId);
    addActivityToUser(currentUser, "document_removed", "Removed a document", { document: documentItem?.name || documentId });
    qs("#dropzone-text").textContent = "Document removed";
  } catch (error) {
    qs("#dropzone-text").textContent = "Could not remove document from the server";
  }
  saveAuthUsers();
  renderStudentDashboard();
}

function toggleShortlist(programmeId) {
  if (!currentUser) return;
  currentUser.shortlist ||= [];
  if (currentUser.shortlist.includes(programmeId)) {
    currentUser.shortlist = currentUser.shortlist.filter((id) => id !== programmeId);
    addActivityToUser(currentUser, "shortlist_updated", "Removed a saved programme", { programmeId });
  } else {
    currentUser.shortlist.push(programmeId);
    addActivityToUser(currentUser, "shortlist_updated", "Saved a programme", { programmeId });
  }
  saveAuthUsers();
  renderResults();
  renderStudentDashboard();
}

function calculateMatches() {
  selectedResultInstitution = null;
  const evaluatedMatches = getMatchingCatalogue()
    .map((programme) => ({ ...programme, match: getProgrammeMatch(programme) }))
    .sort((a, b) => getTierRank(a.match.tier) - getTierRank(b.match.tier) || b.match.overall - a.match.overall || b.match.eligibility - a.match.eligibility);
  latestBlockedMatches = evaluatedMatches.filter((programme) => programme.match.tier === "blocked");
  latestMatches = evaluatedMatches.filter((programme) => programme.match.tier !== "blocked").slice(0, 80);
  recordCurrentUserActivity(
    "matches_calculated",
    "Calculated programme matches",
    { visibleMatches: latestMatches.length, blockedMatches: latestBlockedMatches.length },
    { throttleMs: 90000 }
  );
  updateReadiness();
  renderResults();
  renderStudentDashboard();
}

function renderProgrammeCard(programme) {
  const saved = currentUser?.shortlist?.includes(programme.id);
  const eligibilityBadge = programme.match.eligibility >= 70 ? "green" : programme.match.eligibility >= 45 ? "amber" : "red";
  const confidenceBadge = programme.match.confidence >= 75 ? "green" : programme.match.confidence >= 55 ? "amber" : "red";
  const tier = tierMeta[programme.match.tier] || tierMeta.explore;
  const fundingBreakdown = programme.match.fundingBreakdown || {};
  return `
    <article class="programme-card">
      <div class="programme-top">
        <div>
          <h4 class="programme-title">${escapeHtml(programme.title)}</h4>
          <div class="programme-meta">${escapeHtml(programme.institution)} - ${escapeHtml(programme.duration)} - ${escapeHtml(programme.faculty)}</div>
          <div class="badge-row">
            <span class="badge green">${escapeHtml(programme.level)}</span>
            <span class="badge blue">${escapeHtml(programme.shortInstitution)}</span>
            <span class="badge amber">NMDS ${programme.nmdsPriority}%</span>
            <span class="badge ${tier.badge}">${tier.label}</span>
            <span class="badge ${eligibilityBadge}">Eligibility ${programme.match.eligibility}%</span>
            <span class="badge ${confidenceBadge}">Data ${programme.match.confidence}%</span>
          </div>
        </div>
        <div class="programme-card-actions">
          <div class="match-badge tier-${programme.match.tier}">${programme.match.overall}%</div>
          <button class="secondary-action" type="button" data-shortlist-programme="${escapeHtml(programme.id)}">
            <i data-lucide="${saved ? "bookmark-check" : "bookmark-plus"}"></i>
            ${saved ? "Saved" : "Save"}
          </button>
        </div>
      </div>
      <div class="programme-detail">
        <div class="detail-block">
          <h5>Requirements</h5>
          <ul>${programme.requirements.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
        </div>
        <div class="detail-block">
          <h5>Why this matched</h5>
          <ul>${programme.match.reasons.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
        </div>
        <div class="detail-block">
          <h5>Careers & skills</h5>
          <ul>${[...programme.careers.slice(0, 2), ...programme.skills.slice(0, 2)].map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
        </div>
        <div class="detail-block">
          <h5>Funding estimate</h5>
          <ul>
            <li>Academic ${fundingBreakdown.academic ?? programme.match.academic}%</li>
            <li>Need ${fundingBreakdown.need ?? getNeedScore()}%</li>
            <li>Priority ${fundingBreakdown.priority ?? programme.match.priority}%</li>
            <li>Documents ${fundingBreakdown.documents ?? getDocumentReadinessScore()}%</li>
          </ul>
        </div>
      </div>
      ${
        programme.match.cautions.length
          ? `<div class="programme-alerts">${programme.match.cautions.map((item) => `<span><i data-lucide="triangle-alert"></i>${escapeHtml(item)}</span>`).join("")}</div>`
          : ""
      }
    </article>
  `;
}

function getInstitutionMatchGroups() {
  const displayMatches = latestMatches;
  const grouped = new Map();
  displayMatches.forEach((programme) => {
    const key = programme.institution || "Unknown institution";
    if (!grouped.has(key)) {
      grouped.set(key, {
        institution: key,
        shortInstitution: programme.shortInstitution || getInstitutionShortName(key),
        programmes: [],
        bestOverall: 0,
        bestEligibility: 0,
        bestFunding: 0,
        bestTierRank: 99,
        bestProgramme: programme.title,
        tierCounts: { qualified: 0, almost: 0, explore: 0 },
        reviewCount: 0
      });
    }
    const group = grouped.get(key);
    group.programmes.push(programme);
    const tier = programme.match.tier || "explore";
    const tierRank = getTierRank(tier);
    const previousBestTierRank = group.bestTierRank;
    group.tierCounts[tier] = (group.tierCounts[tier] || 0) + 1;
    if (tierRank < previousBestTierRank || (tierRank === previousBestTierRank && programme.match.overall > group.bestOverall)) {
      group.bestTier = tier;
      group.bestOverall = programme.match.overall;
      group.bestProgramme = programme.title;
    }
    group.bestTierRank = Math.min(group.bestTierRank, tierRank);
    group.bestEligibility = Math.max(group.bestEligibility, programme.match.eligibility);
    group.bestFunding = Math.max(group.bestFunding, programme.match.funding);
    if (programme.reviewStatus !== "approved") group.reviewCount += 1;
  });
  return Array.from(grouped.values()).sort((a, b) => a.bestTierRank - b.bestTierRank || b.bestOverall - a.bestOverall || b.bestEligibility - a.bestEligibility);
}

function renderInstitutionGroup(group) {
  const active = selectedResultInstitution === group.institution;
  const eligibilityBadge = group.bestEligibility >= 70 ? "green" : group.bestEligibility >= 45 ? "amber" : "red";
  const bestTier = tierMeta[group.bestTier] || tierMeta.explore;
  const visibleProgrammes = group.programmes.slice(0, 10);
  return `
    <article class="institution-match ${active ? "active" : ""}">
      <button class="institution-match-head" type="button" data-institution-result="${escapeHtml(group.institution)}" aria-expanded="${active}">
        <div class="institution-icon">${escapeHtml(group.shortInstitution.slice(0, 4))}</div>
        <div class="institution-match-main">
          <h4>${escapeHtml(group.institution)}</h4>
          <p>${group.programmes.length} matched programme${group.programmes.length === 1 ? "" : "s"} - best match: ${escapeHtml(group.bestProgramme)}</p>
          <div class="badge-row">
            <span class="badge blue">${escapeHtml(group.shortInstitution)}</span>
            <span class="badge ${bestTier.badge}">Best: ${bestTier.label}</span>
            ${group.tierCounts.qualified ? `<span class="badge green">${group.tierCounts.qualified} qualified</span>` : ""}
            ${group.tierCounts.almost ? `<span class="badge amber">${group.tierCounts.almost} almost</span>` : ""}
            ${group.tierCounts.explore ? `<span class="badge blue">${group.tierCounts.explore} explore</span>` : ""}
            <span class="badge ${eligibilityBadge}">Eligibility ${group.bestEligibility}%</span>
            <span class="badge amber">Funding ${group.bestFunding}%</span>
            ${group.reviewCount ? `<span class="badge">Review ${group.reviewCount}</span>` : ""}
          </div>
        </div>
        <div class="institution-match-score">
          <strong>${group.bestOverall}%</strong>
          <span>${active ? "Hide" : "View"} programmes</span>
        </div>
      </button>
      ${
        active
          ? `<div class="institution-programmes">
              ${visibleProgrammes.map(renderProgrammeCard).join("")}
              ${
                group.programmes.length > visibleProgrammes.length
                  ? `<p class="institution-more-note">${group.programmes.length - visibleProgrammes.length} more lower-ranked matches from this institution are hidden for now.</p>`
                  : ""
              }
            </div>`
          : ""
      }
    </article>
  `;
}

function renderStrictGateNotice() {
  if (!latestBlockedMatches.length) return "";
  const examples = latestBlockedMatches
    .slice(0, 3)
    .map((programme) => `${programme.title}: ${(programme.match.hardGateFailures || programme.match.requirementGaps || []).slice(0, 1).join("")}`)
    .filter(Boolean);
  return `
    <article class="strict-match-note">
      <div>
        <strong>${latestBlockedMatches.length} programme${latestBlockedMatches.length === 1 ? "" : "s"} hidden by strict subject checks</strong>
        <p>EduGuide is not recommending programmes where hard requirements like Mathematics, Physical Science, Biology, or Agriculture/Food & Nutrition are missing.</p>
      </div>
      ${examples.length ? `<ul>${examples.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
    </article>
  `;
}

function renderBlockedProgrammeCard(programme) {
  const failures = programme.match.hardGateFailures?.length ? programme.match.hardGateFailures : programme.match.requirementGaps || [];
  return `
    <article class="blocked-programme-card">
      <div class="blocked-programme-top">
        <div>
          <h4>${escapeHtml(programme.title)}</h4>
          <p>${escapeHtml(programme.institution)} - ${escapeHtml(programme.duration)} - ${escapeHtml(programme.faculty)}</p>
          <div class="badge-row">
            <span class="badge blue">${escapeHtml(programme.shortInstitution)}</span>
            <span class="badge ${tierMeta.blocked.badge}">${tierMeta.blocked.label}</span>
            <span class="badge amber">Interest ${programme.match.interest}%</span>
            <span class="badge red">Eligibility ${programme.match.eligibility}%</span>
          </div>
        </div>
        <div class="blocked-programme-score">
          <strong>${programme.match.overall}%</strong>
          <span>future fit</span>
        </div>
      </div>
      <div class="blocked-fixes">
        <h5>What must improve first</h5>
        <ul>${failures.slice(0, 4).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      </div>
      <div class="blocked-requirements">
        <h5>Captured requirements</h5>
        <ul>${programme.requirements.slice(0, 4).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      </div>
    </article>
  `;
}

function renderBlockedMatches() {
  if (!latestBlockedMatches.length) {
    return `
      <article class="admin-empty">
        <h4>No blocked pathways right now.</h4>
        <p>Your current profile did not trigger strict subject blockers. Keep checking final entry requirements with each institution.</p>
      </article>
    `;
  }
  const visibleBlocked = latestBlockedMatches.slice(0, 18);
  return `
    <article class="blocked-pathway-intro">
      <div>
        <p class="section-kicker">Future pathways</p>
        <h4>${latestBlockedMatches.length} programme${latestBlockedMatches.length === 1 ? "" : "s"} not eligible yet</h4>
        <p>These are not recommendations for applying now. They are useful if the student wants to supplement or improve a required subject.</p>
      </div>
    </article>
    <div class="blocked-programme-list">
      ${visibleBlocked.map(renderBlockedProgrammeCard).join("")}
    </div>
    ${
      latestBlockedMatches.length > visibleBlocked.length
        ? `<p class="institution-more-note">${latestBlockedMatches.length - visibleBlocked.length} more blocked pathways are hidden for now.</p>`
        : ""
    }
  `;
}

function updateBlockedTabCount() {
  const count = qs("#blocked-tab-count");
  if (!count) return;
  count.textContent = latestBlockedMatches.length ? latestBlockedMatches.length : "";
  count.hidden = !latestBlockedMatches.length;
}

function renderInstitutionMatches() {
  const groups = getInstitutionMatchGroups();
  if (!groups.length) {
    return `
      ${renderStrictGateNotice()}
      <article class="admin-empty">
        <h4>No eligible institution matches yet.</h4>
        <p>Add or confirm the required subjects, especially Mathematics and Physical Science for science, technology, engineering, and architecture pathways.</p>
      </article>
    `;
  }
  if (selectedResultInstitution && !groups.some((group) => group.institution === selectedResultInstitution)) {
    selectedResultInstitution = null;
  }
  const tierCounts = getMatchTierCounts();
  return `
    <div class="institution-match-summary">
      <div>
        <strong>${groups.length} institution${groups.length === 1 ? "" : "s"} found</strong>
        <span>${latestMatches.length} programme matches processed from your marks and preferences.</span>
      </div>
      <div class="tier-summary">
        <span class="badge green">${tierCounts.qualified} qualified</span>
        <span class="badge amber">${tierCounts.almost} almost</span>
        <span class="badge blue">${tierCounts.explore} explore</span>
      </div>
    </div>
    <div class="institution-match-list">
      ${groups.map(renderInstitutionGroup).join("")}
    </div>
    ${renderStrictGateNotice()}
  `;
}

function renderResults() {
  updateBlockedTabCount();
  const blockedPanel = qs("#tab-blocked");
  if (blockedPanel) blockedPanel.innerHTML = renderBlockedMatches();
  if (!latestMatches.length) {
    qs("#tab-programmes").innerHTML = `
      ${renderStrictGateNotice()}
      <article class="admin-empty">
        <h4>No eligible programme matches yet.</h4>
        <p>Enter the subjects required for your target pathway. Technology usually needs Mathematics; engineering, architecture, and many science programmes need Mathematics plus Physical Science or a recognised science subject.</p>
      </article>
    `;
    qs("#tab-skills").innerHTML = "";
    qs("#tab-labour").innerHTML = "";
    return;
  }
  const groups = getInstitutionMatchGroups();
  qs("#results-heading").textContent = `${qs("#full-name").value || "Student"} - ${groups.length} matched institutions`;
  qs("#tab-programmes").innerHTML = renderInstitutionMatches();

  const skillScores = new Map();
  latestMatches.slice(0, 4).forEach((programme) => {
    programme.skills.forEach((skill) => {
      const current = skillScores.get(skill) || 0;
      skillScores.set(skill, Math.max(current, Math.round(programme.match.overall * 0.82)));
    });
  });
  qs("#tab-skills").innerHTML = Array.from(skillScores.entries())
    .slice(0, 8)
    .map(([skill, score]) => `
      <article class="skill-card">
        <div class="skill-row"><strong>${escapeHtml(skill)}</strong><span>${score}%</span></div>
        <div class="skill-bar"><div style="width:${score}%"></div></div>
      </article>
    `)
    .join("");

  const activeSectors = new Set(latestMatches.slice(0, 5).map((programme) => programme.labourSector));
  const labourCards = labourNotes.filter((item) => activeSectors.has(item.sector));
  const genericLabourCards = Array.from(activeSectors)
    .filter((sector) => !labourCards.some((item) => item.sector === sector))
    .map((sector) => ({
      sector,
      note: "This pathway appears in the matched catalogue. Labour-market detail still needs confirmation from reports, employer data, or sector news."
    }));
  qs("#tab-labour").innerHTML = [...labourCards, ...genericLabourCards]
    .map((item) => `
      <article class="labour-card">
        <h4>${escapeHtml(item.sector)}</h4>
        <p>${escapeHtml(item.note)}</p>
      </article>
    `)
    .join("");

  const overall = latestMatches[0]?.match.overall || 0;
  qs("#profile-match").textContent = `${overall}%`;
  qs(".ring-score").style.background = `
    radial-gradient(circle at center, #fff 0 57%, transparent 58%),
    conic-gradient(var(--brand) 0 ${overall}%, #e6eee9 ${overall}% 100%)
  `;
  qs("#score-list").innerHTML = [
    ["Academic", latestMatches[0]?.match.academic || 0],
    ["Interest", latestMatches[0]?.match.interest || 0],
    ["Eligibility", latestMatches[0]?.match.eligibility || 0],
    ["Scholarship estimate", latestMatches[0]?.match.funding || 0],
    ["Data confidence", latestMatches[0]?.match.confidence || 0]
  ]
    .map(([label, value]) => `
      <div>
        <div class="score-row"><span>${label}</span><strong>${value}%</strong></div>
        <div class="score-bar"><div style="width:${value}%"></div></div>
      </div>
    `)
    .join("");
  renderStudentDashboard();
  if (window.lucide) window.lucide.createIcons();
}

function getAiProfilePayload() {
  return {
    name: qs("#full-name").value || currentUser?.name || "Student",
    district: qs("#district").value,
    stream: qs("#stream").value,
    leavingYear: qs("#leaving-year").value,
    incomeBand: qs("#income-band").value,
    needSignals: getSelectedNeedSignals().map((signal) => fundingNeedSignals[signal]?.label || signal),
    preferenceText: qs("#preference-text")?.value || "",
    interests: Array.from(interestState),
    grades: subjects
      .map((subject) => ({
        code: subject.code,
        subject: subject.name,
        grade: gradeState[subject.code] || null
      }))
      .filter((item) => item.grade)
  };
}

function getAiMatchPayload() {
  return latestMatches.filter((programme) => programme.match.tier !== "blocked").slice(0, 8).map((programme) => ({
    id: programme.id,
    title: programme.title,
    institution: programme.institution,
    faculty: programme.faculty,
    level: programme.level,
    duration: programme.duration,
    requirements: programme.requirements.slice(0, 5),
    careers: programme.careers.slice(0, 4),
    skills: programme.skills.slice(0, 4),
    hard_gate_passed: programme.match.hardGatePassed,
    match: programme.match
  }));
}

function getAiChatStorageKey() {
  return `${aiChatStoragePrefix}:${currentUser?.id || "guest"}`;
}

function getInitialAiChatMessage() {
  return {
    id: "ai-welcome",
    role: "assistant",
    content: "Hi, I am EduGuide AI. Enter your grades first, run matches, then ask me what you qualify for, what is blocked, and what subjects to improve.",
    html: "<strong>Hi, I am EduGuide AI.</strong><p>Enter your grades first, run matches, then ask me what you qualify for, what is blocked, and what subjects to improve.</p>"
  };
}

function normalizeAiChatMessage(message = {}) {
  const role = message.role === "assistant" ? "assistant" : "user";
  const content = String(message.content || "").trim();
  if (!content) return null;
  return {
    id: message.id || `ai-msg-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    role,
    content: content.slice(0, 2400),
    html: typeof message.html === "string" ? message.html : "",
    at: message.at || new Date().toISOString()
  };
}

function loadAiChatMessages() {
  try {
    const stored = JSON.parse(localStorage.getItem(getAiChatStorageKey()) || "[]");
    aiChatMessages = Array.isArray(stored) ? stored.map(normalizeAiChatMessage).filter(Boolean).slice(-maxAiChatMessages) : [];
  } catch (error) {
    aiChatMessages = [];
  }
  if (!aiChatMessages.length) aiChatMessages = [getInitialAiChatMessage()];
}

function saveAiChatMessages() {
  if (!currentUser) return;
  localStorage.setItem(getAiChatStorageKey(), JSON.stringify(aiChatMessages.slice(-maxAiChatMessages)));
}

function aiMessageMarkup(message) {
  const isUser = message.role === "user";
  const avatar = isUser ? "You" : "AI";
  const body = message.html || `<p>${escapeHtml(message.content)}</p>`;
  return `
    <div class="ai-message ${isUser ? "user" : "assistant"}">
      <div class="ai-message-avatar">${avatar}</div>
      <div class="ai-message-body">${body}</div>
    </div>
  `;
}

function renderAiChatMessages(typingText = "") {
  const output = qs("#ai-guidance-output");
  if (!output) return;
  const messages = aiChatMessages.length ? aiChatMessages : [getInitialAiChatMessage()];
  output.innerHTML = `
    ${messages.map(aiMessageMarkup).join("")}
    ${typingText
      ? `<div class="ai-message assistant is-thinking">
          <div class="ai-message-avatar">AI</div>
          <div class="ai-message-body"><p>${escapeHtml(typingText)}</p></div>
        </div>`
      : ""}
  `;
  output.scrollTop = output.scrollHeight;
  if (window.lucide) window.lucide.createIcons();
}

function appendAiChatMessage(role, content, html = "") {
  const message = normalizeAiChatMessage({ role, content, html });
  if (!message) return;
  aiChatMessages = [...aiChatMessages.filter((item) => item.id !== "ai-welcome"), message].slice(-maxAiChatMessages);
  saveAiChatMessages();
  renderAiChatMessages();
}

function resetAiChatMessages() {
  aiChatMessages = [getInitialAiChatMessage()];
  saveAiChatMessages();
  renderAiChatMessages();
  qs("#ai-question").value = "";
  qs("#ai-guidance-status").textContent = "New chat started. Your grades and latest matches are still used as context.";
}

function guidanceToConversationText(guidance = {}) {
  const parts = [guidance.summary, guidance.direct_answer, guidance.scholarship_note].filter(Boolean);
  if (Array.isArray(guidance.top_recommendations) && guidance.top_recommendations.length) {
    parts.push(`Top recommendations: ${guidance.top_recommendations.map((item) => `${item.programme || "Programme"} at ${item.institution || "Institution"}: ${item.why || item.action || "match"}`).join(" | ")}`);
  }
  if (Array.isArray(guidance.study_plan) && guidance.study_plan.length) parts.push(`Study plan: ${guidance.study_plan.join(" | ")}`);
  if (Array.isArray(guidance.next_questions) && guidance.next_questions.length) parts.push(`Next questions: ${guidance.next_questions.join(" | ")}`);
  return parts.join("\n").slice(0, 2400) || "Guidance generated from your current EduGuide profile.";
}

function getAiConversationPayload() {
  return aiChatMessages
    .filter((message) => message.id !== "ai-welcome")
    .slice(-12)
    .map((message) => ({ role: message.role, content: message.content }));
}
function renderAiGuidance(guidance, mode, model) {
  const recommendations = guidance.top_recommendations || [];
  const comparison = guidance.comparison || [];
  const answerMarkup = `
    <article class="ai-answer-card">
      <h4>Summary</h4>
      <p>${escapeHtml(guidance.summary || "Guidance generated from your current matches.")}</p>
    </article>
    ${
      guidance.direct_answer
        ? `<article class="ai-answer-card">
            <h4>Answer</h4>
            <p>${escapeHtml(guidance.direct_answer)}</p>
          </article>`
        : ""
    }
    ${
      recommendations.length
        ? `<article class="ai-answer-card">
            <h4>Top recommendations</h4>
            ${recommendations
              .map(
                (item) => `
                  <div class="ai-rec">
                    <strong>${escapeHtml(item.programme || "Programme")} - ${escapeHtml(item.institution || "Institution")}</strong>
                    <em>${escapeHtml(item.tier || "Match")}</em>
                    <p>${escapeHtml(item.why || "This matches your current profile signals.")}</p>
                    <span>${escapeHtml(item.caution || "Verify final requirements before applying.")}</span>
                    <small>${escapeHtml(item.action || "Compare this option with your other matches.")}</small>
                  </div>
                `
              )
              .join("")}
          </article>`
        : ""
    }
    ${
      comparison.length
        ? `<article class="ai-answer-card">
            <h4>Comparison</h4>
            ${comparison
              .map(
                (item) => `
                  <div class="ai-rec">
                    <strong>${escapeHtml(item.programme || "Programme")} - ${escapeHtml(item.institution || "Institution")}</strong>
                    <em>${escapeHtml(item.tier || "Match")}</em>
                    <p>${escapeHtml(item.strength || "Strong profile alignment.")}</p>
                    <span>${escapeHtml(item.concern || "Confirm final requirements before applying.")}</span>
                  </div>
                `
              )
              .join("")}
          </article>`
        : ""
    }
    ${
      guidance.study_plan?.length
        ? `<article class="ai-answer-card">
            <h4>Study plan</h4>
            <ul>${guidance.study_plan.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
          </article>`
        : ""
    }
    ${
      guidance.document_checklist?.length
        ? `<article class="ai-answer-card">
            <h4>Documents</h4>
            <ul>${guidance.document_checklist.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
          </article>`
        : ""
    }
    ${
      guidance.scholarship_note
        ? `<article class="ai-answer-card">
            <h4>Funding note</h4>
            <p>${escapeHtml(guidance.scholarship_note)}</p>
          </article>`
        : ""
    }
    ${
      guidance.next_questions?.length
        ? `<article class="ai-answer-card">
            <h4>Next questions</h4>
            <ul>${guidance.next_questions.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
          </article>`
        : ""
    }
  `;
  appendAiChatMessage("assistant", guidanceToConversationText(guidance), answerMarkup);
  const providerLabel = mode === "gemini" ? "Gemini" : mode === "openai" ? "OpenAI" : "AI";
  qs("#ai-guidance-status").textContent =
    mode === "gemini" || mode === "openai"
      ? `Generated with ${providerLabel} (${model}). Conversation context is active.`
      : "Local fallback guidance shown because AI is not configured or unavailable.";
}
async function requestAiGuidance(mode = "guidance") {
  if (!latestMatches.length) calculateMatches();
  const guidanceButton = qs("#ai-guidance-button");
  const compareButton = qs("#ai-compare-button");
  const questionInput = qs("#ai-question");
  const questionText = questionInput?.value.trim() || "";
  if (!questionText && mode !== "compare") {
    qs("#ai-guidance-status").textContent = "Type a question or choose one of the quick prompts.";
    questionInput?.focus();
    return;
  }

  guidanceButton.disabled = true;
  compareButton.disabled = true;
  if (questionText) appendAiChatMessage("user", questionText);
  renderAiChatMessages(mode === "compare" ? "Comparing your strongest current matches..." : "Reading your latest profile and preparing advice...");
  qs("#ai-guidance-status").textContent = mode === "compare" ? "Comparing top matches..." : "Generating guidance...";

  const payload = {
    mode,
    question: questionText,
    conversation: getAiConversationPayload(),
    profile: getAiProfilePayload(),
    readiness: getNmdsReadiness(),
    documents: currentUser?.documents || [],
    matches: getAiMatchPayload()
  };

  try {
    const response = await fetch("/api/ai/guidance", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error(`AI server returned ${response.status}`);
    const data = await response.json();
    renderAiGuidance(data.guidance || {}, data.mode, data.model);
    if (questionInput) questionInput.value = "";
    recordCurrentUserActivity(mode === "compare" ? "ai_compare" : "ai_guidance", mode === "compare" ? "Compared AI recommendations" : "Requested AI guidance", {
      question: payload.question.slice(0, 120)
    });
  } catch (error) {
    const errorMarkup = `
      <article class="ai-answer-card">
        <h4>Check Gemini API key</h4>
        <p>The matching engine still works, but AI guidance and OCR need a valid Gemini key and model on the server.</p>
        <small>${escapeHtml(error.message || "Unable to reach /api/ai/guidance")}</small>
      </article>
    `;
    appendAiChatMessage("assistant", error.message || "AI configuration needs attention.", errorMarkup);
    qs("#ai-guidance-status").textContent = "AI configuration needs attention.";
  } finally {
    guidanceButton.disabled = false;
    compareButton.disabled = false;
  }
}
function renderSources() {
  qs("#source-grid").innerHTML = sources
    .map((source) => `
      <article class="source-card">
        <div>
          <h4>${source.name}</h4>
          <p class="programme-meta">${source.type}</p>
        </div>
        <a href="${source.url}" target="_blank" rel="noreferrer">${source.url}</a>
        <div class="source-tags">
          ${source.tags.map((tag) => `<span class="badge green">${tag}</span>`).join("")}
        </div>
      </article>
    `)
    .join("");
}

function getUnreviewedUsers() {
  return getVisibleUsers().filter((user) => !isAdmin(user) && !user.reviewedAt);
}

function getFilteredAdminUsers() {
  const query = adminState.search.trim().toLowerCase();
  return getVisibleUsers().filter((user) =>
    [user.id, user.name, user.email, user.role, user.status, user.district, user.lastActivity].some((value) => String(value || "").toLowerCase().includes(query))
  );
}

function getAdminSummary() {
  const visibleUsers = getVisibleUsers();
  return {
    programmeCount: adminProgrammes.length,
    reviewCount: adminProgrammes.filter((programme) => programme.reviewStatus === "needs_admin_review" || programme.reviewStatus === "flagged").length,
    openGapCount: adminGaps.filter((gap) => gap.status === "open").length,
    feeItemCount: adminFees.reduce((total, schedule) => total + schedule.items.length, 0),
    sourceCount: adminSources.length,
    userCount: visibleUsers.length,
    newUserCount: getUnreviewedUsers().length
  };
}

function renderAdminFilters() {
  const filter = qs("#admin-institution-filter");
  if (!filter) return;
  const current = adminState.institution || "all";
  const institutions = Array.from(
    new Set([
      ...(adminData.institutions || []).map((item) => item.name),
      ...adminProgrammes.map((programme) => programme.institution)
    ].filter(Boolean))
  ).sort();
  filter.innerHTML = [
    `<option value="all">All institutions</option>`,
    ...institutions.map((institution) => `<option value="${escapeHtml(institution)}">${escapeHtml(institution)}</option>`)
  ].join("");
  filter.value = institutions.includes(current) ? current : "all";
  adminState.institution = filter.value;
}

function renderAdminMetrics() {
  const summary = getAdminSummary();
  qs("#admin-record-count").textContent = summary.programmeCount;
  qs("#admin-review-count").textContent = summary.reviewCount;
  qs("#admin-gap-count").textContent = summary.openGapCount;
  qs("#admin-fee-count").textContent = summary.feeItemCount;
  qs("#admin-user-count").textContent = summary.userCount;
  qs("#admin-new-user-count").textContent = summary.newUserCount;
  const persistenceLabel = persistenceMode === "server-supabase" || persistenceMode === "supabase" ? "Supabase" : persistenceMode === "server-db" ? "Database" : "Local";
  qs("#admin-health").textContent = `${persistenceLabel} - ${lastPersistenceMessage}`;
  const notice = qs("#admin-user-notice");
  if (notice) {
    notice.hidden = !summary.newUserCount;
    notice.innerHTML = summary.newUserCount
      ? `
        <div>
          <strong>${summary.newUserCount} new student account${summary.newUserCount === 1 ? "" : "s"} need${summary.newUserCount === 1 ? "s" : ""} review.</strong>
          <span>Open Users to inspect profiles, documents, and recent activity.</span>
        </div>
        <button class="secondary-action compact-action" type="button" data-admin-tab-shortcut="users">
          <i data-lucide="users-round"></i>
          View users
        </button>
      `
      : "";
  }
}

function adminSearchMatches(values) {
  const query = adminState.search.trim().toLowerCase();
  if (!query) return true;
  return values.some((value) => String(value || "").toLowerCase().includes(query));
}

function getFilteredAdminProgrammes() {
  return adminProgrammes.filter((programme) => {
    const institutionMatch = adminState.institution === "all" || programme.institution === adminState.institution;
    const statusMatch = adminState.status === "all" || programme.reviewStatus === adminState.status;
    const searchMatch = adminSearchMatches([
      programme.name,
      programme.institution,
      programme.faculty,
      programme.category,
      programme.level,
      programme.requirementsSummary,
      programme.sourceUrl,
      programme.sourceNote,
      programme.feeNote,
      (programme.careers || []).join(" ")
    ]);
    return institutionMatch && statusMatch && searchMatch;
  });
}

function getFilteredAdminGaps() {
  return adminGaps.filter((gap) => {
    const institutionMatch = adminState.institution === "all" || gap.institution === adminState.institution;
    const searchMatch = adminSearchMatches([gap.title, gap.description, gap.institution, gap.programmeName, gap.type]);
    return institutionMatch && searchMatch;
  });
}

function getFilteredAdminFees() {
  return adminFees
    .filter((schedule) => adminState.institution === "all" || schedule.institution === adminState.institution)
    .map((schedule) => ({
      ...schedule,
      items: schedule.items.filter((item) =>
        adminSearchMatches([schedule.institution, schedule.title, item.name, item.programmeGroup, item.studentCategory, item.type])
      )
    }))
    .filter((schedule) => schedule.items.length || adminSearchMatches([schedule.institution, schedule.title]));
}

function getDerivedAdminSources() {
  return adminProgrammes
    .filter((programme) => isCustomAdminProgramme(programme) || programme.sourceNote || programme.feeNote || programme.supportingSourcePath || programme.supportingFeeSourcePath)
    .map((programme) => ({
      institution: programme.institution,
      source_url: programme.sourceUrl || "",
      source_path: programme.supportingSourcePath || programme.supportingFeeSourcePath || "",
      status: programme.reviewStatus || "needs_admin_review",
      records_extracted: 1,
      data_found: [
        "programme record",
        programme.requirementsSummary ? "requirements" : null,
        programme.duration ? "duration" : null,
        programme.feeNote || programme.supportingFeeSourcePath ? "fee note/evidence" : null
      ].filter(Boolean),
      shortage: [
        programme.requirementsSummary ? null : "requirements missing",
        programme.duration ? null : "duration missing",
        programme.feeNote || programme.supportingFeeSourcePath ? null : "fee evidence missing",
        programme.sourceUrl || programme.supportingSourcePath ? null : "official source missing"
      ].filter(Boolean),
      programmeName: programme.name
    }));
}

function getAllAdminSources() {
  return [...adminSources, ...getDerivedAdminSources()];
}

function getFilteredAdminSources() {
  return getAllAdminSources().filter((source) => {
    const institutionMatch = adminState.institution === "all" || source.institution === adminState.institution;
    const searchMatch = adminSearchMatches([
      source.institution,
      source.programmeName,
      source.source_url,
      source.source_path,
      source.status,
      (source.data_found || []).join(" "),
      (source.shortage || []).join(" ")
    ]);
    return institutionMatch && searchMatch;
  });
}

function badgeClassForStatus(status) {
  if (status === "approved" || status === "resolved" || status === "scraped" || status === "manual_extract") return "green";
  if (status === "rejected" || status === "blocked_or_locked" || status === "blocked_or_unstable") return "red";
  if (status === "flagged" || status === "manual_review_needed" || status === "needs_admin_review" || status === "in_progress") return "amber";
  return "blue";
}

function renderAdminCatalogue() {
  const records = getFilteredAdminProgrammes();
  qs("#catalogue-result-count").textContent = `${records.length} records`;
  qs("#admin-programme-list").innerHTML = records.length
    ? records
        .map((programme) => {
          const openGaps = adminGaps.filter((gap) => gap.programmeId === programme.id && gap.status === "open").length;
          return `
            <article class="admin-row ${programme.id === adminState.selectedProgrammeId ? "selected" : ""}" data-programme-id="${escapeHtml(programme.id)}">
              <div class="admin-row-main">
                <div class="admin-row-title">
                  <h4>${escapeHtml(programme.name)}</h4>
                  <span>${escapeHtml(programme.institution)}</span>
                </div>
                <div class="admin-row-meta">
                  <span>${escapeHtml(programme.level || "Level missing")}</span>
                  <span>${escapeHtml(programme.category || "Category missing")}</span>
                  <span>${escapeHtml(programme.duration || "Duration missing")}</span>
                  <span>${escapeHtml(formatStatus(programme.sourceType || "source"))}</span>
                  <span>${openGaps} open gaps</span>
                </div>
              </div>
              <div class="admin-row-actions">
                <span class="badge ${badgeClassForStatus(programme.reviewStatus)}">${formatStatus(programme.reviewStatus)}</span>
                <button type="button" title="Approve" data-admin-action="approve" data-programme-id="${escapeHtml(programme.id)}">
                  <i data-lucide="check"></i>
                </button>
                <button type="button" title="Flag" data-admin-action="flag" data-programme-id="${escapeHtml(programme.id)}">
                  <i data-lucide="flag"></i>
                </button>
                <button class="reject" type="button" title="Reject" data-admin-action="reject" data-programme-id="${escapeHtml(programme.id)}">
                  <i data-lucide="x"></i>
                </button>
              </div>
            </article>
          `;
        })
        .join("")
    : `<article class="admin-empty"><h4>No records match the current filters.</h4><p>Try clearing search or switching institution/status.</p></article>`;

  if (!records.some((record) => record.id === adminState.selectedProgrammeId)) {
    adminState.selectedProgrammeId = records[0]?.id || adminProgrammes[0]?.id || null;
    adminState.editingProgrammeId = null;
  }
}

function renderAdminGaps() {
  const gaps = getFilteredAdminGaps();
  qs("#gap-result-count").textContent = `${gaps.length} gaps`;
  qs("#admin-gap-list").innerHTML = gaps.length
    ? gaps
        .map((gap) => `
          <article class="admin-row gap-row ${gap.status === "resolved" ? "muted-row" : ""}">
            <div class="admin-row-main">
              <div class="admin-row-title">
                <h4>${escapeHtml(gap.title)}</h4>
                <span>${escapeHtml(gap.institution)}</span>
              </div>
              <p>${escapeHtml(gap.programmeName || gap.description)}</p>
              <div class="admin-row-meta">
                <span>${formatStatus(gap.type)}</span>
                <span>${escapeHtml(gap.priority)} priority</span>
                <span>${formatStatus(gap.status)}</span>
              </div>
            </div>
            <div class="admin-row-actions">
              <button type="button" title="Inspect programme" data-gap-select="${escapeHtml(gap.programmeId || "")}" ${gap.programmeId ? "" : "disabled"}>
                <i data-lucide="search"></i>
              </button>
              <button type="button" title="Mark open" data-gap-action="open" data-gap-id="${escapeHtml(gap.id)}" ${gap.status === "open" ? "disabled" : ""}>
                <i data-lucide="rotate-ccw"></i>
              </button>
              <button type="button" title="Mark in progress" data-gap-action="in_progress" data-gap-id="${escapeHtml(gap.id)}" ${gap.status === "in_progress" ? "disabled" : ""}>
                <i data-lucide="clock-3"></i>
              </button>
              <button type="button" title="Resolve gap" data-gap-action="resolved" data-gap-id="${escapeHtml(gap.id)}" ${gap.status === "resolved" ? "disabled" : ""}>
                <i data-lucide="check-check"></i>
              </button>
            </div>
          </article>
        `)
        .join("")
    : `<article class="admin-empty"><h4>No data gaps match the filters.</h4><p>That is rare good news.</p></article>`;
}

function renderAdminFees() {
  const schedules = getFilteredAdminFees();
  const feeItems = schedules.flatMap((schedule) => schedule.items.map((item) => ({ ...item, schedule })));
  qs("#fee-result-count").textContent = `${feeItems.length} fee items`;
  qs("#admin-fee-list").innerHTML = feeItems.length
    ? feeItems
        .map((item) => `
          <article class="admin-row fee-row">
            <div class="admin-row-main">
              <div class="admin-row-title">
                <h4>${escapeHtml(item.itemName || item.name)}</h4>
                <span>${escapeHtml(item.schedule.institution)}</span>
              </div>
              <div class="admin-row-meta">
                <span>${escapeHtml(item.schedule.title)}</span>
                <span>${escapeHtml(item.programmeGroup || "General")}</span>
                <span>${escapeHtml(item.studentCategory || item.attendanceMode || item.type)}</span>
              </div>
            </div>
            <div class="admin-fee-amount">
              <strong>${item.percentOfTuition ? `${item.percentOfTuition}% of tuition` : formatMoney(item.amount, item.schedule.currency)}</strong>
              <span>${escapeHtml(item.basis || item.refundStatus || item.schedule.academicYear || "review")}</span>
            </div>
          </article>
        `)
        .join("")
    : `<article class="admin-empty"><h4>No fee items match the filters.</h4><p>Try another institution or clear search.</p></article>`;
}

function renderAdminSources() {
  const filteredSources = getFilteredAdminSources();
  qs("#source-audit-count").textContent = `${filteredSources.length} sources`;
  qs("#admin-source-list").innerHTML = filteredSources.length
    ? filteredSources
        .map((source) => {
          const href = source.source_url || "";
          const label = source.source_url || source.source_path || "Local evidence";
          return `
            <article class="admin-row source-audit-row">
              <div class="admin-row-main">
                <div class="admin-row-title">
                  <h4>${escapeHtml(source.institution)}</h4>
                  <span class="badge ${badgeClassForStatus(source.status)}">${formatStatus(source.status)}</span>
                </div>
                ${source.programmeName ? `<p>${escapeHtml(source.programmeName)}</p>` : ""}
                <p>${escapeHtml(label)}</p>
                <div class="admin-source-lists">
                  <div><strong>Found</strong><span>${escapeHtml((source.data_found || []).join(", ") || "No direct data captured")}</span></div>
                  <div><strong>Shortage</strong><span>${escapeHtml((source.shortage || []).join(", ") || "None listed")}</span></div>
                </div>
              </div>
              <div class="admin-fee-amount">
                <strong>${source.records_extracted ?? 0}</strong>
                <span>records</span>
                ${href ? `<a href="${escapeHtml(href)}" target="_blank" rel="noreferrer">Open</a>` : ""}
              </div>
            </article>
          `;
        })
        .join("")
    : `<article class="admin-empty"><h4>No sources match the filters.</h4><p>Try another institution.</p></article>`;
}

async function loadAdminUsers() {
  if (!authToken || !isAdmin()) return;
  try {
    const response = await fetch("/api/admin/users", { headers: getAuthHeaders({ Accept: "application/json" }) });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok || !Array.isArray(data.users)) throw new Error(data.detail || "Unable to load users");
    authUsers = data.users.map(normalizeUser).filter(Boolean);
    localStorage.setItem(authUsersKey, JSON.stringify(authUsers));
    renderAdminUsers();
    renderAdminMetrics();
    renderAdminDetail();
    if (window.lucide) window.lucide.createIcons();
  } catch (error) {
    lastPersistenceMessage = error.message || "Could not load users";
  }
}

function applyAdminUsersResponse(data) {
  if (!Array.isArray(data?.users)) return;
  authUsers = data.users.map(normalizeUser).filter(Boolean);
  localStorage.setItem(authUsersKey, JSON.stringify(authUsers));
}
function renderAdminUsers() {
  const list = qs("#admin-user-list");
  if (!list) return;
  const users = getFilteredAdminUsers();
  if (users.length && !users.some((user) => user.id === adminState.selectedUserId)) {
    adminState.selectedUserId = users[0].id;
  }
  if (!users.length) adminState.selectedUserId = null;
  qs("#user-result-count").textContent = `${users.length} users`;
  list.innerHTML = users.length
    ? users
        .map((user) => {
          const self = currentUser?.id === user.id;
          const protectedOwner = isOwner(user);
          const canChangeRole = isAdmin() && !self && !protectedOwner;
          const canChangeStatus = isAdmin() && !self && !protectedOwner;
          const needsReview = !isAdmin(user) && !user.reviewedAt;
          return `
            <article class="admin-row user-row ${user.id === adminState.selectedUserId ? "selected" : ""}" data-user-id="${escapeHtml(user.id)}">
              <div class="admin-row-main">
                <div class="admin-row-title">
                  <h4>${escapeHtml(user.name)}</h4>
                  <span>${escapeHtml(user.email)}</span>
                </div>
                <p>${escapeHtml(user.id)}</p>
                <div class="admin-row-meta">
                  <span>${escapeHtml(user.district || "District missing")}</span>
                  <span>${escapeHtml(user.status || "active")}</span>
                  <span>Last: ${escapeHtml(user.lastActivity || "No activity yet")}</span>
                  <span>${user.documents?.length || 0} documents</span>
                  <span>${user.shortlist?.length || 0} saved programmes</span>
                </div>
              </div>
              <div class="admin-row-actions">
                ${needsReview ? `<span class="badge amber">New</span>` : ""}
                <span class="badge ${isAdmin(user) ? "green" : "blue"}">${escapeHtml(getUserRoleLabel(user))}</span>
                <span class="badge ${user.status === "suspended" ? "red" : "green"}">${escapeHtml(formatStatus(user.status || "active"))}</span>
                ${
                  needsReview
                    ? `<button type="button" title="Mark user reviewed" data-user-review="${escapeHtml(user.id)}">
                        <i data-lucide="badge-check"></i>
                      </button>`
                    : ""
                }
                ${
                  isAdmin(user)
                    ? `<button type="button" title="Remove admin role" data-user-role="${escapeHtml(user.id)}" data-role="student" ${canChangeRole ? "" : "disabled"}>
                        <i data-lucide="shield-minus"></i>
                      </button>`
                    : `<button type="button" title="Grant admin role" data-user-role="${escapeHtml(user.id)}" data-role="admin" ${canChangeRole ? "" : "disabled"}>
                        <i data-lucide="shield-plus"></i>
                      </button>`
                }
                ${
                  user.status === "suspended"
                    ? `<button type="button" title="Reactivate account" data-user-status="${escapeHtml(user.id)}" data-status="active" ${canChangeStatus ? "" : "disabled"}>
                        <i data-lucide="user-check"></i>
                      </button>`
                    : `<button class="reject" type="button" title="Suspend account" data-user-status="${escapeHtml(user.id)}" data-status="suspended" ${canChangeStatus ? "" : "disabled"}>
                        <i data-lucide="user-x"></i>
                      </button>`
                }
              </div>
            </article>
          `;
        })
        .join("")
    : `<article class="admin-empty"><h4>No users match the filters.</h4><p>Try clearing search.</p></article>`;
}

function renderAdminUserDetail(panel) {
  const users = getFilteredAdminUsers();
  if (users.length && !users.some((user) => user.id === adminState.selectedUserId)) {
    adminState.selectedUserId = users[0].id;
  }
  const user = users.find((item) => item.id === adminState.selectedUserId);
  if (!user) {
    panel.innerHTML = `<article class="admin-empty"><h4>No user selected.</h4><p>Registered accounts will appear here after signup.</p></article>`;
    return;
  }
  const grades = Object.entries(user.grades || {});
  const activities = user.activity || [];
  const needsReview = !isAdmin(user) && !user.reviewedAt;
  panel.innerHTML = `
    <div class="detail-card user-detail-card">
      <div class="detail-card-head">
        <p class="section-kicker">User account</p>
        <span class="badge ${isAdmin(user) ? "green" : "blue"}">${escapeHtml(getUserRoleLabel(user))}</span>
      </div>
      <h3>${escapeHtml(user.name)}</h3>
      <p class="detail-muted">${escapeHtml(user.email)}</p>
      <div class="detail-meta-grid">
        <div><span>User ID</span><strong>${escapeHtml(user.id)}</strong></div>
        <div><span>Status</span><strong>${escapeHtml(formatStatus(user.status || "active"))}</strong></div>
        <div><span>District</span><strong>${escapeHtml(user.district || "Missing")}</strong></div>
        <div><span>Created</span><strong>${escapeHtml(formatDateTime(user.createdAt))}</strong></div>
        <div><span>Last active</span><strong>${escapeHtml(formatDateTime(user.lastActiveAt))}</strong></div>
        <div><span>Review</span><strong>${needsReview ? "Needs review" : "Reviewed"}</strong></div>
      </div>
      <div class="detail-section">
        <h4>Profile snapshot</h4>
        <p>${escapeHtml(user.stream || "Stream not set")} - ${escapeHtml(user.leavingYear || "Leaving year missing")} - ${escapeHtml(user.incomeBand || "Income band missing")}</p>
        ${user.preferenceText ? `<p>${escapeHtml(user.preferenceText)}</p>` : `<p><span class="muted-inline">No preference text captured yet.</span></p>`}
      </div>
      <div class="detail-section">
        <h4>Grades</h4>
        ${
          grades.length
            ? `<div class="user-grade-list">${grades.map(([code, grade]) => `<span>${escapeHtml(getSubjectLabel(code))}: <strong>${escapeHtml(grade)}</strong></span>`).join("")}</div>`
            : `<p><span class="muted-inline">No grades entered yet.</span></p>`
        }
      </div>
      <div class="detail-section">
        <h4>Documents and saved programmes</h4>
        <p>${user.documents?.length || 0} document(s), ${user.shortlist?.length || 0} saved programme(s).</p>
      </div>
      <div class="detail-section">
        <h4>Recent activity</h4>
        ${
          activities.length
            ? `<ul class="activity-list">${activities
                .slice(0, 10)
                .map((item) => `<li><strong>${escapeHtml(item.label)}</strong><span>${escapeHtml(formatDateTime(item.at))} by ${escapeHtml(item.actorName || "System")}</span></li>`)
                .join("")}</ul>`
            : `<p><span class="muted-inline">No activity captured yet.</span></p>`
        }
      </div>
      <div class="detail-actions">
        ${
          needsReview
            ? `<button class="primary-button small" type="button" data-user-review="${escapeHtml(user.id)}">
                <i data-lucide="badge-check"></i>
                Mark Reviewed
              </button>`
            : ""
        }
        ${
          !isAdmin(user)
            ? `<button class="secondary-action" type="button" data-user-role="${escapeHtml(user.id)}" data-role="admin">
                <i data-lucide="shield-plus"></i>
                Grant Admin
              </button>`
            : ""
        }
        ${
          user.status === "suspended"
            ? `<button class="secondary-action" type="button" data-user-status="${escapeHtml(user.id)}" data-status="active">
                <i data-lucide="user-check"></i>
                Reactivate
              </button>`
            : `<button class="secondary-action danger" type="button" data-user-status="${escapeHtml(user.id)}" data-status="suspended" ${user.id === currentUser?.id || isOwner(user) ? "disabled" : ""}>
                <i data-lucide="user-x"></i>
                Suspend
              </button>`
        }
      </div>
    </div>
  `;
}

function renderAdminDetail() {
  const panel = qs("#admin-detail-panel");
  if (!panel) return;
  if (adminState.tab === "users") {
    renderAdminUserDetail(panel);
    return;
  }
  const programme = adminProgrammes.find((item) => item.id === adminState.selectedProgrammeId) || adminProgrammes[0];
  if (!panel || !programme) {
    if (panel) panel.innerHTML = `<article class="admin-empty"><h4>No programme selected.</h4></article>`;
    return;
  }
  const gaps = adminGaps.filter((gap) => gap.programmeId === programme.id && gap.status !== "resolved");
  const feeSchedules = adminFees.filter((schedule) => schedule.institution === programme.institution);
  const sourceLabel = programme.sourceUrl || programme.sourcePath || programme.supportingSourcePath || "Source not linked";
  const evidenceItems = [
    programme.sourceUrl,
    programme.supportingSourcePath,
    programme.supportingFeeSourcePath,
    programme.sourceNote,
    programme.feeNote
  ].filter(Boolean);
  const careerItems = programme.careers?.length ? programme.careers : [];
  const isEditing = adminState.editingProgrammeId === programme.id;

  if (isEditing) {
    panel.innerHTML = `
      <div class="detail-card">
        <div class="detail-card-head">
          <p class="section-kicker">Edit record</p>
          <span class="badge ${badgeClassForStatus(programme.reviewStatus)}">${formatStatus(programme.reviewStatus)}</span>
        </div>
        <h3>${escapeHtml(programme.name)}</h3>
        <form class="edit-form" id="admin-edit-form" data-programme-id="${escapeHtml(programme.id)}">
          <div class="edit-grid">
            <label>
              <span>Programme name</span>
              <input name="name" value="${escapeHtml(programme.name)}" required>
            </label>
            <label>
              <span>Code</span>
              <input name="code" value="${escapeHtml(programme.code || "")}">
            </label>
            <label>
              <span>Institution</span>
              <input name="institution" value="${escapeHtml(programme.institution)}" required>
            </label>
            <label>
              <span>Faculty</span>
              <input name="faculty" value="${escapeHtml(programme.faculty || "")}">
            </label>
            <label>
              <span>Category</span>
              <input name="category" value="${escapeHtml(programme.category || "")}">
            </label>
            <label>
              <span>Level</span>
              <input name="level" value="${escapeHtml(programme.level || "")}">
            </label>
            <label>
              <span>Duration</span>
              <input name="duration" value="${escapeHtml(programme.duration || "")}" placeholder="Example: 4 years">
            </label>
            <label>
              <span>Delivery mode</span>
              <input name="deliveryMode" value="${escapeHtml(programme.deliveryMode || "")}" placeholder="Full-time">
            </label>
            <label>
              <span>Official source URL</span>
              <input name="sourceUrl" value="${escapeHtml(programme.sourceUrl || "")}" placeholder="https://...">
            </label>
            <label>
              <span>Evidence file/path</span>
              <input name="supportingSourcePath" value="${escapeHtml(programme.supportingSourcePath || "")}" placeholder="data/... or local PDF name">
            </label>
            <label class="full">
              <span>Careers</span>
              <textarea name="careers" placeholder="One career per line">${escapeHtml(formatListText(programme.careers || []))}</textarea>
            </label>
            <label class="full">
              <span>Requirements</span>
              <textarea name="requirementsSummary" placeholder="Entry requirements">${escapeHtml(programme.requirementsSummary || "")}</textarea>
            </label>
            <label class="full">
              <span>Overview</span>
              <textarea name="overview" placeholder="Programme description">${escapeHtml(programme.overview || "")}</textarea>
            </label>
            <label class="full">
              <span>Source note</span>
              <textarea name="sourceNote" placeholder="What source confirmed this record?">${escapeHtml(programme.sourceNote || "")}</textarea>
            </label>
            <label class="full">
              <span>Fee source or note</span>
              <textarea name="feeNote" placeholder="Fee amounts, missing-fee note, or where to verify fees">${escapeHtml(programme.feeNote || "")}</textarea>
              <input name="supportingFeeSourcePath" value="${escapeHtml(programme.supportingFeeSourcePath || "")}" placeholder="Optional fee evidence URL/file path">
            </label>
          </div>
          <div class="detail-actions">
            <button class="primary-button small" type="submit">
              <i data-lucide="save"></i>
              Save
            </button>
            <button class="secondary-action" type="button" data-admin-cancel-edit>
              Cancel
            </button>
          </div>
        </form>
        <div class="detail-section">
          <h4>Open gaps</h4>
          ${
            gaps.length
              ? gaps.map((gap) => `<p class="gap-pill">${escapeHtml(gap.title)}: ${escapeHtml(gap.description)}</p>`).join("")
              : `<p class="gap-pill resolved">No open programme gaps.</p>`
          }
        </div>
      </div>
    `;
    return;
  }

  panel.innerHTML = `
    <div class="detail-card">
      <div class="detail-card-head">
        <p class="section-kicker">Selected record</p>
        <span class="badge ${badgeClassForStatus(programme.reviewStatus)}">${formatStatus(programme.reviewStatus)}</span>
      </div>
      <h3>${escapeHtml(programme.name)}</h3>
      <div class="detail-meta-grid">
        <div><span>Institution</span><strong>${escapeHtml(programme.institution)}</strong></div>
        <div><span>Code</span><strong>${escapeHtml(programme.code || "Missing")}</strong></div>
        <div><span>Level</span><strong>${escapeHtml(programme.level || "Missing")}</strong></div>
        <div><span>Faculty</span><strong>${escapeHtml(programme.faculty || "Missing")}</strong></div>
        <div><span>Category</span><strong>${escapeHtml(programme.category || "Missing")}</strong></div>
        <div><span>Duration</span><strong>${escapeHtml(programme.duration || "Missing")}</strong></div>
      </div>
      <div class="detail-section">
        <h4>Requirements</h4>
        <p>${shortText(programme.requirementsSummary, "Entry requirements not captured yet.")}</p>
      </div>
      <div class="detail-section">
        <h4>Overview</h4>
        <p>${shortText(programme.overview, "No programme description captured yet.")}</p>
      </div>
      <div class="detail-section">
        <h4>Careers</h4>
        ${
          careerItems.length
            ? `<ul class="detail-list">${careerItems.map((career) => `<li>${escapeHtml(career)}</li>`).join("")}</ul>`
            : `<p><span class="muted-inline">Career alignment will be inferred until admin adds it.</span></p>`
        }
      </div>
      <div class="detail-section">
        <h4>Evidence</h4>
        <p>${escapeHtml(sourceLabel)}</p>
        ${
          evidenceItems.length
            ? `<ul class="detail-list evidence-list">${evidenceItems.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
            : ""
        }
        <div class="badge-row">
          <span class="badge blue">${escapeHtml(programme.sourceType || "source")}</span>
          <span class="badge">${escapeHtml(programme.extractionMethod || "extract")}</span>
        </div>
      </div>
      <div class="detail-section">
        <h4>Open gaps</h4>
        ${
          gaps.length
            ? gaps.map((gap) => `<p class="gap-pill">${escapeHtml(gap.title)}: ${escapeHtml(gap.description)}</p>`).join("")
            : `<p class="gap-pill resolved">No open programme gaps.</p>`
        }
      </div>
      <div class="detail-section">
        <h4>Institution fees</h4>
        ${
          feeSchedules.length
            ? feeSchedules
                .map((schedule) => `<p>${escapeHtml(schedule.title)}: ${schedule.items.length} item(s)</p>`)
                .join("")
            : `<p>No fee schedule linked yet.</p>`
        }
        ${programme.feeNote ? `<p class="gap-pill">${escapeHtml(programme.feeNote)}</p>` : ""}
      </div>
      <div class="detail-actions">
        <button class="secondary-action" type="button" data-admin-edit="${escapeHtml(programme.id)}">
          <i data-lucide="pencil"></i>
          Edit
        </button>
        <button class="primary-button small" type="button" data-admin-action="approve" data-programme-id="${escapeHtml(programme.id)}">
          <i data-lucide="check"></i>
          Approve
        </button>
        <button class="secondary-action" type="button" data-admin-action="flag" data-programme-id="${escapeHtml(programme.id)}">
          <i data-lucide="flag"></i>
          Flag
        </button>
        <button class="secondary-action danger" type="button" data-admin-action="reject" data-programme-id="${escapeHtml(programme.id)}">
          <i data-lucide="x"></i>
          Reject
        </button>
      </div>
    </div>
  `;
}

function setAdminTab(tabName) {
  adminState.tab = tabName;
  if (tabName === "users" && !adminState.selectedUserId) {
    adminState.selectedUserId = getVisibleUsers()[0]?.id || null;
  }
  qsa("[data-admin-tab]").forEach((tab) => tab.classList.toggle("active", tab.dataset.adminTab === tabName));
  qsa(".admin-tab-panel").forEach((panel) => panel.classList.toggle("active", panel.id === `admin-tab-${tabName}`));
  renderAdminDetail();
  if (window.lucide) window.lucide.createIcons();
}

async function setProgrammeReviewStatus(id, status) {
  const programme = adminProgrammes.find((item) => item.id === id);
  if (!programme) return;
  const previousStatus = programme.reviewStatus;
  programme.reviewStatus = status;
  adminState.selectedProgrammeId = id;
  lastPersistenceMessage = supabaseClient ? "Saving..." : "Saved locally";
  renderAdmin();
  try {
    await persistProgrammeStatus(programme, status);
    lastPersistenceMessage = supabaseClient ? "Synced programme review" : "Saved locally";
    recordCurrentUserActivity("admin_programme_reviewed", `Marked programme ${formatStatus(status)}`, { programmeId: programme.id, programmeName: programme.name, status });
  } catch (error) {
    programme.reviewStatus = previousStatus;
    lastPersistenceMessage = `Sync failed: ${error.message || "programme update"}`;
  }
  renderAdmin();
  updateCounts();
  calculateMatches();
}

async function setGapStatus(id, status) {
  const gap = adminGaps.find((item) => item.id === id);
  if (!gap) return;
  const previousStatus = gap.status;
  gap.status = status;
  lastPersistenceMessage = supabaseClient ? "Saving..." : "Saved locally";
  renderAdmin();
  try {
    await persistGapStatus(gap, status);
    lastPersistenceMessage = supabaseClient ? "Synced gap status" : "Saved locally";
    recordCurrentUserActivity("admin_gap_updated", `Marked data gap ${formatStatus(status)}`, { gapId: gap.id, programmeId: gap.programmeId, status });
  } catch (error) {
    gap.status = previousStatus;
    lastPersistenceMessage = `Sync failed: ${error.message || "gap update"}`;
  }
  renderAdmin();
  updateCounts();
}

function resolveGap(id) {
  return setGapStatus(id, "resolved");
}

async function setUserRole(userId, role) {
  if (!isAdmin() || !authToken) return;
  try {
    const response = await fetch(`/api/admin/users/${encodeURIComponent(userId)}/role`, {
      method: "PUT",
      headers: getAuthHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ role })
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) throw new Error(data.detail || "Could not update role");
    applyAdminUsersResponse(data);
    renderAdmin();
  } catch (error) {
    lastPersistenceMessage = error.message || "Could not update role";
    renderAdmin();
  }
}

async function setUserStatus(userId, status) {
  if (!isAdmin() || !authToken) return;
  try {
    const response = await fetch(`/api/admin/users/${encodeURIComponent(userId)}/status`, {
      method: "PUT",
      headers: getAuthHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ status })
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) throw new Error(data.detail || "Could not update account status");
    applyAdminUsersResponse(data);
    renderAdmin();
  } catch (error) {
    lastPersistenceMessage = error.message || "Could not update account status";
    renderAdmin();
  }
}

async function markUserReviewed(userId) {
  if (!isAdmin() || !authToken) return;
  try {
    const response = await fetch(`/api/admin/users/${encodeURIComponent(userId)}/review`, {
      method: "PUT",
      headers: getAuthHeaders({ Accept: "application/json" })
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) throw new Error(data.detail || "Could not review user");
    applyAdminUsersResponse(data);
    renderAdmin();
  } catch (error) {
    lastPersistenceMessage = error.message || "Could not review user";
    renderAdmin();
  }
}
function renderAdmin() {
  renderAdminFilters();
  renderAdminMetrics();
  renderAdminCatalogue();
  renderAdminGaps();
  renderAdminFees();
  renderAdminSources();
  renderAdminUsers();
  renderAdminDetail();
  setAdminTab(adminState.tab);
  if (window.lucide) window.lucide.createIcons();
}

function updateCounts() {
  const institutions = new Set(adminProgrammes.map((programme) => programme.institution));
  qs("#institution-count").textContent = institutions.size;
  qs("#programme-count").textContent = adminProgrammes.length || programmes.length;
  qs("#approved-count").textContent = adminProgrammes.length || programmes.filter((programme) => programme.status === "approved").length;
  qs("#source-count").textContent = getAllAdminSources().length || sources.length;
  qs("#pending-count").textContent = adminGaps.filter((item) => item.status === "open").length;
}

function applyProfilePreset(key) {
  const preset = calibrationProfiles[key];
  if (!preset) return;
  Object.keys(gradeState).forEach((code) => delete gradeState[code]);
  Object.assign(gradeState, preset.grades);
  interestState.clear();
  preset.interests.forEach((interest) => interestState.add(interest));
  if (qs("#stream")) qs("#stream").value = preset.stream;
  if (qs("#income-band")) qs("#income-band").value = preset.incomeBand || "mid";
  if (qs("#preference-text")) qs("#preference-text").value = preset.preferenceText || "";
  setNeedSignalInputs(preset.needSignals || []);
  syncCurrentUserProfile();
  renderGrades();
  renderInterests();
  calculateMatches();
  qs("#dropzone-text").textContent = `${preset.label} calibration profile loaded`;
}

function loadSampleProfile() {
  Object.keys(gradeState).forEach((key) => delete gradeState[key]);
  Object.assign(gradeState, { MATH: "A*", ENG: "B", PSCI: "B", BIO: "C", ACC: "B" });
  persistCurrentGrades();
  interestState.clear();
  ["Technology & IT", "Engineering", "Natural Sciences"].forEach((interest) => interestState.add(interest));
  qs("#income-band").value = "mid";
  setNeedSignalInputs([]);
  syncCurrentUserProfile();
  renderGrades();
  renderInterests();
  calculateMatches();
}

function setupDropzone() {
  const dropzone = qs("#dropzone");
  const input = qs("#file-input");
  const text = qs("#dropzone-text");
  ["dragenter", "dragover"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.add("dragging");
    });
  });
  ["dragleave", "drop"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.remove("dragging");
    });
  });
  dropzone.addEventListener("drop", (event) => {
    const files = Array.from(event.dataTransfer.files);
    if (files.length) addDocuments(files);
    else text.textContent = "No files selected";
  });
  input.addEventListener("change", () => {
    const files = Array.from(input.files);
    if (files.length) addDocuments(files);
    else text.textContent = "No files selected";
    input.value = "";
  });
}

function bindEvents() {
  qsa("[data-auth-mode]").forEach((button) => {
    button.addEventListener("click", () => setAuthMode(button.dataset.authMode));
  });
  qs("#login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    await loginWithCredentials(qs("#login-email").value, qs("#login-password").value);
  });
  qs("#register-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    await registerUser(qs("#register-name").value, qs("#register-email").value, qs("#register-password").value, qs("#register-district").value);
  });
  qs("#logout-button")?.addEventListener("click", signOut);
  qsa("[data-view]").forEach((button) => {
    button.addEventListener("click", () => setView(button.dataset.view));
  });
  qsa("[data-view-target]").forEach((button) => {
    button.addEventListener("click", () => setView(button.dataset.viewTarget));
  });
  qs("#grade-grid")?.addEventListener("change", (event) => {
    const select = event.target.closest("[data-subject]");
    if (!select) return;
    const code = select.dataset.subject;
    const next = select.value;
    if (next) gradeState[code] = next;
    else delete gradeState[code];
    persistCurrentGrades();
    renderGrades();
    calculateMatches();
  });
  qs("#interest-grid")?.addEventListener("click", (event) => {
    const chip = event.target.closest("[data-interest]");
    if (!chip) return;
    const interest = chip.dataset.interest;
    if (interestState.has(interest)) interestState.delete(interest);
    else interestState.add(interest);
    renderInterests();
    calculateMatches();
  });
  ["#full-name", "#district", "#leaving-year", "#stream", "#preference-text"].forEach((selector) => {
    qs(selector)?.addEventListener("change", () => {
      syncCurrentUserProfile();
      renderStudentDashboard();
      renderResults();
    });
  });
  qs("#preference-text")?.addEventListener("input", () => {
    syncCurrentUserProfile();
    calculateMatches();
  });
  qs("#analyse-button")?.addEventListener("click", () => {
    calculateMatches();
    setView("results");
  });
  qs("#refresh-button")?.addEventListener("click", calculateMatches);
  qs("#sample-profile")?.addEventListener("click", loadSampleProfile);
  qsa("[data-profile-preset]").forEach((button) => {
    button.addEventListener("click", () => applyProfilePreset(button.dataset.profilePreset));
  });
  qs("#income-band")?.addEventListener("change", () => {
    syncCurrentUserProfile();
    calculateMatches();
  });
  qsa("[data-need-signal]").forEach((input) =>
    input.addEventListener("change", () => {
      syncCurrentUserProfile();
      calculateMatches();
    })
  );
  qs("#ai-guidance-button")?.addEventListener("click", () => requestAiGuidance("guidance"));
  qs("#ai-compare-button")?.addEventListener("click", () => requestAiGuidance("compare"));
  qsa("[data-ai-prompt]").forEach((button) => {
    button.addEventListener("click", () => {
      const input = qs("#ai-question");
      if (!input) return;
      input.value = button.dataset.aiPrompt || "";
      input.focus();
    });
  });
  qs("#ai-clear-button")?.addEventListener("click", resetAiChatMessages);
  qs("#ai-question")?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      requestAiGuidance("guidance");
    }
  });
  qs("#document-list")?.addEventListener("click", (event) => {
    const applyButton = event.target.closest("[data-apply-document-grades]");
    if (applyButton) {
      applyExtractedGrades(applyButton.dataset.applyDocumentGrades);
      return;
    }
    const rerunButton = event.target.closest("[data-rerun-document-ocr]");
    if (rerunButton) {
      rerunDocumentOcr(rerunButton.dataset.rerunDocumentOcr);
      return;
    }
    const deleteButton = event.target.closest("[data-delete-document]");
    if (!deleteButton) return;
    removeDocument(deleteButton.dataset.deleteDocument);
  });
  qsa("[data-results-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      qsa("[data-results-tab]").forEach((tab) => tab.classList.toggle("active", tab === button));
      qsa(".tab-panel").forEach((panel) => panel.classList.toggle("active", panel.id === `tab-${button.dataset.resultsTab}`));
    });
  });
  qs("#view-results")?.addEventListener("click", (event) => {
    const institutionButton = event.target.closest("[data-institution-result]");
    if (institutionButton) {
      selectedResultInstitution = selectedResultInstitution === institutionButton.dataset.institutionResult ? null : institutionButton.dataset.institutionResult;
      renderResults();
      return;
    }

    const shortlistButton = event.target.closest("[data-shortlist-programme]");
    if (!shortlistButton) return;
    toggleShortlist(shortlistButton.dataset.shortlistProgramme);
  });
  qsa("[data-admin-tab]").forEach((button) => {
    button.addEventListener("click", () => setAdminTab(button.dataset.adminTab));
  });
  qs("#view-admin")?.addEventListener("click", (event) => {
    const shortcut = event.target.closest("[data-admin-tab-shortcut]");
    if (!shortcut) return;
    setAdminTab(shortcut.dataset.adminTabShortcut);
  });
  qs("#admin-search")?.addEventListener("input", (event) => {
    adminState.search = event.target.value;
    renderAdmin();
  });
  qs("#admin-institution-filter")?.addEventListener("change", (event) => {
    adminState.institution = event.target.value;
    renderAdmin();
  });
  qs("#admin-status-filter")?.addEventListener("change", (event) => {
    adminState.status = event.target.value;
    renderAdmin();
  });
  qs("#add-programme")?.addEventListener("click", createAdminProgramme);
  qs("#reset-admin-state")?.addEventListener("click", resetLocalReviewState);
  qs("#view-admin")?.addEventListener("submit", (event) => {
    if (!event.target.matches("#admin-edit-form")) return;
    event.preventDefault();
    saveProgrammeEdit(event.target.dataset.programmeId);
  });
  qs("#view-admin")?.addEventListener("click", (event) => {
    const roleButton = event.target.closest("[data-user-role]");
    if (roleButton) {
      setUserRole(roleButton.dataset.userRole, roleButton.dataset.role);
      return;
    }

    const statusButton = event.target.closest("[data-user-status]");
    if (statusButton) {
      setUserStatus(statusButton.dataset.userStatus, statusButton.dataset.status);
      return;
    }

    const reviewButton = event.target.closest("[data-user-review]");
    if (reviewButton) {
      markUserReviewed(reviewButton.dataset.userReview);
      return;
    }

    const userRow = event.target.closest("[data-user-id]");
    if (userRow && userRow.classList.contains("admin-row")) {
      adminState.selectedUserId = userRow.dataset.userId;
      setAdminTab("users");
      renderAdmin();
      return;
    }

    const editButton = event.target.closest("[data-admin-edit]");
    if (editButton) {
      startProgrammeEdit(editButton.dataset.adminEdit);
      return;
    }

    const cancelEditButton = event.target.closest("[data-admin-cancel-edit]");
    if (cancelEditButton) {
      cancelProgrammeEdit();
      return;
    }

    const actionButton = event.target.closest("[data-admin-action]");
    if (actionButton) {
      const id = actionButton.dataset.programmeId;
      if (actionButton.dataset.adminAction === "approve") setProgrammeReviewStatus(id, "approved");
      if (actionButton.dataset.adminAction === "flag") setProgrammeReviewStatus(id, "flagged");
      if (actionButton.dataset.adminAction === "reject") setProgrammeReviewStatus(id, "rejected");
      return;
    }

    const gapAction = event.target.closest("[data-gap-action]");
    if (gapAction) {
      setGapStatus(gapAction.dataset.gapId, gapAction.dataset.gapAction);
      return;
    }

    const gapSelect = event.target.closest("[data-gap-select]");
    if (gapSelect && gapSelect.dataset.gapSelect) {
      adminState.selectedProgrammeId = gapSelect.dataset.gapSelect;
      adminState.editingProgrammeId = null;
      setAdminTab("catalogue");
      renderAdmin();
      return;
    }

    const row = event.target.closest("[data-programme-id]");
    if (row && row.classList.contains("admin-row")) {
      adminState.selectedProgrammeId = row.dataset.programmeId;
      adminState.editingProgrammeId = null;
      renderAdmin();
    }
  });
}

async function init() {
  await loadServerDatabaseState();
  loadAuthUsers();
  loadLocalReviewState();
  seedServerDatabaseState();
  renderGrades();
  renderInterests();
  renderAdmin();
  renderSources();
  loadAiChatMessages();
  renderAiChatMessages();
  updateCounts();
  calculateMatches();
  setupDropzone();
  bindEvents();
  bindInstallPrompt();
  const initialView = new URLSearchParams(window.location.search).get("view");
  const restored = await restoreAuthSession();
  if (restored && initialView && titles[initialView]) setView(initialView);
  if (window.lucide) window.lucide.createIcons();
}

function registerServiceWorker() {
  if (!("serviceWorker" in navigator) || window.location.protocol === "file:") return;
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}

document.addEventListener("DOMContentLoaded", () => {
  init();
  registerServiceWorker();
});
