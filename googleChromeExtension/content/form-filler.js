/**
 * Form Filler
 * 
 * Fills form fields based on ATS configuration and tailored data.
 * Handles different input types and fill methods.
 */

class FormFiller {
  constructor() {
    this.fillDelay = 100;
  }

  /**
   * Fill all form fields
   */
  async fill(ats, tailoredData) {
    const config = ats.config;
    const selectors = config.inputSelectors;
    
    console.log('[INFO] Starting form fill for', ats.name);
    
    let filledCount = 0;
    let skipCount = 0;

    for (const [fieldName, selectorConfigs] of selectors) {
      const filled = await this.fillField(fieldName, selectorConfigs, tailoredData, config);
      if (filled) {
        filledCount++;
      } else {
        skipCount++;
      }
      await this.delay(this.fillDelay);
    }

    console.log(`[OK] Form fill complete: ${filledCount} filled, ${skipCount} skipped`);
    return { filledCount, skipCount };
  }

  /**
   * Fill a single field
   */
  async fillField(fieldName, selectorConfigs, data, atsConfig) {
    // Skip resume field - handled by file uploader
    if (fieldName === 'resume') {
      return false;
    }

    const value = this.getValueForField(fieldName, data);
    
    if (!value && value !== 0 && value !== false) {
      console.log(`[SKIP] ${fieldName} - no value`);
      return false;
    }

    const configList = Array.isArray(selectorConfigs) ? selectorConfigs : [selectorConfigs];

    for (const selectorConfig of configList) {
      try {
        const filled = await this.tryFillWithSelector(
          fieldName,
          selectorConfig,
          value,
          atsConfig
        );
        
        if (filled) {
          console.log(`[OK] Filled ${fieldName}`);
          return true;
        }
      } catch (error) {
        console.log(`[WARN] Error filling ${fieldName}:`, error.message);
      }
    }
    
    console.log(`[SKIP] ${fieldName} - no matching element`);
    return false;
  }

  /**
   * Get value for a field name
   */
  getValueForField(fieldName, data) {
    const fieldMap = {
      'first_name': data.firstName,
      'last_name': data.lastName,
      'full_name': data.fullName,
      'email': data.email,
      'phone': data.phone,
      'phone_stripped': data.phoneStripped,
      'location': data.location,
      'linkedin': data.linkedin,
      'github': data.github,
      'portfolio': data.portfolio,
      'summary': data.summary,
      'city': data.city,
      'state': data.state,
      'country': data.country,
      'postal_code': data.postalCode,
      'address': data.address,
      'authorized_to_work': data.authorizedToWork,
      'requires_sponsorship': data.requiresSponsorship,
      'gender': data.gender,
      'ethnicity': data.ethnicity,
      'veteran': data.veteran,
      'disability': data.disability
    };

    return fieldMap[fieldName];
  }

  /**
   * Try to fill using a selector config
   */
  async tryFillWithSelector(fieldName, selectorConfig, value, atsConfig) {
    if (typeof selectorConfig === 'string') {
      return this.fillSimpleSelector(selectorConfig, value, atsConfig.defaultMethod);
    }

    if (typeof selectorConfig === 'object') {
      return this.fillComplexSelector(selectorConfig, value, atsConfig);
    }

    return false;
  }

  /**
   * Fill using a simple selector
   */
  fillSimpleSelector(selector, value, method = 'default') {
    const element = this.findElement(selector);

    if (!element) {
      return false;
    }

    return this.fillElement(element, value, method);
  }

  /**
   * Fill using complex selector config with actions
   */
  async fillComplexSelector(config, value, atsConfig) {
    const paths = Array.isArray(config.path) ? config.path : [config.path];
    
    let element = null;
    for (const path of paths) {
      element = this.findElement(path);
      if (element) break;
    }

    if (!element) {
      return false;
    }

    // Transform value if needed
    if (config.values && typeof config.values === 'object') {
      value = this.transformValue(value, config.values);
    }

    // Execute actions if present
    if (config.actions && Array.isArray(config.actions)) {
      return this.executeActions(element, config, config.actions, value, atsConfig);
    }

    const method = config.method || atsConfig.defaultMethod || 'default';
    return this.fillElement(element, value, method);
  }

  /**
   * Fill an element with a value
   */
  fillElement(element, value, method) {
    switch (method) {
      case 'react':
        return this.fillReact(element, value);
      case 'default':
        return this.fillDefault(element, value, true);
      case 'defaultWithoutBlur':
        return this.fillDefault(element, value, false);
      case 'click':
        return this.fillClick(element);
      case 'selectCheckboxOrRadio':
        return this.fillCheckboxRadio(element, value);
      default:
        return this.fillDefault(element, value, true);
    }
  }

  /**
   * Default fill method
   */
  fillDefault(element, value, triggerBlur = true) {
    element.focus();
    element.value = '';
    element.value = value;
    
    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
    
    if (triggerBlur) {
      element.dispatchEvent(new Event('blur', { bubbles: true }));
    }
    
    return true;
  }

  /**
   * React-compatible fill method
   */
  fillReact(element, value) {
    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype, 'value'
    )?.set;
    
    const nativeTextAreaValueSetter = Object.getOwnPropertyDescriptor(
      window.HTMLTextAreaElement.prototype, 'value'
    )?.set;
    
    const setter = element.tagName === 'TEXTAREA' 
      ? nativeTextAreaValueSetter 
      : nativeInputValueSetter;
    
    if (setter) {
      setter.call(element, value);
    } else {
      element.value = value;
    }
    
    // Dispatch React-compatible events
    const inputEvent = new Event('input', { bubbles: true });
    Object.defineProperty(inputEvent, 'simulated', { value: true });
    element.dispatchEvent(inputEvent);
    
    const changeEvent = new Event('change', { bubbles: true });
    element.dispatchEvent(changeEvent);
    
    return true;
  }

  /**
   * Click fill method
   */
  fillClick(element) {
    element.click();
    return true;
  }

  /**
   * Checkbox/radio fill method
   */
  fillCheckboxRadio(element, value) {
    const shouldCheck = value === true || value === 'true' || value === '1' || value === 'yes';
    
    if (element.checked !== shouldCheck) {
      element.click();
    }
    
    return true;
  }

  /**
   * Execute a sequence of actions
   */
  async executeActions(startElement, config, actions, value, atsConfig) {
    let currentElement = startElement;
    const inputPath = config.path;
    
    for (const action of actions) {
      // Skip uploadResume action - handled by file uploader
      if (action.method === 'uploadResume') {
        continue;
      }

      // Replace placeholder in path
      let actionPath = action.path;
      if (actionPath && inputPath) {
        actionPath = actionPath.replace(/%INPUTPATH%/g, inputPath);
      }

      await this.executeAction(currentElement, action, value, atsConfig);
      
      if (action.delay) {
        await this.delay(action.delay);
      }
      
      // Wait for new element if specified
      if (action.time && actionPath) {
        const newElement = await this.waitForElement(actionPath, action.time);
        if (newElement) {
          currentElement = newElement;
        } else if (!action.allowFailure) {
          console.log('[WARN] Timeout waiting for element');
          return false;
        }
      }
    }
    
    return true;
  }

  /**
   * Execute a single action
   */
  async executeAction(element, action, value, atsConfig) {
    switch (action.method) {
      case 'click':
        element.click();
        break;
      case 'default':
        this.fillDefault(element, value, true);
        break;
      case 'defaultWithoutBlur':
        this.fillDefault(element, value, false);
        break;
      case 'clearValue':
        element.value = '';
        element.dispatchEvent(new Event('input', { bubbles: true }));
        break;
      case 'blur':
        element.dispatchEvent(new Event('blur', { bubbles: true }));
        break;
      case 'focus':
        element.focus();
        break;
    }

    // Handle keyboard events
    if (action.event === 'keydown') {
      const event = new KeyboardEvent('keydown', action.eventOptions || {});
      element.dispatchEvent(event);
    }

    // Handle mouse events
    if (action.event === 'mouseover') {
      const event = new MouseEvent('mouseover', { bubbles: true });
      element.dispatchEvent(event);
    }
  }

  /**
   * Transform value using value map
   */
  transformValue(value, valueMap) {
    if (typeof valueMap === 'string') {
      return this.applyNamedTransform(value, valueMap);
    }
    
    if (typeof valueMap === 'object') {
      return valueMap[value] || value;
    }
    
    return value;
  }

  /**
   * Apply named transform
   */
  applyNamedTransform(value, transformName) {
    const transforms = window.VALUE_TRANSFORMS || {};
    const transform = transforms[transformName];
    return transform?.[value] || value;
  }

  /**
   * Find element using XPath or CSS selector
   */
  findElement(selector) {
    return XPathUtils.find(selector);
  }

  /**
   * Wait for element to appear
   */
  async waitForElement(selector, timeout) {
    const paths = Array.isArray(selector) ? selector : [selector];
    const start = Date.now();
    
    while (Date.now() - start < timeout) {
      for (const path of paths) {
        const element = this.findElement(path);
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
  window.FormFiller = FormFiller;
}
