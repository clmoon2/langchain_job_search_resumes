/**
 * Background API Module
 * 
 * Handles API calls from the background script to the backend service.
 */

import { AUTH_CONFIG, API_ENDPOINTS } from '../config/constants.js';
import { authManager } from './auth.js';

class BackgroundApi {
  constructor() {
    this.baseUrl = AUTH_CONFIG.API_BASE;
  }

  /**
   * Get headers with auth token
   */
  getHeaders() {
    const headers = {
      'Content-Type': 'application/json',
      ...authManager.getAuthHeader()
    };
    return headers;
  }

  /**
   * Make an HTTP request
   */
  async request(method, endpoint, data = null) {
    const url = `${this.baseUrl}${endpoint}`;
    
    const config = {
      method,
      headers: this.getHeaders()
    };

    if (data) {
      if (data instanceof FormData) {
        delete config.headers['Content-Type'];
        config.body = data;
      } else {
        config.body = JSON.stringify(data);
      }
    }

    console.log(`[INFO] API ${method} ${endpoint}`);

    const response = await fetch(url, config);

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: response.statusText }));
      console.log(`[ERROR] API ${method} ${endpoint}: ${error.message}`);
      throw new Error(error.message || 'Request failed');
    }

    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      return response.json();
    }

    return response.text();
  }

  /**
   * GET request
   */
  async get(endpoint) {
    return this.request('GET', endpoint);
  }

  /**
   * POST request
   */
  async post(endpoint, data) {
    return this.request('POST', endpoint, data);
  }

  /**
   * Profile API methods
   */
  async getProfile() {
    return this.get(API_ENDPOINTS.GET_PROFILE);
  }

  async updateProfile(profile) {
    return this.post(API_ENDPOINTS.UPDATE_PROFILE, profile);
  }

  /**
   * Resume API methods
   */
  async uploadResume(resumeData, fileName) {
    const formData = new FormData();
    
    const blob = this.base64ToBlob(resumeData, 'application/pdf');
    formData.append('resume', blob, fileName);
    
    return this.post(API_ENDPOINTS.UPLOAD_RESUME, formData);
  }

  async getResume() {
    return this.get(API_ENDPOINTS.GET_RESUME);
  }

  /**
   * Application tracking
   */
  async trackApplication(application) {
    return this.post(API_ENDPOINTS.TRACK_APPLICATION, application);
  }

  async getApplications() {
    return this.get(API_ENDPOINTS.GET_APPLICATIONS);
  }

  /**
   * Convert base64 to Blob
   */
  base64ToBlob(base64, mimeType = 'application/pdf') {
    const base64Data = base64.includes(',') ? base64.split(',')[1] : base64;
    const byteString = atob(base64Data);
    const ab = new ArrayBuffer(byteString.length);
    const ia = new Uint8Array(ab);
    
    for (let i = 0; i < byteString.length; i++) {
      ia[i] = byteString.charCodeAt(i);
    }
    
    return new Blob([ab], { type: mimeType });
  }

  /**
   * Sync profile with backend
   */
  async syncProfile(profile) {
    if (!authManager.isAuthenticated()) {
      console.log('[WARN] Cannot sync profile - not authenticated');
      return null;
    }

    try {
      const result = await this.updateProfile(profile);
      console.log('[OK] Profile synced');
      return result;
    } catch (error) {
      console.log('[ERROR] Profile sync failed:', error.message);
      throw error;
    }
  }

  /**
   * Sync resume with backend
   */
  async syncResume(resumeData, resumeFile, resumeFileName) {
    if (!authManager.isAuthenticated()) {
      console.log('[WARN] Cannot sync resume - not authenticated');
      return null;
    }

    try {
      const result = await this.uploadResume(resumeFile, resumeFileName);
      console.log('[OK] Resume synced');
      return result;
    } catch (error) {
      console.log('[ERROR] Resume sync failed:', error.message);
      throw error;
    }
  }
}

export const backgroundApi = new BackgroundApi();
