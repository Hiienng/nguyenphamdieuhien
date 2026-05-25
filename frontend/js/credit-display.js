/**
 * credit-display.js — F8 (chip + dropdown) and F11 (402 OOC modal)
 *
 * Composes on top of trial-status.js's existing window.fetch wrapper
 * (does NOT replace it) — wraps once more so 402 responses surface
 * the Out-of-Credits modal globally.
 *
 * Listens for the custom `credit-spent` event to refresh the chip
 * after any credit-consuming action.
 *
 * Exposes window.creditDisplay = { refresh, getCached, showOutOfCredits, ... }
 */

(function () {
  'use strict';

  const API_CREDITS = '/api/v1/billing/credits';
  const API_PLANS = '/api/v1/billing/plans';
  const API_SUBSCRIBE = '/api/v1/billing/subscribe';
  const API_TOPUP = '/api/v1/billing/topup';

  let _cached = null;          // last /billing/credits response
  let _cachedPlans = null;     // last /billing/plans response
  let _refreshInflight = null; // dedupe concurrent refreshes
  let _oocOpen = false;        // prevent stacking OOC modals

  // ── Utilities ─────────────────────────────────────────

  function getToken() {
    try { return sessionStorage.getItem('EtseeMate_token'); } catch (_) { return null; }
  }

  function authHeaders() {
    const t = getToken();
    return t ? { 'Authorization': 'Bearer ' + t } : {};
  }

  function formatResetIn(resetAt) {
    if (!resetAt) return '';
    const reset = new Date(resetAt).getTime();
    if (isNaN(reset)) return '';
    const diff = reset - Date.now();
    if (diff <= 0) return 'resets soon';
    const days = Math.ceil(diff / (1000 * 60 * 60 * 24));
    if (days >= 2) return `resets in ${days} days`;
    if (days === 1) return 'resets in 1 day';
    const hrs = Math.max(1, Math.ceil(diff / (1000 * 60 * 60)));
    return `resets in ${hrs}h`;
  }

  // ── Chip rendering ────────────────────────────────────

  function ensureChip() {
    let wrap = document.getElementById('credit-chip-wrap');
    if (wrap) return wrap;

    // Try to inject into the nav-links list (app.html header)
    const navLinks = document.querySelector('nav.nav .nav-links');
    if (!navLinks) return null;

    // Hide the legacy mini badge if present
    const legacy = document.getElementById('nav-credit-badge');
    if (legacy) legacy.style.display = 'none';

    const li = document.createElement('li');
    li.id = 'credit-chip-wrap';
    li.className = 'credit-chip-wrap';
    li.innerHTML = `
      <button type="button"
              id="credit-chip"
              class="credit-chip"
              aria-haspopup="true"
              aria-expanded="false"
              aria-label="Credits">
        <span class="credit-chip-icon" aria-hidden="true">⚡</span>
        <span id="credit-chip-count">—</span>
        <span class="credit-chip-label">credits</span>
        <span class="credit-chip-caret" aria-hidden="true">▾</span>
      </button>
      <div id="credit-dropdown" class="credit-dropdown hidden" role="menu" aria-label="Credit details"></div>
    `;
    // Place before the "Docs" link if possible, else prepend
    const docsLink = Array.from(navLinks.children).find(c =>
      c.querySelector && c.querySelector('a[href$="docs.html"]')
    );
    if (docsLink) navLinks.insertBefore(li, docsLink);
    else navLinks.insertBefore(li, navLinks.firstChild);

    const btn = li.querySelector('#credit-chip');
    btn.addEventListener('click', toggleDropdown);
    document.addEventListener('click', onDocClick);
    document.addEventListener('keydown', onDocKey);
    return li;
  }

  function renderChip(data) {
    const wrap = ensureChip();
    if (!wrap) return;
    const btn = wrap.querySelector('#credit-chip');
    const count = wrap.querySelector('#credit-chip-count');
    if (!btn || !count) return;

    const total = data && typeof data.total === 'number' ? data.total : 0;
    count.textContent = total;

    if (total === 0) {
      btn.classList.add('credit-chip-empty');
    } else {
      btn.classList.remove('credit-chip-empty');
    }
    renderDropdown(data);
  }

  function renderDropdown(data) {
    const dd = document.getElementById('credit-dropdown');
    if (!dd) return;
    const sub = data && typeof data.subscription === 'number' ? data.subscription : 0;
    const top = data && typeof data.topup === 'number' ? data.topup : 0;
    const resetMeta = formatResetIn(data && data.reset_at);
    const hasSub = !!(data && data.has_subscription);

    dd.innerHTML = `
      <div class="credit-dropdown-row">
        <span class="credit-dropdown-label">Subscription credits</span>
        <span class="credit-dropdown-value">${sub}
          ${resetMeta ? `<span class="credit-dropdown-meta">(${resetMeta})</span>` : ''}
        </span>
      </div>
      <div class="credit-dropdown-row">
        <span class="credit-dropdown-label">Top-up credits</span>
        <span class="credit-dropdown-value">${top}
          <span class="credit-dropdown-meta">(never expire)</span>
        </span>
      </div>
      <div class="credit-dropdown-divider"></div>
      <div class="credit-dropdown-actions">
        <button type="button" class="credit-dropdown-btn" data-cd-action="buy">+ Buy credits</button>
        ${hasSub ? '' : `
          <button type="button" class="credit-dropdown-btn credit-dropdown-btn-primary" data-cd-action="upgrade">
            Upgrade to Basic
          </button>
        `}
      </div>
    `;
    dd.querySelectorAll('button[data-cd-action]').forEach(b => {
      b.addEventListener('click', (ev) => {
        ev.stopPropagation();
        closeDropdown();
        if (b.dataset.cdAction === 'buy') openOutOfCreditsModal({ needed: 0, available: (data && data.total) || 0, mode: 'buy' });
        else if (b.dataset.cdAction === 'upgrade') startSubscribe('basic_monthly');
      });
    });
  }

  function toggleDropdown(ev) {
    ev.stopPropagation();
    const dd = document.getElementById('credit-dropdown');
    const btn = document.getElementById('credit-chip');
    if (!dd || !btn) return;
    const isOpen = !dd.classList.contains('hidden');
    if (isOpen) closeDropdown();
    else {
      dd.classList.remove('hidden');
      btn.setAttribute('aria-expanded', 'true');
    }
  }
  function closeDropdown() {
    const dd = document.getElementById('credit-dropdown');
    const btn = document.getElementById('credit-chip');
    if (dd) dd.classList.add('hidden');
    if (btn) btn.setAttribute('aria-expanded', 'false');
  }
  function onDocClick(ev) {
    const wrap = document.getElementById('credit-chip-wrap');
    if (wrap && !wrap.contains(ev.target)) closeDropdown();
  }
  function onDocKey(ev) { if (ev.key === 'Escape') closeDropdown(); }

  // ── API helpers ───────────────────────────────────────

  async function fetchCredits() {
    const token = getToken();
    if (!token) return null;
    try {
      // Use _originalFetch path to avoid recursive 402 handling on the
      // credits endpoint itself.
      const fn = window._creditDisplayBaseFetch || window.fetch;
      const res = await fn(API_CREDITS, {
        method: 'GET',
        headers: Object.assign({ 'Content-Type': 'application/json' }, authHeaders()),
      });
      if (!res.ok) return null;
      return await res.json();
    } catch (e) {
      console.warn('[creditDisplay] fetchCredits failed:', e);
      return null;
    }
  }

  async function fetchPlans() {
    if (_cachedPlans) return _cachedPlans;
    try {
      const fn = window._creditDisplayBaseFetch || window.fetch;
      const res = await fn(API_PLANS, {
        method: 'GET',
        headers: Object.assign({ 'Content-Type': 'application/json' }, authHeaders()),
      });
      if (!res.ok) return null;
      _cachedPlans = await res.json();
      return _cachedPlans;
    } catch (e) {
      console.warn('[creditDisplay] fetchPlans failed:', e);
      return null;
    }
  }

  async function refresh() {
    if (_refreshInflight) return _refreshInflight;
    _refreshInflight = (async () => {
      const data = await fetchCredits();
      if (data) {
        _cached = data;
        renderChip(data);
      }
      return data;
    })();
    try { return await _refreshInflight; }
    finally { _refreshInflight = null; }
  }

  // ── F11: Out-of-Credits modal ─────────────────────────

  function defaultTopups() {
    // Fallback if /plans not loaded yet
    return [
      { code: 'topup_5',  price_usd: 5,  credits: 15 },
      { code: 'topup_10', price_usd: 10, credits: 40, best_value: true },
    ];
  }

  async function openOutOfCreditsModal(detail) {
    if (_oocOpen) return;
    _oocOpen = true;

    // Try to enrich with /plans data
    const plans = await fetchPlans();
    const topups = (plans && Array.isArray(plans.topups) && plans.topups.length)
      ? plans.topups : defaultTopups();
    const basicPlan = plans && Array.isArray(plans.plans)
      ? (plans.plans.find(p => p.code === 'basic_monthly') || plans.plans[0])
      : null;

    const needed = (detail && detail.needed) || 1;
    const available = (detail && typeof detail.available === 'number')
      ? detail.available
      : ((_cached && _cached.total) || 0);
    const mode = (detail && detail.mode) || 'oop'; // 'oop' or 'buy'

    const title = mode === 'buy' ? '💳 Buy credits' : '💳 Out of credits';
    const body = mode === 'buy'
      ? `<p>Choose a top-up pack. You currently have <strong>${available}</strong> credit${available === 1 ? '' : 's'}.</p>`
      : `<p>This action needs <strong>${needed}</strong> credit${needed === 1 ? '' : 's'} but you have <strong>${available}</strong>.</p>`;

    const cardsHtml = topups.map(t => {
      const credits = t.credits;
      const price = t.price_usd;
      const per = credits > 0 ? (price / credits) : 0;
      const best = t.best_value ? `<div class="credit-topup-per" style="color:var(--terracotta);font-weight:600">Best value</div>` : '';
      return `
        <button type="button" class="credit-topup-card" data-topup-code="${t.code}">
          <div class="credit-topup-price">$${price}</div>
          <div class="credit-topup-credits">${credits} cr.</div>
          <div class="credit-topup-per">$${per.toFixed(2)} ea</div>
          ${best}
        </button>
      `;
    }).join('');

    const upgradeHtml = basicPlan ? `
      <div class="credit-upgrade-callout">
        Or upgrade to <strong>${basicPlan.name || 'Basic'}</strong> —
        <strong>$${basicPlan.price_usd || 9}/mo</strong> +
        ${basicPlan.monthly_credits || 5} monthly credits + full access.
      </div>
    ` : `
      <div class="credit-upgrade-callout">
        Or upgrade to <strong>Basic</strong> — <strong>$9/mo</strong> + 5 monthly credits + full access.
      </div>
    `;

    const modal = document.createElement('div');
    modal.className = 'credit-modal';
    modal.id = 'credit-ooc-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.innerHTML = `
      <div class="credit-modal-content" role="document">
        <h2>${title}</h2>
        ${body}
        <div class="credit-topup-grid">${cardsHtml}</div>
        ${upgradeHtml}
        <div class="credit-modal-actions">
          <button type="button" class="credit-btn credit-btn-ghost" data-ooc-action="cancel">Cancel</button>
          <button type="button" class="credit-btn" data-ooc-action="buy" disabled>Buy credits</button>
          <button type="button" class="credit-btn credit-btn-primary" data-ooc-action="upgrade">Upgrade</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);

    let selectedCode = null;
    const buyBtn = modal.querySelector('[data-ooc-action="buy"]');

    modal.querySelectorAll('.credit-topup-card').forEach(card => {
      card.addEventListener('click', () => {
        modal.querySelectorAll('.credit-topup-card').forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        selectedCode = card.dataset.topupCode;
        buyBtn.disabled = false;
      });
    });

    function close() {
      modal.remove();
      _oocOpen = false;
    }

    modal.addEventListener('click', async (ev) => {
      if (ev.target === modal) return close();
      const btn = ev.target.closest && ev.target.closest('button[data-ooc-action]');
      if (!btn) return;
      const act = btn.dataset.oocAction;
      if (act === 'cancel') return close();
      if (act === 'buy') {
        if (!selectedCode) return;
        await startTopup(selectedCode);
      } else if (act === 'upgrade') {
        const planCode = (basicPlan && basicPlan.code) || 'basic_monthly';
        await startSubscribe(planCode);
      }
    });
  }

  async function startTopup(packCode) {
    try {
      const fn = window._creditDisplayBaseFetch || window.fetch;
      const res = await fn(API_TOPUP, {
        method: 'POST',
        headers: Object.assign({ 'Content-Type': 'application/json' }, authHeaders()),
        body: JSON.stringify({ pack: packCode }),
      });
      if (!res.ok) throw new Error('Topup failed: ' + res.status);
      const data = await res.json();
      if (data && data.checkout_url) window.location = data.checkout_url;
    } catch (e) {
      console.error('[creditDisplay] topup error:', e);
      alert('Could not start checkout. Please try again.');
    }
  }

  async function startSubscribe(planCode) {
    try {
      const fn = window._creditDisplayBaseFetch || window.fetch;
      const res = await fn(API_SUBSCRIBE, {
        method: 'POST',
        headers: Object.assign({ 'Content-Type': 'application/json' }, authHeaders()),
        body: JSON.stringify({ plan: planCode || 'basic_monthly' }),
      });
      if (!res.ok) throw new Error('Subscribe failed: ' + res.status);
      const data = await res.json();
      if (data && data.checkout_url) window.location = data.checkout_url;
    } catch (e) {
      console.error('[creditDisplay] subscribe error:', e);
      alert('Could not start checkout. Please try again.');
    }
  }

  // ── Global 402 fetch wrapper (composes on top of any existing wrapper) ──
  // trial-status.js already wraps window.fetch; we keep that base and wrap once more.
  const _baseFetch = window.fetch;
  window._creditDisplayBaseFetch = _baseFetch;

  window.fetch = async function (...args) {
    const response = await _baseFetch.apply(this, args);

    if (response.status === 402) {
      try {
        const cloned = response.clone();
        const errData = await cloned.json();
        const det = errData && errData.detail;
        const isInsufficient =
          (det && typeof det === 'object' && det.type === 'insufficient_credits') ||
          (typeof det === 'string' && det.includes('insufficient_credits'));
        if (isInsufficient) {
          const payload = (det && typeof det === 'object') ? det : {};
          openOutOfCreditsModal({
            needed: payload.needed || 1,
            available: typeof payload.available === 'number' ? payload.available : 0,
          });
          // Also refresh the chip — backend may have updated the balance
          refresh();
        }
      } catch (_) { /* response wasn't JSON */ }
    }
    return response;
  };

  // ── Event hooks ───────────────────────────────────────

  document.addEventListener('credit-spent', () => { refresh(); });

  // Initial paint on DOM ready (after auth bootstrap if available)
  function boot() {
    ensureChip();
    refresh();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      if (typeof _userReady !== 'undefined' && _userReady && _userReady.then) {
        _userReady.then(() => setTimeout(boot, 100));
      } else {
        setTimeout(boot, 150);
      }
    });
  } else {
    if (typeof _userReady !== 'undefined' && _userReady && _userReady.then) {
      _userReady.then(() => setTimeout(boot, 100));
    } else {
      setTimeout(boot, 150);
    }
  }

  // ── Public API ────────────────────────────────────────
  window.creditDisplay = {
    refresh: refresh,
    getCached: () => _cached,
    showOutOfCredits: openOutOfCreditsModal,
    startTopup: startTopup,
    startSubscribe: startSubscribe,
  };
})();
