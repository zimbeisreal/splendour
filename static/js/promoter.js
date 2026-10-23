// ============================================================
// PROMOTER REGISTRATION - express
// ============================================================

let currentStep = 1;
const totalSteps = 4;

// ============================================================
// STEP NAVIGATION
// ============================================================

function goToStep(step) {
    if (step < 1 || step > totalSteps) return;
    
    // Validate current step before proceeding
    if (step > currentStep) {
        if (!validateStep(currentStep)) {
            return;
        }
    }
    
    currentStep = step;
    updateUI();
}

function updateUI() {
    // Update steps
    document.querySelectorAll('.express-form-step').forEach(el => {
        el.classList.toggle('active', parseInt(el.dataset.step) === currentStep);
    });
    
    // Update progress steps
    document.querySelectorAll('.express-progress-step').forEach(el => {
        const stepNum = parseInt(el.dataset.step);
        el.classList.remove('active', 'completed');
        if (stepNum === currentStep) {
            el.classList.add('active');
        } else if (stepNum < currentStep) {
            el.classList.add('completed');
        }
    });
    
    // Update progress bar
    const progress = ((currentStep - 1) / (totalSteps - 1)) * 100;
    document.getElementById('progressFill').style.width = progress + '%';
    
    // Update badge
    document.getElementById('stepBadge').textContent = `Step ${currentStep} of ${totalSteps}`;
    
    // Update review data if on step 4
    if (currentStep === 4) {
        updateReview();
    }
}

// ============================================================
// VALIDATION
// ============================================================

function validateStep(step) {
    const stepElement = document.querySelector(`.express-form-step[data-step="${step}"]`);
    if (!stepElement) return true;
    
    const inputs = stepElement.querySelectorAll('input[required], select[required], textarea[required]');
    let isValid = true;
    
    inputs.forEach(input => {
        if (!input.value.trim()) {
            input.style.borderColor = 'var(--express-red)';
            isValid = false;
        } else {
            input.style.borderColor = '';
        }
    });
    
    if (!isValid) {
        showToast('⚠️ Please fill in all required fields', 'warning');
        // Scroll to first error
        const firstError = stepElement.querySelector('input[required]:invalid, select[required]:invalid, textarea[required]:invalid');
        if (firstError) {
            firstError.focus();
        }
    }
    
    return isValid;
}

// ============================================================
// SKILLS SELECTION
// ============================================================

document.addEventListener('DOMContentLoaded', function() {
    // Skill tags
    document.querySelectorAll('.express-skill-tag').forEach(tag => {
        tag.addEventListener('click', function() {
            this.classList.toggle('selected');
            updateSelectedSkills();
        });
    });
    
    // Form submission
    document.getElementById('promoterForm').addEventListener('submit', submitRegistration);
    
    // Auto-format phone numbers
    document.querySelectorAll('input[type="tel"]').forEach(input => {
        input.addEventListener('input', function() {
            // Only allow digits and +
            this.value = this.value.replace(/[^0-9+]/g, '');
            // Ensure starts with 256 or +
            if (this.value && !this.value.startsWith('256') && !this.value.startsWith('+')) {
                this.value = '256' + this.value;
            }
        });
    });
});

function updateSelectedSkills() {
    const selected = document.querySelectorAll('.express-skill-tag.selected');
    const skills = Array.from(selected).map(el => el.dataset.skill);
    document.getElementById('selectedSkills').value = JSON.stringify(skills);
}

// ============================================================
// REVIEW UPDATE
// ============================================================

function updateReview() {
    const fields = {
        fullName: 'reviewFullName',
        nin: 'reviewNin',
        phoneDirect: 'reviewPhone',
        phoneWhatsapp: 'reviewWhatsapp',
        location: 'reviewLocation',
        experienceMonths: 'reviewExperience',
        promoterType: 'reviewPromoterType',
        teamSize: 'reviewTeamSize',
        expectedDaily: 'reviewDaily',
        expectedWeekly: 'reviewWeekly',
        availableHours: 'reviewHours'
    };
    
    Object.entries(fields).forEach(([inputId, reviewId]) => {
        const input = document.getElementById(inputId);
        const review = document.getElementById(reviewId);
        if (input && review) {
            let value = input.value || '—';
            if (inputId === 'phoneWhatsapp' && !value) value = 'Not provided';
            if (inputId === 'teamSize' && !value) value = 'N/A';
            if (inputId === 'experienceMonths') {
                const select = document.getElementById('experienceMonths');
                value = select.options[select.selectedIndex]?.text || '—';
            }
            if (inputId === 'promoterType') {
                const select = document.getElementById('promoterType');
                value = select.options[select.selectedIndex]?.text || '—';
            }
            if (inputId === 'availableHours') {
                const select = document.getElementById('availableHours');
                value = select.options[select.selectedIndex]?.text || '—';
            }
            if (inputId === 'expectedDaily' || inputId === 'expectedWeekly') {
                value = 'UGX ' + Number(value).toLocaleString();
            }
            review.textContent = value;
        }
    });
    
    // Skills review
    const skillsSelect = document.querySelectorAll('.express-skill-tag.selected');
    const skillsReview = document.getElementById('reviewSkills');
    if (skillsReview) {
        const skillNames = Array.from(skillsSelect).map(el => el.textContent.trim());
        skillsReview.textContent = skillNames.length > 0 ? skillNames.join(', ') : '—';
    }
}

// ============================================================
// SUBMIT REGISTRATION
// ============================================================

async function submitRegistration(e) {
    e.preventDefault();
    
    // Final validation
    if (!validateStep(4)) {
        return;
    }
    
    const submitBtn = document.getElementById('submitBtn');
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Submitting...';
    
    try {
        // Gather form data
        const formData = new FormData(document.getElementById('promoterForm'));
        const data = {
            full_name: formData.get('fullName'),
            nin: formData.get('nin'),
            phone_direct: formData.get('phoneDirect'),
            phone_whatsapp: formData.get('phoneWhatsapp') || null,
            email: formData.get('email') || null,
            location: formData.get('location'),
            previous_companies: formData.get('previousCompanies') || null,
            promoted_products: formData.get('promotedProducts'),
            experience_months: formData.get('experienceMonths'),
            promoter_type: formData.get('promoterType'),
            team_size: formData.get('teamSize') || 0,
            expected_daily: formData.get('expectedDaily'),
            expected_weekly: formData.get('expectedWeekly'),
            available_hours: formData.get('availableHours'),
            preferred_areas: formData.get('preferredAreas') || null,
            skills: JSON.parse(formData.get('selectedSkills') || '[]')
        };
        
        // Submit to API
        const response = await fetch('/promoter/signup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify(data),
            credentials: 'include'
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            // Show success page
            document.getElementById('registrationSection').style.display = 'none';
            document.getElementById('successSection').style.display = 'block';
            
            // Scroll to top
            window.scrollTo({ top: 0, behavior: 'smooth' });
            
            showToast('✅ Registration submitted successfully!', 'success');
        } else {
            showToast('❌ ' + (result.error || 'Registration failed. Please try again.'), 'error');
        }
        
    } catch (error) {
        console.error('Registration error:', error);
        showToast('❌ Network error. Please check your connection and try again.', 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fas fa-paper-plane"></i> Submit Registration';
    }
}

// ============================================================
// TOAST NOTIFICATION
// ============================================================

function showToast(message, type = 'info') {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.style.cssText = `
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 9999;
            width: 90%;
            max-width: 400px;
            display: flex;
            flex-direction: column;
            gap: 8px;
            pointer-events: none;
        `;
        document.body.appendChild(container);
    }
    
    const toast = document.createElement('div');
    const colors = {
        success: 'rgba(16, 185, 129, 0.15)',
        error: 'rgba(231, 36, 42, 0.15)',
        warning: 'rgba(245, 166, 35, 0.15)',
        info: 'rgba(59, 130, 246, 0.15)'
    };
    const borderColors = {
        success: '#10B981',
        error: '#E7242A',
        warning: '#F5A623',
        info: '#3B82F6'
    };
    
    toast.style.cssText = `
        background: var(--express-card);
        color: var(--express-white);
        padding: 12px 16px;
        border-radius: var(--express-radius-sm);
        border: 1px solid ${borderColors[type] || 'var(--express-card-border)'};
        box-shadow: var(--express-shadow);
        font-size: 13px;
        font-weight: 500;
        pointer-events: auto;
        animation: slideUp 0.3s ease-out;
        background: ${colors[type] || 'var(--express-card)'};
        backdrop-filter: blur(10px);
        display: flex;
        align-items: center;
        gap: 10px;
    `;
    
    toast.innerHTML = `<span>${message}</span>`;
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-10px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
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
        WHATSAPP_GROUP: 'https://chat.whatsapp.com/JHasA9C9dW53Ltn6IeFncI?s=cl&p=a&mlu=4&ilr=4',
        TELEGRAM_CHANNEL: 'https://t.me/+eVTIuSk4Wm00NDY0',
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