/* ============================================================
 * 智能问答 Agent 前端
 * - 原生 fetch + ReadableStream 手写 SSE 解析（EventSource 不支持 POST/Header）
 * - 迷你 Markdown 渲染器（代码块/行内代码/粗斜体/标题/列表）
 * - 深色模式、会话历史、移动端抽屉
 * ============================================================ */

/* ---------- 全局状态 ---------- */
let token = localStorage.getItem('token') || '';
let conversationId = null;
let sending = false;
let welcomeEl = null;   // 欢迎页元素引用，remove 后还能加回来

const $ = id => document.getElementById(id);

/* ---------- 主题 ---------- */
function initTheme() {
  const t = localStorage.getItem('theme') || 'light';
  document.documentElement.dataset.theme = t;
}
function toggleTheme() {
  const cur = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = cur;
  localStorage.setItem('theme', cur);
}

/* ---------- 鉴权请求封装 ---------- */
async function api(path, options = {}) {
  const r = await fetch(path, {
    ...options,
    headers: { 'Authorization': 'Bearer ' + token, ...(options.headers || {}) }
  });
  if (r.status === 401) { doLogout(); throw new Error('登录已过期'); }
  return r;
}

/* ---------- 登录 / 注册 ---------- */
function switchTab(tab) {
  $('tabLogin').classList.toggle('active', tab === 'login');
  $('tabRegister').classList.toggle('active', tab === 'register');
  $('loginForm').style.display = tab === 'login' ? '' : 'none';
  $('registerForm').style.display = tab === 'register' ? '' : 'none';
  $('authErr').textContent = '';
}

async function doLogin() {
  const form = new URLSearchParams();
  form.append('username', $('loginEmail').value.trim());
  form.append('password', $('loginPwd').value);
  try {
    const r = await fetch('/auth/login', { method: 'POST', body: form });
    if (!r.ok) { $('authErr').textContent = '登录失败：邮箱或密码错误'; return; }
    token = (await r.json()).access_token;
    localStorage.setItem('token', token);
    enterApp();
  } catch (e) {
    $('authErr').textContent = '网络异常，请稍后重试';
  }
}

async function doRegister() {
  const body = {
    username: $('regName').value.trim(),
    email: $('regEmail').value.trim(),
    password: $('regPwd').value
  };
  if (!body.username || !body.email || body.password.length < 6) {
    $('authErr').textContent = '请填写完整，密码至少 6 位'; return;
  }
  try {
    const r = await fetch('/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      $('authErr').textContent = '注册失败：' + (d.detail || '请检查输入'); return;
    }
    // 注册成功直接登录
    $('loginEmail').value = body.email;
    $('loginPwd').value = body.password;
    switchTab('login');
    doLogin();
  } catch (e) {
    $('authErr').textContent = '网络异常，请稍后重试';
  }
}

function doLogout() {
  localStorage.removeItem('token');
  location.reload();
}

/* ---------- 进入应用 ---------- */
async function enterApp() {
  $('authView').style.display = 'none';
  $('appView').style.display = 'flex';
  $('userName').textContent = $('loginEmail').value || '用户';
  $('userAvatar').textContent = ($('loginEmail').value[0] || 'U').toUpperCase();
  await loadConvList();
}

/* ---------- 侧边栏会话列表 ---------- */
async function loadConvList() {
  const r = await api('/conversations?page=1&page_size=50');
  const data = await r.json();
  const list = $('convList');
  list.innerHTML = '';
  if (!data.items.length) {
    list.innerHTML = '<div class="conv-empty">暂无历史会话</div>';
    return;
  }
  data.items.forEach(c => {
    const item = document.createElement('div');
    item.className = 'conv-item' + (c.id === conversationId ? ' active' : '');
    item.dataset.id = c.id;
    item.innerHTML =
      '<span class="t">' + escapeHtml(c.title || '新对话') + '</span>' +
      '<span class="ops">' +
      '  <button title="重命名" onclick="event.stopPropagation();renameConv(' + c.id + ')">✏️</button>' +
      '  <button title="删除" onclick="event.stopPropagation();deleteConv(' + c.id + ')">🗑️</button>' +
      '</span>';
    item.onclick = () => selectConv(c.id, c.title);
    list.appendChild(item);
  });
}

async function selectConv(id, title) {
  conversationId = id;
  $('convTitle').textContent = title || '对话';
  document.querySelectorAll('.conv-item').forEach(el =>
    el.classList.toggle('active', +el.dataset.id === id));
  closeSidebar();

  // 加载历史消息
  const r = await api('/conversations/' + id);
  const detail = await r.json();
  $('msgs').innerHTML = '';
  detail.messages.forEach(m => appendMsg(m.role, m.content, true));
  scrollBottom();
}

async function renameConv(id) {
  const title = prompt('新的会话标题：');
  if (!title || !title.trim()) return;
  await api('/conversations/' + id, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title: title.trim() })
  });
  await loadConvList();
  if (id === conversationId) $('convTitle').textContent = title.trim();
}

async function deleteConv(id) {
  if (!confirm('确定删除这个会话？')) return;
  await api('/conversations/' + id, { method: 'DELETE' });
  if (id === conversationId) newChat();
  await loadConvList();
}

function newChat() {
  conversationId = null;
  $('convTitle').textContent = '新对话';
  $('msgs').innerHTML = '';
  if (welcomeEl) { $('msgs').appendChild(welcomeEl); welcomeEl.style.display = ''; }
  document.querySelectorAll('.conv-item').forEach(el => el.classList.remove('active'));
  closeSidebar();
  $('input').focus();
}

function useSuggest(text) {
  $('input').value = text;
  send();
}

/* ---------- 消息渲染 ---------- */
function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/* 迷你 Markdown 渲染器（先转义再渲染，防 XSS） */
function renderMarkdown(src) {
  let html = escapeHtml(src);

  // 代码块 ```...```
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (m, lang, code) =>
    '<pre><code>' + code.replace(/\n$/, '') + '</code></pre>');
  // 行内代码
  html = html.replace(/`([^`\n]+)`/g, '<code>$1</code>');
  // 标题
  html = html.replace(/^### (.*)$/gm, '<h3>$1</h3>')
             .replace(/^## (.*)$/gm, '<h2>$1</h2>')
             .replace(/^# (.*)$/gm, '<h1>$1</h1>');
  // 粗体 / 斜体
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
             .replace(/\*([^*\n]+)\*/g, '<em>$1</em>');

  // 列表：把连续的 - / 1. 行包成 ul/ol
  const lines = html.split('\n');
  let out = [], inUl = false, inOl = false;
  for (const line of lines) {
    if (/^\s*[-*] /.test(line)) {
      if (!inUl) { out.push('<ul>'); inUl = true; }
      out.push('<li>' + line.replace(/^\s*[-*] /, '') + '</li>');
    } else if (/^\s*\d+\. /.test(line)) {
      if (!inOl) { out.push('<ol>'); inOl = true; }
      out.push('<li>' + line.replace(/^\s*\d+\. /, '') + '</li>');
    } else {
      if (inUl) { out.push('</ul>'); inUl = false; }
      if (inOl) { out.push('</ol>'); inOl = false; }
      if (line.trim() === '') continue;
      if (/^<(h\d|pre)/.test(line)) out.push(line);
      else out.push('<p>' + line + '</p>');
    }
  }
  if (inUl) out.push('</ul>');
  if (inOl) out.push('</ol>');
  return out.join('');
}

function appendMsg(role, content, isHistory) {
  if (welcomeEl && welcomeEl.parentNode) welcomeEl.remove();

  const row = document.createElement('div');
  row.className = 'msg-row ' + role;

  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar';
  avatar.textContent = role === 'user' ? '🧑' : '🤖';

  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  if (role === 'assistant') bubble.innerHTML = renderMarkdown(content);
  else bubble.textContent = content;

  row.appendChild(avatar);
  row.appendChild(bubble);
  $('msgs').appendChild(row);
  scrollBottom();
  return bubble;
}

function scrollBottom() {
  const box = $('msgs');
  box.scrollTop = box.scrollHeight;
}

/* ---------- 发送 + SSE 流式解析 ---------- */
async function send() {
  const input = $('input');
  const text = input.value.trim();
  if (!text || sending) return;
  sending = true;
  $('sendBtn').disabled = true;
  input.value = '';
  autoGrow(input);

  appendMsg('user', text);
  const bubble = appendMsg('assistant', '');
  bubble.innerHTML = '<span class="typing"><i></i><i></i><i></i></span>';
  let firstDelta = true;
  let answer = '';

  try {
    const body = { message: text };
    if (conversationId) body.conversation_id = conversationId;

    const resp = await api('/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!resp.ok) {
      bubble.classList.add('error');
      bubble.textContent = '请求失败：HTTP ' + resp.status;
      return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buf = '';
    let isNewConv = !conversationId;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf('\n\n')) >= 0) {
        const raw = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        if (!raw.startsWith('data:')) continue;
        const evt = JSON.parse(raw.slice(5).trim());
        if (evt.type === 'meta') {
          conversationId = evt.conversation_id;
        } else if (evt.type === 'delta') {
          if (firstDelta) { bubble.textContent = ''; firstDelta = false; }
          answer += evt.content;
          bubble.textContent = answer;   // 流式期间纯文本，结束后统一渲染 Markdown
          scrollBottom();
        } else if (evt.type === 'error') {
          bubble.classList.add('error');
          bubble.textContent = '[出错了] ' + evt.message;
        }
      }
    }

    if (firstDelta) bubble.textContent = '（无响应内容）';
    else bubble.innerHTML = renderMarkdown(answer);

    // 新会话：服务端已自动生成标题，刷新侧边栏
    if (isNewConv) loadConvList().then(() => {
      const active = document.querySelector('.conv-item[data-id="' + conversationId + '"]');
      if (active) $('convTitle').textContent = active.querySelector('.t').textContent;
    });
  } catch (e) {
    bubble.classList.add('error');
    bubble.textContent = '[网络异常] 请检查连接后重试';
  } finally {
    sending = false;
    $('sendBtn').disabled = false;
    $('input').focus();
  }
}

/* ---------- 移动端抽屉 ---------- */
function openSidebar() {
  $('sidebar').classList.add('open');
  $('mask').classList.add('show');
}
function closeSidebar() {
  $('sidebar').classList.remove('open');
  $('mask').classList.remove('show');
}

/* ---------- 输入框自适应高度 ---------- */
function autoGrow(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 160) + 'px';
}

/* ---------- 初始化 ---------- */
window.addEventListener('DOMContentLoaded', async () => {
  initTheme();
  welcomeEl = $('welcome');
  const input = $('input');
  input.addEventListener('input', () => autoGrow(input));
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  });

  if (token) {
    // 用已存 token 试探拉会话列表，401 会被 api() 拦截去登录
    try { await enterApp(); } catch (e) { /* token 失效 */ }
  }
  if (!token) $('authView').style.display = 'flex';
});
