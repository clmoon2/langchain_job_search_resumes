/**
 * Content Script - Main Entry Point
 * 
 * This is injected into job application pages.
 * It coordinates all the other content script modules.
 */

(async function() {
  'use strict';

  console.log('[INFO] TailoredResume content script loaded');

  // Wait for DOM to be fully loaded
  if (document.readyState === 'loading') {
    await new Promise(resolve => {
      document.addEventListener('DOMContentLoaded', resolve);
    });
  }

  // Initialize the main controller
  const controller = new AutofillController();
  await controller.init();
})();

class AutofillController {
  constructor() {
    this.atsDetector = new ATSDetector();
    this.jobExtractor = new JobExtractor();
    this.resumeTailor = new ResumeTailor();
    this.formFiller = new FormFiller();
    this.fileUploader = new FileUploader();
    this.uiOverlay = new UIOverlay();
    
    this.currentATS = null;
    this.resumeData = null;
    this.jobDescription = null;
  }

  async init() {
    // Step 1: Detect which ATS we're on
    this.currentATS = this.atsDetector.detect();
    
    if (!this.currentATS) {
      console.log('[INFO] No supported ATS detected');
      return;
    }

    console.log('[OK] Detected ATS:', this.currentATS.name);

    // Check if this is a confirmation/success page
    if (this.atsDetector.isSubmittedPage(this.currentATS.config)) {
      console.log('[INFO] Application already submitted');
      return;
    }

    // Notify background script
    try {
      chrome.runtime.sendMessage({
        type: 'ATS_DETECTED',
        atsName: this.currentATS.name
      });
    } catch (error) {
      console.log('[WARN] Could not notify background:', error.message);
    }

    // Step 2: Check authentication status
    let authState;
    try {
      authState = await chrome.runtime.sendMessage({ type: 'GET_AUTH_STATE' });
    } catch (error) {
      console.log('[WARN] Could not get auth state:', error.message);
      authState = { isAuthenticated: false };
    }
    
    if (!authState.isAuthenticated) {
      console.log('[INFO] User not authenticated');
      this.uiOverlay.showAuthPrompt(() => {
        chrome.runtime.sendMessage({ type: 'OPEN_SIGNIN' });
      });
      return;
    }

    // Step 3: Load resume data from storage
    let response;
    try {
      response = await chrome.runtime.sendMessage({ type: 'GET_RESUME_DATA' });
    } catch (error) {
      console.log('[WARN] Could not get resume data:', error.message);
      response = { success: false };
    }
    
    if (!response.success || !response.data.resume) {
      console.log('[INFO] No resume loaded');
      this.uiOverlay.showNoResumeMessage();
      return;
    }

    this.resumeData = response.data;

    // Step 4: Show the autofill button
    this.uiOverlay.showAutofillButton(() => this.handleAutofill());

    // Step 5: Extract job description
    this.jobDescription = this.jobExtractor.extract(this.currentATS);
    
    if (this.jobDescription) {
      console.log('[INFO] Job:', this.jobDescription.title, '@', this.jobDescription.company);
    }
  }

  async handleAutofill() {
    console.log('');
    console.log('============================================================');
    console.log('STARTING AUTOFILL');
    console.log('============================================================');

    try {
      chrome.runtime.sendMessage({ type: 'AUTOFILL_STARTED' });

      // Step 1: Extract job description if not already done
      this.uiOverlay.showProgress('[1/4] Extracting job...');
      if (!this.jobDescription) {
        this.jobDescription = this.jobExtractor.extract(this.currentATS);
      }
      console.log('[OK] Job description extracted');

      // Step 2: Tailor resume for this job
      this.uiOverlay.showProgress('[2/4] Tailoring resume...');
      const tailoredData = this.resumeTailor.tailor(
        this.resumeData.resume,
        this.resumeData.profile,
        this.jobDescription
      );
      console.log('[OK] Resume tailored');

      // Step 3: Fill form fields
      this.uiOverlay.showProgress('[3/4] Filling form...');
      const fillResult = await this.formFiller.fill(this.currentATS, tailoredData);
      console.log(`[OK] Form filled: ${fillResult.filledCount} fields`);

      // Step 4: Upload resume file
      if (this.resumeData.resumeFile) {
        this.uiOverlay.showProgress('[4/4] Uploading resume...');
        const uploadSuccess = await this.fileUploader.upload(
          this.currentATS,
          this.resumeData.resumeFile,
          this.resumeData.resumeFileName
        );
        
        if (uploadSuccess) {
          console.log('[OK] Resume uploaded');
        } else {
          console.log('[WARN] Resume upload failed or skipped');
        }
      } else {
        console.log('[SKIP] No resume file to upload');
      }

      // Step 5: Track application
      await this.trackApplication();

      console.log('============================================================');
      console.log('AUTOFILL COMPLETE');
      console.log('============================================================');
      console.log('');

      this.uiOverlay.showSuccess('[OK] Autofill complete!');
      chrome.runtime.sendMessage({ type: 'AUTOFILL_COMPLETE', success: true });

    } catch (error) {
      console.log('============================================================');
      console.log('[ERROR] Autofill failed:', error.message);
      console.log('============================================================');
      
      this.uiOverlay.showError('[ERROR] ' + error.message);
      chrome.runtime.sendMessage({ type: 'AUTOFILL_COMPLETE', success: false });
    }
  }

  async trackApplication() {
    try {
      await chrome.runtime.sendMessage({
        type: 'TRACK_APPLICATION',
        data: {
          url: window.location.href,
          ats: this.currentATS.name,
          jobTitle: this.jobDescription?.title || '',
          company: this.jobDescription?.company || '',
          appliedAt: new Date().toISOString()
        }
      });
      console.log('[OK] Application tracked');
    } catch (error) {
      console.log('[WARN] Could not track application:', error.message);
    }
  }
}

// Make controller available globally for debugging
if (typeof window !== 'undefined') {
  window.AutofillController = AutofillController;
}
