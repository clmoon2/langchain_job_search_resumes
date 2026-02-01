/**
 * UI Overlay
 * 
 * Creates floating UI elements on the job application page:
 * - Autofill button
 * - Progress indicator
 * - Status messages
 */

class UIOverlay {
  constructor() {
    this.container = null;
    this.button = null;
    this.progress = null;
    this.onAutofill = null;
    
    this.createContainer();
  }

  /**
   * Create the overlay container
   */
  createContainer() {
    // Check if container already exists
    this.container = document.getElementById('tailored-resume-overlay');
    if (this.container) {
      return;
    }

    this.container = document.createElement('div');
    this.container.id = 'tailored-resume-overlay';
    this.container.innerHTML = `
      <div class="tr-overlay-content">
        <div class="tr-button-container">
          <button class="tr-autofill-btn" id="tr-autofill-btn">
            <span class="tr-btn-text">Autofill</span>
          </button>
        </div>
        <div class="tr-progress" id="tr-progress" style="display: none;">
          <span class="tr-progress-text"></span>
        </div>
        <div class="tr-message" id="tr-message" style="display: none;">
          <span class="tr-message-text"></span>
        </div>
      </div>
    `;

    document.body.appendChild(this.container);

    this.button = document.getElementById('tr-autofill-btn');
    this.progress = document.getElementById('tr-progress');
    this.message = document.getElementById('tr-message');

    // Add click handler
    this.button.addEventListener('click', () => {
      if (this.onAutofill) {
        this.onAutofill();
      }
    });
  }

  /**
   * Show the autofill button
   */
  showAutofillButton(callback) {
    this.onAutofill = callback;
    this.container.classList.add('tr-visible');
    this.button.style.display = 'flex';
    this.progress.style.display = 'none';
    this.message.style.display = 'none';
  }

  /**
   * Hide the autofill button
   */
  hideAutofillButton() {
    this.button.style.display = 'none';
  }

  /**
   * Show progress indicator
   */
  showProgress(text) {
    this.button.style.display = 'none';
    this.progress.style.display = 'flex';
    this.progress.querySelector('.tr-progress-text').textContent = text;
    this.message.style.display = 'none';
  }

  /**
   * Show success message
   */
  showSuccess(text) {
    this.button.style.display = 'none';
    this.progress.style.display = 'none';
    this.message.style.display = 'flex';
    this.message.className = 'tr-message tr-message--success';
    this.message.querySelector('.tr-message-text').textContent = text;

    // Hide after delay
    setTimeout(() => {
      this.hideMessage();
    }, 5000);
  }

  /**
   * Show error message
   */
  showError(text) {
    this.button.style.display = 'flex';
    this.progress.style.display = 'none';
    this.message.style.display = 'flex';
    this.message.className = 'tr-message tr-message--error';
    this.message.querySelector('.tr-message-text').textContent = text;

    // Hide after delay
    setTimeout(() => {
      this.hideMessage();
    }, 5000);
  }

  /**
   * Hide message
   */
  hideMessage() {
    this.message.style.display = 'none';
  }

  /**
   * Show auth prompt
   */
  showAuthPrompt(callback) {
    this.container.classList.add('tr-visible');
    this.button.innerHTML = '<span class="tr-btn-text">Sign In to Autofill</span>';
    this.button.style.display = 'flex';
    this.onAutofill = callback;
  }

  /**
   * Show no resume message
   */
  showNoResumeMessage() {
    this.container.classList.add('tr-visible');
    this.button.style.display = 'none';
    this.message.style.display = 'flex';
    this.message.className = 'tr-message tr-message--info';
    this.message.querySelector('.tr-message-text').textContent = 
      'Click extension icon to upload your resume';
  }

  /**
   * Destroy the overlay
   */
  destroy() {
    if (this.container && this.container.parentNode) {
      this.container.parentNode.removeChild(this.container);
    }
    this.container = null;
    this.button = null;
    this.progress = null;
    this.message = null;
  }
}

// Make available globally
if (typeof window !== 'undefined') {
  window.UIOverlay = UIOverlay;
}
