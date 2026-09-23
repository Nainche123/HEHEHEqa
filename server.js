const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const ROOT = __dirname;
const PUBLIC = path.join(ROOT, 'public');
const DB_FILE = process.env.NEXIVO_DB_FILE || path.join(ROOT, 'data', 'db.json');

function loadDotEnv() {
  const file = path.join(ROOT, '.env');
  if (!fs.existsSync(file)) return;
  for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const t = line.trim();
    if (!t || t.startsWith('#')) continue;
    const i = t.indexOf('=');
    if (i <= 0) continue;
    const k = t.slice(0, i).trim();
    const v = t.slice(i + 1).trim().replace(/^["']|["']$/g, '');
    if (process.env[k] === undefined) process.env[k] = v;
  }
}
loadDotEnv();

const PORT = Number(process.env.PORT || 3000);
const OPERATOR_USER = process.env.NEXIVO_OPERATOR_USER || '0nTop';
const OPERATOR_PASSWORD = process.env.NEXIVO_OPERATOR_PASSWORD || '';
const BOT_BRIDGE_SECRET = process.env.NEXIVO_BOT_BRIDGE_SECRET || '';
const BOT_WORKER_SECRET = process.env.NEXIVO_BOT_WORKER_SECRET || '';
const LICENSE_ISSUE_SECRET = process.env.NEXIVO_LICENSE_ISSUE_SECRET || '';
const BOT_CLIENT_ID = String(process.env.NEXIVO_BOT_CLIENT_ID || '').trim();
const BOT_INVITE_URL = String(process.env.NEXIVO_BOT_INVITE_URL || '').trim();
const BOT_DISPLAY_NAME = String(process.env.NEXIVO_BOT_DISPLAY_NAME || 'NEXIVO HUB Bot').trim();
const COOKIE_SECURE = String(process.env.COOKIE_SECURE || 'false') === 'true';
const SESSION_DAYS = Math.max(1, Number(process.env.NEXIVO_SESSION_DAYS || 30));
const OWNER_USER_ID = 'owner';

const PLAN_META = {
  BASIC: { label: 'Basic', prefix: 'VEX-BSC', level: 1, botFamily: 'BASIC', features: ['products', 'orders', 'license', 'settings'] },
  BASIC_PREMIUM: { label: 'Basic Premium', prefix: 'VEX-BSP', level: 2, botFamily: 'BASIC', features: ['products', 'orders', 'license', 'settings', 'notice'] },
  PRO: { label: 'Pro', prefix: 'VEX-PRO', level: 3, botFamily: 'PRO', features: ['products', 'orders', 'license', 'settings', 'notice', 'grades', 'reports'] },
  PRO_PREMIUM: { label: 'Pro Premium', prefix: 'VEX-PRP', level: 4, botFamily: 'PRO', features: ['products', 'orders', 'license', 'settings', 'notice', 'grades', 'reports', 'customers', 'audit'] }
};

const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.svg': 'image/svg+xml', '.ico': 'image/x-icon'
};

function baseDb() {
  return { users: [], licenses: [], sessions: [], products: [], orders: [], settings: {}, audit: [], events: [], bots: [], botCredentials: [], botConfig: {}, meta: { nextEventId: 1 } };
}
function loadDb() {
  try { return { ...baseDb(), ...JSON.parse(fs.readFileSync(DB_FILE, 'utf8')) }; } catch { return baseDb(); }
}
let db = loadDb();
if (!Array.isArray(db.users)) db.users = [];
if (!Array.isArray(db.licenses)) db.licenses = [];
if (!Array.isArray(db.sessions)) db.sessions = [];
if (!Array.isArray(db.products)) db.products = [];
if (!Array.isArray(db.orders)) db.orders = [];
if (!db.settings || typeof db.settings !== 'object') db.settings = {};
if (!Array.isArray(db.audit)) db.audit = [];
if (!Array.isArray(db.events)) db.events = [];
if (!Array.isArray(db.bots)) db.bots = [];
if (!Array.isArray(db.botCredentials)) db.botCredentials = [];
if (!db.botConfig || typeof db.botConfig !== 'object') db.botConfig = {};
if (db.botCredentials.length) { db.botCredentials = []; saveDb(); }
if (!db.meta || typeof db.meta !== 'object') db.meta = { nextEventId: 1 };
if (!Number.isInteger(db.meta.nextEventId) || db.meta.nextEventId < 1) {
  const maxEventId = db.events.reduce((m, e) => Math.max(m, Number(e?.id) || 0), 0);
  db.meta.nextEventId = maxEventId + 1;
}

function ensureOwnerAccount() {
  if (!OPERATOR_PASSWORD) {
    console.warn('[NEXIVO HUB] NEXIVO_OPERATOR_PASSWORD is not set; owner login is disabled until a secret password is configured.');
    return;
  }
  let changed = false;
  let user = db.users.find(u => u.id === OWNER_USER_ID || u.role === 'OWNER');
  if (!user) {
    user = {
      id: OWNER_USER_ID,
      username: OPERATOR_USER,
      passwordHash: hashPassword(OPERATOR_PASSWORD),
      plan: 'PRO_PREMIUM',
      role: 'OWNER',
      licenseId: null,
      createdAt: now()
    };
    db.users.push(user);
    changed = true;
  } else {
    if (user.id !== OWNER_USER_ID) { user.id = OWNER_USER_ID; changed = true; }
    if (user.username !== OPERATOR_USER) { user.username = OPERATOR_USER; changed = true; }
    if (!user.passwordHash || !verifyPassword(OPERATOR_PASSWORD, user.passwordHash)) { user.passwordHash = hashPassword(OPERATOR_PASSWORD); changed = true; }
    if (user.plan !== 'PRO_PREMIUM') { user.plan = 'PRO_PREMIUM'; changed = true; }
    if (user.role !== 'OWNER') { user.role = 'OWNER'; changed = true; }
  }
  let license = db.licenses.find(l => l.id === user.licenseId && l.userId === OWNER_USER_ID);
  if (!license) license = db.licenses.find(l => l.owner === true && l.userId === OWNER_USER_ID);
  if (!license) {
    let key; do { key = keygen('PRO_PREMIUM'); } while (db.licenses.some(x => x.key === key));
    license = {
      id: rid('lic'), key, plan: 'PRO_PREMIUM', status: 'ACTIVE', userId: OWNER_USER_ID,
      createdAt: now(), activatedAt: now(), expiresAt: null, durationDays: 0,
      discordUserId: null, orderId: null, issuerUserId: null, issuerUsername: null,
      botSecret: `vh_${randomText(24)}`, bot: null, owner: true
    };
    db.licenses.unshift(license);
    changed = true;
  } else {
    if (license.userId !== OWNER_USER_ID) { license.userId = OWNER_USER_ID; changed = true; }
    if (license.plan !== 'PRO_PREMIUM') { license.plan = 'PRO_PREMIUM'; changed = true; }
    if (license.status !== 'ACTIVE') { license.status = 'ACTIVE'; changed = true; }
    if (license.expiresAt !== null) { license.expiresAt = null; changed = true; }
    if (license.durationDays !== 0) { license.durationDays = 0; changed = true; }
    if (!license.botSecret) { license.botSecret = `vh_${randomText(24)}`; changed = true; }
    if (license.owner !== true) { license.owner = true; changed = true; }
  }
  if (user.licenseId !== license.id) { user.licenseId = license.id; changed = true; }
  if (!db.settings[OWNER_USER_ID]) { db.settings[OWNER_USER_ID] = {}; changed = true; }
  if (changed) saveDb();
}

function saveDb() {
  fs.mkdirSync(path.dirname(DB_FILE), { recursive: true });
  const tmp = DB_FILE + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(db, null, 2), 'utf8');
  fs.renameSync(tmp, DB_FILE);
}
function now() { return new Date().toISOString(); }
function rid(prefix) { return `${prefix}_${crypto.randomBytes(9).toString('hex')}`; }
function randomText(bytes = 18) { return crypto.randomBytes(bytes).toString('base64url'); }
function hashPassword(password) {
  const salt = crypto.randomBytes(16).toString('hex');
  const hash = crypto.scryptSync(String(password), salt, 64).toString('hex');
  return `${salt}:${hash}`;
}
function verifyPassword(password, stored) {
  const [salt, expected] = String(stored || '').split(':');
  if (!salt || !expected) return false;
  const actual = crypto.scryptSync(String(password), salt, 64).toString('hex');
  if (actual.length !== expected.length) return false;
  return crypto.timingSafeEqual(Buffer.from(actual, 'hex'), Buffer.from(expected, 'hex'));
}
function tokenCryptoKey() {
  if (!BOT_WORKER_SECRET) throw new Error('NEXIVO_BOT_WORKER_SECRET가 필요합니다.');
  return crypto.scryptSync(BOT_WORKER_SECRET, 'nexivo-discord-token-v1', 32);
}
function encryptBotToken(token) {
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv('aes-256-gcm', tokenCryptoKey(), iv);
  const ciphertext = Buffer.concat([cipher.update(String(token), 'utf8'), cipher.final()]);
  const authTag = cipher.getAuthTag();
  return { v: 1, alg: 'aes-256-gcm', iv: iv.toString('base64url'), tag: authTag.toString('base64url'), data: ciphertext.toString('base64url') };
}
function decryptBotToken(payload) {
  if (!payload || payload.v !== 1 || payload.alg !== 'aes-256-gcm') return '';
  try {
    const decipher = crypto.createDecipheriv('aes-256-gcm', tokenCryptoKey(), Buffer.from(String(payload.iv || ''), 'base64url'));
    decipher.setAuthTag(Buffer.from(String(payload.tag || ''), 'base64url'));
    return Buffer.concat([decipher.update(Buffer.from(String(payload.data || ''), 'base64url')), decipher.final()]).toString('utf8');
  } catch {
    return '';
  }
}

function normalizePlan(v) { const p = String(v || '').toUpperCase(); return PLAN_META[p] ? p : 'BASIC'; }
function planLabel(v) { return PLAN_META[normalizePlan(v)].label; }
function planFamily(v) { return PLAN_META[normalizePlan(v)].botFamily; }
function isPremium(v) { return normalizePlan(v).endsWith('_PREMIUM'); }
function keygen(plan) {
  const meta = PLAN_META[plan];
  const a = () => crypto.randomBytes(3).toString('hex').toUpperCase();
  return `${meta.prefix}-${a()}-${a()}-${a()}`;
}
function expiresFor(activatedAt, days) {
  const d = Number(days);
  if (!Number.isFinite(d) || d <= 0 || !activatedAt) return null;
  return new Date(new Date(activatedAt).getTime() + Math.floor(d) * 86400000).toISOString();
}
function licenseExpired(l) { return Boolean(l.expiresAt && new Date(l.expiresAt).getTime() <= Date.now()); }
function remainingDays(l) {
  if (!l.expiresAt) return null;
  return Math.max(0, Math.ceil((new Date(l.expiresAt).getTime() - Date.now()) / 86400000));
}
function effectiveStatus(l) {
  if (l.status === 'REVOKED') return 'REVOKED';
  if (l.status === 'SUSPENDED') return 'SUSPENDED';
  if (licenseExpired(l)) return 'EXPIRED';
  return l.status || 'UNUSED';
}
function stable(v) { return JSON.stringify(v, (k, value) => { if (value && typeof value === 'object' && !Array.isArray(value)) return Object.keys(value).sort().reduce((o, key) => { o[key] = value[key]; return o; }, {}); return value; }); }
function cookie(req, name) {
  const raw = req.headers.cookie || '';
  const pair = raw.split(';').map(x => x.trim()).find(x => x.startsWith(name + '='));
  return pair ? decodeURIComponent(pair.slice(name.length + 1)) : null;
}
function setCookie(res, name, val, maxAge = SESSION_DAYS * 86400) {
  let v = `${name}=${encodeURIComponent(val)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${maxAge}`;
  if (COOKIE_SECURE) v += '; Secure';
  res.setHeader('Set-Cookie', v);
}
function clearCookie(res, name) { setCookie(res, name, '', 0); }
function json(res, status, data, headers = {}) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', ...headers });
  res.end(JSON.stringify(data));
}
function text(res, status, data, headers = {}) { res.writeHead(status, { 'Content-Type': 'text/plain; charset=utf-8', ...headers }); res.end(data); }
function parseBody(req) {
  return new Promise((resolve, reject) => {
    let raw = '';
    req.on('data', c => { raw += c; if (raw.length > 4 * 1024 * 1024) { req.destroy(); reject(new Error('body too large')); } });
    req.on('end', () => {
      if (!raw) return resolve({});
      try { resolve(JSON.parse(raw)); } catch { resolve(Object.fromEntries(new URLSearchParams(raw))); }
    });
    req.on('error', reject);
  });
}
function audit(actor, action, target, detail) {
  db.audit.unshift({ id: rid('aud'), at: now(), actor, action, target, detail: String(detail || '') });
  db.audit = db.audit.slice(0, 800);
}

const sseClients = new Set();
function broadcastEvent(e) {
  for (const client of [...sseClients]) {
    const ownerId = e?.payload?.ownerId;
    const licenseId = e?.payload?.licenseId;
    if (client.kind !== 'worker') {
      if (ownerId && ownerId !== client.userId && licenseId !== client.licenseId) continue;
      if (!ownerId && !licenseId) continue;
    }
    try {
      client.res.write(`event: sync\ndata: ${JSON.stringify(e)}\n\n`);
    } catch {
      sseClients.delete(client);
    }
  }
}

function requestBotSync(userId, reason = 'data_changed') {
  const u = db.users.find(x => x.id === userId);
  if (!u) return false;
  const settings = userSettings(userId);
  if (!settings.guildId) return false;
  pushEvent('bot.inventory_sync_requested', { ownerId: userId, reason, guildId: settings.guildId });
  return true;
}
function pushEvent(type, payload) {
  const e = { id: db.meta.nextEventId++, type, at: now(), payload };
  db.events.push(e);
  db.events = db.events.slice(-2000);
  broadcastEvent(e);
  return e;
}
function createLicense(rawPlan, meta = {}) {
  const plan = normalizePlan(rawPlan);
  let key; do { key = keygen(plan); } while (db.licenses.some(x => x.key === key));
  const d = Number(meta.durationDays);
  const durationDays = Number.isFinite(d) ? Math.max(0, Math.floor(d)) : 30;
  const l = {
    id: rid('lic'), key, plan, status: 'UNUSED', userId: null,
    createdAt: now(), activatedAt: null, expiresAt: null,
    durationDays, discordUserId: meta.discordUserId || null, orderId: meta.orderId || null,
    issuerUserId: meta.issuerUserId || null, issuerUsername: meta.issuerUsername || null,
    botSecret: `vh_${randomText(24)}`, bot: null
  };
  db.licenses.unshift(l);
  pushEvent('license.created', { licenseId: l.id, plan: l.plan, status: l.status, durationDays: l.durationDays });
  audit(meta.actor || 'SYSTEM', 'LICENSE_CREATE', l.id, `${planLabel(l.plan)} / ${l.key} / ${durationDays ? durationDays + '일' : '무기한'}`);
  saveDb();
  return l;
}
function operatorOK(req) {
  const h = String(req.headers.authorization || '');
  return h === 'Basic ' + Buffer.from(`${OPERATOR_USER}:${OPERATOR_PASSWORD}`).toString('base64');
}
function botOK(req, license) {
  const bridge = String(req.headers['x-nexivo-bridge-secret'] || '');
  const licenseMatch = String(req.headers['x-nexivo-license'] || '') === String(license?.key || '');
  const secretMatch = String(req.headers['x-nexivo-bot-secret'] || '') === String(license?.botSecret || '');
  if (!licenseMatch || !secretMatch) return false;
  // Per-license bot secrets are sufficient for customer bots. The shared bridge
  // secret remains supported for older integrations, but is no longer required.
  return !bridge || bridge === BOT_BRIDGE_SECRET;
}
function session(res, user) {
  const token = randomText(32);
  db.sessions.push({ token, userId: user.id, createdAt: now(), expiresAt: new Date(Date.now() + SESSION_DAYS * 86400000).toISOString() });
  db.sessions = db.sessions.filter(s => new Date(s.expiresAt).getTime() > Date.now()).slice(-500);
  saveDb();
  setCookie(res, 'nexivo_session', token);
}
function publicBotConfig() {
  return {
    clientId: String(db.botConfig.clientId || BOT_CLIENT_ID || ''),
    inviteUrl: String(db.botConfig.inviteUrl || BOT_INVITE_URL || ''),
    displayName: String(db.botConfig.displayName || BOT_DISPLAY_NAME || 'NEXIVO HUB Bot'),
    tokenConfigured: db.botConfig.tokenConfigured === true,
    tokenSource: db.botConfig.tokenConfigured === true ? 'secure_server_storage' : 'not_configured',
    tokenMasked: db.botConfig.tokenConfigured === true ? '••••••••••••••••' : ''
  };
}

function publicLicense(l, includeSecret = false) {
  const meta = PLAN_META[normalizePlan(l.plan)];
  const out = {
    id: l.id, key: l.key, plan: l.plan, planLabel: meta.label, status: effectiveStatus(l),
    createdAt: l.createdAt, activatedAt: l.activatedAt, expiresAt: l.expiresAt,
    durationDays: l.durationDays, remainingDays: remainingDays(l), discordUserId: l.discordUserId || null,
    orderId: l.orderId || null, issuerUserId: l.issuerUserId || null, issuerUsername: l.issuerUsername || null, bot: l.bot || null
  };
  if (includeSecret) out.botSecret = l.botSecret;
  return out;
}
function publicUser(u) {
  const l = db.licenses.find(x => x.id === u.licenseId);
  return {
    id: u.id, username: u.username, role: u.role || 'CUSTOMER', plan: u.plan, planLabel: planLabel(u.plan),
    licenseKey: l?.key || null, licenseStatus: l ? effectiveStatus(l) : 'UNKNOWN',
    expiresAt: l?.expiresAt || null, remainingDays: l ? remainingDays(l) : null,
    features: PLAN_META[normalizePlan(u.plan)].features, license: l ? publicLicense(l, false) : null,
    settings: db.settings[u.id] || {}
  };
}
function identity(req) {
  const t = cookie(req, 'nexivo_session');
  if (!t) return { user: null, license: null, reason: 'NO_SESSION' };
  const s = db.sessions.find(x => x.token === t && new Date(x.expiresAt).getTime() > Date.now());
  if (!s) return { user: null, license: null, reason: 'SESSION_EXPIRED' };
  const user = db.users.find(x => x.id === s.userId);
  if (!user) return { user: null, license: null, reason: 'USER_NOT_FOUND' };
  const license = db.licenses.find(x => x.id === user.licenseId);
  if (!license) return { user, license: null, reason: 'LICENSE_NOT_FOUND' };
  return { user, license, reason: effectiveStatus(license) === 'ACTIVE' ? null : effectiveStatus(license) };
}
function featureOK(user, feature) { return user?.role === 'OWNER' || PLAN_META[normalizePlan(user.plan)].features.includes(feature); }
function activeGate(license, res) {
  const status = effectiveStatus(license);
  if (status === 'EXPIRED') return json(res, 403, { error: '라이선스 기간이 만료되었습니다. 새로운 라이선스 키를 구매해주세요!', code: 'LICENSE_EXPIRED', expiresAt: license.expiresAt });
  if (status === 'SUSPENDED') return json(res, 403, { error: '라이선스가 일시 정지되었습니다.', code: 'LICENSE_SUSPENDED' });
  if (status === 'REVOKED') return json(res, 403, { error: '취소된 라이선스입니다.', code: 'LICENSE_REVOKED' });
  if (status !== 'ACTIVE') return json(res, 403, { error: '활성 라이선스가 필요합니다.', code: 'LICENSE_INACTIVE' });
  return null;
}
function sanitizeProduct(p, ownerId, fallbackId) {
  const stock = Number(p?.stock);
  return {
    id: String(p?.id || fallbackId || rid('prd')).slice(0, 80), ownerId,
    name: String(p?.name || '상품').slice(0, 120), price: Math.max(0, Number(p?.price) || 0),
    stock: Number.isFinite(stock) ? Math.max(-1, Math.floor(stock)) : -1,
    category: String(p?.category || '기본').slice(0, 80),
    description: String(p?.description || '').slice(0, 600),
    features: Array.isArray(p?.features) ? p.features.map(x => String(x).slice(0, 160)).slice(0, 40) : [],
    image_url: String(p?.image_url || p?.imageUrl || '').slice(0, 1000),
    createdAt: p?.createdAt || now(), updatedAt: p?.updatedAt || now()
  };
}
function sanitizeOrder(o, ownerId) {
  return { ...o, id: String(o?.id || rid('ord')).slice(0, 100), ownerId, user: String(o?.user || '').slice(0, 120), amount: Number(o?.amount || o?.total || 0) || 0, status: String(o?.status || '주문접수').slice(0, 40), updatedAt: o?.updatedAt || now(), createdAt: o?.createdAt || o?.created_at || now() };
}
function normalizeSettings(raw, base = {}) {
  raw = raw && typeof raw === 'object' ? raw : {};
  base = base && typeof base === 'object' ? base : {};
  const pick = (key, legacyKey, fallback = '') => raw[key] !== undefined ? raw[key] : (raw[legacyKey] !== undefined ? raw[legacyKey] : base[key] ?? fallback);
  const pickBool = (key, legacyKey, fallback = true) => {
    const value = raw[key] !== undefined ? raw[key] : (raw[legacyKey] !== undefined ? raw[legacyKey] : base[key]);
    if (value === undefined) return fallback;
    return value === true || value === 'true' || value === 1 || value === '1';
  };
  return {
    bankInfo: String(pick('bankInfo', 'bank_info')).slice(0, 500),
    guildId: String(pick('guildId', 'guild_id')).slice(0, 80),
    orderCategoryId: String(pick('orderCategoryId', 'order_category_id')).slice(0, 80),
    logChannelId: String(pick('logChannelId', 'log_channel_id')).slice(0, 80),
    buyerRoleId: String(pick('buyerRoleId', 'buyer_role_id')).slice(0, 80),
    orderCategoryName: String(pick('orderCategoryName', 'order_category_name')).slice(0, 120),
    stockChannelId: String(pick('stockChannelId', 'stock_channel_id')).slice(0, 80),
    stockMessageId: String(pick('stockMessageId', 'stock_message_id')).slice(0, 80),
    stockSyncEnabled: pickBool('stockSyncEnabled', 'stock_sync_enabled', true),
  };
}
function userSettings(ownerId) {
  return normalizeSettings(db.settings[ownerId]);
}
function botByLicense(l) { return l.bot || null; }
function touchBot(l, info) {
  l.bot = { ...(l.bot || {}), ...info, lastSeenAt: now() };
  const idx = db.bots.findIndex(b => b.licenseId === l.id);
  const record = { licenseId: l.id, userId: l.userId, ...(l.bot || {}) };
  if (idx >= 0) db.bots[idx] = record; else db.bots.unshift(record);
}
function botContext(req) {
  const key = String(req.headers['x-nexivo-license'] || '').trim().toUpperCase();
  const l = db.licenses.find(x => x.key.toUpperCase() === key);
  if (!l || !botOK(req, l)) return { ok: false, status: 401, error: '봇 연결 인증 정보가 올바르지 않습니다.' };
  const st = effectiveStatus(l);
  if (st !== 'ACTIVE') return { ok: false, status: 403, error: st === 'EXPIRED' ? '라이선스 기간이 만료되었습니다. 새로운 라이선스 키를 구매해주세요!' : `라이선스 상태: ${st}`, code: st === 'EXPIRED' ? 'LICENSE_EXPIRED' : `LICENSE_${st}` };
  const user = db.users.find(x => x.id === l.userId);
  if (!user) return { ok: false, status: 409, error: '라이선스에 연결된 계정이 없습니다.' };
  return { ok: true, license: l, user };
}

ensureOwnerAccount();

async function api(req, res) {
  const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  const p = url.pathname; const method = req.method;
  if (p === '/api/health') return json(res, 200, { ok: true, service: 'NEXIVO HUB', at: now() });

  // Shared Discord bot worker API. The worker is trusted and the Discord bot token is
  // intentionally never accepted from the browser or returned by any response.
  const workerAuth = String(req.headers['x-nexivo-worker-secret'] || '');
  const workerOK = () => {
    if (!BOT_WORKER_SECRET || !workerAuth) return false;
    const a = Buffer.from(workerAuth);
    const b = Buffer.from(BOT_WORKER_SECRET);
    return a.length === b.length && crypto.timingSafeEqual(a, b);
  };
  if (p === '/api/bot/secret-token' && method === 'GET') {
    if (!workerOK()) return json(res, 401, { error: '봇 워커 인증이 필요합니다.' });
    const token = decryptBotToken(db.botConfig.encryptedToken);
    if (!token) return json(res, 404, { error: '저장된 Discord Bot Token이 없습니다.' });
    return json(res, 200, { ok: true, token });
  }

  if (p === '/api/bot/tenants' && method === 'GET') {
    if (!workerOK()) return json(res, 401, { error: '봇 워커 인증이 필요합니다.' });
    const tenants = db.licenses
      .filter(l => effectiveStatus(l) === 'ACTIVE' && l.userId)
      .map(l => {
        const u = db.users.find(x => x.id === l.userId);
        if (!u) return null;
        const st = userSettings(u.id);
        if (!st.guildId) return null;
        return {
          userId: u.id, username: u.username, role: u.role || 'CUSTOMER',
          licenseId: l.id, discordUserId: l.discordUserId || null, plan: l.plan, planLabel: planLabel(l.plan),
          botFamily: planFamily(l.plan), features: PLAN_META[normalizePlan(l.plan)].features,
          guildId: st.guildId, stockChannelId: st.stockChannelId, stockMessageId: st.stockMessageId,
          stockSyncEnabled: st.stockSyncEnabled !== false, settings: st,
          products: db.products.filter(x => x.ownerId === u.id),
          orders: db.orders.filter(x => x.ownerId === u.id).sort((a,b) => String(b.createdAt).localeCompare(String(a.createdAt)))
        };
      }).filter(Boolean);
    return json(res, 200, { at: now(), tenants });
  }
  if (p === '/api/bot/heartbeat' && method === 'POST') {
    if (!workerOK()) return json(res, 401, { error: '봇 워커 인증이 필요합니다.' });
    const b = await parseBody(req);
    const guildId = String(b.guildId || '').trim();
    const tenant = db.licenses.map(l => ({ l, u: db.users.find(x => x.id === l.userId) })).find(x => x.u && userSettings(x.u.id).guildId === guildId && effectiveStatus(x.l) === 'ACTIVE');
    if (!tenant) return json(res, 404, { error: '연결된 라이선스 테넌트를 찾을 수 없습니다.' });
    touchBot(tenant.l, {
      status: 'CONNECTED', guildId, botUserId: b.botUserId || tenant.l.bot?.botUserId || null,
      botUsername: b.botUsername || tenant.l.bot?.botUsername || null,
      workerSeenAt: now(), stockSyncError: b.stockSyncError || null, stockSyncedAt: b.stockSyncedAt || tenant.l.bot?.stockSyncedAt || null, stockMessageId: b.stockMessageId || tenant.l.bot?.stockMessageId || null
    });
    if (b.tokenConfigured === true) { db.botConfig.tokenConfigured = true; db.botConfig.tokenLastVerifiedAt = now(); }
    if (b.stockMessageId || b.stockSyncedAt) {
      const st = userSettings(tenant.u.id);
      db.settings[tenant.u.id] = normalizeSettings({ ...st, stockMessageId: b.stockMessageId || st.stockMessageId }, st);
    }
    saveDb();
    return json(res, 200, { ok: true, licenseId: tenant.l.id, ownerId: tenant.u.id, bot: tenant.l.bot });
  }
  if (p === '/api/bot/stream' && method === 'GET' && workerOK()) {
    res.writeHead(200, { 'Content-Type': 'text/event-stream; charset=utf-8', 'Cache-Control': 'no-cache, no-transform', 'Connection': 'keep-alive', 'X-Accel-Buffering': 'no' });
    const tenants = db.licenses
      .filter(l => effectiveStatus(l) === 'ACTIVE' && l.userId)
      .map(l => {
        const u = db.users.find(x => x.id === l.userId);
        if (!u) return null;
        const st = userSettings(u.id);
        if (!st.guildId) return null;
        return { ownerId: u.id, licenseId: l.id, guildId: st.guildId, plan: l.plan, features: PLAN_META[normalizePlan(l.plan)].features, settings: st, products: db.products.filter(x => x.ownerId === u.id) };
      }).filter(Boolean);
    res.write(`event: ready\ndata: ${JSON.stringify({ ok: true, at: now(), tenants })}\n\n`);
    const client = { res, kind: 'worker' };
    sseClients.add(client);
    const heartbeat = setInterval(() => { try { res.write(`: worker-heartbeat ${Date.now()}\n\n`); } catch {} }, 25000);
    req.on('close', () => { clearInterval(heartbeat); sseClients.delete(client); });
    return;
  }

  // Auth
  if (p === '/api/auth/activate' && method === 'POST') {
    const b = await parseBody(req); const username = String(b.username || '').trim(); const password = String(b.password || ''); const key = String(b.licenseKey || '').trim().toUpperCase();
    if (!/^[A-Za-z0-9._-]{3,32}$/.test(username) || password.length < 6 || !key) return json(res, 400, { error: '아이디(3~32자), 비밀번호(6자 이상), 라이선스 키를 입력해주세요.' });
    const l = db.licenses.find(x => x.key.toUpperCase() === key);
    if (!l) return json(res, 400, { error: '존재하지 않는 라이선스 키입니다.' });
    if (effectiveStatus(l) === 'EXPIRED') return json(res, 400, { error: '이 라이선스는 이미 만료되었습니다. 새로운 라이선스 키를 구매해주세요!', code: 'LICENSE_EXPIRED' });
    if (l.status !== 'UNUSED') return json(res, 400, { error: '이미 활성화되었거나 사용할 수 없는 라이선스입니다.' });
    if (db.users.some(u => u.username.toLowerCase() === username.toLowerCase())) return json(res, 409, { error: '이미 사용 중인 아이디입니다.' });
    const u = { id: rid('usr'), username, passwordHash: hashPassword(password), plan: l.plan, licenseId: l.id, createdAt: now() };
    db.users.push(u); l.userId = u.id; l.status = 'ACTIVE'; l.activatedAt = now(); l.expiresAt = expiresFor(l.activatedAt, l.durationDays); l.bot = { status: 'DISCONNECTED' };
    pushEvent('license.activated', { ownerId: u.id, licenseId: l.id, plan: l.plan }); audit(username, 'LICENSE_ACTIVATE', l.id, l.key); saveDb(); session(res, u);
    return json(res, 200, { ok: true, user: publicUser(u) });
  }
  if (p === '/api/auth/login' && method === 'POST') {
    const b = await parseBody(req); const username = String(b.username || '').trim(); const password = String(b.password || ''); const key = String(b.licenseKey || '').trim().toUpperCase();
    if (OPERATOR_PASSWORD && username.toLowerCase() === OPERATOR_USER.toLowerCase() && password === OPERATOR_PASSWORD) {
      ensureOwnerAccount();
      const owner = db.users.find(x => x.id === OWNER_USER_ID);
      session(res, owner);
      return json(res, 200, { ok: true, user: publicUser(owner) });
    }
    const u = db.users.find(x => x.username.toLowerCase() === username.toLowerCase());
    if (!u || !verifyPassword(password, u.passwordHash)) return json(res, 401, { error: '아이디 또는 비밀번호가 올바르지 않습니다.' });
    const l = db.licenses.find(x => x.id === u.licenseId);
    if (!l || l.key.toUpperCase() !== key) return json(res, 401, { error: '연결된 라이선스 키가 올바르지 않습니다.' });
    const g = activeGate(l, res); if (g) return;
    session(res, u); return json(res, 200, { ok: true, user: publicUser(u) });
  }
  if (p === '/api/auth/logout' && method === 'POST') { db.sessions = db.sessions.filter(s => s.token !== cookie(req, 'nexivo_session')); saveDb(); clearCookie(res, 'nexivo_session'); return json(res, 200, { ok: true }); }

  // Bot bridge - authenticate using platform bridge secret + license key + per-license bot secret.
  if (p === '/api/bot/license/issue' && method === 'POST') {
    if (String(req.headers['x-nexivo-issue-secret'] || '') !== LICENSE_ISSUE_SECRET) return json(res, 401, { error: '라이선스 발급 브리지 인증이 필요합니다.' });
    const b = await parseBody(req); const d = b.durationDays === undefined ? 30 : Number(b.durationDays); const l = createLicense(b.plan, { actor: 'DISCORD_BOT', discordUserId: b.discordUserId, orderId: b.orderId, durationDays: d });
    return json(res, 200, { ok: true, license: publicLicense(l, true) });
  }
  if (p === '/api/bot/register' && method === 'POST') {
    const b = await parseBody(req); const lkey = String(b.licenseKey || req.headers['x-nexivo-license'] || '').trim().toUpperCase();
    const l = db.licenses.find(x => x.key.toUpperCase() === lkey);
    if (!l || !botOK(req, l)) return json(res, 401, { error: '봇 연결 인증 정보가 올바르지 않습니다.' });
    const g = activeGate(l, res); if (g) return;
    const user = db.users.find(x => x.id === l.userId); if (!user) return json(res, 409, { error: '라이선스 계정이 아직 활성화되지 않았습니다.' });
    const tier = String(b.botTier || planFamily(l.plan)).toUpperCase(); if (user.role !== 'OWNER' && tier !== planFamily(l.plan)) return json(res, 400, { error: `이 라이선스는 ${planFamily(l.plan)} 봇에 연결해야 합니다.` });
    const snapshot = b.snapshot || {};
    let products = db.products.filter(x => x.ownerId === user.id);
    let orders = db.orders.filter(x => x.ownerId === user.id);
    let settings = userSettings(user.id);
    if (!products.length && Array.isArray(snapshot.products) && snapshot.products.length) {
      products = snapshot.products.map((x, i) => sanitizeProduct(x, user.id, `P-${String(i + 1).padStart(4, '0')}`));
      db.products = db.products.filter(x => x.ownerId !== user.id).concat(products);
      pushEvent('product.bootstrap', { ownerId: user.id });
    }
    if (!orders.length && snapshot.orders && typeof snapshot.orders === 'object') {
      const arr = Array.isArray(snapshot.orders) ? snapshot.orders : Object.values(snapshot.orders);
      orders = arr.map(x => sanitizeOrder(x, user.id));
      db.orders = db.orders.filter(x => x.ownerId !== user.id).concat(orders);
      pushEvent('order.bootstrap', { ownerId: user.id });
    }
    if ((!settings.bankInfo && !settings.guildId && !settings.orderCategoryId) && snapshot.settings && typeof snapshot.settings === 'object') {
      settings = normalizeSettings(snapshot.settings, settings); db.settings[user.id] = settings; pushEvent('settings.bootstrap', { ownerId: user.id, settings });
    }
    touchBot(l, { status: 'CONNECTED', instanceId: String(b.instanceId || ''), tier, botUserId: b.botUserId || null, botUsername: b.botUsername || null });
    audit(user.username, 'BOT_REGISTER', l.id, `${tier} / ${b.botUsername || b.instanceId || 'bot'}`); saveDb();
    const cursor = db.events.length ? db.events[db.events.length - 1].id : 0;
    return json(res, 200, { ok: true, cursor, plan: l.plan, planLabel: planLabel(l.plan), products, orders, settings, license: publicLicense(l, false), bot: l.bot });
  }
  if (p === '/api/bot/products' && method === 'GET') {
    const ctx = botContext(req); if (!ctx.ok) return json(res, ctx.status, { error: ctx.error, code: ctx.code });
    return json(res, 200, { products: db.products.filter(x => x.ownerId === ctx.user.id) });
  }
  if (p === '/api/bot/orders' && method === 'GET') {
    const ctx = botContext(req); if (!ctx.ok) return json(res, ctx.status, { error: ctx.error, code: ctx.code });
    return json(res, 200, { orders: db.orders.filter(x => x.ownerId === ctx.user.id).sort((a,b)=>String(b.createdAt).localeCompare(String(a.createdAt))) });
  }
  if (p === '/api/bot/settings' && method === 'GET') {
    const ctx = botContext(req); if (!ctx.ok) return json(res, ctx.status, { error: ctx.error, code: ctx.code });
    return json(res, 200, { settings: userSettings(ctx.user.id) });
  }

  if (p === '/api/bot/stream' && method === 'GET') {
    const ctx = botContext(req); if (!ctx.ok) return json(res, ctx.status, { error: ctx.error, code: ctx.code });
    const { license: l, user: botUser } = ctx;
    res.writeHead(200, { 'Content-Type': 'text/event-stream; charset=utf-8', 'Cache-Control': 'no-cache, no-transform', 'Connection': 'keep-alive', 'X-Accel-Buffering': 'no' });
    res.write(`event: ready\ndata: ${JSON.stringify({ ok: true, at: now(), ownerId: botUser.id })}\n\n`);
    const snapshot = db.products.filter(x => x.ownerId === botUser.id);
    res.write(`event: sync\ndata: ${JSON.stringify({ id: 0, type: 'product.snapshot', at: now(), payload: { ownerId: botUser.id, licenseId: l.id, products: snapshot } })}\n\n`);
    touchBot(l, { status: 'CONNECTED' });
    saveDb();
    const client = { res, userId: botUser.id, licenseId: l.id, kind: 'bot' };
    sseClients.add(client);
    const heartbeat = setInterval(() => {
      try {
        touchBot(l, { status: 'CONNECTED' });
        saveDb();
        res.write(`: bot-heartbeat ${Date.now()}\n\n`);
      } catch {}
    }, 25000);
    req.on('close', () => { clearInterval(heartbeat); sseClients.delete(client); });
    return;
  }
  if (p === '/api/bot/sync' && method === 'GET') {
    const ctx = botContext(req); if (!ctx.ok) return json(res, ctx.status, { error: ctx.error, code: ctx.code });
    const { license: l, user } = ctx; const since = Number(url.searchParams.get('since') || 0);
    touchBot(l, { status: 'CONNECTED' });
    const events = db.events.filter(e => e.id > since && (
      e.payload?.ownerId === user.id || e.payload?.licenseId === l.id
    ));
    saveDb();
    return json(res, 200, { ok: true, cursor: db.events.length ? db.events[db.events.length - 1].id : since, events });
  }
  if (p === '/api/bot/worker-state' && method === 'POST') {
    if (!workerOK()) return json(res, 401, { error: '봇 워커 인증이 필요합니다.' });
    const b = await parseBody(req);
    const guildId = String(b.guildId || '').trim();
    const tenant = db.licenses.map(l => ({ l, u: db.users.find(x => x.id === l.userId) })).find(x => x.u && userSettings(x.u.id).guildId === guildId && effectiveStatus(x.l) === 'ACTIVE');
    if (!tenant) return json(res, 404, { error: '활성 라이선스 테넌트를 찾을 수 없습니다.' });
    const { l, u } = tenant;
    let changed = false;
    if (Array.isArray(b.orders)) {
      const incoming = b.orders.map(x => sanitizeOrder(x, u.id));
      const current = db.orders.filter(x => x.ownerId === u.id);
      if (stable(current) !== stable(incoming)) { db.orders = db.orders.filter(x => x.ownerId !== u.id).concat(incoming); pushEvent('order.snapshot', { ownerId: u.id, orders: incoming }); changed = true; }
    }
    if (b.settings && typeof b.settings === 'object') {
      const incoming = normalizeSettings(b.settings, userSettings(u.id));
      if (stable(userSettings(u.id)) !== stable(incoming)) { db.settings[u.id] = incoming; pushEvent('settings.snapshot', { ownerId: u.id, settings: incoming }); changed = true; }
    }
    touchBot(l, { status: 'CONNECTED', guildId, botUserId: b.botUserId || null, botUsername: b.botUsername || null, stockSyncError: b.stockSyncError || null });
    if (changed) audit(u.username, 'BOT_STATE_PUSH', l.id, '공용 봇 데이터 → 웹 동기화');
    saveDb();
    return json(res, 200, { ok: true, changed, ownerId: u.id, licenseId: l.id, plan: l.plan, features: PLAN_META[normalizePlan(l.plan)].features });
  }
  if (p === '/api/bot/state' && method === 'POST') {
    const ctx = botContext(req); if (!ctx.ok) return json(res, ctx.status, { error: ctx.error, code: ctx.code });
    const { license: l, user } = ctx; const b = await parseBody(req);
    let changed = false;
    if (Array.isArray(b.products)) {
      const incoming = b.products.map((x, i) => sanitizeProduct(x, user.id, `P-${String(i + 1).padStart(4, '0')}`));
      const current = db.products.filter(x => x.ownerId === user.id);
      if (stable(current) !== stable(incoming)) { db.products = db.products.filter(x => x.ownerId !== user.id).concat(incoming); pushEvent('product.snapshot', { ownerId: user.id, products: incoming }); changed = true; }
    }
    if (b.orders && (Array.isArray(b.orders) || typeof b.orders === 'object')) {
      const arr = Array.isArray(b.orders) ? b.orders : Object.values(b.orders);
      const incoming = arr.map(x => sanitizeOrder(x, user.id));
      const current = db.orders.filter(x => x.ownerId === user.id);
      if (stable(current) !== stable(incoming)) { db.orders = db.orders.filter(x => x.ownerId !== user.id).concat(incoming); pushEvent('order.snapshot', { ownerId: user.id, orders: incoming }); changed = true; }
    }
    if (b.settings && typeof b.settings === 'object') {
      const incoming = normalizeSettings(b.settings, userSettings(user.id));
      if (stable(userSettings(user.id)) !== stable(incoming)) { db.settings[user.id] = incoming; pushEvent('settings.snapshot', { ownerId: user.id, settings: incoming }); changed = true; }
    }
    touchBot(l, { status: 'CONNECTED', instanceId: String(b.instanceId || l.bot?.instanceId || ''), tier: String(b.botTier || l.bot?.tier || planFamily(l.plan)).toUpperCase(), botUserId: b.botUserId || l.bot?.botUserId || null, botUsername: b.botUsername || l.bot?.botUsername || null });
    if (changed) audit(user.username, 'BOT_STATE_PUSH', l.id, '봇 데이터 → 웹 동기화');
    saveDb(); if (changed && Array.isArray(b.products)) requestBotSync(user.id, 'data_changed'); return json(res, 200, { ok: true, changed, cursor: db.events.length ? db.events[db.events.length - 1].id : 0 });
  }

  // Logged-in customer
  const idn = identity(req);
  if (p === '/api/me' && method === 'GET') {
    if (!idn.user) return json(res, 401, { error: '로그인이 필요합니다.' });
    return json(res, 200, { user: publicUser(idn.user) });
  }
  if (p === '/api/stream' && method === 'GET') {
    if (!idn.user) return json(res, 401, { error: '로그인이 필요합니다.' });
    const gate = activeGate(idn.license, res); if (gate) return;
    res.writeHead(200, { 'Content-Type': 'text/event-stream; charset=utf-8', 'Cache-Control': 'no-cache, no-transform', 'Connection': 'keep-alive', 'X-Accel-Buffering': 'no' });
    res.write(`event: ready\ndata: ${JSON.stringify({ ok: true, at: now() })}\n\n`);
    const client = { res, userId: idn.user.id, licenseId: idn.license.id };
    sseClients.add(client);
    const heartbeat = setInterval(() => { try { res.write(`: keepalive ${Date.now()}\n\n`); } catch {} }, 25000);
    req.on('close', () => { clearInterval(heartbeat); sseClients.delete(client); });
    return;
  }
  if (!idn.user && p.startsWith('/api/')) return json(res, 401, { error: '로그인이 필요합니다.' });
  const gate = activeGate(idn.license, res); if (gate) return;
  const user = idn.user; const license = idn.license;

  if (p === '/api/dashboard' && method === 'GET') {
    const products = db.products.filter(x => x.ownerId === user.id); const orders = db.orders.filter(x => x.ownerId === user.id);
    const lowStock = products.filter(x => x.stock >= 0 && x.stock < 10).length;
    const pendingOrders = orders.filter(x => !['완료', '취소', '마감'].includes(String(x.status))).length;
    const connected = license.bot && license.bot.status === 'CONNECTED' && license.bot.lastSeenAt && Date.now() - new Date(license.bot.lastSeenAt).getTime() < 30000;
    return json(res, 200, { user: publicUser(user), stats: { products: products.length, orders: orders.length, lowStock, pendingOrders, planLabel: planLabel(user.plan), remainingDays: remainingDays(license) }, bot: { connected, ...(license.bot || {}) }, settings: userSettings(user.id), products, orders });
  }
  if (p === '/api/products' && method === 'GET') return json(res, 200, db.products.filter(x => x.ownerId === user.id));
  if (p === '/api/products' && method === 'POST') {
    const b = await parseBody(req); if (!String(b.name || '').trim()) return json(res, 400, { error: '상품명을 입력해주세요.' });
    const x = sanitizeProduct({ name: b.name, category: b.category, price: b.price, stock: b.stock, description: b.description, features: b.features, image_url: b.image_url }, user.id, rid('prd'));
    db.products.unshift(x); pushEvent('product.created', { ownerId: user.id, product: x }); audit(user.username, 'PRODUCT_CREATE', x.id, x.name); saveDb(); requestBotSync(user.id, 'data_changed'); return json(res, 200, x);
  }
  let pm = p.match(/^\/api\/products\/([^/]+)$/);
  if (pm && method === 'PATCH') {
    const x = db.products.find(z => z.id === pm[1] && z.ownerId === user.id); if (!x) return json(res, 404, { error: '상품을 찾을 수 없습니다.' });
    const b = await parseBody(req);
    for (const k of ['name', 'category', 'description', 'image_url']) if (b[k] !== undefined) x[k] = String(b[k] || '').slice(0, k === 'description' ? 600 : 1000);
    if (b.price !== undefined) x.price = Math.max(0, Number(b.price) || 0);
    if (b.stock !== undefined) x.stock = Math.max(-1, Math.floor(Number(b.stock) || 0));
    if (b.features !== undefined) x.features = Array.isArray(b.features) ? b.features.map(v => String(v).slice(0, 160)).slice(0, 40) : String(b.features || '').split(/\r?\n/).map(v => v.trim()).filter(Boolean).slice(0, 40);
    x.updatedAt = now(); pushEvent('product.updated', { ownerId: user.id, product: x }); audit(user.username, 'PRODUCT_UPDATE', x.id, `${x.name} / 재고 ${x.stock}`); saveDb(); requestBotSync(user.id, 'data_changed'); return json(res, 200, x);
  }
  if (pm && method === 'DELETE') {
    const x = db.products.find(z => z.id === pm[1] && z.ownerId === user.id); if (!x) return json(res, 404, { error: '상품을 찾을 수 없습니다.' });
    db.products = db.products.filter(z => z.id !== x.id); pushEvent('product.deleted', { ownerId: user.id, productId: x.id }); audit(user.username, 'PRODUCT_DELETE', x.id, x.name); saveDb(); requestBotSync(user.id, 'data_changed'); return json(res, 200, { ok: true });
  }
  if (p === '/api/orders' && method === 'GET') return json(res, 200, db.orders.filter(x => x.ownerId === user.id).sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt))));
  const om = p.match(/^\/api\/orders\/([^/]+)$/);
  if (om && method === 'PATCH') {
    const x = db.orders.find(z => z.id === om[1] && z.ownerId === user.id); if (!x) return json(res, 404, { error: '주문을 찾을 수 없습니다.' });
    const b = await parseBody(req); if (b.status !== undefined) x.status = String(b.status).slice(0, 40); x.updatedAt = now(); pushEvent('order.updated', { ownerId: user.id, order: x }); audit(user.username, 'ORDER_UPDATE', x.id, x.status); saveDb(); return json(res, 200, x);
  }
  if (p === '/api/reports' && method === 'GET') {
    if (!featureOK(user, 'reports')) return json(res, 403, { error: 'Pro 이상 라이선스가 필요합니다.' });
    const orders = db.orders.filter(x => x.ownerId === user.id);
    const done = orders.filter(x => String(x.status) === '완료');
    const totalRevenue = done.reduce((s, x) => s + (Number(x.amount || x.total) || 0), 0);
    const sold = done.reduce((s, x) => s + (Number(x.quantity) || 1), 0);
    const days = 14;
    const start = new Date(); start.setHours(0,0,0,0); start.setDate(start.getDate() - (days - 1));
    const series = Array.from({ length: days }, (_, i) => {
      const d = new Date(start); d.setDate(start.getDate() + i);
      const key = d.toISOString().slice(0, 10);
      const dayOrders = done.filter(o => String(o.createdAt || '').slice(0,10) === key);
      return { date: d.toISOString(), revenue: dayOrders.reduce((sum,o) => sum + (Number(o.amount || o.total) || 0), 0), orders: dayOrders.length };
    });
    return json(res, 200, { totalRevenue, completed: done.length, totalOrders: orders.length, sold, series });
  }
  if (p === '/api/bot/config' && method === 'GET') {
    if (user.role !== 'OWNER') return json(res, 403, { error: '오너 전용 기능입니다.' });
    return json(res, 200, publicBotConfig());
  }
  if (p === '/api/bot/config' && method === 'PATCH') {
    if (user.role !== 'OWNER') return json(res, 403, { error: '오너 전용 기능입니다.' });
    const b = await parseBody(req);
    const clientId = String(b.clientId || '').trim().slice(0, 80);
    const inviteUrl = String(b.inviteUrl || '').trim().slice(0, 1000);
    const displayName = String(b.displayName || '').trim().slice(0, 100);
    const suppliedToken = String(b.botToken || '').trim();
    if (inviteUrl && !/^https?:\/\//i.test(inviteUrl)) return json(res, 400, { error: '봇 초대 링크는 http:// 또는 https:// 링크여야 합니다.' });
    let encryptedToken = db.botConfig.encryptedToken || null;
    let tokenConfigured = db.botConfig.tokenConfigured === true;
    if (suppliedToken) {
      if (!BOT_WORKER_SECRET) return json(res, 500, { error: '봇 토큰 저장을 위한 서버 보안 시크릿(NEXIVO_BOT_WORKER_SECRET)이 설정되지 않았습니다.' });
      if (suppliedToken.length < 20 || suppliedToken.length > 256) return json(res, 400, { error: 'Discord Bot Token 형식이 올바르지 않습니다.' });
      encryptedToken = encryptBotToken(suppliedToken);
      tokenConfigured = true;
    }
    db.botConfig = { ...db.botConfig, clientId, inviteUrl, displayName: displayName || 'NEXIVO HUB Bot', encryptedToken, tokenConfigured, tokenUpdatedAt: suppliedToken ? now() : (db.botConfig.tokenUpdatedAt || null), updatedAt: now() };
    audit(user.username, 'BOT_CONFIG_UPDATE', user.id, `공용 봇 정보 수정 / 토큰 ${tokenConfigured ? '등록됨' : '미등록'}`);
    pushEvent('bot.config.updated', { ownerId: user.id, botConfig: publicBotConfig() });
    saveDb();
    return json(res, 200, publicBotConfig());
  }
  if (p === '/api/settings' && method === 'GET') return json(res, 200, userSettings(user.id));
  if (p === '/api/settings' && method === 'PATCH') {
    const b = await parseBody(req); const next = normalizeSettings(b, userSettings(user.id));
    db.settings[user.id] = next; pushEvent('settings.updated', { ownerId: user.id, settings: next }); audit(user.username, 'SETTINGS_UPDATE', user.id, '판매/Discord 설정 변경'); saveDb(); if (next.stockSyncEnabled && next.stockChannelId) requestBotSync(user.id, 'settings_changed'); return json(res, 200, next);
  }
  if (p === '/api/bot/status' && method === 'GET') {
    const botSeen = license.bot?.lastSeenAt ? Date.now() - new Date(license.bot.lastSeenAt).getTime() : Infinity;
    const connected = Boolean(license.bot && license.bot.status === 'CONNECTED' && botSeen < 120000);
    return json(res, 200, {
      connected, sharedBot: true, tokenValidated: false,
      bot: license.bot || { status: 'DISCONNECTED' },
      planFamily: planFamily(user.plan), plan: user.plan, planLabel: planLabel(user.plan),
      settings: userSettings(user.id),
      binding: { discordUserId: license.discordUserId || null, guildId: userSettings(user.id).guildId || null },
      botConfig: publicBotConfig(),
      security: { tokenClientVisible: false, sharedTokenServerOnly: true }
    });
  }
  if (p === '/api/bot/connect' && method === 'POST') {
    const b = await parseBody(req);
    const current = userSettings(user.id);
    const guildId = String(b.guildId || current.guildId || '').trim();
    const stockChannelId = String(b.stockChannelId || current.stockChannelId || '').trim();
    if (!/^\d{15,25}$/.test(guildId)) return json(res, 400, { error: '올바른 Discord 서버 ID를 입력해주세요.' });
    if (user.role !== 'OWNER' && !String(license.discordUserId || '').trim()) return json(res, 403, { error: '이 라이선스는 아직 Discord 사용자 ID에 연결되지 않았습니다. 오너에게 라이선스 발급 시 Discord User ID 등록을 요청해주세요.' });
    const conflict = db.licenses.find(x => x.id !== license.id && effectiveStatus(x) === 'ACTIVE' && x.userId && userSettings(x.userId).guildId === guildId);
    if (conflict) return json(res, 409, { error: '이미 다른 활성 라이선스에 연결된 Discord 서버입니다.' });
    if (stockChannelId && !/^\d{15,25}$/.test(stockChannelId)) return json(res, 400, { error: '올바른 재고 채널 ID를 입력해주세요.' });
    db.settings[user.id] = normalizeSettings({ ...current, guildId, stockChannelId, stockSyncEnabled: b.stockSyncEnabled === undefined ? true : Boolean(b.stockSyncEnabled) }, current);
    touchBot(license, { status: 'WAITING', guildId, stockChannelId });
    pushEvent('bot.binding_updated', { ownerId: user.id, licenseId: license.id, guildId, stockChannelId });
    audit(user.username, 'BOT_BIND', license.id, `Discord 서버 ${guildId} 연결 정보 저장`);
    saveDb();
    return json(res, 200, { ok: true, connected: false, sharedBot: true, bot: license.bot, settings: userSettings(user.id) });
  }
  if (p === '/api/bot/disconnect' && method === 'POST') {
    const current = userSettings(user.id);
    db.settings[user.id] = normalizeSettings({ ...current, guildId: '', stockChannelId: '', stockMessageId: '' }, current);
    touchBot(license, { status: 'DISCONNECTED', guildId: '', stockChannelId: '' });
    pushEvent('bot.binding_removed', { ownerId: user.id, licenseId: license.id });
    audit(user.username, 'BOT_UNBIND', license.id, 'Discord 서버 연결 해제');
    saveDb();
    return json(res, 200, { ok: true, connected: false, sharedBot: true, bot: license.bot, settings: userSettings(user.id) });
  }
  if (p === '/api/bot/sync-stock' && method === 'POST') {
    const settings = userSettings(user.id);
    if (!settings.guildId) return json(res, 400, { error: '먼저 Discord 서버를 연결해주세요.' });
    pushEvent('bot.inventory_sync_requested', { ownerId: user.id, licenseId: license.id, guildId: settings.guildId, reason: 'manual' });
    saveDb();
    return json(res, 202, { ok: true, queued: true, sharedBot: true, count: db.products.filter(x => x.ownerId === user.id).length });
  }
  // Owner-only license issuance center. Normal purchaser accounts must never see or call this.
  if (p.startsWith('/api/licenses')) {
    if (user.role !== 'OWNER') return json(res, 403, { error: '오너 전용 기능입니다.' });
  }
  if (p === '/api/licenses' && method === 'GET') {
    return json(res, 200, db.licenses.filter(l => l.issuerUserId === user.id).map(l => publicLicense(l, true)));
  }
  if (p === '/api/licenses' && method === 'POST') {
    const b = await parseBody(req); const plan = normalizePlan(b.plan); const d = b.durationDays === undefined ? 30 : Number(b.durationDays);
    const discordUserId = b.discordUserId === undefined || b.discordUserId === null ? null : String(b.discordUserId).trim();
    if (discordUserId && !/^\d{15,25}$/.test(discordUserId)) return json(res, 400, { error: 'Discord User ID는 15~25자리 숫자로 입력해주세요.' });
    if (!Number.isInteger(d) || d < 0 || d > 3650) return json(res, 400, { error: '기간은 0~3650일 사이의 정수로 입력해주세요.' });
    if (PLAN_META[plan].level > PLAN_META.PRO_PREMIUM.level) return json(res, 403, { error: '지원하지 않는 라이선스 등급입니다.' });
    const l = createLicense(plan, { actor: user.username, issuerUserId: user.id, issuerUsername: user.username, discordUserId, orderId: b.orderId, durationDays: d });
    audit(user.username, 'LICENSE_ISSUE', l.id, `${planLabel(l.plan)} / ${l.key}`); saveDb();
    return json(res, 200, { ok: true, license: publicLicense(l, true) });
  }
  let ownLic = p.match(/^\/api\/licenses\/([^/]+)\/(revoke|suspend|resume|extend|rotate-secret)$/);
  if (ownLic && method === 'POST') {
    const l = db.licenses.find(x => x.id === ownLic[1] && x.issuerUserId === user.id); if (!l) return json(res, 404, { error: '발급한 라이선스를 찾을 수 없습니다.' });
    const action = ownLic[2];
    if (action === 'revoke') { l.status = 'REVOKED'; pushEvent('license.revoked', { licenseId: l.id, ownerId: l.userId, issuerUserId: user.id }); audit(user.username, 'LICENSE_REVOKE', l.id, l.key); }
    if (action === 'suspend') { l.status = 'SUSPENDED'; pushEvent('license.suspended', { licenseId: l.id, ownerId: l.userId, issuerUserId: user.id }); audit(user.username, 'LICENSE_SUSPEND', l.id, l.key); }
    if (action === 'resume') { if (l.status === 'REVOKED') return json(res, 400, { error: '취소된 라이선스는 복구할 수 없습니다.' }); if (licenseExpired(l)) return json(res, 400, { error: '만료된 라이선스는 기간 연장 후 재개해주세요.' }); l.status = l.userId ? 'ACTIVE' : 'UNUSED'; pushEvent('license.resumed', { licenseId: l.id, ownerId: l.userId, issuerUserId: user.id }); audit(user.username, 'LICENSE_RESUME', l.id, l.key); }
    if (action === 'extend') {
      const b = await parseBody(req); const add = Math.floor(Number(b.days)); if (!Number.isInteger(add) || add < 1 || add > 3650) return json(res, 400, { error: '연장 기간은 1~3650일로 입력해주세요.' });
      l.durationDays = (l.durationDays || 0) + add;
      if (l.activatedAt) { const base = l.expiresAt && new Date(l.expiresAt) > new Date() ? new Date(l.expiresAt).getTime() : Date.now(); l.expiresAt = new Date(base + add * 86400000).toISOString(); if (l.status === 'EXPIRED') l.status = l.userId ? 'ACTIVE' : 'UNUSED'; }
      pushEvent('license.extended', { licenseId: l.id, ownerId: l.userId, issuerUserId: user.id, addDays: add, expiresAt: l.expiresAt }); audit(user.username, 'LICENSE_EXTEND', l.id, `${add}일`);
    }
    if (action === 'rotate-secret') { l.botSecret = `vh_${randomText(24)}`; audit(user.username, 'BOT_SECRET_ROTATE', l.id, l.key); pushEvent('bot.secret_rotated', { licenseId: l.id, ownerId: l.userId, issuerUserId: user.id }); }
    saveDb(); return json(res, 200, { ok: true, license: publicLicense(l, true) });
  }
  if (p === '/api/license/rotate-secret' && method === 'POST') { license.botSecret = `vh_${randomText(24)}`; pushEvent('bot.secret_rotated', { ownerId: user.id, licenseId: license.id }); audit(user.username, 'BOT_SECRET_ROTATE', license.id, '봇 연결 시크릿 재발급'); saveDb(); return json(res, 200, { ok: true, license: publicLicense(license, true) }); }
  if (p === '/api/notice' && method === 'GET') { if (!featureOK(user, 'notice')) return json(res, 403, { error: 'Basic Premium 이상 라이선스가 필요합니다.' }); return json(res, 200, { items: [] }); }
  if (p === '/api/grades' && method === 'GET') { if (!featureOK(user, 'grades')) return json(res, 403, { error: 'Pro 이상 라이선스가 필요합니다.' }); return json(res, 200, { items: [] }); }
  if (p === '/api/customers' && method === 'GET') { if (!featureOK(user, 'customers')) return json(res, 403, { error: 'Pro Premium 전용 기능입니다.' }); return json(res, 200, db.users.filter(x => x.id !== user.id).map(publicUser)); }
  if (p === '/api/audit' && method === 'GET') { if (!featureOK(user, 'audit')) return json(res, 403, { error: 'Pro Premium 전용 기능입니다.' }); return json(res, 200, db.audit.filter(a => a.actor === user.username).slice(0, 150)); }
  return json(res, 404, { error: 'Not Found' });
}

function staticFile(req, res) {
  let u = decodeURIComponent(new URL(req.url, `http://${req.headers.host || 'localhost'}`).pathname);
  if (u === '/') u = '/index.html';
  u = path.posix.normalize(u); const safe = u.replace(/^\/+/, ''); const f = path.join(PUBLIC, safe);
  if (!f.startsWith(PUBLIC)) return text(res, 403, 'Forbidden');
  fs.readFile(f, (err, data) => { if (err) return text(res, 404, 'Not Found'); res.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream', 'Cache-Control': 'no-cache', 'X-Content-Type-Options': 'nosniff' }); res.end(data); });
}
const server = http.createServer(async (req, res) => {
  try {
    if (req.method === 'OPTIONS') return json(res, 204, {}, { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-NEXIVO-Bridge-Secret, X-NEXIVO-Issue-Secret, X-NEXIVO-License, X-NEXIVO-Bot-Secret, X-NEXIVO-Worker-Secret', 'Access-Control-Allow-Methods': 'GET,POST,PATCH,DELETE,OPTIONS' });
    if (req.url.startsWith('/api/')) {
      res.setHeader('Access-Control-Allow-Origin', '*');
      res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-NEXIVO-Bridge-Secret, X-NEXIVO-Issue-Secret, X-NEXIVO-License, X-NEXIVO-Bot-Secret, X-NEXIVO-Worker-Secret');
      res.setHeader('Access-Control-Allow-Methods', 'GET,POST,PATCH,DELETE,OPTIONS');
      await api(req, res);
    } else staticFile(req, res);
  } catch (err) { console.error(err); json(res, 500, { error: '서버 오류가 발생했습니다.' }); }
});
server.on('error', err => { console.error(`NEXIVO HUB server error: ${err.message}`); process.exitCode = 1; });
server.listen(PORT, '0.0.0.0', () => { console.log(`NEXIVO HUB running on port ${PORT}`); });
