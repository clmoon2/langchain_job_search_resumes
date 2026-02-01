/**
 * Popup Main Script
 * 
 * Initializes all popup components and handles global state.
 */

class PopupApp {
  constructor() {
    this.authStatus = null;
    this.dropZone = null;
    this.resumePreview = null;
    this.statusIndicator = null;
    this.isAuthenticated = false;
    this.resumeData = null;
  }

  async init() {
    console.log('[INFO] Initializing popup');

    // Initialize components
    this.authStatus = new AuthStatus('auth-container');
    this.dropZone = new DropZone('drop-zone-container');
    this.resumePreview = new ResumePreview('resume-preview');
    this.statusIndicator = new StatusIndicator('status-indicator');

    // Set up event listeners
    this.setupEventListeners();

    // Initialize auth status
    await this.authStatus.init();

    // Load existing data
    await this.loadExistingData();

    // Set up message listeners
    this.setupMessageListeners();

    console.log('[OK] Popup initialized');
  }

  setupEventListeners() {
    // Drop zone file selection
    this.dropZone.onFileSelected = async (file) => {
      await this.handleFileSelected(file);
    };

    // Resume preview actions
    document.getElementById('sync-resume')?.addEventListener('click', () => {
      this.syncResume();
    });

    document.getElementById('clear-resume')?.addEventListener('click', () => {
      this.clearResume();
    });

    // Profile form submission
    document.getElementById('profile-form')?.addEventListener('submit', (e) => {
      e.preventDefault();
      this.saveProfile();
    });
  }

  setupMessageListeners() {
    chrome.runtime.onMessage.addListener((message) => {
      switch (message.type) {
        case 'AUTH_STATE_CHANGED':
          this.handleAuthStateChanged(message.isAuthenticated);
          break;
      }
    });
  }

  async loadExistingData() {
    try {
      // Get auth state
      const authState = await chrome.runtime.sendMessage({ type: 'GET_AUTH_STATE' });
      this.isAuthenticated = authState.isAuthenticated;

      // Update UI based on auth state
      this.updateUIForAuthState();

      // Load resume data if authenticated
      if (this.isAuthenticated) {
        const response = await chrome.runtime.sendMessage({ type: 'GET_RESUME_DATA' });
        if (response.success && response.data.resume) {
          this.resumeData = response.data;
          this.showResumePreview(response.data.resume);
        }

        // Load profile data
        const profileResponse = await chrome.runtime.sendMessage({ type: 'GET_PROFILE' });
        if (profileResponse.success && profileResponse.data) {
          this.populateProfileForm(profileResponse.data);
        }
      }
    } catch (error) {
      console.log('[ERROR] Failed to load existing data:', error.message);
    }
  }

  handleAuthStateChanged(isAuthenticated) {
    this.isAuthenticated = isAuthenticated;
    this.updateUIForAuthState();
    
    if (isAuthenticated) {
      this.loadExistingData();
    }
  }

  updateUIForAuthState() {
    const dropZoneContainer = document.getElementById('drop-zone-container');
    const resumePreview = document.getElementById('resume-preview');
    const userProfile = document.getElementById('user-profile');

    if (this.isAuthenticated) {
      this.statusIndicator.setConnected();
      
      // Show drop zone if no resume, otherwise show preview
      if (this.resumeData?.resume) {
        dropZoneContainer.classList.add('hidden');
        resumePreview.classList.remove('hidden');
      } else {
        dropZoneContainer.classList.remove('hidden');
        resumePreview.classList.add('hidden');
      }
      
      userProfile.classList.remove('hidden');
    } else {
      this.statusIndicator.setDisconnected();
      dropZoneContainer.classList.add('hidden');
      resumePreview.classList.add('hidden');
      userProfile.classList.add('hidden');
    }
  }

  async handleFileSelected(file) {
    console.log('[INFO] File selected:', file.name);
    
    try {
      this.showToast('[INFO] Parsing resume...', 'info');
      
      // Parse the PDF
      const parser = new PDFParser();
      const parsed = await parser.parseFile(file);
      
      console.log('[OK] Resume parsed');

      // Convert file to base64 for storage
      const base64File = await this.fileToBase64(file);

      // Save to storage
      const saveResponse = await chrome.runtime.sendMessage({
        type: 'SAVE_RESUME',
        resume: parsed,
        resumeFile: base64File,
        resumeFileName: file.name
      });

      if (saveResponse.success) {
        this.resumeData = {
          resume: parsed,
          resumeFile: base64File,
          resumeFileName: file.name
        };
        
        this.showResumePreview(parsed);
        this.populateProfileFromResume(parsed);
        this.showToast('[OK] Resume loaded successfully', 'success');
      } else {
        throw new Error(saveResponse.error);
      }
    } catch (error) {
      console.log('[ERROR] Failed to parse resume:', error.message);
      this.showToast('[ERROR] Failed to parse resume: ' + error.message, 'error');
    }
  }

  showResumePreview(resume) {
    const dropZoneContainer = document.getElementById('drop-zone-container');
    const resumePreview = document.getElementById('resume-preview');

    dropZoneContainer.classList.add('hidden');
    resumePreview.classList.remove('hidden');

    this.resumePreview.update(resume);
  }

  populateProfileFromResume(resume) {
    if (!resume.contact) return;

    const contact = resume.contact;
    
    this.setInputValue('profile-first-name', contact.firstName);
    this.setInputValue('profile-last-name', contact.lastName);
    this.setInputValue('profile-email', contact.email);
    this.setInputValue('profile-phone', contact.phone);
    this.setInputValue('profile-location', contact.location);
    this.setInputValue('profile-linkedin', contact.linkedin);
    this.setInputValue('profile-github', contact.github);
  }

  populateProfileForm(profile) {
    this.setInputValue('profile-first-name', profile.firstName);
    this.setInputValue('profile-last-name', profile.lastName);
    this.setInputValue('profile-email', profile.email);
    this.setInputValue('profile-phone', profile.phone);
    this.setInputValue('profile-location', profile.location);
    this.setInputValue('profile-linkedin', profile.linkedin);
    this.setInputValue('profile-github', profile.github);
  }

  setInputValue(id, value) {
    const input = document.getElementById(id);
    if (input && value) {
      input.value = value;
    }
  }

  async saveProfile() {
    const profile = {
      firstName: document.getElementById('profile-first-name')?.value || '',
      lastName: document.getElementById('profile-last-name')?.value || '',
      email: document.getElementById('profile-email')?.value || '',
      phone: document.getElementById('profile-phone')?.value || '',
      location: document.getElementById('profile-location')?.value || '',
      linkedin: document.getElementById('profile-linkedin')?.value || '',
      github: document.getElementById('profile-github')?.value || ''
    };

    try {
      const response = await chrome.runtime.sendMessage({
        type: 'SAVE_PROFILE',
        profile
      });

      if (response.success) {
        this.showToast('[OK] Profile saved', 'success');
      } else {
        throw new Error(response.error);
      }
    } catch (error) {
      console.log('[ERROR] Failed to save profile:', error.message);
      this.showToast('[ERROR] Failed to save profile', 'error');
    }
  }

  async syncResume() {
    if (!this.resumeData) {
      this.showToast('[WARN] No resume to sync', 'error');
      return;
    }

    this.showToast('[INFO] Syncing resume...', 'info');

    try {
      const response = await chrome.runtime.sendMessage({
        type: 'SYNC_RESUME',
        resume: this.resumeData.resume,
        resumeFile: this.resumeData.resumeFile,
        resumeFileName: this.resumeData.resumeFileName
      });

      if (response.success) {
        this.showToast('[OK] Resume synced to cloud', 'success');
      } else {
        throw new Error(response.error);
      }
    } catch (error) {
      console.log('[ERROR] Failed to sync resume:', error.message);
      this.showToast('[ERROR] Sync failed: ' + error.message, 'error');
    }
  }

  async clearResume() {
    try {
      const response = await chrome.runtime.sendMessage({ type: 'CLEAR_RESUME' });

      if (response.success) {
        this.resumeData = null;
        
        const dropZoneContainer = document.getElementById('drop-zone-container');
        const resumePreview = document.getElementById('resume-preview');
        
        dropZoneContainer.classList.remove('hidden');
        resumePreview.classList.add('hidden');
        
        this.showToast('[OK] Resume cleared', 'success');
      } else {
        throw new Error(response.error);
      }
    } catch (error) {
      console.log('[ERROR] Failed to clear resume:', error.message);
      this.showToast('[ERROR] Failed to clear resume', 'error');
    }
  }

  fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  showToast(message, type = 'info') {
    // Remove existing toast
    const existing = document.querySelector('.toast');
    if (existing) {
      existing.remove();
    }

    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
      toast.remove();
    }, 3000);
  }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  const app = new PopupApp();
  app.init();
});
