/**
 * Messaging Utilities
 * 
 * Wrapper around chrome.runtime messaging for consistent communication.
 */

const MessageTypes = {
  // Auth messages
  GET_AUTH_STATE: 'GET_AUTH_STATE',
  OPEN_SIGNIN: 'OPEN_SIGNIN',
  OPEN_SIGNUP: 'OPEN_SIGNUP',
  AUTH_CALLBACK: 'AUTH_CALLBACK',
  AUTH_STATE_CHANGED: 'AUTH_STATE_CHANGED',
  LOGOUT: 'LOGOUT',
  
  // Resume messages
  GET_RESUME_DATA: 'GET_RESUME_DATA',
  SAVE_RESUME: 'SAVE_RESUME',
  CLEAR_RESUME: 'CLEAR_RESUME',
  SYNC_RESUME: 'SYNC_RESUME',
  
  // Profile messages
  GET_PROFILE: 'GET_PROFILE',
  SAVE_PROFILE: 'SAVE_PROFILE',
  SYNC_PROFILE: 'SYNC_PROFILE',
  
  // ATS messages
  ATS_DETECTED: 'ATS_DETECTED',
  AUTOFILL_STARTED: 'AUTOFILL_STARTED',
  AUTOFILL_COMPLETE: 'AUTOFILL_COMPLETE',
  TRACK_APPLICATION: 'TRACK_APPLICATION',
};

class Messenger {
  /**
   * Send a message to the background script
   */
  static async send(type, data = {}) {
    return new Promise((resolve, reject) => {
      try {
        chrome.runtime.sendMessage({ type, ...data }, (response) => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
          } else {
            resolve(response);
          }
        });
      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * Send a message to a specific tab
   */
  static async sendToTab(tabId, type, data = {}) {
    return new Promise((resolve, reject) => {
      try {
        chrome.tabs.sendMessage(tabId, { type, ...data }, (response) => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
          } else {
            resolve(response);
          }
        });
      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * Send a message to all tabs matching a URL pattern
   */
  static async broadcast(urlPattern, type, data = {}) {
    const tabs = await chrome.tabs.query({ url: urlPattern });
    const promises = tabs.map(tab => 
      this.sendToTab(tab.id, type, data).catch(() => null)
    );
    return Promise.all(promises);
  }

  /**
   * Add a message listener
   */
  static addListener(callback) {
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      const result = callback(message, sender);
      
      if (result instanceof Promise) {
        result.then(sendResponse).catch(err => sendResponse({ error: err.message }));
        return true;
      }
      
      if (result !== undefined) {
        sendResponse(result);
      }
      
      return false;
    });
  }

  /**
   * Add a listener for a specific message type
   */
  static on(type, callback) {
    this.addListener((message, sender) => {
      if (message.type === type) {
        return callback(message, sender);
      }
    });
  }

  // Convenience methods for common messages
  static async getAuthState() {
    return this.send(MessageTypes.GET_AUTH_STATE);
  }

  static async openSignIn() {
    return this.send(MessageTypes.OPEN_SIGNIN);
  }

  static async openSignUp() {
    return this.send(MessageTypes.OPEN_SIGNUP);
  }

  static async logout() {
    return this.send(MessageTypes.LOGOUT);
  }

  static async getResumeData() {
    return this.send(MessageTypes.GET_RESUME_DATA);
  }

  static async saveResume(resume, resumeFile, resumeFileName) {
    return this.send(MessageTypes.SAVE_RESUME, { resume, resumeFile, resumeFileName });
  }

  static async clearResume() {
    return this.send(MessageTypes.CLEAR_RESUME);
  }

  static async getProfile() {
    return this.send(MessageTypes.GET_PROFILE);
  }

  static async saveProfile(profile) {
    return this.send(MessageTypes.SAVE_PROFILE, { profile });
  }

  static async trackApplication(data) {
    return this.send(MessageTypes.TRACK_APPLICATION, { data });
  }

  static notifyAutofillStarted() {
    return this.send(MessageTypes.AUTOFILL_STARTED);
  }

  static notifyAutofillComplete(success) {
    return this.send(MessageTypes.AUTOFILL_COMPLETE, { success });
  }

  static notifyAtsDetected(atsName) {
    return this.send(MessageTypes.ATS_DETECTED, { atsName });
  }
}

// Make available globally
if (typeof window !== 'undefined') {
  window.Messenger = Messenger;
  window.MessageTypes = MessageTypes;
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { Messenger, MessageTypes };
}
