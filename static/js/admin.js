
console.log("🚀 Admin dashboard script loaded");
// Configuration and Constants
const CONFIG = {
    API_BASE_URL: '',
    ENDPOINTS: {
        ADMIN_DATA: '/admin/data',
        USER_SEARCH: '/admin/search/users'
    },
    REFRESH_INTERVAL: 30000, // 30 seconds
    DEBOUNCE_DELAY: 500 // Search debounce delay
};

// Application State Management
const AppState = {
    adminData: null,
    lastUpdate: null,
    isLoading: false,
    searchQuery: '',
    currentView: 'dashboard'
};

// DOM Elements Cache
const DOM = {
    elements: {},
    
    // Initialize DOM element references
    init: function() {
        try {
            this.elements = {
                // Stats elements
                totalPayments: document.getElementById('total-payments'),
                totalUsers: document.getElementById('total-users'),
                activeUsers: document.getElementById('active-users'),
                dailyUsers: document.getElementById('daily-new-users'),
                totalBonus: document.getElementById('total-bonus'),
                pendingBonus: document.getElementById('pending-bonus'),
                pendingPayments: document.getElementById('pending-payments'),
                dailyInvestments: document.getElementById('daily-investments'),
                dailyPayouts: document.getElementById('daily-payouts'),

                
                // Change indicators
                paymentsChange: document.getElementById('payments-change'),
                usersChange: document.getElementById('users-change'),
                
                // Payment status elements
                successfulPayments: document.getElementById('successful-payments'),
                successfulAmount: document.getElementById('successful-amount'),
                pendingPaymentsCount: document.getElementById('pending-payments-count'),
                pendingAmount: document.getElementById('pending-amount'),
                failedPayments: document.getElementById('failed-payments'),
                failedAmount: document.getElementById('failed-amount'),
                declinedPayments: document.getElementById('declined-payments'),
                declinedAmount: document.getElementById('declined-amount'),
                cancelledPayments: document.getElementById('cancelled-payments'),
                cancelledAmount: document.getElementById('cancelled-amount'),
                
                // Alert badges
                pendingPaymentsBadge: document.getElementById('pending-payments-badge'),
                pendingBonusesBadge: document.getElementById('pending-bonuses-badge'),
                
                // Tables
                paymentsTableBody: document.getElementById('payments-table-body'),
                
                // Charts
                usersChart: document.getElementById('users-chart'),
                investmentsChart: document.getElementById('investments-chart'),
                
                // Search and controls
                adminSearchInput: document.getElementById('admin-search-input'),
                adminName: document.getElementById('admin-name'),
                
                // Navigation
                navDashboard: document.getElementById('nav-dashboard'),
                navUsers: document.getElementById('nav-users'),
                navPayments: document.getElementById('nav-payments'),
                navBonuses: document.getElementById('nav-bonuses'),
                navReports: document.getElementById('nav-reports'),
                navSettings: document.getElementById('nav-settings'),
                navLogout: document.getElementById('nav-logout'),
                
                // Quick actions
                actionAddUser: document.getElementById('action-add-user'),
                actionProcessBonus: document.getElementById('action-process-bonus'),
                actionManualPayment: document.getElementById('action-manual-payment'),
                actionGenerateReport: document.getElementById('action-generate-report'),
                actionSystemBackup: document.getElementById('action-system-backup'),
                actionBulkActions: document.getElementById('action-bulk-actions'),
                
                // View all links
                viewAllPayments: document.getElementById('view-all-payments')
            };
            
            // Validate critical elements exist
            this.validateRequiredElements();
            
        } catch (error) {
            console.error('DOM initialization failed:', error);
            this.showFatalError('Failed to initialize dashboard. Please refresh the page.');
        }
    },
    
    // Validate that critical elements exist
    validateRequiredElements: function() {
        const criticalElements = [
            'totalPayments', 'totalUsers', 'activeUsers', 'totalBonus',
            'pendingBonus', 'pendingPayments', 'paymentsTableBody'
        ];
        
        criticalElements.forEach(elementId => {
            if (!this.elements[elementId]) {
                throw new Error(`Critical element missing: ${elementId}`);
            }
        });
    },
    
    // Safe element text content update
    safeUpdateText: function(element, text) {
        if (element && typeof text !== 'undefined') {
            element.textContent = text;
        }
    },
    
    // Safe element HTML update
    safeUpdateHTML: function(element, html) {
        if (element && typeof html !== 'undefined') {
            element.innerHTML = html;
        }
    },
    
    // Show fatal error message
    showFatalError: function(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'fatal-error';
        errorDiv.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            background: #f44336;
            color: white;
            padding: 1rem;
            text-align: center;
            z-index: 10000;
            font-weight: bold;
        `;
        errorDiv.textContent = message;
        document.body.appendChild(errorDiv);
    }
};

// API Service Layer
const APIService = {
    /**
     * Generic API request handler
     */
    async request(endpoint, options = {}) {
        const url = endpoint.startsWith('http') ? endpoint : `${CONFIG.API_BASE_URL}${endpoint}`;
        
        const config = {
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                ...options.headers
            },
            ...options
        };
        
        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // Validate response structure
            if (!this.validateResponse(data)) {
                throw new Error('Invalid response format from server');
            }
            
            return data;
            
        } catch (error) {
            console.error(`API request failed for ${endpoint}:`, error);
            throw error;
        }
    },
    
    /**
     * Validate API response structure
     */
    validateResponse(data) {
        return data && typeof data === 'object';
    },
    
    /**
     * Fetch admin dashboard data
     */
    async fetchAdminData() {
        try {
            const data = await this.request(CONFIG.ENDPOINTS.ADMIN_DATA);
            return data;
        } catch (error) {
            console.error('Failed to fetch admin data:', error);
            throw new Error('Unable to load dashboard data. Please try again.');
        }
    },
    




    
    /**
     * Search users
     */
    async searchUsers(query) {
        if (!query || query.length < 2) return { users: [] };
        
        try {
            const data = await this.request(CONFIG.ENDPOINTS.USER_SEARCH, {
                method: 'POST',
                body: JSON.stringify({ query })
            });
            return data;
        } catch (error) {
            console.error('User search failed:', error);
            throw new Error('Search failed. Please try again.');
        }
    }
};

// ... after DOM and APIService definitions ...

// ✅ Add your updateDashboard function here
async function updateDashboard() {
    try {
        const stats = await APIService.fetchAdminData();
        
        console.log("✅ Raw API response:", stats);
        console.log("🔢 total_users =", stats.total_users);
        console.log("🧱 DOM element (total-users):", DOM.elements.totalUsers);

        const formattedTotal = Formatters.formatNumber(stats.total_users);
        console.log("🖨️ Formatted:", formattedTotal);

        DOM.safeUpdateText(DOM.elements.totalUsers, formattedTotal);
        DOM.safeUpdateText(DOM.elements.activeUsers, Formatters.formatNumber(stats.active_users));
        
    } catch (err) {
        console.error("Update failed:", err);
    }
}

// ... rest of your code ...



// Data Formatters and Utilities
const Formatters = {
    /**
     * Format currency values
     */
    formatCurrency(amount, currency = 'UGX') {
        if (typeof amount !== 'number') return '0';
        
        return new Intl.NumberFormat('en-UG', {
            style: 'currency',
            currency: currency,
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(amount);
    },
    
    /**
     * Format large numbers with abbreviations
     */
    formatNumber(num) {
        if (typeof num !== 'number') return '0';
        
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        } else if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toString();
    },
    
    /**
     * Format percentage changes
     */
    formatChange(change) {
        if (typeof change !== 'number') return '';
        
        const sign = change >= 0 ? '+' : '';
        return `${sign}${change.toFixed(1)}%`;
    },
    
    /**
     * Format date for display
     */
    formatDate(dateString) {
        if (!dateString) return 'N/A';
        
        try {
            return new Date(dateString).toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch (error) {
            return 'Invalid Date';
        }
    },
    
    /**
     * Generate status badge HTML
     */
    getStatusBadge(status, amount = null) {
        const statusConfig = {
            completed: { class: 'status-success', text: 'Completed' },
            pending: { class: 'status-warning', text: 'Pending' },
            failed: { class: 'status-danger', text: 'Failed' },
            declined: { class: 'status-info', text: 'Declined' },
            cancelled: { class: 'status-warning', text: 'Cancelled' }
        };
        
        const config = statusConfig[status] || { class: 'status-info', text: status };
        const amountText = amount ? ` (${this.formatCurrency(amount)})` : '';
        
        return `<span class="status-badge ${config.class}">${config.text}${amountText}</span>`;
    }
};

// UI Update Manager
const UIManager = {
    /**
     * Update all dashboard statistics
     */
    // updateStats(data) {
    //     if (!data || !data.stats) return;
        
    //     const stats = data.stats;
        
    //     // Update main statistics
    //     DOM.safeUpdateText(DOM.elements.totalPayments, Formatters.formatCurrency(stats.total_payments));
    //     DOM.safeUpdateText(DOM.elements.totalUsers, Formatters.formatNumber(stats.total_users));
    //     DOM.safeUpdateText(DOM.elements.activeUsers, Formatters.formatNumber(stats.active_users));
    //     DOM.safeUpdateText(DOM.elements.totalBonus, Formatters.formatCurrency(stats.total_bonus));
    //     DOM.safeUpdateText(DOM.elements.pendingBonus, Formatters.formatCurrency(stats.pending_bonus));
    //     DOM.safeUpdateText(DOM.elements.pendingPayments, Formatters.formatNumber(stats.pending_payments));
    //     DOM.safeUpdateText(DOM.elements.dailyInvestments, Formatters.formatCurrency(stats.daily_investments));
    //     DOM.safeUpdateText(DOM.elements.dailyPayouts, Formatters.formatCurrency(stats.daily_payouts));
        
       updateStats(data) {
    if (!data) return;
    
    const stats = data.stats || data; // fallback to top-level
    DOM.safeUpdateText(DOM.elements.totalPayments, Formatters.formatNumber(stats.total_payments));
    DOM.safeUpdateText(DOM.elements.totalUsers, Formatters.formatNumber(stats.total_users));
    DOM.safeUpdateText(DOM.elements.activeUsers, Formatters.formatNumber(stats.active_users));
    DOM.safeUpdateText(DOM.elements.totalBonus, Formatters.formatNumber(stats.total_bonus));
    DOM.safeUpdateText(DOM.elements.pendingBonus, Formatters.formatCurrency(stats.pending_bonus));
    DOM.safeUpdateText(DOM.elements.pendingPayments, Formatters.formatNumber(stats.pending_payments));
    DOM.safeUpdateText(DOM.elements.dailyInvestments, Formatters.formatCurrency(stats.daily_investments || 0));
    DOM.safeUpdateText(DOM.elements.dailyPayouts, Formatters.formatCurrency(stats.daily_payouts));
    DOM.safeUpdateText(DOM.elements.dailyUsers, Formatters.formatNumber(stats.daily_new_users));
        // Update change indicators
        this.updateChangeIndicators(stats);
        
        // Update alert badges
        this.updateAlertBadges(stats);
    },
    
    /**
     * Update change percentage indicators
     */
    updateChangeIndicators(stats) {
        if (stats.payments_change !== undefined) {
            const paymentsChangeElement = DOM.elements.paymentsChange;
            if (paymentsChangeElement) {
                const change = stats.payments_change || 0;
                const changeClass = change >= 0 ? 'change-positive' : 'change-negative';
                const icon = change >= 0 ? 'fa-arrow-up' : 'fa-arrow-down';
                
                DOM.safeUpdateHTML(paymentsChangeElement, `
                    <i class="fas ${icon}"></i>
                    <span>${Formatters.formatChange(change)}</span>
                `);
                paymentsChangeElement.className = `stat-change ${changeClass}`;
            }
        }
        
        if (stats.users_change !== undefined) {
            const usersChangeElement = DOM.elements.usersChange;
            if (usersChangeElement) {
                const change = stats.users_change || 0;
                const changeClass = change >= 0 ? 'change-positive' : 'change-negative';
                const icon = change >= 0 ? 'fa-arrow-up' : 'fa-arrow-down';
                
                DOM.safeUpdateHTML(usersChangeElement, `
                    <i class="fas ${icon}"></i>
                    <span>${Formatters.formatChange(change)}</span>
                `);
                usersChangeElement.className = `stat-change ${changeClass}`;
            }
        }
    },
    
    /**
     * Update alert badges in navigation
     */
    updateAlertBadges(stats) {
        // Pending payments badge
        if (DOM.elements.pendingPaymentsBadge && stats.pending_payments) {
            DOM.safeUpdateText(DOM.elements.pendingPaymentsBadge, 
                stats.pending_payments > 99 ? '99+' : stats.pending_payments.toString());
        }
        
        // Pending bonuses badge
        if (DOM.elements.pendingBonusesBadge && stats.pending_bonus_count) {
            DOM.safeUpdateText(DOM.elements.pendingBonusesBadge, 
                stats.pending_bonus_count > 99 ? '99+' : stats.pending_bonus_count.toString());
        }
    },
    
    /**
     * Update payment status overview
     */
    updatePaymentStatus(data) {
        if (!data || !data.payment_status) return;
        
        const status = data.payment_status;
        
        DOM.safeUpdateText(DOM.elements.successfulPayments, Formatters.formatNumber(status.successful?.count || 0));
        DOM.safeUpdateText(DOM.elements.successfulAmount, Formatters.formatCurrency(status.successful?.amount || 0));
        
        DOM.safeUpdateText(DOM.elements.pendingPaymentsCount, Formatters.formatNumber(status.pending?.count || 0));
        DOM.safeUpdateText(DOM.elements.pendingAmount, Formatters.formatCurrency(status.pending?.amount || 0));
        
        DOM.safeUpdateText(DOM.elements.failedPayments, Formatters.formatNumber(status.failed?.count || 0));
        DOM.safeUpdateText(DOM.elements.failedAmount, Formatters.formatCurrency(status.failed?.amount || 0));
        
        DOM.safeUpdateText(DOM.elements.declinedPayments, Formatters.formatNumber(status.declined?.count || 0));
        DOM.safeUpdateText(DOM.elements.declinedAmount, Formatters.formatCurrency(status.declined?.amount || 0));
        
        DOM.safeUpdateText(DOM.elements.cancelledPayments, Formatters.formatNumber(status.cancelled?.count || 0));
        DOM.safeUpdateText(DOM.elements.cancelledAmount, Formatters.formatCurrency(status.cancelled?.amount || 0));
    },
    
    /**
     * Update recent payments table
     */
    updateRecentPayments(data) {
        if (!data || !data.recent_payments || !DOM.elements.paymentsTableBody) return;
        
        const payments = data.recent_payments;
        
        if (payments.length === 0) {
            DOM.elements.paymentsTableBody.innerHTML = `
                <tr>
                    <td colspan="4" style="text-align: center; color: var(--neutral); padding: 2rem;">
                        <i class="fas fa-receipt" style="font-size: 2rem; margin-bottom: 0.5rem; display: block;"></i>
                        No recent payments
                    </td>
                </tr>
            `;
            return;
        }
        
        const rows = payments.map(payment => `
            <tr>
                <td>
                    <div style="font-weight: 600;">${this.escapeHTML(payment.user_name || 'N/A')}</div>
                    <div style="font-size: 0.8rem; color: var(--neutral);">${this.escapeHTML(payment.user_email || '')}</div>
                </td>
                <td style="font-weight: 700;">${Formatters.formatCurrency(payment.amount)}</td>
                <td>${Formatters.getStatusBadge(payment.status, payment.amount)}</td>
                <td style="font-size: 0.9rem; color: var(--neutral);">
                    ${Formatters.formatDate(payment.created_at)}
                </td>
            </tr>
        `).join('');
        
        DOM.elements.paymentsTableBody.innerHTML = rows;
    },
    
    /**
     * Update chart data (placeholder for chart library integration)
     */
    updateCharts(data) {
        if (!data || !data.charts) return;
        
        const charts = data.charts;
        
        // Users growth chart placeholder
        if (DOM.elements.usersChart && charts.users_growth) {
            // In a real implementation, this would initialize/update a chart library
            console.log('Users growth data:', charts.users_growth);
            // Example: ChartJS.updateChart('usersChart', charts.users_growth);
        }
        
        // Investment trends chart placeholder
        if (DOM.elements.investmentsChart && charts.investment_trends) {
            console.log('Investment trends data:', charts.investment_trends);
            // Example: ChartJS.updateChart('investmentsChart', charts.investment_trends);
        }
    },
    
    /**
     * HTML escape utility for safe content rendering
     */
    escapeHTML(str) {
        if (typeof str !== 'string') return '';
        
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },
    
    /**
     * Show loading state
     */
    showLoading() {
        document.body.style.cursor = 'wait';
        // Add loading indicators to critical sections
        this.addLoadingPlaceholders();
    },
    
    /**
     * Hide loading state
     */
    hideLoading() {
        document.body.style.cursor = 'default';
        this.removeLoadingPlaceholders();
    },
    
    /**
     * Add loading placeholders
     */
    addLoadingPlaceholders() {
        const loadingElements = [
            DOM.elements.totalPayments, DOM.elements.totalUsers, DOM.elements.activeUsers,
            DOM.elements.totalBonus, DOM.elements.pendingBonus, DOM.elements.pendingPayments
        ];
        
        loadingElements.forEach(element => {
            if (element) {
                element.classList.add('loading');
            }
        });
    },
    
    /**
     * Remove loading placeholders
     */
    removeLoadingPlaceholders() {
        const loadingElements = document.querySelectorAll('.loading');
        loadingElements.forEach(element => {
            element.classList.remove('loading');
        });
    },
    
    /**
     * Show error message
     */
    showError(message) {
        // Create or update error notification
        let errorDiv = document.getElementById('dashboard-error');
        if (!errorDiv) {
            errorDiv = document.createElement('div');
            errorDiv.id = 'dashboard-error';
            errorDiv.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: #f44336;
                color: white;
                padding: 1rem 1.5rem;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                z-index: 1000;
                max-width: 400px;
                animation: slideInRight 0.3s ease-out;
            `;
            document.body.appendChild(errorDiv);
        }
        
        errorDiv.innerHTML = `
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <i class="fas fa-exclamation-triangle"></i>
                <span>${this.escapeHTML(message)}</span>
            </div>
            <button onclick="this.parentElement.remove()" style="background: none; border: none; color: white; margin-left: 1rem; cursor: pointer;">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (errorDiv && errorDiv.parentElement) {
                errorDiv.remove();
            }
        }, 5000);
    },
    
    /**
     * Show success message
     */
    showSuccess(message) {
        let successDiv = document.getElementById('dashboard-success');
        if (!successDiv) {
            successDiv = document.createElement('div');
            successDiv.id = 'dashboard-success';
            successDiv.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: #4caf50;
                color: white;
                padding: 1rem 1.5rem;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                z-index: 1000;
                max-width: 400px;
                animation: slideInRight 0.3s ease-out;
            `;
            document.body.appendChild(successDiv);
        }
        
        successDiv.innerHTML = `
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <i class="fas fa-check-circle"></i>
                <span>${this.escapeHTML(message)}</span>
            </div>
            <button onclick="this.parentElement.remove()" style="background: none; border: none; color: white; margin-left: 1rem; cursor: pointer;">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        setTimeout(() => {
            if (successDiv && successDiv.parentElement) {
                successDiv.remove();
            }
        }, 3000);
    }
};

// Event Handlers and User Interactions
const EventManager = {
    /**
     * Initialize all event listeners
     */
    init() {
        this.initSearch();
        this.initNavigation();
        this.initQuickActions();
        this.initRefreshInterval();
    },
    
    /**
     * Initialize search functionality with debouncing
     */
    initSearch() {
        if (!DOM.elements.adminSearchInput) return;
        
        let searchTimeout;
        
        DOM.elements.adminSearchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            const query = e.target.value.trim();
            
            searchTimeout = setTimeout(() => {
                this.handleSearch(query);
            }, CONFIG.DEBOUNCE_DELAY);
        });
        
        // Handle Enter key
        DOM.elements.adminSearchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                clearTimeout(searchTimeout);
                this.handleSearch(e.target.value.trim());
            }
        });
    },
    
    /**
     * Handle user search
     */
    async handleSearch(query) {
        if (query.length < 2) return;
        
        try {
            const results = await APIService.searchUsers(query);
            this.displaySearchResults(results);
        } catch (error) {
            UIManager.showError(error.message);
        }
    },
    
    /**
     * Display search results (to be implemented based on UI requirements)
     */
    displaySearchResults(results) {
        console.log('Search results:', results);
        // Implementation depends on how you want to display search results
        // Could be a dropdown, modal, or redirect to users page
    },
    
    /**
     * Initialize navigation event handlers
     */
    initNavigation() {
        const navItems = [
            DOM.elements.navDashboard,
            DOM.elements.navUsers,
            DOM.elements.navPayments,
            DOM.elements.navBonuses,
            DOM.elements.navReports,
            DOM.elements.navSettings,
            DOM.elements.navLogout
        ].filter(item => item !== null);
        
        navItems.forEach(navItem => {
            navItem.addEventListener('click', (e) => {
                e.preventDefault();
                this.handleNavigation(navItem.id);
            });
        });
    },
    
    /**
     * Handle navigation clicks
     */
    handleNavigation(navId) {
        const viewMap = {
            'nav-dashboard': 'dashboard',
            'nav-users': 'users',
            'nav-payments': 'payments',
            'nav-bonuses': 'bonuses',
            'nav-reports': 'reports',
            'nav-settings': 'settings',
            'nav-logout': 'logout'
        };
        
        const view = viewMap[navId];
        
        if (view === 'logout') {
            this.handleLogout();
            return;
        }
        
        AppState.currentView = view;
        this.updateActiveNav(navId);
        
        // In a full SPA, this would load different views
        // For now, we'll just update the active state
        console.log(`Navigating to: ${view}`);
    },
    
    /**
     * Update active navigation state
     */
    updateActiveNav(activeNavId) {
        // Remove active class from all nav items
        document.querySelectorAll('.nav-link').forEach(nav => {
            nav.classList.remove('active');
        });
        
        // Add active class to clicked nav item
        const activeNav = document.getElementById(activeNavId);
        if (activeNav) {
            activeNav.classList.add('active');
        }
    },
    
    /**
     * Handle logout
     */
    handleLogout() {
        if (confirm('Are you sure you want to logout?')) {
            window.location.href = '/';
        }
    },
    
    /**
     * Initialize quick action buttons
     */
    initQuickActions() {
        const actions = [
            DOM.elements.actionAddUser,
            DOM.elements.actionProcessBonus,
            DOM.elements.actionManualPayment,
            DOM.elements.actionGenerateReport,
            DOM.elements.actionSystemBackup,
            DOM.elements.actionBulkActions
        ].filter(action => action !== null);
        
        actions.forEach(action => {
            action.addEventListener('click', (e) => {
                e.preventDefault();
                this.handleQuickAction(action.id);
            });
        });
    },
    
    /**
     * Handle quick action clicks
     */
    handleQuickAction(actionId) {
        const actionMap = {
            'action-add-user': () => this.openUserModal(),
            'action-process-bonus': () => this.processBonus(),
            'action-manual-payment': () => this.manualPayment(),
            'action-generate-report': () => this.generateReport(),
            'action-system-backup': () => this.systemBackup(),
            'action-bulk-actions': () => this.bulkActions()
        };
        
        const action = actionMap[actionId];
        if (action) {
            action();
        }
    },
    
    /**
     * Quick action handlers (stubs for implementation)
     */
    openUserModal() {
        UIManager.showSuccess('Add User feature would open here');
        console.log('Opening add user modal');
    },
    
    processBonus() {
        UIManager.showSuccess('Bonus processing would start here');
        console.log('Processing bonuses');
    },
    
    manualPayment() {
        UIManager.showSuccess('Manual payment feature would open here');
        console.log('Opening manual payment');
    },
    
    generateReport() {
        UIManager.showSuccess('Report generation started');
        console.log('Generating report');
    },
    
    systemBackup() {
        UIManager.showSuccess('System backup initiated');
        console.log('Starting system backup');
    },
    
    bulkActions() {
        UIManager.showSuccess('Bulk actions modal would open here');
        console.log('Opening bulk actions');
    },
    
    /**
     * Initialize auto-refresh interval
     */
    initRefreshInterval() {
        setInterval(() => {
            if (AppState.currentView === 'dashboard') {
                DashboardManager.loadData();
            }
        }, CONFIG.REFRESH_INTERVAL);
    }
};

// Main Dashboard Manager
const DashboardManager = {
    /**
     * Initialize the dashboard
     */
    async init() {
        try {
            // Initialize DOM references
            DOM.init();
            
            // Initialize event handlers
            EventManager.init();
            
            // Load initial data
            await this.loadData();
            
            // Set up periodic refresh
            this.setupAutoRefresh();
            
            console.log('Admin dashboard initialized successfully');
            // 
             updateDashboard();
            
        } catch (error) {
            console.error('Dashboard initialization failed:', error);
            UIManager.showError('Failed to initialize dashboard. Please refresh the page.');
        }
    },
    
    /**
     * Load dashboard data from API
     */
    async loadData() {
        if (AppState.isLoading) return;
        
        try {
            AppState.isLoading = true;
            UIManager.showLoading();
            
            const data = await APIService.fetchAdminData();
            
            // Update application state
            AppState.adminData = data;
            AppState.lastUpdate = new Date();
            
            // Update UI with new data
            this.updateUI(data);
            
            UIManager.showSuccess('Dashboard updated successfully');
            
        } catch (error) {
            console.error('Failed to load dashboard data:', error);
            UIManager.showError(error.message || 'Failed to load dashboard data');
            
        } finally {
            AppState.isLoading = false;
            UIManager.hideLoading();
        }
    },
    
    /**
     * Update all UI components with new data
     */
    updateUI(data) {
        UIManager.updateStats(data);
        UIManager.updatePaymentStatus(data);
        UIManager.updateRecentPayments(data);
        UIManager.updateCharts(data);
        
        // Update last refresh time if element exists
        const lastUpdateElement = document.getElementById('last-update-time');
        if (lastUpdateElement) {
            lastUpdateElement.textContent = new Date().toLocaleTimeString();
        }
    },
    
    /**
     * Set up automatic data refresh
     */
    setupAutoRefresh() {
        // Refresh on visibility change (when tab becomes active)
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden && AppState.currentView === 'dashboard') {
                this.loadData();
            }
        });
        
        // Manual refresh button (if added to HTML)
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadData());
        }
    },
    
    /**
     * Force refresh dashboard data
     */
    forceRefresh() {
        this.loadData();
    }
};

// Application Bootstrap
document.addEventListener('DOMContentLoaded', function() {
    // Start the application
    DashboardManager.init();
    
    // Global error handler for uncaught errors
    window.addEventListener('error', function(event) {
        console.error('Global error:', event.error);
        UIManager.showError('An unexpected error occurred');
    });
    
    // Handle unhandled promise rejections
    window.addEventListener('unhandledrejection', function(event) {
        console.error('Unhandled promise rejection:', event.reason);
        UIManager.showError('An unexpected error occurred');
    });
});

// Export for potential module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        DashboardManager,
        APIService,
        UIManager,
        Formatters
    };
}
//=======================================================
//
// ADMIN DASHBOARD SEARCH JS
//===========================================================

    
        let currentResults = {
            users: [],
            payments: [],
            bonuses: []
        };

        function handleKeyPress(event) {
            if (event.key === 'Enter') {
                performSearch();
            }
        }

        async function performSearch() {
            const query = document.getElementById('searchInput').value.trim();
            if (!query) {
                alert('Please enter a search query');
                return;
            }

            showLoading();
            
            try {
                const response = await fetch(`/admin/search?q=${encodeURIComponent(query)}`);
                const data = await response.json();
                
                if (response.ok) {
                    currentResults = data;
                    displayAllResults();
                    updateStats();
                } else {
                    throw new Error(data.error || 'Search failed');
                }
            } catch (error) {
                console.error('Search error:', error);
                showError('Search failed: ' + error.message);
            }
        }

        function displayAllResults() {
            displayUsers(currentResults.users);
            displayPayments(currentResults.payments);
            displayBonuses(currentResults.bonuses);
        }

        function displayUsers(users) {
            const container = document.getElementById('usersResults');
            
            if (!users || users.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-users"></i>
                        <h3>No users found</h3>
                        <p>Try searching with different terms</p>
                    </div>
                `;
                return;
            }

            container.innerHTML = users.map(user => `
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">
                            <i class="fas fa-user"></i> ${user.username}
                        </div>
                        <div class="badge badge-user">USER</div>
                    </div>
                    
                    <div class="info-grid">
                        <div class="info-item">
                            <span class="info-label">ID</span>
                            <span class="info-value">#${user.id}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Email</span>
                            <span class="info-value">${user.email || 'N/A'}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Phone</span>
                            <span class="info-value">${user.phone}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Role</span>
                            <span class="info-value">${user.role}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Balance</span>
                            <span class="info-value">${user.balance} UGX</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Wallet Balance</span>
                            <span class="info-value">${user.wallet_balance} UGX</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Referral Code</span>
                            <span class="info-value">${user.referral_code || 'None'}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Status</span>
                            <span class="info-value">
                                <span class="badge ${user.is_active ? 'badge-success' : 'badge-failed'}">
                                    ${user.is_active ? 'Active' : 'Inactive'}
                                </span>
                            </span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Verified</span>
                            <span class="info-value">
                                <span class="badge ${user.is_verified ? 'badge-success' : 'badge-pending'}">
                                    ${user.is_verified ? 'Verified' : 'Pending'}
                                </span>
                            </span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Member Since</span>
                            <span class="info-value">${formatDate(user.member_since)}</span>
                        </div>
                    </div>
                    
                    <div class="user-actions">
                        <button class="btn btn-primary" onclick="viewUserDetails(${user.id})">
                            <i class="fas fa-eye"></i> View Details
                        </button>
                        <button class="btn btn-secondary" onclick="editUser(${user.id})">
                            <i class="fas fa-edit"></i> Edit
                        </button>
                        <button class="btn ${user.is_active ? 'btn-secondary' : 'btn-success'}" 
                                onclick="toggleUserStatus(${user.id}, ${!user.is_active})">
                            <i class="fas ${user.is_active ? 'fa-pause' : 'fa-play'}"></i> 
                            ${user.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                    </div>
                </div>
            `).join('');
        }

        function displayPayments(payments) {
            const container = document.getElementById('paymentsResults');
            
            if (!payments || payments.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-credit-card"></i>
                        <h3>No payments found</h3>
                        <p>Try searching with different terms</p>
                    </div>
                `;
                return;
            }

            container.innerHTML = payments.map(payment => `
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">
                            <i class="fas fa-receipt"></i> ${payment.reference}
                        </div>
                        <div class="badge badge-payment">PAYMENT</div>
                    </div>
                    
                    <div class="info-grid">
                        <div class="info-item">
                            <span class="info-label">Payment ID</span>
                            <span class="info-value">#${payment.id}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Amount</span>
                            <span class="info-value">${payment.amount} ${payment.currency}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Status</span>
                            <span class="info-value">
                                <span class="badge ${getStatusBadgeClass(payment.status)}">
                                    ${payment.status.toUpperCase()}
                                </span>
                            </span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">External Reference</span>
                            <span class="info-value">${payment.external_ref || 'N/A'}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Phone Number</span>
                            <span class="info-value">${payment.phone_number || 'N/A'}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Provider</span>
                            <span class="info-value">${payment.provider || 'N/A'}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Verified</span>
                            <span class="info-value">
                                <span class="badge ${payment.verified ? 'badge-success' : 'badge-pending'}">
                                    ${payment.verified ? 'Yes' : 'No'}
                                </span>
                            </span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">User ID</span>
                            <span class="info-value">${payment.user_id || 'N/A'}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Created At</span>
                            <span class="info-value">${formatDate(payment.created_at)}</span>
                        </div>
                    </div>
                    
                    <div class="user-actions">
                        <button class="btn btn-primary" onclick="viewPaymentDetails(${payment.id})">
                            <i class="fas fa-eye"></i> View Details
                        </button>
                        <button class="btn btn-secondary" onclick="verifyPayment(${payment.id})">
                            <i class="fas fa-check"></i> Verify
                        </button>
                        <button class="btn btn-success" onclick="refundPayment(${payment.id})">
                            <i class="fas fa-undo"></i> Refund
                        </button>
                    </div>
                </div>
            `).join('');
        }

        function displayBonuses(bonuses) {
            const container = document.getElementById('bonusesResults');
            
            if (!bonuses || bonuses.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-gift"></i>
                        <h3>No bonuses found</h3>
                        <p>Try searching with different terms</p>
                    </div>
                `;
                return;
            }

            container.innerHTML = bonuses.map(bonus => `
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">
                            <i class="fas fa-gift"></i> ${bonus.bonus_type} Bonus
                        </div>
                        <div class="badge badge-bonus">BONUS</div>
                    </div>
                    
                    <div class="info-grid">
                        <div class="info-item">
                            <span class="info-label">Bonus ID</span>
                            <span class="info-value">#${bonus.id}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Amount</span>
                            <span class="info-value">${bonus.amount} UGX</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Type</span>
                            <span class="info-value">${bonus.bonus_type}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Status</span>
                            <span class="info-value">
                                <span class="badge ${getStatusBadgeClass(bonus.status)}">
                                    ${bonus.status.toUpperCase()}
                                </span>
                            </span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">User ID</span>
                            <span class="info-value">${bonus.user_id}</span>
                        </div>
                        ${bonus.referred_id ? `
                        <div class="info-item">
                            <span class="info-label">Referred User ID</span>
                            <span class="info-value">${bonus.referred_id}</span>
                        </div>
                        ` : ''}
                        ${bonus.level ? `
                        <div class="info-item">
                            <span class="info-label">Referral Level</span>
                            <span class="info-value">Level ${bonus.level}</span>
                        </div>
                        ` : ''}
                        <div class="info-item">
                            <span class="info-label">Created At</span>
                            <span class="info-value">${formatDate(bonus.created_at)}</span>
                        </div>
                    </div>
                    
                    <div class="user-actions">
                        <button class="btn btn-primary" onclick="viewBonusDetails(${bonus.id})">
                            <i class="fas fa-eye"></i> View Details
                        </button>
                        <button class="btn btn-secondary" onclick="editBonus(${bonus.id})">
                            <i class="fas fa-edit"></i> Edit
                        </button>
                        <button class="btn ${bonus.status === 'active' ? 'btn-secondary' : 'btn-success'}" 
                                onclick="toggleBonusStatus(${bonus.id}, '${bonus.status === 'active' ? 'inactive' : 'active'}')">
                            <i class="fas ${bonus.status === 'active' ? 'fa-pause' : 'fa-play'}"></i> 
                            ${bonus.status === 'active' ? 'Deactivate' : 'Activate'}
                        </button>
                    </div>
                </div>
            `).join('');
        }

        function updateStats() {
            const statsBar = document.getElementById('statsBar');
            statsBar.style.display = 'flex';
            
            document.getElementById('totalResults').textContent = currentResults.total_results || 0;
            document.getElementById('userCount').textContent = currentResults.users?.length || 0;
            document.getElementById('paymentCount').textContent = currentResults.payments?.length || 0;
            document.getElementById('bonusCount').textContent = currentResults.bonuses?.length || 0;
            
            // Update tab counts
            document.getElementById('usersTabCount').textContent = currentResults.users?.length || 0;
            document.getElementById('paymentsTabCount').textContent = currentResults.payments?.length || 0;
            document.getElementById('bonusesTabCount').textContent = currentResults.bonuses?.length || 0;
        }

        function switchTab(tabName) {
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Show selected tab
            document.getElementById(tabName + 'Tab').classList.add('active');
            event.target.classList.add('active');
        }

        function showLoading() {
            const containers = ['usersResults', 'paymentsResults', 'bonusesResults'];
            containers.forEach(containerId => {
                const container = document.getElementById(containerId);
                container.innerHTML = `
                    <div class="loading">
                        <div class="loading-spinner"></div>
                        <p>Searching...</p>
                    </div>
                `;
            });
        }

        function showError(message) {
            const containers = ['usersResults', 'paymentsResults', 'bonusesResults'];
            containers.forEach(containerId => {
                const container = document.getElementById(containerId);
                container.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-exclamation-triangle"></i>
                        <h3>Error</h3>
                        <p>${message}</p>
                    </div>
                `;
            });
        }

        function formatDate(dateString) {
            if (!dateString) return 'N/A';
            const date = new Date(dateString);
            return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
        }

        function getStatusBadgeClass(status) {
            switch (status?.toLowerCase()) {
                case 'success':
                case 'active':
                case 'verified':
                    return 'badge-success';
                case 'pending':
                    return 'badge-pending';
                case 'failed':
                case 'inactive':
                    return 'badge-failed';
                default:
                    return 'badge-pending';
            }
        }

        // Placeholder functions for actions
        function viewUserDetails(userId) {
            alert('View user details: ' + userId);
            // Implement user details view
        }

        function editUser(userId) {
            alert('Edit user: ' + userId);
            // Implement user edit
        }

        function toggleUserStatus(userId, newStatus) {
            if (confirm(`Are you sure you want to ${newStatus ? 'activate' : 'deactivate'} this user?`)) {
                alert(`User ${userId} status changed to: ${newStatus}`);
                // Implement status toggle API call
            }
        }

        function viewPaymentDetails(paymentId) {
            alert('View payment details: ' + paymentId);
            // Implement payment details view
        }

        function verifyPayment(paymentId) {
            if (confirm('Verify this payment?')) {
                alert('Payment verified: ' + paymentId);
                // Implement payment verification
            }
        }

        function refundPayment(paymentId) {
            if (confirm('Refund this payment?')) {
                alert('Payment refunded: ' + paymentId);
                // Implement payment refund
            }
        }

        function viewBonusDetails(bonusId) {
            alert('View bonus details: ' + bonusId);
            // Implement bonus details view
        }

        function editBonus(bonusId) {
            alert('Edit bonus: ' + bonusId);
            // Implement bonus edit
        }

        function toggleBonusStatus(bonusId, newStatus) {
            if (confirm(`Are you sure you want to ${newStatus === 'active' ? 'activate' : 'deactivate'} this bonus?`)) {
                alert(`Bonus ${bonusId} status changed to: ${newStatus}`);
                // Implement bonus status toggle API call
            }
        }

        // Initialize with empty state
        document.addEventListener('DOMContentLoaded', function() {
            // Any initialization code can go here
        });

// admin-dashboard.js
(function () {
  'use strict';

  const CONFIG = {
    BASE_URL: '/api/admin',
    TIMEOUT_MS: 8000,
    MAX_RETRIES: 2,
    CURRENCY: 'USD'
  };

  // 🛡️ Safe fetch wrapper: timeout, retry, error parsing
  async function fetchJSON(endpoint, options = {}) {
    const url = `${CONFIG.BASE_URL}${endpoint}`;
    let attempt = 0;

    while (attempt <= CONFIG.MAX_RETRIES) {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), CONFIG.TIMEOUT_MS);

      try {
        const res = await fetch(url, {
          ...options,
          signal: controller.signal,
          headers: { 'Accept': 'application/json', ...options.headers }
        });
        clearTimeout(timeoutId);

        if (!res.ok) {
          const err = await res.json().catch(() => ({ message: `HTTP ${res.status}` }));
          throw new Error(err.message || `Request failed with status ${res.status}`);
        }
        return await res.json();
      } catch (err) {
        clearTimeout(timeoutId);
        attempt++;
        if (attempt > CONFIG.MAX_RETRIES) throw err;
        await new Promise(r => setTimeout(r, 1000 * attempt)); // Linear backoff
      }
    }
  }

  // 🧱 DOM Utilities
  const DOM = {
    el: (sel) => document.querySelector(sel),
    text: (sel, val) => { const e = DOM.el(sel); if (e) e.textContent = val ?? '—'; },
    html: (sel, val) => { const e = DOM.el(sel); if (e) e.innerHTML = val; },
    show: (sel) => DOM.el(sel)?.classList.remove('d-none'),
    hide: (sel) => DOM.el(sel)?.classList.add('d-none'),
    fmtNum: (n, dec = 2) => Number(n || 0).toLocaleString(undefined, { minimumFractionDigits: dec, maximumFractionDigits: dec }),
    fmtDate: (iso) => iso ? new Date(iso).toLocaleDateString() : '—'
  };

  // 📊 Dashboard Controller
  const AdminDashboard = {
    async init() {
      DOM.hide('#dashboard-content');
      DOM.show('#dashboard-loader');
      DOM.hide('#dashboard-error');

      try {
        // Fetch in parallel: one failure won't break the whole dashboard
        const [statsRes, usersRes, withdrawalsRes] = await Promise.allSettled([
          fetchJSON('/dashboard/stats'),
          fetchJSON('/users/recent?limit=10'),
          fetchJSON('/withdrawals/recent?limit=10')
        ]);

        this.renderStats(statsRes);
        this.renderTable('#recent-users-body', usersRes, this.rowUser);
        this.renderTable('#recent-withdrawals-body', withdrawalsRes, this.rowWithdrawal);

        DOM.hide('#dashboard-loader');
        DOM.show('#dashboard-content');
      } catch (err) {
        console.error('Dashboard init failed:', err);
        DOM.hide('#dashboard-loader');
        DOM.show('#dashboard-error');
        DOM.text('#error-msg', err.message || 'Failed to initialize dashboard');
      }
    },

    renderStats(res) {
      const s = res.status === 'fulfilled' ? res.value : {};
      DOM.text('#stat-users-total', s.total_users);
      DOM.text('#stat-users-pending', s.pending_users);
      DOM.text('#stat-packages-active', s.active_packages);
      DOM.text('#stat-withdrawals-pending', s.pending_withdrawals);
      DOM.text('#stat-volume-total', `$${DOM.fmtNum(s.total_volume)}`);
      DOM.text('#stat-today-users', s.today_users);
      DOM.text('#stat-today-withdrawals', s.today_withdrawals);
    },

    renderTable(selector, res, rowFn) {
      const tbody = DOM.el(selector);
      if (!tbody) return;

      if (res.status === 'fulfilled' && Array.isArray(res.value) && res.value.length) {
        tbody.innerHTML = res.value.map(rowFn).join('');
      } else {
        tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">No data available</td></tr>`;
      }
    },

    rowUser(u) {
      const cls = u.is_active ? 'badge-success' : 'badge-warning';
      return `
        <tr>
          <td>${u.id}</td>
          <td>${u.username}</td>
          <td>${u.email || '—'}</td>
          <td><span class="badge ${cls}">${u.is_active ? 'Active' : 'Inactive'}</span></td>
          <td>${DOM.fmtDate(u.created_at)}</td>
        </tr>`;
    },

    rowWithdrawal(w) {
      const cls = `badge-${w.status}`;
      return `
        <tr>
          <td>${w.id}</td>
          <td>${w.user?.username || 'N/A'}</td>
          <td>$${DOM.fmtNum(w.amount)}</td>
          <td><span class="badge ${cls}">${w.status}</span></td>
          <td>${DOM.fmtDate(w.created_at)}</td>
        </tr>`;
    }
  };

  // 🚀 Bootstrap
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => AdminDashboard.init());
  } else {
    AdminDashboard.init();
  }

  // Expose for manual reload after CRUD actions
  window.AdminDashboard = { reload: () => AdminDashboard.init() };
})();