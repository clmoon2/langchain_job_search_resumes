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
    // Extract token from URL hash or query string
    const hash = window.location.hash.substring(1);
    const params = new URLSearchParams(hash || window.location.search);
    
    // Try different parameter names
    const token = params.get('access_token') || 
                  params.get('token') || 
                  params.get('id_token');
    
    const state = params.get('state');
    const error = params.get('error');
    const errorDescription = params.get('error_description');

    // Check for errors from auth server
    if (error) {
      console.log('[ERROR] Auth error from server:', error);
      showError(errorDescription || error);
      return;
    }

    // Validate we got a token
    if (!token) {
      console.log('[ERROR] No authentication token received');
      showError('No authentication token received.');
      return;
    }

    console.log('[INFO] Token received, sending to service worker');

    // Send token to service worker
    const response = await chrome.runtime.sendMessage({
      type: 'AUTH_CALLBACK',
      token: token,
      state: state
    });

    if (response.success) {
      console.log('[OK] Auth callback successful');
      showSuccess();
      
      // Close this tab after a short delay
      setTimeout(() => {
        window.close();
      }, 2000);
    } else {
      console.log('[ERROR] Auth callback failed:', response.error);
      showError(response.error || 'Failed to complete authentication.');
    }

  } catch (error) {
    console.error('[ERROR] Auth callback error:', error);
    showError(error.message || 'An unexpected error occurred.');
  }
})();
