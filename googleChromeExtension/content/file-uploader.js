/**
 * File Uploader
 * 
 * Handles resume file uploads to ATS platforms.
 * Uses DataTransfer API to programmatically set file inputs.
 */

class FileUploader {
  constructor() {
    this.uploadTimeout = 10000;
  }

  /**
   * Upload resume file to the ATS
   */
  async upload(ats, resumeFileBase64, fileName) {
    console.log('[INFO] Uploading resume:', fileName);

    const config = ats.config;
    const selectors = config.inputSelectors;

    // Get resume selector config
    const resumeConfig = selectors.get('resume');
    if (!resumeConfig) {
      console.log('[WARN] No resume selector configured for', ats.name);
      return false;
    }

    // Convert base64 to File
    const file = this.base64ToFile(resumeFileBase64, fileName);

    // Try each selector
    const configList = Array.isArray(resumeConfig) ? resumeConfig : [resumeConfig];

    for (const selectorConfig of configList) {
      try {
        const success = await this.tryUpload(selectorConfig, file, config);
        if (success) {
          console.log('[OK] Resume uploaded successfully');
          return true;
        }
      } catch (error) {
        console.log('[WARN] Upload attempt failed:', error.message);
      }
    }

    console.log('[ERROR] Failed to upload resume');
    return false;
  }

  /**
   * Try to upload using a selector config
   */
  async tryUpload(selectorConfig, file, atsConfig) {
    const config = typeof selectorConfig === 'string' 
      ? { path: selectorConfig } 
      : selectorConfig;

    // Find the input element
    let inputElement = null;
    const paths = Array.isArray(config.path) ? config.path : [config.path];

    for (const path of paths) {
      inputElement = XPathUtils.find(path);
      if (inputElement) break;
    }

    if (!inputElement) {
      return false;
    }

    // Execute pre-upload actions if specified
    if (config.actions) {
      await this.executePreUploadActions(inputElement, config, atsConfig);
      
      // Find the actual file input if path changed
      for (const action of config.actions) {
        if (action.method === 'uploadResume' && action.path) {
          const uploadPath = action.path.replace(/%INPUTPATH%/g, config.path);
          const newInput = XPathUtils.find(uploadPath);
          if (newInput) {
            inputElement = newInput;
          }
        }
      }
    }

    // Find the file input (might be nested)
    let fileInput = inputElement;
    if (inputElement.tagName !== 'INPUT' || inputElement.type !== 'file') {
      fileInput = inputElement.querySelector('input[type="file"]');
    }

    if (!fileInput) {
      console.log('[WARN] No file input found');
      return false;
    }

    // Upload the file
    const uploaded = await this.setFileInput(fileInput, file);

    if (!uploaded) {
      return false;
    }

    // Wait for upload success indicator if specified
    if (config.actions) {
      for (const action of config.actions) {
        if (action.time && action.path && action.method !== 'uploadResume') {
          const successPath = action.path;
          const successElement = await this.waitForElement(successPath, action.time);
          if (!successElement) {
            console.log('[WARN] Upload success indicator not found');
          }
        }
      }
    }

    return true;
  }

  /**
   * Execute pre-upload actions
   */
  async executePreUploadActions(element, config, atsConfig) {
    if (!config.actions) return;

    for (const action of config.actions) {
      // Skip the actual upload action
      if (action.method === 'uploadResume') continue;

      // Handle delete existing file action
      if (action.path && action.method === 'click') {
        let actionPath = action.path;
        if (config.path) {
          actionPath = actionPath.replace(/%INPUTPATH%/g, config.path);
        }

        const actionElement = XPathUtils.find(actionPath);
        if (actionElement) {
          actionElement.click();
          await this.delay(500);
        } else if (!action.allowFailure) {
          console.log('[WARN] Pre-upload action element not found');
        }
      }

      if (action.delay) {
        await this.delay(action.delay);
      }
    }
  }

  /**
   * Set file input value using DataTransfer API
   */
  async setFileInput(input, file) {
    try {
      // Create DataTransfer and add file
      const dataTransfer = new DataTransfer();
      dataTransfer.items.add(file);
      
      // Set the files property
      input.files = dataTransfer.files;

      // Dispatch events
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));

      console.log('[INFO] File set on input');
      return true;
    } catch (error) {
      console.log('[ERROR] Failed to set file:', error.message);
      
      // Fallback: try direct assignment
      try {
        const dt = new DataTransfer();
        dt.items.add(file);
        Object.defineProperty(input, 'files', {
          value: dt.files,
          writable: true
        });
        input.dispatchEvent(new Event('change', { bubbles: true }));
        return true;
      } catch (fallbackError) {
        console.log('[ERROR] Fallback failed:', fallbackError.message);
        return false;
      }
    }
  }

  /**
   * Convert base64 to File object
   */
  base64ToFile(base64, fileName) {
    // Handle data URL format
    const base64Data = base64.includes(',') ? base64.split(',')[1] : base64;
    const mimeType = base64.includes(',') 
      ? base64.split(',')[0].match(/:(.*?);/)?.[1] || 'application/pdf'
      : 'application/pdf';

    // Decode base64
    const byteCharacters = atob(base64Data);
    const byteNumbers = new Array(byteCharacters.length);
    
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    
    const byteArray = new Uint8Array(byteNumbers);
    const blob = new Blob([byteArray], { type: mimeType });
    
    return new File([blob], fileName, { type: mimeType });
  }

  /**
   * Wait for element to appear
   */
  async waitForElement(selector, timeout) {
    const paths = Array.isArray(selector) ? selector : [selector];
    const start = Date.now();
    
    while (Date.now() - start < timeout) {
      for (const path of paths) {
        const element = XPathUtils.find(path);
        if (element) {
          return element;
        }
      }
      await this.delay(100);
    }
    
    return null;
  }

  /**
   * Delay helper
   */
  delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// Make available globally
if (typeof window !== 'undefined') {
  window.FileUploader = FileUploader;
}
