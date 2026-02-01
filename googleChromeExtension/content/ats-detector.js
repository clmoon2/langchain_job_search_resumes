/**
 * ATS Detector
 * 
 * Detects which ATS platform the current page belongs to
 * based on URL patterns and page content.
 */

class ATSDetector {
  constructor() {
    this.configs = window.ATS_CONFIGS || {};
  }

  /**
   * Detect which ATS the current page belongs to
   */
  detect() {
    const url = window.location.href;
    const hostname = window.location.hostname;

    console.log('[INFO] Detecting ATS for:', hostname);

    // Check each ATS config
    for (const [name, config] of Object.entries(this.configs)) {
      if (this.matchesUrl(url, hostname, config)) {
        // Check if URL is excluded
        if (this.isExcluded(url, config)) {
          console.log('[INFO] URL excluded for ATS:', name);
          continue;
        }

        console.log('[OK] Detected ATS:', name);
        return {
          name,
          config
        };
      }
    }

    console.log('[INFO] No supported ATS detected');
    return null;
  }

  /**
   * Check if URL matches any of the ATS URL patterns
   */
  matchesUrl(url, hostname, config) {
    if (!config.urls) return false;

    for (const pattern of config.urls) {
      if (this.matchPattern(url, hostname, pattern)) {
        return true;
      }
    }

    return false;
  }

  /**
   * Check if URL matches a specific pattern
   */
  matchPattern(url, hostname, pattern) {
    // Convert wildcard pattern to regex
    const regexPattern = pattern
      .replace(/\*/g, '.*')
      .replace(/\?/g, '.')
      .replace(/\//g, '\\/')
      .replace(/\./g, '\\.');

    const regex = new RegExp(regexPattern, 'i');
    return regex.test(url);
  }

  /**
   * Check if URL is in the excluded list
   */
  isExcluded(url, config) {
    if (!config.urlsExcluded) return false;

    for (const pattern of config.urlsExcluded) {
      const regexPattern = pattern
        .replace(/\*/g, '.*')
        .replace(/\?/g, '.')
        .replace(/\//g, '\\/')
        .replace(/\./g, '\\.');

      const regex = new RegExp(regexPattern, 'i');
      if (regex.test(url)) {
        return true;
      }
    }

    return false;
  }

  /**
   * Get ATS config by name
   */
  getConfig(name) {
    return this.configs[name] || null;
  }

  /**
   * Check if we're on a job application page vs job listing page
   */
  isApplicationPage(config) {
    // Check for presence of application form elements
    const formIndicators = [
      'input[type="file"]',
      'input[name*="resume"]',
      'input[name*="email"]',
      'form[id*="application"]',
      'form[class*="application"]'
    ];

    for (const selector of formIndicators) {
      if (document.querySelector(selector)) {
        return true;
      }
    }

    // Check for submit button presence
    if (config.submitButtonPaths) {
      for (const path of config.submitButtonPaths) {
        if (XPathUtils.find(path)) {
          return true;
        }
      }
    }

    return false;
  }

  /**
   * Check if application was already submitted
   */
  isSubmittedPage(config) {
    if (!config.submittedSuccessPaths) return false;

    for (const path of config.submittedSuccessPaths) {
      if (XPathUtils.find(path)) {
        console.log('[INFO] Application already submitted');
        return true;
      }
    }

    return false;
  }
}

// Make available globally
if (typeof window !== 'undefined') {
  window.ATSDetector = ATSDetector;
}
