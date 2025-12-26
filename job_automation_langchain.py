"""
Job Application Automation Pipeline - LangChain Implementation
==============================================================

This is a complete recreation of the n8n workflow in Python using LangChain.

Workflow Steps:
1. Read already-applied jobs from Google Sheets
2. Get resume template from Google Docs
3. Scrape LinkedIn jobs via Apify
4. Filter out already-applied jobs (deduplication)
5. AI-filter jobs for fit (GPT-4.1-mini)
6. Generate tailored LaTeX resume (GPT-4o)
7. Upload to GitHub (triggers GitHub Actions for PDF compilation)
8. Create Google Slides presentation page
9. Find decision-maker email (AnyMailFinder)
10. Append results to Google Sheets
11. Loop for all jobs

Author: Carlos Luna-Peña
"""

import os
import json
import base64
import re
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import asyncio
from dotenv import load_dotenv

# LangChain imports
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain.callbacks import get_openai_callback

# External API clients
import requests
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from urllib.parse import urlparse

# For async operations
import aiohttp
import asyncio


# =============================================================================
# CONFIGURATION
# =============================================================================

load_dotenv()

@dataclass
class Config:
    """Configuration for all API keys and IDs (env-only)."""
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # Apify
    APIFY_API_KEY: str = os.getenv("APIFY_API_KEY", "")
    APIFY_ACTOR_ID: str = os.getenv("APIFY_ACTOR_ID", "hKByXkMQaC5Qt9UMN")
    
    # GitHub
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_REPO: str = os.getenv("GITHUB_REPO", "clmoon2/resumes")
    
    # Google (service account JSON provided via env string)
    GOOGLE_SERVICE_ACCOUNT_JSON: str = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    GOOGLE_SHEETS_ID: str = os.getenv("GOOGLE_SHEETS_ID", "1HVaAPN3KYSILOZ0soHIZQG8dAP6lWFewQ-woltg4YUE")
    GOOGLE_DOCS_ID: str = os.getenv("GOOGLE_DOCS_ID", "16ngTeKOIZtOB_041Wcr0AwKec2f-1WBBgeEabAgnYr0")
    GOOGLE_SLIDES_ID: str = os.getenv("GOOGLE_SLIDES_ID", "1ryNtxMWdDvYhAftE-udf0ECqGNHFYjgevapbi9gcPdY")
    
    # AnyMailFinder
    ANYMAILFINDER_API_KEY: str = os.getenv("ANYMAILFINDER_API_KEY", "")
    
    # LinkedIn Search URL
    LINKEDIN_SEARCH_URL: str = os.getenv(
        "LINKEDIN_SEARCH_URL",
        "https://www.linkedin.com/jobs/search-results/?keywords=software%20internships%20posted%20in%20the%20past%20week"
    )
    
    # Candidate info
    CANDIDATE_NAME: str = os.getenv("CANDIDATE_NAME", "Carlos Luna-Peña")
    
    # Timing / retries
    WAIT_FOR_PDF_SECONDS: int = int(os.getenv("WAIT_FOR_PDF_SECONDS", str(6 * 60)))
    REQUEST_TIMEOUT_SECONDS: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "45"))
    REQUEST_RETRIES: int = int(os.getenv("REQUEST_RETRIES", "3"))
    REQUEST_RETRY_BACKOFF: int = int(os.getenv("REQUEST_RETRY_BACKOFF", "2"))


config = Config()


# =============================================================================
# PROMPTS
# =============================================================================

JOB_FILTER_SYSTEM_PROMPT = """You are a strict job filter for ONE candidate.
Decide if a job is a reasonable fit for this candidate.
Output ONLY compact JSON: {"verdict":"true"} or {"verdict":"false"}.
"""

JOB_FILTER_USER_PROMPT = """CANDIDATE SUMMARY
- CS student @ Texas A&M, looking for SWE / Backend / Full-Stack / AI-Automation / Systems internships.
- Skills: TypeScript, Java, Python, C/C++, SQL.
- Web: React, Next.js, Node.js/Express, FastAPI, Tailwind, REST APIs, JSON.
- Data/DB: PostgreSQL (schema, indexing, query tuning), SQLite.
- DevOps: Docker, Git/GitHub, GitHub Actions (CI), Linux, Bash.
- Auth/Security: OAuth2/Google OAuth, secure cookies, CORS, basic RBAC, rate limiting.
- AI/Automation: PyTorch (image tagging/embeddings), LangChain, OpenAI API, n8n, Apify, Google APIs (Slides/Sheets/Gmail), basic recommendation systems.
- Systems: Linux processes, fork/execvp, pipes, dup2, waitpid, non-blocking I/O, background jobs.

FIT CRITERIA
Return "true" **only if ALL** of these are met:
1) Role is software / ML / AI / platform / systems engineering (not sales, finance, IT support, hardware-only, etc.).
2) Level is intern 
3) At least ~50% of the main tech stack overlaps with the skills above.

Otherwise return "false".

JOB DESCRIPTION (JSON or text)
{job_description}

Respond ONLY with:
{{"verdict":"true"}}
or
{{"verdict":"false"}}
"""

RESUME_SYSTEM_PROMPT = """You are an expert ATS-optimized resume generator using Jake Gutierrez's sb2nov LaTeX template.

YOUR PRIMARY GOAL: Maximize keyword match rate to pass Applicant Tracking Systems while maintaining natural, compelling content.

═══════════════════════════════════════════════════════════════
KEYWORD OPTIMIZATION RULES (HIGHEST PRIORITY)
═══════════════════════════════════════════════════════════════

1. EXTRACT & MATCH KEYWORDS
   - Identify ALL technical skills, tools, frameworks, and technologies from the job description
   - Identify soft skills and action verbs the employer emphasizes
   - Match these EXACTLY as written (e.g., if job says "React.js", use "React.js" not just "React")
   - Include both acronyms AND full forms when space permits (e.g., "CI/CD (Continuous Integration/Continuous Deployment)")

2. KEYWORD PLACEMENT STRATEGY
   - Technical Skills section: List ALL matching technologies from job description FIRST
   - Each bullet point: Include 1-2 relevant keywords naturally
   - Professional summary: Front-load with 3-5 highest-priority keywords from job posting
   - Section headers: Use EXACT section names common in ATS (Education, Experience, Projects, Technical Skills)

3. KEYWORD DENSITY
   - Repeat critical keywords 2-3 times across different sections (naturally, not stuffed)
   - Primary technologies from job description should appear in BOTH skills section AND experience bullets
   - Mirror the job description's language patterns (if they say "collaborate" don't say "work together")

4. KEYWORD CATEGORIES TO EXTRACT FROM JOB DESCRIPTION:
   - Programming languages (Python, Java, JavaScript, etc.)
   - Frameworks/Libraries (React, Django, Spring Boot, etc.)
   - Tools/Platforms (AWS, Docker, Kubernetes, Git, etc.)
   - Databases (PostgreSQL, MongoDB, Redis, etc.)
   - Methodologies (Agile, Scrum, CI/CD, TDD, etc.)
   - Soft skills (leadership, collaboration, communication, etc.)
   - Domain-specific terms (fintech, healthcare, e-commerce, etc.)
   - Seniority signals (intern, entry-level, new grad, junior, etc.)

5. BULLET POINT FORMULA
   [Action Verb] + [Task with Keywords] + [Quantified Result] + [Technology/Tool Used]
   Example: "Developed RESTful APIs using Python and FastAPI, reducing response latency by 40% and serving 10K+ daily requests"

═══════════════════════════════════════════════════════════════
LATEX VALIDATION RULES (CRITICAL - VIOLATIONS CAUSE FAILURE)
═══════════════════════════════════════════════════════════════

1. NEVER use placeholder values like {X}, {Y}, [NUMBER], {PLACEHOLDER}
   - Always use specific realistic numbers: "reduced latency by 35%", "improved throughput by 2.5x"
   
2. BRACE MATCHING (COUNT CAREFULLY):
   - Every { must have a matching }
   - Every \\resumeItem{ must close with } before \\resumeItemListEnd
   - Every \\begin{} must have \\end{}

3. ESCAPE SPECIAL CHARACTERS IN TEXT:
   & → \\&  |  % → \\%  |  $ → \\$  |  # → \\#  |  _ → \\_
   (Do NOT escape LaTeX syntax characters)

4. OUTPUT FORMAT:
   - FIRST character: \\ (backslash of \\documentclass)
   - LAST characters: \\end{document}
   - NO markdown, NO code fences, NO commentary

═══════════════════════════════════════════════════════════════
CONTENT RULES
═══════════════════════════════════════════════════════════════

- Follow CONTROL instructions from builder exactly
- Do NOT include CONTROL block in output
- ONE page maximum (respect bullet caps in CONTROL)
- Do NOT invent employers, degrees, or experiences
- Rephrase existing bullets to incorporate job-specific keywords
- Prioritize experiences/projects most relevant to target role

BEFORE OUTPUTTING, VERIFY:
□ All major keywords from job description appear at least once
□ Technical skills section lists technologies in order of job relevance
□ All \\resumeItem{} properly closed
□ All braces balanced
□ No placeholders remain
□ Ends with \\end{document}"""

RESUME_USER_PROMPT = """Generate an ATS-optimized LaTeX resume tailored for this specific job.

═══════════════════════════════════════════════════════════════
KEYWORD EXTRACTION TASK (DO THIS FIRST)
═══════════════════════════════════════════════════════════════

Before writing the resume, extract from the job description:

1. REQUIRED TECHNICAL SKILLS: List every programming language, framework, tool, database, and platform mentioned
2. PREFERRED/BONUS SKILLS: Technologies that are "nice to have"
3. ACTION VERBS: Verbs the employer uses (develop, design, collaborate, lead, etc.)
4. DOMAIN KEYWORDS: Industry-specific terms (fintech, SaaS, microservices, etc.)
5. SOFT SKILLS: Communication, teamwork, leadership phrases

Then ensure EVERY required skill that exists in my background appears in the resume, using the EXACT terminology from the job posting.

═══════════════════════════════════════════════════════════════
INPUT DATA
═══════════════════════════════════════════════════════════════

JOB DESCRIPTION (extract keywords from this):
{job_description}

RESUME BUILDER HELPER (my background data + template):
{resume_template}

═══════════════════════════════════════════════════════════════
OUTPUT REQUIREMENTS
═══════════════════════════════════════════════════════════════

- Output ONLY valid LaTeX code
- First character must be: \\
- Last characters must be: \\end{{document}}
- No markdown, no explanations, no code fences
- Pure LaTeX only

BEGIN GENERATING THE ATS-OPTIMIZED RESUME NOW:"""


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def slugify(text: str) -> str:
    """Convert text to URL-safe slug"""
    if not text:
        return "na"
    text = re.sub(r'[\r\n\t]', '', text)
    text = text.strip().lower()
    text = re.sub(r'\s+', '-', text)
    text = re.sub(r'[^a-z0-9-]', '', text)
    text = re.sub(r'-+', '-', text)
    text = re.sub(r'^-+|-+$', '', text)
    return text or "na"


def clean_string(text: str) -> str:
    """Remove newlines and extra whitespace"""
    if not text:
        return ""
    return re.sub(r'[\r\n\t]', '', str(text)).strip()


def clean_latex(raw: str) -> str:
    """Clean LaTeX output from LLM"""
    # Remove markdown code fences
    raw = re.sub(r'```latex\s*', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'```tex\s*', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'```\s*', '', raw)
    raw = raw.replace('`', '')
    raw = raw.strip()
    
    # Find documentclass
    doc_class_idx = raw.find('\\documentclass')
    if doc_class_idx > 0:
        raw = raw[doc_class_idx:]
    
    # Ensure proper ending
    if not raw.endswith('\\end{document}'):
        end_doc_idx = raw.rfind('\\end{document}')
        if end_doc_idx > 0:
            raw = raw[:end_doc_idx + 14]
        else:
            raw = raw + '\n\\end{document}'
    
    # Remove trailing whitespace
    return raw.rstrip()


def make_credentials(scopes: List[str]) -> Credentials:
    """Create service account credentials from env-provided JSON."""
    if not config.GOOGLE_SERVICE_ACCOUNT_JSON:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON is required for Google API access")
    try:
        info = json.loads(config.GOOGLE_SERVICE_ACCOUNT_JSON)
    except json.JSONDecodeError as e:
        raise ValueError("Invalid GOOGLE_SERVICE_ACCOUNT_JSON") from e
    return service_account.Credentials.from_service_account_info(info, scopes=scopes)


def request_with_retries(method: str, url: str, *, retries: int = None, timeout: int = None, backoff: int = None, **kwargs):
    """HTTP helper with retries and backoff."""
    retries = retries if retries is not None else config.REQUEST_RETRIES
    timeout = timeout if timeout is not None else config.REQUEST_TIMEOUT_SECONDS
    backoff = backoff if backoff is not None else config.REQUEST_RETRY_BACKOFF
    
    last_exc = None
    for attempt in range(retries):
        try:
            resp = requests.request(method, url, timeout=timeout, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            last_exc = e
            if attempt == retries - 1:
                break
            time.sleep(backoff * (attempt + 1))
    raise last_exc


def build_job_key(job: Dict) -> str:
    """Build a stable dedup key for a job."""
    parts = [
        job.get('id', ''),
        job.get('companyName', ''),
        job.get('title', ''),
        job.get('postedAt', ''),
        job.get('link', '') or job.get('applyUrl', '')
    ]
    combined = "-".join([clean_string(str(p)) for p in parts if p])
    key = slugify(combined)
    return key or "na"


def extract_domain(url_or_domain: str) -> str:
    """Normalize a company website to a bare domain for email lookup."""
    if not url_or_domain:
        return ""
    parsed = urlparse(url_or_domain if "://" in url_or_domain else f"http://{url_or_domain}")
    hostname = parsed.hostname or ""
    hostname = hostname.lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return hostname


def generate_file_path(company_name: str, title: str, posted_at: str = None) -> str:
    """Generate the file path for the resume"""
    company_slug = slugify(company_name) or "unknown-company"
    title_slug = slugify(title) or "unknown-position"
    
    if posted_at:
        date_part = re.sub(r'[^0-9]', '', posted_at)
    else:
        date_part = datetime.now().strftime('%Y%m%d')
    
    # Add timestamp for uniqueness
    timestamp = int(time.time())
    filename = f"carlos-luna-pena-{company_slug}-{title_slug}-{date_part}-{timestamp}.tex"
    return f"resumes/tex/{filename}"


def validate_required_config() -> None:
    """Fail fast if critical environment configuration is missing."""
    required = {
        "OPENAI_API_KEY": config.OPENAI_API_KEY,
        "APIFY_API_KEY": config.APIFY_API_KEY,
        "GITHUB_TOKEN": config.GITHUB_TOKEN,
        "GOOGLE_SERVICE_ACCOUNT_JSON": config.GOOGLE_SERVICE_ACCOUNT_JSON,
        "GOOGLE_SHEETS_ID": config.GOOGLE_SHEETS_ID,
        "GOOGLE_DOCS_ID": config.GOOGLE_DOCS_ID,
        "GOOGLE_SLIDES_ID": config.GOOGLE_SLIDES_ID,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError(f"Missing required configuration values: {', '.join(missing)}")
    if not config.ANYMAILFINDER_API_KEY:
        print("⚠️ ANYMAILFINDER_API_KEY not set; decision-maker email lookup may be skipped.")


def format_salary_info(salary_info: Any) -> str:
    """Return a safe, human-readable salary string from varied Apify payloads."""
    if not salary_info:
        return "Not specified"
    
    # Handle lists or tuples by taking the first usable entry
    if isinstance(salary_info, (list, tuple)):
        for entry in salary_info:
            formatted = format_salary_info(entry)
            if formatted != "Not specified":
                return formatted
        return "Not specified"
    
    # Handle dict structures with common fields
    if isinstance(salary_info, dict):
        for key in ("displayValue", "value", "label", "text"):
            if salary_info.get(key):
                return clean_string(str(salary_info[key]))
        
        low = salary_info.get("min") or salary_info.get("from") or salary_info.get("low")
        high = salary_info.get("max") or salary_info.get("to") or salary_info.get("high")
        currency = salary_info.get("currency") or salary_info.get("curr")
        period = salary_info.get("period") or salary_info.get("unit")
        
        parts = []
        if currency:
            parts.append(str(currency))
        if low or high:
            if low and high:
                parts.append(f"{low}-{high}")
            elif low:
                parts.append(str(low))
            else:
                parts.append(str(high))
        if period:
            parts.append(str(period))
        
        if parts:
            return clean_string(" ".join(parts))
        return "Not specified"
    
    # Fallback for strings or other primitives
    return clean_string(str(salary_info)) or "Not specified"


def validate_latex_output(latex: str) -> bool:
    """Basic validation to avoid uploading clearly invalid LaTeX."""
    if not latex:
        return False
    if "\\documentclass" not in latex or "\\end{document}" not in latex:
        return False
    if len(latex) < 200:  # heuristic guardrail
        return False
    return True


def wait_for_pdf_ready(pdf_url: str, wait_seconds: int) -> bool:
    """Poll for PDF availability with shorter intervals instead of one long sleep."""
    if not pdf_url:
        return False
    
    deadline = time.time() + wait_seconds
    interval = max(5, min(30, wait_seconds // 6 or 5))
    
    while time.time() < deadline:
        try:
            head_resp = request_with_retries(
                "HEAD",
                pdf_url,
                timeout=max(config.REQUEST_TIMEOUT_SECONDS, 60),
                retries=1
            )
            if head_resp.status_code < 400:
                return True
        except requests.RequestException:
            pass
        time.sleep(interval)
    
    return False


# =============================================================================
# API CLIENTS
# =============================================================================

class GoogleSheetsClient:
    """Client for Google Sheets operations"""
    
    def __init__(self):
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        self.creds = make_credentials(scopes)
        self.service = build('sheets', 'v4', credentials=self.creds)
    
    def get_headers(self, spreadsheet_id: str, sheet_name: str = "Sheet1") -> List[str]:
        """Fetch header row to align appends."""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!1:1"
            ).execute(num_retries=2)
            values = result.get('values', [])
            if not values:
                return []
            return values[0]
        except HttpError as e:
            print(f"Error reading headers: {e}")
            return []
    
    def read_sheet(self, spreadsheet_id: str, range_name: str = "A:J") -> List[Dict]:
        """Read all rows from a sheet"""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute(num_retries=2)
            
            values = result.get('values', [])
            if not values:
                return []
            
            headers = values[0]
            rows = []
            for row in values[1:]:
                row_dict = {}
                for i, header in enumerate(headers):
                    row_dict[header] = row[i] if i < len(row) else ""
                rows.append(row_dict)
            return rows
        except HttpError as e:
            print(f"Error reading sheet: {e}")
            return []
    
    def append_row_dict(self, spreadsheet_id: str, row: Dict[str, Any], sheet_name: str = "Sheet1"):
        """Append a row using header alignment."""
        try:
            headers = self.get_headers(spreadsheet_id, sheet_name)
            if not headers:
                headers = list(row.keys())
            values = [row.get(h, "") for h in headers]
            body = {'values': [values]}
            self.service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute(num_retries=2)
        except HttpError as e:
            print(f"Error appending row: {e}")


class GoogleDocsClient:
    """Client for Google Docs operations"""
    
    def __init__(self):
        scopes = ['https://www.googleapis.com/auth/documents.readonly']
        self.creds = make_credentials(scopes)
        self.service = build('docs', 'v1', credentials=self.creds)
    
    def get_document_content(self, document_id: str) -> str:
        """Get the text content of a Google Doc"""
        try:
            doc = self.service.documents().get(documentId=document_id).execute(num_retries=2)
            content = doc.get('body', {}).get('content', [])
            
            text_parts = []
            for element in content:
                if 'paragraph' in element:
                    for para_element in element['paragraph'].get('elements', []):
                        if 'textRun' in para_element:
                            text_parts.append(para_element['textRun'].get('content', ''))
            
            return ''.join(text_parts)
        except HttpError as e:
            print(f"Error reading document: {e}")
            return ""


class GoogleSlidesClient:
    """Client for Google Slides operations"""
    
    def __init__(self):
        scopes = ['https://www.googleapis.com/auth/presentations']
        self.creds = make_credentials(scopes)
        self.service = build('slides', 'v1', credentials=self.creds)
    
    def create_job_slide(self, presentation_id: str, job: Dict, resume_pdf_url: str):
        """Create a slide for a job application"""
        job_id = job.get('id', str(int(time.time())))
        title = job.get('title', 'Unknown Position')
        company = job.get('companyName', 'Unknown Company')
        location = job.get('location', 'Not specified')
        posted_at = job.get('postedAt', 'Unknown')
        salary = format_salary_info(job.get('salaryInfo'))
        job_link = job.get('link', '')
        apply_url = job.get('applyUrl', 'https://people.tamu.edu/~carlunpen/')
        
        requests_body = [
            # Create blank slide
            {
                'createSlide': {
                    'objectId': f'slide_{job_id}',
                    'slideLayoutReference': {'predefinedLayout': 'BLANK'}
                }
            },
            # Create title text box
            {
                'createShape': {
                    'objectId': f'title_box_{job_id}',
                    'shapeType': 'TEXT_BOX',
                    'elementProperties': {
                        'pageObjectId': f'slide_{job_id}',
                        'size': {
                            'width': {'magnitude': 8229600, 'unit': 'EMU'},
                            'height': {'magnitude': 1097280, 'unit': 'EMU'}
                        },
                        'transform': {
                            'scaleX': 1, 'scaleY': 1,
                            'translateX': 228600, 'translateY': 457200,
                            'unit': 'EMU'
                        }
                    }
                }
            },
            # Insert title text
            {
                'insertText': {
                    'objectId': f'title_box_{job_id}',
                    'insertionIndex': 0,
                    'text': f'{title}\n{company}'
                }
            },
            # Create left info box
            {
                'createShape': {
                    'objectId': f'left_box_{job_id}',
                    'shapeType': 'TEXT_BOX',
                    'elementProperties': {
                        'pageObjectId': f'slide_{job_id}',
                        'size': {
                            'width': {'magnitude': 3840480, 'unit': 'EMU'},
                            'height': {'magnitude': 3014640, 'unit': 'EMU'}
                        },
                        'transform': {
                            'scaleX': 1, 'scaleY': 1,
                            'translateX': 457200, 'translateY': 2057800,
                            'unit': 'EMU'
                        }
                    }
                }
            },
            # Insert left box text
            {
                'insertText': {
                    'objectId': f'left_box_{job_id}',
                    'insertionIndex': 0,
                    'text': f'📍 LOCATION\n{location}\n\n📅 POSTED\n{posted_at}\n\n💰 SALARY\n{salary}'
                }
            },
            # Create right info box
            {
                'createShape': {
                    'objectId': f'right_box_{job_id}',
                    'shapeType': 'TEXT_BOX',
                    'elementProperties': {
                        'pageObjectId': f'slide_{job_id}',
                        'size': {
                            'width': {'magnitude': 3840480, 'unit': 'EMU'},
                            'height': {'magnitude': 3014640, 'unit': 'EMU'}
                        },
                        'transform': {
                            'scaleX': 1, 'scaleY': 1,
                            'translateX': 4800000, 'translateY': 2057800,
                            'unit': 'EMU'
                        }
                    }
                }
            },
            # Insert right box text with links
            {
                'insertText': {
                    'objectId': f'right_box_{job_id}',
                    'insertionIndex': 0,
                    'text': 'RESUME\nOpen PDF Resume\n\nLINKEDIN\nView Job Posting\n\nAPPLY\nQuick Apply Link'
                }
            },
        ]
        
        try:
            self.service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': requests_body}
            ).execute()
            print(f"Created slide for {company} - {title}")
        except HttpError as e:
            print(f"Error creating slide: {e}")


class ApifyClient:
    """Client for Apify LinkedIn job scraping"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.apify.com/v2"
    
    def scrape_linkedin_jobs(self, search_url: str, count: int = 100) -> List[Dict]:
        """Scrape LinkedIn jobs using Apify actor"""
        url = f"{self.base_url}/acts/{config.APIFY_ACTOR_ID}/run-sync-get-dataset-items"
        
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "count": count,
            "scrapeCompany": True,
            "urls": [search_url]
        }
        
        try:
            response = request_with_retries(
                "POST",
                url,
                headers=headers,
                json=payload,
                timeout=max(config.REQUEST_TIMEOUT_SECONDS, 300)
            )
            return response.json()
        except requests.RequestException as e:
            print(f"Error scraping LinkedIn: {e}")
            return []


class GitHubClient:
    """Client for GitHub file operations"""
    
    def __init__(self, token: str, repo: str):
        self.token = token
        self.repo = repo
        self.base_url = f"https://api.github.com/repos/{repo}/contents"
    
    def get_file_sha(self, file_path: str) -> Optional[str]:
        """Get SHA of existing file (needed for updates)"""
        url = f"{self.base_url}/{file_path}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        try:
            response = request_with_retries("GET", url, headers=headers)
            if response.status_code == 200:
                return response.json().get('sha')
            return None
        except requests.RequestException:
            return None
    
    def create_or_update_file(self, file_path: str, content: str, message: str) -> Dict:
        """Create or update a file on GitHub"""
        url = f"{self.base_url}/{file_path}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        }
        
        # Base64 encode content
        content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        
        payload = {
            "message": message,
            "content": content_b64
        }
        
        # Check if file exists and get SHA
        sha = self.get_file_sha(file_path)
        if sha:
            payload["sha"] = sha
        
        try:
            response = request_with_retries("PUT", url, headers=headers, json=payload)
            return response.json()
        except requests.RequestException as e:
            print(f"Error uploading to GitHub: {e}")
            return {}


class AnyMailFinderClient:
    """Client for finding decision-maker emails"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.anymailfinder.com/v5.1"
    
    def find_decision_maker(self, domain: str, categories: List[str] = None) -> Dict:
        """Find decision-maker email for a company"""
        if categories is None:
            categories = ["engineering", "hr", "ceo"]
        
        url = f"{self.base_url}/find-email/decision-maker"
        headers = {"Authorization": self.api_key}
        payload = {
            "domain": domain,
            "decision_maker_category": categories
        }
        
        try:
            response = request_with_retries("POST", url, headers=headers, json=payload)
            return response.json()
        except requests.RequestException as e:
            print(f"Error finding email: {e}")
            return {}


# =============================================================================
# LANGCHAIN CHAINS
# =============================================================================

class JobFilterChain:
    """LangChain chain for filtering jobs based on fit"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4.1-mini",
            temperature=0.7,
            api_key=config.OPENAI_API_KEY
        )
        
        self.prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(JOB_FILTER_SYSTEM_PROMPT),
            HumanMessagePromptTemplate.from_template(JOB_FILTER_USER_PROMPT)
        ])
        
        self.chain = self.prompt | self.llm | JsonOutputParser()
    
    def filter_job(self, job: Dict) -> bool:
        """Return True if job is a good fit"""
        try:
            job_description = json.dumps(job, indent=2)
            result = self.chain.invoke({"job_description": job_description})
            verdict = result.get("verdict") if isinstance(result, dict) else None
            if not verdict:
                print(f"LLM filter returned unexpected response: {result}")
                return False
            return str(verdict).lower() == "true"
        except Exception as e:
            print(f"Error filtering job: {e}")
            return False


class ResumeGeneratorChain:
    """LangChain chain for generating tailored resumes"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=1.0,
            max_tokens=4000,
            api_key=config.OPENAI_API_KEY
        )
        
        self.prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(RESUME_SYSTEM_PROMPT),
            HumanMessagePromptTemplate.from_template(RESUME_USER_PROMPT)
        ])
        
        self.chain = self.prompt | self.llm | StrOutputParser()
    
    def generate_resume(self, job: Dict, resume_template: str) -> str:
        """Generate a tailored LaTeX resume"""
        try:
            job_description = json.dumps(job, indent=2)
            raw_latex = self.chain.invoke({
                "job_description": job_description,
                "resume_template": resume_template
            })
            latex = clean_latex(raw_latex)
            if not latex or "\\documentclass" not in latex:
                raise ValueError("LLM returned invalid LaTeX")
            return latex
        except Exception as e:
            print(f"Error generating resume: {e}")
            return ""


# =============================================================================
# MAIN PIPELINE
# =============================================================================

class JobApplicationPipeline:
    """Main pipeline orchestrating the entire workflow"""
    
    def __init__(self):
        validate_required_config()
        
        # Initialize clients
        self.sheets_client = GoogleSheetsClient()
        self.docs_client = GoogleDocsClient()
        self.slides_client = GoogleSlidesClient()
        self.apify_client = ApifyClient(config.APIFY_API_KEY)
        self.github_client = GitHubClient(config.GITHUB_TOKEN, config.GITHUB_REPO)
        self.email_finder = AnyMailFinderClient(config.ANYMAILFINDER_API_KEY)
        
        # Initialize LangChain components
        self.job_filter = JobFilterChain()
        self.resume_generator = ResumeGeneratorChain()
        
        # State
        self.applied_job_ids: set = set()
        self.resume_template: str = ""
    
    def load_applied_jobs(self) -> None:
        """Load already-applied job IDs from Google Sheets"""
        print("📋 Loading already-applied jobs...")
        rows = self.sheets_client.read_sheet(config.GOOGLE_SHEETS_ID)
        self.applied_job_ids = set()
        for row in rows:
            key = row.get('JobKey') or row.get('JobID') or ""
            if key:
                self.applied_job_ids.add(str(key))
        print(f"   Found {len(self.applied_job_ids)} previously applied jobs")
    
    def load_resume_template(self) -> None:
        """Load resume template from Google Docs"""
        print("📄 Loading resume template...")
        attempts = 3
        self.resume_template = ""
        for attempt in range(1, attempts + 1):
            self.resume_template = self.docs_client.get_document_content(config.GOOGLE_DOCS_ID)
            if self.resume_template:
                break
            print(f"   Attempt {attempt}/{attempts} returned empty template; retrying...")
            time.sleep(1)
        if not self.resume_template:
            raise ValueError("Failed to load resume template from Google Docs; aborting pipeline.")
        print(f"   Template loaded ({len(self.resume_template)} characters)")
    
    def scrape_jobs(self) -> List[Dict]:
        """Scrape jobs from LinkedIn via Apify"""
        print("🔍 Scraping LinkedIn jobs...")
        jobs = self.apify_client.scrape_linkedin_jobs(config.LINKEDIN_SEARCH_URL)
        print(f"   Found {len(jobs)} jobs")
        return jobs
    
    def filter_duplicates(self, jobs: List[Dict]) -> List[Dict]:
        """Filter out already-applied jobs"""
        print("🔄 Filtering duplicates...")
        new_jobs = []
        seen_in_run = set()
        for j in jobs:
            job_key = build_job_key(j)
            j['jobKey'] = job_key
            if job_key and job_key not in self.applied_job_ids and job_key not in seen_in_run:
                new_jobs.append(j)
                seen_in_run.add(job_key)
                self.applied_job_ids.add(job_key)
        print(f"   {len(new_jobs)} new jobs after deduplication")
        return new_jobs
    
    def filter_by_fit(self, jobs: List[Dict]) -> List[Dict]:
        """Filter jobs using AI to check fit"""
        print("🤖 AI-filtering jobs for fit...")
        matching_jobs = []
        
        for i, job in enumerate(jobs):
            company = job.get('companyName', 'Unknown')
            title = job.get('title', 'Unknown')
            domain = extract_domain(job.get('companyWebsite', ''))
            
            if self.job_filter.filter_job(job):
                job['companyDomain'] = domain
                matching_jobs.append(job)
                if domain:
                    print(f"   ✅ [{i+1}/{len(jobs)}] {company} - {title}")
                else:
                    print(f"   ⚠️ [{i+1}/{len(jobs)}] {company} - {title} (no domain; email lookup may be skipped)")
            else:
                print(f"   ❌ [{i+1}/{len(jobs)}] {company} - {title}")
        
        print(f"   {len(matching_jobs)} jobs passed AI filter")
        return matching_jobs
    
    def process_job(self, job: Dict) -> Optional[Dict]:
        """Process a single job: generate resume, upload, create slide, find email"""
        company = clean_string(job.get('companyName', 'unknown-company'))
        title = clean_string(job.get('title', 'unknown-position'))
        posted_at = clean_string(job.get('postedAt', ''))
        job_key = job.get('jobKey') or build_job_key(job)
        
        print(f"\n{'='*60}")
        print(f"Processing: {company} - {title}")
        print('='*60)
        
        # 1. Generate resume
        print("   📝 Generating tailored resume...")
        latex = self.resume_generator.generate_resume(job, self.resume_template)
        if not latex or not validate_latex_output(latex):
            print("   ❌ Failed to generate resume")
            return None
        
        # 2. Upload to GitHub
        print("   📤 Uploading to GitHub...")
        file_path = generate_file_path(company, title, posted_at)
        commit_message = f"Add resume for {company} - {title}"
        
        github_response = self.github_client.create_or_update_file(file_path, latex, commit_message)
        if not github_response:
            print("   ❌ Failed to upload to GitHub")
            return None
        
        download_url = github_response.get('content', {}).get('download_url', '')
        pdf_url = download_url.replace('/tex/', '/pdf/').replace('.tex', '.pdf')
        print(f"   ✅ Uploaded: {file_path}")
        
        # 3. Wait for GitHub Actions to compile PDF
        wait_seconds = config.WAIT_FOR_PDF_SECONDS
        print(f"   ⏳ Checking for PDF readiness (up to {wait_seconds}s)...")
        pdf_ready = wait_for_pdf_ready(pdf_url, wait_seconds)
        if not pdf_ready:
            print("   ⚠️ PDF not confirmed ready; verify GitHub Actions artifact if needed")
        
        # 4. Create Google Slide
        print("   📊 Creating presentation slide...")
        self.slides_client.create_job_slide(config.GOOGLE_SLIDES_ID, job, pdf_url)
        
        # 5. Find decision-maker email
        print("   📧 Finding decision-maker email...")
        domain = job.get('companyDomain') or extract_domain(job.get('companyWebsite', ''))
        email_result = self.email_finder.find_decision_maker(domain) if domain else {}
        email = email_result.get('valid_email', '')
        person_name = email_result.get('person_full_name', '')
        person_title = email_result.get('person_job_title', '')
        person_linkedin = email_result.get('person_linkedin_url', '')
        
        if email:
            print(f"   ✅ Found: {person_name} ({email})")
        else:
            print("   ⚠️ No email found")
        
        # 6. Append to Google Sheets
        print("   📋 Appending to tracking sheet...")
        row_values = {
            "Email": email,
            "PersonName": person_name,
            "CompanyWebsite": job.get('companyWebsite', ''),
            "PersonTitle": person_title,
            "PersonLinkedIn": person_linkedin,
            "ResumePdf": pdf_url,
            "ApplyUrl": job.get('applyUrl', ''),
            "JobID": str(job.get('id', '')),
            "JobDescription": job.get('descriptionHtml', '')[:1000],
            "JobKey": job_key
        }
        self.sheets_client.append_row_dict(config.GOOGLE_SHEETS_ID, row_values)
        
        return {
            'job': job,
            'resume_path': file_path,
            'pdf_url': pdf_url,
            'email': email,
            'person_name': person_name
        }
    
    def run(self, max_jobs: int = None) -> List[Dict]:
        """Run the entire pipeline"""
        print("\n" + "="*60)
        print("🚀 STARTING JOB APPLICATION PIPELINE")
        print("="*60 + "\n")
        
        # Initialize
        self.load_applied_jobs()
        self.load_resume_template()
        
        # Scrape and filter
        jobs = self.scrape_jobs()
        jobs = self.filter_duplicates(jobs)
        jobs = self.filter_by_fit(jobs)
        
        if max_jobs:
            jobs = jobs[:max_jobs]
        
        # Process each job
        results = []
        for i, job in enumerate(jobs):
            print(f"\n[{i+1}/{len(jobs)}] Processing job...")
            try:
                result = self.process_job(job)
                if result:
                    results.append(result)
            except Exception as e:
                print(f"   ❌ Error: {e}")
                continue
        
        # Summary
        print("\n" + "="*60)
        print("📊 PIPELINE COMPLETE")
        print("="*60)
        print(f"   Total jobs scraped: {len(jobs)}")
        print(f"   Successfully processed: {len(results)}")
        print(f"   Failed: {len(jobs) - len(results)}")
        
        return results


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    # Run the pipeline
    pipeline = JobApplicationPipeline()
    
    # Process up to 10 jobs for testing (remove limit for full run)
    results = pipeline.run(max_jobs=10)
    
    # Print results
    print("\n📋 Results Summary:")
    for r in results:
        job = r['job']
        print(f"   - {job.get('companyName')} - {job.get('title')}")
        print(f"     Resume: {r['pdf_url']}")
        print(f"     Contact: {r['person_name']} ({r['email']})")