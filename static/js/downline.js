

// ============================================================
// SIMPLIFIED NETWORK CONTROLLER - WORKS WITH YOUR HTML
// ============================================================

// ============================================================
// UPDATE NETWORK STATS - FIXED
// ============================================================

function updateNetworkStats(data) {
    console.log('📊 Updating network stats with data:', data);
    
    // ============================================================
    // EXTRACT VALUES
    // ============================================================
    const referralStats = data.referral_stats || {};
    const lifetimeEarnings = data.lifetime_earnings || {};
    const breakdown = data.breakdown || {};
    
    // Get values with fallbacks
    const totalReferrals = referralStats.total_network_size || 
                          referralStats.total_direct_referrals || 0;
    
    const activeReferrals = referralStats.active_referrals || 0;
    
    const directReferrals = referralStats.direct_referrals_count || 
                           referralStats.total_direct_referrals || 0;
    
    const earnings = lifetimeEarnings.total || 0;
    
    // ============================================================
    // UPDATE STATS CARDS
    // ============================================================
    
    // 1. Total Downline
    const totalEl = document.getElementById('totalDownline');
    if (totalEl) {
        totalEl.textContent = totalReferrals;
        console.log(`✅ Updated totalDownline: ${totalReferrals}`);
    } else {
        console.warn('⚠️ Element #totalDownline not found');
    }
    
    // 2. Active
    const activeEl = document.getElementById('activeDownline');
    if (activeEl) {
        activeEl.textContent = activeReferrals;
        console.log(`✅ Updated activeDownline: ${activeReferrals}`);
    } else {
        console.warn('⚠️ Element #activeDownline not found');
    }
    
    // 3. Level 1 / Direct
    const level1El = document.getElementById('level1Count');
    if (level1El) {
        level1El.textContent = directReferrals;
        console.log(`✅ Updated level1Count: ${directReferrals}`);
    } else {
        console.warn('⚠️ Element #level1Count not found');
    }
    
    // 4. Earnings
    const earningsEl = document.getElementById('networkEarnings');
    if (earningsEl) {
        earningsEl.textContent = formatCurrencyDL(earnings);
        console.log(`✅ Updated networkEarnings: ${formatCurrencyDL(earnings)}`);
    } else {
        console.warn('⚠️ Element #networkEarnings not found');
    }
    
    // 5. Network Badge (header)
    const networkCount = document.getElementById('networkCount');
    if (networkCount) {
        networkCount.textContent = totalReferrals;
        console.log(`✅ Updated networkCount: ${totalReferrals}`);
    } else {
        console.warn('⚠️ Element #networkCount not found');
    }
    
    // ============================================================
    // UPDATE LOCKED BALANCE (if exists)
    // ============================================================
    const lockedBalanceEl = document.getElementById('locked-wallet-Balance');
    if (lockedBalanceEl && breakdown.locked_wallet_balance !== undefined) {
        const lockedBalance = breakdown.locked_wallet_balance || 0;
        lockedBalanceEl.textContent = formatCurrencyDL(lockedBalance);
        console.log(`✅ Updated locked-wallet-Balance: ${lockedBalance}`);
    }
}

// ============================================================
// FORMAT CURRENCY HELPER
// ============================================================
function formatCurrencyDL(amount) {
    if (!amount || amount === 0) return 'UGX 0';
    const num = typeof amount === 'string' ? parseFloat(amount) : amount;
    return `UGX ${num.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}
// ============================================================
// UPDATE REFERRAL LINK - FIXED
// ============================================================
async function updateReferralLink(data) {
    const linkEl = document.getElementById('referralLink');
    if (!linkEl) return;
    
    // Try to get referral link from data (if passed)
    let link = data.referralLink || data.user?.referralLink || '';
    let code = data.referralCode || data.user?.referralCode || '';
    
    // If we already have it, use it
    if (link) {
        linkEl.value = link;
        console.log(`🔗 Referral link from data: ${link}`);
        return;
    }
    
    // If we have code but no link, build it
    if (code) {
        link = `${window.location.origin}?ref=${code}`;
        linkEl.value = link;
        console.log(`🔗 Referral link built from code: ${link}`);
        return;
    }
    
    // If still no link, fetch from profile endpoint
    try {
        console.log('🔗 Fetching referral link from profile endpoint...');
        const response = await fetch('/user/profile', {
            credentials: 'include',
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        
        if (!response.ok) throw new Error('Failed to fetch profile');
        
        const profileData = await response.json();
        console.log('📊 Profile Data:', profileData);
        
        // Try multiple paths
        const user = profileData.user || profileData || {};
        const referralCode = user.referralCode || user.referral_code || profileData.referralCode || '';
        const referralLink = user.referralLink || user.referral_link || profileData.referralLink || '';
        
        if (referralLink) {
            linkEl.value = referralLink;
            console.log(`🔗 Referral link from profile: ${referralLink}`);
        } else if (referralCode) {
            link = `${window.location.origin}?ref=${referralCode}`;
            linkEl.value = link;
            console.log(`🔗 Referral link built from profile code: ${link}`);
        } else {
            linkEl.value = `${window.location.origin}?ref=`;
            console.warn('⚠️ No referral code found in profile');
        }
        
    } catch (error) {
        console.error('❌ Failed to fetch referral link:', error);
        linkEl.value = `${window.location.origin}?ref=`;
    }
}

// ============================================================
// MAIN LOAD FUNCTION - Updated
// ============================================================
async function loadNetworkData() {
    try {
        const response = await fetch('/api/user/total-earnings', {
            credentials: 'include',
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });

        if (!response.ok) throw new Error('Failed to load network data');

        const data = await response.json();
        console.log('📊 Full Network Data:', data);
        
        // Update stats
        updateNetworkStats(data);
        
        // ✅ Update referral link - pass data or fetch separately
        await updateReferralLink(data);
        
    } catch (error) {
        console.error('❌ Failed to load network data:', error);
        setFallbackValues();
        // Try to load referral link anyway
        await updateReferralLink({});
    }
}


// ============================================================
// UPDATE REFERRAL LINK
// ============================================================


// ============================================================
// FALLBACK VALUES
// ============================================================
function setFallbackValues() {
    const elements = {
        'totalDownline': '0',
        'activeDownline': '0',
        'level1Count': '0',
        'networkEarnings': 'UGX 0',
        'networkCount': '0',
        'locked-wallet-Balance': 'UGX 0'
    };
    
    Object.keys(elements).forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = elements[id];
        }
    });
}

// ============================================================
// INIT
// ============================================================
document.addEventListener('DOMContentLoaded', function() {
    console.log('👥 Network Controller Initialized');
    loadNetworkData();
    
    // Auto-refresh every 60 seconds
    setInterval(loadNetworkData, 60000);
    
    // Manual refresh
    window.refreshNetwork = loadNetworkData;
});