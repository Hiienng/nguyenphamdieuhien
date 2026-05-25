/* ============================================
   LANDING PAGE - JAVASCRIPT INTERACTIONS
   EtseeMate MVP Landing Page
   ============================================ */

/* ============================================
   1. CAROUSEL / SLIDER FUNCTIONALITY
   ============================================ */
const CAROUSEL_CONFIG = {
  currentSlide: 0,
  totalSlides: 3,
  autoPlayInterval: null,
  autoPlayDelay: 5000,
};

function carouselInit() {
  startCarouselAutoPlay();
}

function carouselGoto(index) {
  const slides = document.querySelectorAll('.lp-carousel-slide');
  const dots = document.querySelectorAll('.lp-carousel-dot');

  // Validate index
  if (index < 0 || index >= slides.length) return;

  // Remove active state from all slides and dots
  slides.forEach((slide) => slide.classList.remove('lp-carousel-slide-active'));
  dots.forEach((dot) => dot.classList.remove('lp-carousel-dot-active'));

  // Add active state to current slide and dot
  slides[index].classList.add('lp-carousel-slide-active');
  dots[index].classList.add('lp-carousel-dot-active');

  CAROUSEL_CONFIG.currentSlide = index;

  // Reset auto-play timer
  stopCarouselAutoPlay();
  startCarouselAutoPlay();
}

function carouselNext() {
  let nextIndex = CAROUSEL_CONFIG.currentSlide + 1;
  if (nextIndex >= CAROUSEL_CONFIG.totalSlides) {
    nextIndex = 0;
  }
  carouselGoto(nextIndex);
}

function carouselPrev() {
  let prevIndex = CAROUSEL_CONFIG.currentSlide - 1;
  if (prevIndex < 0) {
    prevIndex = CAROUSEL_CONFIG.totalSlides - 1;
  }
  carouselGoto(prevIndex);
}

function startCarouselAutoPlay() {
  CAROUSEL_CONFIG.autoPlayInterval = setInterval(() => {
    carouselNext();
  }, CAROUSEL_CONFIG.autoPlayDelay);
}

function stopCarouselAutoPlay() {
  if (CAROUSEL_CONFIG.autoPlayInterval) {
    clearInterval(CAROUSEL_CONFIG.autoPlayInterval);
    CAROUSEL_CONFIG.autoPlayInterval = null;
  }
}

/* ============================================
   2. ACCORDION / COLLAPSIBLE FAQ
   ============================================ */
function toggleAccordion(button) {
  const isExpanded = button.getAttribute('aria-expanded') === 'true';
  const contentId = button.getAttribute('aria-controls');
  const content = document.getElementById(contentId);

  // Close all other accordion items
  document.querySelectorAll('.lp-accordion-trigger').forEach((trigger) => {
    if (trigger !== button) {
      trigger.setAttribute('aria-expanded', 'false');
      const otherContentId = trigger.getAttribute('aria-controls');
      const otherContent = document.getElementById(otherContentId);
      if (otherContent) {
        otherContent.style.display = 'none';
      }
    }
  });

  // Toggle current accordion item
  if (isExpanded) {
    button.setAttribute('aria-expanded', 'false');
    if (content) content.style.display = 'none';
  } else {
    button.setAttribute('aria-expanded', 'true');
    if (content) content.style.display = 'block';
  }
}

/* ============================================
   3. MODAL / DIALOG FUNCTIONALITY
   ============================================ */
function openAuthModal(mode = 'signup') {
  const modal = document.getElementById('auth-modal');
  const signupForm = document.getElementById('modal-signup');
  const signinForm = document.getElementById('modal-signin');

  // Show appropriate form
  if (mode === 'signup' || mode === 'register') {
    signupForm.classList.add('active');
    signinForm.classList.remove('active');
  } else if (mode === 'signin' || mode === 'login') {
    signinForm.classList.add('active');
    signupForm.classList.remove('active');
  }

  modal.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeAuthModal() {
  const modal = document.getElementById('auth-modal');
  modal.classList.remove('open');
  document.body.style.overflow = '';

  // Reset forms
  document.getElementById('signup-form').reset();
  document.getElementById('signin-form').reset();
  clearErrors();
}

function switchAuthMode(mode) {
  const signupForm = document.getElementById('modal-signup');
  const signinForm = document.getElementById('modal-signin');

  if (mode === 'signup' || mode === 'register') {
    signupForm.classList.add('active');
    signinForm.classList.remove('active');
  } else if (mode === 'login' || mode === 'signin') {
    signinForm.classList.add('active');
    signupForm.classList.remove('active');
  }

  clearErrors();
}

function clearErrors() {
  const signupError = document.getElementById('signup-error');
  const signinError = document.getElementById('signin-error');
  if (signupError) signupError.style.display = 'none';
  if (signinError) signinError.style.display = 'none';
}

/* ============================================
   4. FORM VALIDATION & SUBMISSION
   ============================================ */
const VALIDATION = {
  emailRegex: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
  passwordMinLength: 8,
};

function validateEmail(email) {
  return VALIDATION.emailRegex.test(email);
}

function validatePassword(password) {
  return password && password.length >= VALIDATION.passwordMinLength;
}

function setError(elementId, message) {
  const errorEl = document.getElementById(elementId);
  if (errorEl) {
    errorEl.textContent = message;
    errorEl.style.display = 'block';
  }
}

function clearError(elementId) {
  const errorEl = document.getElementById(elementId);
  if (errorEl) {
    errorEl.textContent = '';
    errorEl.style.display = 'none';
  }
}

async function handleSignup(event) {
  event.preventDefault();
  clearError('signup-error');

  const email = document.getElementById('signup-email').value.trim();
  const password = document.getElementById('signup-password').value;
  const confirm = document.getElementById('signup-confirm').value;
  const button = document.getElementById('signup-btn');

  // Validation
  if (!email) {
    setError('signup-error', 'Email is required.');
    return;
  }
  if (!validateEmail(email)) {
    setError('signup-error', 'Please enter a valid email address.');
    return;
  }
  if (!password) {
    setError('signup-error', 'Password is required.');
    return;
  }
  if (!validatePassword(password)) {
    setError('signup-error', `Password must be at least ${VALIDATION.passwordMinLength} characters.`);
    return;
  }
  if (password !== confirm) {
    setError('signup-error', 'Passwords do not match.');
    return;
  }

  // Submit
  button.disabled = true;
  button.textContent = 'Creating account...';

  try {
    const response = await fetch('/api/v1/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, password }),
    });

    const data = await response.json();

    if (!response.ok) {
      setError('signup-error', data.detail || 'Sign-up failed. Please try again.');
      return;
    }

    // Success - save token and redirect to onboarding
    if (data.access_token) {
      sessionStorage.setItem('EtseeMate_token', data.access_token);
    }

    // Show success message
    showSuccessMessage('Account created successfully! Redirecting to setup...');
    setTimeout(() => {
      // Redirect to onboarding wizard
      window.location.href = '/app.html?onboarding=true';
    }, 2000);
  } catch (error) {
    console.error('Sign-up error:', error);
    setError('signup-error', 'Connection error. Please try again.');
  } finally {
    button.disabled = false;
    button.textContent = 'Create account';
  }
}

async function handleSignin(event) {
  event.preventDefault();
  clearError('signin-error');

  const email = document.getElementById('signin-email').value.trim();
  const password = document.getElementById('signin-password').value;
  const button = document.getElementById('signin-btn');

  // Validation
  if (!email) {
    setError('signin-error', 'Email is required.');
    return;
  }
  if (!validateEmail(email)) {
    setError('signin-error', 'Please enter a valid email address.');
    return;
  }
  if (!password) {
    setError('signin-error', 'Password is required.');
    return;
  }

  // Submit
  button.disabled = true;
  button.textContent = 'Signing in...';

  try {
    const response = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, password }),
    });

    const data = await response.json();

    if (!response.ok) {
      setError('signin-error', data.detail || 'Sign-in failed. Please check your credentials.');
      return;
    }

    // Success - save token and redirect
    if (data.access_token) {
      sessionStorage.setItem('EtseeMate_token', data.access_token);
    }

    // Show success message
    showSuccessMessage('Welcome! Redirecting to dashboard...');
    setTimeout(() => {
      window.location.href = '/app';
    }, 2000);
  } catch (error) {
    console.error('Sign-in error:', error);
    setError('signin-error', 'Connection error. Please try again.');
  } finally {
    button.disabled = false;
    button.textContent = 'Sign in';
  }
}

function showSuccessMessage(message) {
  const modal = document.getElementById('auth-modal');
  const content = modal.querySelector('.lp-modal-content');
  const currentForm = content.querySelector('.lp-modal-form:not([style*="display: none"])');

  if (currentForm) {
    const originalContent = currentForm.innerHTML;
    currentForm.innerHTML = `
      <div style="text-align: center; padding: 20px 0;">
        <div style="font-size: 3rem; margin-bottom: 16px;">✓</div>
        <h2 style="font-family: Georgia, serif; font-size: 1.5rem; color: #141413; margin-bottom: 8px;">Success!</h2>
        <p style="color: #5e5d59; margin-bottom: 16px;">${message}</p>
      </div>
    `;
  }
}

/* ============================================
   5. MODAL CLOSE ON BACKDROP CLICK
   ============================================ */
document.addEventListener('DOMContentLoaded', () => {
  const modal = document.getElementById('auth-modal');

  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        closeAuthModal();
      }
    });
  }

  // Close on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      const modal = document.getElementById('auth-modal');
      if (modal && modal.classList.contains('open')) {
        closeAuthModal();
      }
    }
  });

  // Initialize carousel
  carouselInit();

  // Check if already authenticated
  if (sessionStorage.getItem('EtseeMate_token')) {
    window.location.href = '/app';
  }

  // Add Enter key support to sign-in form
  const signinForm = document.getElementById('signin-form');
  if (signinForm) {
    signinForm.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.target.classList.contains('lp-form-switch-link')) {
        handleSignin(e);
      }
    });
  }

  // Add Enter key support to sign-up form
  const signupForm = document.getElementById('signup-form');
  if (signupForm) {
    signupForm.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.target.classList.contains('lp-form-switch-link')) {
        handleSignup(e);
      }
    });
  }
});

/* ============================================
   6. SMOOTH SCROLL FOR ANCHOR LINKS
   ============================================ */
document.addEventListener('click', (e) => {
  const link = e.target.closest('a[href^="#"]');
  if (link) {
    const href = link.getAttribute('href');
    if (href !== '#') {
      const target = document.querySelector(href);
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }
  }
});
