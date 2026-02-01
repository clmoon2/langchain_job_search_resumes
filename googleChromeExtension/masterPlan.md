# Tailored Resume Autofill Chrome Extension - Master Implementation Plan

> **Project Codename**: TailoredResume
> **Version**: 1.0.0
> **Last Updated**: January 2026

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture Overview](#2-architecture-overview)
3. [File Structure](#3-file-structure)
4. [Authentication Pipeline](#4-authentication-pipeline)
5. [Detailed Component Specifications](#5-detailed-component-specifications)
6. [ATS Configuration Files](#6-ats-configuration-files)
7. [Data Schema](#7-data-schema)
8. [Implementation Phases](#8-implementation-phases)
9. [Testing Strategy](#9-testing-strategy)
10. [Known Challenges & Solutions](#10-known-challenges--solutions)
11. [Resources & References](#11-resources--references)

---

## 1. Project Overview

### 1.1 Goal

Build a Chrome extension that allows users to:

1. **Authenticate** with your service (sign up / sign in)
2. **Drag and drop** their resume (PDF) into the extension
3. **Sync profile data** with your backend service
4. When visiting a job application page, **extract the job description**
5. Use **local processing** to tailor the resume data for that specific job
6. **Autofill** the job application form with the tailored information
7. **Upload** the tailored resume file

### 1.2 Target ATS Platforms (Phase 1)

| Platform | URL Patterns | Complexity |
|----------|--------------|------------|
| **Greenhouse** | `boards.greenhouse.io`, `boards.eu.greenhouse.io` | Medium |
| **Lever** | `jobs.lever.co` | Easy |
| **Workday** | `*.myworkdayjobs.com`, `*.myworkdaysite.com` | Hard |

### 1.3 Key Differentiator from Simplify

- **Your own service** - Users authenticate with YOUR backend
- **Local processing** - Resume tailoring happens entirely in the browser
- **Per-job customization** - Each autofill is tailored to the specific job description
- **User owns the data** - Profile syncs with your service, not a third party

---

## 2. Architecture Overview

### 2.1 High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CHROME EXTENSION                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────┐         ┌─────────────────────────┐               │
│  │       POPUP UI       │         │    SERVICE WORKER       │               │
│  │    (popup/*.*)       │         │   (background/*.js)     │               │
│  │                      │         │                         │               │
│  │  - Auth status       │────────▶│  - Message routing      │               │
│  │  - Sign in/up links  │         │  - Auth token mgmt      │               │
│  │  - Drag & drop zone  │         │  - Storage management   │               │
│  │  - Resume preview    │         │  - API communication    │               │
│  │  - Profile sync      │         │  - Tab communication    │               │
│  └──────────────────────┘         └───────────┬─────────────┘               │
│           │                                   │                              │
│           │                                   │                              │
│           ▼                                   ▼                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         CHROME.STORAGE.LOCAL                          │   │
│  │                                                                       │   │
│  │  {                                                                    │   │
│  │    authToken: "jwt...",      // Authentication token                  │   │
│  │    user: { id, email },      // User info from your service           │   │
│  │    baseResume: { ... },      // Parsed resume data                    │   │
│  │    resumeFile: Blob,         // Original PDF for upload               │   │
│  │    userProfile: { ... },     // Contact info, preferences             │   │
│  │    settings: { ... }         // Extension settings                    │   │
│  │  }                                                                    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│           │                                                                  │
│           │ chrome.storage.local.get()                                       │
│           ▼                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                        CONTENT SCRIPT                                 │   │
│  │                      (content/*.js)                                   │   │
│  │                                                                       │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │ ATS         │  │ Job Desc    │  │ Resume      │  │ Form        │  │   │
│  │  │ Detector    │  │ Extractor   │  │ Tailor      │  │ Filler      │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       │ HTTPS API Calls
                                       ▼
                        ┌──────────────────────────────┐
                        │     YOUR BACKEND SERVICE     │
                        │                              │
                        │  - User authentication       │
                        │  - Profile storage           │
                        │  - Resume storage            │
                        │  - Analytics (optional)      │
                        │                              │
                        │  Endpoints:                  │
                        │  POST /auth/signup           │
                        │  POST /auth/signin           │
                        │  GET  /auth/me               │
                        │  POST /profile               │
                        │  GET  /profile               │
                        │  POST /resume                │
                        └──────────────────────────────┘
```

### 2.2 Data Flow

```
1. USER AUTHENTICATES
   ┌─────────┐     ┌─────────────┐     ┌──────────────┐     ┌─────────────┐
   │  User   │────▶│ Click       │────▶│ Opens auth   │────▶│ Receives    │
   │ clicks  │     │ Sign In/Up  │     │ URL in new   │     │ token via   │
   │ button  │     │ in popup    │     │ tab          │     │ callback    │
   └─────────┘     └─────────────┘     └──────────────┘     └─────────────┘

2. USER UPLOADS RESUME
   ┌─────────┐     ┌─────────────┐     ┌──────────────┐     ┌─────────────┐
   │  User   │────▶│ Popup UI    │────▶│ PDF Parser   │────▶│ Storage +   │
   │ drops   │     │ receives    │     │ extracts     │     │ Sync to     │
   │ PDF     │     │ file        │     │ text/data    │     │ backend     │
   └─────────┘     └─────────────┘     └──────────────┘     └─────────────┘

3. USER VISITS JOB PAGE
   ┌─────────┐     ┌─────────────┐     ┌──────────────┐     ┌─────────────┐
   │ Content │────▶│ ATS         │────▶│ Job Desc     │────▶│ Show        │
   │ Script  │     │ Detector    │     │ Extractor    │     │ Autofill    │
   │ loads   │     │ matches URL │     │ scrapes page │     │ Button      │
   └─────────┘     └─────────────┘     └──────────────┘     └─────────────┘

4. USER CLICKS AUTOFILL
   ┌─────────┐     ┌─────────────┐     ┌──────────────┐     ┌─────────────┐
   │ Get     │────▶│ Resume      │────▶│ Form         │────▶│ Upload      │
   │ resume  │     │ Tailor      │     │ Filler       │     │ Resume      │
   │ from    │     │ customizes  │     │ fills        │     │ File        │
   │ storage │     │ for job     │     │ fields       │     │             │
   └─────────┘     └─────────────┘     └──────────────┘     └─────────────┘
```

---

## 3. File Structure

```
tailored-resume-extension/
│
├── manifest.json                    # Extension configuration
│
├── popup/                           # Popup UI (when clicking extension icon)
│   ├── index.html                   # Main popup HTML
│   ├── popup.js                     # Popup logic
│   ├── popup.css                    # Popup styles
│   └── components/                  # UI components
│       ├── auth-status.js           # Auth state display & buttons
│       ├── drop-zone.js             # Drag & drop component
│       ├── resume-preview.js        # Resume data preview
│       └── status-indicator.js      # Connection/status display
│
├── background/                      # Service worker (background script)
│   ├── service-worker.js            # Main entry point
│   ├── auth.js                      # Authentication handlers
│   └── api.js                       # Backend API communication
│
├── content/                         # Content scripts (injected into pages)
│   ├── content-script.js            # Main entry point
│   ├── ats-detector.js              # Detect which ATS platform
│   ├── job-extractor.js             # Extract job description
│   ├── resume-tailor.js             # YOUR TAILORING LOGIC
│   ├── form-filler.js               # Fill form fields
│   ├── file-uploader.js             # Handle resume file upload
│   └── ui-overlay.js                # Floating autofill button
│
├── auth/                            # Authentication pages
│   ├── callback.html                # OAuth callback handler
│   └── callback.js                  # Process auth callback
│
├── lib/                             # Shared libraries
│   ├── pdf-parser.js                # PDF.js wrapper for parsing resumes
│   ├── storage.js                   # Chrome storage utilities
│   ├── messaging.js                 # Message passing utilities
│   ├── api-client.js                # HTTP client for your backend
│   └── xpath-utils.js               # XPath evaluation helpers
│
├── config/                          # Configuration files
│   ├── ats-selectors.js             # ATS-specific field mappings
│   ├── field-mappings.js            # Resume field to form field mappings
│   └── constants.js                 # URLs, keys, etc.
│
├── assets/                          # Static assets
│   ├── icons/                       # Extension icons (16, 32, 48, 128px)
│   ├── fonts/                       # Optional custom fonts
│   └── images/                      # UI images
│
└── vendor/                          # Third-party libraries
    └── pdf.js/                      # PDF.js library files
        ├── pdf.min.js
        └── pdf.worker.min.js
```

---

## 4. Authentication Pipeline

### 4.1 Overview

The authentication pipeline allows users to sign in or sign up through your backend service. This enables:

- **Profile persistence** across devices
- **Resume storage** in your backend
- **Premium features** (if applicable)
- **Analytics and tracking** of job applications

### 4.2 Authentication Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AUTHENTICATION FLOW                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┐                                                                │
│  │ User     │                                                                │
│  │ clicks   │                                                                │
│  │ Sign In  │                                                                │
│  └────┬─────┘                                                                │
│       │                                                                      │
│       ▼                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ POPUP: Generates auth URL with extension ID for callback             │   │
│  │                                                                       │   │
│  │ const authUrl = `${AUTH_BASE_URL}/signin?                            │   │
│  │   client_id=${CLIENT_ID}&                                            │   │
│  │   redirect_uri=${chrome.identity.getRedirectURL()}&                  │   │
│  │   response_type=token&                                               │   │
│  │   state=${generateState()}`;                                         │   │
│  └────┬─────────────────────────────────────────────────────────────────┘   │
│       │                                                                      │
│       ▼                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ OPTION A: chrome.identity.launchWebAuthFlow (Recommended)            │   │
│  │ - Opens auth page in special Chrome window                            │   │
│  │ - Automatically handles callback                                      │   │
│  │ - More secure, no new tab needed                                      │   │
│  │                                                                       │   │
│  │ OPTION B: chrome.tabs.create                                          │   │
│  │ - Opens auth page in new tab                                          │   │
│  │ - User completes auth on your website                                 │   │
│  │ - Website redirects to extension callback page                        │   │
│  └────┬─────────────────────────────────────────────────────────────────┘   │
│       │                                                                      │
│       ▼                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ YOUR AUTH SERVER (https://your-service.com/auth)                      │   │
│  │                                                                       │   │
│  │ 1. User enters credentials / signs up                                 │   │
│  │ 2. Server validates credentials                                       │   │
│  │ 3. Server generates JWT token                                         │   │
│  │ 4. Server redirects to callback URL with token                        │   │
│  │                                                                       │   │
│  │ Redirect: chrome-extension://{EXT_ID}/auth/callback.html#token=xxx   │   │
│  └────┬─────────────────────────────────────────────────────────────────┘   │
│       │                                                                      │
│       ▼                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ CALLBACK HANDLER (auth/callback.html)                                 │   │
│  │                                                                       │   │
│  │ 1. Extracts token from URL hash/params                                │   │
│  │ 2. Validates token (optional)                                         │   │
│  │ 3. Sends token to service worker                                      │   │
│  │ 4. Service worker stores token in chrome.storage                      │   │
│  │ 5. Closes callback tab / shows success                                │   │
│  └────┬─────────────────────────────────────────────────────────────────┘   │
│       │                                                                      │
│       ▼                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ AUTHENTICATED STATE                                                   │   │
│  │                                                                       │   │
│  │ - Token stored in chrome.storage.local                                │   │
│  │ - User info fetched from /auth/me                                     │   │
│  │ - Profile synced with backend                                         │   │
│  │ - Popup shows user info + logout button                               │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Configuration Constants

```javascript
// config/constants.js

export const AUTH_CONFIG = {
  // Your backend service URLs
  BASE_URL: 'https://your-service.com',
  
  // Authentication endpoints
  SIGNIN_URL: 'https://your-service.com/auth/signin',
  SIGNUP_URL: 'https://your-service.com/auth/signup',
  CALLBACK_PATH: '/auth/callback.html',
  
  // API endpoints
  API_BASE: 'https://your-service.com/api/v1',
  
  // OAuth settings (if using OAuth)
  CLIENT_ID: 'your-chrome-extension-client-id',
  
  // Token settings
  TOKEN_STORAGE_KEY: 'authToken',
  USER_STORAGE_KEY: 'currentUser',
  TOKEN_EXPIRY_KEY: 'tokenExpiry',
};

export const API_ENDPOINTS = {
  // Auth
  ME: '/auth/me',
  REFRESH: '/auth/refresh',
  LOGOUT: '/auth/logout',
  
  // Profile
  GET_PROFILE: '/profile',
  UPDATE_PROFILE: '/profile',
  
  // Resume
  UPLOAD_RESUME: '/resume',
  GET_RESUME: '/resume',
  
  // Job tracking (optional)
  TRACK_APPLICATION: '/applications',
  GET_APPLICATIONS: '/applications',
};
```

### 4.4 Authentication Module Implementation

#### 4.4.1 background/auth.js

```javascript
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
    const data = await chrome.storage.local.get([
      AUTH_CONFIG.TOKEN_STORAGE_KEY,
      AUTH_CONFIG.USER_STORAGE_KEY,
      AUTH_CONFIG.TOKEN_EXPIRY_KEY
    ]);

    this.token = data[AUTH_CONFIG.TOKEN_STORAGE_KEY] || null;
    this.user = data[AUTH_CONFIG.USER_STORAGE_KEY] || null;
    this.tokenExpiry = data[AUTH_CONFIG.TOKEN_EXPIRY_KEY] || null;

    // Check if token is expired
    if (this.token && this.isTokenExpired()) {
      await this.refreshToken();
    }

    // Validate token with server
    if (this.token) {
      try {
        await this.fetchCurrentUser();
      } catch (error) {
        // Token invalid, clear auth state
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
   * User completes authentication on your website
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

    // Option A: Use chrome.identity (recommended for OAuth)
    // return this.launchAuthFlow(authUrl.toString());

    // Option B: Open in new tab (simpler, works for custom auth)
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

    return chrome.tabs.create({ url: authUrl.toString() });
  }

  /**
   * Use chrome.identity.launchWebAuthFlow for OAuth
   * More secure but requires proper OAuth setup
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

          // Extract token from redirect URL
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
   * Called when user is redirected back from auth page
   */
  async handleAuthCallback(token, state = null) {
    // Validate state if provided
    if (state) {
      const storedState = await chrome.storage.local.get('authState');
      if (storedState.authState !== state) {
        throw new Error('Invalid state parameter');
      }
      await chrome.storage.local.remove('authState');
    }

    // Store token
    this.token = token;
    
    // Calculate expiry (assuming JWT with exp claim)
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      this.tokenExpiry = payload.exp ? payload.exp * 1000 : Date.now() + (24 * 60 * 60 * 1000);
    } catch {
      // Default to 24 hours if can't parse
      this.tokenExpiry = Date.now() + (24 * 60 * 60 * 1000);
    }

    // Fetch user info
    await this.fetchCurrentUser();

    // Save to storage
    await chrome.storage.local.set({
      [AUTH_CONFIG.TOKEN_STORAGE_KEY]: this.token,
      [AUTH_CONFIG.USER_STORAGE_KEY]: this.user,
      [AUTH_CONFIG.TOKEN_EXPIRY_KEY]: this.tokenExpiry
    });

    // Notify popup that auth state changed
    chrome.runtime.sendMessage({ type: 'AUTH_STATE_CHANGED', isAuthenticated: true });

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
    } catch (error) {
      // Refresh failed, log out
      await this.logout();
      throw error;
    }
  }

  /**
   * Log out user
   */
  async logout() {
    // Call logout endpoint (optional)
    if (this.token) {
      try {
        await fetch(`${AUTH_CONFIG.API_BASE}${API_ENDPOINTS.LOGOUT}`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${this.token}`
          }
        });
      } catch {
        // Ignore logout errors
      }
    }

    // Clear local state
    this.token = null;
    this.user = null;
    this.tokenExpiry = null;

    // Clear storage
    await chrome.storage.local.remove([
      AUTH_CONFIG.TOKEN_STORAGE_KEY,
      AUTH_CONFIG.USER_STORAGE_KEY,
      AUTH_CONFIG.TOKEN_EXPIRY_KEY
    ]);

    // Notify popup
    chrome.runtime.sendMessage({ type: 'AUTH_STATE_CHANGED', isAuthenticated: false });
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

// Export singleton instance
export const authManager = new AuthManager();
```

#### 4.4.2 auth/callback.html

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Authentication - Tailored Resume</title>
  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }
    
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    
    .container {
      background: white;
      padding: 40px;
      border-radius: 16px;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
      text-align: center;
      max-width: 400px;
    }
    
    .spinner {
      width: 50px;
      height: 50px;
      border: 4px solid #f3f3f3;
      border-top: 4px solid #667eea;
      border-radius: 50%;
      animation: spin 1s linear infinite;
      margin: 0 auto 20px;
    }
    
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
    
    h1 {
      color: #333;
      margin-bottom: 10px;
      font-size: 24px;
    }
    
    p {
      color: #666;
      margin-bottom: 20px;
    }
    
    .success {
      color: #4CAF50;
    }
    
    .error {
      color: #F44336;
    }
    
    .icon {
      font-size: 48px;
      margin-bottom: 20px;
    }
  </style>
</head>
<body>
  <div class="container">
    <div id="loading">
      <div class="spinner"></div>
      <h1>Authenticating...</h1>
      <p>Please wait while we complete your sign in.</p>
    </div>
    
    <div id="success" style="display: none;">
      <div class="icon">✓</div>
      <h1 class="success">Success!</h1>
      <p>You're now signed in. This window will close automatically.</p>
    </div>
    
    <div id="error" style="display: none;">
      <div class="icon">✕</div>
      <h1 class="error">Authentication Failed</h1>
      <p id="error-message">Something went wrong. Please try again.</p>
    </div>
  </div>

  <script src="callback.js"></script>
</body>
</html>
```

#### 4.4.3 auth/callback.js

```javascript
/**
 * Authentication Callback Handler
 * 
 * This page is loaded when your auth server redirects back after login.
 * It extracts the token and sends it to the service worker.
 */

(async function() {
  const loadingEl = document.getElementById('loading');
  const successEl = document.getElementById('success');
  const errorEl = document.getElementById('error');
  const errorMsgEl = document.getElementById('error-message');

  function showSuccess() {
    loadingEl.style.display = 'none';
    successEl.style.display = 'block';
  }

  function showError(message) {
    loadingEl.style.display = 'none';
    errorEl.style.display = 'block';
    errorMsgEl.textContent = message;
  }

  try {
    // Extract token from URL
    // Your server might put it in the hash (#token=xxx) or query string (?token=xxx)
    const hash = window.location.hash.substring(1);
    const params = new URLSearchParams(hash || window.location.search);
    
    // Try different parameter names your server might use
    const token = params.get('access_token') || 
                  params.get('token') || 
                  params.get('id_token');
    
    const state = params.get('state');
    const error = params.get('error');
    const errorDescription = params.get('error_description');

    // Check for errors from auth server
    if (error) {
      showError(errorDescription || error);
      return;
    }

    // Validate we got a token
    if (!token) {
      showError('No authentication token received.');
      return;
    }

    // Send token to service worker
    const response = await chrome.runtime.sendMessage({
      type: 'AUTH_CALLBACK',
      token: token,
      state: state
    });

    if (response.success) {
      showSuccess();
      
      // Close this tab after a short delay
      setTimeout(() => {
        window.close();
      }, 2000);
    } else {
      showError(response.error || 'Failed to complete authentication.');
    }

  } catch (error) {
    console.error('Auth callback error:', error);
    showError(error.message || 'An unexpected error occurred.');
  }
})();
```

### 4.5 Popup Authentication UI

#### 4.5.1 popup/components/auth-status.js

```javascript
/**
 * Auth Status Component
 * 
 * Displays authentication state and sign in/out buttons
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
    this.container.innerHTML = `
      <div class="auth-status auth-status--authenticated">
        <div class="user-info">
          <div class="user-avatar">
            ${this.user.avatar 
              ? `<img src="${this.user.avatar}" alt="Avatar">` 
              : `<span>${this.getInitials()}</span>`
            }
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
    await chrome.runtime.sendMessage({ type: 'OPEN_SIGNIN' });
  }

  async handleSignUp() {
    await chrome.runtime.sendMessage({ type: 'OPEN_SIGNUP' });
  }

  async handleLogout() {
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
```

### 4.6 Service Worker Message Handlers for Auth

Add these handlers to `background/service-worker.js`:

```javascript
import { authManager } from './auth.js';

// Initialize auth on service worker start
authManager.init();

// Message handlers
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  switch (message.type) {
    // Authentication messages
    case 'GET_AUTH_STATE':
      sendResponse(authManager.getAuthState());
      return false;

    case 'OPEN_SIGNIN':
      authManager.openSignIn();
      sendResponse({ success: true });
      return false;

    case 'OPEN_SIGNUP':
      authManager.openSignUp();
      sendResponse({ success: true });
      return false;

    case 'AUTH_CALLBACK':
      handleAuthCallback(message, sendResponse);
      return true; // Async response

    case 'LOGOUT':
      handleLogout(sendResponse);
      return true; // Async response

    // ... other message handlers
  }
});

async function handleAuthCallback(message, sendResponse) {
  try {
    await authManager.handleAuthCallback(message.token, message.state);
    sendResponse({ success: true });
  } catch (error) {
    sendResponse({ success: false, error: error.message });
  }
}

async function handleLogout(sendResponse) {
  try {
    await authManager.logout();
    sendResponse({ success: true });
  } catch (error) {
    sendResponse({ success: false, error: error.message });
  }
}
```

### 4.7 Backend API Requirements

Your backend service needs to implement these endpoints:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BACKEND API REQUIREMENTS                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  AUTHENTICATION ENDPOINTS                                                    │
│  ─────────────────────────                                                   │
│                                                                              │
│  GET /auth/signin                                                            │
│  - Displays sign-in form                                                     │
│  - Query params: redirect_uri, client_id, state                              │
│  - On success: redirects to redirect_uri with token                          │
│                                                                              │
│  GET /auth/signup                                                            │
│  - Displays sign-up form                                                     │
│  - Query params: redirect_uri, client_id, state                              │
│  - On success: redirects to redirect_uri with token                          │
│                                                                              │
│  GET /api/v1/auth/me                                                         │
│  - Returns current user info                                                 │
│  - Headers: Authorization: Bearer <token>                                    │
│  - Response: { id, email, name, avatar }                                     │
│                                                                              │
│  POST /api/v1/auth/refresh                                                   │
│  - Refreshes an expiring token                                               │
│  - Headers: Authorization: Bearer <token>                                    │
│  - Response: { token, expiresIn }                                            │
│                                                                              │
│  POST /api/v1/auth/logout                                                    │
│  - Invalidates the token (optional)                                          │
│  - Headers: Authorization: Bearer <token>                                    │
│                                                                              │
│  PROFILE ENDPOINTS                                                           │
│  ─────────────────                                                           │
│                                                                              │
│  GET /api/v1/profile                                                         │
│  - Returns user's profile data                                               │
│  - Headers: Authorization: Bearer <token>                                    │
│  - Response: { firstName, lastName, email, phone, ... }                      │
│                                                                              │
│  POST /api/v1/profile                                                        │
│  - Updates user's profile                                                    │
│  - Headers: Authorization: Bearer <token>                                    │
│  - Body: { firstName, lastName, phone, ... }                                 │
│                                                                              │
│  RESUME ENDPOINTS                                                            │
│  ────────────────                                                            │
│                                                                              │
│  POST /api/v1/resume                                                         │
│  - Uploads/updates user's resume                                             │
│  - Headers: Authorization: Bearer <token>                                    │
│  - Body: multipart/form-data with file                                       │
│                                                                              │
│  GET /api/v1/resume                                                          │
│  - Returns user's stored resume data                                         │
│  - Headers: Authorization: Bearer <token>                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.8 Redirect URL Configuration

Your backend needs to whitelist the extension's callback URL:

```javascript
// On your backend, whitelist this redirect URI pattern:
// chrome-extension://<extension-id>/auth/callback.html

// The extension ID is assigned when you load the extension in Chrome.
// For development, you can find it at chrome://extensions

// For production (after publishing to Chrome Web Store), 
// the ID will be permanent and you should whitelist it.
```

---

## 5. Detailed Component Specifications

### 5.1 manifest.json

```json
{
  "manifest_version": 3,
  "name": "Tailored Resume Autofill",
  "version": "1.0.0",
  "description": "Drag & drop your resume, get tailored autofill for every job application",
  
  "permissions": [
    "storage",
    "activeTab",
    "scripting",
    "identity"
  ],
  
  "host_permissions": [
    "*://boards.greenhouse.io/*",
    "*://boards.eu.greenhouse.io/*",
    "*://job-boards.greenhouse.io/*",
    "*://job-boards.eu.greenhouse.io/*",
    "*://jobs.lever.co/*",
    "*://jobs.eu.lever.co/*",
    "*://*.myworkdayjobs.com/*",
    "*://*.myworkdaysite.com/*",
    "https://your-service.com/*"
  ],
  
  "action": {
    "default_popup": "popup/index.html",
    "default_icon": {
      "16": "assets/icons/icon-16.png",
      "32": "assets/icons/icon-32.png",
      "48": "assets/icons/icon-48.png",
      "128": "assets/icons/icon-128.png"
    },
    "default_title": "Tailored Resume Autofill"
  },
  
  "background": {
    "service_worker": "background/service-worker.js",
    "type": "module"
  },
  
  "content_scripts": [
    {
      "matches": [
        "*://boards.greenhouse.io/*",
        "*://boards.eu.greenhouse.io/*",
        "*://job-boards.greenhouse.io/*",
        "*://job-boards.eu.greenhouse.io/*",
        "*://jobs.lever.co/*",
        "*://jobs.eu.lever.co/*",
        "*://*.myworkdayjobs.com/*",
        "*://*.myworkdaysite.com/*"
      ],
      "js": [
        "lib/xpath-utils.js",
        "config/ats-selectors.js",
        "content/ats-detector.js",
        "content/job-extractor.js",
        "content/resume-tailor.js",
        "content/form-filler.js",
        "content/file-uploader.js",
        "content/ui-overlay.js",
        "content/content-script.js"
      ],
      "css": ["content/content-styles.css"],
      "run_at": "document_end",
      "all_frames": true
    }
  ],
  
  "web_accessible_resources": [
    {
      "resources": ["assets/*", "vendor/*", "auth/*"],
      "matches": ["<all_urls>"]
    }
  ],
  
  "content_security_policy": {
    "extension_pages": "script-src 'self' 'wasm-unsafe-eval'; object-src 'self'"
  },
  
  "externally_connectable": {
    "matches": ["https://your-service.com/*"]
  }
}
```

### 5.2 Popup UI (popup/index.html)

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Tailored Resume Autofill</title>
  <link rel="stylesheet" href="popup.css">
</head>
<body>
  <div id="app">
    <!-- Header with Auth Status -->
    <header class="header">
      <h1>Resume Autofill</h1>
      <div id="status-indicator" class="status"></div>
    </header>

    <!-- Authentication Section -->
    <section id="auth-container" class="auth-container">
      <!-- Populated by auth-status.js -->
    </section>

    <!-- Drop Zone (shown when authenticated) -->
    <section id="drop-zone-container" class="hidden">
      <div id="drop-zone" class="drop-zone">
        <div class="drop-zone__icon">[FILE]</div>
        <p class="drop-zone__text">Drop your resume here</p>
        <p class="drop-zone__subtext">PDF format supported</p>
        <input type="file" id="file-input" accept=".pdf" hdden>
      </div>
    </section>

    <!-- Resume Preview (shown after upload) -->
    <section id="resume-preview" class="resume-preview hidden">
      <h2>Loaded Resume</h2>
      <div class="resume-info">
        <p><strong>Name:</strong> <span id="preview-name"></span></p>
        <p><strong>Email:</strong> <span id="preview-email"></span></p>
        <p><strong>Phone:</strong> <span id="preview-phone"></span></p>
        <p><strong>Experience:</strong> <span id="preview-experience-count"></span> positions</p>
        <p><strong>Education:</strong> <span id="preview-education-count"></span> entries</p>
      </div>
      <div class="resume-actions">
        <button id="sync-resume" class="btn btn--primary">Sync to Cloud</button>
        <button id="clear-resume" class="btn btn--secondary">Clear</button>
      </div>
    </section>

    <!-- User Profile Form -->
    <section id="user-profile" class="user-profile hidden">
      <h2>Contact Info</h2>
      <form id="profile-form">
        <label>
          First Name
          <input type="text" id="profile-first-name" required>
        </label>
        <label>
          Last Name
          <input type="text" id="profile-last-name" required>
        </label>
        <label>
          Email
          <input type="email" id="profile-email" required>
        </label>
        <label>
          Phone
          <input type="tel" id="profile-phone" required>
        </label>
        <label>
          Location (City, State)
          <input type="text" id="profile-location">
        </label>
        <label>
          LinkedIn URL
          <input type="url" id="profile-linkedin">
        </label>
        <button type="submit" class="btn btn--primary">Save Profile</button>
      </form>
    </section>

    <!-- Footer -->
    <footer class="footer">
      <p>Visit a job application page to autofill</p>
    </footer>
  </div>

  <script src="../vendor/pdf.js/pdf.min.js"></script>
  <script src="../lib/storage.js"></script>
  <script src="components/auth-status.js"></script>
  <script src="components/drop-zone.js"></script>
  <script src="components/resume-preview.js"></script>
  <script src="popup.js"></script>
</body>
</html>
```

### 5.3 Content Script Main Entry (content/content-script.js)

```javascript
/**
 * Content Script - Main Entry Point
 * 
 * This is injected into job application pages.
 * It coordinates all the other content script modules.
 */

(async function() {
  'use strict';

  console.log('[TailoredResume] Content script loaded');

  // Wait for DOM to be fully loaded
  if (document.readyState === 'loading') {
    await new Promise(resolve => {
      document.addEventListener('DOMContentLoaded', resolve);
    });
  }

  // Initialize the main controller
  const controller = new AutofillController();
  await controller.init();
})();

class AutofillController {
  constructor() {
    this.atsDetector = new ATSDetector();
    this.jobExtractor = new JobExtractor();
    this.resumeTailor = new ResumeTailor();
    this.formFiller = new FormFiller();
    this.fileUploader = new FileUploader();
    this.uiOverlay = new UIOverlay();
    
    this.currentATS = null;
    this.resumeData = null;
    this.jobDescription = null;
  }

  async init() {
    // Step 1: Detect which ATS we're on
    this.currentATS = this.atsDetector.detect();
    
    if (!this.currentATS) {
      console.log('[TailoredResume] No supported ATS detected');
      return;
    }

    console.log(`[TailoredResume] Detected ATS: ${this.currentATS.name}`);

    // Notify background script
    chrome.runtime.sendMessage({
      type: 'ATS_DETECTED',
      atsName: this.currentATS.name
    });

    // Step 2: Check authentication status
    const authState = await chrome.runtime.sendMessage({ type: 'GET_AUTH_STATE' });
    
    if (!authState.isAuthenticated) {
      console.log('[TailoredResume] User not authenticated');
      this.uiOverlay.showAuthPrompt(() => {
        chrome.runtime.sendMessage({ type: 'OPEN_SIGNIN' });
      });
      return;
    }

    // Step 3: Load resume data from storage
    const response = await chrome.runtime.sendMessage({ type: 'GET_RESUME_DATA' });
    
    if (!response.success || !response.data.resume) {
      console.log('[TailoredResume] No resume loaded');
      this.uiOverlay.showNoResumeMessage();
      return;
    }

    this.resumeData = response.data;

    // Step 4: Show the autofill button
    this.uiOverlay.showAutofillButton(() => this.handleAutofill());

    // Step 5: Extract job description for preview
    this.jobDescription = this.jobExtractor.extract(this.currentATS);
    
    if (this.jobDescription) {
      console.log('[TailoredResume] Job description extracted:', 
        this.jobDescription.title, '@', this.jobDescription.company);
    }
  }

  async handleAutofill() {
    try {
      chrome.runtime.sendMessage({ type: 'AUTOFILL_STARTED' });
      this.uiOverlay.showProgress('Starting autofill...');

      // Step 1: Extract job description if not already done
      if (!this.jobDescription) {
        this.uiOverlay.showProgress('Extracting job description...');
        this.jobDescription = this.jobExtractor.extract(this.currentATS);
      }

      // Step 2: Tailor resume for this job (YOUR LOCAL LOGIC)
      this.uiOverlay.showProgress('Tailoring resume...');
      const tailoredData = this.resumeTailor.tailor(
        this.resumeData.resume,
        this.resumeData.profile,
        this.jobDescription
      );

      // Step 3: Fill form fields
      this.uiOverlay.showProgress('Filling form...');
      await this.formFiller.fill(this.currentATS, tailoredData);

      // Step 4: Upload resume file
      if (this.resumeData.resumeFile) {
        this.uiOverlay.showProgress('Uploading resume...');
        await this.fileUploader.upload(
          this.currentATS,
          this.resumeData.resumeFile,
          this.resumeData.resumeFileName
        );
      }

      // Step 5: Track application (optional)
      await this.trackApplication();

      this.uiOverlay.showSuccess('Autofill complete!');
      chrome.runtime.sendMessage({ type: 'AUTOFILL_COMPLETE', success: true });

    } catch (error) {
      console.error('[TailoredResume] Autofill error:', error);
      this.uiOverlay.showError('Autofill failed: ' + error.message);
      chrome.runtime.sendMessage({ type: 'AUTOFILL_COMPLETE', success: false });
    }
  }

  async trackApplication() {
    // Optional: Track this application in your backend
    try {
      await chrome.runtime.sendMessage({
        type: 'TRACK_APPLICATION',
        data: {
          url: window.location.href,
          ats: this.currentATS.name,
          jobTitle: this.jobDescription?.title,
          company: this.jobDescription?.company,
          appliedAt: new Date().toISOString()
        }
      });
    } catch (error) {
      console.warn('[TailoredResume] Failed to track application:', error);
    }
  }
}
```

### 5.4 Form Filler (content/form-filler.js)

```javascript
/**
 * Form Filler
 * 
 * Fills form fields based on ATS configuration and tailored data.
 * Handles different input types and fill methods.
 */

class FormFiller {
  constructor() {
    this.fillDelay = 100; // ms between fills for stability
  }

  async fill(ats, tailoredData) {
    const config = ats.config;
    const selectors = config.inputSelectors;
    
    console.log('[FormFiller] Starting form fill for', ats.name);
    
    for (const [fieldName, selectorConfigs] of selectors) {
      await this.fillField(fieldName, selectorConfigs, tailoredData, config);
      await this.delay(this.fillDelay);
    }
  }

  async fillField(fieldName, selectorConfigs, data, atsConfig) {
    // Get the value to fill
    const value = this.getValueForField(fieldName, data);
    
    if (!value && value !== 0) {
      console.log(`[FormFiller] Skipping ${fieldName} - no value`);
      return;
    }

    // Try each selector until one works
    for (const selectorConfig of selectorConfigs) {
      try {
        const filled = await this.tryFillWithSelector(
          fieldName,
          selectorConfig,
          value,
          atsConfig
        );
        
        if (filled) {
          console.log(`[FormFiller] Filled ${fieldName}`);
          return;
        }
      } catch (error) {
        console.warn(`[FormFiller] Error filling ${fieldName}:`, error);
      }
    }
    
    console.log(`[FormFiller] Could not fill ${fieldName} - no matching selector`);
  }

  getValueForField(fieldName, data) {
    // Map field names to data properties
    const fieldMap = {
      'first_name': data.firstName,
      'last_name': data.lastName,
      'full_name': data.fullName,
      'email': data.email,
      'phone': data.phone,
      'phone_stripped': data.phoneStripped,
      'location': data.location,
      'linkedin': data.linkedin,
      'github': data.github,
      'portfolio': data.portfolio,
      'summary': data.summary,
      'city': data.city,
      'state': data.state,
      'country': data.country,
      'postal_code': data.postalCode,
      'address': data.address,
    };

    return fieldMap[fieldName];
  }

  async tryFillWithSelector(fieldName, selectorConfig, value, atsConfig) {
    // Handle string selectors (simple XPath or CSS)
    if (typeof selectorConfig === 'string') {
      return this.fillSimpleSelector(selectorConfig, value, atsConfig.defaultMethod);
    }

    // Handle object selectors (complex with actions)
    if (typeof selectorConfig === 'object') {
      return this.fillComplexSelector(selectorConfig, value, atsConfig);
    }

    return false;
  }

  fillSimpleSelector(selector, value, method = 'default') {
    let element = this.findElement(selector);

    if (!element) {
      return false;
    }

    return this.fillElement(element, value, method);
  }

  async fillComplexSelector(config, value, atsConfig) {
    // Handle array of paths
    const paths = Array.isArray(config.path) ? config.path : [config.path];
    
    let element = null;
    for (const path of paths) {
      element = this.findElement(path);
      if (element) break;
    }

    if (!element) {
      return false;
    }

    // Handle value transformations
    if (config.values && typeof config.values === 'object') {
      value = this.transformValue(value, config.values);
    }

    // Handle actions
    if (config.actions && Array.isArray(config.actions)) {
      return this.executeActions(element, config.actions, value, atsConfig);
    }

    // Simple fill with method
    const method = config.method || atsConfig.defaultMethod || 'default';
    return this.fillElement(element, value, method);
  }

  fillElement(element, value, method) {
    switch (method) {
      case 'react':
        return this.fillReact(element, value);
      case 'default':
      case 'defaultWithoutBlur':
        return this.fillDefault(element, value, method !== 'defaultWithoutBlur');
      case 'click':
        return this.fillClick(element);
      case 'selectCheckboxOrRadio':
        return this.fillCheckboxRadio(element, value);
      default:
        return this.fillDefault(element, value);
    }
  }

  fillDefault(element, value, triggerBlur = true) {
    element.focus();
    element.value = '';
    element.value = value;
    
    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
    
    if (triggerBlur) {
      element.dispatchEvent(new Event('blur', { bubbles: true }));
    }
    
    return true;
  }

  fillReact(element, value) {
    // Use native value setter for React inputs
    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype, 'value'
    )?.set;
    
    const nativeTextAreaValueSetter = Object.getOwnPropertyDescriptor(
      window.HTMLTextAreaElement.prototype, 'value'
    )?.set;
    
    const setter = element.tagName === 'TEXTAREA' 
      ? nativeTextAreaValueSetter 
      : nativeInputValueSetter;
    
    if (setter) {
      setter.call(element, value);
    } else {
      element.value = value;
    }
    
    // Dispatch React-compatible events
    const inputEvent = new Event('input', { bubbles: true });
    Object.defineProperty(inputEvent, 'simulated', { value: true });
    element.dispatchEvent(inputEvent);
    
    return true;
  }

  fillClick(element) {
    element.click();
    return true;
  }

  fillCheckboxRadio(element, value) {
    const shouldCheck = value === true || value === 'true' || value === '1';
    
    if (element.checked !== shouldCheck) {
      element.click();
    }
    
    return true;
  }

  async executeActions(element, actions, value, atsConfig) {
    let currentElement = element;
    
    for (const action of actions) {
      await this.executeAction(currentElement, action, value, atsConfig);
      
      if (action.delay) {
        await this.delay(action.delay);
      }
      
      if (action.time && action.path) {
        const newElement = await this.waitForElement(action.path, action.time);
        if (newElement) {
          currentElement = newElement;
        } else if (!action.allowFailure) {
          throw new Error(`Timeout waiting for element: ${action.path}`);
        }
      }
    }
    
    return true;
  }

  async executeAction(element, action, value, atsConfig) {
    switch (action.method) {
      case 'click':
        element.click();
        break;
      case 'default':
      case 'defaultWithoutBlur':
        this.fillElement(element, action.valueKey ? this.getValueForField(action.valueKey, {}) : value, action.method);
        break;
      case 'clearValue':
        element.value = '';
        element.dispatchEvent(new Event('input', { bubbles: true }));
        break;
      case 'blur':
        element.dispatchEvent(new Event('blur', { bubbles: true }));
        break;
      case 'uploadResume':
        // Handled by file-uploader.js
        break;
    }
  }

  transformValue(value, valueMap) {
    if (typeof valueMap === 'string') {
      return this.applyNamedTransform(value, valueMap);
    }
    
    if (typeof valueMap === 'object') {
      return valueMap[value] || value;
    }
    
    return value;
  }

  applyNamedTransform(value, transformName) {
    const transforms = {
      'countryAbbreviationsToNames': {
        'US': 'United States',
        'USA': 'United States',
        'UK': 'United Kingdom',
        'GB': 'United Kingdom',
        'CA': 'Canada',
        'AU': 'Australia',
      },
      'stateAbbreviationsToNames': {
        'CA': 'California',
        'NY': 'New York',
        'TX': 'Texas',
        'WA': 'Washington',
        'FL': 'Florida',
      }
    };
    
    const transform = transforms[transformName];
    return transform?.[value] || value;
  }

  findElement(selector) {
    // Try XPath first
    if (selector.startsWith('.//') || selector.startsWith('//')) {
      try {
        const result = document.evaluate(
          selector,
          document,
          null,
          XPathResult.FIRST_ORDERED_NODE_TYPE,
          null
        );
        if (result.singleNodeValue) {
          return result.singleNodeValue;
        }
      } catch (e) {
        // Fall through to CSS selector
      }
    }
    
    // Try as CSS selector
    return document.querySelector(selector);
  }

  async waitForElement(selector, timeout) {
    const paths = Array.isArray(selector) ? selector : [selector];
    const start = Date.now();
    
    while (Date.now() - start < timeout) {
      for (const path of paths) {
        const element = this.findElement(path);
        if (element) {
          return element;
        }
      }
      await this.delay(100);
    }
    
    return null;
  }

  delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
```

---

## 6. ATS Configuration Files

### 6.1 Greenhouse Configuration

```javascript
// Extracted from Simplify Copilot - Greenhouse ATS selectors
const GREENHOUSE_CONFIG = {
  name: "Greenhouse",
  urls: [
    "*://boards.greenhouse.io/*",
    "*://boards.eu.greenhouse.io/*",
    "*://job-boards.greenhouse.io/*",
    "*://job-boards.eu.greenhouse.io/*"
  ],
  urlsExcluded: [
    "*://boards.greenhouse.io/*/confirmation"
  ],
  defaultMethod: "react",
  submitButtonPaths: [
    ".//input[@type=\"submit\" and @data-trackingid=\"job-application-submit\"]",
    ".//button[@type=\"submit\" and contains(., \"Submit\")]"
  ],
  submittedSuccessPaths: [
    ".//div[@class=\"confirmation\"]/div[@class=\"confirmation__content\"]"
  ],
  inputSelectors: [
    ["first_name", [
      { path: ".//input[@id=\"first_name\"]", method: "react" },
      { path: ".//input[contains(@name, \"first_name\")]", method: "react" }
    ]],
    ["last_name", [
      { path: ".//input[@id=\"last_name\"]", method: "react" },
      { path: ".//input[contains(@name, \"last_name\")]", method: "react" }
    ]],
    ["email", [
      ".//input[@id=\"email\"]",
      { path: ".//input[contains(@name, \"email\")]", method: "react" }
    ]],
    ["phone_stripped", [
      ".//input[@id=\"phone\"]",
      { path: ".//input[contains(@name, \"phone\")]", method: "react" }
    ]],
    ["location", [
      {
        path: ".//div[contains(@class, \"google-location\")]//input[@name=\"location\"]",
        actions: [
          { method: "clearValue" },
          { delay: 100, method: "defaultWithoutBlur" },
          { time: 2500, path: "//div[contains(@class, \"pac-container\")]//div[contains(@class, \"pac-item\")]", event: "mouseover" },
          { method: "blur" }
        ]
      }
    ]],
    ["resume", [
      {
        path: "//input[@type=\"file\" and (@id=\"resume\" or @id=\"resume_file\")]",
        actions: [
          { method: "uploadResume" }
        ]
      }
    ]],
    ["linkedin", [
      ".//input[contains(@name, \"linkedin\") or contains(@id, \"linkedin\")]"
    ]]
  ]
};
```

### 6.2 Lever Configuration

```javascript
// Extracted from Simplify Copilot - Lever ATS selectors
const LEVER_CONFIG = {
  name: "Lever",
  urls: [
    "*://jobs.lever.co/*",
    "*://jobs.eu.lever.co/*"
  ],
  defaultMethod: "default",
  submitButtonPaths: [
    ".//button[@id=\"btn-submit\"]"
  ],
  submittedSuccessPaths: [
    ".//h3[@data-qa=\"msg-submit-success\"]"
  ],
  inputSelectors: [
    ["full_name", [
      ".//input[@name=\"name\"]"
    ]],
    ["email", [
      ".//input[@name=\"email\"]"
    ]],
    ["phone", [
      ".//input[@name=\"phone\"]"
    ]],
    ["linkedin", [
      ".//input[@name=\"urls[LinkedIn]\"]"
    ]],
    ["github", [
      ".//input[@name=\"urls[GitHub]\"]"
    ]],
    ["portfolio", [
      ".//input[@name=\"urls[Portfolio]\"]"
    ]],
    ["resume", [
      {
        path: ".//input[@type=\"file\" and @id=\"resume-upload-input\"]",
        actions: [
          { method: "uploadResume" },
          { time: 10000, path: ".//span[contains(@class, \"resume-upload-success\")]" }
        ]
      }
    ]]
  ]
};
```

### 6.3 Workday Configuration

```javascript
// Extracted from Simplify Copilot - Workday ATS selectors
const WORKDAY_CONFIG = {
  name: "Workday",
  urls: [
    "*://*.myworkdayjobs.com/*",
    "*://*.myworkdaysite.com/*"
  ],
  defaultMethod: "react",
  warningMessage: "For Workday to autofill correctly, stay on the page while it fills.",
  continueButtonPaths: [
    ".//button[@data-automation-id=\"bottom-navigation-next-button\" and contains(., \"Continue\")]"
  ],
  submitButtonPaths: [
    ".//button[@data-automation-id=\"bottom-navigation-next-button\" and contains(., \"Submit\")]"
  ],
  submittedSuccessPaths: [
    ".//div[@role=\"dialog\"]//h2[contains(., \"Application Submitted\")]"
  ],
  inputSelectors: [
    ["first_name", [
      ".//div[contains(@data-automation-id, \"firstName\")]//input[@type=\"text\"]"
    ]],
    ["last_name", [
      ".//div[contains(@data-automation-id, \"lastName\")]//input[@type=\"text\"]"
    ]],
    ["email", [
      ".//input[@data-automation-id=\"email\"]"
    ]],
    ["phone_stripped", [
      ".//input[@data-automation-id=\"phone-number\"]"
    ]],
    ["country", [
      {
        path: ".//button[@data-automation-id=\"countryDropdown\"]",
        values: "countryAbbreviationsToNames",
        actions: [
          { method: "click" },
          { event: "keydown", eventOptions: { keyCode: 40 }, delay: 20 },
          { time: 3000, path: "//ul[@role=\"listbox\"]//li[@role=\"option\"]", method: "click" }
        ]
      }
    ]],
    ["resume", [
      {
        path: ".//div[@data-automation-id=\"resumeUpload\"]",
        actions: [
          { path: "%INPUTPATH%//button[@data-automation-id=\"delete-file\"]", method: "click", allowFailure: true },
          { method: "uploadResume", path: "%INPUTPATH%//input[@type=\"file\"]" },
          { time: 10000, path: ".//div[@data-automation-id=\"file-upload-successful\"]" }
        ]
      }
    ]]
  ]
};
```

### 6.4 Combined ATS Config File

```javascript
// config/ats-selectors.js

const ATS_CONFIGS = {
  "Greenhouse": GREENHOUSE_CONFIG,
  "Lever": LEVER_CONFIG,
  "Workday": WORKDAY_CONFIG
};
```

---

## 7. Data Schema

### 7.1 Resume Data Schema

```typescript
interface ResumeData {
  rawText: string;
  
  contact: {
    fullName: string;
    firstName: string;
    lastName: string;
    email: string;
    phone: string;
    location: string;
    linkedin: string;
    github?: string;
    portfolio?: string;
  };
  
  summary: string;
  
  experience: Array<{
    company: {
      name: string;
      location?: string;
    };
    title: string;
    startDate: { month: number; year: number; };
    endDate?: { month: number; year: number; };
    currentlyWorking: boolean;
    description: string;
  }>;
  
  education: Array<{
    school: string;
    degree: string;
    degreeCode: number;
    major: string;
    gpa?: string;
    startDate?: { month: number; year: number; };
    endDate?: { month: number; year: number; };
  }>;
  
  skills: string[];
  
  certifications?: Array<{
    name: string;
    issuer?: string;
    date?: string;
  }>;
}
```

### 7.2 User Profile Schema

```typescript
interface UserProfile {
  // From your backend
  id: string;
  email: string;
  
  // Contact info
  firstName: string;
  lastName: string;
  phone: string;
  location: string;
  linkedin: string;
  github?: string;
  portfolio?: string;
  
  // EEO data (optional)
  gender?: string;
  ethnicity?: string;
  veteran?: string;
  disability?: string;
  
  // Work authorization
  authorizedToWork?: boolean;
  requiresSponsorship?: boolean;
}
```

---

## 8. Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Create manifest.json
- [ ] Build popup UI with auth status
- [ ] Implement authentication pipeline
- [ ] Set up service worker
- [ ] Create callback handler

### Phase 2: Resume Upload (Week 2)
- [ ] Add drag & drop UI
- [ ] Integrate PDF.js
- [ ] Implement resume parsing
- [ ] Add chrome.storage wrapper
- [ ] Build resume preview

### Phase 3: Content Scripts (Week 3)
- [ ] Build ATS detector
- [ ] Create ATS config files
- [ ] Build UI overlay (autofill button)
- [ ] Add job description extractor

### Phase 4: Form Filling (Week 4)
- [ ] Build form filler core
- [ ] Implement XPath utilities
- [ ] Add fill methods (default, react)
- [ ] Test on Greenhouse
- [ ] Test on Lever
- [ ] Test on Workday

### Phase 5: Resume Tailoring (Week 5)
- [ ] Build keyword extractor
- [ ] Implement experience scoring
- [ ] Add skill prioritization
- [ ] Implement file uploader

### Phase 6: Polish (Week 6)
- [ ] Error handling
- [ ] Progress indicators
- [ ] Profile sync with backend
- [ ] Comprehensive testing

---

## 9. Testing Strategy

### 9.1 Test Sites

| ATS | Test URL |
|-----|----------|
| Greenhouse | https://boards.greenhouse.io/vimeo/jobs/5123817 |
| Lever | https://jobs.lever.co/figma |
| Workday | Any *.myworkdayjobs.com site |

### 9.2 Test Checklist

```
Authentication
[ ] Sign in opens correct URL
[ ] Sign up opens correct URL
[ ] Callback handles token correctly
[ ] Token stored in storage
[ ] User info fetched and displayed
[ ] Logout clears state

Resume Upload
[ ] PDF parses correctly
[ ] Contact info extracted
[ ] Experience extracted
[ ] Storage saves correctly

ATS Detection
[ ] Greenhouse detected
[ ] Lever detected
[ ] Workday detected

Form Filling
[ ] Fields fill correctly
[ ] React inputs handled
[ ] File upload works
```

---

## 10. Known Challenges & Solutions

### React-Controlled Inputs
Use native value setter:
```javascript
const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
setter.call(element, value);
element.dispatchEvent(new Event('input', { bubbles: true }));
```

### Workday Dropdowns
Requires click → keydown → wait → click sequence.

### File Input Security
Use DataTransfer API:
```javascript
const dt = new DataTransfer();
dt.items.add(file);
input.files = dt.files;
```

---

## 11. Resources & References

### Libraries
- **PDF.js**: https://mozilla.github.io/pdf.js/

### Chrome Extension Docs
- Manifest V3: https://dev.chrome.com/docs/extensions/mv3/
- Identity API: https://developer.chrome.com/docs/extensions/reference/identity/
- Storage API: https://developer.chrome.com/docs/extensions/reference/storage/

---

## Quick Start

1. Create project structure per Section 3
2. Copy manifest.json from Section 5.1
3. Set up authentication (Section 4)
4. Build popup UI
5. Implement content scripts
6. Test on each ATS platform

**Questions?** Review the relevant section or expand implementations as needed.

