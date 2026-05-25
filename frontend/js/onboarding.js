/* ============================================
   ONBOARDING WIZARD - ETSEEMATE
   Frontend Agent (F6)

   Flow:
   1. Check onboarding status on page load
   2. If not completed, show 4-step wizard
   3. Step 1: Product categories (1-3 selection)
   4. Step 2: Seller location (country dropdown)
   5. Step 3: Confirmation & warning
   6. Step 4: Submit & success
   ============================================ */

// State management
const ONBOARDING_STATE = {
  currentStep: 1,
  totalSteps: 4,
  productCategories: [],
  sellerLocation: '',
  understandsWarning: false,
  isSubmitting: false,
  availableCategories: [],
  availableCountries: [],
};

// Configuration
const ONBOARDING_CONFIG = {
  maxProductCategories: 3,
  apiBaseUrl: '/api/v1',
};

// Initialize onboarding on page load
document.addEventListener('DOMContentLoaded', async () => {
  await initializeOnboarding();
});

/**
 * Initialize onboarding: check status and show wizard if needed
 */
async function initializeOnboarding() {
  try {
    // Check onboarding status
    const userResponse = await fetchApi('/auth/me');

    if (userResponse.onboarding_completed) {
      // User already completed onboarding, hide wizard and show dashboard
      hideOnboardingWizard();
      showDashboard();
      return;
    }

    // Fetch product categories and countries
    await fetchProductCategories();
    await fetchCountries();

    // Show onboarding wizard
    showOnboardingWizard();

    // Wire up buttons and render dynamic content (checkboxes, dropdown)
    initializeEventListeners();
  } catch (error) {
    console.error('Failed to initialize onboarding:', error);
    showOnboardingError('Failed to load onboarding. Please refresh the page.');
  }
}

/**
 * Fetch product categories from API
 */
async function fetchProductCategories() {
  try {
    const response = await fetchApi('/references/product-categories');
    if (response.categories && Array.isArray(response.categories)) {
      ONBOARDING_STATE.availableCategories = response.categories;
    }
  } catch (error) {
    console.warn('Failed to fetch product categories:', error);
    // Fallback to default categories
    ONBOARDING_STATE.availableCategories = getDefaultProductCategories();
  }
}

/**
 * Fetch countries list from API or use default
 */
async function fetchCountries() {
  try {
    const response = await fetchApi('/references/countries');
    if (response.countries && Array.isArray(response.countries)) {
      ONBOARDING_STATE.availableCountries = response.countries;
      return;
    }
  } catch (error) {
    console.warn('Failed to fetch countries, using defaults:', error);
  }

  // Fallback to default countries
  ONBOARDING_STATE.availableCountries = getDefaultCountries();
}

/**
 * Generic fetch wrapper with auth token
 */
async function fetchApi(endpoint, options = {}) {
  const token = sessionStorage.getItem('EtseeMate_token');
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(ONBOARDING_CONFIG.apiBaseUrl + endpoint, {
    ...options,
    headers,
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'API error' }));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}

/**
 * Show onboarding wizard modal
 */
function showOnboardingWizard() {
  const wizard = document.getElementById('onboarding-wizard');
  if (wizard) {
    wizard.style.display = 'flex';
  }

  // Hide main dashboard until onboarding completes
  const mainHub = document.querySelector('.hub-wrapper');
  if (mainHub) {
    mainHub.style.display = 'none';
  }
}

/**
 * Hide onboarding wizard modal
 */
function hideOnboardingWizard() {
  const wizard = document.getElementById('onboarding-wizard');
  if (wizard) {
    wizard.style.display = 'none';
  }

  // Show main dashboard
  const mainHub = document.querySelector('.hub-wrapper');
  if (mainHub) {
    mainHub.style.display = 'block';
  }
}

/**
 * Show dashboard (called after onboarding completes)
 */
function showDashboard() {
  const mainHub = document.querySelector('.hub-wrapper');
  if (mainHub) {
    mainHub.style.display = 'block';
  }
}

/**
 * Show error message in wizard
 */
function showOnboardingError(message) {
  const errorEl = document.getElementById('onboarding-error');
  if (errorEl) {
    errorEl.textContent = message;
    errorEl.style.display = 'block';
  }
}

/**
 * Clear error message
 */
function clearOnboardingError() {
  const errorEl = document.getElementById('onboarding-error');
  if (errorEl) {
    errorEl.textContent = '';
    errorEl.style.display = 'none';
  }
}

/**
 * Go to specific step
 */
function goToStep(step) {
  if (step < 1 || step > ONBOARDING_STATE.totalSteps) return;

  // Hide all steps
  document.querySelectorAll('.onboarding-step').forEach((el) => {
    el.style.display = 'none';
  });

  // Show current step
  const stepEl = document.getElementById(`step-${step}`);
  if (stepEl) {
    stepEl.style.display = 'block';
  }

  // Update progress bar
  updateProgressBar(step);

  // Update button states
  updateButtonStates(step);

  ONBOARDING_STATE.currentStep = step;
  clearOnboardingError();
}

/**
 * Next step
 */
function nextStep() {
  // Validate current step
  if (!validateCurrentStep()) {
    return;
  }

  goToStep(ONBOARDING_STATE.currentStep + 1);
}

/**
 * Previous step
 */
function prevStep() {
  goToStep(ONBOARDING_STATE.currentStep - 1);
}

/**
 * Validate current step data
 */
function validateCurrentStep() {
  const step = ONBOARDING_STATE.currentStep;

  if (step === 1) {
    // Validate product selection
    if (ONBOARDING_STATE.productCategories.length === 0) {
      showOnboardingError('Please select at least 1 product category.');
      return false;
    }
  } else if (step === 2) {
    // Validate seller location
    if (!ONBOARDING_STATE.sellerLocation) {
      showOnboardingError('Please select a seller location.');
      return false;
    }
  } else if (step === 3) {
    // Validate understanding checkbox
    if (!ONBOARDING_STATE.understandsWarning) {
      showOnboardingError('Please acknowledge that you understand your product choices are important.');
      return false;
    }
  }

  return true;
}

/**
 * Update progress bar
 */
function updateProgressBar(step) {
  const progressBar = document.getElementById('onboarding-progress-bar');
  if (progressBar) {
    const percentage = (step / ONBOARDING_STATE.totalSteps) * 100;
    progressBar.style.width = `${percentage}%`;
  }

  // Update step counter
  const stepCounter = document.getElementById('onboarding-step-counter');
  if (stepCounter) {
    stepCounter.textContent = `${step}/${ONBOARDING_STATE.totalSteps}`;
  }
}

/**
 * Update button states based on current step
 */
function updateButtonStates(step) {
  const prevBtn = document.getElementById('onboarding-prev-btn');
  const nextBtn = document.getElementById('onboarding-next-btn');
  const submitBtn = document.getElementById('onboarding-submit-btn');

  // Hide next and submit buttons, show them as needed
  if (nextBtn) nextBtn.style.display = step < ONBOARDING_STATE.totalSteps ? 'block' : 'none';
  if (submitBtn) submitBtn.style.display = step === ONBOARDING_STATE.totalSteps ? 'block' : 'none';

  // Disable back button on step 1
  if (prevBtn) {
    prevBtn.disabled = step === 1;
  }
}

/**
 * Handle product category checkbox change
 */
function handleProductCategoryChange(categoryId, isChecked) {
  if (isChecked) {
    // Check if we've reached max products
    if (ONBOARDING_STATE.productCategories.length >= ONBOARDING_CONFIG.maxProductCategories) {
      // Uncheck the checkbox
      const checkbox = document.getElementById(`category-${categoryId}`);
      if (checkbox) checkbox.checked = false;
      showOnboardingError(`Maximum ${ONBOARDING_CONFIG.maxProductCategories} products allowed.`);
      return;
    }
    ONBOARDING_STATE.productCategories.push(categoryId);
  } else {
    ONBOARDING_STATE.productCategories = ONBOARDING_STATE.productCategories.filter((c) => c !== categoryId);
  }

  // Update count display
  updateProductCountDisplay();
  clearOnboardingError();
}

/**
 * Update product count display
 */
function updateProductCountDisplay() {
  const countEl = document.getElementById('product-count');
  if (countEl) {
    countEl.textContent = `Selected: ${ONBOARDING_STATE.productCategories.length}/${ONBOARDING_CONFIG.maxProductCategories}`;
  }

  // Disable checkboxes if max reached
  const checkboxes = document.querySelectorAll('.category-checkbox');
  checkboxes.forEach((checkbox) => {
    const isSelected = ONBOARDING_STATE.productCategories.includes(checkbox.value);
    checkbox.disabled = !isSelected && ONBOARDING_STATE.productCategories.length >= ONBOARDING_CONFIG.maxProductCategories;
  });
}

/**
 * Handle seller location change
 */
function handleSellerLocationChange(countryCode) {
  ONBOARDING_STATE.sellerLocation = countryCode;
  clearOnboardingError();
}

/**
 * Handle understanding checkbox change
 */
function handleUnderstandingChange(isChecked) {
  ONBOARDING_STATE.understandsWarning = isChecked;
  updateSubmitButtonState();
  clearOnboardingError();
}

/**
 * Update submit button state
 */
function updateSubmitButtonState() {
  const submitBtn = document.getElementById('onboarding-submit-btn');
  if (submitBtn) {
    submitBtn.disabled = !ONBOARDING_STATE.understandsWarning;
  }
}

/**
 * Handle form submission
 */
async function handleOnboardingSubmit() {
  clearOnboardingError();

  // Final validation
  if (!validateCurrentStep()) {
    return;
  }

  const submitBtn = document.getElementById('onboarding-submit-btn');
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = 'Setting up your account...';
  }

  try {
    ONBOARDING_STATE.isSubmitting = true;

    const response = await fetchApi('/auth/onboarding/setup', {
      method: 'POST',
      body: JSON.stringify({
        product_categories: ONBOARDING_STATE.productCategories,
        seller_location: ONBOARDING_STATE.sellerLocation,
      }),
    });

    if (response.success) {
      showOnboardingSuccess();
      setTimeout(() => {
        // Redirect to app without onboarding flag
        window.location.href = '/app.html';
      }, 2000);
    }
  } catch (error) {
    console.error('Onboarding submission failed:', error);
    showOnboardingError(error.message || 'Failed to complete setup. Please try again.');

    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Complete Setup';
    }
  } finally {
    ONBOARDING_STATE.isSubmitting = false;
  }
}

/**
 * Show success message
 */
function showOnboardingSuccess() {
  const successEl = document.getElementById('onboarding-success');
  if (successEl) {
    successEl.style.display = 'block';
  }

  const wizardContent = document.querySelector('.onboarding-content');
  if (wizardContent) {
    wizardContent.style.display = 'none';
  }
}

/**
 * Render the smart category picker:
 *   • Search bar (filter by typing)
 *   • Selected-chips bar (quick removal)
 *   • Grouped pills with data-availability dots
 *   • Scrollable container + legend
 *
 * Re-renders on every search input or selection change so the chip state stays
 * in sync. Selection state lives in ONBOARDING_STATE.productCategories.
 */
function renderProductCategories() {
  const container = document.getElementById('product-categories-list');
  if (!container) return;

  // Build the static shell only on first render
  if (!container.dataset.initialized) {
    container.innerHTML = `
      <div class="onboarding-category-search">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true">
          <circle cx="7" cy="7" r="5"/>
          <line x1="11" y1="11" x2="15" y2="15" stroke-linecap="round"/>
        </svg>
        <input type="text" id="category-search-input"
               placeholder="Search 50+ Etsy categories…"
               autocomplete="off" spellcheck="false">
      </div>
      <div class="onboarding-selected-bar" id="category-selected-bar"></div>
      <div class="onboarding-category-scroll" id="category-scroll-area"></div>
      <div class="onboarding-category-legend">
        <span><span class="onboarding-data-dot"></span> Market data ready</span>
        <span><span class="onboarding-data-dot onboarding-data-dot-pending"></span> Coming soon</span>
      </div>
    `;
    container.dataset.initialized = 'true';

    const searchInput = container.querySelector('#category-search-input');
    searchInput.addEventListener('input', (e) => {
      ONBOARDING_STATE._categorySearch = e.target.value.trim().toLowerCase();
      renderCategoryPills();
      renderSelectedChips();
    });
  }

  renderCategoryPills();
  renderSelectedChips();
}

/**
 * Render the grouped pill grid inside the scroll area, filtered by search.
 */
function renderCategoryPills() {
  const scrollArea = document.getElementById('category-scroll-area');
  if (!scrollArea) return;

  const query = ONBOARDING_STATE._categorySearch || '';
  const selectedSet = new Set(ONBOARDING_STATE.productCategories);
  const atMax = selectedSet.size >= 3;

  // Filter
  const filtered = ONBOARDING_STATE.availableCategories.filter((cat) => {
    if (!query) return true;
    const hay = `${cat.label || ''} ${cat.name || ''} ${cat.group || ''}`.toLowerCase();
    return hay.includes(query);
  });

  if (filtered.length === 0) {
    scrollArea.innerHTML =
      `<div class="onboarding-category-empty">No categories match "${escapeHtml(query)}". Try a different keyword or pick "Other Products".</div>`;
    return;
  }

  // Group filtered results
  const grouped = {};
  filtered.forEach((cat) => {
    const g = cat.group || 'Other';
    (grouped[g] = grouped[g] || []).push(cat);
  });

  const groupOrder = [
    'Clothing', 'Accessories', 'Home & Living', 'Art & Prints',
    'Stickers & Paper', 'Kids & Baby', 'Weddings', 'Digital Goods',
    'Beauty & Bath', 'Pets', 'Other',
  ];
  const orderedGroups = groupOrder.filter((g) => grouped[g]);
  Object.keys(grouped).forEach((g) => {
    if (!orderedGroups.includes(g)) orderedGroups.push(g);
  });

  scrollArea.innerHTML = '';
  orderedGroups.forEach((groupName) => {
    const header = document.createElement('h4');
    header.className = 'onboarding-category-group';
    header.textContent = groupName;
    scrollArea.appendChild(header);

    const grid = document.createElement('div');
    grid.className = 'onboarding-category-grid';

    grouped[groupName].forEach((category) => {
      const checked = selectedSet.has(category.id);
      const wrapper = document.createElement('div');
      wrapper.className = 'onboarding-checkbox-wrapper';

      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.id = `category-${category.id}`;
      checkbox.value = category.id;
      checkbox.className = 'category-checkbox';
      checkbox.checked = checked;
      checkbox.disabled = !checked && atMax;
      checkbox.addEventListener('change', (e) => {
        handleProductCategoryChange(category.id, e.target.checked);
        // Re-render so pills disable/enable based on the new max-3 state
        renderCategoryPills();
        renderSelectedChips();
      });

      const label = document.createElement('label');
      label.htmlFor = `category-${category.id}`;
      label.className = 'onboarding-checkbox-label';

      const dot = document.createElement('span');
      dot.className = category.has_data
        ? 'onboarding-data-dot'
        : 'onboarding-data-dot onboarding-data-dot-pending';
      dot.title = category.has_data
        ? 'Market data available now'
        : 'We will start crawling this category for you';
      label.appendChild(dot);
      label.appendChild(document.createTextNode(category.label || category.name));

      wrapper.appendChild(checkbox);
      wrapper.appendChild(label);
      grid.appendChild(wrapper);
    });

    scrollArea.appendChild(grid);
  });
}

/**
 * Render the selected-chips bar at the top of the picker.
 */
function renderSelectedChips() {
  const bar = document.getElementById('category-selected-bar');
  if (!bar) return;

  const ids = ONBOARDING_STATE.productCategories;
  if (ids.length === 0) {
    bar.innerHTML = '<span class="onboarding-selected-empty">No categories selected yet — pick up to 3 below.</span>';
    return;
  }

  bar.innerHTML = '';
  ids.forEach((id) => {
    const cat = ONBOARDING_STATE.availableCategories.find((c) => c.id === id);
    if (!cat) return;
    const chip = document.createElement('span');
    chip.className = 'onboarding-selected-chip';
    chip.appendChild(document.createTextNode(cat.label || cat.name));

    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.setAttribute('aria-label', `Remove ${cat.label || cat.name}`);
    removeBtn.innerHTML = '×';
    removeBtn.addEventListener('click', () => {
      handleProductCategoryChange(id, false);
      renderCategoryPills();
      renderSelectedChips();
    });
    chip.appendChild(removeBtn);
    bar.appendChild(chip);
  });
}

/** Tiny HTML-escape helper for safe interpolation in the empty-state message. */
function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Render country dropdown
 */
function renderCountryDropdown() {
  const select = document.getElementById('seller-location-select');
  if (!select) return;

  // Clear existing options
  select.innerHTML = '<option value="">-- Select a country --</option>';

  ONBOARDING_STATE.availableCountries.forEach((country) => {
    const option = document.createElement('option');
    option.value = country.code;
    option.textContent = country.label;
    select.appendChild(option);
  });

  select.addEventListener('change', (e) => {
    handleSellerLocationChange(e.target.value);
  });
}

/**
 * Initialize all event listeners
 */
function initializeEventListeners() {
  // Next/Previous/Submit buttons
  const nextBtn = document.getElementById('onboarding-next-btn');
  const prevBtn = document.getElementById('onboarding-prev-btn');
  const submitBtn = document.getElementById('onboarding-submit-btn');

  if (nextBtn) nextBtn.addEventListener('click', nextStep);
  if (prevBtn) prevBtn.addEventListener('click', prevStep);
  if (submitBtn) submitBtn.addEventListener('click', handleOnboardingSubmit);

  // Understanding checkbox
  const understandingCheckbox = document.getElementById('understanding-checkbox');
  if (understandingCheckbox) {
    understandingCheckbox.addEventListener('change', (e) => {
      handleUnderstandingChange(e.target.checked);
    });
  }

  // Render dynamic content
  renderProductCategories();
  renderCountryDropdown();

  // Go to step 1
  goToStep(1);
}

/**
 * Default product categories (fallback)
 */
function getDefaultProductCategories() {
  return [
    { id: 'onesie', name: 'onesie', label: 'Custom Onesie' },
    { id: 'blanket', name: 'blanket', label: 'Personalized Blanket' },
    { id: 'sweater', name: 'sweater', label: 'Custom Sweater' },
    { id: 'crown', name: 'crown', label: 'Birthday Crown' },
    { id: 'shirt', name: 'shirt', label: 'Custom Shirt' },
    { id: 'other', name: 'other', label: 'Other Products' },
  ];
}

/**
 * Default countries (fallback - most common)
 */
function getDefaultCountries() {
  return [
    { code: 'US', label: 'United States' },
    { code: 'UK', label: 'United Kingdom' },
    { code: 'CA', label: 'Canada' },
    { code: 'AU', label: 'Australia' },
    { code: 'DE', label: 'Germany' },
    { code: 'FR', label: 'France' },
    { code: 'NL', label: 'Netherlands' },
    { code: 'ES', label: 'Spain' },
    { code: 'IT', label: 'Italy' },
    { code: 'JP', label: 'Japan' },
    { code: 'CN', label: 'China' },
    { code: 'SG', label: 'Singapore' },
    { code: 'IN', label: 'India' },
    { code: 'BR', label: 'Brazil' },
    { code: 'MX', label: 'Mexico' },
  ];
}

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    ONBOARDING_STATE,
    initializeOnboarding,
    nextStep,
    prevStep,
    handleProductCategoryChange,
    handleSellerLocationChange,
    handleOnboardingSubmit,
  };
}
