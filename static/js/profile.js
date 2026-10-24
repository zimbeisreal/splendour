
console.log('🔵 Profile.js loaded successfully!');
// ============================================================
// PRODUCT DATA
// ============================================================
const PRODUCTS = [
  // ── DAILY (20% per day × 25 days) ──────────────────────────
  { id: 'daily_15k',  name: 'GOLD-Daily Withdraw',  price: 15000,  daily: 3000,  total: 75000,
    daily_rate: 20.0, duration: 25, level: 'Daily', sold: false,
    lock_tiers: [] },
    { id:'daily_30k',  name: 'DIAMOND-Daily Withdraw',  price: 30000,  daily: 6000,  total: 150000,
    daily_rate: 20.0, duration: 25, level: 'Daily', sold: false,
    lock_tiers: [] },
  { id: 'daily_50k',  name: 'PLATINUM-Daily Withdraw',  price: 50000,  daily: 10000,  total: 250000,
    daily_rate: 20.0, duration: 25, level: 'Daily', sold: false,
    lock_tiers: [] },
  { id: 'daily_100k', name: 'BRONZE-Daily Withdraw', price: 100000, daily: 20000, total: 500000,
    daily_rate: 20.0, duration: 25, level: 'Daily', sold: false,
    lock_tiers: [] },
  { id: 'daily_200k', name: 'SILVER-Daily Withdraw', price: 200000, daily: 40000, total: 1000000,
    daily_rate: 20.0, duration: 25, level: 'Daily', sold: false,
    lock_tiers: [] },

  // ── LOCK 1 DAY ─────────────────────────────────────────────
//   { id: 'lock_1d_30k',  name: '1-Day 30K',  price: 30000,  daily: 0, total: 40000,
//     daily_rate: 0, duration: 1,  level: '1-Day', sold: false, lock_days: 1,
//     lock_tiers: [] },

  // ── LOCK 3 DAYS ────────────────────────────────────────────
  { id: 'lock_3d_54k',  name: 'BRONZE-LOCK',  price: 54000,  daily: 0, total: 91500,
    daily_rate: 0, duration: 3,  level: '3-Day', sold: false, lock_days: 3,
    lock_tiers: [] },
  { id: 'lock_3d_100k', name: 'SILVER-LOCK', price: 105000, daily: 0, total: 166000,
    daily_rate: 0, duration: 3,  level: '3-Day', sold: false, lock_days: 3,
    lock_tiers: [] },

  // ── LOCK 7 DAYS ────────────────────────────────────────────
  { id: 'lock_7d_76k',  name: 'GOLD-LOCK',  price: 76000,  daily: 0, total: 156000,
    daily_rate: 0, duration: 7,  level: '7-Day', sold: false, lock_days: 7,
    lock_tiers: [] },
  { id: 'lock_7d_115k', name: 'PLATINUM-LOCK', price: 115000, daily: 0, total: 173000,
    daily_rate: 0, duration: 7,  level: '7-Day', sold: false, lock_days: 7,
    lock_tiers: [] },

  // ── LOCK 14 DAYS ───────────────────────────────────────────
  { id: 'lock_14d_153k', name: 'VIP-LOCK', price: 153000, daily: 0, total: 234000,
    daily_rate: 0, duration: 14, level: '14-Day', sold: false, lock_days: 14,
    lock_tiers: [] }
];
console.log('📦 PRODUCTS loaded:', PRODUCTS.length, 'products');
// ============================================================
// HELPERS
// ============================================================

// ============================================================
// PACKAGE PHOTOS — swap URLs here anytime
// ============================================================
const PACKAGE_PHOTOS = {

};

// Small helper — resolves a product to its photo URL
function getPackagePhoto(productId) {
  return PACKAGE_PHOTOS[productId] || '';
}


function formatCurrency(amount) {
    return parseInt(amount || 0).toLocaleString('en-US');
}

function showToast(message, type = 'info', duration = 8000) {
    const old = document.querySelector('.express-toast');
    if (old) old.remove();

    const toast = document.createElement('div');
    toast.className = `express-toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'expressToastDown 0.3s ease-out';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// ============================================================
// STATE MANAGEMENT
// ============================================================
let currentUserData = null;
let currentState = 'loading';

function detectUserState(userData) {
    const hasPackages = userData.packages && userData.packages.length > 0;
    const hasActivePackage = userData.packages && userData.packages.some(p => p.status === 'active');

    if (!hasPackages) return 'new';
    if (hasActivePackage) return 'active';
    return 'returning';
}

// ============================================================
// LOAD USER DATA
// ============================================================
async function loadUserData() {
    try {
        const response = await fetch('/user/profile', {
            method: 'GET',
            credentials: 'include',
            headers: {
                'Accept': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error('Failed to load profile');
        }

        const data = await response.json();
        currentUserData = data;
        const uidEl = document.getElementById('userId');
if (uidEl && data && (data.id || data.userId || data.user_id)) {
    uidEl.value = data.id || data.userId || data.user_id;
}
        currentState = detectUserState(data);

        return data;
    } catch (error) {
        console.error('Error loading user data:', error);
        showToast('⚠️ Could not load your profile', 'error');
        return null;
    }
}

// ============================================================
// PRODUCT PRESENTATION STATE
// ============================================================
const productState = {
    expandedProducts: {},
    selectedLock: {},
    activeSection: 'daily'
};

// ============================================================
// RENDER FUNCTIONS - Core Profile
// ============================================================

function renderBalances(balances) {
    const totalEl = document.getElementById('actual-balance');
    const availableEl = document.getElementById('locked-balance');
    const walletEl = document.getElementById('wallet-balance');
    const grandTotalEl = document.getElementById('total-balancee');
    //const todayEl = document.getElementById('todayEarnings');

    if (totalEl) totalEl.textContent = formatCurrency(balances.total || 0);
    if (availableEl) availableEl.textContent = `UGX ${formatCurrency(balances.available || 0)}`;
    if (walletEl) walletEl.textContent = `UGX ${formatCurrency(balances.wallet || 0)}`;
    //if (todayEl) todayEl.textContent = `+UGX ${formatCurrency(balances.today || 0)}`;
        if (grandTotalEl) {
        const sum = Number(balances.available || 0) + Number(balances.wallet || 0);
        grandTotalEl.textContent = `UGX ${formatCurrency(sum)}`;
    }
}

function renderUser(user) {
    const usernameEl = document.getElementById('username');
    const phoneEl = document.getElementById('userPhone');

    if (usernameEl) usernameEl.textContent = user.username || 'User';
    if (phoneEl) phoneEl.textContent = user.phone || '07XX XXX XXX';
}

function renderActivePackages(packages, totals) {
    const container = document.getElementById('machinesContainer');
    if (!container) return;

    packages = Array.isArray(packages) ? packages : [];
    totals = totals || {};

    const safeTotals = {
        total_investment: totals.total_investment || packages.reduce((sum, p) => sum + (p.amount || 0), 0),
        total_daily_profit: totals.total_daily_profit || packages.reduce((sum, p) => sum + (p.daily_profit || 0), 0),
        total_packages: totals.total_packages || packages.length,
        locked_count: totals.locked_count || packages.filter(p => p.is_locked).length,
        active_count: totals.active_count || packages.filter(p => p.status === 'active').length,
        locked_daily_profit: totals.locked_daily_profit || packages.filter(p => p.is_locked).reduce((sum, p) => sum + (p.daily_profit || 0), 0),
        unlocked_daily_profit: totals.unlocked_daily_profit || packages.filter(p => !p.is_locked).reduce((sum, p) => sum + (p.daily_profit || 0), 0)
    };

    const statsHTML = `
        <div class="express-package-stats">
            <div class="stat-item">
                <span class="stat-value">${safeTotals.total_packages}</span>
                <span class="stat-label">Active Machines</span>
            </div>
            <div class="stat-item">
                <span class="stat-value gold">UGX ${formatCurrency(safeTotals.total_investment)}</span>
                <span class="stat-label">Total Investment</span>
            </div>
            <div class="stat-item">
                <span class="stat-value green">UGX ${formatCurrency(safeTotals.total_daily_profit)}</span>
                <span class="stat-label">Daily Profit</span>
                <span class="stat-sub" style="font-size:10px;color:#888;">
                     ${formatCurrency(safeTotals.locked_daily_profit)} locked | 
                     ${formatCurrency(safeTotals.unlocked_daily_profit)} unlocked
                </span>
            </div>
            <div class="stat-item">
                <span class="stat-value">${safeTotals.locked_count}/${safeTotals.total_packages}</span>
                <span class="stat-label">Locked Machines</span>
            </div>
        </div>
    `;

    if (packages.length === 0) {
        container.innerHTML = `${statsHTML}<div class="express-empty-state">...</div>`;
        return;
    }

    const cardsHTML = packages.map((pkg, index) => {
        const id = pkg.id || index;
        const name = pkg.display_name || pkg.name || 'Machine';
        const emoji = pkg.emoji || '⚙️';
        const amount = pkg.amount || 0;
        const dailyProfit = pkg.daily_profit || 0;
        const baseDailyProfit = pkg.base_daily_profit || 0;
        const dailyRate = pkg.daily_rate || 0;
        const baseDailyRate = pkg.base_daily_rate || 0;
        const totalProfit = pkg.total_profit || 0;
        const baseTotalProfit = pkg.base_total_profit || 0;
       // const isLocked = pkg.is_locked || false;
        const lockBonusRate = pkg.lock_bonus_rate || 0;
        //const lockDuration = pkg.lock_duration_days || 0;
        const canLock = pkg.can_lock || false;
        const lockBonusTiers = pkg.lock_bonus_tiers || {};

        // const progress = pkg.progress_percentage || 0;
        // const daysActive = pkg.days_active || 0;
        // const daysRemaining = pkg.days_remaining || 0;
        // const durationDays = pkg.duration_days || 26;

        const isLocked = pkg.is_locked || false;              // already defined above in your code
const lockDuration = pkg.lock_duration_days || 0;      // already defined above

// For locked packages, use the lock duration as the effective duration
const effectiveDuration = isLocked && lockDuration > 0
    ? lockDuration
    : (pkg.duration_days || 26);

// Recompute progress against the correct duration
let progress, daysActive, daysRemaining;

if (isLocked && lockDuration > 0 && pkg.activated_at) {
    const activated = new Date(pkg.activated_at);
    const now = new Date();
    daysActive = Math.max(0, Math.floor((now - activated) / (1000 * 60 * 60 * 24)));
    progress = Math.min((daysActive / lockDuration) * 100, 100);
    daysRemaining = Math.max(0, lockDuration - daysActive);
} else {
    progress = pkg.progress_percentage || 0;
    daysActive = pkg.days_active || 0;
    daysRemaining = pkg.days_remaining || 0;
}

const durationDays = effectiveDuration;

        const rateDisplayText = pkg.rate_display_text || `${dailyRate}%`;
        const bonusDisplayText = pkg.bonus_display_text || '';
        const lockBadge = pkg.lock_badge || ` +${lockBonusRate}%`;
        const statusDisplay = pkg.is_locked_display || (isLocked ? ' Locked' : ' Active');
        const referralBonus = pkg.referral_bonus || 0;
        const supportLevel = pkg.support_level || 'Basic';
        const hasBonus = isLocked && lockBonusRate > 0;
        const bonusAmount = hasBonus ? (dailyProfit - baseDailyProfit) : 0;

        return `
            <div class="express-machine-card ${isLocked ? 'locked' : ''}" data-package-id="${id}">
                <div class="express-machine-header">
                    <span class="express-machine-name">
                        <span class="emoji">${emoji}</span>
                        ${name}
                    </span>
                    <span class="express-machine-status ${isLocked ? 'locked' : 'active'}">
                        ${statusDisplay}
                        ${isLocked ? `(${lockDuration}d)` : ''}
                    </span>
                </div>

                <div style="padding:0 16px;margin-top:-4px;font-size:10px;color:#888;">
                    <span style="background:rgba(255,255,255,0.05);padding:2px 10px;border-radius:10px;">
                        ${supportLevel} Support ${referralBonus > 0 ? `• Referral ${referralBonus}%` : ''}
                    </span>
                </div>

<div class="express-machine-details">
    <!-- Investment tile (always) -->
    <div class="express-machine-detail">
        <span class="value gold">UGX ${formatCurrency(amount)}</span>
        <span class="label">Investment</span>
    </div>

    <!-- Daily Profit tile (unlocked only) -->
    ${!isLocked ? `
        <div class="express-machine-detail">
            <span class="value green">UGX ${formatCurrency(dailyProfit)}</span>
            <span class="label">Daily Profit</span>
            ${hasBonus ? `
                <span class="bonus-label" style="font-size:9px;color:#4CAF50;display:block;margin-top:2px;">
                    +${formatCurrency(bonusAmount)} bonus
                </span>
            ` : ''}
            ${bonusDisplayText ? `
                <span class="bonus-label" style="font-size:9px;color:#f5a623;display:block;margin-top:2px;">
                    ${bonusDisplayText}
                </span>
            ` : ''}
        </div>
    ` : ''}

    <!-- Remaining tile (always) -->
    <div class="express-machine-detail">
        <span class="value">${daysRemaining}d</span>
        <span class="label">Remaining</span>
    </div>

    <!-- Total Profit tile (always) -->
    <div class="express-machine-detail">
        <span class="value">UGX ${formatCurrency(totalProfit)}</span>
        <span class="label">Total Profit</span>
        ${hasBonus ? `
            <span style="font-size:9px;color:#888;display:block;">
                Base: UGX ${formatCurrency(baseTotalProfit)}
            </span>
        ` : ''}
    </div>
</div>


       ${!isLocked ? `
    <div class="express-machine-rate-info" style="padding:4px 16px;text-align:center;font-size:12px;border-top:1px solid rgba(255,255,255,0.05);border-bottom:1px solid rgba(255,255,255,0.05);">
        <span style="color:#888;">
            Rate: <span style="color:#fff;font-weight:normal;">
                ${rateDisplayText}
            </span>
        </span>
        ${baseDailyRate > 0 ? `
            <span style="margin-left:8px;font-size:10px;color:#888;">
                Base: ${baseDailyRate}%
            </span>
        ` : ''}
    </div>
` : ''}

                <div class="express-machine-progress" style="padding:8px 16px;">
                    <div class="express-progress-header" style="display:flex;justify-content:space-between;font-size:11px;color:#888;margin-bottom:4px;">
                        <span>Day ${daysActive} of ${durationDays}</span>
                        <span>${Math.round(progress)}%</span>
                    </div>
                    <div class="express-progress-bar" style="height:4px;background:#2a2a2a;border-radius:2px;overflow:hidden;">
                        <div class="express-progress-fill" style="width:${progress}%;height:100%;background:${isLocked ? '#f5a623' : '#4CAF50'};border-radius:2px;transition:width 0.3s;"></div>
                    </div>
                </div>

                ${!isLocked && canLock && Object.keys(lockBonusTiers).length > 0 ? `
                    <div style="padding:4px 16px;font-size:9px;color:#888;display:flex;gap:12px;justify-content:center;border-bottom:1px solid rgba(255,255,255,0.05);">
                        <span>Lock bonuses:</span>
                        ${Object.entries(lockBonusTiers).map(([days, rate]) => `
                            <span style="background:rgba(245,166,35,0.1);padding:1px 6px;border-radius:8px;color:#f5a623;">
                                ${days}d → +${rate}%
                            </span>
                        `).join('')}
                    </div>
                ` : ''}

                ${isLocked && pkg.lock_end_date ? `
    <div class="express-machine-withdraw-info" style="padding:8px 16px;border-top:1px solid rgba(255,255,255,0.05);display:flex;align-items:center;justify-content:space-between;gap:8px;">
        <span style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;">
            Withdraw Date
        </span>
        <span style="font-size:13px;font-weight:700;color:#f5a623;">
            ${formatWithdrawDate(pkg.lock_end_date)}
        </span>
    </div>
` : ''}

                <div class="express-machine-actions" style="display:flex;gap:8px;padding:8px 16px 12px;">
                    ${!isLocked && canLock ? `
                        <button class="express-machine-lock-btn" data-package="${id}" style="flex:1;padding:8px;border:none;border-radius:6px;background:#f5a623;color:#000;font-size:11px;font-weight:bold;cursor:pointer;transition:all 0.2s;">
                            🔒 Lock for ${lockBonusRate || 2}% Bonus
                        </button>
                    ` : ''}
                
${(() => {
    // Not locked → no transfer button (either already transferred, or a daily package)
    if (!isLocked) return '';

    // Lock is active — check whether the lock date has passed
    const lockEnd = pkg.lock_end_date ? new Date(pkg.lock_end_date) : null;
    const isMature = lockEnd && lockEnd <= new Date();
    const earnings = Number(pkg.lock_earnings || 0);

    // Lock still running → show disabled "waiting" button
    if (!isMature) {
        return `
            <button class="express-machine-lock-btn" data-package="${id}" disabled
                style="flex:1;padding:8px;border:none;border-radius:6px;background:rgba(245,166,35,0.15);color:#f5a623;font-size:11px;font-weight:bold;cursor:not-allowed;opacity:0.6;">
                 Transfer on ${formatWithdrawDate(pkg.lock_end_date)}
            </button>
        `;
    }

    // Lock matured → show enabled Transfer button
    if (earnings > 0) {
        return `
            <button class="express-machine-transfer-btn" data-package="${id}"
                style="flex:1;padding:8px;border:none;border-radius:6px;background:#f5a623;color:#000;font-size:11px;font-weight:bold;cursor:pointer;transition:all 0.2s;">
                 Transfer UGX ${formatCurrency(earnings)}
            </button>
        `;
    }

    // Matured but no earnings → nothing to render
    return '';
})()}
                </div>
            </div>
        `;
    }).join('');

    container.innerHTML = statsHTML + cardsHTML;

    document.querySelectorAll('.express-machine-lock-btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const packageId = this.dataset.package;
            const pkg = packages.find(p => p.id == packageId);
            if (pkg && pkg.lock_bonus_tiers) {
                showLockOptions(packageId, pkg.lock_bonus_tiers);
            }
        });
    });

 
document.querySelectorAll('.express-machine-transfer-btn').forEach(btn => {
    btn.addEventListener('click', async function (e) {
        e.stopPropagation();``
        const packageId = this.dataset.package;
        await handlePackageTransfer(packageId, this);
    });
});
    document.querySelectorAll('.express-machine-details-btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const packageId = this.dataset.package;
            const pkg = packages.find(p => p.id == packageId);
            showPackageDetails(pkg);
        });
    });
}

async function handlePackageTransfer(packageId, btn) {
    if (!confirm('Transfer this package\'s payout to your deposit balance?')) return;

    const originalHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = ' Transferring...';

    try {
        const res = await fetch(`/wallet/transfer-locked/${packageId}`, {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            }
        });

        const raw = await res.text();
        let data;
        try { data = JSON.parse(raw); }
        catch { data = { error: 'Transfer failed' }; }

        if (!res.ok || data.success === false) {
            throw new Error(data.error || data.message || 'Transfer failed');
        }

        showToast(` ${data.message || 'Transfer successful'}`, 'success');

        // Reload everything
        setTimeout(() => {
            loadUserData().then(d => {
                if (d) {
                    renderAll(d);
                    renderProducts(PRODUCTS, d);
                }
            });
        }, 500);

    } catch (err) {
        console.error('Package transfer error:', err);
        showToast('⚠️ ' + err.message, 'error');
        btn.disabled = false;
        btn.innerHTML = originalHTML;
    }
}
function formatWithdrawDate(isoDate) {
    if (!isoDate) return '—';
    try {
        const d = new Date(isoDate);
        // Add 1 day buffer
        d.setDate(d.getDate());
        return d.toLocaleDateString('en-GB', {
            day: '2-digit',
            month: 'short',
            year: 'numeric'
        });
    } catch (e) {
        return '—';
    }
}
function showLockOptions(packageId, tiers) {
    const options = Object.entries(tiers)
        .map(([days, rate]) => `${days} days → +${rate}%`)
        .join('\n');
    showToast(`🔒 Lock options for package ${packageId}:\n${options}`, 'info');
}

function handleUnlockPackage(packageId) {
    showToast('🔓 Unlock feature coming soon!', 'info');
}

function showPackageDetails(pkg) {
    if (!pkg) {
        showToast(' Package details coming soon!', 'info');
        return;
    }
    
    const details = `
        📦 Package: ${pkg.name} ${pkg.emoji}
        💰 Investment: UGX ${formatCurrency(pkg.amount)}
        📈 Daily Rate: ${pkg.daily_rate}%
        💵 Daily Profit: UGX ${formatCurrency(pkg.daily_profit)}
        📊 Total Profit: UGX ${formatCurrency(pkg.total_profit)}
        🔄 Total Return: UGX ${formatCurrency(pkg.total_return)}
        ${pkg.is_locked ? `🔒 Locked (${pkg.lock_duration_days}d, +${pkg.lock_bonus_rate}%)` : '🔓 Unlocked'}
        📅 Days Active: ${pkg.days_active}/${pkg.duration_days}
        ⏳ Remaining: ${pkg.days_remaining}d
        ${pkg.referral_bonus ? `🤝 Referral Bonus: ${pkg.referral_bonus}%` : ''}
        🏷️ Support: ${pkg.support_level}
    `;
    showToast(details, 'info');
}

function renderNetwork(network) {
    const totalEl = document.getElementById('totalDownline');
    const activeEl = document.getElementById('activeDownline');
    const level1El = document.getElementById('level1Count');
    const earningsEl = document.getElementById('networkEarnings');

    if (totalEl) totalEl.textContent = network.total || 0;
    if (activeEl) activeEl.textContent = network.active || 0;
    if (level1El) level1El.textContent = network.direct || 0;
    if (earningsEl) earningsEl.textContent = formatCurrency(network.earnings || 0);
}

function renderReferral(referral) {
    const linkEl = document.getElementById('referralLink');
    const totalEl = document.getElementById('totalReferrals');
    const activeEl = document.getElementById('activeReferrals');
    const earningsEl = document.getElementById('referralEarnings');

    if (linkEl) linkEl.value = referral.link || '';
    if (totalEl) totalEl.textContent = referral.total || 0;
    if (activeEl) activeEl.textContent = referral.active || 0;
    if (earningsEl) earningsEl.textContent = formatCurrency(referral.earnings || 0);
}

function renderAccount(user) {
    const phoneEl = document.getElementById('accountPhone');
    const sinceEl = document.getElementById('memberSince');
    const idEl = document.getElementById('userId');
    const codeEl = document.getElementById('userReferralCode');

    if (phoneEl) phoneEl.textContent = user.phone || '—';
    if (sinceEl) sinceEl.textContent = user.memberSince || '—';
    if (idEl) idEl.textContent = user.userId || '—';
    if (codeEl) codeEl.textContent = user.referralCode || '—';
}

// ============================================================
// PRODUCT PRESENTATION - RENDER FUNCTIONS
// ============================================================

function renderProducts(products = PRODUCTS, user = null) {
    const container = document.getElementById('expressProducts');
    if (!container) {
        console.error('❌ Container #expressProducts not found');
        return;
    }
    console.log('🟢 renderProducts function defined');
    console.log('🔄 Rendering products with phone input...');

    const hasPackages = user && user.packages && user.packages.length > 0;
    const purchasedIds = hasPackages ? user.packages.map(p => p.product_id || p.id) : [];

    const html = `
        ${renderIntroduction()}
        ${renderDailySection(products, purchasedIds)}
        ${renderLockingSection(products, purchasedIds)}
    `;

    container.innerHTML = html;

    attachPresentationListeners(products);
    attachProductListeners();
}

function renderIntroduction() {
    return `
        <div class="express-products-intro">
            <h2 class="express-intro-title"> Invest in a Machine</h2>
            <p class="express-intro-desc">
                Choose how you want your machine to earn. Two powerful ways to grow your investment.
            </p>
            
            <div class="express-intro-tabs">
                <button class="express-intro-tab active" data-section="daily">
                    <span class="tab-icon"></span>
                    <span class="tab-label">Daily Withdrawal</span>
                    <span class="tab-sub">6% daily</span>
                </button>
                <button class="express-intro-tab" data-section="locking">
                    <span class="tab-icon"></span>
                    <span class="tab-label">Locking Machines</span>
                    <span class="tab-sub">Higher daily rates</span>
                </button>
            </div>

            <div class="express-intro-info">
                <div class="intro-method daily-active">
                    <h4> Daily Withdrawal</h4>
                    <p>Earn <strong>6% daily</strong> for <strong>26 days</strong>. Withdraw your earnings every day.</p>
                </div>
                <div class="intro-method locking-inactive">
                    <h4> Locking</h4>
                    <p>Lock your machine for a selected period and earn <strong>higher daily rates</strong> up to 14%.</p>
                </div>
            </div>
        </div>
    `;
}

function renderDailySection(products, purchasedIds) {
    const dailyProducts = products.filter(p => !p.sold);
    
    return `
        <section class="express-daily-section" id="dailyMachines">
            <div class="express-section-header">
                <h2 class="express-section-title"> Daily Withdrawal Machines</h2>
                <p class="express-section-desc">
                    Invest in a machine and earn <strong>6% daily</strong> for <strong>26 days</strong>.
                </p>
                <ul class="express-section-features">
                    <li>✅ Earn daily</li>
                    <li>✅ 6% daily rate</li>
                    <li>✅ 26-day earning duration</li>
                    <li>✅ See your expected daily earnings before investing</li>
                </ul>
            </div>
            
            <div class="express-daily-grid">
                ${dailyProducts.map(product => 
                    renderDailyCard(product, purchasedIds)
                ).join('')}
            </div>
        </section>
    `;
}

function renderDailyCard(product, purchasedIds) {
    const isPurchased = purchasedIds.includes(product.id);
    const isSold = product.sold;
    const isExpanded = productState.expandedProducts[product.id] || false;

console.log(`Rendering ${product.name}:`);
console.log(' - product.id:', product.id);
console.log(' - purchasedIds array:', purchasedIds);
console.log(' - isPurchased?', purchasedIds.includes(product.id));
console.log(' - isSold?', product.sold);

    return `
        <div class="express-daily-card ${isPurchased ? 'purchased' : ''} ${isSold ? 'sold' : ''}" 
             data-product-id="${product.id}">
            
            <div class="express-daily-header">
                <span class="daily-emoji">${product.emoji}</span>
                <div class="daily-name-group">
                    <span class="daily-name">${product.name}</span>
                    <span class="daily-level ${product.level.toLowerCase()}">${product.level}</span>
                </div>
            </div>

            <div class="express-daily-investment">
                <span class="investment-label">Investment</span>
                <span class="investment-amount">UGX ${formatCurrency(product.price)}</span>
            </div>

            <div class="express-daily-earnings">
                <span class="earnings-label">Daily Earnings</span>
                <span class="earnings-amount">UGX ${formatCurrency(product.daily)}</span>
                <span class="earnings-rate">6% Daily</span>
            </div>

            <div class="express-daily-meta">
                <div class="meta-item">
                    <span class="meta-label">Duration</span>
                    <span class="meta-value">${product.duration} days</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Expected Total</span>
                    <span class="meta-value gold">UGX ${formatCurrency(product.total)}</span>
                </div>
            </div>

            <div class="express-daily-howto">
                <span class="howto-icon">ℹ️</span>
                <span class="howto-text">
                    Invest once and this machine earns <strong>UGX ${formatCurrency(product.daily)}</strong> daily 
                    for ${product.duration} days.
                </span>
            </div>

            <!-- PHONE INPUT FIELD -->
            ${!isPurchased && !isSold ? `
                <div class="express-daily-phone">
                    <div class="express-phone-wrapper">
                        <span class="express-phone-icon"></span>
                        <input type="tel" 
                               class="express-phone-input" 
                               placeholder="Phone number" 
                               maxlength="15"
                               autocomplete="off"
                               pattern="[0-9+\\s-]+"
                               title="Please enter a valid phone number" />
                    </div>
                    <span class="express-phone-hint">Enter your phone number to receive payment confirmation</span>
                </div>
            ` : ''}

            <button class="express-daily-toggle" data-product="${product.id}" aria-expanded="${isExpanded}">
                <span>${isExpanded ? 'Hide Details' : 'View Full Details'}</span>
                <i class="fas ${isExpanded ? 'fa-chevron-up' : 'fa-chevron-down'}"></i>
            </button>

            <div class="express-daily-details ${isExpanded ? 'expanded' : ''}" id="details-${product.id}">
                <div class="details-grid">
                    <div class="detail-item">
                        <span class="detail-label">Investment</span>
                        <span class="detail-value">UGX ${formatCurrency(product.price)}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Daily Rate</span>
                        <span class="detail-value">${product.daily_rate}%</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Daily Earnings</span>
                        <span class="detail-value gold">UGX ${formatCurrency(product.daily)}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Duration</span>
                        <span class="detail-value">${product.duration} days</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Total Profit</span>
                        <span class="detail-value green">UGX ${formatCurrency(product.total - product.price)}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Total Return</span>
                        <span class="detail-value gold">UGX ${formatCurrency(product.total)}</span>
                    </div>
                    ${product.level ? `
                        <div class="detail-item">
                            <span class="detail-label">Support Level</span>
                            <span class="detail-value">${product.level}</span>
                        </div>
                    ` : ''}
                </div>
            </div>

            <div class="express-daily-actions">
                ${!isPurchased && !isSold ? `
                    <button class="express-product-buy-btn" 
                            data-product="${product.id}" 
                            data-price="${product.price}" 
                            data-days="0"
                            data-type="daily">
                         Invest in ${product.name}
                    </button>
                ` : isPurchased ? `
                    <button class="express-product-details-btn" data-product="${product.id}">
                         View Your Machine
                    </button>
                ` : `
                    <span class="express-sold-badge">❌ Sold Out</span>
                `}
            </div>
        </div>
    `;
}

function renderLockingSection(products, purchasedIds) {
    const lockingProducts = products.filter(p => !p.sold);
    
    return `
        <section class="express-locking-section" id="lockingMachines">
            <div class="express-section-header locking">
                <h2 class="express-section-title">Locking Machines</h2>
                <p class="express-section-desc">
                    Lock your machine for a selected period to earn a <strong>higher daily rate</strong>.
                </p>
                <p class="express-section-desc-small">
                    The longer you lock, the higher your daily earnings.
                </p>
                
                <div class="express-locking-process">
                    <span class="process-step">1️⃣ Choose a machine</span>
                    <span class="process-arrow">→</span>
                    <span class="process-step">2️⃣ Choose lock duration</span>
                    <span class="process-arrow">→</span>
                    <span class="process-step">3️⃣ See exact daily earnings</span>
                    <span class="process-arrow">→</span>
                    <span class="process-step">4️⃣ Invest</span>
                </div>
            </div>

            <div class="express-locking-rate-guide">
                <h3 class="guide-title">📊 Locking Rate Guide</h3>
                <div class="guide-grid">
                    <div class="guide-item">
                        <span class="guide-duration">7 Days</span>
                        <span class="guide-label">Short Lock</span>
                        <span class="guide-rate">8% Daily</span>
                    </div>
                    <div class="guide-item">
                        <span class="guide-duration">14 Days</span>
                        <span class="guide-label">Extended Lock</span>
                        <span class="guide-rate">10% Daily</span>
                    </div>
                    <div class="guide-item">
                        <span class="guide-duration">28 Days</span>
                        <span class="guide-label">Long-Term Lock</span>
                        <span class="guide-rate">12% Daily</span>
                    </div>
                    <div class="guide-item">
                        <span class="guide-duration">56 Days</span>
                        <span class="guide-label">Maximum Lock</span>
                        <span class="guide-rate">14% Daily</span>
                    </div>
                </div>
            </div>

            <div class="express-locking-grid">
                ${lockingProducts.map(product => 
                    renderLockingCard(product, purchasedIds)
                ).join('')}
            </div>
        </section>
    `;
}

function renderLockingCard(product, purchasedIds) {
    const isPurchased = purchasedIds.includes(product.id);
    const isSold = product.sold;
    const selectedDuration = productState.selectedLock[product.id] || null;

console.log(`Rendering ${product.name}:`);
console.log(' - product.id:', product.id);
console.log(' - purchasedIds array:', purchasedIds);
console.log(' - isPurchased?', purchasedIds.includes(product.id));
console.log(' - isSold?', product.sold);

    return `
        <div class="express-locking-card ${isPurchased ? 'purchased' : ''} ${isSold ? 'sold' : ''}" 
             data-product-id="${product.id}">
            
            <div class="express-locking-header">
                <span class="locking-emoji">${product.emoji}</span>
                <div class="locking-name-group">
                    <span class="locking-name">${product.name}</span>
                    <span class="locking-level ${product.level.toLowerCase()}">${product.level}</span>
                </div>
            </div>

            <div class="express-locking-investment">
                <span class="investment-label">Investment</span>
                <span class="investment-amount">UGX ${formatCurrency(product.price)}</span>
            </div>

            <div class="express-locking-options">
                <span class="options-label">Locking Options</span>
                <p class="options-desc">Choose how long you want to lock your machine.</p>
                
                <div class="options-grid">
                    ${product.lock_tiers.map(tier => {
                        const isSelected = selectedDuration === tier.days;
                        return `
                            <button class="lock-option ${isSelected ? 'selected' : ''}" 
                                    data-product="${product.id}" 
                                    data-days="${tier.days}"
                                    data-rate="${tier.bonus + 6}">
                                <span class="lock-days">${tier.days} Days</span>
                                <span class="lock-rate">${tier.bonus + 6}% Daily</span>
                                <span class="lock-earnings">UGX ${formatCurrency(tier.daily)}/day</span>
                                ${isSelected ? '<span class="lock-selected">✅ Selected</span>' : ''}
                            </button>
                        `;
                    }).join('')}
                </div>
            </div>

            ${selectedDuration ? renderLockingDetails(product, selectedDuration) : ''}

            <!-- PHONE INPUT FIELD -->
            ${!isPurchased && !isSold ? `
                <div class="express-locking-phone">
                    <div class="express-phone-wrapper">
                        <span class="express-phone-icon">📱</span>
                        <input type="tel" 
                               class="express-phone-input" 
                               placeholder="Phone number" 
                               maxlength="15"
                               autocomplete="tel"
                               pattern="[0-9+\\s-]+"
                               title="Please enter a valid phone number" />
                    </div>
                    <span class="express-phone-hint">Enter your phone number to receive payment confirmation</span>
                </div>
            ` : ''}

            <div class="express-locking-actions">
                ${!isPurchased && !isSold ? `
                    ${selectedDuration ? `
                        <button class="express-product-buy-btn locking" 
                                data-product="${product.id}" 
                                data-days="${selectedDuration}"
                                data-price="${product.price}"
                                data-type="locking">
                            🔒 Invest ${selectedDuration}-Day Lock
                        </button>
                    ` : `
                        <button class="express-locking-select-hint" disabled>
                            👆 Select a locking duration above
                        </button>
                    `}
                ` : isPurchased ? `
                    <button class="express-product-details-btn" data-product="${product.id}">
                        📊 View Your Machine
                    </button>
                ` : `
                    <span class="express-sold-badge">❌ Sold Out</span>
                `}
            </div>
        </div>
    `;
}

function renderLockingDetails(product, days) {
    const tier = product.lock_tiers.find(t => t.days === days);
    if (!tier) return '';

    const baseRate = product.daily_rate || 6;
    const lockRate = tier.bonus + baseRate;

    return `
        <div class="express-locking-selected">
            <div class="selected-header">
                <span class="selected-badge">✅ Selected</span>
                <span class="selected-duration">${days}-Day Lock</span>
            </div>
            
            <div class="selected-details">
                <div class="selected-item">
                    <span class="selected-label">Daily Rate</span>
                    <span class="selected-value rate">${lockRate}%</span>
                </div>
                <div class="selected-item">
                    <span class="selected-label">Daily Earnings</span>
                    <span class="selected-value earnings">UGX ${formatCurrency(tier.daily)}</span>
                </div>
                <div class="selected-item">
                    <span class="selected-label">Lock Period</span>
                    <span class="selected-value">${days} days</span>
                </div>
                <div class="selected-item">
                    <span class="selected-label">Total Return</span>
                    <span class="selected-value total">UGX ${formatCurrency(tier.total)}</span>
                </div>
                <div class="selected-item">
                    <span class="selected-label">Total Profit</span>
                    <span class="selected-value profit">UGX ${formatCurrency(tier.total - product.price)}</span>
                </div>
            </div>
        </div>
    `;
}

// ============================================================
// PRESENTATION EVENT LISTENERS
// ============================================================

function attachPresentationListeners(products) {
    // Section Navigation Tabs
    document.querySelectorAll('.express-intro-tab').forEach(tab => {
        tab.addEventListener('click', function(e) {
            const section = this.dataset.section;
            
            document.querySelectorAll('.express-intro-tab').forEach(t => {
                t.classList.toggle('active', t.dataset.section === section);
            });
            
            const dailyInfo = document.querySelector('.intro-method.daily-active');
            const lockingInfo = document.querySelector('.intro-method.locking-inactive');
            
            if (section === 'daily') {
                if (dailyInfo) dailyInfo.style.display = 'block';
                if (lockingInfo) lockingInfo.style.display = 'none';
                const dailySection = document.getElementById('dailyMachines');
                if (dailySection) {
                    dailySection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            } else {
                if (dailyInfo) dailyInfo.style.display = 'none';
                if (lockingInfo) lockingInfo.style.display = 'block';
                const lockingSection = document.getElementById('lockingMachines');
                if (lockingSection) {
                    lockingSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }
        });
    });

    // Daily Card Toggle
    document.querySelectorAll('.express-daily-toggle').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const productId = this.dataset.product;
            const isExpanded = this.getAttribute('aria-expanded') === 'true';
            
            productState.expandedProducts[productId] = !isExpanded;
            
            const details = document.getElementById(`details-${productId}`);
            if (details) {
                details.classList.toggle('expanded', !isExpanded);
            }
            
            this.setAttribute('aria-expanded', !isExpanded);
            this.innerHTML = `
                <span>${!isExpanded ? 'Hide Details' : 'View Full Details'}</span>
                <i class="fas ${!isExpanded ? 'fa-chevron-up' : 'fa-chevron-down'}"></i>
            `;
        });
    });

    // Locking Option Selection
    document.querySelectorAll('.lock-option').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const productId = this.dataset.product;
            const days = parseInt(this.dataset.days);
            
            productState.selectedLock[productId] = days;
            
            // Re-render the locking section to update the selected state
            const product = products.find(p => p.id === productId);
            if (product) {
                const section = document.querySelector('.express-locking-section');
                if (section) {
                    const purchasedIds = [];
                    section.innerHTML = renderLockingSection(products, purchasedIds);
                    attachPresentationListeners(products);
                    attachProductListeners();
                }
            }
        });
    });
}

// ============================================================
// PRODUCT LISTENERS
// ============================================================

function attachProductListeners() {
    // All buy buttons - daily and locking
    document.querySelectorAll('.express-product-buy-btn').forEach(btn => {
        btn.addEventListener('click', handleProductInvestment);
    });

    // Phone input enter key support
    document.querySelectorAll('.express-phone-input').forEach(input => {
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                const card = this.closest('.express-daily-card, .express-locking-card, .express-product-card');
                if (card) {
                    const btn = card.querySelector('.express-product-buy-btn');
                    if (btn) btn.click();
                }
            }
        });
    });

    // Details buttons
    document.querySelectorAll('.express-product-details-btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const productId = this.dataset.product;
            const product = PRODUCTS.find(p => p.id === productId);
            showProductDetails(product);
        });
    });
}

// ============================================================
// HANDLE PRODUCT INVESTMENT - Unified for Daily & Locking
// ============================================================

async function handleProductInvestment(e) {
    const btn = e.currentTarget;
    const productId = btn.dataset.product;
    const days = parseInt(btn.dataset.days) || 0;
    const price = parseInt(btn.dataset.price) || 0;
    const type = btn.dataset.type || 'daily';

    // Find the phone input in the card
    const card = btn.closest('.express-daily-card, .express-locking-card, .express-product-card');
    const phoneInput = card ? card.querySelector('.express-phone-input') : null;
    const phone = phoneInput ? phoneInput.value.trim() : '';

    // Validate phone
    if (!phone || phone.length < 10) {
        showToast('📱 Please enter a valid phone number (e.g., 07XX XXX XXX)', 'warning');
        if (phoneInput) {
            phoneInput.focus();
            phoneInput.style.borderColor = 'var(--express-red)';
            setTimeout(() => {
                phoneInput.style.borderColor = '';
            }, 2000);
        }
        return;
    }

    // Validate phone format
    const phoneClean = phone.replace(/[^0-9+]/g, '');
    if (phoneClean.length < 10) {
        showToast('📱 Phone number must have at least 10 digits', 'warning');
        if (phoneInput) phoneInput.focus();
        return;
    }

    // Disable button and show loading state
    const originalText = btn.innerHTML;
    btn.innerHTML = '⏳ Processing...';
    btn.disabled = true;

    try {
        // Find product details
        const product = PRODUCTS.find(p => p.id === productId);
        if (!product) {
            throw new Error('Product not found');
        }

        // Determine amount to charge
        let amount = price;
        let lockDays = days;
        let isLocking = days > 0;

        // If locking, get the specific tier details
        if (isLocking) {
            const tier = product.lock_tiers.find(t => t.days === days);
            if (tier) {
                amount = product.price;
            }
        }

        const payload = {
            product: productId,
            amount: amount,
            phone: phone,
            lock_days: lockDays,
            is_locking: isLocking,
            type: type,
            lock_total: isLocking ? (product.total || 0) : 0
        };

        console.log('📤 Investment payload:', payload);

        const response = await fetch('/payments/initiate', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify(payload),
            credentials: 'include'
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.message || 'Investment failed');
        }

        const lockMsg = isLocking ? ` locked for ${lockDays} days` : '';
        showToast(`✅ Investment successful${lockMsg}!`, 'success');

        // Clear phone input on success
        if (phoneInput) phoneInput.value = '';

        // Reset selected lock state after successful investment
        if (isLocking) {
            productState.selectedLock[productId] = null;
            // Re-render to reset the UI
            const section = document.querySelector('.express-locking-section');
            if (section) {
                const purchasedIds = [];
                section.innerHTML = renderLockingSection(PRODUCTS, purchasedIds);
                attachPresentationListeners(PRODUCTS);
                attachProductListeners();
            }
        }

        // Reload user data to update balances
        setTimeout(async () => {
            const userData = await loadUserData();
            if (userData) {
                renderAll(userData);
            }
        }, 1500);

    } catch (error) {
        console.error('Investment error:', error);
        showToast('⚠️ ' + error.message, 'error');
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

function showProductDetails(product) {
    if (!product) {
        showToast('📊 Product details coming soon!', 'info');
        return;
    }
    
    const details = `
        📦 ${product.emoji} ${product.name}
        💰 Price: UGX ${formatCurrency(product.price)}
        📈 Daily Rate: ${product.daily_rate}%
        💵 Daily Profit: UGX ${formatCurrency(product.daily)}
        📊 Total Return: UGX ${formatCurrency(product.total)}
        ⏱️ Duration: ${product.duration} days
        🏷️ Level: ${product.level}
        ${product.lock_tiers ? `\n🔒 Lock Tiers:\n${product.lock_tiers.map(tier => 
            `${tier.days} days: +${tier.bonus}% (Daily: UGX ${formatCurrency(tier.daily)}, Total: UGX ${formatCurrency(tier.total)})`
        ).join('\n')}` : ''}
        ${product.sold ? '\n❌ Sold Out' : ''}
    `;
    showToast(details, 'info');
}

// ============================================================
// RENDER ALL
// ============================================================

function renderAll(userData) {
    const data = userData || currentUserData;
    if (!data) return;

    renderUser(data);
    renderBalances({
        total: data.totalBalance || data.actualBalance + data.walletBalance || 0,
        available: data.actualBalance || 0,
        wallet: data.walletBalance || 0,
        today: data.todayEarnings || 0
    });
  
    renderActivePackages(data.packages || []);
    renderNetwork({
        total: data.totalDownline || 0,
        active: data.activeDownline || 0,
        direct: data.directReferrals || 0,
        earnings: data.networkEarnings || 0
    });
    renderPendingBonus(data.pending_bonus);
    renderReferral({
        link: data.referralLink || '',
        total: data.totalReferrals || 0,
        active: data.activeReferrals || 0,
        earnings: data.referralEarnings || 0
    });
    renderAccount(data);
}


// ============================================================
// EVENT BINDINGS
// ============================================================

// 
// ============================================================
// INITIALIZATION
// ============================================================

async function init() {
    console.log('🏠 express Profile Loading...');

    const userData = await loadUserData();

    if (userData) {
        renderAll(userData);
        renderProducts(PRODUCTS, userData);
    } else {
        renderProducts(PRODUCTS, null);
    }

    bindEvents();

    console.log('✅ express Profile Ready');
    console.log(`📦 State: ${currentState}`);
}
console.log('🔴 About to auto-init...');


// ============================================================
// WITHDRAW - COMPLETE FIXED MODULE
// ============================================================

// ============================================================
// WITHDRAW - COMPLETE FIXED MODULE
// ============================================================

(function() {
    'use strict';

    // ============================================================
    // DOM REFS
    // ============================================================
    let modal = null;
    let modalForm = null;
    let modalPhone = null;
    let modalAmount = null;
    let modalSubmitBtn = null;
    let modalMessage = null;
    let modalBalance = null;
    let quickAmounts = [];

    // ============================================================
    // INIT MODAL REFERENCES
    // ============================================================
    function initRefs() {
        modal = document.getElementById('withdrawModal');
        if (!modal) {
            console.warn('⚠️ Withdraw modal not found in DOM');
            return false;
        }
        modalForm = document.getElementById('withdrawForm');
        modalPhone = document.getElementById('withdrawPhone');
        modalAmount = document.getElementById('withdrawAmount');
        modalSubmitBtn = document.getElementById('withdrawSubmitBtn');
        modalMessage = document.getElementById('withdrawMessage');
       // modalBalance = document.getElementById('modalAvailableBalance');
        quickAmounts = document.querySelectorAll('.express-quick-amount');
        return true;
    }

    // ============================================================
    // UPDATE BALANCE
    // ============================================================
    function updateAvailableBalance() {
        // This will be called from bindEvents
        if (modalBalance) {
            // Try to get balance from currentUserData
            if (currentUserData && currentUserData.actualBalance !== undefined) {
                modalBalance.textContent = `UGX ${Number(currentUserData.actualBalance).toLocaleString()}`;
                return;
            }
            
            // Fallback: fetch from server
            fetch('/user/profile', {
                credentials: 'include',
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            })
            .then(response => response.ok ? response.json() : null)
            .then(data => {
                if (data && modalBalance) {
                    const balance = data.actualBalance || 0;
                    modalBalance.textContent = `UGX ${Number(balance).toLocaleString()}`;
                }
            })
            .catch(error => console.error('Failed to load balance:', error));
        }
    }

    // ============================================================
    // OPEN MODAL
    // ============================================================
    function openWithdrawModal() {
        if (!initRefs()) return;
        
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
        
        // Reset form
        if (modalForm) modalForm.reset();
        if (modalSubmitBtn) {
            modalSubmitBtn.disabled = false;
            modalSubmitBtn.innerHTML = '<i class="fas fa-arrow-up"></i> Withdraw';
        }
        
        // Clear highlights
        quickAmounts.forEach(b => b.classList.remove('active'));
        
        // Clear messages
        if (modalMessage) modalMessage.innerHTML = '';
        
        // Update balance
        updateAvailableBalance();
        
        // Focus phone input
        setTimeout(() => {
            if (modalPhone) modalPhone.focus();
        }, 300);
        
        console.log('✅ Withdraw modal opened');
    }

    // ============================================================
    // CLOSE MODAL
    // ============================================================
    function closeWithdrawModal() {
        if (modal) {
            modal.classList.remove('active');
            document.body.style.overflow = '';
            console.log('✅ Withdraw modal closed');
        }
    }

    // ============================================================
    // HANDLE WITHDRAW SUBMIT
    // ============================================================
    async function handleWithdrawSubmit(e) {
        e.preventDefault();

        if (!modalPhone || !modalAmount || !modalSubmitBtn) {
            console.error('❌ Modal elements not found');
            return;
        }

        const phone = modalPhone.value.trim();
        const amount = modalAmount.value.trim();
        const btn = modalSubmitBtn;

        // Validate phone
        if (!phone || phone.length < 10) {
            showToast('📱 Please enter a valid phone number', 'warning');
            modalPhone.focus();
            return;
        }

        // Validate amount
        const amountNum = parseInt(amount);
        if (!amount || isNaN(amountNum)) {
            showToast('💰 Please enter a valid amount', 'warning');
            modalAmount.focus();
            return;
        }

        if (amountNum < 3000) {
            showToast('💰 Minimum withdrawal is UGX 3,000', 'warning');
            modalAmount.focus();
            return;
        }

        if (amountNum > 1000000) {
            showToast('💰 Maximum withdrawal is UGX 1,000,000', 'warning');
            modalAmount.focus();
            return;
        }

        // Disable button
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';

        try {
            const response = await fetch('/payments/withdraw', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    phone_number: phone,
                    amount: amountNum
                }),
                credentials: 'include'
            });

  const rawText = await response.text();
console.log('🔍 Raw backend response:', rawText);

let data;
try {
    data = JSON.parse(rawText);
} catch (e) {
    data = { error: 'Withdrawal failed' };
}

console.log('🔍 Parsed data:', data);

// ✅ Backend uses "error" for failures, "message" for successes
if (!response.ok || data.success === false) {
    const msg = data.error || data.message || 'Withdrawal failed';
    const details = data.details ? ` — ${data.details}` : '';
    throw new Error(msg + details);
}

// ===== SUCCESS (unchanged) =====
//showToast(`✅ Withdrawal of UGX ${amountNum.toLocaleString()} initiated successfully!`, 'success');
// ...

            // Success
            showToast(`Withdrawal of UGX ${amountNum.toLocaleString()} initiated successfully!`, 'success');
            
            if (modalMessage) {
                modalMessage.innerHTML = `
                    <div style="background:rgba(16,185,129,0.1);border:1px solid #10B981;border-radius:12px;padding:12px;margin-bottom:16px;color:#10B981;display:flex;align-items:center;gap:10px;">
                        <i class="fas fa-check-circle" style="font-size:18px;"></i>
                        <span>Withdrawal of UGX ${amountNum.toLocaleString()} initiated successfully!</span>
                    </div>
                `;
            }

            // Close modal and refresh
            setTimeout(() => {
                closeWithdrawModal();
                // Reload all data
                loadUserData().then(data => {
                    if (data) {
                        renderAll(data);
                        renderProducts(PRODUCTS, data);
                    }
                });
            }, 2000);

                } catch (error) {
        console.error('❌ Withdrawal error:', error);

        const msg = error.message || 'Withdrawal failed';
        showToast('⚠️ ' + msg, 'error');

        if (modalMessage) {
            modalMessage.innerHTML = `
                <div style="background:rgba(231,36,42,0.1);border:1px solid #E7242A;border-radius:12px;padding:12px;margin-bottom:16px;color:#E7242A;display:flex;align-items:center;gap:10px;">
                    <i class="fas fa-exclamation-circle" style="font-size:18px;"></i>
                    <span>${msg}</span>
                </div>
            `;
        }

        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-arrow-up"></i> Withdraw';
        }
    }
//==================================================================================



// ============================================================
// TRANSFER LOCKED BALANCE → DEPOSIT BALANCE
// ============================================================
async function handleTransfer() {
    const btn = document.getElementById('transferBtn');
    if (!btn) return;

    if (!confirm('Transfer your locked balance to deposit balance? It will be available for withdrawal immediately.')) {
        return;
    }

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Transferring...';

    try {
        const response = await fetch('/wallet/transfer-locked', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'include'
        });

        const rawText = await response.text();
        let data;
        try {
            data = JSON.parse(rawText);
        } catch (e) {
            data = { error: 'Transfer failed' };
        }

        if (!response.ok || data.success === false) {
            const msg = data.error || data.message || 'Transfer failed';
            throw new Error(msg);
        }

        showToast(` ${data.message || 'Transfer successful'}`, 'success');

        // Refresh balances
        setTimeout(() => {
            loadUserData().then(d => {
                if (d) {
                    renderAll(d);
                    renderProducts(PRODUCTS, d);
                }
            });
        }, 800);

    } catch (error) {
        console.error('Transfer error:', error);
        showToast('⚠️ ' + error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-exchange-alt"></i> Transfer';
    }
}

// Bind
const transferBtn = document.getElementById('transferBtn');
if (transferBtn) {
    transferBtn.addEventListener('click', handleTransfer);
}
    // ============================================================
    // BIND EVENTS
    // ============================================================
    function bindWithdrawEvents() {
        if (!initRefs()) {
            console.error('❌ Cannot bind withdraw events - modal not found');
            return;
        }

        console.log('🔗 Binding withdraw events...');

        // Withdraw button in hero
        const withdrawBtn = document.getElementById('withdrawBtn');
        if (withdrawBtn) {
            withdrawBtn.removeEventListener('click', openWithdrawModal);
            withdrawBtn.addEventListener('click', openWithdrawModal);
            console.log('✅ Withdraw button bound');
        } else {
            console.warn('⚠️ #withdrawBtn not found in DOM');
        }

        // Close buttons
        const closeBtn = document.getElementById('closeWithdrawModal');
        if (closeBtn) {
            closeBtn.removeEventListener('click', closeWithdrawModal);
            closeBtn.addEventListener('click', closeWithdrawModal);
        }

        const cancelBtn = document.getElementById('cancelWithdraw');
        if (cancelBtn) {
            cancelBtn.removeEventListener('click', closeWithdrawModal);
            cancelBtn.addEventListener('click', closeWithdrawModal);
        }

        // Overlay click
        if (modal) {
            modal.addEventListener('click', function(e) {
                if (e.target === this) closeWithdrawModal();
            });
        }

        // Escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                if (modal && modal.classList.contains('active')) {
                    closeWithdrawModal();
                }
            }
        });

        // Quick amount buttons
        quickAmounts.forEach(btn => {
            btn.addEventListener('click', function() {
                const amount = this.dataset.amount;
                if (modalAmount) {
                    modalAmount.value = amount;
                    quickAmounts.forEach(b => b.classList.remove('active'));
                    this.classList.add('active');
                }
            });
        });

        // Form submit
        if (modalForm) {
            modalForm.removeEventListener('submit', handleWithdrawSubmit);
            modalForm.addEventListener('submit', handleWithdrawSubmit);
        }

        console.log('🏦 Withdraw events bound successfully');
    }

    // ============================================================
    // EXPOSE PUBLIC API
    // ============================================================
    window.Withdraw = {
        open: openWithdrawModal,
        close: closeWithdrawModal,
        updateBalance: updateAvailableBalance,
        bindEvents: bindWithdrawEvents
    };

    console.log('🔵 Withdraw module loaded');

})();

// ============================================================
// UPDATE bindEvents() TO CALL THE WITHDRAW MODULE
// ============================================================

// Replace your existing bindEvents() with this:
function bindEvents() {
    // ✅ Initialize withdraw module events
    if (window.Withdraw && typeof window.Withdraw.bindEvents === 'function') {
        window.Withdraw.bindEvents();
    }

    // Logout buttons
document.getElementById('logoutBtn')?.addEventListener('click', async function () {
    if (!confirm('Are you sure you want to logout?')) return;

    const btn = this;
    const originalHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Logging out...';

    try {
        const res = await fetch('/api/logout', {
            method: 'POST',
            credentials: 'include',
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });

        if (res.ok) {
            showToast('👋 Logged out', 'success');
            setTimeout(() => window.location.href = '/', 800);
        } else {
            throw new Error('Logout failed');
        }
    } catch (err) {
        console.error('Logout error:', err);
        showToast('⚠️ Logout failed. Please try again.', 'error');
        btn.disabled = false;
        btn.innerHTML = originalHTML;
    }
});

    document.getElementById('reinvestBtn')?.addEventListener('click', function() {
        document.getElementById('packagesSection').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });

    document.getElementById('copyRefBtn')?.addEventListener('click', function() {
        const link = document.getElementById('referralLink');
        if (link) {
            link.select();
            document.execCommand('copy');
            showToast('Referral link copied!', 'success');
        }
    });

 

    document.getElementById('inviteNetworkBtn')?.addEventListener('click', function() {
        const link = document.getElementById('referralLink')?.value || '';
        if (link) {
            navigator.clipboard?.writeText(link).then(() => {
                showToast('Referral link copied!', 'success');
            }).catch(() => {
                const input = document.getElementById('referralLink');
                if (input) {
                    input.select();
                    document.execCommand('copy');
                    showToast('Referral link copied!', 'success');
                }
            });
        }
    });

    document.getElementById('notificationBell')?.addEventListener('click', function() {
        document.getElementById('notificationsContainer').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });

    document.getElementById('viewAllNotifications')?.addEventListener('click', function() {
        showToast('📬 All notifications coming soon!', 'info');
    });

    document.getElementById('loadMoreTxns')?.addEventListener('click', function() {
        showToast('📜 Loading more transactions...', 'info');
    });

    document.querySelectorAll('.express-level-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.express-level-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            showToast(`📊 Filtering: ${this.textContent.trim()}`, 'info');
        });
    });
}

// ============================================================
// SINGLE AUTO-INIT - KEEP ONLY THIS ONE
// ============================================================
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}


/* ============================================================
   express · EXPRESS · MINIMAL PRODUCT RENDERERS
   Overrides the legacy card renderers completely.
   ============================================================ */

function _ugx(n) {
  return parseInt(n || 0).toLocaleString('en-US');
}

// ---------- DAILY PRODUCT CARD ----------
function renderDailyCard(product, purchasedIds) {
  const isPurchased = purchasedIds.includes(product.id);
  const isSold = product.sold;

const bgUrl = getPackagePhoto(product.id);
const bgStyle = bgUrl ? `style="background-image:url('${bgUrl}')"` : '';

return `
    <div class="express-daily-card ${isPurchased ? 'purchased' : ''} ${isSold ? 'sold' : ''}" 
         data-product-id="${product.id}" ${bgStyle}>

      <div class="express-daily-header">
        <span class="daily-name">${product.name}</span>
        <span class="daily-level">Daily</span>
      </div>

      <div class="express-daily-investment">
        <span class="investment-label">Invest</span>
        <span class="investment-amount">UGX ${_ugx(product.price)}</span>
      </div>

      <div class="express-daily-earnings">
        <span class="earnings-label">Earn / Day</span>
        <span class="earnings-amount">UGX ${_ugx(product.daily)}</span>
      </div>

      <div class="express-daily-meta">
        <div class="meta-item">
          <span class="meta-label">Duration</span>
          <span class="meta-value">${product.duration} days</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">Total Profit</span>
          <span class="meta-value gold">UGX ${_ugx(product.total)}</span>
        </div>
      </div>

      ${!isPurchased && !isSold ? `
        <div class="express-daily-phone">
          <div class="express-phone-wrapper">
            <span class="express-phone-icon"></span>
            <input type="tel" class="express-phone-input"
                   placeholder="Phone number" maxlength="15" autocomplete="off" />
          </div>
        </div>
        <button class="express-product-buy-btn"
                data-product="${product.id}"
                data-price="${product.price}"
                data-days="0"
                data-type="daily">
           Invest Now
        </button>
      ` : isPurchased ? `
        <button class="express-product-details-btn" data-product="${product.id}">View Machine</button>
      ` : `
        <span class="express-sold-badge">Sold Out</span>
      `}
    </div>
  `;
}

// ---------- LOCK PRODUCT CARD ----------
function renderLockingCard(product, purchasedIds) {
  const isPurchased = purchasedIds.includes(product.id);
  const isSold = product.sold;
  const days = product.lock_days || 0;
  const profit = (product.total || 0) - (product.price || 0);

   const bgUrl = getPackagePhoto(product.id);                          // ← ADD
  const bgStyle = bgUrl ? `style="background-image:url('${bgUrl}')"` : '';  // ← ADD

return `
    <div class="express-locking-card ${isPurchased ? 'purchased' : ''} ${isSold ? 'sold' : ''}"
         data-product-id="${product.id}" ${bgStyle}>  

      <div class="express-locking-header">
        <span class="locking-name">${product.name}</span>
        <span class="locking-level">${days}-Day Lock</span>
      </div>

      <div class="express-locking-investment">
        <span class="investment-label">Invest</span>
        <span class="investment-amount">UGX ${_ugx(product.price)}</span>
      </div>

      <div class="express-daily-earnings">
        <span class="earnings-label">Total Return</span>
        <span class="earnings-amount">UGX ${_ugx(product.total)}</span>
      </div>

      <div class="express-daily-meta">
        <div class="meta-item">
          <span class="meta-label">Lock Duration</span>
          <span class="meta-value">${days} days</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">Profit</span>
          <span class="meta-value gold">UGX ${_ugx(profit)}</span>
        </div>
      </div>

      ${!isPurchased && !isSold ? `
        <div class="express-locking-phone">
          <div class="express-phone-wrapper">
            <span class="express-phone-icon"></span>
            <input type="tel" class="express-phone-input"
                   placeholder="Phone number" maxlength="15" autocomplete="off" />
          </div>
        </div>
        <button class="express-product-buy-btn locking"
                data-product="${product.id}"
                data-price="${product.price}"
                data-days="${days}"
                data-type="locking">
           Confirm Lock
        </button>
      ` : isPurchased ? `
        <button class="express-product-details-btn" data-product="${product.id}">View Machine</button>
      ` : `
        <span class="express-sold-badge">Sold Out</span>
      `}
    </div>
  `;
}

// ---------- SECTION RENDERERS (minimal) ----------
function renderDailySection(products, purchasedIds) {
  const items = products.filter(p => !p.lock_days && !p.sold);
  if (!items.length) return '';
  return `
    <div class="express-section-header">
      <h2 class="express-section-title"> Withdraw Everyday</h2>
       <h4 class="express-section-subtitle">
        <span>These are products where you withdraw your profits everyday</span>
      </h4>
    </div>
    <div class="express-daily-grid">
      ${items.map(p => renderDailyCard(p, purchasedIds)).join('')}
    </div>
  `;
}

function renderLockingSection(products, purchasedIds) {
  const locks = products.filter(p => p.lock_days && !p.sold);
  if (!locks.length) return '';

  const byDays = n => locks.filter(p => p.lock_days === n);
  const group = (title, days) => {
    const items = byDays(days);
    if (!items.length) return '';
    return `
      <div class="express-section-header">
        <h2 class="express-section-title"> ${title}</h2>
      </div>
      <div class="express-locking-grid">
        ${items.map(p => renderLockingCard(p, purchasedIds)).join('')}
      </div>
    `;
  };

  return `
    ${group('1-Day Lock',  1)}
    ${group('3-Day Lock',  3)}
    ${group('7-Day Lock',  7)}
    ${group('14-Day Lock', 14)}
  `;
}

function renderIntroduction() {
  return ''; // disabled — new design has no intro block
}

// ---------- MASTER renderProducts (overrides legacy) ----------
function renderProducts(products = PRODUCTS, user = null) {
  const container = document.getElementById('expressProducts');
  if (!container) {
    console.error('❌ Container #expressProducts not found');
    return;
  }

  const hasPackages = user && user.packages && user.packages.length > 0;
  const purchasedIds = hasPackages ? user.packages.map(p => p.product_id || p.id) : [];

  container.innerHTML = `
    ${renderDailySection(products, purchasedIds)}
    ${renderLockingSection(products, purchasedIds)}
  `;

  attachProductListeners();
}

// ---------- LISTENERS (minimal) ----------
function attachPresentationListeners() { /* no-op — no tier UI to bind */ }

function attachProductListeners() {
  document.querySelectorAll('.express-product-buy-btn').forEach(btn => {
    btn.removeEventListener('click', handleProductInvestment);
    btn.addEventListener('click', handleProductInvestment);
  });

  document.querySelectorAll('.express-phone-input').forEach(input => {
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        const card = this.closest('.express-daily-card, .express-locking-card');
        if (card) {
          const btn = card.querySelector('.express-product-buy-btn');
          if (btn) btn.click();
        }
      }
    });
  });

  document.querySelectorAll('.express-product-details-btn').forEach(btn => {
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      const productId = this.dataset.product;
      const product = PRODUCTS.find(p => p.id === productId);
      showProductDetails(product);
    });
  });
}



/* ===== DEPOSIT MODAL JAVASCRIPT ===== */

(function() {
  'use strict';

  // ===== CONFIGURATION =====
  const CONFIG = {
    API_ENDPOINT: '/payments/initiate',
    AIRTEL_NUMBER: '0701719760',
    MIN_AMOUNT: 500,
    MAX_AMOUNT: 10000000,
    PHONE_REGEX: /^0[0-9]{9}$/,
    REFERENCE_PREFIX: 'DEP'
  };

  // ===== DOM ELEMENTS =====
  const elements = {
    modal: document.getElementById('depositModal'),
    closeBtn: document.getElementById('closeDepositModal'),
    cancelBtn: document.getElementById('cancelDeposit'),
    form: document.getElementById('depositForm'),
    phoneInput: document.getElementById('depositPhone'),
    amountInput: document.getElementById('depositAmount'),
    phoneError: document.getElementById('phoneError'),
    amountError: document.getElementById('amountError'),
    referenceInput: document.getElementById('userReference'),
    copyReferenceBtn: document.getElementById('copyReferenceBtn'),
    copyAirtelBtn: document.getElementById('copyAirtelNumber'),
    submitBtn: document.getElementById('submitDeposit'),
    statusDiv: document.getElementById('depositStatus'),
    quickAmountBtns: document.querySelectorAll('.express-quick-amount')
  };

  // ===== STATE =====
  let state = {
    isSubmitting: false,
    reference: null
  };

  // ===== UTILITY FUNCTIONS =====

  /**
   * Generate a unique deposit reference
   */
  function generateReference() {
    const timestamp = Date.now().toString(36).toUpperCase();
    const random = Math.random().toString(36).substring(2, 6).toUpperCase();
    return `${CONFIG.REFERENCE_PREFIX}-${timestamp}-${random}`;
  }

  /**
   * Format number with commas
   */
  function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }

  /**
   * Show error message for a field
   */
  function showError(element, message) {
    if (element) {
      element.textContent = message;
      element.classList.add('visible');
      const input = element.previousElementSibling;
      if (input && input.classList.contains('express-form-input')) {
        input.classList.add('error');
      }
    }
  }

  /**
   * Clear error message for a field
   */
  function clearError(element) {
    if (element) {
      element.textContent = '';
      element.classList.remove('visible');
      const input = element.previousElementSibling;
      if (input && input.classList.contains('express-form-input')) {
        input.classList.remove('error');
      }
    }
  }

  /**
   * Clear all errors
   */
  function clearAllErrors() {
    clearError(elements.phoneError);
    clearError(elements.amountError);
  }

  /**
   * Show status message
   */
  function showStatus(message, type = 'info') {
    if (!elements.statusDiv) return;
    
    const icons = {
      success: '<i class="fas fa-check-circle"></i>',
      error: '<i class="fas fa-exclamation-circle"></i>',
      loading: '<div class="express-spinner"></div>',
      info: '<i class="fas fa-info-circle"></i>'
    };
    
    elements.statusDiv.innerHTML = `${icons[type] || ''} <span>${message}</span>`;
    elements.statusDiv.className = `express-deposit-status visible ${type}`;
  }

  /**
   * Hide status message
   */
  function hideStatus() {
    if (elements.statusDiv) {
      elements.statusDiv.className = 'express-deposit-status';
      elements.statusDiv.innerHTML = '';
    }
  }

  /**
   * Set loading state on submit button
   */
  function setLoading(isLoading) {
    state.isSubmitting = isLoading;
    
    if (elements.submitBtn) {
      elements.submitBtn.disabled = isLoading;
      
      if (isLoading) {
        elements.submitBtn.innerHTML = `
          <div class="express-spinner"></div> Processing...
        `;
      } else {
        elements.submitBtn.innerHTML = `
          <i class="fas fa-paper-plane"></i> Submit Deposit
        `;
      }
    }
  }

  /**
   * Copy text to clipboard
   */
  async function copyToClipboard(text, buttonEl, originalHTML) {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        // Fallback for non-secure contexts
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      }
      
      // Visual feedback
      if (buttonEl) {
        buttonEl.classList.add('copied');
        const originalText = buttonEl.innerHTML;
        buttonEl.innerHTML = '<i class="fas fa-check"></i> Copied!';
        
        setTimeout(() => {
          buttonEl.classList.remove('copied');
          buttonEl.innerHTML = originalHTML || originalText;
        }, 2000);
      }
      
      return true;
    } catch (err) {
      console.error('Copy failed:', err);
      return false;
    }
  }

  // ===== VALIDATION =====

  /**
   * Validate phone number
   */
  function validatePhone(phone) {
    const cleaned = phone.trim().replace(/\s+/g, '');
    
    if (!cleaned) {
      return { valid: false, message: 'Phone number is required' };
    }
    
    if (!CONFIG.PHONE_REGEX.test(cleaned)) {
      return { 
        valid: false, 
        message: 'Enter a valid 10-digit number starting with 0 (e.g., 0701719760)' 
      };
    }
    
    return { valid: true, value: cleaned };
  }

  /**
   * Validate amount
   */
  function validateAmount(amount) {
    const num = parseFloat(amount);
    
    if (!amount || isNaN(num)) {
      return { valid: false, message: 'Amount is required' };
    }
    
    if (num < CONFIG.MIN_AMOUNT) {
      return { 
        valid: false, 
        message: `Minimum deposit is UGX ${formatNumber(CONFIG.MIN_AMOUNT)}` 
      };
    }
    
    if (num > CONFIG.MAX_AMOUNT) {
      return { 
        valid: false, 
        message: `Maximum deposit is UGX ${formatNumber(CONFIG.MAX_AMOUNT)}` 
      };
    }
    
    if (!Number.isInteger(num)) {
      return { valid: false, message: 'Amount must be a whole number' };
    }
    
    return { valid: true, value: num };
  }

  /**
   * Validate entire form
   */
  function validateForm() {
    clearAllErrors();
    let isValid = true;
    
    // Validate phone
    const phoneResult = validatePhone(elements.phoneInput.value);
    if (!phoneResult.valid) {
      showError(elements.phoneError, phoneResult.message);
      isValid = false;
    }
    
    // Validate amount
    const amountResult = validateAmount(elements.amountInput.value);
    if (!amountResult.valid) {
      showError(elements.amountError, amountResult.message);
      isValid = false;
    }
    
    return {
      isValid,
      phone: phoneResult.value,
      amount: amountResult.value
    };
  }

  // ===== API COMMUNICATION =====

  /**
   * Submit deposit to backend
   */
  async function submitDeposit(phone, amount) {
    const payload = {
      payment_type: 'deposit',
      payment_method: 'mobile',
      phone: phone,
      amount: amount,
      reference: state.reference,
      product: 'deposit',
      lock_days: 0,
      is_locking: false
    };

    console.log('📤 Submitting deposit:', payload);

    const response = await fetch(CONFIG.API_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      credentials: 'include',
      body: JSON.stringify(payload)
    });

    let data;
    try {
      data = await response.json();
    } catch (e) {
      throw new Error(`Server returned ${response.status} with invalid JSON`);
    }

    if (!response.ok) {
      throw new Error(data.error || data.message || `Request failed (${response.status})`);
    }

    return data;
  }

  // ===== FORM HANDLING =====

  /**
   * Handle form submission
   */
  async function handleSubmit(e) {
    e.preventDefault();
    
    if (state.isSubmitting) return;
    
    hideStatus();
    
    const validation = validateForm();
    if (!validation.isValid) {
      showStatus('Please fix the errors above', 'error');
      return;
    }

    setLoading(true);
    showStatus('Initiating deposit...', 'loading');

    try {
      const result = await submitDeposit(validation.phone, validation.amount);
      
      console.log('✅ Deposit response:', result);
      
      showStatus(
        `Deposit initiated successfully! Reference: ${state.reference}. ` +
        `Please call +256 200 300 300 to confirm.`,
        'success'
      );
      
      // Reset form after success
      setTimeout(() => {
        resetForm();
        showStatus(
          'Deposit submitted. Check your phone for confirmation.',
          'success'
        );
      }, 5000);
      
    } catch (error) {
      console.error('❌ Deposit error:', error);
      showStatus(error.message || 'Failed to initiate deposit. Please try again.', 'error');
    } finally {
      setLoading(false);
    }
  }

  /**
   * Reset form to initial state
   */
  function resetForm() {
    elements.form.reset();
    clearAllErrors();
    state.reference = generateReference();
    elements.referenceInput.value = state.reference;
    
    // Remove active state from quick amount buttons
    elements.quickAmountBtns.forEach(btn => btn.classList.remove('active'));
  }

  /**
   * Handle quick amount button click
   */
  function handleQuickAmount(e) {
    const btn = e.currentTarget;
    const amount = btn.dataset.amount;
    
    if (amount) {
      elements.amountInput.value = amount;
      clearError(elements.amountError);
      
      elements.quickAmountBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    }
  }

  /**
   * Handle phone input formatting
   */
  function handlePhoneInput(e) {
    let value = e.target.value.replace(/\D/g, '');
    
    // Limit to 10 digits
    if (value.length > 10) {
      value = value.substring(0, 10);
    }
    
    e.target.value = value;
    
    if (value.length === 10) {
      clearError(elements.phoneError);
    }
  }

  /**
   * Handle amount input
   */
  function handleAmountInput(e) {
    const value = e.target.value;
    
    if (value && parseFloat(value) >= CONFIG.MIN_AMOUNT) {
      clearError(elements.amountError);
    }
    
    // Remove active state from quick buttons if custom amount
    const matchingBtn = Array.from(elements.quickAmountBtns)
      .find(btn => btn.dataset.amount === value);
    
    elements.quickAmountBtns.forEach(btn => {
      btn.classList.toggle('active', btn === matchingBtn);
    });
  }

  // ===== MODAL CONTROLS =====

  /**
   * Open modal
   */
  function openModal() {
    if (!elements.modal) return;
    
    // Generate fresh reference
    state.reference = generateReference();
    elements.referenceInput.value = state.reference;
    
    hideStatus();
    clearAllErrors();
    elements.modal.classList.add('active');
    
    // Focus phone input after animation
    setTimeout(() => {
      if (elements.phoneInput) elements.phoneInput.focus();
    }, 300);
    
    // Prevent body scroll
    document.body.style.overflow = 'hidden';
  }

  /**
   * Close modal
   */
  function closeModal() {
    if (!elements.modal || state.isSubmitting) return;
    
    elements.modal.classList.remove('active');
    document.body.style.overflow = '';
    
    // Reset after close animation
    setTimeout(() => {
      resetForm();
      hideStatus();
    }, 300);
  }

  // ===== EVENT LISTENERS =====

  function bindEvents() {
    // Form submission
    if (elements.form) {
      elements.form.addEventListener('submit', handleSubmit);
    }
    
    // Modal controls
    if (elements.closeBtn) {
      elements.closeBtn.addEventListener('click', closeModal);
    }
    
    if (elements.cancelBtn) {
      elements.cancelBtn.addEventListener('click', closeModal);
    }
    
    // Close on overlay click
    if (elements.modal) {
      elements.modal.addEventListener('click', (e) => {
        if (e.target === elements.modal) {
          closeModal();
        }
      });
    }
    
    // Close on Escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && elements.modal.classList.contains('active')) {
        closeModal();
      }
    });
    
    // Phone input
    if (elements.phoneInput) {
      elements.phoneInput.addEventListener('input', handlePhoneInput);
    }
    
    // Amount input
    if (elements.amountInput) {
      elements.amountInput.addEventListener('input', handleAmountInput);
    }
    
    // Quick amount buttons
    elements.quickAmountBtns.forEach(btn => {
      btn.addEventListener('click', handleQuickAmount);
    });
    
    // Copy reference
    if (elements.copyReferenceBtn) {
      elements.copyReferenceBtn.addEventListener('click', () => {
        copyToClipboard(
          state.reference,
          elements.copyReferenceBtn,
          '<i class="fas fa-copy"></i> Copy'
        );
      });
    }
    
    // Copy Airtel number
    if (elements.copyAirtelBtn) {
      elements.copyAirtelBtn.addEventListener('click', () => {
        copyToClipboard(
          CONFIG.AIRTEL_NUMBER,
          elements.copyAirtelBtn,
          '<i class="fas fa-copy"></i>'
        );
      });
    }
  }

  // ===== INITIALIZATION =====

  function init() {
    if (!elements.modal) {
      console.warn('Deposit modal not found in DOM');
      return;
    }
    
    bindEvents();
    
    // Generate initial reference
    state.reference = generateReference();
    if (elements.referenceInput) {
      elements.referenceInput.value = state.reference;
    }
    
    console.log('✅ Deposit modal initialized');
  }

  // ===== PUBLIC API =====
  window.DepositModal = {
    open: openModal,
    close: closeModal,
    reset: resetForm,
    isOpen: () => elements.modal && elements.modal.classList.contains('active')
  };

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
// ============================================================
// PENDING BONUS HELPERS
// ============================================================

let _pendingCountdownTimer = null;

/**
 * Parse a naive-UTC ISO string (e.g. "2026-10-07T14:30:00") as UTC.
 */
function _parseNaiveUTC(iso) {
  if (!iso) return null;
  if (/[Zz]|[+-]\d{2}:?\d{2}$/.test(iso)) return new Date(iso);
  return new Date(iso + 'Z');
}

function _formatCountdown(msRemaining) {
  if (msRemaining <= 0) return { text: 'Maturing now…', expired: true };
  
  const totalMinutes = Math.floor(msRemaining / 60000);
  const days    = Math.floor(totalMinutes / 1440);
  const hours   = Math.floor((totalMinutes % 1440) / 60);
  const minutes = totalMinutes % 60;
  
  if (days > 0)  return { text: `${days}d ${hours}h`, expired: false };
  if (hours > 0) return { text: `${hours}h ${minutes}m`, expired: false };
  return { text: `${minutes}m`, expired: false };
}
function renderPendingBonus(pending) {
return;
  const card    = document.getElementById('pendingBonusCard');
  const amount  = document.getElementById('pendingBonusAmount');
  const cdText  = document.getElementById('pendingBonusCountdownText');
  const hint    = document.getElementById('pendingBonusHint');
  const dailyAmount = document.getElementById('dailyPendingAmount');
  
  // ↓ Daily card targets
  const dailyLine = document.getElementById('dailyPendingLine');
  const dailyText = document.getElementById('dailyPendingText');
  
  // No pending → hide both
  if (!pending || !pending.total || pending.total <= 0) {
    if (card) card.style.display = 'none';
    if (dailyLine) dailyLine.style.display = 'none';
    if (_pendingCountdownTimer) {
      clearInterval(_pendingCountdownTimer);
      _pendingCountdownTimer = null;
    }
    return;
  }
  
  // Show both
  if (card) card.style.display = 'flex';
  if (amount) amount.textContent = `UGX ${Number(pending.total).toLocaleString()}`;
  if (dailyAmount) dailyAmount.textContent = `UGX ${Number(pending.total).toLocaleString()}`;
  if (dailyLine) dailyLine.style.display = 'inline-flex';
  
  if (hint) {
    hint.textContent = pending.count > 1
      ? `${pending.count} bonuses maturing`
      : '';
  }
  
  const nextMaturesAt = _parseNaiveUTC(pending.next_matures_at);
  if (!nextMaturesAt) return;
  
  if (_pendingCountdownTimer) clearInterval(_pendingCountdownTimer);
  
  const tick = () => {
    const remaining = nextMaturesAt.getTime() - Date.now();
    const { text, expired } = _formatCountdown(remaining);
    
    const line = expired
      ? 'Maturing now…'
      : `Matures in ${text}`;
    
    // Update both targets
    if (cdText) cdText.textContent = expired
      ? 'Maturing now — refresh in a moment'
      : `Matures in ${text}`;
    
    if (dailyText) dailyText.textContent = line;
    
    // Toggle green state on Daily card
    if (dailyLine) {
      dailyLine.classList.toggle('expired', expired);
    }
    
    if (expired) {
      clearInterval(_pendingCountdownTimer);
      _pendingCountdownTimer = null;
      // Optional: auto-refresh
      // if (typeof loadUserProfile === 'function') loadUserProfile();
    }
  };
  
  tick();
  _pendingCountdownTimer = setInterval(tick, 30000);
}


// ============================================================
// DEBUG: lock state inspection — remove after debugging
// ============================================================
setTimeout(() => {
    fetch('/user/profile', { credentials: 'include' })
        .then(r => r.json())
        .then(d => {
            console.log('═══════════════════════════════════════════');
            console.log('🔍 LOCK DEBUG — user:', d.id, d.username);
            console.log('═══════════════════════════════════════════');
            d.packages?.forEach(p => {
                const L  = !!p.is_locked;
                const E  = p.lock_end_date ? new Date(p.lock_end_date) : null;
                const M  = E && E <= new Date();
                const $  = Number(p.lock_earnings || 0);
                const btn = !L ? 'SKIP (not locked)'
                          : !M ? 'SKIP (still waiting)'
                          : $ <= 0 ? 'SKIP (no earnings)'
                          : '✅ BUTTON SHOULD SHOW';
                console.log(
                    `📦 ${p.id} "${p.package}"`,
                    '\n   is_locked:', p.is_locked,
                    '\n   lock_end_date:', p.lock_end_date,
                    '\n   parsed lockEnd:', E,
                    '\n   now:', new Date(),
                    '\n   lockEnd <= now?', M,
                    '\n   lock_earnings:', p.lock_earnings,
                    '\n   →', btn
                );
            });
            console.log('═══════════════════════════════════════════');
        });
}, 2000);