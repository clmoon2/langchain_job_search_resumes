/**
 * Authentication Module
 * 
 * Handles all authentication-related operations:
 * - Initiating sign in/sign up flows
 * - Processing auth callbacks
 * - Token management (storage, refresh, validation)
 * - User session management
 */

import { AUTH_CONFIG, API_ENDPOINTS } from '../config/constants.js';

class AuthManager {
  constructor() {
    this.token = null;
    this.user = null;
    this.tokenExpiry = null;
  }

  /**
   * Initialize auth state from storage
   */
  async init() {
    console.log('[INFO] Initializing auth manager');
    
    const data = await chrome.storage.local.get([
      AUTH_CONFIG.TOKEN_STORAGE_KEY,
      AUTH_CONFIG.USER_STORAGE_KEY,
      AUTH_CONFIG.TOKEN_EXPIRY_KEY
    ]);

    this.token = data[AUTH_CONFIG.TOKEN_STORAGE_KEY] || null;
    this.user = data[AUTH_CONFIG.USER_STORAGE_KEY] || null;
    this.tokenExpiry = data[AUTH_CONFIG.TOKEN_EXPIRY_KEY] || null;

    if (this.token && this.isTokenExpired()) {
      console.log('[WARN] Token expired, attempting refresh');
      try {
        await this.refreshToken();
      } catch (error) {
        console.log('[ERROR] Token refresh failed:', error.message);
        await this.logout();
      }
    }

    if (this.token) {
      try {
        await this.fetchCurrentUser();
        console.log('[OK] Auth initialized, user:', this.user?.email);
      } catch (error) {
        console.log('[ERROR] Failed to fetch user:', error.message);
        await this.logout();
      }
    }

    return this.isAuthenticated();
  }

  /**
   * Check if user is authenticated
   */
  isAuthenticated() {
    return !!this.token && !!this.user && !this.isTokenExpired();
  }

  /**
   * Check if token is expired
   */
  isTokenExpired() {
    if (!this.tokenExpiry) return false;
    return Date.now() > this.tokenExpiry;
  }

  /**
   * Open sign-in page in new tab
   */
  async openSignIn() {
    const state = this.generateState();
    await chrome.storage.local.set({ authState: state });

    const callbackUrl = chrome.runtime.getURL(AUTH_CONFIG.CALLBACK_PATH);
    
    const authUrl = new URL(AUTH_CONFIG.SIGNIN_URL);
    authUrl.searchParams.set('redirect_uri', callbackUrl);
    authUrl.searchParams.set('client_id', AUTH_CONFIG.CLIENT_ID);
    authUrl.searchParams.set('response_type', 'token');
    authUrl.searchParams.set('state', state);

    console.log('[INFO] Opening sign-in page');
    return chrome.tabs.create({ url: authUrl.toString() });
  }

  /**
   * Open sign-up page in new tab
   */
  async openSignUp() {
    const state = this.generateState();
    await chrome.storage.local.set({ authState: state });

    const callbackUrl = chrome.runtime.getURL(AUTH_CONFIG.CALLBACK_PATH);
    
    const authUrl = new URL(AUTH_CONFIG.SIGNUP_URL);
    authUrl.searchParams.set('redirect_uri', callbackUrl);
    authUrl.searchParams.set('client_id', AUTH_CONFIG.CLIENT_ID);
    authUrl.searchParams.set('response_type', 'token');
    authUrl.searchParams.set('state', state);

    console.log('[INFO] Opening sign-up page');
    return chrome.tabs.create({ url: authUrl.toString() });
  }

  /**
   * Use chrome.identity.launchWebAuthFlow for OAuth
   */
  async launchAuthFlow(authUrl) {
    return new Promise((resolve, reject) => {
      chrome.identity.launchWebAuthFlow(
        {
          url: authUrl,
          interactive: true
        },
        (redirectUrl) => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
            return;
          }

          const url = new URL(redirectUrl);
          const token = url.hash.match(/access_token=([^&]*)/)?.[1] ||
                        url.searchParams.get('token');

          if (token) {
            this.handleAuthCallback(token);
            resolve(token);
          } else {
            reject(new Error('No token received'));
          }
        }
      );
    });
  }

  /**
   * Handle authentication callback
   */
  async handleAuthCallback(token, state = null) {
    console.log('[INFO] Processing auth callback');

    if (state) {
      const storedState = await chrome.storage.local.get('authState');
      if (storedState.authState !== state) {
        throw new Error('Invalid state parameter');
      }
      await chrome.storage.local.remove('authState');
    }

    this.token = token;
    
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      this.tokenExpiry = payload.exp ? payload.exp * 1000 : Date.now() + (24 * 60 * 60 * 1000);
    } catch {
      this.tokenExpiry = Date.now() + (24 * 60 * 60 * 1000);
    }

    await this.fetchCurrentUser();

    await chrome.storage.local.set({
      [AUTH_CONFIG.TOKEN_STORAGE_KEY]: this.token,
      [AUTH_CONFIG.USER_STORAGE_KEY]: this.user,
      [AUTH_CONFIG.TOKEN_EXPIRY_KEY]: this.tokenExpiry
    });

    chrome.runtime.sendMessage({ type: 'AUTH_STATE_CHANGED', isAuthenticated: true });
    console.log('[OK] Auth callback processed successfully');

    return this.user;
  }

  /**
   * Fetch current user from API
   */
  async fetchCurrentUser() {
    const response = await fetch(`${AUTH_CONFIG.API_BASE}${API_ENDPOINTS.ME}`, {
      headers: {
        'Authorization': `Bearer ${this.token}`
      }
    });

    if (!response.ok) {
      throw new Error('Failed to fetch user');
    }

    this.user = await response.json();
    return this.user;
  }

  /**
   * Refresh the authentication token
   */
  async refreshToken() {
    console.log('[INFO] Refreshing token');
    
    try {
      const response = await fetch(`${AUTH_CONFIG.API_BASE}${API_ENDPOINTS.REFRESH}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.token}`
        }
      });

      if (!response.ok) {
        throw new Error('Token refresh failed');
      }

      const data = await response.json();
      await this.handleAuthCallback(data.token);
      console.log('[OK] Token refreshed');
    } catch (error) {
      console.log('[ERROR] Token refresh failed:', error.message);
      await this.logout();
      throw error;
    }
  }

  /**
   * Log out user
   */
  async logout() {
    console.log('[INFO] Logging out');

    if (this.token) {
      try {
        await fetch(`${AUTH_CONFIG.API_BASE}${API_ENDPOINTS.LOGOUT}`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${this.token}`
          }
        });
      } catch {
        // Ignore logout endpoint errors
      }
    }

    this.token = null;
    this.user = null;
    this.tokenExpiry = null;

    await chrome.storage.local.remove([
      AUTH_CONFIG.TOKEN_STORAGE_KEY,
      AUTH_CONFIG.USER_STORAGE_KEY,
      AUTH_CONFIG.TOKEN_EXPIRY_KEY
    ]);

    chrome.runtime.sendMessage({ type: 'AUTH_STATE_CHANGED', isAuthenticated: false });
    console.log('[OK] Logged out');
  }

  /**
   * Generate random state for CSRF protection
   */
  generateState() {
    const array = new Uint8Array(32);
    crypto.getRandomValues(array);
    return Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('');
  }

  /**
   * Get authorization header for API calls
   */
  getAuthHeader() {
    return this.token ? { 'Authorization': `Bearer ${this.token}` } : {};
  }

  /**
   * Get current auth state for popup
   */
  getAuthState() {
    return {
      isAuthenticated: this.isAuthenticated(),
      user: this.user,
      tokenExpiry: this.tokenExpiry
    };
  }
}

export const authManager = new AuthManager();
