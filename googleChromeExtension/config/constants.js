/**
 * Configuration Constants
 * 
 * Contains all configuration values for the extension.
 * Replace placeholder URLs with your actual backend service URLs.
 */

export const AUTH_CONFIG = {
  // Backend service URLs - replace with your actual service
  BASE_URL: 'https://your-service.com',
  
  // Authentication endpoints
  SIGNIN_URL: 'https://your-service.com/auth/signin',
  SIGNUP_URL: 'https://your-service.com/auth/signup',
  CALLBACK_PATH: '/auth/callback.html',
  
  // API endpoints
  API_BASE: 'https://your-service.com/api/v1',
  
  // OAuth settings
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
  
  // Job tracking
  TRACK_APPLICATION: '/applications',
  GET_APPLICATIONS: '/applications',
};

export const STORAGE_KEYS = {
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

export const MESSAGE_TYPES = {
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

export const ATS_NAMES = {
  GREENHOUSE: 'Greenhouse',
  LEVER: 'Lever',
  WORKDAY: 'Workday',
};

export const FILL_METHODS = {
  DEFAULT: 'default',
  DEFAULT_WITHOUT_BLUR: 'defaultWithoutBlur',
  REACT: 'react',
  CLICK: 'click',
  CHECKBOX_RADIO: 'selectCheckboxOrRadio',
};

export const LOG_PREFIX = '[TailoredResume]';
