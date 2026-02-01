/**
 * Status Indicator Component
 * 
 * Shows connection/authentication status in the header.
 */

class StatusIndicator {
  constructor(elementId) {
    this.element = document.getElementById(elementId);
  }

  setConnected() {
    if (!this.element) return;
    
    this.element.textContent = 'Connected';
    this.element.className = 'status status--connected';
  }

  setDisconnected() {
    if (!this.element) return;
    
    this.element.textContent = 'Not signed in';
    this.element.className = 'status status--disconnected';
  }

  setLoading() {
    if (!this.element) return;
    
    this.element.textContent = 'Loading...';
    this.element.className = 'status';
  }

  setError(message = 'Error') {
    if (!this.element) return;
    
    this.element.textContent = message;
    this.element.className = 'status status--disconnected';
  }

  setCustom(text, className = '') {
    if (!this.element) return;
    
    this.element.textContent = text;
    this.element.className = `status ${className}`;
  }
}
