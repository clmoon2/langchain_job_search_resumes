/**
 * Service Worker
 * 
 * Main background script that handles message routing,
 * authentication, and storage management.
 */

import { authManager } from './auth.js';
import { backgroundApi } from './api.js';
import { STORAGE_KEYS, MESSAGE_TYPES } from '../config/constants.js';

console.log('[INFO] Service worker starting');

// Initialize auth on service worker start
authManager.init().then(isAuth => {
  console.log('[OK] Auth initialized, authenticated:', isAuth);
}).catch(error => {
  console.log('[ERROR] Auth init failed:', error.message);
});

// Message handlers
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('[INFO] Message received:', message.type);
  
  const handler = messageHandlers[message.type];
  
  if (handler) {
    const result = handler(message, sender);
    
    if (result instanceof Promise) {
      result
        .then(response => sendResponse(response))
        .catch(error => sendResponse({ success: false, error: error.message }));
      return true;
    }
    
    if (result !== undefined) {
      sendResponse(result);
    }
    
    return false;
  }
  
  console.log('[WARN] Unknown message type:', message.type);
  sendResponse({ success: false, error: 'Unknown message type' });
  return false;
});

const messageHandlers = {
  // Authentication handlers
  [MESSAGE_TYPES.GET_AUTH_STATE]: () => {
    return authManager.getAuthState();
  },

  [MESSAGE_TYPES.OPEN_SIGNIN]: async () => {
    await authManager.openSignIn();
    return { success: true };
  },

  [MESSAGE_TYPES.OPEN_SIGNUP]: async () => {
    await authManager.openSignUp();
    return { success: true };
  },

  [MESSAGE_TYPES.AUTH_CALLBACK]: async (message) => {
    try {
      await authManager.handleAuthCallback(message.token, message.state);
      return { success: true };
    } catch (error) {
      return { success: false, error: error.message };
    }
  },

  [MESSAGE_TYPES.LOGOUT]: async () => {
    try {
      await authManager.logout();
      return { success: true };
    } catch (error) {
      return { success: false, error: error.message };
    }
  },

  // Resume handlers
  [MESSAGE_TYPES.GET_RESUME_DATA]: async () => {
    try {
      const data = await chrome.storage.local.get([
        STORAGE_KEYS.BASE_RESUME,
        STORAGE_KEYS.RESUME_FILE,
        STORAGE_KEYS.RESUME_FILE_NAME,
        STORAGE_KEYS.USER_PROFILE
      ]);
      
      return {
        success: true,
        data: {
          resume: data[STORAGE_KEYS.BASE_RESUME],
          resumeFile: data[STORAGE_KEYS.RESUME_FILE],
          resumeFileName: data[STORAGE_KEYS.RESUME_FILE_NAME],
          profile: data[STORAGE_KEYS.USER_PROFILE]
        }
      };
    } catch (error) {
      return { success: false, error: error.message };
    }
  },

  [MESSAGE_TYPES.SAVE_RESUME]: async (message) => {
    try {
      await chrome.storage.local.set({
        [STORAGE_KEYS.BASE_RESUME]: message.resume,
        [STORAGE_KEYS.RESUME_FILE]: message.resumeFile,
        [STORAGE_KEYS.RESUME_FILE_NAME]: message.resumeFileName
      });
      console.log('[OK] Resume saved to storage');
      return { success: true };
    } catch (error) {
      console.log('[ERROR] Failed to save resume:', error.message);
      return { success: false, error: error.message };
    }
  },

  [MESSAGE_TYPES.CLEAR_RESUME]: async () => {
    try {
      await chrome.storage.local.remove([
        STORAGE_KEYS.BASE_RESUME,
        STORAGE_KEYS.RESUME_FILE,
        STORAGE_KEYS.RESUME_FILE_NAME
      ]);
      console.log('[OK] Resume cleared');
      return { success: true };
    } catch (error) {
      return { success: false, error: error.message };
    }
  },

  [MESSAGE_TYPES.SYNC_RESUME]: async (message) => {
    try {
      const result = await backgroundApi.syncResume(
        message.resume,
        message.resumeFile,
        message.resumeFileName
      );
      return { success: true, data: result };
    } catch (error) {
      return { success: false, error: error.message };
    }
  },

  // Profile handlers
  [MESSAGE_TYPES.GET_PROFILE]: async () => {
    try {
      const data = await chrome.storage.local.get(STORAGE_KEYS.USER_PROFILE);
      return { success: true, data: data[STORAGE_KEYS.USER_PROFILE] };
    } catch (error) {
      return { success: false, error: error.message };
    }
  },

  [MESSAGE_TYPES.SAVE_PROFILE]: async (message) => {
    try {
      await chrome.storage.local.set({
        [STORAGE_KEYS.USER_PROFILE]: message.profile
      });
      console.log('[OK] Profile saved');
      return { success: true };
    } catch (error) {
      return { success: false, error: error.message };
    }
  },

  [MESSAGE_TYPES.SYNC_PROFILE]: async (message) => {
    try {
      const result = await backgroundApi.syncProfile(message.profile);
      return { success: true, data: result };
    } catch (error) {
      return { success: false, error: error.message };
    }
  },

  // ATS and autofill handlers
  [MESSAGE_TYPES.ATS_DETECTED]: (message) => {
    console.log('[INFO] ATS detected:', message.atsName);
    return { success: true };
  },

  [MESSAGE_TYPES.AUTOFILL_STARTED]: () => {
    console.log('[INFO] Autofill started');
    return { success: true };
  },

  [MESSAGE_TYPES.AUTOFILL_COMPLETE]: (message) => {
    console.log(message.success ? '[OK] Autofill complete' : '[ERROR] Autofill failed');
    return { success: true };
  },

  [MESSAGE_TYPES.TRACK_APPLICATION]: async (message) => {
    try {
      const result = await backgroundApi.trackApplication(message.data);
      console.log('[OK] Application tracked');
      return { success: true, data: result };
    } catch (error) {
      console.log('[WARN] Failed to track application:', error.message);
      return { success: false, error: error.message };
    }
  }
};

// Handle extension icon click
chrome.action.onClicked.addListener((tab) => {
  console.log('[INFO] Extension icon clicked');
});

// Handle installation
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    console.log('[INFO] Extension installed');
  } else if (details.reason === 'update') {
    console.log('[INFO] Extension updated to version', chrome.runtime.getManifest().version);
  }
});

console.log('[OK] Service worker initialized');
