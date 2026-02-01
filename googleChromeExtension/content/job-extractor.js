/**
 * Job Extractor
 * 
 * Extracts job description, title, company name, and other
 * relevant information from the job posting page.
 */

class JobExtractor {
  constructor() {
    this.extractedData = null;
  }

  /**
   * Extract job information from the current page
   */
  extract(ats) {
    console.log('[INFO] Extracting job description for:', ats.name);

    const config = ats.config;
    const selectors = config.jobDescriptionSelectors || {};

    this.extractedData = {
      title: this.extractText(selectors.title),
      company: this.extractText(selectors.company),
      description: this.extractDescription(selectors.description),
      location: this.extractText(selectors.location),
      url: window.location.href,
      extractedAt: new Date().toISOString()
    };

    // Try fallback extraction if selectors didn't work
    if (!this.extractedData.title) {
      this.extractedData.title = this.extractTitleFallback();
    }

    if (!this.extractedData.company) {
      this.extractedData.company = this.extractCompanyFallback();
    }

    if (!this.extractedData.description) {
      this.extractedData.description = this.extractDescriptionFallback();
    }

    console.log('[OK] Extracted job:', this.extractedData.title, '@', this.extractedData.company);
    
    return this.extractedData;
  }

  /**
   * Extract text from selector(s)
   */
  extractText(selectors) {
    if (!selectors) return '';

    const selectorList = Array.isArray(selectors) ? selectors : [selectors];

    for (const selector of selectorList) {
      const text = XPathUtils.getText(selector);
      if (text) {
        return text.trim();
      }
    }

    return '';
  }

  /**
   * Extract job description
   */
  extractDescription(selectors) {
    if (!selectors) return '';

    const selectorList = Array.isArray(selectors) ? selectors : [selectors];

    for (const selector of selectorList) {
      const element = XPathUtils.find(selector);
      if (element) {
        return this.cleanDescription(element.innerText || element.textContent);
      }
    }

    return '';
  }

  /**
   * Fallback title extraction
   */
  extractTitleFallback() {
    // Try common title selectors
    const titleSelectors = [
      'h1.job-title',
      'h1[class*="title"]',
      '.posting-headline h2',
      '[data-testid="job-title"]',
      'h1',
      'title'
    ];

    for (const selector of titleSelectors) {
      const element = document.querySelector(selector);
      if (element) {
        const text = element.textContent.trim();
        if (text && text.length < 200) {
          return text;
        }
      }
    }

    // Try page title
    const pageTitle = document.title;
    if (pageTitle) {
      // Remove common suffixes
      return pageTitle
        .replace(/\s*[-|]\s*(Greenhouse|Lever|Workday|Careers?).*$/i, '')
        .replace(/\s*at\s+.+$/i, '')
        .trim();
    }

    return '';
  }

  /**
   * Fallback company extraction
   */
  extractCompanyFallback() {
    // Try common company selectors
    const companySelectors = [
      '.company-name',
      '[class*="company"]',
      '[data-testid="company-name"]',
      '.posting-headline .company'
    ];

    for (const selector of companySelectors) {
      const element = document.querySelector(selector);
      if (element) {
        const text = element.textContent.trim();
        if (text && text.length < 100) {
          return text;
        }
      }
    }

    // Try meta tags
    const metaCompany = document.querySelector('meta[property="og:site_name"]');
    if (metaCompany) {
      return metaCompany.getAttribute('content');
    }

    // Try extracting from URL
    const hostname = window.location.hostname;
    const urlMatch = hostname.match(/jobs\.lever\.co\/([^\/]+)/i) ||
                     hostname.match(/boards\.greenhouse\.io\/([^\/]+)/i) ||
                     hostname.match(/([^.]+)\.myworkdayjobs\.com/i);
    
    if (urlMatch) {
      return this.formatCompanyName(urlMatch[1]);
    }

    return '';
  }

  /**
   * Fallback description extraction
   */
  extractDescriptionFallback() {
    // Try common description containers
    const descriptionSelectors = [
      '.job-description',
      '[class*="description"]',
      '.content',
      '#content',
      'main',
      'article'
    ];

    for (const selector of descriptionSelectors) {
      const element = document.querySelector(selector);
      if (element) {
        const text = this.cleanDescription(element.innerText || element.textContent);
        if (text.length > 200) {
          return text;
        }
      }
    }

    return '';
  }

  /**
   * Clean up description text
   */
  cleanDescription(text) {
    if (!text) return '';

    return text
      .replace(/\s+/g, ' ')
      .replace(/\n\s*\n/g, '\n\n')
      .trim()
      .substring(0, 10000);
  }

  /**
   * Format company name from URL slug
   */
  formatCompanyName(slug) {
    return slug
      .replace(/-/g, ' ')
      .replace(/_/g, ' ')
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ');
  }

  /**
   * Extract keywords from job description
   */
  extractKeywords() {
    if (!this.extractedData?.description) return [];

    const text = this.extractedData.description.toLowerCase();
    
    // Common tech keywords to look for
    const techKeywords = [
      'javascript', 'typescript', 'python', 'java', 'c++', 'c#', 'go', 'rust',
      'react', 'angular', 'vue', 'node', 'express', 'django', 'flask', 'spring',
      'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'terraform',
      'sql', 'postgresql', 'mysql', 'mongodb', 'redis', 'elasticsearch',
      'git', 'ci/cd', 'agile', 'scrum', 'jira',
      'rest', 'api', 'graphql', 'microservices',
      'machine learning', 'ai', 'data science', 'analytics'
    ];

    const found = [];
    for (const keyword of techKeywords) {
      if (text.includes(keyword)) {
        found.push(keyword);
      }
    }

    return found;
  }

  /**
   * Extract required years of experience
   */
  extractYearsOfExperience() {
    if (!this.extractedData?.description) return null;

    const text = this.extractedData.description;
    
    // Match patterns like "5+ years", "3-5 years", "minimum 2 years"
    const patterns = [
      /(\d+)\+?\s*(?:years?|yrs?)\s*(?:of)?\s*(?:experience|exp)/i,
      /(?:minimum|at least|min)\s*(\d+)\s*(?:years?|yrs?)/i,
      /(\d+)\s*-\s*(\d+)\s*(?:years?|yrs?)/i
    ];

    for (const pattern of patterns) {
      const match = text.match(pattern);
      if (match) {
        return parseInt(match[1]);
      }
    }

    return null;
  }

  /**
   * Get extracted data
   */
  getData() {
    return this.extractedData;
  }
}

// Make available globally
if (typeof window !== 'undefined') {
  window.JobExtractor = JobExtractor;
}
