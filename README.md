# applyEasy

Automated job application pipeline: scrapes LinkedIn jobs, generates tailored LaTeX resumes, compiles PDFs, uploads to GitHub, and sends outreach emails with follow-ups.

## Quick Start

### 1. Clone and enter the repo

```
git clone <repo-url>
cd applyEasy
```

### 2. Get credentials

You need these credentials (ask the team lead for existing values):

| Credential | Where to get it |
|---|---|
| Google Service Account JSON | Google Cloud Console > IAM > Service Accounts |
| Gmail OAuth2 tokens | Run `setup_gmail_oauth.py` (see below) |
| OpenAI API key | https://platform.openai.com/api-keys |
| Apify API key | https://console.apify.com/account/integrations |
| GitHub token | https://github.com/settings/tokens (needs `repo` scope) |
| AnyMailFinder API key | https://anymailfinder.com/ |
| Google Sheets/Docs/Slides IDs | From the URL of each Google resource |

### 3. Set up credentials

```
cp .env.example .env
cp service-account.json.example service-account.json
```

Edit `.env` and `service-account.json` with real values.

### 4. Gmail OAuth setup (first time only)

This must be done on a machine with a browser:

```
cp gmail_credentials.json.example gmail_credentials.json
# Edit gmail_credentials.json with your OAuth client config
pip install google-auth-oauthlib google-api-python-client
python setup_gmail_oauth.py
# Copy the output tokens into your .env file
```

### 5. Run with Docker

```
./setup.sh
docker compose run --rm pipeline
```

Or run individual services:

```
docker compose run --rm pipeline    # Job scraping + resume pipeline
docker compose run --rm email       # Email outreach + follow-ups
docker compose run --rm dev         # Interactive shell for debugging
```

### 6. Run without Docker

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

You also need `pdflatex` installed:

```
# Ubuntu/Debian
sudo apt-get install texlive-latex-base texlive-fonts-recommended texlive-latex-extra

# macOS
brew install --cask mactex-no-gui
```

Then run:

```
python job_automation_langchain.py    # Main pipeline
python email_outreach_flow.py        # Email outreach
```

## Project Structure

```
.env.example                  # Credential template
.env                          # Your credentials (git-ignored)
service-account.json          # Google service account key (git-ignored)
gmail_credentials.json        # Gmail OAuth client config (git-ignored)
job_automation_langchain.py   # Main pipeline: scrape, filter, resume, upload
email_outreach_flow.py        # Email outreach with follow-up system
add_sheet_headers.py          # One-time sheet schema setup
setup_gmail_oauth.py          # One-time Gmail OAuth token setup
resume_helper_fixed.txt       # Resume template data
Dockerfile                    # Multi-arch container (AMD64 + ARM64)
docker-compose.yml            # Service definitions
setup.sh                      # Team onboarding script
requirements.txt              # Python dependencies
```

## Troubleshooting

**LaTeX compilation fails**: Check `tex/failed/` for the failed `.tex` file and `_pdflatex.log`. Common causes: missing LaTeX packages, unescaped special characters, mismatched braces.

**Gmail auth fails**: Re-run `python setup_gmail_oauth.py`. Ensure Gmail API is enabled in Google Cloud Console.

**Apify returns no jobs**: Verify `APIFY_API_KEY` is valid and `LINKEDIN_SEARCH_URL` returns results in a browser.

**Google Sheets permission denied**: Share the sheet with your service account email (`name@project.iam.gserviceaccount.com`) as Editor.
