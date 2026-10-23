// ===== TRANSACTION HISTORY FUNCTIONS =====

let currentTxnPage = 1;
let currentTxnFilter = 'all';
let isLoadingTxns = false;
let hasMoreTxns = true;

// Load Transaction History
async function loadTransactionHistory(filter = 'all', page = 1, append = false) {
    if (isLoadingTxns) return;
    isLoadingTxns = true;
    
    const container = document.getElementById('transactionList');
    const skeleton = document.getElementById('txnSkeleton');
    const countBadge = document.getElementById('txnCount');
    const loadMoreBtn = document.getElementById('loadMoreTxns');
    
    // Show skeleton on first load
    if (!append && skeleton) skeleton.style.display = 'block';
    if (loadMoreBtn) loadMoreBtn.textContent = 'Loading...';
    
    try {
        const response = await fetch(`/api/recent_activity/user?page=${page}&page_size=20`, {
            credentials: 'include',
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        
        const data = await response.json();
        
        if (skeleton) skeleton.style.display = 'none';
        if (loadMoreBtn) loadMoreBtn.innerHTML = '<i class="fas fa-chevron-down"></i> Load More';
        
        if (data.activities && data.activities.length > 0) {
            let activities = data.activities;
            
            // Apply filter
            if (filter !== 'all') {
                activities = data.activities.filter(a => a.type === filter);
            }
            
            // Update badge count
            if (countBadge) countBadge.textContent = activities.length;
            
            // Check if more pages
            hasMoreTxns = data.pagination?.has_next || false;
            if (loadMoreBtn) {
                loadMoreBtn.style.display = hasMoreTxns ? 'block' : 'none';
            }
            
            // Render transactions
            const html = activities.map(t => `
                <div class="txn-item" onclick="showTxnDetail('${t.id || ''}')">
                    <div class="txn-icon ${t.type || 'deposit'}">
                        <i class="fas ${getTxnIcon(t.type)}"></i>
                    </div>
                    <div class="txn-info">
                        <div class="txn-title">${t.title || 'Transaction'}</div>
                        <div class="txn-date">${formatTxnDate(t.timestamp)}</div>
                    </div>
                    <div class="txn-right">
                        <div class="txn-amount ${t.amount > 0 ? 'positive' : 'negative'}">
                            ${t.amount > 0 ? '+' : ''}${formatTxnAmount(t.amount)}
                        </div>
                        <div class="txn-status ${t.status || 'completed'}">
                            ${t.status || 'Completed'}
                        </div>
                    </div>
                </div>
            `).join('');
            
            if (append) {
                container.innerHTML += html;
            } else {
                container.innerHTML = html;
            }
            
        } else {
            container.innerHTML = `
                <div class="txn-empty">
                    <i class="fas fa-inbox"></i>
                    <p>No transactions yet</p>
                    <small>Start investing to see your history</small>
                </div>
            `;
            if (countBadge) countBadge.textContent = '0';
            if (loadMoreBtn) loadMoreBtn.style.display = 'none';
        }
        
    } catch (error) {
        console.error('Error loading transactions:', error);
        if (skeleton) skeleton.style.display = 'none';
        if (!append) {
            container.innerHTML = `
                <div class="txn-empty" style="color:#ff6b6b;">
                    <i class="fas fa-exclamation-circle"></i>
                    <p>Failed to load transactions</p>
                    <small>Please try again</small>
                </div>
            `;
        }
    } finally {
        isLoadingTxns = false;
        if (loadMoreBtn) loadMoreBtn.innerHTML = '<i class="fas fa-chevron-down"></i> Load More';
    }
}

// Helper Functions for Transactions
function getTxnIcon(type) {
    const icons = {
        'deposit': 'fa-arrow-down',
        'withdraw': 'fa-arrow-up',
        'bonus': 'fa-gift',
        'investment': 'fa-chart-line',
        'referral': 'fa-user-plus'
    };
    return icons[type] || 'fa-circle';
}

function formatTxnDate(dateStr) {
    if (!dateStr) return '---';
    const d = new Date(dateStr);
    const now = new Date();
    const diff = now - d;
    
    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return Math.floor(diff / 60000) + 'm ago';
    if (diff < 86400000) return Math.floor(diff / 3600000) + 'h ago';
    if (diff < 604800000) return Math.floor(diff / 86400000) + 'd ago';
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatTxnAmount(amount) {
    if (!amount) return '0';
    return Number(amount).toLocaleString('en-US', { minimumFractionDigits: 0 });
}

// Show Transaction Detail
window.showTxnDetail = function(id) {
    showToast('📊 Transaction details coming soon!');
};

// Load More Transactions
document.getElementById('loadMoreTxns')?.addEventListener('click', function() {
    if (!isLoadingTxns && hasMoreTxns) {
        currentTxnPage++;
        loadTransactionHistory(currentTxnFilter, currentTxnPage, true);
    }
});

// Transaction Filter Buttons
document.querySelectorAll('.txn-filter-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        document.querySelectorAll('.txn-filter-btn').forEach(b => b.classList.remove('active'));
        this.classList.add('active');
        currentTxnFilter = this.dataset.filter;
        currentTxnPage = 1;
        hasMoreTxns = true;
        loadTransactionHistory(currentTxnFilter, 1, false);
    });
});


