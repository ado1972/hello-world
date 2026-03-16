# SFG Web-Scraper CRM Agent

An AI-powered lead-generation agent that scrapes the entire web to find potential customers for **SFG**, then stores them in a local CRM database.

Built on **Claude Opus 4.6** with built-in `web_search` and `web_fetch` tools — no third-party scraping APIs needed.

---

## How it works

```
You → main.py scrape --query "..."
         │
         ▼
   Claude Opus 4.6
   ┌──────────────────────────────────────────┐
   │  web_search  ──► searches the internet   │
   │  web_fetch   ──► reads pages in detail   │
   │  save_lead   ──► writes to SQLite CRM    │
   └──────────────────────────────────────────┘
         │
         ▼
   crm.db  (SQLite — leads table)
         │
         ▼
   python src/main.py leads   (view results)
```

Claude autonomously decides what to search, which pages to fetch, and what constitutes a strong lead for SFG — using adaptive thinking to reason about the best research strategy.

---

## Quick start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set your API key

```bash
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY and SFG_DESCRIPTION
```

### 3. Run a scraping session

```bash
# Find logistics companies in the Midwest that could use SFG services
python src/main.py scrape \
  --query "logistics and freight companies in the Midwest USA" \
  --max-leads 25

# Find fintech startups
python src/main.py scrape \
  --query "fintech startups Series A Series B needing compliance solutions" \
  --max-leads 15
```

### 4. View your leads

```bash
# All leads
python src/main.py leads

# Only new leads
python src/main.py leads --status new

# CRM stats
python src/main.py stats
```

### 5. Update a lead status

```bash
python src/main.py update 7 --status contacted --notes "Left voicemail, follow up Friday"
```

---

## Configuration

| Variable          | Description                                      |
|-------------------|--------------------------------------------------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key (required)              |
| `SFG_DESCRIPTION`   | Describe SFG so Claude knows who to target     |

**Example `SFG_DESCRIPTION`:**
```
SFG provides fleet-management software for mid-size trucking companies (50–500 trucks).
Our ideal customer is a logistics or freight company that still uses spreadsheets or
legacy dispatch systems and is looking to modernise.
```

---

## Lead statuses

| Status      | Meaning                           |
|-------------|-----------------------------------|
| `new`       | Just discovered (default)         |
| `contacted` | You've reached out                |
| `qualified` | Confirmed as a real opportunity   |
| `closed`    | Deal won                          |
| `rejected`  | Not a fit / not interested        |

---

## Project structure

```
hello-world/
├── src/
│   ├── agent.py   ← Claude agentic loop + tool definitions
│   ├── crm.py     ← SQLite CRM (leads, search_runs tables)
│   └── main.py    ← CLI (scrape / leads / update / stats)
├── requirements.txt
├── .env.example
└── crm.db         ← created automatically on first run
```

---

## Example scraping queries

```bash
# By industry
python src/main.py scrape --query "construction companies in Texas needing project management tools"

# By pain point
python src/main.py scrape --query "restaurants struggling with food waste and inventory management"

# By geography
python src/main.py scrape --query "manufacturing SMBs in the Southeast US hiring operations managers"

# By signal
python src/main.py scrape --query "companies that recently raised Series A in supply chain tech"
```
