/**
 * Resume Preview Component
 * 
 * Displays a summary of the loaded resume data.
 */

class ResumePreview {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.nameEl = document.getElementById('preview-name');
    this.emailEl = document.getElementById('preview-email');
    this.phoneEl = document.getElementById('preview-phone');
    this.experienceCountEl = document.getElementById('preview-experience-count');
    this.educationCountEl = document.getElementById('preview-education-count');
  }

  update(resume) {
    if (!resume) {
      this.clear();
      return;
    }

    // Update contact info
    if (resume.contact) {
      this.nameEl.textContent = resume.contact.fullName || '-';
      this.emailEl.textContent = resume.contact.email || '-';
      this.phoneEl.textContent = resume.contact.phone || '-';
    }

    // Update counts
    const experienceCount = resume.experience?.length || 0;
    const educationCount = resume.education?.length || 0;
    
    this.experienceCountEl.textContent = `${experienceCount} position${experienceCount !== 1 ? 's' : ''}`;
    this.educationCountEl.textContent = `${educationCount} entr${educationCount !== 1 ? 'ies' : 'y'}`;
  }

  clear() {
    this.nameEl.textContent = '-';
    this.emailEl.textContent = '-';
    this.phoneEl.textContent = '-';
    this.experienceCountEl.textContent = '0 positions';
    this.educationCountEl.textContent = '0 entries';
  }

  show() {
    this.container?.classList.remove('hidden');
  }

  hide() {
    this.container?.classList.add('hidden');
  }
}
