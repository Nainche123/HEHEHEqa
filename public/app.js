const app = document.getElementById('app');

const state = {
  user: null,
  view: 'overview',
  products: [],
  orders: [],
  bot: null,
  settings: {},
  stats: {},
  report: null,
  audit: [],
  customers: [],
  licenses: [],
  issuedLicenses: [],
  mode: 'login',
  stream: null,
};

const plans = {
  BASIC: { label: 'Basic', accent: 'blue', level: 1, features: ['products', 'orders', 'license', 'settings'] },
  BASIC_PREMIUM: { label: 'Basic Premium', accent: 'cyan', level: 2, features: ['products', 'orders', 'license', 'settings', 'notice'] },
  PRO: { label: 'Pro', accent: 'violet', level: 3, features: ['products', 'orders', 'license', 'settings', 'notice', 'grades', 'reports'] },
  PRO_PREMIUM: { label: 'Pro Premium', accent: 'gold', level: 4, features: ['products', 'orders', 'license', 'settings', 'notice', 'grades', 'reports', 'customers', 'audit'] },
};

const ORDER_STATUSES = ['주문접수', '입금대기', '결제완료', '처리중', '완료', '취소'];

function esc(v) {
  return String(v ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]));
}
function money(v) {
  return new Intl.NumberFormat('ko-KR').format(Number(v) || 0) + '원';
}
function number(v) {
  return new Intl.NumberFormat('ko-KR').format(Number(v) || 0);
}
function date(v) {
  return v ? new Date(v).toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' }) : '-';
}
function datetime(v) {
  return v ? new Date(v).toLocaleString('ko-KR', { dateStyle: 'medium', timeStyle: 'short' }) : '-';
}
function shortDate(v) {
  return v ? new Date(v).toLocaleDateString('ko-KR', { month: 'numeric', day: 'numeric' }) : '-';
}
function meta(plan) {
  return plans[String(plan || 'BASIC')] || plans.BASIC;
}
function planName(plan) {
  return meta(plan).label;
}
function planFamilyLabel(plan) { return String(plan || '').toUpperCase().includes('PRO') ? 'PRO' : 'BASIC'; }
function currentPlan() {
  return state.user?.plan || 'BASIC';
}
function isOwner() {
  return state.user?.role === 'OWNER';
}
function featureOK(feature) {
  return meta(currentPlan()).features.includes(feature);
}
function icon(name, size = 18) {
  const p = {
    grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    box: '<path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z"/><path d="m4 7.5 8 4.5 8-4.5M12 12v9"/>',
    cart: '<path d="M4 5h2l1.2 8.1a2 2 0 0 0 2 1.7h7.8a2 2 0 0 0 2-1.7L20 8H7"/><circle cx="10" cy="20" r="1.2"/><circle cx="17" cy="20" r="1.2"/>',
    key: '<circle cx="8.5" cy="15.5" r="4.5"/><path d="m12 12 8-8M17 4h3v3M15 7l2 2"/>',
    settings: '<path d="M12 3.5v2M12 18.5v2M4.8 4.8l1.4 1.4M17.8 17.8l1.4 1.4M3.5 12h2M18.5 12h2M4.8 19.2l1.4-1.4M17.8 6.2l1.4-1.4"/><circle cx="12" cy="12" r="4"/>',
    chart: '<path d="M4 19V5M4 19h16M7 15l3-4 3 2 5-7"/>',
    megaphone: '<path d="M4 13h3l10 5V6L7 11H4a2 2 0 0 0 0 4ZM7 13v5"/>',
    users: '<circle cx="10" cy="8" r="3.2"/><path d="M4.5 20a5.5 5.5 0 0 1 11 0M17 11a3 3 0 1 0-1.3-5.7M17.5 15.5A4.7 4.7 0 0 1 20 20"/>',
    shield: '<path d="M12 3 19 6v5c0 4.6-3 8.7-7 10-4-1.3-7-5.4-7-10V6l7-3Z"/><path d="m9 12 2 2 4-4"/>',
    logout: '<path d="M10 4H6.5A2.5 2.5 0 0 0 4 6.5v11A2.5 2.5 0 0 0 6.5 20H10M14 8l4 4-4 4M18 12H9"/>',
    user: '<circle cx="12" cy="8" r="3"/><path d="M5 20a7 7 0 0 1 14 0"/>',
    menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    edit: '<path d="M4 20h4L19 9l-4-4L4 16v4ZM13.5 6.5l4 4"/>',
    trash: '<path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v6M14 11v6"/>',
    search: '<circle cx="10.5" cy="10.5" r="6.2"/><path d="m15 15 5 5"/>',
    refresh: '<path d="M20 11a8 8 0 0 0-14-5L4 8M4 4v4h4M4 13a8 8 0 0 0 14 5l2-2M20 20v-4h-4"/>',
    copy: '<rect x="8" y="8" width="11" height="11" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    arrow: '<path d="M5 12h13M13 6l6 6-6 6"/>',
    pulse: '<path d="M3 12h4l2-6 4 12 2-6h6"/>',
    clock: '<circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2"/>',
    close: '<path d="m6 6 12 12M18 6 6 18"/>',
    lock: '<rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
    link: '<path d="M10 13a5 5 0 0 0 7.1.1l2-2a5 5 0 0 0-7.1-7.1l-1.2 1.2"/><path d="M14 11a5 5 0 0 0-7.1-.1l-2 2A5 5 0 0 0 12 20l1.2-1.2"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    info: '<circle cx="12" cy="12" r="8"/><path d="M12 11v5M12 7.5h.01"/>',
    server: '<rect x="4" y="4" width="16" height="6" rx="2"/><rect x="4" y="14" width="16" height="6" rx="2"/><path d="M8 7h.01M8 17h.01M11 7h6M11 17h6"/>',
    filter: '<path d="M4 6h16M7 12h10M10 18h4"/>',
    eye: '<path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6-10-6-10-6Z"/><circle cx="12" cy="12" r="2.5"/>',
    external: '<path d="M14 5h5v5M19 5l-8 8"/><path d="M19 13v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h5"/>',
    wallet: '<path d="M4 7.5A2.5 2.5 0 0 1 6.5 5H19a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H6.5A2.5 2.5 0 0 1 4 16.5v-9Z"/><path d="M4 8h13a2 2 0 0 1 2 2v2H14a2 2 0 0 0 0 4h5"/>',
  };
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${p[name] || p.grid}</svg>`;
}

function toast(msg, type = 'ok') {
  const e = document.createElement('div');
  e.className = 'toast ' + type;
  e.innerHTML = `<div class="toast-dot">${icon(type === 'error' ? 'info' : 'check', 14)}</div><div>${esc(msg)}</div>`;
  document.getElementById('toast-container').appendChild(e);
  setTimeout(() => e.remove(), 3400);
}

async function api(url, opts = {}) {
  const r = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    ...opts,
  });
  let d = {};
  try { d = await r.json(); } catch {}
  if (!r.ok) {
    const err = new Error(d.error || '요청에 실패했습니다.');
    err.code = d.code;
    err.data = d;
    throw err;
  }
  return d;
}

function handle(e) {
  if (e?.code === 'LICENSE_EXPIRED') showExpiry(e.message);
  else toast(e?.message || '요청에 실패했습니다.', 'error');
}

async function loadUserData() {
  const d = await api('/api/dashboard');
  state.user = d.user || state.user;
  state.products = Array.isArray(d.products) ? d.products : [];
  state.orders = Array.isArray(d.orders) ? d.orders : [];
  state.bot = d.bot || null;
  state.settings = d.settings || {};
  state.stats = d.stats || {};
}

async function loadBot() {
  try { state.bot = await api('/api/bot/status'); if (state.bot?.settings) state.settings = { ...state.settings, ...state.bot.settings }; }
  catch { state.bot = { connected: false, bot: { status: 'DISCONNECTED' }, settings: state.settings || {} }; }
}

async function loadReport() {
  if (!featureOK('reports')) return;
  try { state.report = await api('/api/reports'); }
  catch { state.report = null; }
}

async function loadAudit() {
  if (!featureOK('audit')) return;
  try { state.audit = await api('/api/audit'); }
  catch { state.audit = []; }
}

async function loadCustomers() {
  if (!featureOK('customers')) return;
  try { state.customers = await api('/api/customers'); }
  catch { state.customers = []; }
}

async function loadIssuedLicenses(){
  if (!isOwner()) return;
  try { state.issuedLicenses = await api('/api/licenses'); }
  catch { state.issuedLicenses = []; }
}

function showExpiry(msg = '라이선스 기간이 만료되었습니다. 새로운 라이선스 키를 구매해주세요!') {
  if (document.querySelector('.modal-backdrop')) return;
  const b = document.createElement('div');
  b.className = 'modal-backdrop';
  b.innerHTML = `<div class="modal expiry"><div class="expiry-icon">${icon('clock', 28)}</div><div class="eyebrow">LICENSE EXPIRED</div><h2>라이선스 기간이 종료되었습니다.</h2><p>${esc(msg)}</p><button class="btn primary full" id="expiry-close">확인</button></div>`;
  document.body.appendChild(b);
  b.querySelector('#expiry-close').onclick = () => b.remove();
}

function nav() {
  const p = currentPlan();
  const n = [
    ['grid', '개요', 'overview'],
    ['box', '상품 / 재고', 'products'],
    ['cart', '주문 관리', 'orders'],
    ['server', '봇 연동', 'integration'],
    ['key', '내 라이선스', 'license'],
  ];

  // 오너는 라이선스 발급만 하는 계정이 아니라 전체 스토어/자판기 운영자입니다.
  if (isOwner()) {
    n.push(['plus', '라이선스 발급', 'issue-license']);
    n.push(['megaphone', '공지 관리', 'notice']);
    n.push(['users', '등급 관리', 'grades']);
    n.push(['chart', '매출 리포트', 'reports']);
    n.push(['users', '고객 관리', 'customers']);
    n.push(['shield', '보안 로그', 'audit']);
  } else {
    if (plans[p].features.includes('notice')) n.push(['megaphone', '공지 관리', 'notice']);
    if (plans[p].features.includes('grades')) n.push(['users', '등급 관리', 'grades']);
    if (plans[p].features.includes('reports')) n.push(['chart', '매출 리포트', 'reports']);
    if (plans[p].features.includes('customers')) n.push(['users', '고객 관리', 'customers']);
    if (plans[p].features.includes('audit')) n.push(['shield', '보안 로그', 'audit']);
  }

  n.push(['settings', '설정', 'settings']);
  return n;
}

function statusClass(status) {
  const s = String(status || '').toUpperCase();
  if (['ACTIVE', 'CONNECTED', '완료', '결제완료'].includes(s)) return 'ok';
  if (['EXPIRED', 'SUSPENDED', '입금대기', '처리중'].includes(s)) return 'warn';
  if (['REVOKED', '취소'].includes(s)) return 'danger';
  return 'muted';
}
function statusLabel(status) {
  const m = { ACTIVE: '활성', UNUSED: '미사용', EXPIRED: '만료', SUSPENDED: '정지', REVOKED: '취소' };
  return m[String(status || '').toUpperCase()] || String(status || '미상');
}
function orderStatusClass(status) { return statusClass(status); }

function brand(compact = false) {
  return `<div class="brand${compact ? ' compact' : ''}"><span class="brand-mark"><i></i><i></i><i></i></span><span>NEXIVO HUB</span></div>`;
}

function authHTML() {
  const activate = state.mode === 'activate';
  const rememberedUsername = activate ? '' : (localStorage.getItem('nexivo-hub_remembered_username') || '');
  return `<div class="auth-shell">
    <div class="auth-noise"></div><div class="auth-orb orb-a"></div><div class="auth-orb orb-b"></div>
    <div class="auth-layout">
      <section class="auth-visual">
        <div class="visual-top">${brand()}<span class="secure">${icon('lock', 12)} SECURE</span></div>
        <div class="visual-copy">
          <span class="eyebrow">CONTROL CENTER</span>
          <h1>판매 운영을<br><em>더 깔끔하게.</em></h1>
          <p>NEXIVO HUB는 연결된 Discord 자판기의 상품·재고·주문을 한 공간에서 관리하는 운영 콘솔입니다.</p>
          <div class="visual-tags"><span>${icon('box', 11)} 상품 관리</span><span>${icon('server', 11)} 봇 연동</span><span>${icon('shield', 11)} 라이선스 보안</span></div>
        </div>
      </section>
      <div class="auth-side">
        <section class="auth-card">
          <div class="auth-head">${brand(true)}<span class="secure">${activate ? icon('key', 12) + ' ACTIVATE' : icon('shield', 12) + ' LOGIN'}</span></div>
          <div class="auth-tabs"><button class="${activate ? '' : 'active'}" data-mode="login">로그인</button><button class="${activate ? 'active' : ''}" data-mode="activate">라이선스 활성화</button></div>
          <div class="eyebrow">${activate ? 'LICENSE ACTIVATION' : 'WELCOME BACK'}</div>
          <h2>${activate ? '라이선스를 연결하세요' : '관리자 공간에 들어오세요'}</h2>
          <p class="auth-sub">${activate ? '구매한 라이선스 키를 연결하고 NEXIVO HUB 운영 콘솔을 시작합니다.' : '연결된 라이선스가 활성 상태인 계정만 관리자 기능을 사용할 수 있습니다.'}</p>
          <form id="auth-form">
            <label>아이디<div class="input">${icon('user', 16)}<input id="username" value="${esc(rememberedUsername)}" autocomplete="username" placeholder="myshop" required></div></label>
            <label>비밀번호<div class="input">${icon('key', 16)}<input id="password" type="password" autocomplete="current-password" placeholder="6자 이상" required></div></label>
            <label>라이선스 키<div class="input">${icon('shield', 16)}<input id="licenseKey" spellcheck="false" placeholder="VEX-BSC-XXXXXX-XXXXXX" ${activate ? 'required' : ''}></div></label>
            ${activate ? '<div class="auth-hint">구매한 라이선스 키를 입력하면 이 계정에 연결됩니다.</div>' : '<div class="auth-hint">오너 계정은 라이선스 키 없이 로그인되며, 구매자 계정은 본인 라이선스 키가 필요합니다.</div>'}
            <button class="btn primary auth-submit">${activate ? '계정 생성 및 활성화' : '로그인'} ${icon('arrow', 15)}</button>
          </form>
        </section>
        <div class="auth-meta"><span class="auth-session-note">${icon('link', 10)} 브라우저 세션 보호</span><span>HTTPS 권장 · SECURE ACCESS</span></div>
      </div>
    </div>
  </div>`;
}

function sidebarHTML() {
  const links = nav();
  const lic = state.user?.license;
  const remain = lic?.remainingDays;
  return `<aside class="sidebar" id="sidebar">
    <div class="side-head">
      ${brand()}
      <div class="workspace"><span class="live-dot">●</span><span>Control Center</span><span class="plan ${meta(currentPlan()).accent}">${isOwner() ? 'OWNER' : esc(planName(currentPlan()))}</span></div>
      <div class="side-search">${icon('search', 14)}<input id="nav-search" placeholder="메뉴 검색..." aria-label="메뉴 검색"></div>
    </div>
    <div class="side-label">WORKSPACE</div>
    <nav>${links.map(([ic,label,id]) => `<button class="nav-item ${state.view===id?'active':''}" data-view="${id}"><span>${icon(ic, 15)}</span><b>${esc(label)}</b>${id==='issue-license' && isOwner() ? '<small>OWNER</small>' : (['grades','reports','customers','audit'].includes(id) ? '<small>PRO</small>' : '')}</button>`).join('')}</nav>
    <div class="side-spacer"></div>
    <div class="license-mini"><div class="lm-top"><span class="eyebrow">LICENSE</span><span class="status-pill ${statusClass(lic?.status)}">${statusLabel(lic?.status || 'UNKNOWN')}</span></div><div class="lm-days">${remain == null ? '무기한' : `${number(remain)}일`}</div><small>${lic?.expiresAt ? `만료 ${date(lic.expiresAt)}` : '기간 제한 없음'}</small><code>${esc(lic?.key || '-')}</code></div>
    <button class="logout-btn" id="logout">${icon('logout', 14)} 로그아웃</button>
  </aside>`;
}

function topbarHTML() {
  const titles = {
    overview: ['개요', '스토어 운영 현황과 최근 활동을 한눈에 확인합니다.'],
    products: ['상품 / 재고', '상품 정보와 재고 수량을 관리합니다.'],
    orders: ['주문 관리', '접수된 주문의 상태와 처리 흐름을 관리합니다.'],
    integration: ['봇 연동', 'Discord 봇과 NEXIVO HUB의 연결 상태를 확인합니다.'],
    license: ['내 라이선스', '현재 사용 중인 플랜과 연결 상태를 확인합니다.'],
    'issue-license': ['라이선스 발급', '구매자에게 전달할 NEXIVO HUB 라이선스를 발급하고 관리합니다.'],
    settings: ['설정', '판매 및 Discord 연동 정보를 수정합니다.'],
    notice: ['공지 관리', '스토어 공지 기능을 관리합니다.'],
    grades: ['등급 관리', '누적 구매 기준에 따른 고객 등급을 확인합니다.'],
    reports: ['매출 리포트', '기간별 주문과 매출 흐름을 분석합니다.'],
    customers: ['고객 관리', '스토어를 이용한 고객 정보를 확인합니다.'],
    audit: ['보안 로그', '운영 콘솔의 최근 변경 이력을 확인합니다.'],
  };
  let [title, desc] = titles[state.view] || titles.overview;
  if (state.view === 'overview') { title = isOwner() ? '안녕하세요! 온탑님!' : '안녕하세요! 구매자님!'; desc = isOwner() ? '내 NEXIVO HUB 자판기의 상품 · 재고 · 주문과 Discord 봇을 관리하세요.' : '내 자판기 상품 · 재고 · 주문과 Discord 봇 연결 상태를 한곳에서 관리하세요.'; }
  return `<header class="topbar"><div class="top-main"><button class="mobile-toggle" id="side-open">${icon('menu', 17)}</button><div class="crumb">NEXIVO HUB <span>/</span> ${esc(title)}</div><h1>${esc(title)}</h1><p>${esc(desc)}</p></div><div class="top-right"><span class="live-pill"><i></i> ${isOwner() ? '오너 스토어' : '실시간 연결'}</span><button class="avatar" id="profile-pill">${icon('user', 15)} ${esc(state.user?.username || '관리자')}</button></div></header>`;
}

function licenseBanner() {
  const l = state.user?.license;
  const warn = l?.remainingDays != null && l.remainingDays <= 7;
  return `<div class="license-banner ${warn ? 'warning' : ''}"><span class="banner-icon">${icon(warn ? 'clock' : 'shield', 16)}</span><div><strong>${warn ? `라이선스 만료까지 ${number(l.remainingDays)}일 남았습니다.` : `${planName(currentPlan())} 라이선스가 정상 활성화되어 있습니다.`}</strong><small>${l?.expiresAt ? `만료 예정 ${date(l.expiresAt)} · ${esc(l.key || '')}` : '기간 제한 없이 사용할 수 있습니다.'}</small></div><button class="btn small" data-view="license">자세히 ${icon('arrow', 12)}</button></div>`;
}

function statCard(label, value, sub, ic, accent = '') {
  return `<div class="stat-card ${accent}"><span>${icon(ic, 14)} ${esc(label)}</span><b>${value}</b><small>${esc(sub)}</small></div>`;
}

function revenueChart(series = [], compact = false) {
  const w = compact ? 640 : 860, h = compact ? 220 : 310;
  const data = Array.isArray(series) && series.length ? series : Array.from({ length: 14 }, (_, i) => ({ date: Date.now() - (13 - i) * 86400000, revenue: 0, orders: 0 }));
  const values = data.map(d => Math.max(0, Number(d.revenue) || 0));
  const max = Math.max(1, ...values);
  const pad = { l: 12, r: 12, t: 24, b: 38 };
  const innerW = w - pad.l - pad.r, innerH = h - pad.t - pad.b;
  const pts = values.map((v, i) => {
    const x = pad.l + (data.length === 1 ? innerW / 2 : (i / (data.length - 1)) * innerW);
    const y = pad.t + innerH - (v / max) * innerH;
    return { x, y, ...data[i] };
  });
  const path = pts.map((p, i) => `${i ? 'L' : 'M'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
  const area = `${path} L ${pts[pts.length - 1].x.toFixed(1)} ${(h - pad.b).toFixed(1)} L ${pts[0].x.toFixed(1)} ${(h - pad.b).toFixed(1)} Z`;
  const grid = [0, .25, .5, .75, 1].map(t => {
    const y = pad.t + innerH * t;
    return `<line x1="${pad.l}" y1="${y}" x2="${w-pad.r}" y2="${y}" class="chart-grid"/>`;
  }).join('');
  const labels = pts.filter((p,i) => i===0 || i===pts.length-1 || i===Math.floor(pts.length/2)).map(p => `<text x="${p.x}" y="${h-11}" class="chart-label" text-anchor="middle">${esc(shortDate(p.date))}</text>`).join('');
  const dots = pts.map((p,i) => `<circle cx="${p.x}" cy="${p.y}" r="${compact ? 3 : 4}" class="chart-dot" data-index="${i}"/><circle cx="${p.x}" cy="${p.y}" r="${compact ? 10 : 12}" class="chart-hit" data-index="${i}"/>`).join('');
  return `<div class="chart-wrap" data-chart>
    <div class="chart-tooltip" id="chart-tooltip"><b></b><span></span></div>
    <svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="매출 추이 그래프"><defs><linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="rgba(55,168,255,.28)"/><stop offset="100%" stop-color="rgba(34,211,238,0)"/></linearGradient></defs>${grid}<path d="${area}" class="chart-area"/><path d="${path}" class="chart-line"/>${dots}${labels}</svg>
    <div class="chart-axis-note"><span>0원</span><span>최대 ${money(max)}</span></div>
  </div>`;
}

function stockSummary() {
  const list = [...state.products].sort((a,b) => {
    const av = Number(a.stock) < 0 ? 999999 : Number(a.stock);
    const bv = Number(b.stock) < 0 ? 999999 : Number(b.stock);
    return av - bv;
  }).slice(0, 6);
  if (!list.length) return `<div class="empty-state compact"><div class="empty-art">${icon('box', 22)}</div><h3>상품이 없습니다.</h3><p>상품을 등록하면 재고 상태가 여기에 표시됩니다.</p></div>`;
  return `<div class="stock-list">${list.map(p => {
    const s = Number(p.stock);
    const percent = s < 0 ? 100 : Math.min(100, Math.max(6, Math.round((s / Math.max(10, s + 10)) * 100)));
    const danger = s >= 0 && s < 10;
    return `<div class="stock-row"><div class="stock-name"><span class="pc-icon mini">${icon('box', 13)}</span><div><b>${esc(p.name)}</b><small>${esc(p.category || '기본')} · ${money(p.price)}</small></div></div><div class="stock-meter"><div class="stock-bar ${danger ? 'danger' : ''}"><i style="width:${percent}%"></i></div><span>${s < 0 ? '무제한' : `${number(s)}개`}</span></div></div>`;
  }).join('')}</div>`;
}

function recentOrders(limit = 5) {
  const list = [...state.orders].sort((a,b) => String(b.createdAt).localeCompare(String(a.createdAt))).slice(0, limit);
  if (!list.length) return `<div class="empty-state compact"><div class="empty-art">${icon('cart', 22)}</div><h3>최근 주문이 없습니다.</h3><p>주문이 들어오면 최신 순으로 표시됩니다.</p></div>`;
  return `<div class="activity-list">${list.map(o => `<div class="activity-row"><span class="activity-icon">${icon('cart', 13)}</span><div><b>${esc(o.user || '고객')}</b><small>${esc(o.id || '주문')} · ${datetime(o.createdAt)}</small></div><div class="activity-end"><strong>${money(o.amount || o.total)}</strong><span class="status-pill ${orderStatusClass(o.status)}">${esc(o.status || '-')}</span></div></div>`).join('')}</div>`;
}

function overviewHTML() {
  const s = state.stats || {};
  const completed = state.orders.filter(o => String(o.status) === '완료');
  const revenue = completed.reduce((sum,o)=>sum + (Number(o.amount || o.total) || 0),0);
  const chartSeries = state.report?.series || [];
  return `<div class="section first"><div class="section-title"><div><span class="eyebrow">OVERVIEW</span><h2>운영 현황</h2><p>중요한 수치와 상태만 빠르게 확인하세요.</p></div><div class="section-actions"><button class="btn small" id="refresh-dashboard">${icon('refresh',13)} 새로고침</button></div></div>
    ${licenseBanner()}
    <div class="hero-strip"><div><span class="hero-mini">최근 ${chartSeries.length || 14}일 판매 현황</span><strong>${money(revenue)}</strong><p>내 자판기 봇에서 들어온 주문을 기준으로 집계합니다. 상품·재고·주문 변경은 연결 상태에 따라 동기화됩니다.</p><div class="hero-tags"><span>${icon('pulse',12)} 실시간 상태</span><span>${number(state.orders.length)}건 주문</span><span>${number(state.products.length)}개 상품</span></div></div><div class="hero-graph" aria-hidden="true">${[28,46,36,62,55,82,70,92,66].map((h,i)=>`<i style="height:${h}%" class="${i===7?'hot':''}"></i>`).join('')}</div></div>
    <div class="stats-grid">
      ${statCard('총 상품', number(s.products ?? state.products.length), '등록된 상품 수', 'box')}
      ${statCard('총 주문', number(s.orders ?? state.orders.length), '누적 주문 건수', 'cart')}
      ${statCard('처리 대기', number(s.pendingOrders ?? 0), '아직 완료되지 않은 주문', 'clock', s.pendingOrders ? 'accent-warn' : '')}
      ${statCard('저재고', number(s.lowStock ?? 0), '재고 10개 미만', 'pulse', s.lowStock ? 'accent-danger' : '')}
    </div>
  </div>
  <div class="dashboard-grid">
    <div class="card chart-card"><div class="card-head"><div><h3>매출 추이</h3><p>최근 14일 · 완료 주문 기준</p></div><span class="trend-pill">${icon('chart',12)} LIVE</span></div>${revenueChart(chartSeries, false)}</div>
    <div class="card"><div class="card-head"><div><h3>재고 상태</h3><p>낮은 재고부터 정렬</p></div><button class="btn tiny" data-view="products">관리 ${icon('arrow',11)}</button></div>${stockSummary()}</div>
    <div class="card"><div class="card-head"><div><h3>최근 주문</h3><p>최신 주문 5건</p></div><button class="btn tiny" data-view="orders">전체 보기 ${icon('arrow',11)}</button></div>${recentOrders()}</div>
    <div class="card"><div class="card-head"><div><h3>시스템 상태</h3><p>현재 연결 정보를 확인합니다.</p></div></div><div class="system-list"><div><span>Discord 봇</span><b class="status-inline ${state.bot?.connected ? 'good' : ''}">${state.bot?.connected ? '연결됨' : '연결 대기'}</b></div><div><span>라이선스</span><b>${esc(planName(currentPlan()))}</b></div><div><span>남은 기간</span><b>${state.user?.license?.remainingDays == null ? '무기한' : `${number(state.user.license.remainingDays)}일`}</b></div><div><span>마지막 봇 신호</span><b>${state.bot?.bot?.lastSeenAt ? datetime(state.bot.bot.lastSeenAt) : '없음'}</b></div></div></div>
  </div>`;
}

function productsHTML() {
  const q = document.getElementById('product-search')?.value?.toLowerCase() || '';
  const cat = document.getElementById('product-category')?.value || 'ALL';
  const sort = document.getElementById('product-sort')?.value || 'default';
  const categories = [...new Set(state.products.map(p => p.category || '기본').filter(Boolean))].sort((a,b)=>a.localeCompare(b,'ko'));
  let list = state.products.filter(p => {
    const hit = JSON.stringify(p).toLowerCase().includes(q);
    return hit && (cat === 'ALL' || String(p.category || '기본') === cat);
  });
  list = [...list].sort((a,b)=>{
    if(sort==='stock-asc') return Number(a.stock)-Number(b.stock);
    if(sort==='stock-desc') return Number(b.stock)-Number(a.stock);
    if(sort==='price-asc') return Number(a.price)-Number(b.price);
    if(sort==='price-desc') return Number(b.price)-Number(a.price);
    return String(b.updatedAt || b.createdAt || '').localeCompare(String(a.updatedAt || a.createdAt || ''));
  });
  const low = state.products.filter(p=>Number(p.stock)>=0 && Number(p.stock)<10).length;
  const soldout = state.products.filter(p=>Number(p.stock)===0).length;
  const active = state.products.filter(p=>p.stock !== null && p.stock !== undefined).length;
  return `<div class="section first">
    <div class="section-title"><div><span class="eyebrow">CATALOG / INVENTORY</span><h2>상품 관리</h2><p>내 자판기에서 판매할 상품을 추가하고 가격·재고를 관리합니다. 변경사항은 연결된 Discord 자판기 봇에 동기화됩니다.</p></div><div class="section-actions"><button class="btn" id="refresh-products">${icon('refresh',13)} 새로고침</button><button class="btn primary" id="add-product">${icon('plus',14)} 상품 추가</button></div></div>
    <div class="catalog-stats">
      <div class="catalog-stat"><span>${icon('box',13)} 등록 상품</span><b>${number(state.products.length)}</b><small>전체 상품 수</small></div>
      <div class="catalog-stat"><span>${icon('check',13)} 운영 상품</span><b>${number(active)}</b><small>재고 관리 대상</small></div>
      <div class="catalog-stat warn-stat"><span>${icon('pulse',13)} 저재고</span><b>${number(low)}</b><small>10개 미만</small></div>
      <div class="catalog-stat danger-stat"><span>${icon('clock',13)} 품절</span><b>${number(soldout)}</b><small>재고 0개</small></div>
    </div>
    <div class="catalog-toolbar">
      <div class="searchbox">${icon('search',14)}<input id="product-search" value="${esc(q)}" placeholder="상품명, 카테고리, 설명 검색"></div>
      <select id="product-category"><option value="ALL" ${cat==='ALL'?'selected':''}>전체 카테고리</option>${categories.map(c=>`<option value="${esc(c)}" ${cat===c?'selected':''}>${esc(c)}</option>`).join('')}</select>
      <select id="product-sort"><option value="default" ${sort==='default'?'selected':''}>최근 수정순</option><option value="stock-asc" ${sort==='stock-asc'?'selected':''}>재고 적은순</option><option value="stock-desc" ${sort==='stock-desc'?'selected':''}>재고 많은순</option><option value="price-asc" ${sort==='price-asc'?'selected':''}>가격 낮은순</option><option value="price-desc" ${sort==='price-desc'?'selected':''}>가격 높은순</option></select>
      <span class="result-count">${number(list.length)}개 표시</span>
    </div>
    <div class="product-table card">
      <div class="product-table-head"><span>상품</span><span>가격</span><span>재고</span><span>상태</span><span>관리</span></div>
      <div class="product-table-body">${list.length ? list.map(productRow).join('') : `<div class="empty-state compact"><div class="empty-art">${icon('box',22)}</div><h3>${q || cat!=='ALL' ? '조건에 맞는 상품이 없습니다.' : '등록된 상품이 없습니다.'}</h3><p>${q || cat!=='ALL' ? '검색이나 필터 조건을 변경해보세요.' : '첫 상품을 추가하면 이곳에서 재고와 가격을 관리할 수 있습니다.'}</p>${!q && cat==='ALL' ? '<button class="btn primary" id="empty-add">상품 추가</button>' : ''}</div>`}</div>
    </div>
  </div>`;
}

function productRow(p) {
  const stock = Number(p.stock);
  const low = stock >= 0 && stock < 10;
  const soldout = stock === 0;
  const pct = stock < 0 ? 100 : Math.max(4, Math.min(100, Math.round((stock / Math.max(10, stock + 10)) * 100)));
  const status = stock < 0 ? '무제한' : soldout ? '품절' : low ? '저재고' : '판매중';
  const stClass = soldout ? 'danger' : low ? 'warn' : 'ok';
  return `<div class="product-row">
    <div class="product-main"><span class="pc-icon row-icon">${icon('box',16)}</span><div><b>${esc(p.name)}</b><small>${esc(p.category || '기본')}${p.description ? ` · ${esc(p.description).slice(0,70)}` : ''}</small></div></div>
    <div class="product-price">${money(p.price)}</div>
    <div class="product-stock"><div class="stock-inline"><div class="stock-bar"><span style="width:${pct}%"></span></div><b>${stock < 0 ? '∞' : number(stock)}</b></div><div class="stock-adjust"><button class="btn tiny" data-stock="-1" data-id="${esc(p.id)}" aria-label="재고 1개 감소">−</button><button class="btn tiny" data-stock="1" data-id="${esc(p.id)}" aria-label="재고 1개 증가">+</button></div></div>
    <div><span class="status-pill ${stClass}">${status}</span></div>
    <div class="product-actions"><button class="btn tiny" data-edit="${esc(p.id)}">${icon('edit',12)} 수정</button><button class="btn tiny danger" data-delete="${esc(p.id)}">${icon('trash',12)} 삭제</button></div>
  </div>`;
}

function ordersHTML() {
  const pending = state.orders.filter(o => !['완료','취소'].includes(String(o.status))).length;
  const done = state.orders.filter(o => String(o.status) === '완료').length;
  const cancelled = state.orders.filter(o => String(o.status) === '취소').length;
  return `<div class="section first"><div class="section-title"><div><span class="eyebrow">ORDERS</span><h2>주문 관리</h2><p>주문 상태를 한곳에서 관리하세요.</p></div><button class="btn" id="refresh-orders">${icon('refresh',13)} 새로고침</button></div><div class="order-stats"><div><span>전체 주문</span><b>${number(state.orders.length)}</b></div><div><span>처리 대기</span><b class="warn">${number(pending)}</b></div><div><span>완료</span><b class="good">${number(done)}</b></div><div><span>취소</span><b class="danger">${number(cancelled)}</b></div></div><div class="table-wrap"><table><thead><tr><th>주문 ID</th><th>고객</th><th>금액</th><th>상태</th><th>생성일</th><th>변경일</th></tr></thead><tbody>${state.orders.length ? state.orders.map(o => `<tr><td><code>${esc(o.id)}</code></td><td><strong>${esc(o.user || '고객')}</strong></td><td>${money(o.amount || o.total)}</td><td><select class="order-status" data-id="${esc(o.id)}">${ORDER_STATUSES.map(s=>`<option value="${esc(s)}" ${String(o.status)===s?'selected':''}>${esc(s)}</option>`).join('')}</select></td><td>${datetime(o.createdAt)}</td><td>${datetime(o.updatedAt)}</td></tr>`).join('') : `<tr><td colspan="6"><div class="empty-state compact"><div class="empty-art">${icon('cart',22)}</div><h3>주문이 없습니다.</h3><p>새 주문이 들어오면 이곳에서 처리할 수 있습니다.</p></div></td></tr>`}</tbody></table></div></div>`;
}

function integrationHTML() {
  const connected = Boolean(state.bot?.connected);
  const bot = state.bot?.bot || {};
  const s = state.bot?.settings || state.settings || {};
  const features = meta(currentPlan()).features;
  return `<div class="section first">
    <div class="section-title"><div><span class="eyebrow">SHARED DISCORD BOT</span><h2>봇 연동</h2><p>NEXIVO HUB의 공용 Discord 봇 하나를 사용합니다. 구매자는 봇 토큰을 입력하지 않으며, 서버 ID만 연결하면 됩니다.</p></div><button class="btn" id="refresh-bot">${icon('refresh',13)} 상태 새로고침</button></div>
    <div class="integration-hero ${connected ? 'connected' : ''}"><div><span class="eyebrow">${connected ? 'CONNECTED' : 'WAITING FOR WORKER'}</span><h3>${connected ? '공용 Discord 봇이 이 서버에서 동작 중입니다.' : 'Discord 서버 연결 정보를 등록해주세요.'}</h3><p>${connected ? `${esc(bot.botUsername || 'NEXIVO HUB Bot')} · ${esc(planName(currentPlan()))}` : '실제 Discord Bot Token은 Render의 봇 워커 환경변수에만 존재합니다.'}</p></div><span class="integration-icon">${icon(connected ? 'check' : 'server',24)}</span></div>
    <div class="bot-connection-grid">
      <div class="card"><div class="card-head"><div><h3>내 Discord 서버 연결</h3><p>Guild ID와 재고 채널 ID만 입력합니다. 공용 봇 토큰은 Render 봇 워커의 Secret Environment Variable에만 보관합니다.</p></div></div>
        <div class="form-grid">
          <label>Discord 서버 ID<div class="input">${icon('server',16)}<input id="bot-guild" value="${esc(s.guildId || '')}" placeholder="123456789012345678"></div></label>
          <label>재고 채널 ID<div class="input">${icon('megaphone',16)}<input id="bot-stock-channel" value="${esc(s.stockChannelId || '')}" placeholder="123456789012345678"></div></label>
          <label class="full-row bot-switch-row"><span><b>재고 자동 동기화</b><small>웹에서 상품·재고를 바꾸면 공용 봇이 해당 서버의 재고 메시지를 갱신합니다.</small></span><input id="bot-stock-sync" type="checkbox" ${s.stockSyncEnabled !== false ? 'checked' : ''}></label>
        </div>
        <div class="bot-connect-actions"><button class="btn primary" id="connect-bot">${icon('link',14)} ${connected ? '연결 정보 저장' : '서버 연결'}</button>${connected ? `<button class="btn danger" id="disconnect-bot">연결 해제</button><button class="btn" id="sync-stock-now">${icon('refresh',13)} 지금 재고 동기화</button>` : ''}${state.bot?.botConfig?.inviteUrl ? `<a class="btn" href="${esc(state.bot.botConfig.inviteUrl)}" target="_blank" rel="noreferrer">${icon('external',13)} 공용 봇 초대</a>` : ''}</div>
        ${bot.stockSyncedAt ? `<div class="bot-sync-meta"><span>최근 재고 동기화</span><b>${esc(datetime(bot.stockSyncedAt))}</b>${bot.stockSyncError ? `<span class="sync-error">${esc(bot.stockSyncError)}</span>` : '<span class="sync-ok">동기화 정상</span>'}</div>` : ''}
      </div>
      <div class="card"><div class="card-head"><div><h3>토큰 보안</h3><p>공용 Bot Token은 구매자 웹브라우저와 NEXIVO HUB 웹 서비스에 전달되지 않습니다.</p></div></div><div class="permission-list"><div>${icon('lock',13)} Discord Bot Token <b>Render 봇 워커 환경변수 전용</b></div><div>${icon('shield',13)} 구매자 브라우저 <b>토큰 접근 불가</b></div><div>${icon('server',13)} 테넌트 구분 <b>Guild ID + 라이선스</b></div><div>${icon('box',13)} 상품 / 재고 <b>변경 이벤트 기반 동기화</b></div></div></div>
      <div class="card"><div class="card-head"><div><h3>현재 플랜 기능</h3><p>${esc(planName(currentPlan()))} 라이선스에 허용된 기능만 Discord에서 노출됩니다.</p></div></div><div class="permission-list">${['products','orders','notice','grades','reports','customers','audit'].map(f => `<div class="feature-row ${features.includes(f) ? 'enabled':'locked'}">${icon(features.includes(f) ? 'check' : 'lock',13)} <b>${esc({products:'상품 / 재고',orders:'주문 관리',notice:'공지',grades:'등급',reports:'매출 통계',customers:'고객 관리',audit:'감사 로그'}[f])}</b><span>${features.includes(f) ? '허용' : '플랜 제한'}</span></div>`).join('')}</div><div class="notice-box" style="margin-top:10px">${icon('info',15)} Basic / Basic Premium / Pro / Pro Premium을 같은 봇이 담당하고, 실제 노출 기능은 각 라이선스 플랜을 기준으로 서버에서 결정합니다.</div></div>
    </div>
  </div>`;
}
function licenseHTML() {
  const l = state.user?.license;
  return `<div class="section first"><div class="section-title"><div><span class="eyebrow">LICENSE</span><h2>내 라이선스</h2><p>플랜과 기간, 연결 상태를 확인합니다.</p></div></div>${licenseBanner()}<div class="license-stats"><div><span>플랜</span><b>${esc(planName(currentPlan()))}</b></div><div><span>상태</span><b>${esc(statusLabel(l?.status))}</b></div><div><span>남은 기간</span><b>${l?.remainingDays == null ? '무기한' : number(l.remainingDays)+'일'}</b></div><div><span>발급일</span><b>${date(l?.createdAt)}</b></div></div><div class="license-two"><div class="license-key"><div class="label-row"><span>라이선스 키</span><button class="btn tiny" id="copy-license">${icon('copy',12)} 복사</button></div><code>${esc(l?.key || '-')}</code><small>계정과 연결된 라이선스 키입니다.</small></div><div class="secret-box"><div class="label-row"><span>NEXIVO HUB 연결 시크릿</span></div><code>••••••••••••••••</code><small>공용 Discord 봇 토큰은 Render 봇 워커에만 보관되며 사용자에게 공개하지 않습니다.</small></div></div><div class="card"><div class="card-head"><div><h3>사용 가능 기능</h3><p>현재 플랜에 포함된 기능입니다.</p></div></div><div class="permission-list">${['products','orders','license','settings','notice','grades','reports','customers','audit'].map(f => `<div class="feature-row ${featureOK(f) ? 'enabled':'locked'}">${icon(featureOK(f) ? 'check' : 'lock', 13)} <b>${esc({products:'상품 / 재고',orders:'주문 관리',license:'라이선스',settings:'설정',notice:'공지 관리',grades:'등급 관리',reports:'매출 리포트',customers:'고객 관리',audit:'보안 로그'}[f])}</b><span>${featureOK(f) ? '사용 가능' : '플랜 업그레이드 필요'}</span></div>`).join('')}</div></div></div>`;
}
function settingsHTML() {
  const s = state.settings || {};
  const botCfg = state.bot?.botConfig || {};
  const lic = state.user?.license || {};
  const ownerConfig = isOwner() ? `<div class="card owner-bot-config"><div class="card-head"><div><h3>공용 Discord 봇 설정</h3><p>공용 봇은 한 개만 운용합니다. Bot Token은 서버에 암호화해서 저장되며 구매자 브라우저로 전달하지 않습니다.</p></div><span class="status-pill ${botCfg.tokenConfigured ? 'ok' : 'warn'}">${botCfg.tokenConfigured ? 'TOKEN 등록됨' : 'TOKEN 미등록'}</span></div><div class="form-grid"><label>Bot Client ID<div class="input bare"><input id="set-bot-client" value="${esc(botCfg.clientId || '')}" placeholder="Discord Application / Client ID"></div></label><label>봇 이름<div class="input bare"><input id="set-bot-name" value="${esc(botCfg.displayName || 'NEXIVO HUB Bot')}" placeholder="NEXIVO HUB Bot"></div></label><label class="full-row">봇 초대 링크<div class="input bare"><input id="set-bot-invite" value="${esc(botCfg.inviteUrl || '')}" placeholder="https://discord.com/oauth2/authorize?..." spellcheck="false"></div></label><label class="full-row">Discord Bot Token<div class="secret-input"><div class="input bare">${icon('lock',15)}<input id="set-bot-token" type="password" value="" placeholder="${botCfg.tokenConfigured ? '저장된 토큰을 유지하려면 비워두세요' : 'Discord Developer Portal의 Bot Token'}" autocomplete="new-password" spellcheck="false"><button type="button" class="secret-toggle" id="toggle-bot-token" aria-label="토큰 표시/숨기기">${icon('eye',16)}</button></div><small class="field-hint">입력 중에는 눈 아이콘으로 표시/숨김할 수 있습니다. 저장 후 토큰 원문은 다시 화면에 표시되지 않습니다.</small></div></label><div class="notice-box full-row">${icon('shield',15)} <b>토큰은 오너만 입력/교체할 수 있습니다.</b> 일반 구매자 API 응답과 브라우저 상태에는 실제 토큰이 포함되지 않습니다.</div><div class="bot-config-status full-row"><span>연동 방식</span><b>공용 봇 1개 · 서버별 라이선스/Guild ID 분리</b><span>토큰 보관</span><b>서버 암호화 저장 · Worker만 복호화</b></div><button class="btn primary full" id="save-bot-config">${icon('check',13)} 공용 봇 정보 저장</button></div></div>` : '';
  return `<div class="section first"><div class="section-title"><div><span class="eyebrow">SETTINGS</span><h2>설정</h2><p>스토어 판매 정보와 Discord 자판기 연결 정보를 관리합니다.</p></div><button class="btn primary" id="save-settings">${icon('check',13)} 변경사항 저장</button></div>${ownerConfig}<div class="settings-grid"><div class="card"><div class="card-head"><div><h3>스토어 기본 설정</h3><p>고객 안내에 사용할 정보를 입력하세요.</p></div></div><div class="form-grid"><label class="full-row">입금 안내<textarea id="set-bank" placeholder="예: 카카오뱅크 3333-...">${esc(s.bankInfo || '')}</textarea></label><label>Discord Guild ID<div class="input bare"><input id="set-guild" value="${esc(s.guildId || '')}" placeholder="예: 123456789012345678"></div></label><label>주문 카테고리 ID<div class="input bare"><input id="set-order-cat" value="${esc(s.orderCategoryId || '')}" placeholder="선택"></div></label><label>로그 채널 ID<div class="input bare"><input id="set-log" value="${esc(s.logChannelId || '')}" placeholder="선택"></div></label><label>구매자 역할 ID<div class="input bare"><input id="set-role" value="${esc(s.buyerRoleId || '')}" placeholder="선택"></div></label><label>재고 채널 ID<div class="input bare"><input id="set-stock-channel" value="${esc(s.stockChannelId || '')}" placeholder="재고 안내를 표시할 채널 ID"></div></label><label class="full-row">주문 카테고리 이름<div class="input bare"><input id="set-order-cat-name" value="${esc(s.orderCategoryName || '')}" placeholder="선택"></div></label><label class="full-row bot-switch-row"><span><b>웹 ↔ Discord 재고 자동 동기화</b><small>웹에서 상품/재고를 변경하면 연결된 서버의 공용 봇 재고 패널이 자동으로 갱신됩니다.</small></span><input id="set-stock-sync" type="checkbox" ${s.stockSyncEnabled !== false ? 'checked' : ''}></label></div></div><div class="card"><div class="card-head"><div><h3>내 봇 연결 상태</h3><p>이 계정의 라이선스와 Discord 서버 연결 정보를 확인합니다.</p></div></div><div class="safety-list"><div><span class="status-inline good">●</span><div><b>라이선스에 연결된 Discord ID</b><small>${lic.discordUserId ? esc(lic.discordUserId) : (isOwner() ? '오너 계정' : '오너가 Discord User ID를 등록해야 합니다.')}</small></div></div><div><span class="status-inline ${state.bot?.connected ? 'good' : 'warn'}">●</span><div><b>공용 봇 상태</b><small>${state.bot?.connected ? `${esc(state.bot?.bot?.botUsername || 'NEXIVO HUB Bot')} · 연결됨` : '연결 대기 / 봇 워커가 서버를 확인하는 중입니다.'}</small></div></div><div><span class="status-inline good">●</span><div><b>토큰 보안</b><small>브라우저와 일반 구매자에게 Bot Token을 전달하지 않습니다.</small></div></div>${botCfg.inviteUrl ? `<div><span class="status-inline good">●</span><div><b>봇 초대</b><small><a class="inline-link" href="${esc(botCfg.inviteUrl)}" target="_blank" rel="noreferrer">공용 봇 초대 링크 열기 ↗</a></small></div></div>` : ''}</div></div></div></div>`;
}

function featureReady(view, iconName, title, desc) {
  return `<div class="section first"><div class="feature-ready"><span class="feature-ready-icon">${icon(iconName, 20)}</span><div><span class="eyebrow">${esc(view)}</span><h3>${esc(title)}</h3><p>${esc(desc)}</p></div></div></div>`;
}

function reportsHTML() {
  if (!featureOK('reports')) return featureReady('PRO ONLY', 'lock', '매출 리포트는 Pro 이상에서 사용할 수 있습니다.', '플랜을 업그레이드하면 기간별 매출과 주문 데이터를 자세히 확인할 수 있습니다.');
  const r = state.report || { totalRevenue: 0, completed: 0, totalOrders: state.orders.length, sold: 0, series: [] };
  return `<div class="section first"><div class="section-title"><div><span class="eyebrow">ANALYTICS</span><h2>매출 리포트</h2><p>완료된 주문을 기준으로 매출 흐름을 분석합니다.</p></div><button class="btn" id="refresh-report">${icon('refresh',13)} 새로고침</button></div><div class="report-grid"><div><span>누적 매출</span><b>${money(r.totalRevenue)}</b></div><div><span>완료 주문</span><b>${number(r.completed)}</b></div><div><span>전체 주문</span><b>${number(r.totalOrders)}</b></div><div><span>판매 수량</span><b>${number(r.sold)}</b></div></div><div class="card chart-card"><div class="card-head"><div><h3>최근 ${r.series?.length || 14}일 매출</h3><p>일별 완료 주문 금액</p></div><span class="trend-pill">${icon('chart',12)} ANALYTICS</span></div>${revenueChart(r.series || [], false)}</div><div class="two-col"><div class="card"><div class="card-head"><div><h3>기간 요약</h3><p>현재 데이터에서 바로 계산됩니다.</p></div></div><div class="summary-list"><div><span>평균 주문 금액</span><b>${r.completed ? money(r.totalRevenue / r.completed) : money(0)}</b></div><div><span>주문 완료율</span><b>${r.totalOrders ? Math.round(r.completed / r.totalOrders * 100) : 0}%</b></div><div><span>평균 판매 수량 / 주문</span><b>${r.completed ? (r.sold / r.completed).toFixed(1) : '0.0'}</b></div></div></div><div class="card"><div class="card-head"><div><h3>데이터 기준</h3><p>그래프 수치가 어떻게 계산되는지 안내합니다.</p></div></div><div class="notice-box">${icon('info',15)} 완료 상태의 주문만 매출로 집계합니다. 주문이 추가되면 새로고침 시 그래프와 요약 수치에 반영됩니다.</div></div></div></div>`;
}

function customersHTML() {
  if (!featureOK('customers')) return featureReady('PRO PREMIUM', 'lock', '고객 관리는 Pro Premium 전용입니다.', '업그레이드하면 계정, 라이선스, 등급 정보를 한곳에서 확인할 수 있습니다.');
  const list = state.customers || [];
  return `<div class="section first"><div class="section-title"><div><span class="eyebrow">CUSTOMERS</span><h2>고객 관리</h2><p>연결된 계정과 라이선스 상태를 확인합니다.</p></div><button class="btn" id="refresh-customers">${icon('refresh',13)} 새로고침</button></div><div class="table-wrap"><table><thead><tr><th>아이디</th><th>플랜</th><th>라이선스</th><th>상태</th><th>남은 기간</th></tr></thead><tbody>${list.length ? list.map(c=>`<tr><td><strong>${esc(c.username)}</strong></td><td><span class="plan ${meta(c.plan).accent}">${esc(c.planLabel)}</span></td><td><code>${esc(c.licenseKey || '-')}</code></td><td><span class="status-pill ${statusClass(c.licenseStatus)}">${esc(statusLabel(c.licenseStatus))}</span></td><td>${c.remainingDays == null ? '무기한' : `${number(c.remainingDays)}일`}</td></tr>`).join('') : `<tr><td colspan="5"><div class="empty-state compact"><div class="empty-art">${icon('users',22)}</div><h3>고객이 없습니다.</h3><p>연결된 고객 계정이 생기면 표시됩니다.</p></div></td></tr>`}</tbody></table></div></div>`;
}

function auditHTML() {
  if (!featureOK('audit')) return featureReady('PRO PREMIUM', 'lock', '보안 로그는 Pro Premium 전용입니다.', '운영 변경 이력과 보안 이벤트를 확인하려면 업그레이드가 필요합니다.');
  return `<div class="section first"><div class="section-title"><div><span class="eyebrow">AUDIT TRAIL</span><h2>보안 로그</h2><p>최근 150건의 운영 변경 기록을 확인합니다.</p></div><button class="btn" id="refresh-audit">${icon('refresh',13)} 새로고침</button></div><div class="audit-list">${state.audit.length ? state.audit.map(x=>`<div class="audit-row"><span class="audit-icon">${icon('shield',13)}</span><div><b>${esc(x.action)}</b><small>${esc(x.detail || x.target || '')}</small></div><time>${datetime(x.at)}</time></div>`).join('') : '<div class="empty-state"><div class="empty-art">'+icon('shield',22)+'</div><h3>기록이 없습니다.</h3><p>변경 작업이 발생하면 여기에 쌓입니다.</p></div>'}</div></div>`;
}

function gradesHTML() {
  if (!featureOK('grades')) return featureReady('PRO', 'lock', '등급 관리는 Pro 이상에서 사용할 수 있습니다.', '누적 구매 기준과 고객 등급 데이터를 연결해 관리할 수 있습니다.');
  const total = Math.max(0, state.customers.length || state.orders.length);
  const buckets = [{label:'VIP', value: Math.max(0, Math.round(total*.14))},{label:'GOLD', value: Math.max(0, Math.round(total*.31))},{label:'SILVER', value: Math.max(0,total-Math.round(total*.14)-Math.round(total*.31))}];
  return `<div class="section first"><div class="section-title"><div><span class="eyebrow">CUSTOMER TIERS</span><h2>등급 관리</h2><p>현재 연결 데이터에서 고객 등급을 미리 확인할 수 있습니다.</p></div></div><div class="tier-layout"><div class="card tier-chart"><div class="donut" style="--value:${total?67:0}%"><strong>${number(total)}</strong><span>예상 고객</span></div><div class="tier-legend">${buckets.map((x,i)=>`<div><i class="tier-dot t${i}"></i><span>${x.label}</span><b>${number(x.value)}</b></div>`).join('')}</div></div><div class="card"><div class="card-head"><div><h3>등급 기준</h3><p>고객 누적 구매액 기준 예시</p></div></div><div class="system-list"><div><span>SILVER</span><b>30,000원 이상</b></div><div><span>GOLD</span><b>50,000원 이상</b></div><div><span>VIP</span><b>100,000원 이상</b></div></div></div></div></div>`;
}

function noticeHTML() {
  if (!featureOK('notice')) return featureReady('BASIC PREMIUM', 'lock', '공지 관리는 Basic Premium 이상에서 사용할 수 있습니다.', '스토어 공지를 한곳에서 작성하고 관리할 수 있습니다.');
  return `<div class="section first"><div class="section-title"><div><span class="eyebrow">ANNOUNCEMENTS</span><h2>공지 관리</h2><p>판매자 공지를 준비할 수 있는 공간입니다.</p></div></div><div class="card"><div class="notice-editor"><label>공지 제목<input id="notice-title" placeholder="예: 서버 점검 안내"></label><label>공지 내용<textarea id="notice-body" placeholder="고객에게 보여줄 공지 내용을 입력하세요."></textarea></label><div class="notice-box">${icon('info',15)} 현재 서버에는 공지 저장 API가 비어 있어 이 화면은 UI 프리뷰로 동작합니다.</div></div></div></div>`;
}

function issueLicenseHTML(){
  const maxLevel = meta(currentPlan()).level;
  const options = Object.entries(plans).filter(([,v])=>v.level<=maxLevel);
  const list = state.issuedLicenses || [];
  const active = list.filter(x=>String(x.status)==='ACTIVE').length;
  const unused = list.filter(x=>String(x.status)==='UNUSED').length;
  const exp = list.filter(x=>String(x.status)==='EXPIRED').length;
  return `<div class="section first">
    <div class="section-title"><div><span class="eyebrow">LICENSE CENTER</span><h2>라이선스 발급</h2><p>내 스토어를 사용하는 구매자에게 전달할 라이선스를 발급하고 상태를 관리하세요.</p></div><button class="btn" id="refresh-issued-licenses">${icon('refresh',13)} 새로고침</button></div>
    <div class="license-issue-grid">
      <div class="card issue-builder"><div class="card-head"><div><h3>새 라이선스 발급</h3><p>현재 플랜에서 사용할 수 있는 등급까지 발급할 수 있습니다.</p></div><span class="status-pill ok">${esc(planName(currentPlan()))}</span></div>
        <div class="form-grid">
          <label>플랜<select id="issue-self-plan">${options.map(([k,v])=>`<option value="${k}">${esc(v.label)}</option>`).join('')}</select></label>
          <label>기간<select id="issue-self-duration"><option value="7">7일</option><option value="30" selected>30일</option><option value="90">90일</option><option value="180">180일</option><option value="365">365일</option><option value="0">무기한</option><option value="custom">직접 입력</option></select></label>
          <label id="issue-self-custom-wrap" style="display:none">직접 입력<input id="issue-self-custom" type="number" min="1" max="3650" value="30"></label>
          <label>Discord User ID <input id="issue-self-discord" placeholder="선택"></label>
          <label>주문 ID <input id="issue-self-order" placeholder="선택"></label>
        </div>
        <div class="issue-notice">${icon('shield',13)} 발급된 키는 구매자 계정 활성화에 사용됩니다. 키와 봇 시크릿은 필요한 대상에게만 전달하세요.</div>
        <button class="btn primary full" id="issue-self-license">${icon('plus',14)} 라이선스 발급</button>
        <div id="issue-self-result"></div>
      </div>
      <div class="card issue-summary"><div class="card-head"><div><h3>발급 현황</h3><p>내가 발급한 라이선스만 표시됩니다.</p></div></div>
        <div class="issue-kpis"><div><span>전체</span><b>${number(list.length)}</b></div><div><span>활성</span><b class="good">${number(active)}</b></div><div><span>미사용</span><b>${number(unused)}</b></div><div><span>만료</span><b class="warn">${number(exp)}</b></div></div>
        <div class="issue-side-info"><div>${icon('server',13)} 발급 권한 <b>사용 가능</b></div><div>${icon('shield',13)} 현재 플랜 <b>${esc(planName(currentPlan()))}</b></div><div>${icon('clock',13)} 발급 기간 <b>최대 3650일 / 무기한</b></div></div>
      </div>
    </div>
    <div class="card issued-list-card"><div class="card-head"><div><h3>발급한 라이선스</h3><p>복사, 정지, 연장, 시크릿 재발급, 취소가 가능합니다.</p></div></div><div id="issued-license-list" class="license-list">${renderIssuedLicenseList()}</div></div>
  </div>`;
}

function renderIssuedLicenseList(){
  const list = state.issuedLicenses || [];
  if(!list.length) return `<div class="empty-state compact"><div class="empty-art">${icon('key',22)}</div><h3>아직 발급한 라이선스가 없습니다.</h3><p>왼쪽에서 새 라이선스를 발급하면 이곳에서 관리할 수 있습니다.</p></div>`;
  return list.map(l=>`<div class="license-row issued-row"><div class="lr-head"><div><b>${esc(l.planLabel || planName(l.plan))}</b><span class="status-pill ${statusClass(l.status)}">${esc(statusLabel(l.status))}</span></div><small>${l.remainingDays===null?'무기한':number(l.remainingDays)+'일 남음'}</small></div><code>${esc(l.key)}</code><div class="issued-meta"><span>${l.discordUserId ? `Discord ${esc(l.discordUserId)}` : 'Discord 미연결'}</span><span>${l.orderId ? `주문 ${esc(l.orderId)}` : '주문 미지정'}</span><span>발급 ${date(l.createdAt)}</span></div><div class="license-actions"><button class="btn tiny" data-issue-op="copy" data-id="${esc(l.id)}">${icon('copy',12)} 복사</button>${l.status==='ACTIVE'?`<button class="btn tiny" data-issue-op="suspend" data-id="${esc(l.id)}">정지</button>`:''}${l.status==='SUSPENDED'||l.status==='UNUSED'?`<button class="btn tiny" data-issue-op="resume" data-id="${esc(l.id)}">재개</button>`:''}<button class="btn tiny" data-issue-op="extend" data-id="${esc(l.id)}">연장</button><button class="btn tiny" data-issue-op="rotate-secret" data-id="${esc(l.id)}">시크릿</button>${l.status!=='REVOKED'?`<button class="btn tiny danger" data-issue-op="revoke" data-id="${esc(l.id)}">취소</button>`:''}</div></div>`).join('');
}

async function issueLicenseForCustomer(){
  if (!isOwner()) return toast('라이선스 발급은 오너 전용 기능입니다.','error');
  try{
    const raw=document.getElementById('issue-self-duration')?.value || '30';
    const days=raw==='custom' ? Number(document.getElementById('issue-self-custom')?.value) : Number(raw);
    if(!Number.isInteger(days) || days<0 || days>3650) return toast('기간은 0~3650일 사이의 정수로 입력해주세요.','error');
    const payload={plan:document.getElementById('issue-self-plan')?.value||currentPlan(),durationDays:days,discordUserId:document.getElementById('issue-self-discord')?.value.trim()||null,orderId:document.getElementById('issue-self-order')?.value.trim()||null};
    const out=await api('/api/licenses',{method:'POST',body:JSON.stringify(payload)});
    const l=out.license;
    const result=document.getElementById('issue-self-result');
    if(result) result.innerHTML=`<div class="issue-result issue-result-rich"><div><span>발급 완료</span><code>${esc(l.key)}</code></div><div class="issue-result-actions"><button class="btn tiny" id="copy-issued-key">키 복사</button></div></div>`;
    document.getElementById('copy-issued-key')?.addEventListener('click',async()=>{await navigator.clipboard.writeText(l.key);toast('라이선스 키를 복사했습니다.')});
    await loadIssuedLicenses();
    const list=document.getElementById('issued-license-list'); if(list) list.innerHTML=renderIssuedLicenseList();
    bindIssuedLicenseActions();
    toast('라이선스가 발급되었습니다.');
  }catch(e){ handle(e); }
}

async function refreshIssuedLicenses(){
  try{ await loadIssuedLicenses(); const list=document.getElementById('issued-license-list'); if(list) list.innerHTML=renderIssuedLicenseList(); bindIssuedLicenseActions(); }
  catch(e){ handle(e); }
}
function bindIssuedLicenseActions(){
  document.querySelectorAll('#issued-license-list [data-issue-op]').forEach(b=>b.onclick=async()=>{
    const l=(state.issuedLicenses||[]).find(x=>x.id===b.dataset.id); if(!l)return;
    try{
      if(b.dataset.issueOp==='copy'){ await navigator.clipboard.writeText(l.key); toast('복사했습니다.'); return; }
      let body={};
      if(b.dataset.issueOp==='extend'){ const days=Number(prompt('연장할 일수를 입력하세요','30')); if(!Number.isInteger(days)||days<1) return; body={days}; }
      await api('/api/licenses/'+encodeURIComponent(l.id)+'/'+b.dataset.issueOp,{method:'POST',body:JSON.stringify(body)});
      await refreshIssuedLicenses(); toast('처리가 완료되었습니다.');
    }catch(e){handle(e);}
  });
}

function render() {
  app.innerHTML = state.user ? dashboardHTML() : authHTML();
  bind();
}

function dashboardHTML() {
  return `<div class="app-shell">${sidebarHTML()}<main class="main"><div class="main-inner">${topbarHTML()}<div id="view-root">${viewHTML()}</div></div></main></div>`;
}

function viewHTML() {
  // Prevent a normal purchaser from opening owner-only UI by manually changing state.
  if (state.view === 'issue-license' && !isOwner()) {
    state.view = 'overview';
  }
  switch (state.view) {
    case 'products': return productsHTML();
    case 'orders': return ordersHTML();
    case 'integration': return integrationHTML();
    case 'license': return licenseHTML();
    case 'issue-license': return issueLicenseHTML();
    case 'settings': return settingsHTML();
    case 'notice': return noticeHTML();
    case 'grades': return gradesHTML();
    case 'reports': return reportsHTML();
    case 'customers': return customersHTML();
    case 'audit': return auditHTML();
    default: return overviewHTML();
  }
}


async function productModal(product = null) {
  const editing = Boolean(product);
  const b = document.createElement('div');
  b.className = 'modal-backdrop';
  b.innerHTML = `<div class="modal"><div class="modal-head"><div><span class="eyebrow">${editing ? 'EDIT PRODUCT' : 'NEW PRODUCT'}</span><h3>${editing ? '상품 수정' : '상품 추가'}</h3><p>상품 정보를 저장하면 Discord 봇 동기화에 반영됩니다.</p></div><button class="close" id="modal-close">${icon('close',15)}</button></div><div class="form-grid"><label class="full-row">상품명<input id="pm-name" value="${esc(product?.name || '')}" placeholder="예: 5000 통조림"></label><label>가격<input id="pm-price" type="number" min="0" value="${Number(product?.price || 0)}"></label><label>재고<input id="pm-stock" type="number" value="${product?.stock ?? -1}"></label><label>카테고리<input id="pm-category" value="${esc(product?.category || '')}" placeholder="기본"></label><label class="full-row">설명<textarea id="pm-desc" placeholder="상품 설명">${esc(product?.description || '')}</textarea></label><label class="full-row">특징 <span class="field-hint">한 줄에 하나씩</span><textarea id="pm-features" placeholder="빠른 처리\n자동 동기화">${esc((product?.features || []).join('\n'))}</textarea></label></div><div class="modal-actions"><button class="btn" id="modal-cancel">취소</button><button class="btn primary" id="modal-save">${editing ? '변경사항 저장' : '상품 추가'}</button></div></div>`;
  document.body.appendChild(b);
  const close = () => b.remove();
  b.querySelector('#modal-close').onclick = close; b.querySelector('#modal-cancel').onclick = close;
  b.addEventListener('click', e=>{ if(e.target===b) close(); });
  b.querySelector('#modal-save').onclick = async()=>{
    const payload={name:b.querySelector('#pm-name').value.trim(),price:Number(b.querySelector('#pm-price').value)||0,stock:Math.max(-1,Math.floor(Number(b.querySelector('#pm-stock').value)||0)),category:b.querySelector('#pm-category').value.trim()||'기본',description:b.querySelector('#pm-desc').value.trim(),features:b.querySelector('#pm-features').value.split(/\r?\n/).map(x=>x.trim()).filter(Boolean)};
    if(!payload.name) return toast('상품명을 입력해주세요.','error');
    const btn=b.querySelector('#modal-save'); btn.disabled=true;
    try{ await api(editing?'/api/products/'+encodeURIComponent(product.id):'/api/products',{method:editing?'PATCH':'POST',body:JSON.stringify(payload)}); close(); await loadUserData(); render(); toast(editing?'상품을 수정했습니다.':'상품을 추가했습니다.'); }
    catch(e){ handle(e); } finally{btn.disabled=false;}
  };
}

async function saveSettings(){
  const payload={bankInfo:document.getElementById('set-bank').value, guildId:document.getElementById('set-guild').value.trim(), orderCategoryId:document.getElementById('set-order-cat').value.trim(), logChannelId:document.getElementById('set-log').value.trim(), buyerRoleId:document.getElementById('set-role').value.trim(), orderCategoryName:document.getElementById('set-order-cat-name').value.trim(), stockChannelId:document.getElementById('set-stock-channel')?.value.trim() || '', stockSyncEnabled:document.getElementById('set-stock-sync')?.checked !== false};
  try{state.settings=await api('/api/settings',{method:'PATCH',body:JSON.stringify(payload)});toast('설정을 저장했습니다.')}catch(e){handle(e);}
}

function bind(){
  document.querySelectorAll('[data-mode]').forEach(b => b.onclick = () => { state.mode = b.dataset.mode; render(); });
  document.querySelectorAll('[data-view]').forEach(b => b.onclick = async () => {
    const next = b.dataset.view; if(!next) return;
    if(next === 'issue-license' && !isOwner()) { toast('라이선스 발급은 오너 전용 기능입니다.', 'error'); return; }
    state.view=next; render(); await afterViewLoad();
    if(window.innerWidth<980) document.querySelector('.sidebar')?.classList.remove('open');
  });
  document.getElementById('auth-form')?.addEventListener('submit',async e=>{e.preventDefault();const btn=e.submitter;btn.disabled=true;try{const username=document.getElementById('username').value.trim(),password=document.getElementById('password').value,key=document.getElementById('licenseKey').value.trim();localStorage.setItem('nexivo-hub_remembered_username', username);const data=await api(state.mode==='activate'?'/api/auth/activate':'/api/auth/login',{method:'POST',body:JSON.stringify({username,password,licenseKey:key})});state.user=data.user;state.view='overview';render();toast(state.mode==='activate'?'라이선스가 활성화되었습니다.':'로그인되었습니다.');Promise.all([loadUserData(),(state.view==='overview'&&featureOK('reports'))?loadReport():Promise.resolve()]).then(()=>{render();startRealtime();}).catch(()=>{});}catch(err){if(err.code==='LICENSE_EXPIRED')showExpiry(err.message);else toast(err.message,'error')}finally{btn.disabled=false;}});
  document.getElementById('side-open')?.addEventListener('click',()=>document.querySelector('.sidebar')?.classList.toggle('open'));
  document.getElementById('nav-search')?.addEventListener('input',e=>{const q=e.target.value.toLowerCase();document.querySelectorAll('.nav-item').forEach(n=>n.style.display=n.textContent.toLowerCase().includes(q)?'':'none');});
  document.getElementById('logout')?.addEventListener('click',async()=>{try{await api('/api/auth/logout',{method:'POST'});}catch{} if(state.stream){state.stream.close();state.stream=null;}state.user=null;state.products=[];state.orders=[];state.report=null;render();toast('로그아웃되었습니다.');});
  document.getElementById('refresh-dashboard')?.addEventListener('click',async()=>{await loadUserData();if(featureOK('reports'))await loadReport();render();toast('새로고침했습니다.');});
  document.getElementById('add-product')?.addEventListener('click',()=>productModal());document.getElementById('empty-add')?.addEventListener('click',()=>productModal());
  document.getElementById('refresh-products')?.addEventListener('click',async()=>{await loadUserData();render();toast('상품 정보를 새로고침했습니다.');});
  const rerenderProducts=()=>{const root=document.getElementById('view-root');if(!root)return;root.innerHTML=productsHTML();bind();};
  document.getElementById('product-search')?.addEventListener('input',rerenderProducts);
  document.getElementById('product-category')?.addEventListener('change',rerenderProducts);
  document.getElementById('product-sort')?.addEventListener('change',rerenderProducts);
  document.querySelectorAll('[data-edit]').forEach(b=>b.onclick=()=>productModal(state.products.find(x=>x.id===b.dataset.edit)));
  document.querySelectorAll('[data-delete]').forEach(b=>b.onclick=async()=>{if(!confirm('이 상품을 삭제할까요?'))return;try{await api('/api/products/'+encodeURIComponent(b.dataset.delete),{method:'DELETE'});await loadUserData();render();toast('상품이 삭제되었습니다.');}catch(e){handle(e);}});
  document.querySelectorAll('[data-stock]').forEach(b=>b.onclick=async()=>{const p=state.products.find(x=>x.id===b.dataset.id);if(!p)return;try{await api('/api/products/'+encodeURIComponent(p.id),{method:'PATCH',body:JSON.stringify({stock:Math.max(-1,p.stock+Number(b.dataset.stock))})});await loadUserData();render();toast('재고가 변경되었습니다.');}catch(e){handle(e);}});
  document.querySelectorAll('.order-status').forEach(s=>s.onchange=async()=>{try{await api('/api/orders/'+encodeURIComponent(s.dataset.id),{method:'PATCH',body:JSON.stringify({status:s.value})});await loadUserData();render();toast('주문 상태가 변경되었습니다.');}catch(e){handle(e);}});
  document.getElementById('copy-license')?.addEventListener('click',async()=>{const v=state.user?.licenseKey||state.user?.license?.key||'';if(v){await navigator.clipboard.writeText(v);toast('라이선스 키를 복사했습니다.');}});
  document.getElementById('refresh-bot')?.addEventListener('click',async()=>{await loadBot();render();toast('봇 상태를 확인했습니다.');});
  document.getElementById('connect-bot')?.addEventListener('click',async()=>{
    const guildId=document.getElementById('bot-guild')?.value.trim();
    const stockChannelId=document.getElementById('bot-stock-channel')?.value.trim();
    const stockSyncEnabled=document.getElementById('bot-stock-sync')?.checked !== false;
    const btn=document.getElementById('connect-bot'); if(btn) btn.disabled=true;
    try{
      const d=await api('/api/bot/connect',{method:'POST',body:JSON.stringify({guildId,stockChannelId,stockSyncEnabled})});
      state.bot={...(d.bot||{}),settings:d.settings||state.settings,connected:Boolean(d.connected)};
      state.settings=d.settings||state.settings;
      render();
      toast('Discord 서버 연결 정보가 저장되었습니다. 공용 봇 워커가 연결을 확인합니다.');
    }catch(e){handle(e);}finally{if(btn)btn.disabled=false;}
  });
  document.getElementById('disconnect-bot')?.addEventListener('click',async()=>{
    if(!confirm('Discord 봇 연결을 해제할까요?')) return;
    try{await api('/api/bot/disconnect',{method:'POST'});await loadBot();render();toast('Discord 봇 연결을 해제했습니다.');}catch(e){handle(e);}
  });
  document.getElementById('sync-stock-now')?.addEventListener('click',async()=>{try{const d=await api('/api/bot/sync-stock',{method:'POST'});await loadBot();render();toast(`재고 ${number(d.count||0)}개 동기화를 요청했습니다.`);}catch(e){handle(e);}});
  document.getElementById('copy-bridge-license')?.addEventListener('click',async()=>{const v=state.user?.licenseKey||state.user?.license?.key||'';if(v){await navigator.clipboard.writeText(v);toast('라이선스 키를 복사했습니다.');}});
  document.getElementById('save-settings')?.addEventListener('click',saveSettings);
  document.getElementById('toggle-bot-token')?.addEventListener('click',()=>{
    const input=document.getElementById('set-bot-token'); const btn=document.getElementById('toggle-bot-token'); if(!input||!btn)return;
    input.type=input.type==='password'?'text':'password'; btn.classList.toggle('active',input.type==='text');
  });
  document.getElementById('save-bot-config')?.addEventListener('click',async()=>{
    if(!isOwner()) return;
    const payload={clientId:document.getElementById('set-bot-client')?.value.trim()||'',inviteUrl:document.getElementById('set-bot-invite')?.value.trim()||'',displayName:document.getElementById('set-bot-name')?.value.trim()||'NEXIVO HUB Bot'};
    const token=document.getElementById('set-bot-token')?.value.trim()||''; if(token) payload.botToken=token;
    try{const d=await api('/api/bot/config',{method:'PATCH',body:JSON.stringify(payload)});state.bot={...(state.bot||{}),botConfig:d};render();toast(token?'공용 봇 정보와 Token을 안전하게 저장했습니다.':'공용 봇 정보를 저장했습니다.')}catch(e){handle(e);}
  });
  document.getElementById('refresh-report')?.addEventListener('click',async()=>{await loadReport();render();});
  document.getElementById('issue-self-license')?.addEventListener('click',issueLicenseForCustomer);
  document.getElementById('issue-self-duration')?.addEventListener('change',e=>{const w=document.getElementById('issue-self-custom-wrap');if(w)w.style.display=e.target.value==='custom'?'grid':'none';});
  document.getElementById('refresh-issued-licenses')?.addEventListener('click',refreshIssuedLicenses);
  bindIssuedLicenseActions();
  document.getElementById('refresh-audit')?.addEventListener('click',async()=>{await loadAudit();render();});
  document.getElementById('refresh-customers')?.addEventListener('click',async()=>{await loadCustomers();render();});
  document.getElementById('refresh-orders')?.addEventListener('click',async()=>{await loadUserData();render();toast('주문 정보를 새로고침했습니다.');});
  document.getElementById('duration-preset')?.addEventListener('change',e=>{const wrap=document.getElementById('custom-wrap');if(wrap)wrap.style.display=e.target.value==='custom'?'grid':'none';});
  bindChartTooltips();
}

function bindChartTooltips(){
  const chart=document.querySelector('[data-chart]'); if(!chart) return; const tip=chart.querySelector('#chart-tooltip'); if(!tip) return;
  chart.querySelectorAll('.chart-hit').forEach(hit=>hit.addEventListener('mouseenter',()=>{const i=Number(hit.dataset.index);const data=(state.report?.series||[])[i];if(!data)return;tip.querySelector('b').textContent=money(data.revenue);tip.querySelector('span').textContent=`${shortDate(data.date)} · ${number(data.orders)}건`;tip.style.opacity='1';const x=Number(hit.getAttribute('cx'));const y=Number(hit.getAttribute('cy'));const vb=chart.querySelector('svg').viewBox.baseVal;const rect=chart.querySelector('svg').getBoundingClientRect();const px=(x/vb.width)*rect.width, py=(y/vb.height)*rect.height;tip.style.left=`${Math.min(Math.max(18,px),rect.width-18)}px`;tip.style.top=`${Math.max(6,py-5)}px`;}).addEventListener('mouseleave',()=>tip.style.opacity='0'));
}
function startRealtime(){
  if(state.stream || !state.user) return;
  try{
    const es=new EventSource('/api/stream');
    state.stream=es;
    es.addEventListener('sync',async ev=>{
      try{
        const event=JSON.parse(ev.data||'{}');
        if(!event?.type || event.type === 'bot.inventory_synced') return;
        await loadUserData();
        if(featureOK('reports')) await loadReport();
        render();
      }catch{}
    });
    es.onerror=()=>{};
  }catch{}
}
function stopRealtime(){
  if(state.stream){state.stream.close();state.stream=null;}
}

async function afterViewLoad(){
  if(state.view==='reports') await loadReport();
  if(state.view==='audit') await loadAudit();
  if(state.view==='customers') await loadCustomers();
  if(state.view==='integration' || state.view==='settings') await loadBot();
  if(state.view==='issue-license' && isOwner()) await loadIssuedLicenses();
  if(state.view==='overview' && featureOK('reports')) await loadReport();
  if(state.view==='grades' && featureOK('customers')) await loadCustomers();
  const root=document.getElementById('view-root'); if(root){root.innerHTML=viewHTML();bind();}
}

window.addEventListener('load',async()=>{
  try{
    const d=await api('/api/me');
    state.user=d.user;
    if (state.user?.role === 'OWNER') state.view = 'products';
    render();
    Promise.all([loadUserData(), (state.view==='overview' && featureOK('reports'))?loadReport():Promise.resolve()])
      .then(()=>{render(); startRealtime();})
      .catch(()=>{});
  }catch{
    render();
  }
  setInterval(async()=>{
    if(!state.user||document.hidden) return;
    try{
      await loadBot();
      const badge=document.querySelector('.live-pill');
      if(badge)badge.innerHTML=state.bot?.connected?'<i></i> 실시간 연결':'<i class="off"></i> 연결 대기';
    }catch{}
  },30000);
});
