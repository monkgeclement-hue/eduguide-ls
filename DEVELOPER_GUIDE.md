# Developer Guide — EduGuide Lesotho

Welcome to the EduGuide Lesotho project! This guide helps developers understand, extend, and maintain the application.

## Table of Contents

1. [Project Overview](#project-overview)
2. [Getting Started](#getting-started)
3. [Project Structure](#project-structure)
4. [Core Concepts](#core-concepts)
5. [Development Workflow](#development-workflow)
6. [Working with Data](#working-with-data)
7. [API Development](#api-development)
8. [Frontend Development](#frontend-development)
9. [Testing](#testing)
10. [Deployment](#deployment)
11. [Troubleshooting](#troubleshooting)

---

## Project Overview

**EduGuide Lesotho** is a web application that helps students discover and research education programmes across Lesotho's top institutions.

### Key Statistics
- **233+ Programmes** catalogued from 10+ institutions
- **8 Categories** (Technology, Business, Education, etc.)
- **156 Career Paths** mapped to programmes
- **12 Institutions** represented

### Technology Stack

**Backend:**
- Python 3.10+
- FastAPI (modern async framework)
- Uvicorn (ASGI server)
- JSON-based data storage

**Frontend:**
- HTML5 + CSS3
- Vanilla JavaScript (no frameworks)
- Service Worker (PWA)
- Progressive Web App support

**Data:**
- JSON files (programmes.flat.json)
- Supabase (production database)
- Git version control

**Deployment:**
- Render.com (production)
- GitHub Actions (CI/CD)
- Docker containers

---

## Getting Started

### Prerequisites

- **Python 3.10+** (`python --version`)
- **Node.js** (optional, for frontend tools)
- **Git** (for version control)
- **VS Code** (recommended)

### Initial Setup

```bash
# 1. Clone the repository
git clone https://github.com/monkgeclement-hue/eduguide-ls.git
cd eduguide-ls

# 2. Create Python virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# or
source venv/bin/activate  # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start the development server
python -m uvicorn server:app --reload --host 127.0.0.1 --port 8765

# 5. Open browser
# Navigate to http://127.0.0.1:8765
```

### Verify Setup

```bash
# Check Python version
python --version  # Should be 3.10 or higher

# Check FastAPI installation
python -c "import fastapi; print(fastapi.__version__)"

# Test server startup (should see "Application startup complete")
python server.py
```

---

## Project Structure

```
eduguide-ls/
│
├── 📄 server.py                    # Backend API (FastAPI)
├── 📄 app.js                       # Frontend JavaScript logic
├── 📄 index.html                   # Main HTML template
├── 📄 styles.css                   # Application styling
├── 📄 requirements.txt             # Python dependencies
├── 📄 Dockerfile                   # Docker configuration
├── 📄 render.yaml                  # Render deployment config
│
├── 📁 data/                        # Data directory
│   ├── real/
│   │   ├── 📄 programmes.flat.json ⭐ MAIN DATABASE
│   │   ├── programmes.by-institution.json
│   │   ├── summary.json
│   │   └── 📁 fees/                # Fee structure files
│   │       ├── nul-fee-structure-2024-2025.json
│   │       ├── iems-fee-structure-2026-2027.json
│   │       └── ... more institutions
│   ├── 📄 README.md                # Data documentation
│   └── 📁 uploads/                 # User uploads
│
├── 📁 scripts/                     # Data processing scripts
│   ├── 📄 scrape-real-programmes.py
│   ├── 📄 build-admin-catalog.py
│   ├── 📄 enrich-catalogue.py
│   └── 📄 automate-data-population.py ⭐ AUTOMATION
│
├── 📁 supabase/                    # Database configuration
│   ├── 📄 schema.sql
│   ├── 📄 seed.sql
│   └── 📄 runtime.sql
│
├── 📁 icons/                       # Application icons
├── 📁 .github/                     # GitHub workflows (CI/CD)
│
└── 📋 DOCUMENTATION FILES
    ├── README.md                   # Main project README
    ├── QUICK_REFERENCE.md          # Quick start guide
    ├── API_DOCUMENTATION.md        # API endpoint reference
    ├── AUTOMATION.md               # Data enrichment guide
    ├── data-enrichment.conf        # Enrichment configuration
    ├── DEPLOYMENT.md               # Deployment procedures
    └── PRODUCTION_SETUP.md         # Production checklist
```

---

## Core Concepts

### 1. Programme Object

Every programme in the database has this structure:

```python
Programme = {
    "id": str,                      # Unique ID (kebab-case)
    "institution": str,             # Institution name
    "name": str,                    # Programme name
    "category": str,                # Field category
    "level": str,                   # degree/diploma/certificate
    "duration": str,                # e.g., "4 years with project"
    "requirements_summary": str,    # Entry requirements
    "career_options": list[str],    # 4 relevant careers
    "source_url": str,              # Where it came from
    "review_status": str,           # approved/needs_review
    "supporting_fee_source_path": str,  # Path to fee file (optional)
    "fee_note": str                 # Fee description (optional)
}
```

### 2. Career Path Mapping

Career paths are intelligently matched to programmes using regex patterns:

```python
CAREER_PATH_MAPPING = {
    r"(computer|it|software|network)": [
        "Software Developer",
        "Systems Analyst",
        "Database Administrator",
        "IT Support Specialist"
    ]
    # ... more patterns
}
```

### 3. Institution Standardization

All institution names are standardized:
- National University of Lesotho (not NUL)
- Limkokwing University Lesotho (not Limkokwing-ULS)
- Consistent capitalization and spacing

### 4. Review Status Workflow

```
Programmes flow through review states:

Initial Data
    ↓
[manual_entry | scraped_data | needs_admin_review]
    ↓
Enrichment Applied
    ↓
[approved]  ← Ready for display
    ↓
Published
    ↓
[In Production]
```

---

## Development Workflow

### Daily Development

```bash
# 1. Start fresh
git fetch origin
git pull origin main

# 2. Create feature branch
git checkout -b feature/your-feature-name

# 3. Make changes
# ... edit files ...

# 4. Test locally
python -m uvicorn server:app --reload

# 5. Commit changes
git add .
git commit -m "feat: clear description of changes"

# 6. Push to GitHub
git push origin feature/your-feature-name

# 7. Create Pull Request on GitHub
# → Review → Merge → Auto-deploy
```

### Code Style

**Python (PEP 8):**
```python
# Good
def get_programmes_by_category(category: str) -> list:
    """Retrieve all programmes for a category."""
    return [p for p in programmes if p["category"] == category]

# Avoid
def getProgsByCategory(cat):
    return [p for p in programmes if p["category"] == cat]
```

**JavaScript (ES6+):**
```javascript
// Good
const filterByInstitution = (programmes, institution) => {
  return programmes.filter(p => p.institution === institution);
};

// Avoid
function filterByInstitution(programmes, institution) {
  var result = [];
  for (var i = 0; i < programmes.length; i++) {
    if (programmes[i].institution === institution) {
      result.push(programmes[i]);
    }
  }
  return result;
}
```

### Commit Message Format

```
<type>: <subject>

<body>

<footer>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

```bash
# Example
git commit -m "feat: add career path search filter

- Allow filtering programmes by specific career paths
- Add career filter UI component
- Update API to support career parameter

Closes #42"
```

---

## Working with Data

### Loading Programmes

```python
# In server.py
import json
from pathlib import Path

def load_programmes():
    path = Path("data/real/programmes.flat.json")
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

programmes = load_programmes()
```

```javascript
// In app.js
async function loadProgrammes() {
  const response = await fetch('/api/programmes');
  const { data } = await response.json();
  return data;
}

let programmes = await loadProgrammes();
```

### Enriching Data

```bash
# Run the enrichment automation
python automate-data-population.py

# This will:
# 1. Add career paths if missing
# 2. Add duration rules from institutions
# 3. Link fee structures
# 4. Filter Botho to Lesotho-only offerings
# 5. Update review_status to "approved"
```

### Verifying Data Changes

```bash
# Before committing, check what changed
git diff data/real/programmes.flat.json | head -50

# See summary of changes
git diff --stat data/real/programmes.flat.json

# Preview specific programme changes
git diff data/real/programmes.flat.json | grep -A 5 "programme-name"
```

### Adding New Programmes

```python
# Method 1: Manual addition in JSON file
{
  "id": "new-institution-new-programme",
  "institution": "New Institution",
  "name": "New Programme Name",
  "category": "Technology & ICT",
  "level": "degree",
  "duration": null,  # Will be filled by enrichment
  "requirements_summary": "Entry requirements...",
  "career_options": null,  # Will be filled by enrichment
  "source_url": "https://...",
  "review_status": "needs_admin_review"
}

# Method 2: Use enrichment automation
# The script will add missing career paths and duration automatically
python automate-data-population.py
```

---

## API Development

### Adding a New Endpoint

```python
# In server.py
from fastapi import FastAPI, Query
from typing import Optional

app = FastAPI()

@app.get("/api/programmes")
async def get_programmes(
    institution: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(100),
    offset: int = Query(0)
):
    """Get programmes with optional filtering."""
    programmes = load_programmes()
    
    # Apply filters
    if institution:
        programmes = [p for p in programmes if p["institution"] == institution]
    if level:
        programmes = [p for p in programmes if p["level"] == level]
    if category:
        programmes = [p for p in programmes if p["category"] == category]
    
    # Apply pagination
    return {
        "status": "success",
        "data": programmes[offset:offset+limit],
        "count": len(programmes),
        "total": len(load_programmes())
    }
```

### Testing Endpoints

```bash
# Test in PowerShell
$response = Invoke-WebRequest -Uri "http://localhost:8765/api/programmes?level=degree"
$response.Content | ConvertFrom-Json | Select-Object -ExpandProperty data | Get-Member

# Or use curl
curl "http://localhost:8765/api/programmes?institution=NUL"
curl "http://localhost:8765/api/programmes?category=Technology"
```

### API Documentation

All endpoints are documented in [API_DOCUMENTATION.md](API_DOCUMENTATION.md).

---

## Frontend Development

### Main JavaScript File (app.js)

```javascript
// Global state
let programmes = [];
let filteredProgrammes = [];
let currentFilters = {};

// Load data on startup
async function initialize() {
  programmes = await fetch('/api/programmes')
    .then(r => r.json())
    .then(d => d.data);
  
  displayProgrammes(programmes);
}

// Filter programmes
function filterProgrammes(filters) {
  currentFilters = filters;
  filteredProgrammes = programmes.filter(p => {
    return Object.entries(filters).every(([key, value]) => {
      if (!value) return true;  // Skip empty filters
      
      if (key === "career_options") {
        return p.career_options?.includes(value);
      }
      return p[key] === value;
    });
  });
  
  displayProgrammes(filteredProgrammes);
}

// Display programmes in DOM
function displayProgrammes(items) {
  const container = document.getElementById("programmes-container");
  container.innerHTML = items.map(p => `
    <div class="programme-card">
      <h3>${p.name}</h3>
      <p><strong>${p.institution}</strong> — ${p.level}</p>
      <p>${p.duration}</p>
      <p><em>${p.category}</em></p>
      <div class="careers">
        ${p.career_options?.map(c => `<span class="tag">${c}</span>`).join("")}
      </div>
    </div>
  `).join("");
}
```

### Styling (styles.css)

```css
/* Layout */
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

/* Programme cards */
.programme-card {
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.programme-card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  transition: all 0.2s;
}

/* Career tags */
.tag {
  display: inline-block;
  background: #e7f3ff;
  color: #0066cc;
  padding: 4px 12px;
  border-radius: 20px;
  margin: 4px 4px 4px 0;
  font-size: 0.9em;
}
```

---

## Testing

### Manual Testing

```bash
# 1. Start server
python -m uvicorn server:app --reload

# 2. Test in browser
# http://localhost:8765/

# 3. Test API endpoints
# http://localhost:8765/api/programmes
# http://localhost:8765/api/programmes?level=degree
# http://localhost:8765/api/institutions

# 4. Test search
# http://localhost:8765/api/search?q=software

# 5. Check console for errors (F12)
```

### Smoke Testing

```bash
# Run smoke tests (if available)
powershell -ExecutionPolicy Bypass -File smoke-test.ps1
```

### Data Validation

```bash
# Check JSON is valid
python -c "import json; json.load(open('data/real/programmes.flat.json'))"

# Check required fields exist
python -c "
import json
programmes = json.load(open('data/real/programmes.flat.json'))
required = ['id', 'name', 'institution', 'level', 'career_options']
for p in programmes:
    for field in required:
        assert field in p, f'Missing {field} in {p.get(\"id\")}'"
```

---

## Deployment

### Local Testing (Before Deploy)

```bash
# 1. Build and test Docker image
docker build -t eduguide-ls .
docker run -p 8765:8765 eduguide-ls

# 2. Test endpoints
curl http://localhost:8765/api/programmes

# 3. Check all data loads correctly
# Open http://localhost:8765 in browser
```

### Deploying to Production

```bash
# 1. Commit changes
git add .
git commit -m "feat: describe your feature"

# 2. Push to main
git push origin main

# 3. GitHub Actions automatically:
#    - Runs tests
#    - Builds Docker image
#    - Deploys to Render.com

# 4. Monitor deployment
# https://dashboard.render.com
```

For detailed deployment info, see [DEPLOYMENT.md](DEPLOYMENT.md) and [PRODUCTION_SETUP.md](PRODUCTION_SETUP.md).

---

## Troubleshooting

### Server won't start

```bash
# Check port is available
netstat -ano | findstr :8765

# Kill process on port 8765 (Windows)
taskkill /PID <PID> /F

# Try different port
python -m uvicorn server:app --port 8766
```

### Programmes not loading

```bash
# Verify JSON file exists and is valid
python -c "import json; json.load(open('data/real/programmes.flat.json'))" 

# Check file path in server.py
# Should be: Path("data/real/programmes.flat.json")

# Verify data/real/ directory exists
ls data/real/programmes.flat.json  # Should show file
```

### API returns 404

```bash
# Verify endpoint exists in server.py
grep -n "@app.get" server.py

# Check route matches exactly
# /api/programmes (correct) not /api/programme (wrong)

# Test with curl
curl "http://localhost:8765/api/programmes"
```

### Enrichment script fails

```bash
# Check Python version
python --version  # Should be 3.10+

# Verify data file exists
ls data/real/programmes.flat.json

# Run with verbose output
python -u automate-data-population.py

# Check error message
python automate-data-population.py 2>&1 | head -20
```

### Git conflicts

```bash
# Abort merge and start over
git merge --abort

# Update your branch
git fetch origin
git rebase origin/main

# If conflicts, resolve manually then:
git add .
git rebase --continue
```

---

## Resources

📖 **Documentation:**
- [README.md](README.md) — Project overview
- [API_DOCUMENTATION.md](API_DOCUMENTATION.md) — API reference
- [QUICK_REFERENCE.md](QUICK_REFERENCE.md) — Quick start
- [AUTOMATION.md](AUTOMATION.md) — Data enrichment
- [data/README.md](data/README.md) — Data structure

💻 **External Resources:**
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Supabase Documentation](https://supabase.com/docs)
- [Render.com Docs](https://render.com/docs)
- [Python Official](https://python.org)

🤝 **Getting Help:**
- Check existing GitHub Issues
- Review commit history: `git log --oneline`
- Ask in pull request reviews
- Check troubleshooting section above

---

## Next Steps

1. **Set up development environment** (see Getting Started)
2. **Read the API Documentation** to understand endpoints
3. **Explore the data** in `data/real/programmes.flat.json`
4. **Try running a feature** (filter, search, etc.)
5. **Make a small change** and test locally
6. **Create a pull request** for code review

**Happy coding! 🚀**

---

**Version**: 1.0  
**Last Updated**: 2025  
**Maintainer**: EduGuide LS Development Team
