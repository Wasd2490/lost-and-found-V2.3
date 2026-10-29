/**
 * 智慧校园失物登记认领系统 - 公共JS模块
 * 提供：HTTP请求封装、导航栏渲染、HTML转义、状态徽章、时间格式化
 * 所有页面都引入此文件
 */

/** 统一HTTP请求封装：自动序列化JSON、带Cookie、解析错误 */
async function api(url, options = {}) {
  const opts = Object.assign({
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
  }, options);
  if (opts.body && typeof opts.body !== 'string') {
    opts.body = JSON.stringify(opts.body);
  }
  const resp = await fetch(url, opts);
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok && !data.error) {
    data.error = '请求失败 (' + resp.status + ')';
  }
  return data;
}

/** 渲染顶部导航栏：根据登录状态显示不同按钮 */
async function renderNavbar() {
  const navEl = document.getElementById('navbar');
  if (!navEl) return;
  const { user } = await api('/api/me');
  let rightLinks;
  if (user) {
    const adminLink = user.role === 'admin'
      ? '<a href="/admin.html">管理后台</a>' : '';
    rightLinks = `
      <span class="user-info">${escapeHtml(user.real_name || user.username)}</span>
      <a href="/delivery.html">配送追踪</a>
      <a href="/my.html">我的记录</a>
      ${adminLink}
      <a href="#" onclick="doLogout();return false;">退出</a>
    `;
  } else {
    rightLinks = `
      <a href="/login.html">登录</a>
      <a href="/register.html">注册</a>
    `;
  }
  navEl.innerHTML = `
    <div class="container inner">
      <a href="/" class="brand">
        <span class="logo">智</span>
        智慧校园失物登记认领系统
      </a>
      <div class="links">
        <a href="/">首页</a>
        <a href="/post-notice.html">招领启事</a>
        <a href="/post-lost.html">寻物启事</a>
        ${rightLinks}
      </div>
    </div>
  `;
  window.__CURRENT_USER = user;
}

async function doLogout() {
  await api('/api/logout', { method: 'POST' });
  location.href = '/';
}

function escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function statusBadge(status) {
  const map = {
    pending: '<span class="badge pending">待审核</span>',
    approved: '<span class="badge approved">已通过</span>',
    rejected: '<span class="badge rejected">已驳回</span>',
    claimed: '<span class="badge claimed">已完成</span>',
  };
  return map[status] || status;
}

function fmtTime(s) {
  if (!s) return '';
  return String(s).replace('T', ' ').slice(0, 16);
}

const icon = {
  location: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>',
  clock: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
  search: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
  camera: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>',
};

function compressImage(file, maxW = 800, quality = 0.75) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = e => {
      const img = new Image();
      img.onload = () => {
        const w = Math.min(img.width, maxW);
        const h = img.height * (w / img.width);
        const canvas = document.createElement('canvas');
        canvas.width = w; canvas.height = h;
        canvas.getContext('2d').drawImage(img, 0, 0, w, h);
        resolve(canvas.toDataURL('image/jpeg', quality));
      };
      img.onerror = reject;
      img.src = e.target.result;
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

async function uploadImage(dataUrl) {
  const r = await api('/api/upload', { method: 'POST', body: { image: dataUrl } });
  if (r.error) throw new Error(r.error);
  return r.path;
}

document.addEventListener('DOMContentLoaded', renderNavbar);

/* ===================== 以下为 V2 新增：PWA / 通知铃铛 / 手机号脱敏 ===================== */

/** 注册 Service Worker（PWA 离线壳） */
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch((err) => {
      console.warn('[SW] register failed:', err);
    });
  });
}

/**
 * 手机号脱敏：11 位手机号返回前3后4中间****；其他格式返回前2后2中间****。
 * 后端已脱敏，前端列表/管理后台展示时统一再处理一次。
 */
function maskPhone(phone) {
  const s = String(phone == null ? '' : phone).trim();
  if (!s) return '';
  if (/^\d{11}$/.test(s)) return s.slice(0, 3) + '****' + s.slice(-4);
  if (s.length <= 4) return s;
  return s.slice(0, 2) + '****' + s.slice(-2);
}

/* ---------- 通知铃铛 ---------- */
const BELL_ICON = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>';

let __bellPanelEl = null;
let __bellTimer = null;

/** 等待导航栏渲染完成后，把铃铛插到 .links 里（"我的记录"前面） */
function initNotificationBell() {
  // 等 #navbar .links 出现
  const tryInsert = (n) => {
    if (n > 40) return; // 最多 ~4s
    const links = document.querySelector('#navbar .links');
    if (!links || !links.querySelector('a[href="/my.html"]')) {
      setTimeout(() => tryInsert(n + 1), 100);
      return;
    }
    insertBell(links);
    startBellPolling();
  };
  tryInsert(0);
}

function insertBell(linksEl) {
  if (document.getElementById('bell-btn')) return;
  const bell = document.createElement('button');
  bell.type = 'button';
  bell.id = 'bell-btn';
  bell.className = 'bell-btn';
  bell.title = '通知';
  bell.innerHTML = BELL_ICON +
    '<span class="bell-badge" id="bell-badge" style="display:none;">0</span>';
  bell.onclick = (e) => { e.stopPropagation(); toggleBellPanel(); };

  const myLink = linksEl.querySelector('a[href="/my.html"]');
  linksEl.insertBefore(bell, myLink);

  // 全局点击关闭面板
  document.addEventListener('click', (e) => {
    if (__bellPanelEl && !__bellPanelEl.contains(e.target) && e.target.id !== 'bell-btn') {
      hideBellPanel();
    }
  });
}

function toggleBellPanel() {
  if (__bellPanelEl && __bellPanelEl.style.display === 'block') {
    hideBellPanel();
  } else {
    showBellPanel();
  }
}

function hideBellPanel() {
  if (__bellPanelEl) __bellPanelEl.style.display = 'none';
}

function showBellPanel() {
  if (!__bellPanelEl) {
    __bellPanelEl = document.createElement('div');
    __bellPanelEl.id = 'bell-panel';
    __bellPanelEl.className = 'bell-panel';
    document.body.appendChild(__bellPanelEl);
  }
  __bellPanelEl.style.display = 'block';
  __bellPanelEl.innerHTML = '<div style="padding:14px;color:var(--text-secondary);font-size:13px;">加载中...</div>';
  loadBellPanel();
}

async function loadBellPanel() {
  const r = await api('/api/notifications');
  if (!__bellPanelEl) return;
  if (r.error) {
    __bellPanelEl.innerHTML = '<div style="padding:14px;color:var(--text-secondary);font-size:13px;">登录后可查看通知</div>';
    return;
  }
  const list = r.list || [];
  if (!list.length) {
    __bellPanelEl.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-secondary);font-size:13px;">暂无通知</div>';
    return;
  }
  __bellPanelEl.innerHTML = `
    <div class="bell-panel-head">
      <span>通知（未读 ${r.unread_count || 0}）</span>
      <button class="btn small secondary" onclick="markAllRead()">全部标为已读</button>
    </div>
    <div class="bell-panel-body">
      ${list.slice(0, 20).map(n => `
        <div class="bell-item ${n.is_read ? 'read' : ''}">
          <div class="bell-msg">${escapeHtml(n.message || '')}</div>
          <div class="bell-time">${fmtTime(n.created_at || '')}</div>
        </div>
      `).join('')}
    </div>
  `;
}

async function markAllRead() {
  await api('/api/notifications/read-all', { method: 'POST' });
  updateBellBadge(0);
  if (__bellPanelEl) loadBellPanel();
}

function updateBellBadge(n) {
  const badge = document.getElementById('bell-badge');
  if (!badge) return;
  const v = Number(n) || 0;
  if (v > 0) {
    badge.style.display = 'inline-block';
    badge.textContent = v > 99 ? '99+' : String(v);
  } else {
    badge.style.display = 'none';
  }
}

async function pollNotifications() {
  // 未登录时跳过（window.__CURRENT_USER 由 renderNavbar 设置）
  if (!window.__CURRENT_USER) { updateBellBadge(0); return; }
  try {
    const r = await api('/api/notifications');
    if (r && !r.error) updateBellBadge(r.unread_count || 0);
  } catch (e) { /* 静默 */ }
}

function startBellPolling() {
  pollNotifications();
  if (__bellTimer) clearInterval(__bellTimer);
  __bellTimer = setInterval(pollNotifications, 30000);
}

document.addEventListener('DOMContentLoaded', initNotificationBell);
