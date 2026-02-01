/**
 * Resume Tailor
 * 
 * Tailors resume data for a specific job description.
 * This is where local processing happens to customize the resume
 * for each job application.
 */

class ResumeTailor {
  constructor() {
    this.jobKeywords = [];
  }

  /**
   * Tailor resume data for a specific job
   */
  tailor(resume, profile, jobDescription) {
    console.log('[INFO] Tailoring resume for job');

    if (!resume || !resume.contact) {
      console.log('[WARN] No resume data to tailor');
      return this.getDefaultProfile(profile);
    }

    // Extract keywords from job description
    this.jobKeywords = this.extractKeywords(jobDescription?.description || '');

    // Build tailored data combining resume and profile
    const tailored = {
      // Contact information - prefer profile over resume
      firstName: profile?.firstName || resume.contact.firstName || '',
      lastName: profile?.lastName || resume.contact.lastName || '',
      fullName: profile?.firstName && profile?.lastName 
        ? `${profile.firstName} ${profile.lastName}`
        : resume.contact.fullName || '',
      email: profile?.email || resume.contact.email || '',
      phone: profile?.phone || resume.contact.phone || '',
      phoneStripped: this.stripPhone(profile?.phone || resume.contact.phone || ''),
      location: profile?.location || resume.contact.location || '',
      linkedin: profile?.linkedin || resume.contact.linkedin || '',
      github: profile?.github || resume.contact.github || '',
      portfolio: profile?.portfolio || resume.contact.portfolio || '',

      // Parse location components
      ...this.parseLocation(profile?.location || resume.contact.location || ''),

      // Professional summary - tailored if possible
      summary: this.tailorSummary(resume.summary, jobDescription),

      // Experience - prioritized by relevance
      experience: this.prioritizeExperience(resume.experience, jobDescription),

      // Education
      education: resume.education || [],

      // Skills - prioritized by relevance
      skills: this.prioritizeSkills(resume.skills, jobDescription),

      // Work authorization (from profile)
      authorizedToWork: profile?.authorizedToWork,
      requiresSponsorship: profile?.requiresSponsorship,

      // EEO data (from profile)
      gender: profile?.gender,
      ethnicity: profile?.ethnicity,
      veteran: profile?.veteran,
      disability: profile?.disability
    };

    console.log('[OK] Resume tailored');
    return tailored;
  }

  /**
   * Get default profile when no resume is loaded
   */
  getDefaultProfile(profile) {
    return {
      firstName: profile?.firstName || '',
      lastName: profile?.lastName || '',
      fullName: profile?.firstName && profile?.lastName 
        ? `${profile.firstName} ${profile.lastName}`
        : '',
      email: profile?.email || '',
      phone: profile?.phone || '',
      phoneStripped: this.stripPhone(profile?.phone || ''),
      location: profile?.location || '',
      linkedin: profile?.linkedin || '',
      github: profile?.github || '',
      portfolio: profile?.portfolio || '',
      ...this.parseLocation(profile?.location || ''),
      summary: '',
      experience: [],
      education: [],
      skills: []
    };
  }

  /**
   * Extract keywords from job description
   */
  extractKeywords(description) {
    if (!description) return [];

    const text = description.toLowerCase();
    const words = text.split(/\W+/);
    
    // Count word frequencies
    const frequency = {};
    for (const word of words) {
      if (word.length > 3) {
        frequency[word] = (frequency[word] || 0) + 1;
      }
    }

    // Filter for meaningful keywords
    const stopWords = new Set([
      'the', 'and', 'for', 'with', 'you', 'your', 'will', 'have', 'are',
      'our', 'this', 'that', 'from', 'they', 'been', 'more', 'when',
      'what', 'about', 'which', 'their', 'work', 'team', 'also'
    ]);

    const keywords = Object.entries(frequency)
      .filter(([word]) => !stopWords.has(word))
      .sort((a, b) => b[1] - a[1])
      .slice(0, 50)
      .map(([word]) => word);

    return keywords;
  }

  /**
   * Tailor summary to highlight relevant experience
   */
  tailorSummary(summary, jobDescription) {
    if (!summary) return '';

    // For now, return original summary
    // Future: use NLP to rewrite summary highlighting relevant skills
    return summary;
  }

  /**
   * Prioritize experience entries based on relevance to job
   */
  prioritizeExperience(experience, jobDescription) {
    if (!experience || !experience.length) return [];
    if (!jobDescription?.description) return experience;

    // Score each experience entry
    const scored = experience.map(exp => ({
      ...exp,
      score: this.scoreRelevance(
        `${exp.title} ${exp.description}`.toLowerCase(),
        this.jobKeywords
      )
    }));

    // Sort by score (descending) while maintaining some chronological order
    scored.sort((a, b) => {
      const scoreDiff = b.score - a.score;
      if (Math.abs(scoreDiff) > 5) return scoreDiff;
      
      // If scores are similar, prefer more recent experience
      const dateA = a.startDate?.year || 0;
      const dateB = b.startDate?.year || 0;
      return dateB - dateA;
    });

    return scored;
  }

  /**
   * Prioritize skills based on relevance to job
   */
  prioritizeSkills(skills, jobDescription) {
    if (!skills || !skills.length) return [];
    if (!jobDescription?.description) return skills;

    const jobText = jobDescription.description.toLowerCase();

    // Score each skill
    const scored = skills.map(skill => ({
      skill,
      score: jobText.includes(skill.toLowerCase()) ? 10 : 0
    }));

    // Sort by score (matching skills first)
    scored.sort((a, b) => b.score - a.score);

    return scored.map(s => s.skill);
  }

  /**
   * Score relevance of text to job keywords
   */
  scoreRelevance(text, keywords) {
    let score = 0;
    for (const keyword of keywords) {
      if (text.includes(keyword)) {
        score += 1;
      }
    }
    return score;
  }

  /**
   * Strip phone number to digits only
   */
  stripPhone(phone) {
    if (!phone) return '';
    return phone.replace(/\D/g, '');
  }

  /**
   * Parse location into components
   */
  parseLocation(location) {
    if (!location) {
      return {
        city: '',
        state: '',
        country: '',
        postalCode: '',
        address: ''
      };
    }

    const parts = location.split(',').map(p => p.trim());

    // Try to identify city, state, country
    let city = '', state = '', country = '', postalCode = '';

    if (parts.length >= 2) {
      city = parts[0];
      
      // Check if second part is a state abbreviation
      const statePart = parts[1].trim();
      const stateMatch = statePart.match(/^([A-Z]{2})(?:\s+(\d{5}))?$/);
      
      if (stateMatch) {
        state = stateMatch[1];
        postalCode = stateMatch[2] || '';
      } else {
        state = statePart;
      }
    } else if (parts.length === 1) {
      city = parts[0];
    }

    // Check for country
    if (parts.length >= 3) {
      country = parts[2];
    }

    return {
      city,
      state,
      country,
      postalCode,
      address: location
    };
  }

  /**
   * Get formatted experience description
   */
  formatExperience(experience) {
    if (!experience) return '';

    const lines = [];
    for (const exp of experience) {
      const dateRange = this.formatDateRange(exp.startDate, exp.endDate, exp.currentlyWorking);
      lines.push(`${exp.title} at ${exp.company?.name} (${dateRange})`);
      if (exp.description) {
        lines.push(exp.description);
      }
      lines.push('');
    }

    return lines.join('\n').trim();
  }

  /**
   * Format date range
   */
  formatDateRange(startDate, endDate, currentlyWorking) {
    const formatDate = (date) => {
      if (!date) return '';
      const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      const month = date.month ? months[date.month - 1] : '';
      return `${month} ${date.year}`.trim();
    };

    const start = formatDate(startDate);
    const end = currentlyWorking ? 'Present' : formatDate(endDate);

    if (start && end) {
      return `${start} - ${end}`;
    } else if (start) {
      return `${start} - Present`;
    }

    return '';
  }
}

// Make available globally
if (typeof window !== 'undefined') {
  window.ResumeTailor = ResumeTailor;
}
