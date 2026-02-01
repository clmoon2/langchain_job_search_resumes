#!/bin/bash
# Install systemd timer for email outreach
# Run with: sudo bash install.sh

set -e

echo "Installing email outreach systemd timer..."

# Copy service and timer files
sudo cp email-outreach.service /etc/systemd/system/
sudo cp email-outreach.timer /etc/systemd/system/

# Set correct permissions
sudo chmod 644 /etc/systemd/system/email-outreach.service
sudo chmod 644 /etc/systemd/system/email-outreach.timer

# Reload systemd
sudo systemctl daemon-reload

# Enable the timer (starts on boot)
sudo systemctl enable email-outreach.timer

# Start the timer now
sudo systemctl start email-outreach.timer

echo ""
echo "Installation complete!"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status email-outreach.timer  # Check timer status"
echo "  sudo systemctl list-timers                  # List all timers"
echo "  sudo systemctl start email-outreach.service # Run manually now"
echo "  journalctl -u email-outreach.service        # View logs"
echo "  tail -f /home/carlu/langchain_job_search_resumes/email_outreach.log"
echo ""
echo "To set timezone to Chicago:"
echo "  sudo timedatectl set-timezone America/Chicago"
