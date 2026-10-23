// ============================================================
// SKYLINE — AUTH PAGE
// Sign In / Create Account · Mobile-First
// Contract preserved from original main.js:
//   #pulseSwitch[data-active], .pulse-switch-btn[data-form],
//   [data-switch], .pulse-eye[data-target], .pulse-input,
//   .pulse-form.active, .pulse-submit
// ============================================================

(function () {
  'use strict';

  // ============================================================
  // DOM REFS
  // ============================================================
  const loginForm    = document.getElementById('loginForm');
  const registerForm = document.getElementById('registerForm');
  const switchRoot   = document.getElementById('pulseSwitch');
  // Tabs use .sky-tab visually but data-form contract is identical
  const switchBtns   = document.querySelectorAll('#pulseSwitch .sky-tab, #pulseSwitch .pulse-switch-btn');
  const formLinks    = document.querySelectorAll('[data-switch]');
  const pwdToggles   = document.querySelectorAll('.pulse-eye');
  const allInputs    = document.querySelectorAll('.pulse-input');

  if (!loginForm || !registerForm) {
    console.warn('⚠️ Skyline auth: forms not found — aborting auth.js init');
    return;
  }

  // ============================================================
  // TOAST SYSTEM
  // ============================================================
  function showToast(message, type = 'info', duration = 4000) {
    const old = document.querySelector('.pulse-toast');
    if (old) old.remove();

    const toast = document.createElement('div');
    toast.className = `pulse-toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
      toast.style.animation = 'sky-toast-down 0.3s ease-out forwards';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }

  window.showToast = window.showToast || showToast;

  // ============================================================
  // FORM SWITCHING
  // ============================================================
  function switchForm(form) {
    // 1. Toggle active state on the tab buttons
    switchBtns.forEach(btn => {
      btn.classList.toggle('active', btn.dataset.form === form);
    });

    // 2. Update data-active on the switcher root (CSS reads this if needed)
    if (switchRoot) {
      switchRoot.dataset.active = form;
    }

    // 3. Toggle form visibility
    loginForm.classList.remove('active');
    registerForm.classList.remove('active');

    if (form === 'login') {
      loginForm.classList.add('active');
    } else {
      registerForm.classList.add('active');
    }

    // 4. Focus first input of newly-active form
    setTimeout(() => {
      const firstInput = (form === 'login' ? loginForm : registerForm)
        .querySelector('.pulse-input');
      firstInput?.focus();
    }, 150);
  }

  // Tab buttons
  switchBtns.forEach(btn => {
    btn.addEventListener('click', function () {
      switchForm(this.dataset.form);
    });
  });

  // Footer links ("Create access" / "Sign in")
  formLinks.forEach(link => {
    link.addEventListener('click', function (e) {
      e.preventDefault();
      switchForm(this.dataset.switch);
    });
  });

  // ============================================================
  // PASSWORD TOGGLE
  // ============================================================
  pwdToggles.forEach(btn => {
    btn.addEventListener('click', function () {
      const target = document.getElementById(this.dataset.target);
      const icon = this.querySelector('i');
      if (!target || !icon) return;

      if (target.type === 'password') {
        target.type = 'text';
        icon.classList.replace('fa-eye', 'fa-eye-slash');
        this.setAttribute('aria-label', 'Hide PIN');
      } else {
        target.type = 'password';
        icon.classList.replace('fa-eye-slash', 'fa-eye');
        this.setAttribute('aria-label', 'Show PIN');
      }
    });
  });

  // ============================================================
  // REFERRAL CODE FROM URL — dynamic (no hardcoding)
  // Reads ?ref=..., shows the chip, prefills #regReferral,
  // mirrors into hidden #referralCode legacy hook.
  // ============================================================
  function populateReferral() {
    const urlParams = new URLSearchParams(window.location.search);
    const ref = (urlParams.get('ref') || '').trim();

    const chip      = document.getElementById('skyRefChip');
    const chipCode  = document.getElementById('skyRefCode');
    const regInput  = document.getElementById('regReferral');
    const legacyIn  = document.getElementById('referralCode');

    // Mirror into legacy hidden input for backward compat
    if (legacyIn) legacyIn.value = ref;

    if (!ref) {
      if (chip) chip.hidden = true;
      return;
    }

    // Show permanent chip
    if (chip && chipCode) {
      chipCode.textContent = ref;
      chip.hidden = false;
    }

    // Prefill invite code field + auto-switch to register
    if (regInput) {
      regInput.value = ref;
      regInput.placeholder = '🔒 Referral applied';
    }
    switchForm('register');
  }
  populateReferral();

  // ============================================================
  // SIGN-IN HANDLER
  // ============================================================
  loginForm.addEventListener('submit', async function (e) {
    e.preventDefault();

    const phone = document.getElementById('loginPhone').value.trim();
    const pin   = document.getElementById('loginPin').value.trim();
    const btn   = this.querySelector('.pulse-submit');

    if (!phone || phone.length < 10) {
      showToast('📱 Please enter a valid phone number', 'warning');
      return;
    }
    if (!pin || pin.length !== 5 || !/^\d{5}$/.test(pin)) {
      showToast('🔒 Enter a 5-digit PIN', 'warning');
      return;
    }

    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Signing in…';
    btn.disabled = true;

    try {
      const response = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email_or_phone: phone, password: pin }),
        credentials: 'include',
      });

      const data = await response.json();
      console.log('📊 Skyline login response:', data);

      if (!response.ok) {
        throw new Error(data.message || 'Login failed');
      }

      const userRole = data.role || data.user?.role || data.user?.user_role || 'user';
      console.log('👤 User ID:', data.user?.id || data.id);
      console.log('🔑 User role:', userRole);

      sessionStorage.setItem('skyline_just_logged_in', 'true');
      localStorage.setItem('skyline_welcome_seen', 'false');
      localStorage.setItem('userRole', userRole);

      if (data.user) {
        localStorage.setItem('userData', JSON.stringify(data.user));
      }

      const isAdmin = ['admin', 'sub_admin', 'super_admin'].includes(userRole);
      const redirectUrl = isAdmin ? '/admin/dashboard' : '/profile?show_welcome=true';

      console.log(`Redirecting to: ${redirectUrl} (isAdmin: ${isAdmin})`);

      showToast('Welcome back to Skyline', 'success');

      setTimeout(() => {
        window.location.replace(redirectUrl);
      }, 1200);

    } catch (error) {
      console.error('Login error:', error);
      showToast('⚠️ ' + error.message, 'error');
      btn.innerHTML = originalText;
      btn.disabled = false;
    }
  });

  // ============================================================
  // CREATE-ACCOUNT HANDLER
  // ============================================================
  registerForm.addEventListener('submit', async function (e) {
    e.preventDefault();

    const username = document.getElementById('regUsername').value.trim();
    const phone    = document.getElementById('regPhone').value.trim();
    const pin      = document.getElementById('regPin').value.trim();
    const referral = document.getElementById('regReferral').value.trim();
    const btn      = this.querySelector('.pulse-submit');

    if (!username || username.length < 3) {
      showToast('Username must be at least 3 characters', 'warning');
      return;
    }
    if (!phone || phone.length < 10) {
      showToast('Valid phone number required', 'warning');
      return;
    }
    if (!pin || pin.length !== 5 || !/^\d{5}$/.test(pin)) {
      showToast('Enter 5 for numners PIN', 'warning');
      return;
    }

    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating account…';
    btn.disabled = true;

    try {
      const payload = {
        username: username,
        phone: phone,
        pin: pin,
        referralCode: referral || null,
      };

      const response = await fetch('/api/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        credentials: 'include',
      });

      const data = await response.json();
      console.log('📊 Skyline signup response:', data);

      if (!response.ok) {
        throw new Error(data.error || data.message || 'Registration failed');
      }

      sessionStorage.setItem('skyline_just_logged_in', 'true');
      localStorage.setItem('skyline_welcome_seen', 'false');

      showToast('Skyline account sucessful. logging in…', 'success');

      setTimeout(() => {
        window.location.href = '/profile?show_welcome=true';
      }, 1200);

    } catch (error) {
      console.error('Registration error:', error);
      showToast('⚠️ ' + error.message, 'error');
      btn.innerHTML = originalText;
      btn.disabled = false;
    }
  });

  // ============================================================
  // KEYBOARD SUPPORT — Enter submits current form
  // ============================================================
  allInputs.forEach(input => {
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        const form = this.closest('.sky-form, .pulse-form');
        if (form) {
          form.querySelector('.pulse-submit')?.click();
        }
      }
    });
  });

  // ============================================================
  // INIT
  // ============================================================
  console.log('🌆 Skyline — Auth ready');
  switchForm('login');

})();