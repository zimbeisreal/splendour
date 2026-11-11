/* Splendour auth. API contract is identical to the splendour backend:
   POST /api/login   { email_or_phone: string, password: string(4 digits) }
   POST /api/signup  { username: letters, phone: "07XXXXXXXX", pin: string(4 digits), referralCode: string|null, email?: string }
   Same-origin, JSON, session cookie (credentials: include). No tokens or passwords are stored or logged. */
(function () {
  'use strict';
  const API = { login: '/api/login', signup: '/api/signup' };
  const TIMEOUT_MS = 20000;
  const ADMIN_ROLES = ['admin', 'sub_admin', 'super_admin'];
  /* PLACEHOLDER: WhatsApp opens a chat with the company number, not a group. Set real invite URLs here. */
  const LINKS = { whatsapp: 'https://wa.me/256782570103', telegram: '' };
  const MSG = {
    network: 'No internet connection. Check your network.',
    s405: 'This action is not allowed. Refresh the page and try again.',
    s500: 'Something went wrong on our side. Please try again shortly.',
    pin: 'Password must be exactly 4 numbers.'
  };
  const COUNTRIES = [{ c: 'UG', n: 'Uganda', d: '+256' }, { c: 'KE', n: 'Kenya', d: '+254' }, { c: 'TZ', n: 'Tanzania', d: '+255' }];

  const $ = id => document.getElementById(id);
  const app = $('app'), form = $('form'), statusEl = $('status');
  let cur = COUNTRIES[0], mode = 'login', submitting = false;

  /* ---------- UI helpers (textContent only: server text is never parsed as HTML) ---------- */
  function showStatus(text, type) { // type: ok | warn | bad
    statusEl.className = 'status' + (type === 'warn' ? ' warn' : type === 'bad' ? ' bad' : '');
    statusEl.textContent = text;
  }
  function setErr(el, msg) { el.setAttribute('aria-invalid', msg ? 'true' : 'false'); $(el.id + '-e').textContent = msg || ''; }
  function busy(btn, on, label) {
    if (on) { btn.dataset.t = btn.textContent; btn.textContent = label; } else if (btn.dataset.t) btn.textContent = btn.dataset.t;
    btn.disabled = on; submitting = on;
  }
  function serverText(data, keys) {
    for (const k of keys) if (typeof data[k] === 'string' && data[k].trim()) return data[k].trim().slice(0, 200);
    return MSG.s500;
  }

  /* ---------- Login / Register switch: the only thing that shows or hides content ---------- */
  function setMode(m) {
    mode = m; app.dataset.mode = m;
    $('rowPhone').hidden = $('rowEmail').hidden = m !== 'register';
    $('forgot').hidden = m === 'register';
    const reg = $('regBtn'), log = $('loginBtn');
    reg.className = 'btn' + (m === 'register' ? ' primary' : ''); log.className = 'btn' + (m === 'login' ? ' primary' : '');
    reg.type = m === 'register' ? 'submit' : 'button'; log.type = m === 'login' ? 'submit' : 'button';
    $('pass').autocomplete = m === 'register' ? 'new-password' : 'current-password';
    $('userLabel').textContent = m === 'register' ? 'Username' : 'Username or phone';
    if (m === 'register') $('user').value = $('user').value.replace(/[^A-Za-z]/g, '');
    $('modeTitle').textContent = m === 'register' ? 'Create account' : 'Log in';
    ['user', 'phone', 'email', 'pass'].forEach(id => setErr($(id), ''));
    statusEl.textContent = ''; closeList();
  }
  $('regBtn').addEventListener('click', () => { if (mode === 'login') setMode('register'); });
  $('loginBtn').addEventListener('click', () => { if (mode === 'register') setMode('login'); });

  /* ---------- Input filters (same as backend rules) ---------- */
  $('pass').addEventListener('input', e => { e.target.value = e.target.value.replace(/\D/g, ''); });
  $('phone').addEventListener('input', e => { e.target.value = e.target.value.replace(/\D/g, ''); });
  $('user').addEventListener('input', e => { if (mode === 'register') e.target.value = e.target.value.replace(/[^A-Za-z]/g, ''); });
  ['user', 'phone', 'email', 'pass'].forEach(id => $(id).addEventListener('input', function () { setErr(this, ''); }));

  /* Referral code from ?ref=, sent as referralCode (null when absent) */
  const ref = (new URLSearchParams(location.search).get('ref') || '').trim();
  $('regReferral').value = ref;

  /* Phone: backend wants a 10-digit local number "07XXXXXXXX". Country selector is UI only; no country field is sent. */
  function national(v) {
    let d = v.replace(/\D/g, ''); const dial = cur.d.slice(1);
    if (d.indexOf(dial) === 0 && d.length > 9) d = d.slice(dial.length);
    return d.replace(/^0+/, '');
  }

  /* ---------- Network ---------- */
  async function post(url, body) {
    const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), TIMEOUT_MS);
    let res, text;
    try {
      res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify(body), credentials: 'include', cache: 'no-store', signal: ctl.signal });
      text = await res.text();
    } catch (_) { return { network: true }; } finally { clearTimeout(timer); }
    let data = {};
    try { data = JSON.parse(text); } catch (_) { /* HTML or empty body */ }
    if (!data || typeof data !== 'object') data = {};
    return { res, data };
  }

  /* ---------- LOGIN ---------- */
  async function doLogin() {
    const idIn = $('user'), pinIn = $('pass'), btn = $('loginBtn');
    const id = idIn.value.trim(), pin = pinIn.value.trim(), bad = [];
    setErr(idIn, id ? '' : 'Enter your phone number or username.'); if (!id) bad.push(idIn);
    const pinOk = /^\d{4}$/.test(pin); setErr(pinIn, pinOk ? '' : MSG.pin); if (!pinOk) bad.push(pinIn);
    if (bad.length) { bad[0].focus(); return; }

    busy(btn, true, 'Logging in…');
    const r = await post(API.login, { email_or_phone: id, password: pin });
    if (r.network) { busy(btn, false); return showStatus(MSG.network, 'bad'); }
    const { res, data } = r;

    if (res.ok) {
      const role = data.role || (data.user && (data.user.role || data.user.user_role)) || 'user';
      try { /* keys read by the post-login pages */
        sessionStorage.setItem('splendour_just_logged_in', 'true');
        localStorage.setItem('splendour_welcome_seen', 'false');
        localStorage.setItem('userRole', role);
        if (data.user) localStorage.setItem('userData', JSON.stringify(data.user));
      } catch (_) { /* storage unavailable */ }
      showStatus('Welcome To Splendour. Enjoy!', 'ok');
      const admin = ADMIN_ROLES.includes(role);
      return setTimeout(() => location.replace(admin ? '/admin/dashboard' : '/profile?show_welcome=true'), 1000);
    }
    busy(btn, false);
    if (res.status === 401) return setErr(pinIn, 'Wrong password. Try again.');
    if (res.status === 404) return setErr(idIn, 'No account found with that phone or username. Please register first.');
    showStatus(res.status === 405 ? MSG.s405 : res.status >= 500 ? MSG.s500 : serverText(data, ['message', 'error']), 'bad');
  }

  /* ---------- REGISTER ---------- */
  async function doRegister() {
    const uIn = $('user'), eIn = $('email'), phIn = $('phone'), pinIn = $('pass'), btn = $('regBtn');
    const username = uIn.value.trim(), email = eIn.value.trim(), pin = pinIn.value.trim();
    const nat = national(phIn.value), phone = nat ? '0' + nat : '';
    const checks = [
      [uIn, /^[A-Za-z]+$/.test(username), 'Username must use letters only.'],
      [phIn, /^07\d{8}$/.test(phone), 'Phone must be 10 digits starting with 07.'],
      [eIn, !email || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email), 'Email is not valid. Fix it or leave it empty.'],
      [pinIn, /^\d{4}$/.test(pin), MSG.pin]
    ];
    checks.forEach(c => setErr(c[0], c[1] ? '' : c[2]));
    const bad = checks.find(c => !c[1]);
    if (bad) { bad[0].focus(); return; }

    const payload = { username, phone, pin, referralCode: ref || null };
    if (email) payload.email = email;

    busy(btn, true, 'Creating account…');
    const r = await post(API.signup, payload);
    busy(btn, false);
    if (r.network) return showStatus(MSG.network, 'bad');
    const { res, data } = r;

    if (res.status === 201 || res.status === 200) {
      $('user').value = phone; $('pass').value = '';
      showStatus('You have created account sucessfully.', 'ok');
      return setTimeout(() => { setMode('login'); $('pass').focus(); }, 1500);
    }
    showStatus(res.status === 405 ? MSG.s405 : res.status >= 500 ? MSG.s500 : serverText(data, ['error', 'message']), 'bad');
  }

  form.addEventListener('submit', e => { e.preventDefault(); if (submitting) return; statusEl.textContent = ''; mode === 'login' ? doLogin() : doRegister(); });

  /* ---------- Password show/hide, forgot link (placeholder), group links ---------- */
  $('tog').addEventListener('click', function () {
    const show = $('pass').type === 'password'; $('pass').type = show ? 'text' : 'password';
    this.textContent = show ? 'Hide' : 'Show'; this.setAttribute('aria-pressed', show); this.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
  });
  $('forgot').addEventListener('click', e => { e.preventDefault(); showStatus('Password reset is not connected yet.', 'warn'); });
  [['wa', 'whatsapp', 'WhatsApp'], ['tg', 'telegram', 'Telegram']].forEach(x => {
    const a = $(x[0]); if (LINKS[x[1]]) a.href = LINKS[x[1]];
    a.addEventListener('click', e => { if (!LINKS[x[1]]) { e.preventDefault(); showStatus(x[2] + ' group link has not been set yet.', 'warn'); } });
  });

  /* ---------- Country code listbox (UG, KE, TZ) ---------- */
  const cc = $('cc'), list = $('ccList');
  COUNTRIES.forEach((o, i) => {
    const li = document.createElement('li'); li.setAttribute('role', 'option'); li.tabIndex = -1; li.dataset.i = i;
    const a = document.createElement('span'), b = document.createElement('span');
    a.textContent = o.c + ' ' + o.n; b.textContent = o.d; li.append(a, b); list.appendChild(li);
  });
  const items = () => Array.from(list.children);
  function openList() { list.hidden = false; cc.setAttribute('aria-expanded', 'true'); items().forEach((li, i) => li.setAttribute('aria-selected', COUNTRIES[i] === cur)); items()[COUNTRIES.indexOf(cur)].focus(); }
  function closeList() { list.hidden = true; cc.setAttribute('aria-expanded', 'false'); }
  function pick(i) { cur = COUNTRIES[i]; $('ccText').textContent = cur.c + ' ' + cur.d; closeList(); cc.focus(); }
  cc.addEventListener('click', () => list.hidden ? openList() : closeList());
  cc.addEventListener('keydown', e => { if (e.key === 'ArrowDown') { e.preventDefault(); openList(); } });
  list.addEventListener('click', e => { const li = e.target.closest('li'); if (li) pick(+li.dataset.i); });
  list.addEventListener('keydown', e => {
    const els = items(), i = els.indexOf(document.activeElement);
    if (e.key === 'ArrowDown') { e.preventDefault(); els[Math.min(i + 1, els.length - 1)].focus(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); els[Math.max(i - 1, 0)].focus(); }
    else if (e.key === 'Home') { e.preventDefault(); els[0].focus(); }
    else if (e.key === 'End') { e.preventDefault(); els[els.length - 1].focus(); }
    else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(i); }
    else if (e.key === 'Escape' || e.key === 'Tab') { closeList(); cc.focus(); }
  });
  document.addEventListener('click', e => { if (!list.hidden && !e.target.closest('.phone-wrap')) closeList(); });
})();
