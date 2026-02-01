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
7. Compile LaTeX to PDF locally using pdflatex
8. Upload both .tex and .pdf files to GitHub
9. Create Google Slides presentation page
10. Find decision-maker email (AnyMailFinder)
11. Append results to Google Sheets
12. Loop for all jobs

Requirements:
- pdflatex must be installed (texlive-latex-base, texlive-fonts-recommended, texlive-latex-extra)

Author: Carlos Luna-Peña
"""

import os
import json
import base64
import re
import time
import subprocess
import tempfile
import shutil
import uuid
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass
from dotenv import load_dotenv

# LangChain imports
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser

# External API clients
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from urllib.parse import urlparse
import click


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
    GITHUB_REPO: str = os.getenv("GITHUB_REPO", "applyEasy/Backend")
    
    # Google (service account JSON provided via env string)
    GOOGLE_SERVICE_ACCOUNT_JSON: str = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    GOOGLE_SHEETS_ID: str = os.getenv("GOOGLE_SHEETS_ID", "")
    GOOGLE_DOCS_ID: str = os.getenv("GOOGLE_DOCS_ID", "")
    GOOGLE_SLIDES_ID: str = os.getenv("GOOGLE_SLIDES_ID", "")
    
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
    # DEPRECATED: No longer used - PDF is now compiled locally before upload
    WAIT_FOR_PDF_SECONDS: int = int(os.getenv("WAIT_FOR_PDF_SECONDS", str(6 * 60)))
    REQUEST_TIMEOUT_SECONDS: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "45"))
    REQUEST_RETRIES: int = int(os.getenv("REQUEST_RETRIES", "3"))
    REQUEST_RETRY_BACKOFF: int = int(os.getenv("REQUEST_RETRY_BACKOFF", "2"))


config = Config()


def check_pdflatex_installed() -> Tuple[bool, str]:
    """
    Check if pdflatex is available and required packages are installed.

    Returns:
        Tuple of (success: bool, error_message: str)
    """
    # First check if pdflatex binary exists
    try:
        result = subprocess.run(
            ['pdflatex', '--version'],
            capture_output=True,
            timeout=10
        )
        if result.returncode != 0:
            return False, "pdflatex not found or not working"
    except FileNotFoundError:
        return False, "pdflatex not found. Please install texlive."
    except subprocess.TimeoutExpired:
        return False, "pdflatex version check timed out"

    # Test compilation with packages used by resume template
    test_latex = r"""
\documentclass[letterpaper,11pt]{article}
\usepackage{latexsym}
\usepackage[empty]{fullpage}
\usepackage{titlesec}
\usepackage{marvosym}
\usepackage[usenames,dvipsnames]{color}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}
\begin{document}
Test
\end{document}
"""

    temp_dir = tempfile.mkdtemp(prefix='latex_test_')
    test_tex = Path(temp_dir) / "test.tex"
    test_pdf = Path(temp_dir) / "test.pdf"

    try:
        test_tex.write_text(test_latex, encoding='utf-8')
        result = subprocess.run(
            ['pdflatex', '-interaction=nonstopmode', '-halt-on-error', 'test.tex'],
            cwd=temp_dir,
            capture_output=True,
            timeout=30,
            text=True
        )

        if result.returncode != 0:
            # Extract the error from pdflatex output
            output_lines = result.stdout.split('\n')
            error_lines = [l for l in output_lines if l.startswith('!') or 'Fatal error' in l]
            if error_lines:
                error_msg = error_lines[0]
            else:
                # Look for missing package errors
                missing_pkg = [l for l in output_lines if 'File' in l and 'not found' in l]
                if missing_pkg:
                    error_msg = missing_pkg[0]
                else:
                    error_msg = "Test compilation failed (check LaTeX packages)"
            return False, error_msg

        if not test_pdf.exists():
            return False, "Test compilation produced no PDF output"

        return True, ""

    except subprocess.TimeoutExpired:
        return False, "Test compilation timed out (30s)"
    except Exception as e:
        return False, f"Test compilation error: {e}"
    finally:
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass


# =============================================================================
# PROMPTS
# =============================================================================

JOB_FILTER_SYSTEM_PROMPT = """You are a strict job filter for ONE candidate.
Decide if a job is a reasonable fit for this candidate.
Output ONLY compact JSON: {{"verdict":"true"}} or {{"verdict":"false"}}.
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


def make_credentials(scopes: List[str]) -> service_account.Credentials:
    """Create service account credentials from env-provided JSON or file path."""
    source = config.GOOGLE_SERVICE_ACCOUNT_JSON
    if not source:
        # Graceful fallback to local file for convenience
        default_path = "service-account.json"
        if os.path.isfile(default_path):
            source = default_path
        else:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON is required for Google API access")
    
    if os.path.isfile(source):
        with open(source, "r", encoding="utf-8") as f:
            raw_json = f.read()
    else:
        raw_json = source
    
    try:
        info = json.loads(raw_json)
    except json.JSONDecodeError as e:
        raise ValueError("Invalid GOOGLE_SERVICE_ACCOUNT_JSON content") from e
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

    # Truncate slugs to prevent overly long filenames (max 50 chars each)
    company_slug = company_slug[:50]
    title_slug = title_slug[:50]

    # Extract digits from posted_at, fallback to current date if empty
    if posted_at:
        date_part = re.sub(r'[^0-9]', '', posted_at)
    if not posted_at or not date_part:  # Handle empty string after digit extraction
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
        click.secho("[WARN] ANYMAILFINDER_API_KEY not set; decision-maker email lookup may be skipped.", fg="yellow")


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


def extract_pdf_text(pdf_source: Union[str, bytes]) -> str:
    """Extract text from PDF for ATS scoring.

    Args:
        pdf_source: Either a file path (str) or PDF bytes (bytes)
    """
    try:
        import fitz  # PyMuPDF - more reliable than PyPDF2
        if isinstance(pdf_source, bytes):
            doc = fitz.open(stream=pdf_source, filetype="pdf")
        else:
            doc = fitz.open(pdf_source)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    except ImportError:
        try:
            # Fallback to PyPDF2 (only works with file paths)
            import PyPDF2
            if isinstance(pdf_source, bytes):
                import io
                f = io.BytesIO(pdf_source)
            else:
                f = open(pdf_source, 'rb')
            try:
                reader = PyPDF2.PdfReader(f)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() or ""
                return text
            finally:
                f.close()
        except ImportError:
            click.secho("   [WARN] Neither PyMuPDF nor PyPDF2 installed, skipping text extraction", fg="yellow")
            return ""
    except Exception as e:
        click.secho(f"   [WARN] PDF text extraction failed: {e}", fg="yellow")
        return ""


def validate_latex_output(latex: str) -> bool:
    """Validate LaTeX output to avoid uploading malformed files that will fail compilation."""
    if not latex:
        return False

    # Check for required structural elements
    required_elements = ["\\documentclass", "\\begin{document}", "\\end{document}"]
    for element in required_elements:
        if element not in latex:
            click.secho(f"   [WARN] LaTeX validation failed: missing {element}", fg="yellow")
            return False

    # Minimum length heuristic
    if len(latex) < 200:
        click.secho("   [WARN] LaTeX validation failed: content too short", fg="yellow")
        return False

    # Check for malformed titleformat commands (orphaned braces before \begin{document})
    begin_doc_idx = latex.find("\\begin{document}")
    preamble = latex[:begin_doc_idx] if begin_doc_idx > 0 else ""

    # Detect orphaned closing braces at line start (common LLM truncation pattern)
    orphan_brace_pattern = re.compile(r'^\s*\}\s*\{', re.MULTILINE)
    if orphan_brace_pattern.search(preamble):
        click.secho("   [WARN] LaTeX validation failed: detected malformed command (orphaned braces in preamble)", fg="yellow")
        return False

    # Check for incomplete titleformat (pattern: }{}{}{ without preceding \titleformat)
    if re.search(r'\}\s*\{\}\s*\{\}\s*\{', preamble):
        incomplete_titleformat = not re.search(r'\\titleformat\s*\{', preamble)
        if incomplete_titleformat:
            click.secho("   [WARN] LaTeX validation failed: incomplete \\titleformat command", fg="yellow")
            return False

    # Basic brace balance check in preamble
    open_braces = preamble.count('{')
    close_braces = preamble.count('}')
    if abs(open_braces - close_braces) > 5:  # Allow some tolerance for edge cases
        click.secho(f"   [WARN] LaTeX validation failed: brace imbalance in preamble ({open_braces} open, {close_braces} close)", fg="yellow")
        return False

    return True


def compile_latex_to_pdf(latex_content: str, base_filename: str) -> Optional[Tuple[str, bytes]]:
    """
    Compile LaTeX content to PDF using pdflatex.

    Args:
        latex_content: The LaTeX source code
        base_filename: Base name for the output files (without extension)

    Returns:
        Tuple of (pdf_path, pdf_bytes) if successful, None if compilation fails
    """
    # Create temp directory for compilation
    temp_dir = tempfile.mkdtemp(prefix='latex_compile_')
    tex_path = Path(temp_dir) / f"{base_filename}.tex"
    pdf_path = Path(temp_dir) / f"{base_filename}.pdf"
    compilation_succeeded = False

    try:
        # Write LaTeX content to temp file
        tex_path.write_text(latex_content, encoding='utf-8')

        # Run pdflatex twice (for references/TOC)
        for pass_num in range(2):
            result = subprocess.run(
                ['pdflatex', '-interaction=nonstopmode', '-halt-on-error', tex_path.name],
                cwd=temp_dir,
                capture_output=True,
                timeout=60,
                text=True
            )

            if result.returncode != 0:
                # Save failed .tex file and full pdflatex output for debugging
                failed_dir = Path("tex/failed")
                failed_dir.mkdir(parents=True, exist_ok=True)

                # Save .tex file
                failed_tex = failed_dir / f"{base_filename}_FAILED.tex"
                shutil.copy(tex_path, failed_tex)

                # Save full pdflatex output to log file
                log_file = failed_dir / f"{base_filename}_pdflatex.log"
                log_file.write_text(result.stdout, encoding='utf-8')

                print(f"   pdflatex pass {pass_num + 1} failed:")
                print(f"   Failed .tex saved to: {failed_tex}")
                print(f"   Full log saved to: {log_file}")

                # Print last 30 lines for immediate context
                stderr_lines = result.stdout.split('\n')[-30:]
                for line in stderr_lines:
                    if line.strip():
                        print(f"      {line}")

                print(f"   Temp dir preserved for debugging: {temp_dir}")
                return None

        # Verify PDF was created and is non-empty
        if not pdf_path.exists() or pdf_path.stat().st_size == 0:
            # Save failed .tex file for debugging
            failed_dir = Path("tex/failed")
            failed_dir.mkdir(parents=True, exist_ok=True)
            failed_tex = failed_dir / f"{base_filename}_FAILED_NO_PDF.tex"
            shutil.copy(tex_path, failed_tex)

            print("   PDF file was not created or is empty")
            print(f"   Failed .tex saved to: {failed_tex}")
            print(f"   Temp dir preserved for debugging: {temp_dir}")
            return None

        # Read PDF bytes
        pdf_bytes = pdf_path.read_bytes()
        compilation_succeeded = True

        return (str(pdf_path), pdf_bytes)

    except subprocess.TimeoutExpired:
        # Save failed .tex file for debugging
        failed_dir = Path("tex/failed")
        failed_dir.mkdir(parents=True, exist_ok=True)
        failed_tex = failed_dir / f"{base_filename}_FAILED_TIMEOUT.tex"
        shutil.copy(tex_path, failed_tex)

        print("   pdflatex compilation timed out (60s)")
        print(f"   Failed .tex saved to: {failed_tex}")
        print(f"   Temp dir preserved for debugging: {temp_dir}")
        return None
    except Exception as e:
        # Save failed .tex file for debugging
        failed_dir = Path("tex/failed")
        failed_dir.mkdir(parents=True, exist_ok=True)
        failed_tex = failed_dir / f"{base_filename}_FAILED_EXCEPTION.tex"
        try:
            shutil.copy(tex_path, failed_tex)
            print(f"   Failed .tex saved to: {failed_tex}")
        except:
            pass

        print(f"   LaTeX compilation error: {e}")
        print(f"   Temp dir preserved for debugging: {temp_dir}")
        return None
    finally:
        # Only clean up temp directory if compilation succeeded
        if compilation_succeeded:
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass


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
    
    def create_job_slide(self, presentation_id: str, job: Dict, resume_pdf_url: str) -> bool:
        """Create a slide for a job application. Returns True on success, False on failure."""
        # Use UUID suffix to ensure globally unique object IDs (prevents collision if same job ID)
        job_id = f"{job.get('id', 'noid')}_{uuid.uuid4().hex[:8]}"
        title = job.get('title', 'Unknown Position')
        company = job.get('companyName', 'Unknown Company')
        location = job.get('location', 'Not specified')
        posted_at = job.get('postedAt', 'Unknown')

        # Get ATS scores (replaces salary display)
        ats_scores = job.get('ats_scores', {})
        ats_score = ats_scores.get('overall_score', 'N/A')
        ats_recommendation = ats_scores.get('recommendation', 'N/A')
        ats_display = f"{ats_score}/100 ({ats_recommendation})"

        # Fallback chain for job link to prevent empty URL in hyperlink
        job_link = job.get('link', '') or job.get('applyUrl', '') or 'https://linkedin.com/jobs'
        apply_url = job.get('applyUrl', '') or 'https://people.tamu.edu/~carlunpen/'

        # Define right box text and calculate link indices dynamically (prevents hardcoding bugs)
        right_box_text = 'RESUME\nOpen PDF Resume\n\nLINKEDIN\nView Job Posting\n\nAPPLY\nQuick Apply Link'
        resume_link_start = right_box_text.find('Open PDF Resume')
        resume_link_end = resume_link_start + len('Open PDF Resume')
        job_link_start = right_box_text.find('View Job Posting')
        job_link_end = job_link_start + len('View Job Posting')
        apply_link_start = right_box_text.find('Quick Apply Link')
        apply_link_end = apply_link_start + len('Quick Apply Link')

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
                    'text': f'LOCATION\n{location}\n\nPOSTED\n{posted_at}\n\nATS SCORE\n{ats_display}'
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
                    'text': right_box_text
                }
            },
            # Add hyperlink to "Open PDF Resume" (dynamically calculated indices)
            {
                'updateTextStyle': {
                    'objectId': f'right_box_{job_id}',
                    'textRange': {
                        'type': 'FIXED_RANGE',
                        'startIndex': resume_link_start,
                        'endIndex': resume_link_end
                    },
                    'style': {
                        'link': {'url': resume_pdf_url},
                        'foregroundColor': {
                            'opaqueColor': {
                                'rgbColor': {'red': 0.102, 'green': 0.4, 'blue': 0.898}
                            }
                        },
                        'underline': True
                    },
                    'fields': 'link,foregroundColor,underline'
                }
            },
            # Add hyperlink to "View Job Posting" (dynamically calculated indices)
            {
                'updateTextStyle': {
                    'objectId': f'right_box_{job_id}',
                    'textRange': {
                        'type': 'FIXED_RANGE',
                        'startIndex': job_link_start,
                        'endIndex': job_link_end
                    },
                    'style': {
                        'link': {'url': job_link},
                        'foregroundColor': {
                            'opaqueColor': {
                                'rgbColor': {'red': 0.102, 'green': 0.4, 'blue': 0.898}
                            }
                        },
                        'underline': True
                    },
                    'fields': 'link,foregroundColor,underline'
                }
            },
            # Add hyperlink to "Quick Apply Link" (dynamically calculated indices)
            {
                'updateTextStyle': {
                    'objectId': f'right_box_{job_id}',
                    'textRange': {
                        'type': 'FIXED_RANGE',
                        'startIndex': apply_link_start,
                        'endIndex': apply_link_end
                    },
                    'style': {
                        'link': {'url': apply_url},
                        'foregroundColor': {
                            'opaqueColor': {
                                'rgbColor': {'red': 0.102, 'green': 0.4, 'blue': 0.898}
                            }
                        },
                        'underline': True
                    },
                    'fields': 'link,foregroundColor,underline'
                }
            },
            # Style title box: 32pt, bold, dark gray, centered
            {
                'updateTextStyle': {
                    'objectId': f'title_box_{job_id}',
                    'style': {
                        'fontSize': {'magnitude': 32, 'unit': 'PT'},
                        'bold': True,
                        'foregroundColor': {
                            'opaqueColor': {
                                'rgbColor': {'red': 0.149, 'green': 0.149, 'blue': 0.149}
                            }
                        }
                    },
                    'fields': 'fontSize,bold,foregroundColor'
                }
            },
            {
                'updateParagraphStyle': {
                    'objectId': f'title_box_{job_id}',
                    'style': {
                        'alignment': 'CENTER',
                        'lineSpacing': 110
                    },
                    'fields': 'alignment,lineSpacing'
                }
            },
            # Style left box: 13pt font
            {
                'updateTextStyle': {
                    'objectId': f'left_box_{job_id}',
                    'style': {
                        'fontSize': {'magnitude': 13, 'unit': 'PT'}
                    },
                    'fields': 'fontSize'
                }
            },
            # Style right box: 13pt font
            {
                'updateTextStyle': {
                    'objectId': f'right_box_{job_id}',
                    'style': {
                        'fontSize': {'magnitude': 13, 'unit': 'PT'}
                    },
                    'fields': 'fontSize'
                }
            },
            # Left box paragraph spacing
            {
                'updateParagraphStyle': {
                    'objectId': f'left_box_{job_id}',
                    'style': {
                        'lineSpacing': 120,
                        'spaceAbove': {'magnitude': 8, 'unit': 'PT'},
                        'spaceBelow': {'magnitude': 8, 'unit': 'PT'}
                    },
                    'fields': 'lineSpacing,spaceAbove,spaceBelow'
                }
            },
            # Right box paragraph spacing
            {
                'updateParagraphStyle': {
                    'objectId': f'right_box_{job_id}',
                    'style': {
                        'lineSpacing': 120,
                        'spaceAbove': {'magnitude': 8, 'unit': 'PT'},
                        'spaceBelow': {'magnitude': 8, 'unit': 'PT'}
                    },
                    'fields': 'lineSpacing,spaceAbove,spaceBelow'
                }
            },
            # Left box background: light blue with blue border
            {
                'updateShapeProperties': {
                    'objectId': f'left_box_{job_id}',
                    'shapeProperties': {
                        'shapeBackgroundFill': {
                            'solidFill': {
                                'color': {
                                    'rgbColor': {'red': 0.949, 'green': 0.969, 'blue': 1.0}
                                }
                            }
                        },
                        'outline': {
                            'outlineFill': {
                                'solidFill': {
                                    'color': {
                                        'rgbColor': {'red': 0.698, 'green': 0.8, 'blue': 0.949}
                                    }
                                }
                            },
                            'weight': {'magnitude': 25400, 'unit': 'EMU'}
                        }
                    },
                    'fields': 'shapeBackgroundFill.solidFill.color,outline'
                }
            },
            # Right box background: light green with green border
            {
                'updateShapeProperties': {
                    'objectId': f'right_box_{job_id}',
                    'shapeProperties': {
                        'shapeBackgroundFill': {
                            'solidFill': {
                                'color': {
                                    'rgbColor': {'red': 0.969, 'green': 1.0, 'blue': 0.949}
                                }
                            }
                        },
                        'outline': {
                            'outlineFill': {
                                'solidFill': {
                                    'color': {
                                        'rgbColor': {'red': 0.698, 'green': 0.898, 'blue': 0.698}
                                    }
                                }
                            },
                            'weight': {'magnitude': 25400, 'unit': 'EMU'}
                        }
                    },
                    'fields': 'shapeBackgroundFill.solidFill.color,outline'
                }
            },
        ]
        
        try:
            self.service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': requests_body}
            ).execute()
            click.secho(f"   [OK] Created slide for {company} - {title}", fg="green")
            return True
        except HttpError as e:
            click.secho(f"   [ERROR] Error creating slide: {e}", fg="red")
            return False


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

    def upload_binary_file(self, file_path: str, content_bytes: bytes, message: str) -> Dict:
        """Upload a binary file (like PDF) to GitHub."""
        url = f"{self.base_url}/{file_path}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        }

        # Base64 encode binary content
        content_b64 = base64.b64encode(content_bytes).decode('utf-8')

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
            print(f"Error uploading binary to GitHub: {e}")
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
            model="gpt-4o-mini",
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


# =============================================================================
# HYBRID RESUME GENERATION SYSTEM (GPT-4o Content + Template LaTeX + ATS Scoring)
# =============================================================================

class HybridContentGenerator:
    """
    Uses GPT-4o to generate tailored resume CONTENT (not LaTeX syntax).
    Returns structured JSON that will be plugged into templates.

    This is the key insight: GPT-4o is excellent at understanding job requirements
    and tailoring content, but struggles with LaTeX syntax. We separate concerns:
    - GPT-4o: Content intelligence (what to say)
    - Templates: LaTeX formatting (how to say it)
    """

    CONTENT_GENERATION_PROMPT = """You are an expert resume content generator for internship applications.

Your task: Analyze this job description and the candidate's background, then select and tailor the MOST COMPELLING content for this specific role.

**Critical Rules:**
1. Return ONLY valid JSON (no markdown, no code fences, no LaTeX, no explanation)
2. Select the 3-4 MOST RELEVANT bullet points for each experience
3. REWRITE bullets to incorporate job-specific keywords naturally
4. Prioritize experiences/projects most relevant to this role
5. Reorder skills to put job-matching technologies FIRST
6. Use EXACT terminology from the job description (e.g., if JD says "React.js", use "React.js")

**Job Description:**
{job_description}

**Candidate Background Data:**
{resume_data}

**Return JSON in this EXACT structure:**
{{
  "experiences": [
    {{
      "company": "AIPHRODITE",
      "title": "Technical Lead \\& Full Stack / ML",
      "dates": "Sep. 2024 -- Present",
      "location": "College Station, TX",
      "bullets": [
        "First bullet tailored to this job with relevant keywords...",
        "Second bullet highlighting relevant skills...",
        "Third bullet with quantified achievements..."
      ]
    }},
    {{
      "company": "applyeasy.tech",
      "title": "Founder \\& Full-Stack Developer",
      "dates": "January 2024 -- Present",
      "location": "College Station, TX",
      "bullets": [
        "First bullet...",
        "Second bullet...",
        "Third bullet..."
      ]
    }}
  ],
  "projects": [
    {{
      "name": "carlosOS -- Custom Unix Shell",
      "tech": "C, Linux, Systems Programming",
      "dates": "October 2024",
      "bullets": [
        "First bullet...",
        "Second bullet..."
      ]
    }},
    {{
      "name": "Project Name",
      "tech": "Tech Stack",
      "dates": "Date",
      "bullets": ["..."]
    }},
    {{
      "name": "Project Name",
      "tech": "Tech Stack",
      "dates": "Date",
      "bullets": ["..."]
    }}
  ],
  "skills": {{
    "Languages": ["Python", "TypeScript", "JavaScript", "C/C++", "Java", "SQL"],
    "Frameworks": ["React", "Next.js", "FastAPI", "Node.js", "LangChain"],
    "Databases \\& Tools": ["PostgreSQL", "Docker", "Git", "GitHub Actions", "Linux"]
  }},
  "education_bullets": [
    "Relevant Coursework: Software Engineering, Algorithms, Operating Systems, AI",
    "Dean's List or other relevant achievement"
  ]
}}

**IMPORTANT:**
- Include EXACTLY 2 experiences (AIPHRODITE and applyeasy.tech)
- Include EXACTLY 3 projects (choose the 3 most relevant)
- Include 3-4 bullets per experience, 2 bullets per project
- Escape special characters: & becomes \\&, % becomes \\%
- Use -- for date ranges (not -)
- Return ONLY the JSON object, nothing else"""

    def __init__(self):
        try:
            self.llm = ChatOpenAI(
                model="gpt-4o",
                temperature=0.7,  # Creative but controlled
                max_tokens=3000,
                api_key=config.OPENAI_API_KEY
            )
            self.prompt = ChatPromptTemplate.from_template(self.CONTENT_GENERATION_PROMPT)
            self.chain = self.prompt | self.llm | JsonOutputParser()
            print("   [INFO] HybridContentGenerator initialized (using gpt-4o)")
        except Exception as e:
            click.secho(f"   [WARN] HybridContentGenerator initialization failed: {e}", fg="yellow")
            raise

    def generate_content(self, job: Dict, resume_data: str) -> Dict:
        """
        Generate tailored content selections for this job.

        Args:
            job: Job description dict from LinkedIn
            resume_data: Raw resume helper text with all background data

        Returns:
            JSON dict with experiences, projects, skills, education_bullets
        """
        try:
            job_description = json.dumps(job, indent=2)
            content = self.chain.invoke({
                "job_description": job_description,
                "resume_data": resume_data
            })

            # Validate required keys
            required_keys = ["experiences", "projects", "skills", "education_bullets"]
            for key in required_keys:
                if key not in content:
                    raise ValueError(f"Missing required key in GPT-4o response: {key}")

            # Log what was generated
            num_exp = len(content.get("experiences", []))
            num_proj = len(content.get("projects", []))
            click.secho(f"   [OK] Generated tailored content: {num_exp} experiences, {num_proj} projects", fg="green")

            return content

        except Exception as e:
            click.secho(f"   [ERROR] Content generation failed: {e}", fg="red")
            raise  # Fail fast - don't submit bad resumes


class ATSScorer:
    """
    Scores resumes against job descriptions using keyword matching and heuristics.
    Provides objective quality metrics before submission.
    """

    def __init__(self):
        self.initialized = True
        print("   [INFO] ATSScorer initialized")

    def score_resume(self, resume_text: str, job_description: str) -> Dict:
        """
        Score resume against job description.

        Returns:
            {
                "overall_score": 78,           # 0-100
                "keyword_match_pct": 65.5,     # percentage
                "missing_keywords": ["Docker", "Kubernetes"],
                "matched_keywords": ["Python", "React", "TypeScript"],
                "recommendation": "GOOD",      # STRONG/GOOD/FAIR/WEAK
                "should_submit": True          # Based on threshold
            }
        """
        if not resume_text or not job_description:
            return {
                "overall_score": 0,
                "keyword_match_pct": 0,
                "missing_keywords": [],
                "matched_keywords": [],
                "recommendation": "UNKNOWN",
                "should_submit": True  # Don't block if no text
            }

        try:
            # Extract keywords from job description
            job_keywords = self._extract_keywords(job_description)

            # Check which keywords appear in resume
            resume_lower = resume_text.lower()
            matched = []
            missing = []

            for keyword in job_keywords:
                if keyword.lower() in resume_lower:
                    matched.append(keyword)
                else:
                    missing.append(keyword)

            # Calculate scores
            if len(job_keywords) > 0:
                keyword_match_pct = (len(matched) / len(job_keywords)) * 100
            else:
                keyword_match_pct = 100

            # Overall score is weighted
            # 70% keyword match, 30% format/length heuristics
            format_score = self._score_format(resume_text)
            overall_score = int(0.7 * keyword_match_pct + 0.3 * format_score)

            recommendation = self._get_recommendation(overall_score)
            should_submit = overall_score >= 60

            return {
                "overall_score": overall_score,
                "keyword_match_pct": round(keyword_match_pct, 1),
                "missing_keywords": missing[:10],  # Top 10 missing
                "matched_keywords": matched,
                "recommendation": recommendation,
                "should_submit": should_submit
            }

        except Exception as e:
            click.secho(f"   [WARN] ATS scoring failed: {e}", fg="yellow")
            return {
                "overall_score": 0,
                "keyword_match_pct": 0,
                "missing_keywords": [],
                "matched_keywords": [],
                "recommendation": "ERROR",
                "should_submit": True  # Don't block on error
            }

    def _extract_keywords(self, job_description: str) -> List[str]:
        """Extract important keywords from job description."""
        # Common technical keywords to look for
        tech_keywords = [
            # Languages
            "python", "javascript", "typescript", "java", "c++", "c#", "go", "rust",
            "sql", "html", "css", "bash", "shell",
            # Frameworks
            "react", "react.js", "next.js", "nextjs", "node.js", "nodejs", "express",
            "fastapi", "django", "flask", "spring", "angular", "vue", "svelte",
            "tailwind", "tailwindcss",
            # Databases
            "postgresql", "postgres", "mysql", "mongodb", "redis", "sqlite",
            "dynamodb", "cassandra", "elasticsearch",
            # Tools/Platforms
            "docker", "kubernetes", "k8s", "aws", "azure", "gcp", "linux", "git",
            "github", "gitlab", "jenkins", "ci/cd", "terraform", "ansible",
            # AI/ML
            "machine learning", "ml", "ai", "deep learning", "pytorch", "tensorflow",
            "langchain", "openai", "llm", "nlp", "computer vision",
            # Concepts
            "rest", "restful", "api", "microservices", "agile", "scrum",
            "tdd", "testing", "unit test", "integration test"
        ]

        job_lower = job_description.lower()
        found_keywords = []

        for keyword in tech_keywords:
            if keyword in job_lower:
                found_keywords.append(keyword)

        return found_keywords

    def _score_format(self, resume_text: str) -> int:
        """Score resume format/structure (0-100)."""
        score = 100

        # Penalize if too short
        if len(resume_text) < 500:
            score -= 30
        elif len(resume_text) < 1000:
            score -= 15

        # Penalize if too long (multi-page)
        if len(resume_text) > 5000:
            score -= 20

        # Check for key sections (case-insensitive)
        text_lower = resume_text.lower()
        if "education" not in text_lower:
            score -= 10
        if "experience" not in text_lower:
            score -= 15
        if "skills" not in text_lower:
            score -= 10

        return max(0, min(100, score))

    def _get_recommendation(self, score: int) -> str:
        """Convert score to recommendation level."""
        if score >= 80:
            return "STRONG"
        elif score >= 70:
            return "GOOD"
        elif score >= 60:
            return "FAIR"
        else:
            return "WEAK"


class ResumeDataLoader:
    """Parses resume_helper_fixed.txt and extracts structured resume data."""

    def __init__(self, helper_file: str = "resume_helper_fixed.txt"):
        try:
            file_path = Path(helper_file)
            if not file_path.exists():
                raise FileNotFoundError(f"Resume template file not found: {helper_file}")

            self.raw_content = file_path.read_text(encoding='utf-8')
            print(f"   [INFO] Loaded resume template ({len(self.raw_content)} chars)")

            # Extract all sections
            self.preamble = self._extract_preamble()
            self.contact_info = self._extract_contact()
            self.education = self._extract_education()
            self.experience = self._extract_experience()
            self.projects = self._extract_projects()
            self.skills = self._extract_skills()

            click.secho(f"   [OK] Parsed: preamble, contact, education, {len(self.experience)} experiences, {len(self.projects)} projects", fg="green")

        except Exception as e:
            click.secho(f"   [ERROR] ResumeDataLoader initialization failed: {e}", fg="red")
            raise

    def _extract_preamble(self) -> str:
        """Extract LaTeX preamble between markers."""
        try:
            start_marker = "<<< BEGIN JG-PREAMBLE"
            end_marker = "<<< END JG-PREAMBLE"

            start_idx = self.raw_content.find(start_marker)
            end_idx = self.raw_content.find(end_marker)

            if start_idx == -1 or end_idx == -1:
                raise ValueError(f"Preamble markers not found (start: {start_idx}, end: {end_idx})")

            # Extract content between markers (skip the marker lines themselves)
            start_idx = self.raw_content.find('\n', start_idx) + 1
            preamble = self.raw_content[start_idx:end_idx].strip()

            if "\\documentclass" not in preamble:
                raise ValueError("Preamble missing \\documentclass command")

            return preamble

        except Exception as e:
            click.secho(f"   [ERROR] Failed to extract preamble: {e}", fg="red")
            raise

    def _extract_contact(self) -> Dict:
        """Extract contact information (hardcoded for now, can be made dynamic)."""
        return {
            "name": "Carlos Luna-Peña",
            "branding": "Computer Science @ Texas A\\&M University",
            "email": "carlunpen@tamu.edu",
            "phone": "(956) 867-1776",
            "github": "github.com/clmoon2",
            "github_url": "https://github.com/clmoon2",
            "linkedin": "linkedin.com/in/carlunpen",
            "linkedin_url": "https://linkedin.com/in/carlunpen",
            "portfolio": "applyeasy.tech",
            "portfolio_url": "https://applyeasy.tech"
        }

    def _extract_education(self) -> Dict:
        """Extract education information."""
        return {
            "institution": "Texas A\\&M University",
            "location": "College Station, TX",
            "degree": "Bachelor of Science in Computer Science",
            "gpa": "3.8/4.0",
            "graduation": "May 2026",
            "bullets": [
                "Relevant Coursework: Data Structures \\& Algorithms, Computer Architecture, Database Systems, Operating Systems",
                "Dean's List: Fall 2023, Spring 2024"
            ]
        }

    def _extract_experience(self) -> List[Dict]:
        """Extract work experience with bullet variants."""
        # Hardcoded for now - could be made dynamic by parsing resume_helper_fixed.txt
        return [
            {
                "company": "AIPHRODITE",
                "title": "Software Engineer Intern",
                "dates": "June 2024 -- August 2024",
                "location": "Remote",
                "bullets": [
                    "Built full-stack web application using React, Node.js, and PostgreSQL to automate image tagging, reducing manual work by 75\\%",
                    "Engineered PyTorch-based image classification pipeline achieving 87\\% accuracy on 500+ product images",
                    "Designed and implemented RESTful API with FastAPI serving 10K+ daily requests with <200ms latency",
                    "Integrated OAuth 2.0 authentication and JWT-based session management for secure user access",
                    "Optimized PostgreSQL queries and added database indexing, improving query performance by 40\\%",
                    "Deployed containerized application using Docker and implemented CI/CD pipeline with GitHub Actions"
                ]
            },
            {
                "company": "applyeasy.tech",
                "title": "Founder \\& Full-Stack Developer",
                "dates": "January 2024 -- Present",
                "location": "College Station, TX",
                "bullets": [
                    "Developed AI-powered job application platform using Next.js, React, and Tailwind CSS with 500+ active users",
                    "Architected PostgreSQL database schema with optimized indexing for fast querying of 50K+ job postings",
                    "Implemented LangChain and OpenAI API integration for automated resume generation and keyword matching",
                    "Built secure authentication system using OAuth 2.0 with Google Sign-In and encrypted session cookies",
                    "Integrated Google APIs (Sheets, Slides, Gmail) for automated workflow orchestration and tracking",
                    "Designed responsive UI with React and Tailwind following mobile-first principles"
                ]
            }
        ]

    def _extract_projects(self) -> List[Dict]:
        """Extract project entries."""
        return [
            {
                "name": "carlosOS -- Custom Unix Shell",
                "tech": "C, Linux, Systems Programming",
                "dates": "October 2024",
                "bullets": [
                    "Implemented Unix shell in C with support for piping, I/O redirection, and background processes",
                    "Utilized fork/execvp for process creation and waitpid for job control and status tracking",
                    "Handled signals (SIGINT, SIGTSTP) for proper interrupt and suspension of foreground processes"
                ]
            },
            {
                "name": "Aggie Events -- Campus Event Discovery Platform",
                "tech": "React, Node.js, Express, PostgreSQL, REST API",
                "dates": "September 2024",
                "bullets": [
                    "Built full-stack event discovery platform with React frontend and Node.js/Express backend",
                    "Designed PostgreSQL schema with normalized tables for events, organizations, and user preferences",
                    "Implemented RESTful API with endpoints for CRUD operations, filtering, and search functionality",
                    "Created responsive UI with real-time search and category filtering using React hooks"
                ]
            },
            {
                "name": "ApplyEasy Engine -- Job Application Automation",
                "tech": "Python, LangChain, OpenAI API, LaTeX, Google APIs",
                "dates": "December 2024",
                "bullets": [
                    "Engineered automated job application pipeline using Python, LangChain, and OpenAI API",
                    "Integrated LinkedIn job scraping via Apify and AI-powered resume tailoring with GPT-4",
                    "Automated LaTeX resume compilation and PDF generation with local pdflatex subprocess",
                    "Orchestrated workflow with Google Sheets, Slides, and GitHub APIs for tracking and storage"
                ]
            }
        ]

    def _extract_skills(self) -> Dict[str, List[str]]:
        """Extract technical skills categorized."""
        return {
            "Languages": ["TypeScript", "JavaScript", "Python", "Java", "C", "C++", "SQL", "Bash", "LaTeX"],
            "Web \\& Frameworks": ["React", "Next.js", "Node.js", "Express", "FastAPI", "Tailwind CSS", "HTML/CSS"],
            "Databases \\& Tools": ["PostgreSQL", "SQLite", "Git", "GitHub", "Docker", "Linux", "REST APIs"],
            "AI \\& Libraries": ["LangChain", "OpenAI API", "PyTorch", "NumPy", "Pandas"],
            "Other": ["OAuth 2.0", "JWT", "CI/CD", "GitHub Actions", "Agile", "TDD"]
        }


class ContentSelector:
    """Selects the most relevant resume content based on job keywords."""

    def __init__(self, resume_data: ResumeDataLoader):
        self.data = resume_data

    def select_experience_bullets(
        self,
        experience: Dict,
        keywords: Dict[str, List[str]],
        max_bullets: int = 4
    ) -> List[str]:
        """
        Select top N bullets that best match job keywords.

        Algorithm: Score each bullet by counting keyword matches, return top N.
        """
        try:
            # Flatten all keywords into a set for matching
            all_keywords = set()
            for category, kw_list in keywords.items():
                all_keywords.update([kw.lower() for kw in kw_list])

            if not all_keywords:
                # No keywords extracted - return first N bullets
                bullets = experience.get("bullets", [])
                return bullets[:max_bullets]

            # Score each bullet by keyword match count
            bullet_scores = []
            for bullet in experience.get("bullets", []):
                bullet_lower = bullet.lower()
                score = sum(1 for kw in all_keywords if kw in bullet_lower)
                bullet_scores.append((score, bullet))

            # Sort by score descending, take top N
            bullet_scores.sort(reverse=True, key=lambda x: x[0])
            selected = [bullet for score, bullet in bullet_scores[:max_bullets]]

            # Ensure we have at least some bullets (fallback to first N if scoring failed)
            if not selected and experience.get("bullets"):
                selected = experience["bullets"][:max_bullets]

            return selected

        except Exception as e:
            click.secho(f"   [WARN] Error selecting bullets: {e}, using first {max_bullets}", fg="yellow")
            return experience.get("bullets", [])[:max_bullets]

    def select_projects(
        self,
        projects: List[Dict],
        keywords: Dict[str, List[str]],
        max_projects: int = 3
    ) -> List[Dict]:
        """
        Select top N projects that best match keywords.
        """
        try:
            # Flatten keywords
            all_keywords = set()
            for category, kw_list in keywords.items():
                all_keywords.update([kw.lower() for kw in kw_list])

            if not all_keywords or not projects:
                return projects[:max_projects]

            # Score each project (combine tech stack + bullets for scoring)
            project_scores = []
            for project in projects:
                score = 0
                # Score tech stack
                tech = project.get("tech", "").lower()
                score += sum(1 for kw in all_keywords if kw in tech)

                # Score bullets
                for bullet in project.get("bullets", []):
                    bullet_lower = bullet.lower()
                    score += sum(1 for kw in all_keywords if kw in bullet_lower)

                project_scores.append((score, project))

            # Sort and select top N
            project_scores.sort(reverse=True, key=lambda x: x[0])
            return [proj for score, proj in project_scores[:max_projects]]

        except Exception as e:
            click.secho(f"   [WARN] Error selecting projects: {e}, using first {max_projects}", fg="yellow")
            return projects[:max_projects]

    def reorder_skills(
        self,
        skills: Dict[str, List[str]],
        keywords: Dict[str, List[str]]
    ) -> Dict[str, List[str]]:
        """
        Reorder skills within each category by relevance to job keywords.
        """
        try:
            # Flatten job keywords
            all_keywords = set()
            for category, kw_list in keywords.items():
                all_keywords.update([kw.lower() for kw in kw_list])

            if not all_keywords:
                return skills  # No reordering needed

            reordered = {}
            for category, skill_list in skills.items():
                # Score each skill by keyword match
                skill_scores = []
                for skill in skill_list:
                    skill_lower = skill.lower()
                    # Check if any keyword matches this skill
                    score = 1 if any(kw in skill_lower for kw in all_keywords) else 0
                    skill_scores.append((score, skill))

                # Sort by score descending (matched skills first), keep original order for ties
                skill_scores.sort(key=lambda x: (-x[0], skill_list.index(x[1])))
                reordered[category] = [skill for score, skill in skill_scores]

            return reordered

        except Exception as e:
            click.secho(f"   [WARN] Error reordering skills: {e}, using original order", fg="yellow")
            return skills


class LaTeXBuilder:
    """Builds complete LaTeX resume from components with proper escaping."""

    @staticmethod
    def escape_latex(text: str) -> str:
        """Escape LaTeX special characters (except already-escaped sequences)."""
        if not text:
            return ""
        # Don't double-escape already-escaped characters
        # Only escape raw special characters: & % $ # _ { } ~ ^
        replacements = {
            '&': r'\&',
            '%': r'\%',
            '$': r'\$',
            '#': r'\#',
            '_': r'\_',
        }
        result = text
        for char, escaped in replacements.items():
            # Only replace if not already escaped
            result = re.sub(f'(?<!\\\\){re.escape(char)}', escaped, result)
        return result

    def build_resume(
        self,
        preamble: str,
        contact: Dict,
        education: Dict,
        experience: List[Dict],
        projects: List[Dict],
        skills: Dict[str, List[str]]
    ) -> str:
        """Assemble complete LaTeX document."""
        try:
            parts = [
                preamble,
                "\\begin{document}",
                self._format_heading(contact),
                self._format_education(education),
                self._format_experience(experience),
                self._format_projects(projects),
                self._format_skills(skills),
                "\\end{document}"
            ]

            latex = "\n\n".join(parts)

            # Validate brace balance
            open_count = latex.count('{')
            close_count = latex.count('}')
            if abs(open_count - close_count) > 5:
                click.secho(f"   [WARN] Brace imbalance detected ({open_count} open, {close_count} close)", fg="yellow")

            return latex

        except Exception as e:
            click.secho(f"   [ERROR] Failed to build LaTeX: {e}", fg="red")
            raise

    def _format_heading(self, contact: Dict) -> str:
        """Generate centered heading with contact info."""
        name = contact.get("name", "")
        branding = contact.get("branding", "")
        email = contact.get("email", "")
        github = contact.get("github", "")
        github_url = contact.get("github_url", "")
        linkedin = contact.get("linkedin", "")
        linkedin_url = contact.get("linkedin_url", "")

        return f"""\\begin{{center}}
    \\textbf{{\\Huge \\scshape {name}}} \\\\ \\vspace{{1pt}}
    \\small {branding} \\\\ \\vspace{{1pt}}
    \\small {email} $|$
    \\href{{{github_url}}}{{{github}}} $|$
    \\href{{{linkedin_url}}}{{{linkedin}}}
\\end{{center}}"""

    def _format_education(self, education: Dict) -> str:
        """Generate Education section."""
        inst = education.get("institution", "")
        loc = education.get("location", "")
        degree = education.get("degree", "")
        gpa = education.get("gpa", "")
        grad = education.get("graduation", "")
        bullets = education.get("bullets", [])

        bullet_items = "\n        ".join([f"\\resumeItem{{{b}}}" for b in bullets])

        return f"""\\section{{Education}}
  \\resumeSubHeadingListStart
    \\resumeSubheading
      {{{inst}}}{{{loc}}}
      {{{degree}; GPA: {gpa}}}{{{grad}}}
      \\resumeItemListStart
        {bullet_items}
      \\resumeItemListEnd
  \\resumeSubHeadingListEnd"""

    def _format_experience(self, experiences: List[Dict]) -> str:
        """Generate Experience section with selected bullets."""
        exp_entries = []
        for exp in experiences:
            company = exp.get("company", "")
            title = exp.get("title", "")
            dates = exp.get("dates", "")
            location = exp.get("location", "")
            bullets = exp.get("bullets", [])

            bullet_items = "\n        ".join([f"\\resumeItem{{{b}}}" for b in bullets])

            entry = f"""    \\resumeSubheading
      {{{company}}}{{{location}}}
      {{{title}}}{{{dates}}}
      \\resumeItemListStart
        {bullet_items}
      \\resumeItemListEnd"""
            exp_entries.append(entry)

        return f"""\\section{{Experience}}
  \\resumeSubHeadingListStart
{chr(10).join(exp_entries)}
  \\resumeSubHeadingListEnd"""

    def _format_projects(self, projects: List[Dict]) -> str:
        """Generate Projects section."""
        proj_entries = []
        for proj in projects:
            name = proj.get("name", "")
            tech = proj.get("tech", "")
            dates = proj.get("dates", "")
            bullets = proj.get("bullets", [])

            bullet_items = "\n        ".join([f"\\resumeItem{{{b}}}" for b in bullets])

            entry = f"""    \\resumeProjectHeading
      {{\\textbf{{{name}}} $|$ \\emph{{{tech}}}}}{{{dates}}}
      \\resumeItemListStart
        {bullet_items}
      \\resumeItemListEnd"""
            proj_entries.append(entry)

        return f"""\\section{{Projects}}
  \\resumeSubHeadingListStart
{chr(10).join(proj_entries)}
  \\resumeSubHeadingListEnd"""

    def _format_skills(self, skills: Dict[str, List[str]]) -> str:
        """Generate Technical Skills section."""
        skill_lines = []
        for category, skill_list in skills.items():
            skills_str = ", ".join(skill_list)
            skill_lines.append(f"\\textbf{{{category}}}{{: {skills_str}}} \\\\")

        # Remove trailing \\ from last line
        if skill_lines:
            skill_lines[-1] = skill_lines[-1].rstrip(" \\")

        skills_content = "\n             ".join(skill_lines)

        return f"""\\section{{Technical Skills}}
 \\begin{{itemize}}[leftmargin=0.15in, label={{}}]
    \\small{{\\item{{
     {skills_content}
    }}}}
 \\end{{itemize}}"""


class HybridResumeGenerator:
    """
    Hybrid resume generator: GPT-4o for content, templates for LaTeX.

    This approach combines the best of both worlds:
    - GPT-4o: Excellent at understanding job requirements and tailoring content
    - Templates: 100% reliable LaTeX structure (no more orphaned braces!)

    The key insight: GPT-4o generated "absolutely flawless" resume for TikTok
    that got an online assessment. We keep that content quality while fixing
    the LaTeX formatting issues.
    """

    def __init__(self):
        try:
            print("   [INFO] Initializing HybridResumeGenerator...")

            # Load resume data for the prompt (background info for GPT-4o)
            self.data_loader = ResumeDataLoader("resume_helper_fixed.txt")

            # Initialize content generator (GPT-4o)
            self.content_generator = HybridContentGenerator()

            # Initialize LaTeX builder (template-based)
            self.latex_builder = LaTeXBuilder()

            click.secho("   [OK] HybridResumeGenerator ready (GPT-4o content + template LaTeX)", fg="green")

        except Exception as e:
            click.secho(f"   [ERROR] HybridResumeGenerator initialization failed: {e}", fg="red")
            raise

    def generate_resume(self, job: Dict) -> str:
        """
        Generate a tailored LaTeX resume for a specific job.

        Process:
        1. GPT-4o analyzes job and generates tailored content (JSON)
        2. Template assembles content into valid LaTeX

        Args:
            job: Job description dict from LinkedIn (via Apify)

        Returns:
            Complete LaTeX document string
        """
        try:
            # Step 1: Generate tailored content with GPT-4o
            print("   [INFO] Generating tailored content with GPT-4o...")
            content = self.content_generator.generate_content(
                job,
                self.data_loader.raw_content  # Pass full background data
            )

            # Step 2: Build LaTeX from content using templates
            print("   [INFO] Assembling LaTeX from template...")

            # Format education (static info + GPT-4o bullets)
            education = {
                "institution": self.data_loader.education.get("institution", "Texas A\\&M University"),
                "location": self.data_loader.education.get("location", "College Station, TX"),
                "degree": self.data_loader.education.get("degree", "Bachelor of Science in Computer Science"),
                "gpa": self.data_loader.education.get("gpa", "3.8/4.0"),
                "graduation": self.data_loader.education.get("graduation", "May 2026"),
                "bullets": content.get("education_bullets", self.data_loader.education.get("bullets", []))
            }

            # Use GPT-4o generated content for experiences, projects, skills
            latex = self.latex_builder.build_resume(
                preamble=self.data_loader.preamble,
                contact=self.data_loader.contact_info,
                education=education,
                experience=content.get("experiences", []),
                projects=content.get("projects", []),
                skills=content.get("skills", {})
            )

            click.secho(f"   [OK] Generated {len(latex)} chars of LaTeX (hybrid approach)", fg="green")
            return latex

        except Exception as e:
            click.secho(f"   [ERROR] Resume generation failed: {e}", fg="red")
            import traceback
            traceback.print_exc()
            return ""


# =============================================================================
# MAIN PIPELINE
# =============================================================================

class JobApplicationPipeline:
    """Main pipeline orchestrating the entire workflow"""
    
    def __init__(self):
        validate_required_config()

        # Check pdflatex is available and packages are installed
        print("[INFO] Verifying LaTeX installation...")
        pdflatex_ok, pdflatex_error = check_pdflatex_installed()
        if not pdflatex_ok:
            raise RuntimeError(
                f"LaTeX check failed: {pdflatex_error}\n\n"
                "Please install texlive with required packages:\n"
                "  Ubuntu/Debian: sudo apt-get install texlive-latex-base texlive-fonts-recommended texlive-latex-extra\n"
                "  macOS: brew install --cask mactex-no-gui\n"
                "  Windows: Install MiKTeX from https://miktex.org/"
            )
        click.secho("   [OK] LaTeX installation verified", fg="green")

        # Create local tex directory for storing .tex files
        self.tex_dir = Path("tex")
        self.tex_dir.mkdir(exist_ok=True)

        # Initialize clients
        self.sheets_client = GoogleSheetsClient()
        self.docs_client = GoogleDocsClient()
        self.slides_client = GoogleSlidesClient()
        self.apify_client = ApifyClient(config.APIFY_API_KEY)
        self.github_client = GitHubClient(config.GITHUB_TOKEN, config.GITHUB_REPO)
        self.email_finder = AnyMailFinderClient(config.ANYMAILFINDER_API_KEY)
        
        # Initialize LangChain components
        self.job_filter = JobFilterChain()
        self.resume_generator = HybridResumeGenerator()
        self.ats_scorer = ATSScorer()

        # State
        self.applied_job_ids: set = set()
        self.resume_template: str = ""  # Kept for compatibility, not used anymore
    
    def load_applied_jobs(self) -> None:
        """Load already-applied job IDs from Google Sheets"""
        print("[INFO] Loading already-applied jobs...")
        rows = self.sheets_client.read_sheet(config.GOOGLE_SHEETS_ID)
        self.applied_job_ids = set()
        for row in rows:
            key = row.get('JobKey') or row.get('JobID') or ""
            if key:
                self.applied_job_ids.add(str(key))
        print(f"   Found {len(self.applied_job_ids)} previously applied jobs")
    
    def load_resume_template(self) -> None:
        """Verify resume template file exists (loaded by HybridResumeGenerator)"""
        print("[INFO] Verifying resume template...")
        template_path = Path("resume_helper_fixed.txt")
        if not template_path.exists():
            raise ValueError(f"Resume template not found: {template_path}")
        click.secho(f"   [OK] Template file verified: {template_path}", fg="green")
    
    def scrape_jobs(self) -> List[Dict]:
        """Scrape jobs from LinkedIn via Apify"""
        print("[INFO] Scraping LinkedIn jobs...")
        jobs = self.apify_client.scrape_linkedin_jobs(config.LINKEDIN_SEARCH_URL)
        if not jobs:
            click.secho("   [WARN] No jobs returned from Apify. Check search URL or API status.", fg="yellow")
        else:
            print(f"   Found {len(jobs)} jobs")
        return jobs
    
    def filter_duplicates(self, jobs: List[Dict]) -> List[Dict]:
        """Filter out already-applied jobs"""
        print("[INFO] Filtering duplicates...")
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
        print("[INFO] AI-filtering jobs for fit...")
        matching_jobs = []
        
        for i, job in enumerate(jobs):
            company = job.get('companyName', 'Unknown')
            title = job.get('title', 'Unknown')
            domain = extract_domain(job.get('companyWebsite', ''))
            
            if self.job_filter.filter_job(job):
                job['companyDomain'] = domain
                matching_jobs.append(job)
                if domain:
                    click.secho(f"   [OK] [{i+1}/{len(jobs)}] {company} - {title}", fg="green")
                else:
                    click.secho(f"   [WARN] [{i+1}/{len(jobs)}] {company} - {title} (no domain; email lookup may be skipped)", fg="yellow")
            else:
                click.secho(f"   [SKIP] [{i+1}/{len(jobs)}] {company} - {title}", fg="red")
        
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
        
        # 1. Generate resume (template-based with keyword extraction)
        print("   [INFO] Generating tailored resume...")
        latex = self.resume_generator.generate_resume(job)
        if not latex or not validate_latex_output(latex):
            click.secho("   [ERROR] Failed to generate resume", fg="red")
            return None
        
        # 2. Generate file paths (same base name for both .tex and .pdf)
        tex_file_path = generate_file_path(company, title, posted_at)
        base_name = Path(tex_file_path).stem
        pdf_file_path = tex_file_path.replace('/tex/', '/pdf/').replace('.tex', '.pdf')

        # 3. Compile LaTeX to PDF locally FIRST (before any GitHub push)
        print("   [INFO] Compiling LaTeX to PDF locally...")
        compile_result = compile_latex_to_pdf(latex, base_name)
        if compile_result is None:
            # Log compilation failure to CSV for tracking
            failure_log = Path("compilation_failures.csv")
            if not failure_log.exists():
                failure_log.write_text("timestamp,company,title,tex_file\n", encoding='utf-8')

            with open(failure_log, "a", encoding='utf-8') as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"{timestamp},{company},{title},{tex_file_path}\n")

            click.secho("   [ERROR] Failed to compile LaTeX to PDF - skipping GitHub push", fg="red")
            return None

        pdf_path, pdf_bytes = compile_result
        click.secho("   [OK] PDF compiled successfully", fg="green")

        # 4. ATS Scoring (NEW - score resume before proceeding)
        print("   [INFO] Scoring resume with ATS simulator...")
        resume_text = extract_pdf_text(pdf_bytes)
        job_desc_str = json.dumps(job, indent=2)
        ats_scores = self.ats_scorer.score_resume(resume_text, job_desc_str)

        print(f"   [INFO] ATS Score: {ats_scores['overall_score']}/100 ({ats_scores['recommendation']})")
        print(f"   [INFO] Keyword Match: {ats_scores['keyword_match_pct']}%")
        if ats_scores['missing_keywords']:
            click.secho(f"   [WARN] Missing: {', '.join(ats_scores['missing_keywords'][:5])}", fg="yellow")

        if not ats_scores['should_submit']:
            click.secho(f"   [SKIP] Skipping due to low ATS score ({ats_scores['overall_score']} < 60)", fg="red")
            return None

        # Store ATS scores in job dict for later use
        job['ats_scores'] = ats_scores

        # 5. Save .tex file locally (not to GitHub)
        local_tex_path = self.tex_dir / Path(tex_file_path).name
        print(f"   [INFO] Saving .tex locally...")
        try:
            local_tex_path.write_text(latex, encoding='utf-8')
            click.secho(f"   [OK] Saved: {local_tex_path}", fg="green")
        except Exception as e:
            click.secho(f"   [ERROR] Failed to save .tex locally: {e}", fg="red")
            return None

        # 5. Upload .pdf file to GitHub (needed for slide links)
        print("   [INFO] Uploading .pdf to GitHub...")
        pdf_response = self.github_client.upload_binary_file(
            pdf_file_path,
            pdf_bytes,
            f"Add compiled PDF for {company} - {title}"
        )
        if pdf_response.get('message') or not pdf_response.get('content'):
            click.secho(f"   [ERROR] Failed to upload .pdf file: {pdf_response.get('message', 'No content returned')}", fg="red")
            return None
        click.secho(f"   [OK] Uploaded: {pdf_file_path}", fg="green")

        # PDF URL is available immediately (no waiting needed!)
        pdf_url = f"https://raw.githubusercontent.com/{config.GITHUB_REPO}/main/{pdf_file_path}"
        print(f"   [INFO] PDF ready: {pdf_url}")

        # 6. Create Google Slide
        print("   [INFO] Creating presentation slide...")
        slide_created = self.slides_client.create_job_slide(config.GOOGLE_SLIDES_ID, job, pdf_url)
        if not slide_created:
            click.secho("   [WARN] Slide creation failed but continuing with remaining steps...", fg="yellow")

        # 7. Find decision-maker email
        print("   [INFO] Finding decision-maker email...")
        domain = job.get('companyDomain') or extract_domain(job.get('companyWebsite', ''))
        email_result = self.email_finder.find_decision_maker(domain) if domain else {}
        email = email_result.get('valid_email', '')
        person_name = email_result.get('person_full_name', '')
        person_title = email_result.get('person_job_title', '')
        person_linkedin = email_result.get('person_linkedin_url', '')

        if email:
            click.secho(f"   [OK] Found: {person_name} ({email})", fg="green")
        else:
            click.secho("   [WARN] No email found", fg="yellow")

        # 9. Append to Google Sheets (with ATS metrics + email outreach fields)
        print("   [INFO] Appending to tracking sheet...")
        row_values = {
            # Core fields (matching spreadsheet headers)
            "Email": email,
            "Name": person_name,
            "Company Website": job.get('companyWebsite', ''),
            "JobTitle": job.get('title', ''),
            "JobUrl": job.get('link', ''),
            "ResumePdfUrl": pdf_url,
            "ApplyLink": job.get('applyUrl', ''),
            "JobID": str(job.get('id', '')),
            "JobDescription": job.get('descriptionHtml', ''),  # Full description, no truncation
            # New fields for email outreach
            "CompanyName": job.get('companyName', ''),
            "JobLocation": job.get('location', ''),
            "PostedAt": job.get('postedAt', ''),
            "MatchedSkills": ', '.join(ats_scores.get('matched_keywords', [])[:10]),
            "EmailStatus": "pending",  # For email outreach flow
            "EmailSentAt": "",
            "DraftedEmail": "",
            # Follow-up tracking fields
            "EmailCount": "0",         # Number of emails sent (0, 1, 2, or 3)
            "LastEmailSentAt": "",     # Timestamp of most recent email
            "NextFollowUpDate": "",    # When to send next follow-up
        }
        self.sheets_client.append_row_dict(config.GOOGLE_SHEETS_ID, row_values)

        return {
            'job': job,
            'resume_path': str(local_tex_path),
            'pdf_url': pdf_url,
            'email': email,
            'person_name': person_name,
            'ats_scores': ats_scores
        }
    
    def run(self, max_jobs: int = None) -> List[Dict]:
        """Run the entire pipeline"""
        click.secho("\n" + "="*60, fg="blue")
        click.secho("STARTING JOB APPLICATION PIPELINE", fg="blue", bold=True)
        click.secho("="*60 + "\n", fg="blue")
        
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
                click.secho(f"   [ERROR] {e}", fg="red")
                continue
        
        # Summary
        click.secho("\n" + "="*60, fg="blue")
        click.secho("PIPELINE COMPLETE", fg="blue", bold=True)
        click.secho("="*60, fg="blue")
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
    print("\n[INFO] Results Summary:")
    for r in results:
        job = r['job']
        print(f"   - {job.get('companyName')} - {job.get('title')}")
        print(f"     Resume: {r['pdf_url']}")
        print(f"     Contact: {r['person_name']} ({r['email']})")
