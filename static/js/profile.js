/* Splendour profile: Wallet, Deposit, Withdraw.
   The backend decides balances, bonuses and what is withdrawable; this file only displays them.
   The only client-side maths is the withdraw preview (5% fee) and the minimum checks. */
(function () {
  'use strict';
  const DEMO = window.SPLENDOUR_DEMO === true; // set only by the preview build; never true in production

  /* ===== PLACEHOLDERS: replace with the real backend contract (endpoints, field names) ===== */
  /* Real backend routes (payments blueprint):
     POST /payments/initiate   deposit: {payment_type:'deposit', phone:'07XXXXXXXX', amount}  -> {reference, status}
                               invest:  {payment_type:'package', product:<catalog key>, amount, is_locking?, lock_days?}
                                        402 {code:'INSUFFICIENT_FUNDS', required, available, shortfall} = deposit first
     GET  /payments/status/<reference> -> {status: pending|completed|failed}
     POST /payments/withdraw   {phone, amount} -> {success, net_amount, fee, status, withdrawal_id}
   Wallet:  GET /user/profile (actualBalance, welcomeBonus, referralBonus, pending_bonus, packages[], profile details)
            GET /api/user/total-earnings (breakdown.wallet_balance, breakdown.locked_wallet_balance)
   Messages: GET /api/notifications (array, latest 10), PUT /api/notifications/<id>/read */
  /* Team: GET /api/salary (summary + direct referrals by username), GET /api/network/referral-link (referral_code). */
  const API = { profile: '/user/profile', earnings: '/api/user/total-earnings', notes: '/api/notifications', initiate: '/payments/initiate', status: '/payments/status/', withdraw: '/payments/withdraw',
    salary: '/api/salary', link: '/api/network/referral-link' };
  const CAT = window.SPLENDOUR_CATALOG || { plans: [] }; // generated from the backend catalog (js/catalog.js)
  const F = { actual: 'actual_balance', wallet: 'wallet_balance', welcome: 'welcome_bonus', available: 'available_balance',
    referral: 'referral_bonus', locked: 'locked_balance', pending: 'pending_profit', invested: 'has_invested', phone: 'phone' };
  const LOGIN_URL = '/';
  const R = { minDeposit: CAT.minDeposit || 20000, minWithdraw: 3000, minInvest: CAT.minInvest || 20000, fee: 0.10, waitSec: 300, pollMs: 5000 };
  const VIEWS = ['wallet', 'deposit', 'daily', 'lock', 'team', 'profile'];
  const STATS = [['pending', 'Profit on its way', 'Daily profit that is added to your balance 24 hours after it is earned.'],
    ['locked', 'Locked in lock plans', 'Money inside your lock plans. It is released when each plan ends.'],
    ['referral', 'Referral bonus', 'Bonus for the people you invited.'], ['welcome', 'Welcome bonus', 'Can be withdrawn after your first investment.']];

  const $ = id => document.getElementById(id);
  const num = v => Number(v) || 0;
  const fmt = n => 'UGX ' + Math.round(num(n)).toLocaleString('en-US');
  const digits = e => { e.target.value = e.target.value.replace(/\D/g, ''); };
  let W = null, P = null, busy = false, wait = null;

  /* ===== Network (same-origin JSON, session cookie, timeout) ===== */
  const M = { w: { actual_balance: 50000, wallet_balance: 1200000, welcome_bonus: 10000, total_deposits: 1000000, total_earnings: 310000,
    daily_earnings: 120000, lock_earnings: 90000, referral_bonus: 60000, has_invested: false, total_withdrawn: 0, phone: '0782570103' }, p: null,
    n: [{ id: 3, message: 'Team bonus paid: UGX 5,000\n3 more of your friends have invested.\nIt was added to your balance. The next group starts from 0.', is_read: false, created_at: new Date(Date.now() - 3600e3).toISOString().slice(0, 19), notification_type: 'salary' },
      { id: 2, message: 'Plan started: Quartz\nInvested: UGX 20,000\nEarns: UGX 6 a day for 26 days\nFirst profit: after 24 hours\nYour UGX 20,000 returns on day 26.', is_read: true, created_at: new Date(Date.now() - 864e5 * 9).toISOString().slice(0, 19), notification_type: 'package_activation' }] };
  function mock(url, method, b) { // preview only: imitates the real routes
    return new Promise(res => setTimeout(() => {
      if (M.p && !M.p.done && Date.now() > M.p.at) { M.w.actual_balance += M.p.a; M.w.total_deposits += M.p.a; M.p.done = true; }
      const out = (d, st) => res({ res: { ok: (st || 200) < 400, status: st || 200 }, data: d || {} });
      const take = a => { const x = Math.min(a, M.w.actual_balance); M.w.actual_balance -= x; M.w.wallet_balance = Math.max(0, M.w.wallet_balance - (a - x)); };
      if (url === API.profile) return out({ username: 'mukasa_j', phone: M.w.phone, email: 'mukasa@example.com', memberSince: '2026-09-14T09:00:00Z', isVerified: true, referralCode: 'SPL4821',
        actualBalance: M.w.actual_balance, welcomeBonus: M.w.welcome_bonus, referralBonus: M.w.referral_bonus, total_packages: M.w.has_invested ? 1 : 0,
        pending_bonus: { total: 18, count: 3, next_matures_at: null },
        packages: M.w.has_invested ? [{ id: 1, display_name: 'Quartz', name: 'Quartz 20K', amount: 20000, status: 'active', daily_profit: 6, total_returns: 20156, duration_days: 26, days_active: 9, days_remaining: 17, progress: 35, is_locked: false },
          { id: 2, display_name: 'Vault 50K', name: 'Vault 50K', amount: 50000, status: 'active', daily_profit: 0, duration_days: 30, days_active: 12, days_remaining: 18, progress: 40, is_locked: true, lock_end_date: '2026-11-27T09:00:00Z', lock_earnings: 52000 }] : [] });
      if (url === API.earnings) return out({ breakdown: { wallet_balance: String(M.w.wallet_balance), locked_wallet_balance: '72000.00' } });
      if (url === API.notes) return out(M.n);
      if (url.indexOf(API.notes + '/') === 0 && method === 'PUT') { const n = M.n.find(x => url.indexOf('/' + x.id + '/') > 0); if (n) n.is_read = true; return out({ success: true }); }
      if (url === API.link) return out({ success: true, referral_code: 'SPL4821' });
      if (url === API.salary) return out({ success: true, config: { monthly_amount: 10000, monthly_threshold: 250000, group_size: 3, group_amount: 5000 },
        monthly: { qualified: false, direct_active_investment: 140000, threshold: 250000, remaining: 110000, progress_pct: 56, amount: 10000, months_paid: 0, next_pay_at: null, total_paid: 0 },
        team: { active_referrals: 4, total_referrals: 6, group_size: 3, groups_completed: 1, groups_paid: 1, in_progress: 1, needed_for_next: 2, next_reward: 5000, total_paid: 5000 },
        totals: { total_paid: 5000, paid_this_month: 5000, due_now: 0 },
        referrals: [['grace_n', 60000], ['moses256', 40000], ['kato_j', 20000], ['sarah_k', 20000], ['peter_o', 0], ['amina', 0]]
          .map((r, i) => ({ username: r[0], is_active: r[1] > 0, total_invested: r[1], joined_at: '2026-10-' + String(20 - i).padStart(2, '0') + 'T08:00:00Z' })) });
      if (url === API.initiate && b.payment_type === 'deposit') { M.p = { a: b.amount, at: Date.now() + 7000, done: false }; return out({ reference: 'demo-ref', status: 'pending' }); }
      if (url === API.initiate) {
        const have = M.w.actual_balance + M.w.wallet_balance;
        if (have < b.amount) return out({ error: 'Not enough balance. Deposit first, then invest.', code: 'INSUFFICIENT_FUNDS', required: b.amount, available: have, shortfall: b.amount - have }, 402);
        take(b.amount); M.w.has_invested = true; return out({ success: true, status: 'completed' });
      }
      if (url.indexOf(API.status) === 0) return out({ reference: 'demo-ref', status: M.p && M.p.done ? 'completed' : 'pending' });
      if (url === API.withdraw) { take(b.amount); const f = Math.round(b.amount * 0.05); return out({ success: true, net_amount: String(b.amount - f), fee: String(f), status: 'completed' }); }
      out({ error: 'Not found' }, 404);
    }, 300));
  }
  async function call(url, method, body) {
    if (DEMO) return mock(url, method, body);
    const ctl = new AbortController(), t = setTimeout(() => ctl.abort(), 60000); let res, text;
    try {
      res = await fetch(url, { method, headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: body ? JSON.stringify(body) : undefined, credentials: 'include', cache: 'no-store', signal: ctl.signal });
      text = await res.text();
    } catch (_) { return { network: true }; } finally { clearTimeout(t); }
    let data = {}; try { data = JSON.parse(text); } catch (_) { /* not JSON */ }
    return { res, data: data && typeof data === 'object' ? data : {} };
  }
  const srvText = d => { for (const k of ['message', 'error']) if (typeof d[k] === 'string' && d[k].trim()) return d[k].trim().slice(0, 200); return 'Something went wrong on our side. Please try again shortly.'; };
  const NET = 'No internet connection. Check your network.';

  /* ===== UI helpers ===== */
  let tt; function toast(t) { const el = $('toast'); el.textContent = t; el.hidden = false; clearTimeout(tt); tt = setTimeout(() => { el.hidden = true; }, 3200); }
  function setErr(id, m) { $(id).setAttribute('aria-invalid', m ? 'true' : 'false'); $(id + '-e').textContent = m || ''; }
  const avail = w => w[F.available] != null ? num(w[F.available]) : num(w[F.actual]) + num(w[F.wallet]) + num(w[F.welcome]);

  /* ===== Wallet ===== */
  $('stats').append(...STATS.map(s => { const d = document.createElement('div'); d.className = 'card';
    d.innerHTML = '<p class="row"><span></span><b data-k="' + s[0] + '">—</b></p><p class="hint"></p>';
    d.querySelector('span').textContent = s[1]; d.querySelector('.hint').textContent = s[2]; return d; }));
  function render() {
    if (!W) return;
    document.querySelectorAll('[data-k]').forEach(el => { el.textContent = fmt(el.dataset.k === 'available' ? avail(W) : W[F[el.dataset.k]]); });
    const done = [avail(W) > 0 || !!W[F.invested], !!W[F.invested], !!W[F.invested], false];
    document.querySelectorAll('[data-step]').forEach((li, i) => li.classList.toggle('done', done[i]));
    $('startCard').hidden = !!W[F.invested];
    updatePlans();
  }
  async function refresh() {
    const [p, e] = await Promise.all([call(API.profile, 'GET'), call(API.earnings, 'GET')]);
    if (p.network || e.network) return banner(NET);
    if ((p.res.status === 401 || e.res.status === 401) && !DEMO) return location.replace(LOGIN_URL);
    if (!p.res.ok) return banner(srvText(p.data));
    if (!e.res.ok) return banner(srvText(e.data));
    $('banner').hidden = true; P = p.data; W = mapWallet(p.data, e.data); render(); renderProfile(); return W;
  }
  /* Backend numbers only. Welcome bonus comes from the user object (key welcomeBonus). */
  function mapWallet(p, e) {
    const b = e.breakdown || {}, pk = Array.isArray(p.packages) ? p.packages : [];
    return { actual_balance: num(p.actualBalance), wallet_balance: num(b.wallet_balance), welcome_bonus: num(p.welcomeBonus != null ? p.welcomeBonus : p.welcome_bonus),
      referral_bonus: num(p.referralBonus), locked_balance: num(b.locked_wallet_balance), pending_profit: num((p.pending_bonus || {}).total),
      has_invested: num(p.total_packages) > 0 || pk.length > 0, phone: p.phone };
  }
  function banner(t) { $('bannerText').textContent = t; $('banner').hidden = false; }
  $('retry').addEventListener('click', refresh);

  /* ===== Routing (#wallet, #deposit, #daily, #lock, #team, #profile) ===== */
  function route() {
    let h = location.hash.slice(1); if (VIEWS.indexOf(h) < 0) h = 'wallet';
    document.querySelectorAll('[data-view]').forEach(s => { s.hidden = s.id !== 'v-' + h; });
    document.querySelectorAll('[data-nav]').forEach(a => { const on = a.dataset.nav === (h === 'deposit' ? 'wallet' : h); if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
    document.title = 'Splendour | ' + h.charAt(0).toUpperCase() + h.slice(1);
    if (h !== 'deposit') { stopWait(); showIn('form'); }
    $('main').scrollTop = 0; const hd = $('h-' + h); if (hd) hd.focus({ preventScroll: true });
    if (h === 'team') loadTeam();
    if (h === 'profile') { loadNotes(); renderProfile(); }
  }
  window.addEventListener('hashchange', route);

  /* ===== Deposit ===== */
  const tabs = [$('tIn'), $('tMan')], panels = [$('pIn'), $('pMan')];
  function pickTab(i) { tabs.forEach((t, k) => { t.setAttribute('aria-selected', k === i); t.tabIndex = k === i ? 0 : -1; panels[k].hidden = k !== i; }); }
  tabs.forEach((t, i) => { t.addEventListener('click', () => pickTab(i));
    t.addEventListener('keydown', e => { if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { const n = 1 - i; pickTab(n); tabs[n].focus(); } }); });
  ['dPhone', 'dAmt', 'wPhone', 'wAmt'].forEach(id => $(id).addEventListener('input', e => { digits(e); setErr(id, ''); }));

  const showIn = s => { $('inForm').hidden = s !== 'form'; $('inWait').hidden = s !== 'wait'; $('inRes').hidden = s !== 'res'; };
  function result(title, body, primary, onP) {
    $('resT').textContent = title; $('resB').textContent = body; $('resP').textContent = primary; $('resP').onclick = onP;
    $('resS').onclick = () => { location.hash = '#wallet'; }; showIn('res');
  }
  function stopWait() { if (wait) { clearInterval(wait.tick); clearInterval(wait.poll); wait = null; } }
  function startWait(phone, amount, ref) {
    stopWait(); showIn('wait'); $('wApp').classList.remove('done'); $('wBal').classList.remove('done');
    $('waitMsg').textContent = 'We sent a payment prompt to ' + phone + '. Enter your mobile money PIN to approve ' + fmt(amount) + '.';
    const end = Date.now() + R.waitSec * 1000;
    const show = () => { const s = Math.max(0, Math.ceil((end - Date.now()) / 1000)); $('cd').textContent = Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); return s; };
    show(); wait = {};
    wait.tick = setInterval(() => { if (show() === 0) { stopWait(); result('We did not get your approval', 'We waited 5 minutes. If you did approve the prompt, your balance will update once it is confirmed, so check your wallet again soon. If not, you can try again.', 'TRY AGAIN', () => showIn('form')); } }, 1000);
    wait.poll = setInterval(async () => {
      const r = await call(API.status + encodeURIComponent(ref), 'GET'); if (!wait || r.network || !r.res.ok) return;
      const st = String(r.data.status || '').toLowerCase();
      if (st === 'completed') {
        stopWait(); $('wApp').classList.add('done'); $('wBal').classList.add('done'); await refresh();
        result('Deposit successful', fmt(amount) + ' was added to your balance. Now choose a plan and invest.', 'CHOOSE A PLAN', () => { location.hash = '#daily'; });
      } else if (st === 'failed') {
        stopWait(); result('Deposit not completed', 'The payment was declined or cancelled, so nothing was added. Check the number and try again.', 'TRY AGAIN', () => showIn('form'));
      }
    }, R.pollMs);
  }
  $('depForm').addEventListener('submit', async e => {
    e.preventDefault(); if (busy) return; $('dErr').textContent = '';
    const phone = $('dPhone').value.trim(), amount = parseInt($('dAmt').value, 10) || 0;
    const pOk = /^07\d{8}$/.test(phone), aOk = amount >= R.minDeposit;
    setErr('dPhone', pOk ? '' : 'Phone must be 10 digits starting with 07.'); setErr('dAmt', aOk ? '' : 'Minimum deposit is ' + fmt(R.minDeposit) + '.');
    if (!pOk) return $('dPhone').focus(); if (!aOk) return $('dAmt').focus();
    busy = true; $('dBtn').disabled = true; $('dBtn').textContent = 'Sending request…';
    const r = await call(API.initiate, 'POST', { payment_type: 'deposit', phone, amount });
    busy = false; $('dBtn').disabled = false; $('dBtn').textContent = 'CONFIRM DEPOSIT';
    if (r.network) return void ($('dErr').textContent = NET);
    if (!r.res.ok) return void ($('dErr').textContent = r.res.status === 405 ? 'This action is not allowed. Refresh the page and try again.' : srvText(r.data));
    if (!r.data.reference) return void ($('dErr').textContent = 'We could not start the deposit. Please try again.');
    startWait(phone, amount, r.data.reference);
  });
  $('waitClose').addEventListener('click', () => { stopWait(); toast('Your balance updates once the deposit is confirmed.'); location.hash = '#wallet'; showIn('form'); });
  $('copyBtn').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText($('coNum').textContent); toast('Number copied.'); } catch (_) { toast('Press and hold the number to copy it.'); }
  });

  /* ===== Withdraw ===== */
  const dlg = $('wd');
  function preview() {
    const a = parseInt($('wAmt').value, 10) || 0, ok = a >= R.minWithdraw, f = Math.round(a * R.fee);
    $('pA').textContent = ok ? fmt(a) : '—'; $('pF').textContent = ok ? '- ' + fmt(f) : '—'; $('pN').textContent = ok ? fmt(a - f) : '—';
  }
  $('wAmt').addEventListener('input', preview);
  $('openWd').addEventListener('click', () => {
    $('wdForm').hidden = false; $('wdRes').hidden = true; $('wErr').textContent = '';
    if (W && W[F.phone] && !$('wPhone').value) $('wPhone').value = String(W[F.phone]).replace(/\D/g, '').slice(0, 10);
    preview(); dlg.showModal();
  });
  $('wdX').addEventListener('click', () => dlg.close()); $('wrOk').addEventListener('click', () => dlg.close());
  dlg.addEventListener('click', e => { if (e.target === dlg) dlg.close(); });
  $('wForm').addEventListener('submit', async e => {
    e.preventDefault(); if (busy) return; $('wErr').textContent = '';
    const phone = $('wPhone').value.trim(), amount = parseInt($('wAmt').value, 10) || 0;
    const pOk = /^07\d{8}$/.test(phone);
    const aMsg = amount < R.minWithdraw ? 'Minimum withdrawal is ' + fmt(R.minWithdraw) + '.' : (W && amount > avail(W) ? 'That is more than your available balance.' : '');
    setErr('wPhone', pOk ? '' : 'Phone must be 10 digits starting with 07.'); setErr('wAmt', aMsg);
    if (!pOk) return $('wPhone').focus(); if (aMsg) return $('wAmt').focus();
    busy = true; $('wBtn').disabled = true; $('wBtn').textContent = 'Withdrawing…';
    const r = await call(API.withdraw, 'POST', { phone, amount });
    busy = false; $('wBtn').disabled = false; $('wBtn').textContent = 'WITHDRAW';
    if (r.network) return void ($('wErr').textContent = NET);
    if (!r.res.ok) return void ($('wErr').textContent = r.res.status === 405 ? 'This action is not allowed. Refresh the page and try again.' : srvText(r.data));
    const net = num(r.data.net_amount) || amount - Math.round(amount * R.fee), fee = r.data.fee != null ? num(r.data.fee) : amount - net;
    const review = r.data.status === 'pending_admin';
    $('wrT').textContent = review ? 'Withdrawal submitted' : 'Withdrawal sent';
    $('wrB').textContent = (review ? 'Your withdrawal is being reviewed and will be processed shortly. You will receive ' : '') + fmt(net) + (review ? '' : ' is on its way') + ' to ' + phone + '. Fee: ' + fmt(fee) + '. You can see it in Transactions.';
    $('wdForm').hidden = true; $('wdRes').hidden = false; $('wAmt').value = ''; refresh();
  });

  /* ===== Plans. Daily: 0.03% a day for 26 days (profit credited by the backend every 24 hours), amount back on day 26.
     Lock: fixed term, amount + profit paid at maturity. ===== */
  const PD = CAT.plans.filter(p => p.kind === 'daily'), LK = CAT.plans.filter(p => p.kind === 'lock');
  if (!CAT.plans.length) banner('Products could not be loaded. Refresh the page.');
  const gem = i => '<svg viewBox="0 0 100 100" width="' + (34 + i * 3) + '" height="' + (34 + i * 3) + '" aria-hidden="true"><polygon points="50,6 90,38 50,94 10,38" fill="#fff"/><polygon points="50,6 90,38 66,38" fill="#8FB2FF"/><path d="M10 38H90M34 38L50 94L66 38M34 38L50 6L66 38" fill="none" stroke="#4A2C9A" stroke-width="4" stroke-linejoin="round"/></svg>';
  const pad = i => '<svg viewBox="0 0 24 24" width="' + (34 + i * 4) + '" height="' + (34 + i * 4) + '" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/><circle cx="12" cy="15.5" r="1.2" fill="#8FB2FF" stroke="none"/></svg>';
  const SETS = [{ data: PD, list: $('plans'), need: $('needDep'), pic: gem }, { data: LK, list: $('lockPlans'), need: $('needDepLock'), pic: pad }];
  let cur = null;
  const okHint = d => d.kind === 'lock' ? 'Locked for ' + d.days + ' days. You get ' + fmt(d.total) + ' back at the end, ' + fmt(d.profit) + ' profit.' : 'Profit is added every 24 hours. Your ' + fmt(d.amount) + ' comes back as daily profits.';
  SETS.forEach(S => S.data.forEach((d, i) => {
    const lock = d.kind === 'lock', c = document.createElement('article'); c.className = 'plan'; c.dataset.i = i;
    c.innerHTML = '<div class="pic t' + (i % 3) + '">' + S.pic(i) + '</div><div class="pbody"><h3></h3><p class="pl"></p><p class="row"><span></span><b></b></p><p class="row"><span></span><b></b></p><p class="hint ph"></p><button class="btn primary" type="button">INVEST</button></div>';
    const sp = c.querySelectorAll('.row span'), b = c.querySelectorAll('.row b');
    c.querySelector('h3').textContent = d.name; c.querySelector('.pl').textContent = fmt(d.amount) + ' · ' + d.days + ' days';
    sp[0].textContent = lock ? 'Profit' : 'Daily profit'; b[0].textContent = fmt(lock ? d.profit : d.daily);
    sp[1].textContent = lock ? 'Pays at maturity' : 'Total returns'; b[1].textContent = fmt(d.total);
    c.querySelector('button').setAttribute('aria-label', 'Invest ' + fmt(d.amount) + ' in ' + d.name); S.list.appendChild(c);
  }));
  function updatePlans() {
    const have = W ? avail(W) : null;
    SETS.forEach(S => {
      S.need.hidden = !(W && have < S.data[0].amount);
      S.list.querySelectorAll('.plan').forEach(c => {
        const d = S.data[+c.dataset.i], h = c.querySelector('.ph'), low = W && have < d.amount;
        h.classList.toggle('need', !!low);
        h.textContent = low ? 'You need ' + fmt(d.amount - have) + ' more. Tap Invest to deposit first.' : okHint(d);
      });
    });
  }
  SETS.forEach(S => S.list.addEventListener('click', async e => {
    const b = e.target.closest('button'); if (!b) return; const d = S.data[+b.closest('.plan').dataset.i]; cur = d;
    if (!W) await refresh(); if (!W) return toast('We could not load your balance. Check your connection and try again.');
    const have = avail(W);
    if (have < d.amount) { // not enough balance: explain and send to Deposit
      $('dfMsg').textContent = 'To invest in ' + d.name + ' you need more balance than you have now.';
      $('dfA').textContent = fmt(d.amount); $('dfB').textContent = fmt(have); $('dfN').textContent = fmt(d.amount - have); return $('df').showModal();
    }
    const lock = d.kind === 'lock';
    $('ivT').firstChild.textContent = 'Invest in ' + d.name + ' ';
    $('ivA').textContent = fmt(d.amount); $('ivBal').textContent = fmt(have - d.amount); $('ivD').textContent = fmt(d.daily || 0);
    $('ivDRow').hidden = lock; $('ivDur').textContent = d.days + ' days';
    $('ivP').textContent = fmt(d.profit); $('ivT2').textContent = fmt(d.total); $('ivErr').textContent = '';
    $('ivHint').textContent = lock ? 'Your ' + fmt(d.amount) + ' is locked for ' + d.days + ' days. When it ends you get ' + fmt(d.total) + '.'
      : 'Profit is added to your balance every 24 hours. Your ' + fmt(d.amount) + ' is returned on day 26.';
    $('ivForm').hidden = false; $('ivRes').hidden = true; $('iv').showModal();
  }));
  $('dfX').addEventListener('click', () => $('df').close()); $('dfCancel').addEventListener('click', () => $('df').close()); $('dfGo').addEventListener('click', () => $('df').close());
  $('ivX').addEventListener('click', () => $('iv').close()); $('irOk').addEventListener('click', () => $('iv').close());
  [$('df'), $('iv')].forEach(dg => dg.addEventListener('click', e => { if (e.target === dg) dg.close(); }));
  $('ivBtn').addEventListener('click', async () => {
    if (busy || !cur) return; busy = true; $('ivBtn').disabled = true; $('ivBtn').textContent = 'Investing…'; $('ivErr').textContent = '';
    const lock = cur.kind === 'lock', body = { payment_type: 'package', product: cur.key, amount: cur.amount };
    if (lock) { body.is_locking = true; body.lock_days = cur.days; }
    const r = await call(API.initiate, 'POST', body);
    busy = false; $('ivBtn').disabled = false; $('ivBtn').textContent = 'CONFIRM INVESTMENT';
    if (r.network) return void ($('ivErr').textContent = NET);
    if (r.res.status === 402) { // backend says the balance is too low: same Deposit first sheet
      $('iv').close(); $('dfMsg').textContent = 'To invest in ' + cur.name + ' you need more balance than you have now.';
      $('dfA').textContent = fmt(r.data.required || cur.amount); $('dfB').textContent = fmt(r.data.available); $('dfN').textContent = fmt(r.data.shortfall);
      refresh(); return $('df').showModal();
    }
    if (!r.res.ok) return void ($('ivErr').textContent = r.res.status === 405 ? 'This action is not allowed. Refresh the page and try again.' : srvText(r.data));
    $('irT').textContent = 'Investment started';
    $('irB').textContent = lock ? cur.name + ': ' + fmt(cur.amount) + ' is locked for ' + cur.days + ' days. You will receive ' + fmt(cur.total) + ' when it ends.'
      : cur.name + ': ' + fmt(cur.amount) + ' is now earning ' + fmt(cur.daily) + ' a day. Your first profit arrives after 24 hours, and your ' + fmt(cur.amount) + ' returns on day 26.';
    $('ivForm').hidden = true; $('ivRes').hidden = false; refresh();
  });

  /* ===== Team: invite link, monthly salary, team bonus, friends. The backend decides every amount and payment. ===== */
  const T = { link: '', busy: false };
  const dt = s => { const d = s ? new Date(s) : null; return d && !isNaN(d) ? d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'; };
  const tmBanner = t => { $('tmBannerText').textContent = t || ''; $('tmBanner').hidden = !t; };
  async function loadTeam() {
    if (T.busy) return; T.busy = true;
    const [s, l] = await Promise.all([call(API.salary, 'GET'), call(API.link, 'GET')]);
    T.busy = false;
    if (s.network || l.network) return tmBanner(NET);
    if ((s.res.status === 401 || l.res.status === 401) && !DEMO) return location.replace(LOGIN_URL);
    if (l.res.ok && l.data.referral_code) { // the sign-in page reads ?ref= from its own address
      T.link = location.origin + LOGIN_URL.replace(/\/?$/, '/') + '?ref=' + encodeURIComponent(l.data.referral_code);
      $('tmLink').textContent = T.link; $('tmCopy').disabled = false; $('tmShare').disabled = !navigator.share;
    } else { $('tmLink').textContent = 'Your invite link is not ready yet. Try again shortly.'; }
    if (!s.res.ok) return tmBanner(srvText(s.data));
    tmBanner(''); renderTeam(s.data); refresh(); // refresh: salary may have just been added to the balance
  }
  function renderTeam(d) {
    const c = d.config || {}, m = d.monthly || {}, t = d.team || {}, tot = d.totals || {};
    const size = num(t.group_size) || num(c.group_size) || 3, inp = num(t.in_progress), need = num(t.needed_for_next) || size;
    // monthly salary
    $('msAmt').textContent = fmt(m.amount || c.monthly_amount) + ' / month';
    const pct = Math.max(0, Math.min(100, num(m.progress_pct)));
    $('msBar').style.width = pct + '%'; $('msBarWrap').setAttribute('aria-valuenow', Math.round(pct));
    $('msLbl').textContent = fmt(m.direct_active_investment) + ' of ' + fmt(m.threshold || c.monthly_threshold); $('msPct').textContent = Math.round(pct) + '%';
    $('msHint').textContent = m.qualified
      ? 'You earn ' + fmt(m.amount) + ' every month. It is added to your balance automatically.'
      : 'Your friends’ investments add up here. Reach ' + fmt(m.threshold) + ' to unlock ' + fmt(m.amount) + ' every month. ' + fmt(m.remaining) + ' to go.';
    $('msInfo').hidden = !m.qualified; $('msNext').textContent = dt(m.next_pay_at); $('msPaid').textContent = fmt(m.total_paid);
    // team bonus
    $('tbAmt').textContent = fmt(t.next_reward || c.group_amount) + ' per ' + size;
    [...$('tbSteps').children].forEach((li, i) => { li.classList.toggle('on', i < inp); li.textContent = i < inp ? '✓' : String(i + 1); });
    $('tbLbl').textContent = inp + ' of ' + size + ' friends counted';
    $('tbHint').textContent = inp === 0 && num(t.groups_completed) > 0
      ? 'Well done! Your bonus was added. A new group starts now: invite ' + size + ' more friends who invest to earn ' + fmt(t.next_reward) + ' again.'
      : 'Invite ' + need + ' more friend' + (need === 1 ? '' : 's') + ' who ' + (need === 1 ? 'invests' : 'invest') + ' to earn ' + fmt(t.next_reward) + '.';
    $('tbGroups').textContent = String(num(t.groups_paid)); $('tbPaid').textContent = fmt(t.total_paid);
    $('tpAll').textContent = fmt(tot.total_paid); $('tpMonth').textContent = fmt(tot.paid_this_month);
    // friends (usernames only)
    const list = $('tmList'); list.textContent = ''; const rs = Array.isArray(d.referrals) ? d.referrals : [];
    $('tmEmpty').hidden = rs.length > 0;
    rs.forEach(r => {
      const row = document.createElement('div'); row.className = 'fr';
      const a = document.createElement('div'), n = document.createElement('b'), sub = document.createElement('small');
      n.textContent = String(r.username || ''); sub.textContent = 'Joined ' + dt(r.joined_at) + (r.is_active ? ' · invested ' + fmt(r.total_invested) : '');
      a.append(n, sub);
      const chip = document.createElement('span'); chip.className = 'chip' + (r.is_active ? ' on' : ''); chip.textContent = r.is_active ? 'Active' : 'Not yet';
      row.append(a, chip); list.appendChild(row);
    });
  }
  async function copyText(txt) {
    try { await navigator.clipboard.writeText(txt); return true; } catch (_) { /* fall back below */ }
    const ta = document.createElement('textarea'); ta.value = txt; ta.setAttribute('readonly', ''); ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select(); let ok = false; try { ok = document.execCommand('copy'); } catch (_) { /* ignore */ } ta.remove(); return ok;
  }
  $('tmCopy').addEventListener('click', async () => toast(await copyText(T.link) ? 'Link copied. Paste it in WhatsApp or Telegram.' : 'Could not copy. Press and hold the link to copy it.'));
  $('tmShare').addEventListener('click', () => { if (navigator.share) navigator.share({ title: 'Join me on Splendour', text: 'Join me on Splendour and start earning.', url: T.link }).catch(() => {}); });
  $('tmRetry').addEventListener('click', loadTeam);

  /* ===== Profile: account details, active plans, messages ===== */
  const N = { list: null, busy: false };
  const when = iso => { if (!iso) return ''; const d = new Date(/(Z|[+-]\d\d:?\d\d)$/.test(iso) ? iso : iso + 'Z'); if (isNaN(d)) return ''; // server sends UTC without a zone
    const m = Math.round((Date.now() - d) / 60000); if (m < 1) return 'Just now'; if (m < 60) return m + ' min ago'; if (m < 1440) return Math.round(m / 60) + ' h ago';
    if (m < 10080) return Math.round(m / 1440) + ' days ago'; return dt(d.toISOString()); };
  function renderProfile() {
    if (!P) return;
    $('pfName').textContent = String(P.username || ''); $('pfAv').textContent = String(P.username || '?').charAt(0).toUpperCase();
    $('pfPhone').textContent = P.phone || '—'; $('pfEmail').textContent = P.email || 'Not added';
    $('pfSince').textContent = dt(P.memberSince); $('pfCode').textContent = P.referralCode || '—';
    $('pfVer').textContent = P.isVerified ? 'Verified' : 'Not yet verified';
    $('pfVerHint').textContent = P.isVerified ? 'Our team has confirmed your account.' : 'Our team will call you to confirm your account. Keep your phone on.';
    const act = (Array.isArray(P.packages) ? P.packages : []).filter(k => k.status === 'active'), box = $('pfPlans'); box.textContent = '';
    $('pfNoPlans').hidden = act.length > 0;
    act.forEach(k => {
      const c = document.createElement('div'); c.className = 'pl2';
      const h = document.createElement('div'); h.className = 'row'; const n = document.createElement('b'); n.textContent = String(k.display_name || k.name || 'Plan'); const a = document.createElement('span'); a.textContent = fmt(k.amount); h.append(n, a);
      const bar = document.createElement('div'); bar.className = 'bar'; bar.setAttribute('role', 'progressbar'); bar.setAttribute('aria-valuemin', '0'); bar.setAttribute('aria-valuemax', '100');
      const pr = Math.max(0, Math.min(100, num(k.progress))); bar.setAttribute('aria-valuenow', String(pr)); bar.setAttribute('aria-label', 'Progress of ' + (k.display_name || k.name));
      const i = document.createElement('i'); i.style.width = pr + '%'; bar.appendChild(i);
      const d = document.createElement('p'); d.className = 'hint';
      d.textContent = (k.is_locked ? 'Locked until ' + dt(k.lock_end_date) + '. You receive ' + fmt(k.lock_earnings) + '.' : 'Earns ' + fmt(k.daily_profit) + ' a day. Your ' + fmt(k.amount) + ' returns in daily earnings.')
        + ' Day ' + Math.min(num(k.days_active), num(k.duration_days)) + ' of ' + num(k.duration_days) + ', ' + num(k.days_remaining) + ' days left.';
      c.append(h, bar, d); box.appendChild(c);
    });
  }
  function renderNotes() {
    const box = $('pfNotes'); box.textContent = ''; const L = N.list;
    $('pfNoteErr').hidden = L !== null; $('pfNoNotes').hidden = !(L && L.length === 0);
    const unread = L ? L.filter(x => !x.is_read).length : 0; $('navDot').hidden = unread === 0; $('pfUnread').textContent = unread ? unread + ' new' : '';
    (L || []).forEach(x => {
      const b = document.createElement('button'); b.type = 'button'; b.className = 'note' + (x.is_read ? '' : ' new'); b.dataset.id = x.id;
      const lines = String(x.message || '').split('\n'), t = document.createElement('b'), body = document.createElement('span'), tm = document.createElement('small');
      t.textContent = lines[0]; body.textContent = lines.slice(1).join('\n'); tm.textContent = when(x.created_at);
      b.setAttribute('aria-label', (x.is_read ? '' : 'Unread. ') + lines[0] + '. ' + tm.textContent); b.append(t, body, tm); box.appendChild(b);
    });
  }
  async function loadNotes() {
    if (N.busy) return; N.busy = true; const r = await call(API.notes, 'GET'); N.busy = false;
    if (r.network || !r.res.ok || !Array.isArray(r.data)) { if (N.list === null) renderNotes(); return; } N.list = r.data; renderNotes();
  }
  $('pfNotes').addEventListener('click', async e => {
    const b = e.target.closest('.note'); if (!b || !b.classList.contains('new')) return; const n = N.list.find(x => String(x.id) === b.dataset.id); if (!n) return;
    n.is_read = true; renderNotes(); const r = await call(API.notes + '/' + n.id + '/read', 'PUT');
    if (r.network || !r.res.ok) { n.is_read = false; renderNotes(); toast('Could not mark as read. Check your connection.'); }
  });
  $('pfNoteRetry').addEventListener('click', loadNotes);

  route(); refresh(); loadNotes();
})();
