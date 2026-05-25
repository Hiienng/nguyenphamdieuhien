/**
 * trial-status.js — Trial period UI management
 *
 * Handles:
 * - Fetching trial status from /api/v1/billing/trial-status
 * - Displaying trial banner (active or expired)
 * - Handling 403 trial_expired errors globally
 * - Showing upgrade modal when trial expires
 */

// ── Trial Status Management ────────────────────────────

let _cachedTrialStatus = null;

/**
 * Fetch trial status from backend
 */
async function fetchTrialStatus(token) {
  if (!token) {
    console.warn('[TrialStatus] No token provided');
    return null;
  }

  try {
    const response = await fetch('/api/v1/billing/trial-status', {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      console.warn('[TrialStatus] Failed to fetch trial status:', response.status);
      return null;
    }

    const data = await response.json();
    _cachedTrialStatus = data;
    return data;
  } catch (err) {
    console.error('[TrialStatus] Error fetching trial status:', err);
    return null;
  }
}

/**
 * Display trial banner in the container
 */
function displayTrialBanner(trialStatus) {
  const container = document.getElementById('trial-banner-container');
  if (!container) return;

  if (!trialStatus) {
    container.innerHTML = '';
    return;
  }

  if (trialStatus.trial_active) {
    // Active trial banner
    const daysText = trialStatus.days_remaining === 1 ? 'day' : 'days';
    container.innerHTML = `
      <div class="trial-banner trial-banner-active">
        <span class="trial-icon">⏳</span>
        <span class="trial-text">Free trial: <strong>${trialStatus.days_remaining} ${daysText} remaining</strong></span>
        <a href="/#pricing" class="trial-link">Upgrade now</a>
      </div>
    `;
  } else if (!trialStatus.can_access_features) {
    // Expired trial banner
    container.innerHTML = `
      <div class="trial-banner trial-banner-expired">
        <span class="trial-icon">⚠️</span>
        <span class="trial-text">Trial expired. <strong>Upgrade to continue.</strong></span>
        <button onclick="window.location.href='/#pricing'" class="trial-link btn-primary">Upgrade</button>
      </div>
    `;
  } else {
    // User has paid subscription
    container.innerHTML = '';
  }
}

/**
 * Initialize trial status on page load
 */
async function initTrialStatus() {
  const token = sessionStorage.getItem('EtseeMate_token');
  if (!token) {
    console.log('[TrialStatus] No token in session storage');
    return;
  }

  try {
    const trialStatus = await fetchTrialStatus(token);
    if (trialStatus) {
      displayTrialBanner(trialStatus);
    }
  } catch (err) {
    console.error('[TrialStatus] Failed to initialize trial status:', err);
  }
}

/**
 * Handle 403 trial_expired errors globally
 * Call this after any API call that might return 403
 */
function handleTrialExpiredError(error) {
  // Check if error is a 403 with trial_expired detail
  if (error.status === 403 && error.detail && error.detail.includes('trial_expired')) {
    showTrialExpiredModal();
  }
}

/**
 * Show modal when trial has expired
 */
function showTrialExpiredModal() {
  const modal = document.getElementById('trial-expired-modal');
  if (modal) {
    modal.classList.remove('hidden');
  }
}

/**
 * Hide the trial expired modal
 */
function hideTrialExpiredModal() {
  const modal = document.getElementById('trial-expired-modal');
  if (modal) {
    modal.classList.add('hidden');
  }
}

/**
 * Enhanced fetch wrapper to handle trial expiration
 * Wraps the existing authFetch function to catch 403 errors
 */
async function authFetchWithTrialCheck(url, opts = {}) {
  try {
    // Use the global authFetch if available, otherwise use fetch
    const fetchFn = typeof authFetch !== 'undefined' ? authFetch : fetch;
    const response = await fetchFn(url, opts);

    // If 403, check if it's a trial_expired error
    if (response.status === 403) {
      try {
        const errorData = await response.json();
        if (errorData.detail && errorData.detail.includes('trial_expired')) {
          showTrialExpiredModal();
          // Also update the banner to show expired state
          await refreshTrialStatus();
        }
      } catch {
        // Could not parse error response, but still 403
      }
    }

    return response;
  } catch (err) {
    console.error('[TrialStatus] Fetch error:', err);
    throw err;
  }
}

/**
 * Refresh trial status from server
 */
async function refreshTrialStatus() {
  const token = sessionStorage.getItem('EtseeMate_token');
  if (!token) return;

  const trialStatus = await fetchTrialStatus(token);
  if (trialStatus) {
    displayTrialBanner(trialStatus);
  }
}

// ── Auto-initialize on DOMContentLoaded ────────────────

document.addEventListener('DOMContentLoaded', () => {
  // Wait for user to be ready if available
  if (typeof _userReady !== 'undefined') {
    _userReady.then(() => {
      setTimeout(() => {
        initTrialStatus();
      }, 100);
    });
  } else {
    // Fallback: initialize immediately
    setTimeout(() => {
      initTrialStatus();
    }, 100);
  }
});

// ── Global error handler for fetch failures ────────────

// Store original fetch to wrap it
const originalFetch = window.fetch;

window.fetch = async function(...args) {
  const response = await originalFetch.apply(this, args);

  // Check for 403 trial_expired on any fetch
  if (response.status === 403) {
    try {
      const clonedResponse = response.clone();
      const errorData = await clonedResponse.json();
      if (errorData.detail && errorData.detail.includes('trial_expired')) {
        console.log('[TrialStatus] Trial expired detected in response');
        showTrialExpiredModal();
        // Refresh banner state
        await refreshTrialStatus();
      }
    } catch {
      // Could not parse error response
    }
  }

  return response;
};

// ── Export functions for external use ────────────────

window.trialStatus = {
  fetch: fetchTrialStatus,
  display: displayTrialBanner,
  init: initTrialStatus,
  handleError: handleTrialExpiredError,
  showModal: showTrialExpiredModal,
  hideModal: hideTrialExpiredModal,
  refresh: refreshTrialStatus,
  fetchWithCheck: authFetchWithTrialCheck,
  getCached: () => _cachedTrialStatus,
};
