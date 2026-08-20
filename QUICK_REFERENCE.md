# EduGuide LS - Quick Reference Guide

## What This Project Does

**EduGuide Lesotho** is a comprehensive education programme discovery platform for Lesotho. It aggregates data from 10+ educational institutions, providing students with:
- Searchable catalogue of 233+ programmes
- Career path guidance for each programme
- Fee information and cost comparisons
- Duration and entry requirements
- Institution profiles and contact info

## Key Files & What They Do

| File | Purpose | Type |
|------|---------|------|
| `server.py` | Backend API (FastAPI/Uvicorn) | Python |
| `app.js` | Frontend application logic | JavaScript |
| `index.html` | Main UI template | HTML |
| `styles.css` | Application styling | CSS |
| `data/real/programmes.flat.json` | ⭐ Main programme database | JSON |
| `automate-data-population.py` | Data enrichment automation | Python |
| `AUTOMATION.md` | How enrichment works | Documentation |

## Quick Start

### Run the Development Server
```bash
# Terminal tab 1: Start the backend
py -m uvicorn server:app --reload --host 127.0.0.1 --port 8765

# Terminal tab 2: Open in browser
# Navigate to http://127.0.0.1:8765
```

Or use VS Code task:
- Press `Ctrl+Shift+B`
- Select "Run EduGuide LS"

### Enriching Programme Data
```bash
# Automatically add career paths, duration, fees to programmes
python automate-data-population.py

# Then commit changes
git add data/real/programmes.flat.json
git commit -m "data: refresh programme enrichments"
git push
```

## Data Structure

### One Programme Record
```json
{
  "id": "nul-ba-international-relations",
  "institution": "National University of Lesotho",
  "name": "BA in International Relations",
  "category": "Law & Social Sciences",
  "level": "Degree",
  "duration": "5 years with attachment and project",
  "requirements_summary": "5 O-level passes...",
  "source_url": "https://nul.ls/programmes",
  "review_status": "approved",
  "career_options": [
    "Diplomat",
    "UN Official",
    "Policy Analyst",
    "International NGO Officer"
  ],
  "supporting_fee_source_path": "data/real/fees/nul-fee-structure-2024-2025.json"
}
```

## Common Tasks

### Search for a Programme
```javascript
// In app.js
const results = programmes.filter(p => 
  p.name.toLowerCase().includes("business")
);
```

### Filter by Career Path
```javascript
const techJobs = programmes.filter(p =>
  p.career_options?.includes("Software Developer")
);
```

### Group by Institution
```javascript
const grouped = {};
programmes.forEach(p => {
  if (!grouped[p.institution]) grouped[p.institution] = [];
  grouped[p.institution].push(p);
});
```

### Get Fees for a Programme
```javascript
// 1. Get supporting_fee_source_path from programme
// 2. Load that JSON file
// 3. Match programme level and institution
// 4. Display tuition, registration, total cost
```

## Key Automation Features

### 1. Career Path Matching
Automatically assigns 4 relevant careers based on programme name:
- **"Software Engineering"** → Developer, Systems Analyst, DBA, IT Support
- **"Fashion Design"** → Fashion Designer, Textile Designer, Buyer, Retail Manager
- **"Business Management"** → Business Analyst, Operations Manager, etc.

### 2. Duration Rules
Sets consistent programme length by institution and level:
- **Limkokwing Degree**: 4 years with project
- **NUL Degree**: 5 years with attachment and project
- **Diploma**: 3-4 years typically

### 3. Botho University Filter
Only keeps Lesotho-based Botho offerings (removes Botswana-only programmes)

### 4. Fee Linking
Connects programmes to fee structure files for pricing info

## Project Structure

```
New project/
├── server.py                    ← Backend API
├── app.js                       ← Frontend logic
├── index.html                   ← UI template
├── styles.css                   ← Styling
├── automate-data-population.py  ← Data enrichment
├── AUTOMATION.md                ← Automation guide
├── data-enrichment.conf         ← Configuration
│
├── data/
│   ├── real/
│   │   ├── programmes.flat.json ← ⭐ Main database
│   │   ├── fees/                ← Fee structures
│   │   ├── institutions/        ← Institution profiles
│   │   └── README.md            ← Data documentation
│   └── README.md
│
├── scripts/
│   ├── scrape-real-programmes.py
│   ├── build-admin-catalog.py
│   └── enrich-catalogue.py
│
└── supabase/
    ├── schema.sql
    └── seed.sql
```

## Deployment

### Local Development
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run server
python server.py

# 3. Open http://127.0.0.1:8765 in browser
```

### Production (Render.com)
```bash
# Automated via GitHub + render.yaml
# Push to main branch → Deploy automatically
git push origin main
```

See [PRODUCTION_SETUP.md](PRODUCTION_SETUP.md) and [DEPLOYMENT.md](DEPLOYMENT.md) for details.

## API Endpoints

| Endpoint | Returns | Parameters |
|----------|---------|------------|
| `GET /` | HTML page | — |
| `GET /api/programmes` | All programmes | `?institution`, `?level`, `?category` |
| `GET /api/programmes/:id` | Single programme | — |
| `GET /api/institutions` | All institutions | — |
| `GET /search?q=...` | Search results | `q`: search query |

## Troubleshooting

**Server won't start?**
- Check port 8765 is available: `netstat -ano | findstr :8765`
- Clear cache: `pip install --force-reinstall uvicorn`

**Programmes not showing?**
- Check `review_status` is "approved" in JSON
- Verify `data/real/programmes.flat.json` exists and is valid JSON

**Enrichment not working?**
- Run: `python automate-data-population.py`
- Check for error messages
- See [AUTOMATION.md](AUTOMATION.md) troubleshooting section

**Deployment issues?**
- Check [DEPLOYMENT.md](DEPLOYMENT.md)
- Review Render.com logs: https://dashboard.render.com

## Team Contacts

- **Data Maintenance**: See scripts/ for data sourcing
- **Development**: See README.md for contribution guidelines
- **Deployment**: Check PRODUCTION_SETUP.md

## Resources

📖 [AUTOMATION.md](AUTOMATION.md) — Data enrichment details  
📖 [DEPLOYMENT.md](DEPLOYMENT.md) — Deployment procedures  
📖 [PRODUCTION_SETUP.md](PRODUCTION_SETUP.md) — Production checklist  
📖 [data/README.md](data/README.md) — Data structure & governance  
📖 [README.md](README.md) — Full project documentation

---

**Quick Command Reference:**

```bash
# Start server
py -m uvicorn server:app --reload

# Enrich data
python automate-data-population.py

# Git workflow
git add .
git commit -m "description"
git push

# Check status
git status
git log --oneline -5
```

**Version**: 1.0  
**Last Updated**: 2025  
**Status**: Production Ready
