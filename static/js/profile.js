(function () {
  'use strict';
  const $ = s => document.querySelector(s);
  const ugx = n => Math.round(Number(n) || 0).toLocaleString('en-US');
  const esc = t => String(t == null ? '' : t).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const PHONE = /^07\d{8}$/;
  const LOGIN_URL = '/';
  const LIMITS = { dep: [500, 10000000], wd: [3000, 1000000] };
  const MSG = { net: 'No internet connection. Check your network.', s405: 'This action is not allowed. Refresh the page and try again.',
    s500: 'Something went wrong on our side. Please try again shortly.' };

  // ---- Products (rates: daily 1% per month, fixed once over the term) ----
  const DAILY = [20000, 50000, 100000, 200000, 500000, 800000].map(p => ({ id: 'daily_' + p, kind: 'daily', price: p, profit: p * 0.15, total: p * 0.15 * 14, days: 14, emoji: '📈' }));
  const FIXED = [[50000, 3, 45], [100000, 3, 55], [160000, 6, 65], [300000, 6, 75], [650000, 6, 85]].map(([p, d, r]) =>
    ({ id: 'fixed_' + p + '_' + d, kind: 'fixed', price: p, days: d, rate: r, profit: p * r / 100, total: p + p * r / 100, emoji: '🏛️' }));
  const ALL = DAILY.concat(FIXED);

  let S = { tab: 'daily', user: {}, earn: {}, acts: [] };

  // ---- API ----
  async function call(url, body) {
    const o = { credentials: 'include', headers: { 'X-Requested-With': 'XMLHttpRequest', Accept: 'application/json' } };
    if (body !== undefined) { o.method = 'POST'; o.headers['Content-Type'] = 'application/json'; if (body) o.body = JSON.stringify(body); }
    let res;
    try { res = await fetch(url, o); } catch (_) { return { net: true }; }
    let data = {}; try { data = JSON.parse(await res.text()); } catch (_) {}
    if (res.status === 401) { location.replace(LOGIN_URL); }
    return { res, data };
  }
  const fail = r => r.net ? MSG.net : r.res.status === 405 ? MSG.s405 : r.res.status >= 500 ? MSG.s500
    : (r.data.error || r.data.message || MSG.s500) + (r.data.details ? ' — ' + r.data.details : '');
  const ok = r => !r.net && r.res.ok && r.data.success !== false;

  let tt;
  function toast(t, k) { const e = $('#toast'); e.textContent = t; e.className = 'toast ' + (k || ''); e.hidden = false; clearTimeout(tt); tt = setTimeout(() => e.hidden = true, 3500); }

  async function load() {
    const [p, e, a] = await Promise.all([call('/user/profile'), call('/api/user/total-earnings'), call('/api/recent_activity/user?page=1&page_size=100')]);
    if (ok(p) || (!p.net && p.res.ok)) S.user = p.data; else toast(fail(p), 'bad');
    if (!e.net && e.res.ok) S.earn = e.data;
    if (!a.net && a.res.ok) S.acts = a.data.activities || [];
    $('#hello').textContent = '👋 Hi, ' + (S.user.username || 'there');
    render();
  }

  // ---- Sheet ----
  function sheet(html) { $('#sheet').innerHTML = '<button class="x" id="sx" aria-label="Close">✕</button>' + html; $('#wrap').hidden = false; $('#sx').onclick = close; }
  function close() { $('#wrap').hidden = true; }
  $('#wrap').addEventListener('click', e => { if (e.target.id === 'wrap') close(); });

  function phoneField(btn, err) {
    const i = $('#ph');
    i.addEventListener('input', () => {
      i.value = i.value.replace(/\D/g, '');
      const good = PHONE.test(i.value);
      i.classList.toggle('bad', i.value.length > 0 && !good);
      btn.disabled = !good;
      err.hidden = good || !i.value;
      err.textContent = '⚠️ Phone must be 10 digits starting with 07.';
    });
  }

  // ---- Product ----
  function product(id) {
    const p = ALL.find(x => x.id === id), f = p.kind === 'fixed';
    sheet(`<div class="ph" style="border-radius:14px;height:90px;font-size:42px">${p.emoji}</div>
      <h2>${f ? p.days + ' days · ' + p.rate + '%' : 'Daily earnings'}</h2>
      <div class="row"><span>💰 Invest</span><b>UGX ${ugx(p.price)}</b></div>
      <div class="row"><span>📈 ${f ? 'Profit at maturity' : 'Profit per day'}</span><b class="up">+${ugx(p.profit)}</b></div>
      <div class="row"><span>🏦 ${f ? 'You get back' : 'Total after 14 Days'}</span><b>${ugx(p.total)}</b></div>
      ${f ? '<p class="sm">🔓 Withdrawable after maturity.</p>' : ''}
      <label for="ph">📞 Mobile money number · 07xxxxxxxx</label>
      <input id="ph" type="tel" inputmode="numeric" maxlength="10" placeholder="0771234567" autocomplete="tel">
      <p class="err" id="pe" role="alert" hidden></p>
      <button class="btn" id="pay" disabled>💳 Pay UGX ${ugx(p.price)}</button>`);
    const b = $('#pay'); phoneField(b, $('#pe'));
    b.onclick = async () => {
      const phone = $('#ph').value.trim(); if (!PHONE.test(phone)) return;
      b.disabled = true; b.textContent = '⏳ Sending…';
      const r = await call('/payments/initiate', { product: p.id, amount: p.price, phone, lock_days: p.days,
        is_locking: f, type: f ? 'locking' : 'daily', lock_total: f ? p.total : 0 });

    if (!ok(r)) {
    b.disabled = false;
    b.textContent = '💳 Pay UGX ' + ugx(p.price);
    $('#pe').hidden = false;
    $('#pe').textContent = '⚠️ ' + fail(r);
    return;
  }
      close();
     toast('✅ Payment request sent. Approve it on your phone.', 'ok'); 
       // Internal balance payment = already completed, no poll needed
  if (r.data.status === 'completed') {
    toast('✅ Package purchased.', 'ok');
    load();
    return;
  }   
    // Wait for the webhook to land, then reload once
    //console.log('initiate response:', JSON.stringify(r));
  const status = await waitForPayment(r.data.reference);
  if (status === 'completed') {
    toast('✅ Payment confirmed.', 'ok');
  } else if (status === 'failed') {
    toast('❌ Payment failed or expired.', 'err');
  } else {
    toast('⏱ Still pending — check again in a moment.', 'warn');
  }
  load();                                    // refresh the page data once
};    
//         setTimeout(load, 1500); }
//      else { b.disabled = false; b.textContent = '💳 Pay UGX ' + ugx(p.price); $('#pe').hidden = false; $('#pe').textContent = '⚠️ ' + fail(r); }
    };
   

  // ---- Deposit / Withdraw ----
  function money(kind) {
    const dep = kind === 'dep', [min, max] = LIMITS[kind];
    sheet(`<h2>${dep ? '⬇️ Deposit' : '⬆️ Withdraw'}</h2>
      <label for="am">💰 Amount (UGX) · ${ugx(min)} to ${ugx(max)}</label>
      <input id="am" type="tel" inputmode="numeric" placeholder="${ugx(min)}">
      <label for="ph">📞 ${dep ? 'Number to pay from' : 'Number to receive money'} · 07xxxxxxxx</label>
      <input id="ph" type="tel" inputmode="numeric" maxlength="10" placeholder="0771234567">
      <p class="err" id="pe" role="alert" hidden></p>
      <button class="btn" id="go" disabled>${dep ? 'Pay now' : 'Withdraw now'}</button>`);
    const b = $('#go'), err = $('#pe'), am = $('#am'), ph = $('#ph');
    const check = () => {
      am.value = am.value.replace(/\D/g, ''); ph.value = ph.value.replace(/\D/g, '');
      const n = parseInt(am.value, 10), pg = PHONE.test(ph.value), ag = n >= min && n <= max;
      ph.classList.toggle('bad', ph.value.length > 0 && !pg); am.classList.toggle('bad', am.value.length > 0 && !ag);
      const m = am.value && !ag ? `Amount must be between ${ugx(min)} and ${ugx(max)}.` : ph.value && !pg ? 'Phone must be 10 digits starting with 07.' : '';
      err.hidden = !m; err.textContent = '⚠️ ' + m; b.disabled = !(pg && ag);
    };
    am.oninput = ph.oninput = check;
    b.onclick = async () => {
      const amount = parseInt(am.value, 10), phone = ph.value; b.disabled = true; b.textContent = '⏳ Sending…';
      const r = dep ? await call('/payments/initiate', { payment_type: 'deposit', payment_method: 'mobile', phone, amount,
          reference: 'DEP-' + Date.now().toString(36).toUpperCase(), product: 'deposit', lock_days: 0, is_locking: false })
        : await call('/payments/withdraw', { phone_number: phone, amount });
         if (!ok(r)) {
    b.disabled = false;
    b.textContent = dep ? 'Pay now' : 'Withdraw now';
    err.hidden = false;
    err.textContent = '⚠️ ' + fail(r);
    return;
  }

  close();
  toast(dep ? '✅ Approve the payment on your phone.' : '✅ Withdrawal started.', 'ok');

  if (dep) {
    console.log('initiate response:', JSON.stringify(r));
    const status = await waitForPayment(r.data.reference);
    if (status === 'completed')      toast('✅ Deposit credited.', 'ok');
    else if (status === 'failed')    toast('❌ Deposit failed.', 'err');
    else                             toast('⏱ Still pending — refresh later.', 'warn');
  }

  load();
};
//       if (ok(r)) { close(); toast(dep ? '✅ Approve the payment on your phone.' : '✅ Withdrawal started.', 'ok'); setTimeout(load, 1500); }
//       else { b.disabled = false; b.textContent = dep ? 'Pay now' : 'Withdraw now'; err.hidden = false; err.textContent = '⚠️ ' + fail(r); }
//     };
   }

async function waitForPayment(reference, { timeoutMs = 180000, intervalMs = 3000 } = {}) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    await new Promise(r => setTimeout(r, intervalMs));
    const r = await call('/payments/status/' + encodeURIComponent(reference));
    if (!ok(r)) continue;                        // transient error → retry
    if (r.data.status === 'completed' || r.data.status === 'failed') {
      return r.data.status;
    }
  }
  return 'timeout';
}
  // ---- Lists ----
  const sum = t => S.acts.filter(a => a.type === t).reduce((s, a) => s + Math.abs(Number(a.amount) || 0), 0);
  function history(type, title) {
    const rows = S.acts.filter(a => a.type === type).map(a => `<div class="row"><span>${esc(a.title || title)}<br><span class="sm">${esc(String(a.timestamp || '').slice(0, 10))} · ${esc(a.status || 'completed')}</span></span><b>${ugx(Math.abs(a.amount))}</b></div>`).join('');
    sheet(`<h2>${title}</h2>${rows || '<p class="sm">Nothing here yet.</p>'}`);
  }
  function fixedList() {
    const pk = (S.user.packages || []).filter(p => p.is_locked);
    const rows = pk.map(p => {
      const end = p.lock_end_date ? new Date(p.lock_end_date) : null, mature = end && end <= new Date() && Number(p.lock_earnings) > 0;
      return `<div class="row"><span>UGX ${ugx(p.amount)}<br><span class="sm">Matures ${end ? end.toLocaleDateString('en-GB') : '—'}</span></span>
        ${mature ? `<button class="btn" data-w="${esc(p.id)}" style="min-height:40px">Withdraw ${ugx(p.lock_earnings)}</button>` : '<span class="sm">🔒 Locked</span>'}</div>`;
    }).join('');
    sheet(`<h2>🔒 My fixed investments</h2>${rows || '<p class="sm">No fixed investments yet.</p>'}`);
    document.querySelectorAll('[data-w]').forEach(b => b.onclick = async () => {
      b.disabled = true; const r = await call('/wallet/transfer-locked/' + b.dataset.w, '');
      if (ok(r)) { close(); toast('✅ ' + (r.data.message || 'Moved to your balance.'), 'ok'); setTimeout(load, 800); }
      else { b.disabled = false; toast('⚠️ ' + fail(r), 'bad'); }
    });
  }

  // ---- Tabs ----
  const card = p => `<button class="card pc" data-p="${p.id}"><div class="ph">${p.emoji}</div><div class="in"><span class="big">${ugx(p.price)}</span>
    <span class="up">+${ugx(p.profit)}${p.kind === 'daily' ? ' / day' : ''}</span>${p.kind === 'fixed' ? `<span class="sm">${p.days} days · ${p.rate}%</span>` : '<span class="sm">Earn daily</span>'}</div></button>`;
  const tile = (i, l, v, a) => `<${a ? 'button' : 'div'} class="card tile" ${a ? `data-a="${a}"` : ''}><span class="sm">${i} ${l}</span><span class="big">${v}</span></${a ? 'button' : 'div'}>`;

  function render() {
    const u = S.user, e = S.earn, v = $('#view'), t = S.tab;
    if (t === 'daily') v.innerHTML = '<h2>📈 Daily earnings · 15% per day</h2><div class="grid">' + DAILY.map(card).join('') + '</div>';
    if (t === 'fixed') v.innerHTML = '<h2>🧊 Fixed investments · withdraw after maturity</h2><div class="grid">' + FIXED.map(card).join('') + '</div>';
    if (t === 'account') {
      const fx = (u.packages || []).filter(p => p.is_locked).reduce((s, p) => s + (Number(p.amount) || 0), 0);
      v.innerHTML = `<div class="card hero"><span class="sm">💼 Total available</span><div class="big">UGX ${ugx(u.actualBalance)}</div></div>
      <div class="acts"><button class="btn" data-a="dep">⬇️ Deposit</button><button class="btn alt" data-a="wd">⬆️ Withdraw</button><button class="btn alt" data-a="rech">🔄 Recharge</button></div>
      <div class="grid">${tile('🎁', 'Welcome bonus', ugx(u.bonus))}${tile('🤝', 'Referral bonus', ugx(u.referralBonus))}
      ${tile('📥', 'Total deposited ›', ugx(u.total_deposits != null ? u.total_deposits : sum('deposit')), 'hd')}${tile('📤', 'Total withdrawn ›', ugx(u.total_withdrawals != null ? u.total_withdrawals : sum('withdraw')), 'hw')}
      ${tile('🔒', 'Fixed investments ›', ugx(fx), 'fx')}${tile('💸', 'Daily earnings', ugx((e.lifetime_earnings || {}).total))}
      ${tile('✅', 'Active products', u.active_packages_count || 0)}</div>`;
    }
    if (t === 'network') {
      const r = e.referral_stats || {}, total = r.total_network_size || r.total_direct_referrals || 0, act = r.active_referrals || 0,
        direct = r.direct_referrals_count || r.total_direct_referrals || 0,
        link = u.referralLink || (u.referralCode ? location.origin + '/?ref=' + u.referralCode : ''), q = encodeURIComponent('Join S&S Group: ' + link);
      const rows = S.acts.filter(a => a.type === 'referral').map(a => `<div class="row"><span>${esc(a.title || 'Referral')}<br><span class="sm">${esc(String(a.timestamp || '').slice(0, 10))}</span></span><b class="up">+${ugx(a.amount)}</b></div>`).join('');
      v.innerHTML = `<label for="rl">🔗 Your referral link</label><div class="chips"><input id="rl" readonly value="${esc(link)}" style="flex:3"><button id="cp" style="flex:1">📋 Copy</button></div>
      <div class="soc"><a href="https://wa.me/?text=${q}" target="_blank" rel="noopener" style="background:#25D366">💬 WhatsApp</a><a href="https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent('Join S&S Group')}" target="_blank" rel="noopener" style="background:#229ED9">✈️ Telegram</a></div>
      <div class="grid">${tile('👥', 'Total', total)}${tile('🙋', 'Direct', direct)}${tile('🟢', 'Active', act)}${tile('⚪', 'Inactive', Math.max(0, total - act))}</div>
      <h2 style="margin-top:12px">🧾 Referral earnings</h2><div class="card">${rows || '<span class="sm">No referral earnings yet.</span>'}</div>`;
      $('#cp').onclick = async () => { try { await navigator.clipboard.writeText(link); } catch (_) { $('#rl').select(); document.execCommand('copy'); } toast('✅ Copied!', 'ok'); };
    }
  }

  $('#view').addEventListener('click', e => {
    const p = e.target.closest('[data-p]'), a = e.target.closest('[data-a]');
    if (p) return product(p.dataset.p);
    if (!a) return;
    const k = a.dataset.a;
    if (k === 'dep' || k === 'wd') money(k);
    if (k === 'rech') setTab('daily');
    if (k === 'hd') history('deposit', '📥 Deposits');
    if (k === 'hw') history('withdraw', '📤 Withdrawals');
    if (k === 'fx') fixedList();
  });
  function setTab(t) { S.tab = t; document.querySelectorAll('#nav button').forEach(b => b.classList.toggle('on', b.dataset.tab === t)); render(); $('#view').scrollTop = 0; }
  $('#nav').addEventListener('click', e => { const b = e.target.closest('button'); if (b) setTab(b.dataset.tab); });
  $('#logoutBtn').onclick = async () => { if (!confirm('Logout?')) return; const r = await call('/api/logout', ''); if (!r.net && r.res.ok) location.href = '/'; else toast('⚠️ Logout failed. Try again.', 'bad'); };
  document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });

  render(); load();
})();