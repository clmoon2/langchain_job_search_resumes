/**
 * XPath Utilities
 * 
 * Helper functions for XPath evaluation and element selection.
 */

const XPathUtils = {
  /**
   * Evaluate an XPath expression and return the first matching element
   */
  findFirst(xpath, context = document) {
    try {
      const result = document.evaluate(
        xpath,
        context,
        null,
        XPathResult.FIRST_ORDERED_NODE_TYPE,
        null
      );
      return result.singleNodeValue;
    } catch (error) {
      console.warn('[XPathUtils] Error evaluating XPath:', xpath, error);
      return null;
    }
  },

  /**
   * Evaluate an XPath expression and return all matching elements
   */
  findAll(xpath, context = document) {
    try {
      const result = document.evaluate(
        xpath,
        context,
        null,
        XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,
        null
      );
      
      const nodes = [];
      for (let i = 0; i < result.snapshotLength; i++) {
        nodes.push(result.snapshotItem(i));
      }
      return nodes;
    } catch (error) {
      console.warn('[XPathUtils] Error evaluating XPath:', xpath, error);
      return [];
    }
  },

  /**
   * Find an element using either XPath or CSS selector
   */
  find(selector, context = document) {
    if (this.isXPath(selector)) {
      return this.findFirst(selector, context);
    }
    return context.querySelector(selector);
  },

  /**
   * Find all elements using either XPath or CSS selector
   */
  findAllMixed(selector, context = document) {
    if (this.isXPath(selector)) {
      return this.findAll(selector, context);
    }
    return Array.from(context.querySelectorAll(selector));
  },

  /**
   * Check if a selector is an XPath expression
   */
  isXPath(selector) {
    return selector.startsWith('.//') || 
           selector.startsWith('//') || 
           selector.startsWith('(');
  },

  /**
   * Try multiple selectors and return the first matching element
   */
  findFirstMatch(selectors, context = document) {
    for (const selector of selectors) {
      const element = this.find(selector, context);
      if (element) {
        return element;
      }
    }
    return null;
  },

  /**
   * Wait for an element to appear
   */
  async waitFor(selector, timeout = 5000, context = document) {
    const start = Date.now();
    
    while (Date.now() - start < timeout) {
      const element = this.find(selector, context);
      if (element) {
        return element;
      }
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    return null;
  },

  /**
   * Wait for any of multiple selectors to appear
   */
  async waitForAny(selectors, timeout = 5000, context = document) {
    const start = Date.now();
    
    while (Date.now() - start < timeout) {
      const element = this.findFirstMatch(selectors, context);
      if (element) {
        return element;
      }
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    return null;
  },

  /**
   * Check if an element is visible
   */
  isVisible(element) {
    if (!element) return false;
    
    const style = window.getComputedStyle(element);
    return style.display !== 'none' && 
           style.visibility !== 'hidden' && 
           style.opacity !== '0' &&
           element.offsetParent !== null;
  },

  /**
   * Find visible element from selectors
   */
  findVisible(selectors, context = document) {
    const selectorList = Array.isArray(selectors) ? selectors : [selectors];
    
    for (const selector of selectorList) {
      const elements = this.findAllMixed(selector, context);
      for (const element of elements) {
        if (this.isVisible(element)) {
          return element;
        }
      }
    }
    
    return null;
  },

  /**
   * Get text content from element
   */
  getText(selector, context = document) {
    const element = this.find(selector, context);
    return element ? element.textContent.trim() : '';
  },

  /**
   * Get attribute value from element
   */
  getAttribute(selector, attribute, context = document) {
    const element = this.find(selector, context);
    return element ? element.getAttribute(attribute) : null;
  },

  /**
   * Replace %INPUTPATH% placeholder in XPath with actual path
   */
  replacePlaceholder(xpath, inputPath) {
    return xpath.replace(/%INPUTPATH%/g, inputPath);
  },

  /**
   * Build XPath for element with specific attribute containing text
   */
  buildContainsXPath(tag, attribute, text) {
    return `//${tag}[contains(@${attribute}, "${text}")]`;
  },

  /**
   * Build XPath for element with specific text content
   */
  buildTextXPath(tag, text) {
    return `//${tag}[contains(text(), "${text}")]`;
  }
};

// Make available globally for content scripts
if (typeof window !== 'undefined') {
  window.XPathUtils = XPathUtils;
}
