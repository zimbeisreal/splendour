

   // Group Modal Functions
function openGroupModal(groupType) {
    const modal = document.getElementById(groupType + 'Modal');
    modal.style.display = 'flex';
    setTimeout(() => {
        modal.querySelector('.group-modal').classList.add('active');
    }, 10);
}

function closeGroupModal(groupType) {
    const modal = document.getElementById(groupType + 'Modal');
    modal.querySelector('.group-modal').classList.remove('active');
    setTimeout(() => {
        modal.style.display = 'none';
    }, 300);
}

function registerGroup(size) {
    // Redirect to registration page with group size parameter
    window.location.href = `/register?group_size=${size}`;
}

// Close modal when clicking outside
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('group-modal-overlay')) {
        const modals = document.querySelectorAll('.group-modal-overlay');
        modals.forEach(modal => {
            modal.querySelector('.group-modal').classList.remove('active');
            setTimeout(() => {
                modal.style.display = 'none';
            }, 300);
        });
    }
});
/**
 * express - User Profile Module
 * Handles user data loading, profile display, and deposit reference generation
 * @module profile
 */

(function() {
    'use strict';

    // ============================================
    // CONFIGURATION
    // ============================================
    const CONFIG = {
        API_ENDPOINT: '/user/profile',
        REFERENCE_PREFIX: 'express00',
        FALLBACK_REFERENCE: '0000',
        CURRENCY_LOCALE: 'en-UG'
    };

    // ============================================
    // DOM CACHE - Single source of truth
    // ============================================
    const DOM = {
        // User elements
        username: document.getElementById('username'),
        referralLink: document.getElementById('referralLink'),
        userId: document.getElementById('user-id'),
        heroActivePackages: document.getElementById('heroActivePackages'),
        actualBalance: document.getElementById('actual-balance'),
        
        // Deposit reference
        userReference: document.getElementById('userReference'),
        
        // Package elements
        packageContainer: document.getElementById('package'),
        totalInvested: document.getElementById('total-invested'),
        totalReturns: document.getElementById('total-returns'),
        
        // Other elements
        memberSince: document.getElementById('memberSince'),
        isVerified: document.getElementById('isVerified'),
        phone: document.getElementById('phone'),
        referralCode: document.getElementById('referral_code'),
        bonus: document.getElementById('bonus'),
        referralBonus: document.getElementById('referral-bonus')
    };

    // ============================================
    // UTILITY FUNCTIONS
    // ============================================
    
    /**
     * Format currency for Uganda Shillings
     * @param {number} amount - The amount to format
     * @returns {string} Formatted currency string
     */
    const formatCurrency = (amount) => {
        if (amount === undefined || amount === null || isNaN(amount)) return '0';
        return new Intl.NumberFormat(CONFIG.CURRENCY_LOCALE).format(amount);
    };

    /**
     * Safely get element value with fallback
     * @param {string} id - Element ID
     * @param {*} fallback - Fallback value
     * @returns {*} Element value or fallback
     */
    const safeGetElementValue = (id, fallback = 'N/A') => {
        const element = document.getElementById(id);
        return element ? element.value || fallback : fallback;
    };

    /**
     * Safely set element text content
     * @param {HTMLElement} element - DOM element
     * @param {*} value - Value to set
     * @param {*} fallback - Fallback value
     */
    const safeSetText = (element, value, fallback = 'N/A') => {
        if (element) {
            element.textContent = value || fallback;
        }
    };

    /**
     * Safely set element value
     * @param {HTMLElement} element - DOM element
     * @param {*} value - Value to set
     * @param {*} fallback - Fallback value
     */
    const safeSetValue = (element, value, fallback = 'N/A') => {
        if (element) {
            element.value = value || fallback;
        }
    };

    // ============================================
    // CORE FUNCTIONS
    // ============================================

    /**
     * Set deposit reference with user ID
     * @param {string|number} userId - User ID from backend
     */
    const setDepositReference = (userId) => {
        const referenceInput = DOM.userReference;
        
        if (!referenceInput) {
            console.warn('Deposit reference input not found');
            return;
        }

        if (userId && userId !== 'N/A' && userId !== 'undefined') {
            const formattedRef = `${CONFIG.REFERENCE_PREFIX}${userId}`;
            referenceInput.value = formattedRef;
            console.log('✅ Deposit reference set:', formattedRef);
        } else {
            referenceInput.value = CONFIG.FALLBACK_REFERENCE;
            console.warn('⚠️ Using fallback reference - no valid user ID');
        }
    };

    /**
     * Calculate and display package statistics
     * @param {Array} packages - User's packages array
     */
    const displayPackageStats = (packages) => {
        if (!packages || !Array.isArray(packages)) {
            console.warn('No packages data available');
            return;
        }

        // Calculate totals
        const totalInvested = packages.reduce((sum, pkg) => sum + (pkg.amount || 0), 0);
        const totalReturns = packages.reduce((sum, pkg) => sum + (pkg.total_returns || 0), 0);

        // Update DOM
        if (DOM.totalInvested) {
            DOM.totalInvested.textContent = `UGX ${formatCurrency(totalInvested)}`;
        }
        
        if (DOM.totalReturns) {
            DOM.totalReturns.textContent = `UGX ${formatCurrency(totalReturns)}`;
        }
    };

    /**
     * Render error state in package container
     */
    const renderError = () => {
        const container = DOM.packageContainer;
        if (container) {
            container.innerHTML = `
                <div class="error-message">
                    <i class="fas fa-exclamation-circle"></i>
                    <p>Error loading profile. Please refresh the page.</p>
                    <button onclick="location.reload()" class="express-btn express-btn-primary">
                        <i class="fas fa-sync-alt"></i> Retry
                    </button>
                </div>
            `;
        }
    };

    /**
     * Initialize user profile with data from backend
     * @param {Object} user - User data from API
     */
    const initializeProfile = (user) => {
        console.log('📊 Initializing user profile:', user);

        try {
            // 1. Set user details
            safeSetValue(DOM.referralLink, user.referralLink);
            safeSetText(DOM.username, user.username);
            safeSetText(DOM.heroActivePackages, user.active_packages_count || 0);
            
            // Set balance
            if (DOM.actualBalance) {
                DOM.actualBalance.textContent = formatCurrency(user.actualBalance || 0);
            }

            // 2. Set user ID and deposit reference (MOST IMPORTANT)
            const userId = user.id || user.userId || user.user_id || 'N/A';
            
            // Display user ID if element exists
            safeSetText(DOM.userId, userId);
            
            // Set deposit reference
            setDepositReference(userId);

            // 3. Display package statistics
            displayPackageStats(user.packages);

            // 4. Set optional fields if they exist
            safeSetText(DOM.memberSince, 
                user.memberSince ? new Date(user.memberSince).toLocaleDateString() : null
            );
            safeSetText(DOM.isVerified, user.isVerified ? 'Yes' : 'No');
            safeSetText(DOM.phone, user.phone);
            safeSetText(DOM.referralCode, user.referralCode);
            
            if (DOM.bonus) {
                DOM.bonus.textContent = formatCurrency(user.bonus);
            }
            if (DOM.referralBonus) {
                DOM.referralBonus.textContent = formatCurrency(user.referralBonus || 0);
            }

            console.log('✅ Profile initialized successfully');

        } catch (error) {
            console.error('❌ Error initializing profile:', error);
            renderError();
        }
    };

    /**
     * Fetch user profile from API
     */
    const fetchUserProfile = () => {
        console.log('🔄 Fetching user profile...');
        
        fetch(CONFIG.API_ENDPOINT)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                return response.json();
            })
            .then(user => {
                initializeProfile(user);
            })
            .catch(error => {
                console.error('❌ Error fetching user profile:', error);
                renderError();
            });
    };

    // ============================================
    // EVENT LISTENERS
    // ============================================

    /**
     * Setup deposit button click handler
     * Refreshes reference when modal opens
     */
    const setupDepositButton = () => {
        const depositBtn = document.getElementById('depositBtn');
        if (depositBtn) {
            depositBtn.addEventListener('click', function() {
                // Refresh reference from user ID
                const userId = safeGetElementValue('userId') || 
                              document.getElementById('user-id')?.textContent || 
                              'N/A';
                setDepositReference(userId);
                
                // Open modal
                const modal = document.getElementById('depositModal');
                if (modal) {
                    modal.classList.add('active');
                    document.body.style.overflow = 'hidden';
                }
            });
        }
    };

    /**
     * Setup copy reference button
     */
    const setupCopyButton = () => {
        const copyBtn = document.getElementById('copyReferenceBtn');
        if (copyBtn) {
            copyBtn.addEventListener('click', function() {
                const refInput = DOM.userReference;
                if (!refInput) return;

                const refValue = refInput.value;
                
                // Use modern clipboard API with fallback
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(refValue)
                        .then(() => showCopySuccess(this))
                        .catch(() => fallbackCopy(refInput));
                } else {
                    fallbackCopy(refInput);
                }
            });
        }
    };

    /**
     * Show copy success feedback
     * @param {HTMLElement} button - The copy button element
     */
    const showCopySuccess = (button) => {
        const originalText = button.innerHTML;
        button.innerHTML = '<i class="fas fa-check"></i> Copied!';
        button.style.background = '#10B981';
        button.style.color = 'white';
        
        setTimeout(() => {
            button.innerHTML = originalText;
            button.style.background = '';
            button.style.color = '';
        }, 2000);
    };

    /**
     * Fallback copy method for older browsers
     * @param {HTMLInputElement} input - The input element to copy from
     */
    const fallbackCopy = (input) => {
        input.select();
        input.setSelectionRange(0, 99999);
        document.execCommand('copy');
        showToast('Reference copied!', 'success');
    };

    /**
     * Show toast notification
     * @param {string} message - Toast message
     * @param {string} type - Toast type (success, error, warning)
     */
    const showToast = (message, type = 'info') => {
        // Remove existing toasts
        document.querySelectorAll('.express-toast').forEach(t => t.remove());
        
        const toast = document.createElement('div');
        toast.className = `express-toast ${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'expressToastDown 0.3s forwards';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    };

    // ============================================
    // INITIALIZATION
    // ============================================

    /**
     * Main initialization function
     */
    const init = () => {
        console.log('🚀 express Profile Module Initializing...');
        
        // Fetch user profile
        fetchUserProfile();
        
        // Setup event listeners
        setupDepositButton();
        setupCopyButton();
        
        console.log('✅ express Profile Module Initialized');
    };

    // Run when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();



class EarningsDashboard {
    constructor(options = {}) {
        this.apiBaseUrl = options.apiBaseUrl || '';
        this.refreshInterval = options.refreshInterval || 300000;
        this.elements = {};
        console.log("🎯 EarningsDashboard created");
        this.init();
    }

    init() {
        console.log("🔄 Initializing dashboard...");
        this.cacheElements();
        this.bindEvents();
        this.loadEarnings();
        
        if (this.refreshInterval > 0) {
            setInterval(() => this.loadEarnings(), this.refreshInterval);
        }
    }

    cacheElements() {
        console.log("🔍 Caching HTML elements...");
        
        // Main period elements
        this.elements.today = document.getElementById('earningsToday');
        this.elements.week = document.getElementById('earningsWeek');
        this.elements.month = document.getElementById('earningsMonth');
        this.elements.total = document.getElementById('earningsTotal'); // Add this to HTML
        
        // Breakdown elements
        this.elements.referralBonus = document.getElementById('referral-bonus');
        this.elements.signupBonus = document.getElementById('bonus');
        this.elements.availableBalance = document.getElementById('available-balance');
        this.elements.walletBalance = document.getElementById('wallet-balance');
        this.elements.lockedBalance = document.getElementById('locked-wallet-Balance');
        this.elements.activeReferrals = document.getElementById('total-direct-referrals');
        
        // Log what we found
        console.log("📊 Elements found:", {
            today: !!this.elements.today,
            week: !!this.elements.week,
            month: !!this.elements.month,
            total: !!this.elements.total,
            referralBonus: !!this.elements.referralBonus,
            signupBonus: !!this.elements.signupBonus,
            availableBalance: !!this.elements.availableBalance,
            walletBalance: !!this.elements.walletBalance,
            lockedBalance: !!this.elements.lockedBalance,
            activeReferrals: !!this.elements.activeReferrals
        });

        // Create error container if needed
        this.elements.errorContainer = document.getElementById('earnings-error') || this.createErrorContainer();
    }

    createErrorContainer() {
        const container = document.createElement('div');
        container.id = 'earnings-error';
        container.className = 'alert alert-danger';
        container.style.display = 'none';
        
        const mainContainer = document.querySelector('.container, main, body');
        if (mainContainer) {
            mainContainer.prepend(container);
        }
        
        return container;
    }

    bindEvents() {
        const refreshBtn = document.getElementById('refresh-earnings');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadEarnings());
        }
    }

    async loadEarnings() {
        console.log("📡 Fetching earnings data from API...");
        
        try {
            this.setLoadingState(true);
            this.hideError();

            const response = await fetch('/api/user/total-earnings', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                credentials: 'same-origin'
            });

            console.log("📨 API Response status:", response.status);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log("✅ API Data received:", data);
            
            if (data.error) {
                throw new Error(data.message || data.error);
            }

            this.updateDisplay(data);
            this.setLoadingState(false);
            console.log("🎉 Dashboard updated successfully!");

        } catch (error) {
            console.error('❌ Failed to load earnings:', error);
            this.showError(error.message);
            this.setLoadingState(false);
        }
    }

    updateDisplay(data) {
        console.log("🖥️ Updating display with data...");
        
        // Update period totals (these are at root level)
        this.updateElement(this.elements.today, data.today);
        this.updateElement(this.elements.week, data.this_week);
        this.updateElement(this.elements.month, data.this_month);
        
        // Update lifetime total from lifetime_earnings.total
        if (data.lifetime_earnings && data.lifetime_earnings.total) {
            this.updateElement(this.elements.total, data.lifetime_earnings.total);
        }
        
        // Update breakdown - FIXED: Use data.breakdown (not data.breakdown inside breakdown)
        if (data.breakdown) {
           console.log("💰 Updating breakdown values:", data.breakdown);
    
            // Referral bonus from current breakdown
            //this.updateElement(this.elements.referralBonus, data.breakdown.referral_bonus);
            
            // Signup bonus from current breakdown
            this.updateElement(this.elements.signupBonus, data.breakdown.signup_bonus);
            
            // Available balance from current breakdown
            this.updateElement(this.elements.availableBalance, data.breakdown.available_balance);
            
            // Wallet balance from current breakdown
            this.updateElement(this.elements.walletBalance, data.breakdown.wallet_balance);
            //this.updateElement(this.elements.lockedBalance, data.breakdown.locked_wallet_balance);
            this.updateElement(this.elements.lockedBalance, data.breakdown.locked_wallet_balance);
            //  Enable/disable Transfer button based on locked balance
            updateTransferButton(parseFloat(data.breakdown.locked_wallet_balance || 0));            

        }
        
        // Update referral stats
        if (data.referral_stats) {
            console.log("👥 Updating referral stats:", data.referral_stats);
            
            // Use total_direct_referrals from referral_stats
            this.updateElement(this.elements.activeReferrals, data.referral_stats.total_direct_referrals);
        }
        
        // If you want to display lifetime referral bonus separately:
        if (data.lifetime_earnings && data.lifetime_earnings.breakdown) {
            console.log("📈 Lifetime referral bonus:", data.lifetime_earnings.breakdown.referral_bonus);
            // You could update a separate element here if needed
        }
    }

    updateElement(element, value) {
        if (element) {
            // Format as currency with 2 decimal places if it's a number
            let displayValue = value;
            if (value !== undefined && value !== null && !isNaN(parseFloat(value))) {
                const numValue = parseFloat(value);
                displayValue = numValue.toLocaleString('en-US', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                });
            } else if (value === undefined || value === null) {
                displayValue = '0.00';
            }
            
            element.textContent = displayValue;
            console.log(`✅ Updated ${element.id} to:`, displayValue);
        } else {
            console.warn("⚠️ Element not found for update");
        }
    }

    setLoadingState(isLoading) {
        // Add loading indicators if needed
        const loader = document.getElementById('earnings-loader');
        if (loader) {
            loader.style.display = isLoading ? 'block' : 'none';
        }
    }

    showError(message) {
        if (this.elements.errorContainer) {
            this.elements.errorContainer.textContent = message;
            this.elements.errorContainer.style.display = 'block';
        }
    }

    hideError() {
        if (this.elements.errorContainer) {
            this.elements.errorContainer.style.display = 'none';
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.earningsDashboard = new EarningsDashboard();
});


function updateTransferButton(lockedBalance) {
    const btn = document.getElementById('transferBtn');
    if (!btn) return;

    if (!lockedBalance || lockedBalance <= 34000) {
        btn.disabled = true;
        btn.title = 'No locked balance to Transfer';
    } else {
        btn.disabled = false;
        btn.title = `Transfer UGX ${lockedBalance.toLocaleString()} to deposit balance`;
    }
}



class DailyBonusNotifier {
    constructor() {
        this.notificationContainer = null;
        this.init();
    }

    init() {
        // Create notification container
        this.createNotificationContainer();
        
        // Check for new bonuses on page load
        this.checkForNewBonuses();
        
        // Set up periodic checks (every 30 seconds)
        setInterval(() => this.checkForNewBonuses(), 90000);
    }

    createNotificationContainer() {
        this.notificationContainer = document.createElement('div');
        this.notificationContainer.id = 'bonus-notifications';
        this.notificationContainer.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 10000;
            max-width: 350px;
        `;
        document.body.appendChild(this.notificationContainer);
    }

    async checkForNewBonuses() {
        try {
            const response = await fetch('/api/user/today-bonus');
            const data = await response.json();
            
            if (data.has_bonus && data.amount > 0) {
                this.showBonusNotification(data.amount, data.package_name);
                
                // Mark as seen to prevent duplicate notifications
                await this.markBonusAsSeen(data.bonus_id);
            }
        } catch (error) {
            console.log('Error checking bonuses:', error);
        }
    }

    showBonusNotification(amount, packageName = '') {
        // Check if notification already exists
        const existingNotification = document.querySelector('.bonus-notification');
        if (existingNotification) {
            existingNotification.remove();
        }

        const notification = document.createElement('div');
        notification.className = 'bonus-notification';
        notification.style.cssText = `
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 20px;
            margin-bottom: 10px;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            animation: slideIn 0.5s ease-out;
            position: relative;
            min-width: 300px;
        `;

        const message = packageName 
            ? `Your daily bonus of $${amount} for ${packageName} has been paid! 🎉`
            : `Your daily bonus of $${amount} has been paid! 🎉`;

        notification.innerHTML = `
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <div>
                    <div style="font-weight: bold; font-size: 16px; margin-bottom: 5px;">Daily Bonus Paid!</div>
                    <div style="font-size: 14px; opacity: 0.9;">${message}</div>
                </div>
                <button class="close-bonus-notification" style="background: none; border: none; color: white; font-size: 18px; cursor: pointer; padding: 0; margin-left: 10px;">×</button>
            </div>
        `;

        // Add close button functionality
        notification.querySelector('.close-bonus-notification').addEventListener('click', () => {
            this.removeNotification(notification);
        });

        // Auto-remove after 8 seconds
        setTimeout(() => {
            this.removeNotification(notification);
        }, 8000);

        this.notificationContainer.appendChild(notification);

        // Add CSS animation
        this.addNotificationStyles();
    }

    removeNotification(notification) {
        notification.style.animation = 'slideOut 0.5s ease-in';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 500);
    }

    addNotificationStyles() {
        if (!document.getElementById('bonus-notification-styles')) {
            const styles = document.createElement('style');
            styles.id = 'bonus-notification-styles';
            styles.textContent = `
                @keyframes slideIn {
                    from {
                        transform: translateX(100%);
                        opacity: 0;
                    }
                    to {
                        transform: translateX(0);
                        opacity: 1;
                    }
                }
                @keyframes slideOut {
                    from {
                        transform: translateX(0);
                        opacity: 1;
                    }
                    to {
                        transform: translateX(100%);
                        opacity: 0;
                    }
                }
                .bonus-notification:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 6px 20px rgba(0,0,0,0.25);
                    transition: all 0.3s ease;
                }
            `;
            document.head.appendChild(styles);
        }
    }

    async markBonusAsSeen(bonusId) {
        try {
            await fetch('/api/user/mark-bonus-seen', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ bonus_id: bonusId })
            });
        } catch (error) {
            console.log('Error marking bonus as seen:', error);
        }
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    new DailyBonusNotifier();
});

// Add this to your dashboard to show recent bonuses
class BonusDashboard {
    constructor() {
        this.container = document.getElementById('bonus-history');
        if (this.container) {
            this.loadBonusHistory();
        }
    }

    async loadBonusHistory() {
        try {
            const response = await fetch('/api/user/bonus-history');
            const bonuses = await response.json();
            
            this.renderBonusHistory(bonuses);
        } catch (error) {
            console.log('Error loading bonus history:', error);
        }
    }

    renderBonusHistory(bonuses) {
        if (!bonuses.length) {
            this.container.innerHTML = '<p>No bonus history available.</p>';
            return;
        }

        const html = `
            <div class="bonus-history-header">
                <h3>Recent Daily Bonuses</h3>
            </div>
            <div class="bonus-list">
                ${bonuses.map(bonus => `
                    <div class="bonus-item">
                        <div class="bonus-amount">+$${bonus.amount}</div>
                        <div class="bonus-details">
                            <div class="bonus-type">Daily Bonus</div>
                            <div class="bonus-date">${new Date(bonus.date).toLocaleDateString()}</div>
                        </div>
                        <div class="bonus-package">Package #${bonus.package_id}</div>
                    </div>
                `).join('')}
            </div>
        `;

        this.container.innerHTML = html;
    }
}

// notifications.js - SINGLE CLEAN VERSION

// Helper function - define once
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Single loadNotifications function
async function loadNotifications() {
    // Use the correct container from your HTML
    const container = document.getElementById('notificationsContent');
    const countElement = document.getElementById('notificationsCount');
    
    // Safety check - exit if elements don't exist
    if (!container) {
        console.warn('notificationsContent element not found in DOM');
        return;
    }
    
    try {
        const response = await fetch('/api/notifications', {
            headers: {
                'Content-Type': 'application/json'
            
            }
        });
        
        if (!response.ok) throw new Error('Failed to load notifications');
        
        const notifications = await response.json();
        
        // Update count if element exists
        if (countElement) {
            const unreadCount = notifications.filter(n => !n.is_read).length;
            countElement.textContent = unreadCount;
        }
        
        if (!notifications || notifications.length === 0) {
            container.innerHTML = `
                <div class="text-center py-4">
                    <i class="fas fa-bell-slash text-muted mb-2" style="font-size: 24px;"></i>
                    <p class="text-muted mb-0">No Messages yet</p>
                </div>
            `;
            return;
        }
        
        // Show only last 5 notifications
        const recent = notifications.slice(0, 5);
        
        let html = '<div class="notifications-list">';
        for (let notif of recent) {
            const date = notif.created_at ? new Date(notif.created_at).toLocaleDateString() : 'Recent';
            html += `
                <div class="notification-item ${notif.is_read ? 'read' : ''}" data-id="${notif.id}">
                    <div class="notification-icon">
                        <i class="fas ${notif.is_read ? 'fa-envelope-open' : 'fa-envelope'}"></i>
                    </div>
                    <div class="notification-content">
                        <div class="notification-message">${escapeHtml(notif.message)}</div>
                        <div class="notification-date">${date}</div>
                    </div>
                    ${!notif.is_read ? '<div class="notification-unread-dot"></div>' : ''}
                </div>
            `;
        }
        html += '</div>';
        
        container.innerHTML = html;
        
        // Add click handlers to mark as read
        document.querySelectorAll('.notification-item').forEach(item => {
            item.addEventListener('click', async () => {
                const id = item.dataset.id;
                if (!item.classList.contains('read')) {
                    try {
                        await apiCache.fetch(`/api/notifications/${id}/read`, { method: 'PUT' });
                        item.classList.add('read');
                        const dot = item.querySelector('.notification-unread-dot');
                        if (dot) dot.remove();
                        
                        // Update unread count
                        if (countElement) {
                            const currentCount = parseInt(countElement.textContent) || 0;
                            countElement.textContent = Math.max(0, currentCount - 1);
                        }
                    } catch (err) {
                        console.error('Failed to mark as read:', err);
                    }
                }
            });
        });
        
    } catch (err) {
        console.error('Error loading notifications:', err);
        container.innerHTML = `
            <div class="text-center py-4">
                <i class="fas fa-exclamation-triangle text-warning mb-2" style="font-size: 24px;"></i>
                <p class="text-muted mb-0">Failed to load notifications</p>
                <button onclick="loadNotifications()" class="btn btn-sm btn-outline-primary mt-2">
                    <i class="fas fa-sync-alt"></i> Retry
                </button>
            </div>
        `;
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        if (document.getElementById('notificationsContent')) {
            loadNotifications();
            // Refresh every 30 seconds
            setInterval(loadNotifications, 30000);
        }
    });
} else {
    if (document.getElementById('notificationsContent')) {
        loadNotifications();
        setInterval(loadNotifications, 120000);
    }
}
// Update function mapping
function updateDashboardUI(data) {
    // Wallet balances
    document.getElementById('wallet-balance').textContent = formatNumber(data.wallet_balance || 0);
    document.getElementById('available-balance-subnote').textContent = formatNumber(data.available_balance || 0);
    document.getElementById('available-balance-mini').textContent = formatNumber(data.available_balance || 0);
    
    // Mini stats
    document.getElementById('actual-balance').textContent = formatNumber(data.actual_balance || 0);
    document.getElementById('referral-bonus-mini').textContent = formatNumber(data.referralBonus || 0);
    document.getElementById('bonus-mini').textContent = formatNumber(data.bonus || 0);
    document.getElementById('earnings-total-mini').textContent = formatNumber(data.lifetime_earnings?.total || 0);
    
    // Financial summary
    document.getElementById('earnings-today').textContent = formatNumber(data.today || 0);
    document.getElementById('earnings-week').textContent = formatNumber(data.this_week || 0);
    document.getElementById('earnings-total').textContent = formatNumber(data.lifetime_earnings?.total || 0);
    
    // Main section
    document.getElementById('main-direct-referrals').textContent = data.referral_stats?.direct_referrals_count || 0;
    document.getElementById('main-referral-bonus').textContent = formatNumber(data.referral_bonus || 0);
    
    // Profile
    document.getElementById('profile-email').textContent = data.email || 'Not set';
    document.getElementById('profile-phone').textContent = data.phone || 'Not set';
    document.getElementById('profile-verified').textContent = data.is_verified ? 'Yes' : 'No';
    document.getElementById('profile-join-date').textContent = formatDate(data.memberSince);
    
    // Direct referrals
    const referralCount = data.referral_stats?.direct_referrals_count || 0;
    document.getElementById('total-direct-referrals-mini').textContent = referralCount;
    document.getElementById('main-direct-referrals').textContent = referralCount;
}



// ============================================================
// WELCOME MODAL CONTROLLER
// ============================================================
// ============================================================
// WELCOME MODAL CONTROLLER - Show on every login
// ============================================================

(function() {
    'use strict';

    const CONFIG = {
        STORAGE_KEY: 'adidas_welcome_seen',
        WHATSAPP_GROUP: '',
        TELEGRAM_CHANNEL: '',
        DISPLAY_DELAY: 600,
    };

    const modal = document.getElementById('welcomeModal');
    const skipBtn = document.getElementById('skipWelcome');
    const notificationToggle = document.getElementById('enableNotifications');
    const whatsappLink = document.querySelector('.welcome-link.whatsapp');
    const telegramLink = document.querySelector('.welcome-link.telegram');

    function shouldShowModal() {
        const hasSeen = localStorage.getItem(CONFIG.STORAGE_KEY) === 'true';
        const isProfilePage = window.location.pathname.includes('/profile');
        const justLoggedIn = sessionStorage.getItem('adidas_just_logged_in') === 'true';
        const urlParam = new URLSearchParams(window.location.search).get('show_welcome') === 'true';
        
        // ✅ Show modal on every login
        return isProfilePage && (justLoggedIn || urlParam) && !hasSeen;
    }

    function showModal() {
        if (!modal) return;
        setTimeout(() => {
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
        }, CONFIG.DISPLAY_DELAY);
    }

    function hideModal(shouldRemember = true) {
        if (!modal) return;
        modal.classList.remove('active');
        document.body.style.overflow = '';
        
        if (shouldRemember) {
            localStorage.setItem(CONFIG.STORAGE_KEY, 'true');
            sessionStorage.removeItem('adidas_just_logged_in');
        }
        
        // Clean URL
        const url = new URL(window.location);
        url.searchParams.delete('show_welcome');
        window.history.replaceState({}, '', url);
    }

    function handleSocialClick(platform, url) {
        window.open(url, '_blank');
        localStorage.setItem('adidas_social_joined', platform);
        localStorage.setItem('adidas_social_joined_at', new Date().toISOString());
        setTimeout(() => hideModal(true), 500);
    }

    function setupEventListeners() {
        if (skipBtn) {
            skipBtn.addEventListener('click', () => hideModal(true));
        }

        if (whatsappLink) {
            whatsappLink.addEventListener('click', (e) => {
                e.preventDefault();
                handleSocialClick('whatsapp', CONFIG.WHATSAPP_GROUP);
            });
        }

        if (telegramLink) {
            telegramLink.addEventListener('click', (e) => {
                e.preventDefault();
                handleSocialClick('telegram', CONFIG.TELEGRAM_CHANNEL);
            });
        }

        if (notificationToggle) {
            notificationToggle.addEventListener('change', function() {
                localStorage.setItem('adidas_notifications_enabled', this.checked ? 'true' : 'false');
            });
        }

        if (modal) {
            modal.addEventListener('click', function(e) {
                if (e.target === modal) hideModal(true);
            });
        }

        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && modal?.classList.contains('active')) {
                hideModal(true);
            }
        });
    }

    function restorePreferences() {
        const notificationsEnabled = localStorage.getItem('adidas_notifications_enabled') === 'true';
        if (notificationToggle) {
            notificationToggle.checked = notificationsEnabled;
        }
    }

    function init() {
        console.log('🔔 Welcome Modal Initialized');
        restorePreferences();
        setupEventListeners();
        
        if (shouldShowModal()) {
            showModal();
        } else {
            sessionStorage.removeItem('adidas_just_logged_in');
        }
    }

    window.WelcomeModal = {
        show: showModal,
        hide: hideModal,
        isVisible: () => modal?.classList.contains('active') || false,
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();



// ============================================================
// express - WELCOME MODAL CONTROLLER
// ============================================================

(function() {
    'use strict';

    // ============================================================
    // DOM REFS
    // ============================================================
    const modal = document.getElementById('welcomeModal');
    const skipBtn = document.getElementById('skipWelcome');
    const closeBtn = document.getElementById('closeWelcomeModal');
    const notificationToggle = document.getElementById('enableNotifications');
    const whatsappLink = document.getElementById('whatsappLink');
    const telegramLink = document.getElementById('telegramLink');

    // ============================================================
    // STORAGE KEYS
    // ============================================================
    const STORAGE_KEY = 'express_welcome_seen';
    const SESSION_KEY = 'express_just_logged_in';

    // ============================================================
    // TOAST
    // ============================================================
    function showToast(message, type = 'info', duration = 3000) {
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
    // CHECK IF MODAL SHOULD SHOW
    // ============================================================
    function shouldShowModal() {
        const hasSeen = localStorage.getItem(STORAGE_KEY) === 'true';
        const justLoggedIn = sessionStorage.getItem(SESSION_KEY) === 'true';
        const urlParam = new URLSearchParams(window.location.search).get('show_welcome') === 'true';
        
        // Don't show on mobile if already seen
        if (hasSeen) return false;
        
        // Show if: just logged in OR URL param
        return justLoggedIn || urlParam;
    }

    // ============================================================
    // SHOW MODAL
    // ============================================================
    function showModal() {
        if (!modal) return;

        setTimeout(() => {
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
        }, 300);
    }

    // ============================================================
    // HIDE MODAL
    // ============================================================
    function hideModal(shouldRemember = true) {
        if (!modal) return;

        modal.classList.remove('active');
        document.body.style.overflow = '';

        if (shouldRemember) {
            localStorage.setItem(STORAGE_KEY, 'true');
            sessionStorage.removeItem(SESSION_KEY);
            
            // Clean URL
            const url = new URL(window.location);
            url.searchParams.delete('show_welcome');
            window.history.replaceState({}, '', url);
        }
    }

    // ============================================================
    // HANDLE SOCIAL LINK CLICKS
    // ============================================================
    function handleSocialClick(platform, url) {
        // Open in new tab
        window.open(url, '_blank');
        
        // Store engagement
        localStorage.setItem('express_social_joined', platform);
        localStorage.setItem('express_social_joined_at', new Date().toISOString());
        
        showToast(`✅ Joined ${platform} group!`, 'success');
        
        // Close modal after short delay
        setTimeout(() => {
            hideModal(true);
        }, 600);
    }

    // ============================================================
    // HANDLE NOTIFICATION TOGGLE
    // ============================================================
    function handleNotificationToggle() {
        const isChecked = notificationToggle?.checked || false;
        localStorage.setItem('express_notifications_enabled', isChecked ? 'true' : 'false');
        
        if (isChecked) {
            // Request notification permission
            if ('Notification' in window && Notification.permission === 'default') {
                Notification.requestPermission();
            }
            showToast('🔔 Notifications enabled!', 'success');
        } else {
            showToast('🔕 Notifications disabled', 'info');
        }
    }

    // ============================================================
    // SET JUST LOGGED IN FLAG
    // ============================================================
    function setJustLoggedIn() {
        sessionStorage.setItem(SESSION_KEY, 'true');
        // Reset seen status for new login
        localStorage.removeItem(STORAGE_KEY);
    }

    // ============================================================
    // RESTORE PREFERENCES
    // ============================================================
    function restorePreferences() {
        const notificationsEnabled = localStorage.getItem('express_notifications_enabled') === 'true';
        if (notificationToggle) {
            notificationToggle.checked = notificationsEnabled;
        }
    }

    // ============================================================
    // SETUP EVENT LISTENERS
    // ============================================================
    function setupEventListeners() {
        // Skip button
        if (skipBtn) {
            skipBtn.addEventListener('click', () => hideModal(true));
        }

        // Close button
        if (closeBtn) {
            closeBtn.addEventListener('click', () => hideModal(true));
        }

        // WhatsApp link
        if (whatsappLink) {
            whatsappLink.addEventListener('click', (e) => {
                e.preventDefault();
                handleSocialClick('WhatsApp', whatsappLink.href);
            });
        }

        // Telegram link
        if (telegramLink) {
            telegramLink.addEventListener('click', (e) => {
                e.preventDefault();
                handleSocialClick('Telegram', telegramLink.href);
            });
        }

        // Notification toggle
        if (notificationToggle) {
            notificationToggle.addEventListener('change', handleNotificationToggle);
        }

        // Close on overlay click
        if (modal) {
            modal.addEventListener('click', function(e) {
                if (e.target === modal) {
                    hideModal(true);
                }
            });
        }

        // Escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && modal?.classList.contains('active')) {
                hideModal(true);
            }
        });
    }

    // ============================================================
    // INIT
    // ============================================================
    function init() {
        console.log('🏠 express Welcome Modal Initialized');

        // Restore preferences
        restorePreferences();

        // Setup events
        setupEventListeners();

        // Check if modal should show
        if (shouldShowModal()) {
            showModal();
        } else {
            // Clean up session flag if not showing
            sessionStorage.removeItem(SESSION_KEY);
            
            // Clean URL
            const url = new URL(window.location);
            if (url.searchParams.has('show_welcome')) {
                url.searchParams.delete('show_welcome');
                window.history.replaceState({}, '', url);
            }
        }
    }

    // ============================================================
    // EXPOSE PUBLIC API
    // ============================================================
    window.WelcomeModal = {
        show: showModal,
        hide: hideModal,
        setJustLoggedIn: setJustLoggedIn,
        isVisible: () => modal?.classList.contains('active') || false,
        reset: () => {
            localStorage.removeItem(STORAGE_KEY);
            sessionStorage.removeItem(SESSION_KEY);
        }
    };

    // ============================================================
    // AUTO-INIT
    // ============================================================
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();