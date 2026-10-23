/* ============================================================
   express · EXPRESS · TAB BAR CONTROLLER
   Pure UI — no API calls.
   ============================================================ */
(function () {
  'use strict';

  const TABS = ['home', 'invest', 'team', 'rewards', 'me'];
  const DEFAULT_TAB = 'home';

  // Auxiliary sections that should be hidden on tab change
  const AUX_SECTIONS = [
    'notificationsSection',
    'txnSection',
    'packagesSection',
  ];

  function hideAuxSections() {
    AUX_SECTIONS.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.hidden = true;
    });
  }

  function activate(tab) {
    if (!TABS.includes(tab)) tab = DEFAULT_TAB;

    // Toggle panels
    document.querySelectorAll('.express-tabpanel').forEach(p => {
      p.classList.toggle('is-active', p.dataset.tab === tab);
    });

    // Toggle bottom tab buttons
    document.querySelectorAll('.express-tab').forEach(b => {
      b.classList.toggle('is-active', b.dataset.tab === tab);
    });

    // ✅ Hide all auxiliary sections when switching tabs
    hideAuxSections();

    // Scroll to top of main
    const main = document.getElementById('expressMain');
    if (main) main.scrollTop = 0;

    // Persist
    try { sessionStorage.setItem('express_active_tab', tab); } catch (e) {}
    document.dispatchEvent(new CustomEvent('tab:changed', { detail: { tab } }));
  }

  // ✅ Toggle helper — click opens if hidden, closes if visible
  function toggleSection(id) {
    const s = document.getElementById(id);
    if (!s) return;

    if (s.hidden) {
      s.hidden = false;
      s.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else {
      s.hidden = true;
    }
  }

  function bind() {
    // Bottom tab buttons
    document.querySelectorAll('.express-tab').forEach(btn => {
      btn.addEventListener('click', () => activate(btn.dataset.tab));
    });

    // Home tab quick-access rows
    document.getElementById('quickMachines')?.addEventListener('click', () => activate('invest'));
    document.getElementById('quickTxns')?.addEventListener('click', () => activate('me'));
    document.getElementById('quickNotifications')?.addEventListener('click', () => activate('me'));

    // Me tab quick-access rows — now proper toggles
    document.getElementById('meNotifications')?.addEventListener('click', () => {
      toggleSection('notificationsSection');
    });
    document.getElementById('meTxns')?.addEventListener('click', () => {
      toggleSection('txnSection');
    });
    document.getElementById('meMachines')?.addEventListener('click', () => {
      toggleSection('packagesSection');
    });

    // ✅ Click outside dismisses any open auxiliary section
    document.addEventListener('click', (e) => {
      AUX_SECTIONS.forEach(id => {
        const s = document.getElementById(id);
        if (!s || s.hidden) return;

        // Ignore clicks inside the section
        if (s.contains(e.target)) return;

        // Ignore clicks on the trigger buttons that open them
        const triggers = [
          'meNotifications', 'meTxns', 'meMachines',
          'quickNotifications', 'quickTxns', 'quickMachines',
        ];
        for (const t of triggers) {
          const trigger = document.getElementById(t);
          if (trigger && (trigger === e.target || trigger.contains(e.target))) return;
        }

        s.hidden = true;
      });
    });

    // Restore last tab
    try {
      const saved = sessionStorage.getItem('express_active_tab');
      if (saved) activate(saved);
    } catch (e) {}
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind);
  } else {
    bind();
  }
})();