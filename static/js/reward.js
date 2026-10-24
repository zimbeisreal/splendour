/* ===== REWARDS TAB ===== */
(function () {
    'use strict';

    const $ = (id) => document.getElementById(id);

    const tab       = $('tab-rewards');
    const claimBtn  = $('rewardsClaimBtn');

    if (!tab) {
        console.warn('⚠️ Rewards tab not found');
        return;
    }

    let currentData = null;
    let loaded      = false;

    // ---------- LOAD ----------
    async function loadRewards() {
        try {
            const res = await fetch('/api/user/rewards', {
                credentials: 'include',
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            const raw = await res.text();
            let data;
            try { data = JSON.parse(raw); }
            catch { data = { error: 'Failed to load rewards' }; }

            if (!res.ok || data.error) {
                showToast(data.error || 'Failed to load rewards', 'error');
                return;
            }
            currentData = data;
            loaded = true;
            render(data);
        } catch (err) {
            console.error('Rewards load error:', err);
            showToast('Network error loading rewards', 'error');
        }
    }

    // Expose so tab click can trigger load
    window.loadRewardsTab = function () {
        if (!loaded) loadRewards();
    };

    // ---------- RENDER ----------
    function render(data) {
        const { stats, level_reward, cycle_reward } = data;

        // Stats tiles
        setText('rewardsStatRegistered', stats.referrals_joined);
        setText('rewardsStatActive',     stats.referrals_active);
        setText('rewardsStatInactive',   stats.referrals_inactive);
        setText('rewardsStatInvested',   'UGX ' + fmt(stats.active_invested));

        // Hero badge
        const levelUnlocked = level_reward.qualified;
        const icon = $('rewardsCurrentLevelIcon');
        if (icon) icon.classList.toggle('locked', !levelUnlocked);

        setText('rewardsCurrentLevelText',
            levelUnlocked
                ? 'Level 1 · Bronze'
                : `No Reward Yet · ${level_reward.current}/${level_reward.requirement} active`
        );

        // Progress bar — toward 3 active
        const pct = Math.min(100,
            (level_reward.current / level_reward.requirement) * 100
        );
        setText('rewardsProgressLabel',
            `Active referrals toward ${level_reward.requirement}`
        );
        setText('rewardsProgressPercent', Math.round(pct) + '%');
        const fill = $('rewardsProgressFill');
        if (fill) fill.style.width = pct + '%';

        setText('rewardsProgressMeta',
            level_reward.current >= level_reward.requirement
                ? 'Requirements met 🎉'
                : `${level_reward.requirement - level_reward.current} more active referrals needed`
        );

        renderLevelReward(level_reward);
        renderCycleReward(cycle_reward);

       // Referral code / link
       // const codeEl = $('rewardsReferralCode');
    //     if (codeEl && !codeEl.value) {
    //         // Reuse the same link the Team tab uses
    //         const teamLink = $('referralLink');
    //         if (teamLink && teamLink.value) codeEl.value = teamLink.value;
    //     }
    }

    function renderLevelReward(level) {
        const panel = $('rewardsClaimPanel');
        const meta  = $('rewardsClaimMeta');
        const txt   = $('rewardsClaimBtnText');

        if (panel) panel.style.display = 'flex';
        setText('rewardsClaimAmount', 'UGX ' + fmt(level.reward));

        if (level.paid) {
            if (meta) meta.textContent = '✅ Already paid';
            if (claimBtn) claimBtn.disabled = true;
            if (txt) txt.textContent = 'Paid';
        } else if (level.can_claim) {
            if (meta) meta.textContent = 'Claim available now — credited to locked balance';
            if (claimBtn) claimBtn.disabled = false;
            if (txt) txt.textContent = `Claim UGX ${fmt(level.reward)}`;
        } else {
            if (meta) meta.textContent =
                `${level.current}/${level.requirement} active referrals`;
            if (claimBtn) claimBtn.disabled = true;
            if (txt) txt.textContent = 'Locked';
        }
    }

    function renderCycleReward(cycle) {
        const list = $('rewardsLevelsList');
        if (!list) return;

        const pct = cycle.percent || 0;
        list.innerHTML = `
            <div class="express-rewards-level-row current">
                <div class="express-rewards-level-head">
                    <span class="express-rewards-level-name">
                        <span class="icon"></span> 20-Referral Bonus
                    </span>
                    <span class="express-rewards-level-state current">
                        ${cycle.progress}/${cycle.cycle_size}
                    </span>
                </div>
                <div class="express-rewards-level-detail" style="grid-template-columns:1fr;">
                    <div style="width:100%;">
                        <div class="express-rewards-progress-bar" style="margin:6px 0;">
                            <div class="express-rewards-progress-fill" style="width:${pct}%"></div>
                        </div>
                        <span style="color:var(--express-muted);font-size:11px;">
                            Each referral = UGX ${fmt(cycle.per_referral_value)} ·
                            ${cycle.remaining} more to earn UGX ${fmt(cycle.cycle_reward)}
                        </span>
                    </div>
                </div>
                <div class="express-rewards-level-detail">
                    <div class="kv"><span class="k">Paid cycles</span><span class="v">${cycle.paid_cycles}</span></div>
                    <div class="kv"><span class="k">Payout</span><span class="v gold">UGX ${fmt(cycle.cycle_reward)}</span></div>
                    <div class="kv"><span class="k">Credited to</span><span class="v">Locked</span></div>
                </div>
            </div>
        `;
    }

    // ---------- CLAIM ----------
    if (claimBtn) {
        claimBtn.addEventListener('click', async () => {
            if (claimBtn.disabled) return;
            claimBtn.disabled = true;
            const txt = $('rewardsClaimBtnText');
            const original = txt ? txt.textContent : '';
            if (txt) txt.textContent = 'Claiming…';

            try {
                const res = await fetch('/api/user/rewards/claim', {
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
                catch { data = { error: 'Claim failed' }; }

                if (!res.ok || data.success === false) {
                    throw new Error(data.error || data.message || 'Claim failed');
                }
                showToast(`✅ UGX ${fmt(data.claimed)} credited to your locked balance`, 'success');
                await loadRewards();
            } catch (err) {
                console.error('Claim error:', err);
                showToast('⚠️ ' + err.message, 'error');
                if (txt) txt.textContent = original;
                claimBtn.disabled = false;
            }
        });
    }

    // ---------- Helpers ----------
    function fmt(n) {
        return parseFloat(n || 0).toLocaleString('en-US', {
            minimumFractionDigits: 0, maximumFractionDigits: 0
        });
    }
    function setText(id, val) {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    }

    // Initial load (tab may already be visible if it's the default, unlikely)
    // ---------- TAB ACTIVATION ----------
    document.addEventListener('tab:changed', (e) => {
        if (e.detail && e.detail.tab === 'rewards') {
            console.log('🔵 Rewards tab activated — loading');
            loadRewards();
        }
    });

    // Also expose for manual trigger
    window.loadRewardsTab = loadRewards;

    // If the tab is already active on load (sessionStorage restore)
    if (tab.classList.contains('is-active')) {
        console.log('🔵 Rewards tab is default — loading');
        loadRewards();
    }

    console.log('🎁 Rewards tab ready');
})();