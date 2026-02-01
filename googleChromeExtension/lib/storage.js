/**
 * Storage Utilities
 * 
 * Wrapper around chrome.storage.local for consistent data access.
 */

const StorageKeys = {
  AUTH_TOKEN: 'authToken',
  CURRENT_USER: 'currentUser',
  TOKEN_EXPIRY: 'tokenExpiry',
  AUTH_STATE: 'authState',
  BASE_RESUME: 'baseResume',
  RESUME_FILE: 'resumeFile',
  RESUME_FILE_NAME: 'resumeFileName',
  USER_PROFILE: 'userProfile',
  SETTINGS: 'settings',
};

class StorageManager {
  /**
   * Get a value from storage
   */
  static async get(key) {
    const result = await chrome.storage.local.get(key);
    return result[key];
  }

  /**
   * Get multiple values from storage
   */
  static async getMultiple(keys) {
    return chrome.storage.local.get(keys);
  }

  /**
   * Set a value in storage
   */
  static async set(key, value) {
    return chrome.storage.local.set({ [key]: value });
  }

  /**
   * Set multiple values in storage
   */
  static async setMultiple(data) {
    return chrome.storage.local.set(data);
  }

  /**
   * Remove a value from storage
   */
  static async remove(key) {
    return chrome.storage.local.remove(key);
  }

  /**
   * Remove multiple values from storage
   */
  static async removeMultiple(keys) {
    return chrome.storage.local.remove(keys);
  }

  /**
   * Clear all storage
   */
  static async clear() {
    return chrome.storage.local.clear();
  }

  // Auth-specific methods
  static async getAuthToken() {
    return this.get(StorageKeys.AUTH_TOKEN);
  }

  static async setAuthToken(token) {
    return this.set(StorageKeys.AUTH_TOKEN, token);
  }

  static async getCurrentUser() {
    return this.get(StorageKeys.CURRENT_USER);
  }

  static async setCurrentUser(user) {
    return this.set(StorageKeys.CURRENT_USER, user);
  }

  static async getTokenExpiry() {
    return this.get(StorageKeys.TOKEN_EXPIRY);
  }

  static async setTokenExpiry(expiry) {
    return this.set(StorageKeys.TOKEN_EXPIRY, expiry);
  }

  static async clearAuth() {
    return this.removeMultiple([
      StorageKeys.AUTH_TOKEN,
      StorageKeys.CURRENT_USER,
      StorageKeys.TOKEN_EXPIRY,
      StorageKeys.AUTH_STATE
    ]);
  }

  // Resume-specific methods
  static async getResumeData() {
    const data = await this.getMultiple([
      StorageKeys.BASE_RESUME,
      StorageKeys.RESUME_FILE,
      StorageKeys.RESUME_FILE_NAME,
      StorageKeys.USER_PROFILE
    ]);
    
    return {
      resume: data[StorageKeys.BASE_RESUME],
      resumeFile: data[StorageKeys.RESUME_FILE],
      resumeFileName: data[StorageKeys.RESUME_FILE_NAME],
      profile: data[StorageKeys.USER_PROFILE]
    };
  }

  static async setResumeData(resume, resumeFile, resumeFileName) {
    return this.setMultiple({
      [StorageKeys.BASE_RESUME]: resume,
      [StorageKeys.RESUME_FILE]: resumeFile,
      [StorageKeys.RESUME_FILE_NAME]: resumeFileName
    });
  }

  static async clearResumeData() {
    return this.removeMultiple([
      StorageKeys.BASE_RESUME,
      StorageKeys.RESUME_FILE,
      StorageKeys.RESUME_FILE_NAME
    ]);
  }

  // Profile-specific methods
  static async getUserProfile() {
    return this.get(StorageKeys.USER_PROFILE);
  }

  static async setUserProfile(profile) {
    return this.set(StorageKeys.USER_PROFILE, profile);
  }

  // Settings-specific methods
  static async getSettings() {
    return this.get(StorageKeys.SETTINGS) || {};
  }

  static async setSettings(settings) {
    return this.set(StorageKeys.SETTINGS, settings);
  }

  static async updateSettings(updates) {
    const current = await this.getSettings();
    return this.setSettings({ ...current, ...updates });
  }

  /**
   * Convert a File/Blob to base64 for storage
   */
  static async fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  /**
   * Convert base64 back to Blob
   */
  static base64ToBlob(base64, mimeType = 'application/pdf') {
    const byteString = atob(base64.split(',')[1]);
    const ab = new ArrayBuffer(byteString.length);
    const ia = new Uint8Array(ab);
    
    for (let i = 0; i < byteString.length; i++) {
      ia[i] = byteString.charCodeAt(i);
    }
    
    return new Blob([ab], { type: mimeType });
  }
}

// Make available globally
if (typeof window !== 'undefined') {
  window.StorageManager = StorageManager;
  window.StorageKeys = StorageKeys;
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { StorageManager, StorageKeys };
}
