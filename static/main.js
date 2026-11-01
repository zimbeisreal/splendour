(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const loginForm = $('loginForm'), registerForm = $('registerForm'), switchRoot = $('pulseSwitch');
  const tabs = document.querySelectorAll('.pulse-switch-btn');
  const MSG = {
    network: 'No internet connection. Check your network.',
    s405: 'This action is not allowed. Refresh the page and try again.',
    s500: 'Something went wrong on our side. Please try again shortly.'
  };

  function showError(el, text, ok) {
    el.textContent = (ok ? '✅ ' : '⚠️ ') + text;
    el.className = 'ss-error' + (ok ? ' ok' : '');
    el.hidden = false;
  }
  const clearError = el => { el.hidden = true; el.textContent = ''; };
  const mark = (input, bad) => input.classList.toggle('bad', !!bad);

  function switchForm(form) {
    tabs.forEach(b => b.classList.toggle('active', b.dataset.form === form));
    switchRoot.dataset.active = form;
    loginForm.classList.toggle('active', form === 'login');
    registerForm.classList.toggle('active', form === 'register');
  }
  tabs.forEach(b => b.addEventListener('click', () => switchForm(b.dataset.form)));

  document.querySelectorAll('.pulse-eye').forEach(btn => btn.addEventListener('click', () => {
    const t = $(btn.dataset.target); const show = t.type === 'password';
    t.type = show ? 'text' : 'password';
    btn.textContent = show ? '🙈' : '👁';
    btn.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
  }));

  $('forgotLink').addEventListener('click', e => e.preventDefault()); // placeholder only

  // Digits only on phone and password fields
  ['regPhone', 'regPin', 'loginPin'].forEach(id =>
    $(id).addEventListener('input', e => { e.target.value = e.target.value.replace(/\D/g, ''); }));
  $('regUsername').addEventListener('input', e => { e.target.value = e.target.value.replace(/[^A-Za-z]/g, ''); });

  // Referral (from ?ref=), read-only
  const ref = (new URLSearchParams(location.search).get('ref') || '').trim();
  $('regReferral').value = ref; $('referralCode').value = ref;
  if (ref) $('skyRefText').textContent = 'Referred by: ' + ref;

  async function post(url, body) {
    let res;
    try {
      res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), credentials: 'include' });
    } catch (_) { return { network: true }; }
    let data = {};
    try { data = JSON.parse(await res.text()); } catch (_) { /* HTML or empty body */ }
    return { res, data };
  }

  function busy(btn, on, label) {
    if (on) { btn.dataset.t = btn.innerHTML; btn.innerHTML = '⏳ ' + label; }
    else btn.innerHTML = btn.dataset.t;
    btn.disabled = on;
  }

  // ---------- LOGIN ----------
  loginForm.addEventListener('submit', async e => {
    e.preventDefault();
    const idIn = $('loginPhone'), pinIn = $('loginPin'), err = $('loginError'), btn = loginForm.querySelector('.pulse-submit');
    const id = idIn.value.trim(), pin = pinIn.value.trim();
    clearError(err); mark(idIn, !id); mark(pinIn, !/^\d{4}$/.test(pin));
    if (!id) return showError(err, 'Enter your phone number or username.');
    if (!/^\d{4}$/.test(pin)) return showError(err, 'Password must be exactly 4 numbers.');

    busy(btn, true, 'Logging in…');
    const r = await post('/api/login', { email_or_phone: id, password: pin });
    if (r.network) { busy(btn, false); return showError(err, MSG.network); }
    const { res, data } = r;

    if (res.ok) {
      const role = data.role || data.user?.role || data.user?.user_role || 'user';
      try {
        sessionStorage.setItem('skyline_just_logged_in', 'true');
        localStorage.setItem('skyline_welcome_seen', 'false');
        localStorage.setItem('userRole', role);
        if (data.user) localStorage.setItem('userData', JSON.stringify(data.user));
      } catch (_) {}
      showError(err, 'Welcome back!', true);
      const admin = ['admin', 'sub_admin', 'super_admin'].includes(role);
      return setTimeout(() => location.replace(admin ? '/admin/dashboard' : '/profile?show_welcome=true'), 1000);
    }
    busy(btn, false);
    const text = res.status === 401 ? 'Wrong password. Try again.'
      : res.status === 404 ? 'No account found with that phone or username. Please register first.'
      : res.status === 405 ? MSG.s405
      : res.status >= 500 ? MSG.s500
      : (data.message || data.error || MSG.s500);
    if (res.status === 401) mark(pinIn, true);
    if (res.status === 404) mark(idIn, true);
    showError(err, text);
  });

  // ---------- REGISTER ----------
  registerForm.addEventListener('submit', async e => {
    e.preventDefault();
    const uIn = $('regUsername'), eIn = $('regEmail'), phIn = $('regPhone'), pinIn = $('regPin');
    const err = $('regError'), btn = registerForm.querySelector('.pulse-submit');
    const username = uIn.value.trim(), email = eIn.value.trim(), phone = phIn.value.trim(), pin = pinIn.value.trim();
    clearError(err);
    const checks = [
      [uIn, /^[A-Za-z]+$/.test(username), 'Username must use letters only.'],
      [eIn, !email || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email), 'Email is not valid. Fix it or leave it empty.'],
      [phIn, /^07\d{8}$/.test(phone), 'Phone must be 10 digits starting with 07.'],
      [pinIn, /^\d{4}$/.test(pin), 'Password must be exactly 4 numbers.']
    ];
    checks.forEach(c => mark(c[0], !c[1]));
    const bad = checks.find(c => !c[1]);
    if (bad) { bad[0].focus(); return showError(err, bad[2]); }

    const payload = { username, phone, pin, referralCode: $('regReferral').value.trim() || null };
    if (email) payload.email = email;

    busy(btn, true, 'Creating account…');
    const r = await post('/api/signup', payload);
    busy(btn, false);
    if (r.network) return showError(err, MSG.network);
    const { res, data } = r;

    if (res.status === 201 || res.status === 200) {
      $('loginPhone').value = phone; $('loginPin').value = '';
      showError(err, 'Account created! Please log in.', true);
      return setTimeout(() => { switchForm('login'); $('loginPin').focus(); }, 1500);
    }
    showError(err, res.status === 405 ? MSG.s405 : res.status >= 500 ? MSG.s500 : (data.error || data.message || MSG.s500));
  });

  switchForm('register');
})();
