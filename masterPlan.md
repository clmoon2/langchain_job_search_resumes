 Hybrid Resume Generation + ATS Scoring Plan

 Executive Summary

 Problem: Current system has two issues:
 1. Technical: 90% LaTeX compilation failures due to malformed output (orphaned braces)
 2. Strategic: Even successful resumes may not be optimized for ATS/recruiter approval

 Key Insight from User: GPT-4o generated "absolutely flawless" resume for TikTok frontend role that got an online assessment. The content quality is
 EXCELLENT - we just need to fix the LaTeX formatting issues.

 Solution: Hybrid approach that combines GPT-4o's content intelligence with template reliability and ATS validation:
 1. GPT-4o generates compelling, tailored content (bullet points, descriptions)
 2. Template system assembles correct LaTeX structure (no more malformed braces)
 3. ATS scorer validates resume quality before submission (quality control gate)

 Impact:
 - Content Quality: Keep GPT-4o's superior job understanding and tailoring
 - Reliability: 10% -> 95%+ success rate (template-based LaTeX assembly)
 - Strategic: Only submit high-scoring resumes (ATS validation gate)
 - Cost: Similar to current ($0.015/resume for GPT-4o content generation)
 - Future: Can automate quality gates (e.g., only submit if ATS score > 75%)

 ---
 Root Cause Analysis

 What's Working Well

 GPT-4o content generation is EXCELLENT:
 - User got online assessment from TikTok with GPT-4o generated resume
 - Resume was "absolutely flawless" and "perfectly displaying what a recruiter would want"
 - Proves GPT-4o has superior understanding of job requirements and can tailor content effectively
 - We should keep GPT-4o for content generation

 What's Broken

 1. LaTeX Formatting (90% failure rate):
 [WARN] LaTeX validation failed: detected malformed command (orphaned braces in preamble)

 Root cause: resume_helper.txt contains double braces {{ that confuse GPT-4o:

 \titleformat{{\section}}{{
   \vspace{{-4pt}}\scshape\raggedright\large
 }}{{}}{{0em}}{{}}[\color{{black}}\titlerule \vspace{{-5pt}}]

 GPT-4o outputs orphaned braces instead of clean LaTeX. Even with 260+ lines of prompt trying to enforce rules, it fails 90% of the time.

 2. No Quality Control:
 - No way to measure if resumes are ATS-optimized
 - No validation of keyword matching or relevance scores
 - Submitting potentially weak resumes without knowing their quality

 Why Hybrid Approach Solves Both

 Separation of concerns:
 - GPT-4o: Does what it's best at (understanding jobs, writing compelling content)
 - Templates: Does what it's best at (generating syntactically correct LaTeX)
 - ATS Scorer: Provides objective quality metrics before submission

 This keeps the proven content quality while fixing reliability and adding strategic validation.

 ---
 Proposed Hybrid Architecture

 High-Level Design

 ┌────────────────────────────────────────────────────────────────┐
 │  Job Description (JSON from LinkedIn via Apify)                │
 └────────────────┬───────────────────────────────────────────────┘
                  │
                  ▼
 ┌────────────────────────────────────────────────────────────────┐
 │  PHASE 1: Content Generation (GPT-4o)                          │
 │  ─────────────────────────────────────────────────────────     │
 │  INPUT: Job description + resume_helper.txt (background data)  │
 │  PROMPT: Generate tailored CONTENT ONLY (not full LaTeX)       │
 │    • Tailored bullet points for each experience                │
 │    • Selected & reordered projects by relevance                │
 │    • Reordered technical skills                                │
 │    • Tailored education bullets (if applicable)                │
 │  OUTPUT: JSON with content selections                          │
 │  • Cost: ~$0.015 per job                                       │
 │  • Speed: ~5-10s                                               │
 │  • Quality: PROVEN (TikTok success)                            │
 └────────────────┬───────────────────────────────────────────────┘
                  │
                  ▼
 ┌────────────────────────────────────────────────────────────────┐
 │  PHASE 2: LaTeX Assembly (Template-Based)                      │
 │  ─────────────────────────────────────────────────────────     │
 │  INPUT: Content JSON from Phase 1 + LaTeX template             │
 │  PROCESS:                                                      │
 │    • Load preamble from resume_helper_fixed.txt                │
 │    • Plug in contact info (static)                             │
 │    • Insert Education section with GPT-4o bullets              │
 │    • Insert Experience section with GPT-4o bullets             │
 │    • Insert Projects section (GPT-4o selected)                 │
 │    • Insert Technical Skills (GPT-4o ordered)                  │
 │    • Assemble into complete LaTeX document                     │
 │  OUTPUT: Valid LaTeX document (guaranteed correct braces)      │
 │  • Cost: $0                                                    │
 │  • Speed: <100ms                                               │
 │  • Reliability: 100% (deterministic template)                  │
 └────────────────┬───────────────────────────────────────────────┘
                  │
                  ▼
 ┌────────────────────────────────────────────────────────────────┐
 │  PHASE 3: PDF Compilation & Parsing                            │
 │  ─────────────────────────────────────────────────────────     │
 │  • compile_latex_to_pdf() - pdflatex subprocess                │
 │  • Extract text from PDF (pyresparser or PyMuPDF)              │
 │  • Prepare for ATS scoring                                     │
 └────────────────┬───────────────────────────────────────────────┘
                  │
                  ▼
 ┌────────────────────────────────────────────────────────────────┐
 │  PHASE 4: ATS Scoring & Validation (NEW)                       │
 │  ─────────────────────────────────────────────────────────     │
 │  TOOL: ats-resume-scorer library                               │
 │  INPUT: Resume text + Job description                          │
 │  METRICS:                                                      │
 │    • Overall ATS score (0-100, target: 75+)                    │
 │    • Keyword match % (target: 60-80%)                          │
 │    • Missing keywords list                                     │
 │    • Technical skills overlap                                  │
 │  DECISION:                                                     │
 │    [OK] Score >= 75: Proceed to submission                       │
 │    [WARN]  Score 60-74: Log warning, submit anyway (for now)       │
 │    [SKIP] Score < 60: Skip or retry with different approach        │
 │  • Cost: $0 (local library)                                    │
 │  • Speed: ~1-2s                                                │
 └────────────────┬───────────────────────────────────────────────┘
                  │
                  ▼
 ┌────────────────────────────────────────────────────────────────┐
 │  PHASE 5: Upload & Tracking (Enhanced Logging)                 │
 │  ─────────────────────────────────────────────────────────     │
 │  • Save .tex and .pdf locally                                  │
 │  • Upload PDF to GitHub                                        │
 │  • Create Google Slide                                         │
 │  • Find decision-maker email (AnyMailFinder)                   │
 │  • Log to Google Sheets WITH ATS METRICS:                      │
 │    - Company, position, date, etc. (existing)                  │
 │    - ATS score, keyword match %, missing keywords (NEW)        │
 │    - Resume URL (existing)                                     │
 │  • Track success rate by ATS score for analytics               │
 └────────────────────────────────────────────────────────────────┘

 Component Breakdown

 1. HybridContentGenerator (Modified ResumeGeneratorChain)

 Replaces current ResumeGeneratorChain but generates JSON content instead of full LaTeX.

 class HybridContentGenerator:
     """
     Uses GPT-4o to generate tailored resume CONTENT (not LaTeX syntax).
     Returns structured JSON that will be plugged into templates.
     """

     CONTENT_GENERATION_PROMPT = """You are an expert resume content generator for internship applications.

 Your task: Analyze this job description and the candidate's background, then select and tailor the MOST COMPELLING content for this specific role.

 **Critical Rules:**
 1. Return ONLY JSON (no markdown, no code fences, no LaTeX)
 2. Select the 3-4 MOST RELEVANT bullet points for each experience
 3. Rewrite bullets to incorporate job-specific keywords naturally
 4. Prioritize experiences/projects most relevant to this role
 5. Reorder skills to put job-matching technologies FIRST

 **Job Description:**
 {job_description}

 **Candidate Background:**
 {resume_template}

 **Return JSON in this exact structure:**
 {{
   "experiences": [
     {{
       "company": "AIPHRODITE",
       "title": "Technical Lead & Full Stack / ML",
       "dates": "Sep. 2024 -- Present",
       "location": "College Station, TX",
       "bullets": [
         "Architected FastAPI backend with PostgreSQL achieving 40% latency reduction...",
         "Developed AI fashion advisor using LangChain...",
         "Led 6-person team with 35% reduction in PR rework..."
       ]
     }}
   ],
   "projects": [
     {{
       "name": "carlosOS",
       "subtitle": "C, C++, x86 Assembly, QEMU",
       "bullets": [
         "Implemented x86 bootloader and kernel...",
         "Built userland shell..."
       ]
     }}
   ],
   "skills": {{
     "Languages": ["Python", "TypeScript", "JavaScript", "C/C++", "Java"],
     "Frameworks": ["React", "Next.js", "FastAPI", "LangChain"],
     "Tools": ["Docker", "Git", "PostgreSQL", "n8n", "GitHub Actions"]
   }},
   "education_bullets": [
     "Relevant Coursework: Software Engineering, Algorithms, AI",
     "Completed writing-intensive coursework including specifications"
   ]
 }}

 **Return ONLY the JSON object. No other text.**
 """

     def __init__(self):
         self.llm = ChatOpenAI(
             model="gpt-4o",
             temperature=0.7,  # Creative but controlled
             max_tokens=2000,
             api_key=config.OPENAI_API_KEY
         )
         self.prompt = ChatPromptTemplate.from_template(
             self.CONTENT_GENERATION_PROMPT
         )
         self.chain = self.prompt | self.llm | JsonOutputParser()

     def generate_content(self, job: Dict, resume_template: str) -> Dict:
         """
         Generate tailored content selections for this job.

         Returns JSON with:
         - experiences (list of dicts with bullets)
         - projects (list of dicts with bullets)
         - skills (dict of skill categories)
         - education_bullets (list)
         """
         try:
             job_description = json.dumps(job, indent=2)
             content = self.chain.invoke({
                 "job_description": job_description,
                 "resume_template": resume_template
             })
             return content
         except Exception as e:
             print(f"   [WARN] Content generation failed: {e}")
             raise  # Fail fast, don't submit bad resumes

 Benefits:
 - GPT-4o does complex job analysis and content tailoring (proven to work!)
 - Outputs structured JSON, not LaTeX (eliminates brace errors)
 - Temperature 0.7 for creative but controlled tailoring
 - Clear separation: content intelligence vs. formatting

 ---
 2. LaTeXBuilder (New Class)

 Assembles valid LaTeX from GPT-4o's content JSON.

 class LaTeXBuilder:
     """Builds complete LaTeX resume from GPT-4o content JSON."""

     def __init__(self):
         # Load preamble once at initialization
         preamble_path = Path("resume_helper_fixed.txt")
         self.preamble = self._extract_preamble(preamble_path)

     def _extract_preamble(self, path: Path) -> str:
         """Extract lines between <<< BEGIN JG-PREAMBLE >>> and <<< END JG-PREAMBLE >>>"""
         content = path.read_text(encoding='utf-8')
         start_marker = "<<< BEGIN JG-PREAMBLE >>>"
         end_marker = "<<< END JG-PREAMBLE >>>"
         start = content.find(start_marker) + len(start_marker)
         end = content.find(end_marker)
         return content[start:end].strip()

     def build_resume(self, content_json: Dict) -> str:
         """
         Assemble complete LaTeX document from GPT-4o content JSON.

         Input format (from HybridContentGenerator):
         {
           "experiences": [...],
           "projects": [...],
           "skills": {...},
           "education_bullets": [...]
         }

         Returns: Valid LaTeX document string
         """
         parts = [
             self.preamble,
             "\\begin{document}",
             self._format_heading(),  # Static contact info
             self._format_education(content_json["education_bullets"]),
             self._format_experience(content_json["experiences"]),
             self._format_projects(content_json["projects"]),
             self._format_skills(content_json["skills"]),
             "\\end{document}"
         ]
         return "\n\n".join(parts)

     def _format_heading(self) -> str:
         """Generate static heading"""
         return r"""%----------HEADING-----------------
 \begin{center}
     \textbf{\Huge Carlos Luna-Peña} \\
     \vspace{1pt}
     \small Computer Science @ Texas A\&M \\
     \vspace{1pt}
     \href{mailto:carlunpen@gmail.com}{carlunpen@gmail.com} $|$
     \href{https://github.com/clmoon2}{GitHub: clmoon2} $|$
     \href{https://linkedin.com/in/carlos-luna}{LinkedIn: carlos-luna} $|$
     \href{https://applyeasy.tech}{applyeasy.tech} \\
 \end{center}"""

     def _format_experience(self, experiences: List[Dict]) -> str:
         """Generate Experience section from JSON"""
         lines = ["%-----------EXPERIENCE-----------------", "\\section{Experience}",
                  "  \\resumeSubHeadingListStart", ""]

         for exp in experiences:
             lines.append(f"    \\resumeSubheading")
             lines.append(f"      {{{exp['company']}}}{{{exp['location']}}}")
             lines.append(f"      {{{exp['title']}}}{{{exp['dates']}}}")
             lines.append(f"      \\resumeItemListStart")
             for bullet in exp['bullets']:
                 escaped_bullet = self._escape_latex(bullet)
                 lines.append(f"        \\resumeItem{{{escaped_bullet}}}")
             lines.append(f"      \\resumeItemListEnd")
             lines.append("")

         lines.append("  \\resumeSubHeadingListEnd")
         return "\n".join(lines)

     def _escape_latex(self, text: str) -> str:
         """Escape LaTeX special characters"""
         replacements = {
             '&': r'\&',
             '%': r'\%',
             '$': r'\$',
             '#': r'\#',
             '_': r'\_',
             '{': r'\{',
             '}': r'\}',
             '~': r'\textasciitilde{}',
             '^': r'\^{}'
         }
         for char, escaped in replacements.items():
             text = text.replace(char, escaped)
         return text

     # Similar _format_projects(), _format_skills(), _format_education()...

 Key Benefits:
 - Template-based = 100% correct LaTeX structure
 - Takes JSON input (no LaTeX parsing errors)
 - Deterministic and testable
 - Proper escaping of special characters

 ---
 3. ATSScorer (New Class)

 Validates resume quality using the ats-resume-scorer library.

 class ATSScorer:
     """Scores resumes against job descriptions using ATS simulation."""

     def __init__(self):
         # Install with: pip install ats-resume-scorer
         try:
             from ats_resume_scorer import ATSResumeScorer
             self.scorer = ATSResumeScorer()
         except ImportError:
             print("[WARN] ats-resume-scorer not installed. Run: pip install ats-resume-scorer")
             self.scorer = None

     def score_resume(self, resume_text: str, job_description: str) -> Dict:
         """
         Score resume against job description.

         Returns:
         {
             "overall_score": 78,           # 0-100
             "keyword_match_pct": 65.5,     # percentage
             "missing_keywords": ["Docker", "Kubernetes"],
             "technical_skills_overlap": 80.0,
             "recommendation": "GOOD",      # STRONG/GOOD/FAIR/WEAK
             "should_submit": True          # Based on threshold
         }
         """
         if not self.scorer:
             # Fallback if library not available
             return {
                 "overall_score": 0,
                 "keyword_match_pct": 0,
                 "missing_keywords": [],
                 "recommendation": "UNKNOWN",
                 "should_submit": True  # Don't block if scorer unavailable
             }

         try:
             results = self.scorer.score_resume(
                 resume_text=resume_text,
                 job_description=job_description
             )

             # Normalize results to our format
             score = results.get('overall_score', 0)

             return {
                 "overall_score": score,
                 "keyword_match_pct": results.get('keyword_match', 0),
                 "missing_keywords": results.get('missing_keywords', []),
                 "technical_skills_overlap": results.get('skills_overlap', 0),
                 "recommendation": self._get_recommendation(score),
                 "should_submit": score >= 60  # Threshold: 60+
             }

         except Exception as e:
             print(f"[WARN] ATS scoring failed: {e}")
             return {"overall_score": 0, "should_submit": True}  # Don't block on error

     def _get_recommendation(self, score: int) -> str:
         """Convert score to recommendation level"""
         if score >= 80:
             return "STRONG"
         elif score >= 70:
             return "GOOD"
         elif score >= 60:
             return "FAIR"
         else:
             return "WEAK"

 Benefits:
 - Objective quality metrics before submission
 - Catches poorly-tailored resumes early
 - Provides actionable feedback (missing keywords)
 - Can raise quality bar over time (increase threshold)

 Future enhancements:
 - Retry resume generation if score < threshold
 - A/B test different prompts based on ATS scores
 - Track correlation between ATS score and interview rate

 ---
 4. HybridResumeGenerator (Replacement for ResumeGeneratorChain)

 Main orchestrator that coordinates all components.

 class HybridResumeGenerator:
     """
     Hybrid resume generator: GPT-4o for content, templates for LaTeX.
     Replaces ResumeGeneratorChain.
     """

     def __init__(self):
         self.content_generator = HybridContentGenerator()
         self.latex_builder = LaTeXBuilder()
         self.ats_scorer = ATSScorer()

     def generate_resume(self, job: Dict, resume_template: str) -> Tuple[str, Dict]:
         """
         Generate resume and return (latex_string, ats_metrics).

         Process:
         1. GPT-4o generates content JSON
         2. Template assembles LaTeX
         3. ATS scorer validates quality

         Returns:
             (latex_document, ats_scores_dict)
         """
         print("   [INFO] Generating tailored content with GPT-4o...")
         content_json = self.content_generator.generate_content(job, resume_template)

         print("   [INFO] Assembling LaTeX from template...")
         latex = self.latex_builder.build_resume(content_json)

         # Note: ATS scoring happens AFTER PDF compilation in pipeline
         # This method just returns LaTeX
         return latex, {}  # ATS scores filled in later by pipeline


 Integration point in JobApplicationPipeline:

 # In process_job() method:

 # Step 1: Generate resume (content + LaTeX assembly)
 latex, _ = self.resume_generator.generate_resume(job, self.resume_template)

 # Step 2: Compile to PDF
 pdf_path = compile_latex_to_pdf(latex, filename)

 # Step 3: ATS Scoring (NEW)
 if pdf_path:
     resume_text = extract_text_from_pdf(pdf_path)
     job_desc = json.dumps(job)
     ats_scores = self.ats_scorer.score_resume(resume_text, job_desc)

     print(f"   [INFO] ATS Score: {ats_scores['overall_score']}/100 ({ats_scores['recommendation']}")
     print(f"   [INFO] Keyword Match: {ats_scores['keyword_match_pct']}%")

     if not ats_scores['should_submit']:
         print(f"   [WARN] Low ATS score ({ats_scores['overall_score']}), skipping submission")
         return None  # Skip this job

 # Step 4: Continue with upload, slides, email, sheets (existing code)
 ...

 Benefits of this hybrid:
 - Content quality: GPT-4o's proven job understanding
 - Reliability: 100% valid LaTeX from templates
 - Quality control: ATS validation before submission
 - Cost: ~$0.015/resume (same as current, worth it for quality)
 - Speed: ~6-12s total (5-10s GPT-4o + 1-2s ATS + compilation)

 ---
 Implementation Plan

 Phase 1: Setup (ATS Library + Fix resume_helper.txt)

 Goal: Install dependencies and fix template formatting.

 Tasks:
 1. Install ATS scorer library
 pip install ats-resume-scorer==2.0.0
 2. Create resume_helper_fixed.txt (fix double braces)
 sed 's/{{/{/g; s/}}/}/g' resume_helper.txt > resume_helper_fixed.txt
 3. Test preamble compiles
   - Extract preamble from fixed file
   - Create minimal LaTeX document
   - Run pdflatex to verify no errors

 Files modified:
 - Create: resume_helper_fixed.txt
 - Update: requirements.txt (add ats-resume-scorer)

 Validation:
 - ats-resume-scorer library installs successfully
 - Preamble from resume_helper_fixed.txt compiles without errors
 - All braces balanced

 ---
 Phase 2: Implement Hybrid Components

 Goal: Build the 4 new classes.

 File: job_automation_langchain.py

 Task 2.1: HybridContentGenerator

 Location: Add after line ~1330 (after current ResumeGeneratorChain)

 Changes:
 - Create new CONTENT_GENERATION_PROMPT (JSON output, not LaTeX)
 - Modify to use JsonOutputParser() instead of StrOutputParser()
 - Method signature: generate_content(job, resume_template) -> Dict

 Validation:
 - Returns valid JSON with experiences, projects, skills, education_bullets
 - Content is tailored to job (test with sample job description)

 Task 2.2: LaTeXBuilder

 Location: Add after HybridContentGenerator

 Implementation:
 - Load preamble from resume_helper_fixed.txt in __init__
 - build_resume(content_json) method assembles LaTeX
 - Helper methods: _format_heading(), _format_experience(), _format_projects(), _format_skills(), _format_education()
 - _escape_latex() for special character escaping

 Validation:
 - Generated LaTeX compiles to PDF
 - All braces balanced
 - Special characters (& in Texas A&M) properly escaped

 Task 2.3: ATSScorer

 Location: Add after LaTeXBuilder

 Implementation:
 - Import ats-resume-scorer library
 - score_resume(resume_text, job_description) returns metrics dict
 - Graceful fallback if library not available
 - Threshold logic (60+ = submit)

 Validation:
 - Successfully scores test resume
 - Returns all expected metrics
 - Handles errors gracefully

 Task 2.4: HybridResumeGenerator

 Location: Replace current ResumeGeneratorChain (lines ~1297-1329)

 Changes:
 - Rename class to HybridResumeGenerator
 - Coordinate: content_generator → latex_builder
 - Method signature stays same: generate_resume(job, resume_template) -> str

 Validation:
 - Successfully generates resume from test job
 - Output compiles to PDF
 - Takes ~5-10s (GPT-4o time)

 ---
 Phase 3: Integration

 Goal: Wire up new generator and ATS scoring in pipeline.

 Task 3.1: Update JobApplicationPipeline.init

 File: job_automation_langchain.py, line ~1955

 Change:
 # OLD:
 # self.resume_generator = ResumeGeneratorChain()

 # NEW:
 self.resume_generator = HybridResumeGenerator()
 self.ats_scorer = ATSScorer()  # Add ATS scorer

 Task 3.2: Add ATS Scoring to process_job()

 File: job_automation_langchain.py, line ~2040-2050

 Insert after PDF compilation, before upload:

 # After: pdf_path = compile_latex_to_pdf(...)

 # NEW: ATS Scoring
 print("   [INFO] Scoring resume with ATS simulator...")
 resume_text = self._extract_pdf_text(pdf_path)
 job_desc_str = json.dumps(job, indent=2)
 ats_scores = self.ats_scorer.score_resume(resume_text, job_desc_str)

 print(f"   ATS Score: {ats_scores['overall_score']}/100 ({ats_scores['recommendation']})")
 print(f"   Keyword Match: {ats_scores['keyword_match_pct']:.1f}%")

 if not ats_scores['should_submit']:
     print(f"   [WARN] Skipping due to low ATS score")
     return None

 Task 3.3: Add PDF text extraction helper

 File: job_automation_langchain.py

 Add new utility function:

 def extract_pdf_text(pdf_path: str) -> str:
     """Extract text from PDF for ATS scoring."""
     try:
         import PyPDF2
         with open(pdf_path, 'rb') as f:
             reader = PyPDF2.PdfReader(f)
             text = ""
             for page in reader.pages:
                 text += page.extract_text()
             return text
     except ImportError:
         print("[WARN] PyPDF2 not installed, skipping text extraction")
         return ""
     except Exception as e:
         print(f"[WARN] PDF text extraction failed: {e}")
         return ""

 Task 3.4: Update Google Sheets logging

 File: job_automation_langchain.py, GoogleSheetsClient class

 Modify append_application() to include ATS metrics:

 def append_application(self, data: Dict, ats_scores: Dict = None):
     """Append application with ATS metrics"""
     row = [
         data.get("timestamp"),
         data.get("company"),
         data.get("title"),
         data.get("location"),
         data.get("url"),
         data.get("resume_url"),
         # NEW ATS metrics columns:
         ats_scores.get("overall_score", "") if ats_scores else "",
         ats_scores.get("keyword_match_pct", "") if ats_scores else "",
         ats_scores.get("recommendation", "") if ats_scores else "",
         json.dumps(ats_scores.get("missing_keywords", [])) if ats_scores else ""
     ]
     # ... append to sheet

 ---
 Phase 4: Testing

 Goal: Verify hybrid system works end-to-end.

 Task 4.1: Unit Tests

 1. Test HybridContentGenerator:
 job = {"title": "Frontend Engineer", "description": "React, TypeScript..."}
 content = generator.generate_content(job, resume_template)
 assert "experiences" in content
 assert len(content["experiences"]) > 0
 2. Test LaTeXBuilder:
 latex = builder.build_resume(sample_content_json)
 assert latex.startswith("\\documentclass")
 assert latex.count("{") == latex.count("}")
 3. Test ATSScorer:
 scores = scorer.score_resume(sample_resume_text, sample_job_desc)
 assert "overall_score" in scores
 assert 0 <= scores["overall_score"] <= 100
 4. Test HybridResumeGenerator:
 latex, _ = generator.generate_resume(test_job, resume_template)
 pdf = compile_latex_to_pdf(latex, "test")
 assert pdf is not None

 Task 4.2: Integration Test

 Run on small batch:
 # Edit max_jobs to 5
 python job_automation_langchain.py

 Expected results:
 - 5 jobs processed
 - 4-5 resumes successfully generated (80%+ success)
 - All resumes compile to PDF
 - ATS scores logged for each resume
 - Can see score distribution in Google Sheets

 ---
 Phase 5: Monitoring & Iteration

 Goal: Track performance and optimize over time.

 Metrics to monitor:
 1. Compilation success rate: Should be 95%+ (vs 10% before)
 2. ATS score distribution: Track average, min, max
 3. Interview rate by ATS score: Does 80+ score → more interviews?
 4. Missing keywords: What keywords are we consistently missing?

 Future optimizations:
 1. Raise ATS threshold: Start at 60, increase to 70 or 75 based on results
 2. Retry on low scores: If score < 70, retry with different prompt
 3. A/B test prompts: Test different content generation strategies
 4. Keyword feedback loop: Add missing keywords to resume_template

 ---
 Success Criteria

 Immediate Goals (Phase 1-3)

 - resume_helper_fixed.txt created with single braces
 - All 4 new classes implemented (HybridContentGenerator, LaTeXBuilder, ATSScorer, HybridResumeGenerator)
 - Integration complete (new generator wired up, ATS scoring added)
 - Compilation success rate >= 95%

 Testing Goals (Phase 4)

 - All unit tests pass
 - Integration test shows 80%+ success rate
 - Generated resumes compile to PDF
 - ATS scores logged to Google Sheets

 Strategic Goals (Phase 5)

 - Can measure resume quality objectively (ATS scores)
 - Track correlation between ATS score and interview rate
 - Iterate on prompts based on data
 - Improve average ATS score over time

 ---
 Files Modified

 | File                        | Changes                                     | Lines Affected                                         |
 |-----------------------------|---------------------------------------------|--------------------------------------------------------|
 | resume_helper.txt           | Fix double braces → resume_helper_fixed.txt | All                                                    |
 | job_automation_langchain.py | Add 4 new classes, modify pipeline          | ~1297-1329 (replace), ~1955 (+init), ~2040-2050 (+ATS) |
 | requirements.txt            | Add ats-resume-scorer                       | +1                                                     |
 | Google Sheets schema        | Add ATS metric columns                      | +4 columns                                             |

 ---
 Risk Assessment

 Risk 1: ATS Library Not Accurate

 Impact: Medium (scores don't correlate with real results)
 Mitigation:
 - Track interview rate by ATS score to validate
 - Can swap libraries later (Resume Matcher, custom TF-IDF)
 - Use as directional metric, not absolute truth

 Risk 2: GPT-4o Still Generates Bad JSON

 Impact: Medium (resume generation fails)
 Mitigation:
 - JsonOutputParser handles most parsing issues
 - Add retry logic (3 attempts)
 - Fallback to simpler prompt if JSON parsing fails

 Risk 3: LaTeX Template Bugs

 Impact: Low (deterministic, testable)
 Mitigation:
 - Unit test all _format methods
 - Validate preamble compilation in Phase 1
 - Keep existing validation functions

 Risk 4: Users Game ATS Scores

 Impact: Low (we want good scores!)
 Mitigation:
 - Track interview rate as ground truth
 - Don't over-optimize for score at expense of readability
 - Human review of high-score resumes periodically

 ---
 Next Steps

 1. Get user approval on hybrid approach
 2. Phase 1: Install ats-resume-scorer, fix resume_helper.txt
 3. Phase 2: Implement 4 new classes
 4. Phase 3: Wire up pipeline integration
 5. Phase 4: Test on small batch
 6. Phase 5: Monitor and iterate

 Ready to implement!
