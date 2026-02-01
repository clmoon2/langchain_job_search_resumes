/**
 * API Client
 * 
 * HTTP client for communicating with the backend service.
 */

import { AUTH_CONFIG, API_ENDPOINTS } from '../config/constants.js';

class ApiClient {
  constructor(baseUrl = AUTH_CONFIG.API_BASE) {
    this.baseUrl = baseUrl;
    this.token = null;
  }

  /**
   * Set the authentication token
   */
  setToken(token) {
    this.token = token;
  }

  /**
   * Clear the authentication token
   */
  clearToken() {
    this.token = null;
  }

  /**
   * Get default headers for requests
   */
  getHeaders(includeAuth = true) {
    const headers = {
      'Content-Type': 'application/json',
    };

    if (includeAuth && this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    return headers;
  }

  /**
   * Make an HTTP request
   */
  async request(method, endpoint, data = null, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const includeAuth = options.includeAuth !== false;

    const config = {
      method,
      headers: this.getHeaders(includeAuth),
    };

    if (data) {
      if (data instanceof FormData) {
        delete config.headers['Content-Type'];
        config.body = data;
      } else {
        config.body = JSON.stringify(data);
      }
    }

    const response = await fetch(url, config);

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: response.statusText }));
      throw new ApiError(response.status, error.message || 'Request failed');
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
  async get(endpoint, options = {}) {
    return this.request('GET', endpoint, null, options);
  }

  /**
   * POST request
   */
  async post(endpoint, data, options = {}) {
    return this.request('POST', endpoint, data, options);
  }

  /**
   * PUT request
   */
  async put(endpoint, data, options = {}) {
    return this.request('PUT', endpoint, data, options);
  }

  /**
   * PATCH request
   */
  async patch(endpoint, data, options = {}) {
    return this.request('PATCH', endpoint, data, options);
  }

  /**
   * DELETE request
   */
  async delete(endpoint, options = {}) {
    return this.request('DELETE', endpoint, null, options);
  }

  // Auth API methods
  async getCurrentUser() {
    return this.get(API_ENDPOINTS.ME);
  }

  async refreshToken() {
    return this.post(API_ENDPOINTS.REFRESH);
  }

  async logout() {
    return this.post(API_ENDPOINTS.LOGOUT);
  }

  // Profile API methods
  async getProfile() {
    return this.get(API_ENDPOINTS.GET_PROFILE);
  }

  async updateProfile(profile) {
    return this.post(API_ENDPOINTS.UPDATE_PROFILE, profile);
  }

  // Resume API methods
  async uploadResume(file) {
    const formData = new FormData();
    formData.append('resume', file);
    return this.post(API_ENDPOINTS.UPLOAD_RESUME, formData);
  }

  async getResume() {
    return this.get(API_ENDPOINTS.GET_RESUME);
  }

  // Application tracking API methods
  async trackApplication(application) {
    return this.post(API_ENDPOINTS.TRACK_APPLICATION, application);
  }

  async getApplications() {
    return this.get(API_ENDPOINTS.GET_APPLICATIONS);
  }
}

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

// Create singleton instance
const apiClient = new ApiClient();

export { ApiClient, ApiError, apiClient };
