/**
 * Auth Status Component
 * 
 * Displays authentication state and sign in/out buttons.
 */

class AuthStatus {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.isAuthenticated = false;
    this.user = null;
  }

  async init() {
    // Get current auth state from background
    const response = await chrome.runtime.sendMessage({ type: 'GET_AUTH_STATE' });
    this.isAuthenticated = response.isAuthenticated;
    this.user = response.user;
    this.render();

    // Listen for auth state changes
    chrome.runtime.onMessage.addListener((message) => {
      if (message.type === 'AUTH_STATE_CHANGED') {
        this.isAuthenticated = message.isAuthenticated;
        if (message.user) {
          this.user = message.user;
        } else if (!message.isAuthenticated) {
          this.user = null;
        }
        this.render();
      }
    });
  }

  render() {
    if (this.isAuthenticated && this.user) {
      this.renderAuthenticated();
    } else {
      this.renderUnauthenticated();
    }
  }

  renderAuthenticated() {
    const initials = this.getInitials();
    const avatarContent = this.user.avatar 
      ? `<img src="${this.user.avatar}" alt="Avatar">` 
      : `<span>${initials}</span>`;

    this.container.innerHTML = `
      <div class="auth-status auth-status--authenticated">
        <div class="user-info">
          <div class="user-avatar">
            ${avatarContent}
          </div>
          <div class="user-details">
            <span class="user-name">${this.user.name || this.user.email}</span>
            <span class="user-email">${this.user.email}</span>
          </div>
        </div>
        <button id="logout-btn" class="btn btn--secondary btn--small">
          Sign Out
        </button>
      </div>
    `;

    document.getElementById('logout-btn').addEventListener('click', () => {
      this.handleLogout();
    });
  }

  renderUnauthenticated() {
    this.container.innerHTML = `
      <div class="auth-status auth-status--unauthenticated">
        <p class="auth-prompt">Sign in to sync your profile across devices</p>
        <div class="auth-buttons">
          <button id="signin-btn" class="btn btn--primary">
            Sign In
          </button>
          <button id="signup-btn" class="btn btn--secondary">
            Sign Up
          </button>
        </div>
      </div>
    `;

    document.getElementById('signin-btn').addEventListener('click', () => {
      this.handleSignIn();
    });

    document.getElementById('signup-btn').addEventListener('click', () => {
      this.handleSignUp();
    });
  }

  async handleSignIn() {
    console.log('[INFO] Sign in clicked');
    await chrome.runtime.sendMessage({ type: 'OPEN_SIGNIN' });
  }

  async handleSignUp() {
    console.log('[INFO] Sign up clicked');
    await chrome.runtime.sendMessage({ type: 'OPEN_SIGNUP' });
  }

  async handleLogout() {
    console.log('[INFO] Logout clicked');
    await chrome.runtime.sendMessage({ type: 'LOGOUT' });
  }

  getInitials() {
    if (!this.user) return '?';
    const name = this.user.name || this.user.email || '';
    return name.split(' ')
      .map(part => part[0])
      .join('')
      .toUpperCase()
      .substring(0, 2);
  }
}
