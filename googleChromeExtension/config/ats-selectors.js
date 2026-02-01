/**
 * ATS Selector Configurations
 * 
 * Contains field selectors and fill configurations for each supported ATS platform.
 */

const GREENHOUSE_CONFIG = {
  name: 'Greenhouse',
  urls: [
    '*://boards.greenhouse.io/*',
    '*://boards.eu.greenhouse.io/*',
    '*://job-boards.greenhouse.io/*',
    '*://job-boards.eu.greenhouse.io/*'
  ],
  urlsExcluded: [
    '*://boards.greenhouse.io/*/confirmation'
  ],
  defaultMethod: 'react',
  submitButtonPaths: [
    './/input[@type="submit" and @data-trackingid="job-application-submit"]',
    './/button[@type="submit" and contains(., "Submit")]'
  ],
  submittedSuccessPaths: [
    './/div[@class="confirmation"]/div[@class="confirmation__content"]'
  ],
  jobDescriptionSelectors: {
    title: '.app-title, h1.job-title, [data-mapped="true"] h1',
    company: '.company-name, [data-company-name]',
    description: '#content, .content, [data-mapped="true"]',
    location: '.location, [data-location]'
  },
  inputSelectors: new Map([
    ['first_name', [
      { path: './/input[@id="first_name"]', method: 'react' },
      { path: './/input[contains(@name, "first_name")]', method: 'react' },
      { path: './/input[@autocomplete="given-name"]', method: 'react' }
    ]],
    ['last_name', [
      { path: './/input[@id="last_name"]', method: 'react' },
      { path: './/input[contains(@name, "last_name")]', method: 'react' },
      { path: './/input[@autocomplete="family-name"]', method: 'react' }
    ]],
    ['email', [
      { path: './/input[@id="email"]', method: 'react' },
      { path: './/input[contains(@name, "email")]', method: 'react' },
      { path: './/input[@type="email"]', method: 'react' }
    ]],
    ['phone_stripped', [
      { path: './/input[@id="phone"]', method: 'react' },
      { path: './/input[contains(@name, "phone")]', method: 'react' },
      { path: './/input[@type="tel"]', method: 'react' }
    ]],
    ['location', [
      {
        path: './/div[contains(@class, "google-location")]//input[@name="location"]',
        method: 'react',
        actions: [
          { method: 'clearValue' },
          { delay: 100, method: 'defaultWithoutBlur' },
          { time: 2500, path: '//div[contains(@class, "pac-container")]//div[contains(@class, "pac-item")]', event: 'mouseover' },
          { method: 'blur' }
        ]
      },
      { path: './/input[contains(@name, "location")]', method: 'react' }
    ]],
    ['linkedin', [
      { path: './/input[contains(@name, "linkedin") or contains(@id, "linkedin")]', method: 'react' },
      { path: './/input[contains(@placeholder, "LinkedIn")]', method: 'react' }
    ]],
    ['github', [
      { path: './/input[contains(@name, "github") or contains(@id, "github")]', method: 'react' },
      { path: './/input[contains(@placeholder, "GitHub")]', method: 'react' }
    ]],
    ['portfolio', [
      { path: './/input[contains(@name, "portfolio") or contains(@id, "portfolio")]', method: 'react' },
      { path: './/input[contains(@name, "website") or contains(@id, "website")]', method: 'react' }
    ]],
    ['resume', [
      {
        path: '//input[@type="file" and (@id="resume" or @id="resume_file" or contains(@name, "resume"))]',
        actions: [
          { method: 'uploadResume' }
        ]
      }
    ]]
  ])
};

const LEVER_CONFIG = {
  name: 'Lever',
  urls: [
    '*://jobs.lever.co/*',
    '*://jobs.eu.lever.co/*'
  ],
  defaultMethod: 'default',
  submitButtonPaths: [
    './/button[@id="btn-submit"]',
    './/button[contains(@class, "postings-btn-submit")]'
  ],
  submittedSuccessPaths: [
    './/h3[@data-qa="msg-submit-success"]',
    './/div[contains(@class, "application-confirmation")]'
  ],
  jobDescriptionSelectors: {
    title: '.posting-headline h2, .posting-title',
    company: '.posting-headline .company, .main-header-logo img[alt]',
    description: '.posting-page .content, .section-wrapper',
    location: '.posting-categories .location, .sort-by-time .location'
  },
  inputSelectors: new Map([
    ['full_name', [
      { path: './/input[@name="name"]', method: 'default' },
      { path: './/input[@id="name"]', method: 'default' }
    ]],
    ['email', [
      { path: './/input[@name="email"]', method: 'default' },
      { path: './/input[@type="email"]', method: 'default' }
    ]],
    ['phone', [
      { path: './/input[@name="phone"]', method: 'default' },
      { path: './/input[@type="tel"]', method: 'default' }
    ]],
    ['location', [
      { path: './/input[@name="location"]', method: 'default' },
      { path: './/input[contains(@placeholder, "Location")]', method: 'default' }
    ]],
    ['linkedin', [
      { path: './/input[@name="urls[LinkedIn]"]', method: 'default' },
      { path: './/input[contains(@placeholder, "LinkedIn")]', method: 'default' }
    ]],
    ['github', [
      { path: './/input[@name="urls[GitHub]"]', method: 'default' },
      { path: './/input[contains(@placeholder, "GitHub")]', method: 'default' }
    ]],
    ['portfolio', [
      { path: './/input[@name="urls[Portfolio]"]', method: 'default' },
      { path: './/input[@name="urls[Other]"]', method: 'default' }
    ]],
    ['resume', [
      {
        path: './/input[@type="file" and @id="resume-upload-input"]',
        actions: [
          { method: 'uploadResume' },
          { time: 10000, path: './/span[contains(@class, "resume-upload-success")]' }
        ]
      },
      {
        path: './/input[@type="file" and contains(@name, "resume")]',
        actions: [
          { method: 'uploadResume' }
        ]
      }
    ]]
  ])
};

const WORKDAY_CONFIG = {
  name: 'Workday',
  urls: [
    '*://*.myworkdayjobs.com/*',
    '*://*.myworkdaysite.com/*'
  ],
  defaultMethod: 'react',
  warningMessage: 'For Workday to autofill correctly, stay on the page while it fills.',
  continueButtonPaths: [
    './/button[@data-automation-id="bottom-navigation-next-button" and contains(., "Continue")]',
    './/button[contains(@class, "css-") and contains(., "Continue")]'
  ],
  submitButtonPaths: [
    './/button[@data-automation-id="bottom-navigation-next-button" and contains(., "Submit")]',
    './/button[contains(@class, "css-") and contains(., "Submit")]'
  ],
  submittedSuccessPaths: [
    './/div[@role="dialog"]//h2[contains(., "Application Submitted")]',
    './/div[contains(@class, "WMQT")]//h2'
  ],
  jobDescriptionSelectors: {
    title: '[data-automation-id="jobPostingHeader"] h2, .css-1q2dra3',
    company: '[data-automation-id="companyLogo"] img[alt], .css-1jxf684',
    description: '[data-automation-id="jobPostingDescription"], .css-1wnpb1n',
    location: '[data-automation-id="locations"], .css-129m7dg'
  },
  inputSelectors: new Map([
    ['first_name', [
      { path: './/div[contains(@data-automation-id, "firstName")]//input[@type="text"]', method: 'react' },
      { path: './/input[@data-automation-id="legalNameSection_firstName"]', method: 'react' }
    ]],
    ['last_name', [
      { path: './/div[contains(@data-automation-id, "lastName")]//input[@type="text"]', method: 'react' },
      { path: './/input[@data-automation-id="legalNameSection_lastName"]', method: 'react' }
    ]],
    ['email', [
      { path: './/input[@data-automation-id="email"]', method: 'react' },
      { path: './/input[contains(@data-automation-id, "email")]', method: 'react' }
    ]],
    ['phone_stripped', [
      { path: './/input[@data-automation-id="phone-number"]', method: 'react' },
      { path: './/input[contains(@data-automation-id, "phone")]', method: 'react' }
    ]],
    ['country', [
      {
        path: './/button[@data-automation-id="countryDropdown"]',
        values: 'countryAbbreviationsToNames',
        actions: [
          { method: 'click' },
          { event: 'keydown', eventOptions: { keyCode: 40 }, delay: 20 },
          { time: 3000, path: '//ul[@role="listbox"]//li[@role="option"]', method: 'click' }
        ]
      }
    ]],
    ['address', [
      { path: './/input[@data-automation-id="addressSection_addressLine1"]', method: 'react' }
    ]],
    ['city', [
      { path: './/input[@data-automation-id="addressSection_city"]', method: 'react' }
    ]],
    ['state', [
      {
        path: './/button[@data-automation-id="addressSection_countryRegion"]',
        values: 'stateAbbreviationsToNames',
        actions: [
          { method: 'click' },
          { time: 3000, path: '//ul[@role="listbox"]//li[@role="option"]', method: 'click' }
        ]
      }
    ]],
    ['postal_code', [
      { path: './/input[@data-automation-id="addressSection_postalCode"]', method: 'react' }
    ]],
    ['linkedin', [
      { path: './/input[contains(@data-automation-id, "linkedin")]', method: 'react' }
    ]],
    ['resume', [
      {
        path: './/div[@data-automation-id="resumeUpload"]',
        actions: [
          { path: '%INPUTPATH%//button[@data-automation-id="delete-file"]', method: 'click', allowFailure: true },
          { method: 'uploadResume', path: '%INPUTPATH%//input[@type="file"]' },
          { time: 10000, path: './/div[@data-automation-id="file-upload-successful"]' }
        ]
      },
      {
        path: './/input[@type="file" and contains(@data-automation-id, "resume")]',
        actions: [
          { method: 'uploadResume' }
        ]
      }
    ]]
  ])
};

// Export configurations
const ATS_CONFIGS = {
  'Greenhouse': GREENHOUSE_CONFIG,
  'Lever': LEVER_CONFIG,
  'Workday': WORKDAY_CONFIG
};

// Make available globally for content scripts
if (typeof window !== 'undefined') {
  window.ATS_CONFIGS = ATS_CONFIGS;
}
