/**
 * Drop Zone Component
 * 
 * Handles drag & drop and file selection for resume uploads.
 */

class DropZone {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.dropZone = this.container?.querySelector('.drop-zone');
    this.fileInput = this.container?.querySelector('#file-input');
    this.onFileSelected = null;

    this.init();
  }

  init() {
    if (!this.dropZone || !this.fileInput) {
      console.log('[WARN] Drop zone elements not found');
      return;
    }

    // Click to select file
    this.dropZone.addEventListener('click', () => {
      this.fileInput.click();
    });

    // File input change
    this.fileInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (file) {
        this.handleFile(file);
      }
    });

    // Drag events
    this.dropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.stopPropagation();
      this.dropZone.classList.add('drop-zone--active');
    });

    this.dropZone.addEventListener('dragleave', (e) => {
      e.preventDefault();
      e.stopPropagation();
      this.dropZone.classList.remove('drop-zone--active');
    });

    this.dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      e.stopPropagation();
      this.dropZone.classList.remove('drop-zone--active');

      const files = e.dataTransfer.files;
      if (files.length > 0) {
        this.handleFile(files[0]);
      }
    });
  }

  handleFile(file) {
    // Validate file type
    if (!file.type.includes('pdf')) {
      this.showError('Please select a PDF file');
      return;
    }

    // Validate file size (max 10MB)
    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
      this.showError('File size must be less than 10MB');
      return;
    }

    console.log('[INFO] File selected:', file.name);

    if (this.onFileSelected) {
      this.onFileSelected(file);
    }
  }

  showError(message) {
    console.log('[ERROR]', message);
    
    // Show temporary error message
    const originalText = this.dropZone.querySelector('.drop-zone__text').textContent;
    const textEl = this.dropZone.querySelector('.drop-zone__text');
    
    textEl.textContent = message;
    textEl.style.color = '#F44336';

    setTimeout(() => {
      textEl.textContent = originalText;
      textEl.style.color = '';
    }, 3000);
  }

  show() {
    this.container?.classList.remove('hidden');
  }

  hide() {
    this.container?.classList.add('hidden');
  }

  setLoading(loading) {
    if (loading) {
      this.dropZone?.classList.add('loading');
      const textEl = this.dropZone?.querySelector('.drop-zone__text');
      if (textEl) {
        textEl.textContent = 'Parsing resume...';
      }
    } else {
      this.dropZone?.classList.remove('loading');
      const textEl = this.dropZone?.querySelector('.drop-zone__text');
      if (textEl) {
        textEl.textContent = 'Drop your resume here';
      }
    }
  }
}
