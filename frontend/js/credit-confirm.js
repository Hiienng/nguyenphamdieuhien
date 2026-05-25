/**
 * credit-confirm.js — F10: Pre-action confirmation modal
 *
 * Exported as window.confirmCreditSpend(cost, featureName)
 *   → Promise<boolean>
 *
 * Behavior:
 *   - If balance > 3 (or unknown), resolves true silently.
 *   - If balance <= 3, shows a modal asking the user to confirm spend.
 *
 * Reads the latest balance from window.creditDisplay.getCached() if
 * available; otherwise falls back to _currentUser.credit_balance.
 */

(function () {
  'use strict';

  const LOW_BALANCE_THRESHOLD = 3;

  function getCurrentBalance() {
    try {
      if (window.creditDisplay && typeof window.creditDisplay.getCached === 'function') {
        const cached = window.creditDisplay.getCached();
        if (cached && typeof cached.total === 'number') return cached.total;
      }
    } catch (_) {}
    try {
      if (typeof _currentUser !== 'undefined' && _currentUser) {
        return _currentUser.credit_balance || 0;
      }
    } catch (_) {}
    return null; // unknown
  }

  function buildModal(cost, balance, featureName) {
    const featureLabel = featureName || 'this action';
    const costNoun = cost === 1 ? 'credit' : 'credits';
    const balNoun = balance === 1 ? 'credit' : 'credits';

    const modal = document.createElement('div');
    modal.className = 'credit-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.innerHTML = `
      <div class="credit-modal-content" role="document">
        <h2>Use ${cost} ${costNoun} to ${featureLabel}?</h2>
        <p>You have <strong>${balance} ${balNoun}</strong> remaining.</p>
        <div class="credit-modal-actions">
          <button type="button" class="credit-btn credit-btn-ghost" data-action="cancel">Cancel</button>
          <button type="button" class="credit-btn credit-btn-primary" data-action="confirm">
            Yes, use ${cost} ${costNoun}
          </button>
        </div>
      </div>
    `;
    return modal;
  }

  /**
   * Confirm spending `cost` credits for `featureName`.
   * @param {number} cost
   * @param {string} [featureName] - e.g. "score thumbnail"
   * @returns {Promise<boolean>}
   */
  async function confirmCreditSpend(cost, featureName) {
    cost = cost || 1;
    const balance = getCurrentBalance();

    // Unknown balance OR safely above threshold → no prompt
    if (balance === null || balance > LOW_BALANCE_THRESHOLD) return true;

    return new Promise(function (resolve) {
      const modal = buildModal(cost, balance, featureName);
      document.body.appendChild(modal);

      function cleanup(result) {
        modal.removeEventListener('click', onClick);
        document.removeEventListener('keydown', onKey);
        modal.remove();
        resolve(result);
      }
      function onClick(ev) {
        const target = ev.target;
        if (target === modal) return cleanup(false); // backdrop click
        const btn = target.closest && target.closest('button[data-action]');
        if (!btn) return;
        cleanup(btn.dataset.action === 'confirm');
      }
      function onKey(ev) {
        if (ev.key === 'Escape') cleanup(false);
        if (ev.key === 'Enter') cleanup(true);
      }

      modal.addEventListener('click', onClick);
      document.addEventListener('keydown', onKey);

      // Focus the confirm button for accessibility
      const confirmBtn = modal.querySelector('[data-action="confirm"]');
      if (confirmBtn) confirmBtn.focus();
    });
  }

  window.confirmCreditSpend = confirmCreditSpend;
})();
