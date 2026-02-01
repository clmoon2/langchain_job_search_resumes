/**
 * PDF Parser
 * 
 * Parses PDF resumes using PDF.js and extracts structured data.
 */

class PDFParser {
  constructor() {
    this.pdfjsLib = null;
  }

  /**
   * Initialize PDF.js library
   */
  async init() {
    if (this.pdfjsLib) return;
    
    if (typeof pdfjsLib !== 'undefined') {
      this.pdfjsLib = pdfjsLib;
      this.pdfjsLib.GlobalWorkerOptions.workerSrc = chrome.runtime.getURL('vendor/pdf.js/pdf.worker.min.js');
    } else {
      throw new Error('PDF.js library not loaded');
    }
  }

  /**
   * Parse a PDF file and extract text
   */
  async parseFile(file) {
    await this.init();
    
    const arrayBuffer = await file.arrayBuffer();
    const pdf = await this.pdfjsLib.getDocument({ data: arrayBuffer }).promise;
    
    let fullText = '';
    const pages = [];
    
    for (let i = 1; i <= pdf.numPages; i++) {
      const page = await pdf.getPage(i);
      const textContent = await page.getTextContent();
      const pageText = textContent.items.map(item => item.str).join(' ');
      pages.push(pageText);
      fullText += pageText + '\n';
    }
    
    const extractedData = this.extractResumeData(fullText);
    
    return {
      rawText: fullText,
      pages,
      ...extractedData
    };
  }

  /**
   * Extract structured data from resume text
   */
  extractResumeData(text) {
    return {
      contact: this.extractContactInfo(text),
      summary: this.extractSummary(text),
      experience: this.extractExperience(text),
      education: this.extractEducation(text),
      skills: this.extractSkills(text),
    };
  }

  /**
   * Extract contact information
   */
  extractContactInfo(text) {
    const contact = {
      fullName: '',
      firstName: '',
      lastName: '',
      email: '',
      phone: '',
      location: '',
      linkedin: '',
      github: '',
      portfolio: ''
    };

    // Extract email
    const emailMatch = text.match(/[\w.+-]+@[\w-]+\.[\w.-]+/i);
    if (emailMatch) {
      contact.email = emailMatch[0].toLowerCase();
    }

    // Extract phone - various formats
    const phonePatterns = [
      /\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}/,
      /\+1[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}/,
      /\d{3}[-.\s]\d{3}[-.\s]\d{4}/
    ];
    
    for (const pattern of phonePatterns) {
      const phoneMatch = text.match(pattern);
      if (phoneMatch) {
        contact.phone = phoneMatch[0];
        break;
      }
    }

    // Extract LinkedIn URL
    const linkedinMatch = text.match(/(?:https?:\/\/)?(?:www\.)?linkedin\.com\/in\/[\w-]+/i);
    if (linkedinMatch) {
      contact.linkedin = linkedinMatch[0].startsWith('http') 
        ? linkedinMatch[0] 
        : 'https://' + linkedinMatch[0];
    }

    // Extract GitHub URL
    const githubMatch = text.match(/(?:https?:\/\/)?(?:www\.)?github\.com\/[\w-]+/i);
    if (githubMatch) {
      contact.github = githubMatch[0].startsWith('http') 
        ? githubMatch[0] 
        : 'https://' + githubMatch[0];
    }

    // Extract name - typically first line or before contact info
    const lines = text.split('\n').filter(line => line.trim());
    if (lines.length > 0) {
      const firstLine = lines[0].trim();
      if (firstLine.length < 50 && !firstLine.includes('@') && !firstLine.match(/\d{3}/)) {
        contact.fullName = firstLine;
        const nameParts = firstLine.split(/\s+/);
        if (nameParts.length >= 2) {
          contact.firstName = nameParts[0];
          contact.lastName = nameParts[nameParts.length - 1];
        } else if (nameParts.length === 1) {
          contact.firstName = nameParts[0];
        }
      }
    }

    // Extract location - look for city, state pattern
    const locationMatch = text.match(/([A-Z][a-z]+(?:\s[A-Z][a-z]+)?),?\s*([A-Z]{2})\b/);
    if (locationMatch) {
      contact.location = `${locationMatch[1]}, ${locationMatch[2]}`;
    }

    return contact;
  }

  /**
   * Extract professional summary
   */
  extractSummary(text) {
    const summaryPatterns = [
      /(?:summary|objective|profile|about)\s*:?\s*\n?([\s\S]{50,500}?)(?=\n\s*(?:experience|education|skills|work|employment)|\n\n)/i
    ];

    for (const pattern of summaryPatterns) {
      const match = text.match(pattern);
      if (match && match[1]) {
        return match[1].trim().replace(/\s+/g, ' ');
      }
    }

    return '';
  }

  /**
   * Extract work experience
   */
  extractExperience(text) {
    const experiences = [];
    
    // Split text into sections
    const experienceSection = this.extractSection(text, 
      ['experience', 'work history', 'employment', 'professional experience', 'work experience'],
      ['education', 'skills', 'certifications', 'projects', 'awards']
    );

    if (!experienceSection) return experiences;

    // Match job entries
    const jobPattern = /([A-Z][A-Za-z\s&,.-]+?)\s*(?:at|@|-|,|\|)\s*([A-Z][A-Za-z\s&,.-]+?)\s*\n?\s*([A-Z][a-z]+\.?\s*\d{4})\s*[-–]\s*(Present|[A-Z][a-z]+\.?\s*\d{4})/gi;
    
    let match;
    while ((match = jobPattern.exec(experienceSection)) !== null) {
      const experience = {
        title: match[1].trim(),
        company: {
          name: match[2].trim(),
          location: ''
        },
        startDate: this.parseDate(match[3]),
        endDate: match[4].toLowerCase() === 'present' ? null : this.parseDate(match[4]),
        currentlyWorking: match[4].toLowerCase() === 'present',
        description: ''
      };

      // Extract description until next job entry or section
      const startIndex = match.index + match[0].length;
      const nextMatch = experienceSection.slice(startIndex).search(/[A-Z][A-Za-z\s&,.-]+\s*(?:at|@|-|,|\|)\s*[A-Z]/);
      
      if (nextMatch > 0) {
        experience.description = experienceSection.slice(startIndex, startIndex + nextMatch).trim();
      } else {
        experience.description = experienceSection.slice(startIndex, startIndex + 500).trim();
      }

      experiences.push(experience);
    }

    return experiences;
  }

  /**
   * Extract education
   */
  extractEducation(text) {
    const education = [];
    
    const educationSection = this.extractSection(text,
      ['education', 'academic', 'degrees'],
      ['experience', 'skills', 'work', 'employment', 'certifications']
    );

    if (!educationSection) return education;

    // Match education entries
    const degreePatterns = [
      /(?:Bachelor|Master|Ph\.?D\.?|B\.?S\.?|B\.?A\.?|M\.?S\.?|M\.?A\.?|M\.?B\.?A\.?|Associate)/i
    ];

    const lines = educationSection.split('\n');
    let currentEntry = null;

    for (const line of lines) {
      const trimmedLine = line.trim();
      if (!trimmedLine) continue;

      // Check for degree
      for (const pattern of degreePatterns) {
        if (pattern.test(trimmedLine)) {
          if (currentEntry) {
            education.push(currentEntry);
          }
          
          currentEntry = {
            school: '',
            degree: '',
            degreeCode: 0,
            major: '',
            gpa: '',
            startDate: null,
            endDate: null
          };

          currentEntry.degree = this.extractDegree(trimmedLine);
          currentEntry.degreeCode = this.getDegreeCode(currentEntry.degree);
          currentEntry.major = this.extractMajor(trimmedLine);
          break;
        }
      }

      // Check for school name
      if (currentEntry && !currentEntry.school) {
        const schoolMatch = trimmedLine.match(/(?:University|College|Institute|School)\s+(?:of\s+)?[A-Za-z\s]+/i);
        if (schoolMatch) {
          currentEntry.school = schoolMatch[0].trim();
        }
      }

      // Check for dates
      const dateMatch = trimmedLine.match(/(\d{4})\s*[-–]\s*(\d{4}|Present)/i);
      if (currentEntry && dateMatch) {
        currentEntry.startDate = { year: parseInt(dateMatch[1]), month: 1 };
        if (dateMatch[2].toLowerCase() !== 'present') {
          currentEntry.endDate = { year: parseInt(dateMatch[2]), month: 12 };
        }
      }

      // Check for GPA
      const gpaMatch = trimmedLine.match(/GPA:?\s*(\d\.\d+)/i);
      if (currentEntry && gpaMatch) {
        currentEntry.gpa = gpaMatch[1];
      }
    }

    if (currentEntry) {
      education.push(currentEntry);
    }

    return education;
  }

  /**
   * Extract skills
   */
  extractSkills(text) {
    const skillsSection = this.extractSection(text,
      ['skills', 'technical skills', 'technologies', 'competencies'],
      ['experience', 'education', 'certifications', 'projects']
    );

    if (!skillsSection) return [];

    // Common separators: comma, bullet, pipe, semicolon
    const skills = skillsSection
      .split(/[,;|•·]\s*|\n/)
      .map(s => s.trim())
      .filter(s => s.length > 1 && s.length < 50)
      .filter(s => !s.match(/^(skills|technical|competencies|technologies):?$/i));

    return [...new Set(skills)];
  }

  /**
   * Extract a section from text
   */
  extractSection(text, startKeywords, endKeywords) {
    const lowerText = text.toLowerCase();
    
    let startIndex = -1;
    for (const keyword of startKeywords) {
      const index = lowerText.indexOf(keyword);
      if (index !== -1 && (startIndex === -1 || index < startIndex)) {
        startIndex = index;
      }
    }

    if (startIndex === -1) return null;

    let endIndex = text.length;
    for (const keyword of endKeywords) {
      const index = lowerText.indexOf(keyword, startIndex + 20);
      if (index !== -1 && index < endIndex) {
        endIndex = index;
      }
    }

    return text.slice(startIndex, endIndex);
  }

  /**
   * Parse a date string
   */
  parseDate(dateStr) {
    const months = {
      'jan': 1, 'january': 1,
      'feb': 2, 'february': 2,
      'mar': 3, 'march': 3,
      'apr': 4, 'april': 4,
      'may': 5,
      'jun': 6, 'june': 6,
      'jul': 7, 'july': 7,
      'aug': 8, 'august': 8,
      'sep': 9, 'sept': 9, 'september': 9,
      'oct': 10, 'october': 10,
      'nov': 11, 'november': 11,
      'dec': 12, 'december': 12
    };

    const parts = dateStr.toLowerCase().match(/([a-z]+)\.?\s*(\d{4})/);
    if (parts) {
      const month = months[parts[1]] || 1;
      const year = parseInt(parts[2]);
      return { month, year };
    }

    const yearOnly = dateStr.match(/(\d{4})/);
    if (yearOnly) {
      return { month: 1, year: parseInt(yearOnly[1]) };
    }

    return null;
  }

  /**
   * Extract degree name from text
   */
  extractDegree(text) {
    const degreePatterns = [
      { pattern: /Ph\.?D\.?/i, name: 'Doctor of Philosophy' },
      { pattern: /M\.?B\.?A\.?/i, name: 'Master of Business Administration' },
      { pattern: /M\.?S\.?/i, name: 'Master of Science' },
      { pattern: /M\.?A\.?/i, name: 'Master of Arts' },
      { pattern: /Master/i, name: 'Master' },
      { pattern: /B\.?S\.?/i, name: 'Bachelor of Science' },
      { pattern: /B\.?A\.?/i, name: 'Bachelor of Arts' },
      { pattern: /Bachelor/i, name: 'Bachelor' },
      { pattern: /Associate/i, name: 'Associate' }
    ];

    for (const { pattern, name } of degreePatterns) {
      if (pattern.test(text)) {
        return name;
      }
    }

    return '';
  }

  /**
   * Get degree code from degree name
   */
  getDegreeCode(degree) {
    const degreeLower = degree.toLowerCase();
    
    if (degreeLower.includes('phd') || degreeLower.includes('doctor')) return 5;
    if (degreeLower.includes('master') || degreeLower.includes('mba')) return 4;
    if (degreeLower.includes('bachelor')) return 3;
    if (degreeLower.includes('associate')) return 2;
    if (degreeLower.includes('high school')) return 1;
    
    return 0;
  }

  /**
   * Extract major from text
   */
  extractMajor(text) {
    const majorMatch = text.match(/(?:in|of)\s+([A-Za-z\s]+?)(?:\s*,|\s*$|\s*\d)/i);
    if (majorMatch) {
      return majorMatch[1].trim();
    }
    return '';
  }
}

// Make available globally
if (typeof window !== 'undefined') {
  window.PDFParser = PDFParser;
}
