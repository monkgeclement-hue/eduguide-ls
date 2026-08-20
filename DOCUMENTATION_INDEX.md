# EduGuide Documentation Index

Complete documentation reference for the EduGuide Lesotho education programme discovery platform.

## 📚 Documentation by Audience

### For New Developers
Start here if you're joining the team:

1. **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** — 10-minute overview
   - Project snapshot
   - Quick start commands
   - Key files and automation features
   - Common tasks with code examples

2. **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)** — Complete development handbook
   - Environment setup
   - Project architecture
   - Development workflow
   - Testing procedures
   - Deployment guide

3. **[API_DOCUMENTATION.md](API_DOCUMENTATION.md)** — API endpoint reference
   - All endpoints with parameters
   - Response formats and examples
   - Error handling
   - Rate limiting and CORS

### For Data Managers
Working with the programme database:

1. **[data/README.md](data/README.md)** — Data structure and governance
   - Directory structure
   - Data enrichment automation
   - Quality metrics
   - Maintenance procedures
   - Data governance workflow

2. **[AUTOMATION.md](AUTOMATION.md)** — Data enrichment tool guide
   - Career path mapping system
   - Institution-specific duration rules
   - Fee structure linking
   - Botho filtering logic
   - Customization instructions

3. **[data-enrichment.conf](data-enrichment.conf)** — Configuration reference
   - Career path patterns
   - Institution rules
   - Fee mappings
   - Validation rules

### For DevOps / Production
Deployment and operations:

1. **[DEPLOYMENT.md](DEPLOYMENT.md)** — Deployment procedures
   - Manual deployment steps
   - Server configuration
   - Environment variables
   - Monitoring setup

2. **[PRODUCTION_SETUP.md](PRODUCTION_SETUP.md)** — Production checklist
   - Pre-deployment validation
   - Performance tuning
   - Security configuration
   - Backup procedures

### For Project Managers
Project overview and team info:

1. **[README.md](README.md)** — Main project README
   - Project overview
   - Technology stack
   - Installation instructions
   - Contributing guidelines

---

## 📋 Documentation Files Reference

| File | Purpose | Audience | Length |
|------|---------|----------|--------|
| [README.md](README.md) | Project overview | All | ~150 lines |
| [QUICK_REFERENCE.md](QUICK_REFERENCE.md) | 10-minute quickstart | Developers | ~200 lines |
| [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) | Complete dev handbook | Developers | ~700 lines |
| [API_DOCUMENTATION.md](API_DOCUMENTATION.md) | API endpoint reference | Developers | ~400 lines |
| [AUTOMATION.md](AUTOMATION.md) | Data enrichment guide | Data team | ~200 lines |
| [data-enrichment.conf](data-enrichment.conf) | Enrichment config | Data team | ~100 lines |
| [data/README.md](data/README.md) | Data structure | Data team | ~300 lines |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Deployment guide | DevOps | ~200 lines |
| [PRODUCTION_SETUP.md](PRODUCTION_SETUP.md) | Production checklist | DevOps | ~150 lines |
| **DOCUMENTATION_INDEX.md** | **This file** | **All** | **~400 lines** |

---

## 🚀 Quick Start Paths

### Path 1: I want to run the project locally
1. Read [QUICK_REFERENCE.md](QUICK_REFERENCE.md) — "Quick Start" section
2. Follow setup commands to get server running
3. Open http://localhost:8765 in browser

**Estimated time:** 5 minutes

---

### Path 2: I want to understand the API
1. Read [API_DOCUMENTATION.md](API_DOCUMENTATION.md) — "Overview" and "Endpoints" sections
2. Try API calls: curl or browser
3. Reference response formats for integration

**Estimated time:** 20 minutes

---

### Path 3: I want to modify data
1. Read [data/README.md](data/README.md) — "Data Governance" section
2. Review [AUTOMATION.md](AUTOMATION.md) — "Customization" section
3. Edit [data-enrichment.conf](data-enrichment.conf) if needed
4. Run enrichment: `python automate-data-population.py`

**Estimated time:** 30 minutes

---

### Path 4: I want to add a feature
1. Read [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) — "Getting Started" to "Development Workflow"
2. Set up development environment
3. Create feature branch: `git checkout -b feature/your-feature`
4. Make changes and test locally
5. Commit and push, then create pull request

**Estimated time:** 1-2 hours depending on feature complexity

---

### Path 5: I want to deploy to production
1. Read [DEPLOYMENT.md](DEPLOYMENT.md) — "Before You Deploy" section
2. Review [PRODUCTION_SETUP.md](PRODUCTION_SETUP.md) — full checklist
3. Run smoke tests: `powershell -File smoke-test.ps1`
4. Push to main branch (auto-deploys via GitHub Actions)
5. Monitor at Render.com dashboard

**Estimated time:** 1 hour

---

## 🎯 Key Concepts Explained

### Career Path Mapping
- **What:** Intelligent assignment of career paths to programmes based on programme name
- **How:** Regex pattern matching against 11+ discipline categories
- **Where:** [AUTOMATION.md](AUTOMATION.md#career-path-mapping) and [data-enrichment.conf](data-enrichment.conf)
- **Example:** "BSc Software Engineering" matches pattern → gets ["Software Developer", "Systems Analyst", ...]

### Institution Duration Rules
- **What:** Institution-specific duration standards for each programme level
- **How:** Look up institution + level, apply predefined duration
- **Where:** [AUTOMATION.md](AUTOMATION.md#duration-rules) and [data-enrichment.conf](data-enrichment.conf)
- **Example:** NUL degree = "5 years with attachment and project"

### Botho Filtering
- **What:** Filter Botho University to only Lesotho-based programmes
- **How:** Check for "Lesotho" in programme text, exclude Botswana-only offerings
- **Where:** [AUTOMATION.md](AUTOMATION.md#botho-filtering)
- **Example:** Removes 1 non-Lesotho offering from 234 total

### Review Status Workflow
- **What:** Tracks whether a programme is approved for display
- **States:** `needs_admin_review`, `approved`, `archived`
- **Where:** [data/README.md](data/README.md#data-governance)
- **Current:** All 233 programmes marked "approved"

---

## 🔍 Finding Information

### By Topic

**API & Endpoints:**
- Overview: [API_DOCUMENTATION.md](API_DOCUMENTATION.md#overview)
- Specific endpoint: [API_DOCUMENTATION.md](API_DOCUMENTATION.md#endpoints)
- Curl examples: [API_DOCUMENTATION.md](API_DOCUMENTATION.md#examples)
- Error handling: [API_DOCUMENTATION.md](API_DOCUMENTATION.md#error-responses)

**Data & Database:**
- Structure: [data/README.md](data/README.md#directory-structure)
- Adding programmes: [data/README.md](data/README.md#adding-new-programmes)
- Governance: [data/README.md](data/README.md#data-governance)
- Quality metrics: [data/README.md](data/README.md#data-quality-notes)

**Automation:**
- How it works: [AUTOMATION.md](AUTOMATION.md#how-it-works)
- Career mapping: [AUTOMATION.md](AUTOMATION.md#career-path-mapping)
- Customizing: [AUTOMATION.md](AUTOMATION.md#customization)
- Troubleshooting: [AUTOMATION.md](AUTOMATION.md#troubleshooting)

**Code & Development:**
- Setup: [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md#getting-started)
- Architecture: [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md#project-structure)
- Making changes: [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md#development-workflow)
- API dev: [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md#api-development)
- Frontend: [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md#frontend-development)

**Deployment:**
- Step-by-step: [DEPLOYMENT.md](DEPLOYMENT.md)
- Production checklist: [PRODUCTION_SETUP.md](PRODUCTION_SETUP.md)
- Troubleshooting: [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md#troubleshooting)

### By Problem

**"How do I get started?"**
→ [QUICK_REFERENCE.md](QUICK_REFERENCE.md)

**"How do I run it locally?"**
→ [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md#getting-started)

**"What's the API?"**
→ [API_DOCUMENTATION.md](API_DOCUMENTATION.md)

**"How do I add/modify programmes?"**
→ [data/README.md](data/README.md#adding-new-programmes)

**"How do I run the enrichment?"**
→ [AUTOMATION.md](AUTOMATION.md#usage)

**"How do I deploy?"**
→ [DEPLOYMENT.md](DEPLOYMENT.md)

**"Something's broken, help!"**
→ [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md#troubleshooting)

**"What should I do before deploying?"**
→ [PRODUCTION_SETUP.md](PRODUCTION_SETUP.md)

---

## 📊 Project Statistics

**Programme Database:**
- Total programmes: 233
- Total institutions: 12
- Total categories: 8
- Total career paths: 156

**Enrichment Coverage:**
- Programmes with career paths: 100%
- Programmes with duration: 100%
- Programmes with fee references: ~40%
- Programmes marked "approved": 100%

**Documentation Coverage:**
- Core functionality: 100% documented
- API endpoints: 100% documented
- Deployment procedures: 100% documented
- Code examples: Included throughout

---

## 🔗 Repository Links

**GitHub:**
- Repository: https://github.com/monkgeclement-hue/eduguide-ls
- Main branch: All documentation in root directory
- Commits: Check `git log` for deployment history

**Production:**
- Live site: https://eduguide-ls.onrender.com
- API base: https://eduguide-ls.onrender.com/api
- Dashboard: https://dashboard.render.com

**Data:**
- Master programmes file: `data/real/programmes.flat.json`
- Fee structures: `data/real/fees/`
- Institutions data: `data/real/institutions/`

---

## 📝 Documentation Maintenance

### Keeping Docs Updated

When you make changes:

1. **Modify code:**
   - Update relevant documentation sections
   - Add examples if introducing new patterns
   - Update statistics if data changes

2. **Add a new feature:**
   - Document in [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)
   - Add API endpoint to [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
   - Update [README.md](README.md) feature list

3. **Modify data:**
   - Update statistics in [data/README.md](data/README.md)
   - Document changes in [data-enrichment.conf](data-enrichment.conf)
   - Add to [AUTOMATION.md](AUTOMATION.md) if rule changes

4. **Update deployment:**
   - Modify [DEPLOYMENT.md](DEPLOYMENT.md) and [PRODUCTION_SETUP.md](PRODUCTION_SETUP.md)
   - Test procedures locally first
   - Get peer review before merging

### Documentation Style Guide

- **Markdown format:** Standard GitHub Flavored Markdown
- **Code blocks:** Use triple backticks with language identifier
- **Headings:** Use `#` for H1, `##` for H2, etc.
- **Links:** Use relative paths `[text](file.md#section)`
- **Examples:** Include working code snippets
- **Tables:** Use GitHub markdown tables for structured data

---

## 🤝 Contributing to Documentation

### Process

1. **Identify gap:** Find missing or unclear documentation
2. **Create branch:** `git checkout -b docs/topic-name`
3. **Make changes:** Edit relevant .md files
4. **Commit:** `git commit -m "docs: clear description"`
5. **Push:** `git push origin docs/topic-name`
6. **PR:** Create pull request for review

### Review Checklist

- [ ] Markdown format is valid
- [ ] Examples are tested and working
- [ ] Links are correct and relative paths work
- [ ] Information is accurate and current
- [ ] Tone is clear and helpful
- [ ] No spelling or grammar errors

---

## 📞 Getting Help

**For Questions About:**

- **API:** See [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
- **Data:** See [data/README.md](data/README.md)
- **Development:** See [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)
- **Deployment:** See [DEPLOYMENT.md](DEPLOYMENT.md)
- **Automation:** See [AUTOMATION.md](AUTOMATION.md)

**If Not Found:**

1. Check troubleshooting section of relevant doc
2. Search GitHub Issues
3. Review commit history: `git log --oneline`
4. Ask in pull request or team chat

---

## 📅 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jan 2025 | Initial comprehensive documentation suite |

---

## 🎓 Learning Resources

**External:**
- [FastAPI Docs](https://fastapi.tiangolo.com)
- [Python 3 Guide](https://docs.python.org/3/)
- [Git Documentation](https://git-scm.com/doc)
- [Markdown Guide](https://www.markdownguide.org/)

**In This Project:**
- [All documentation files](.) — Start with README.md
- [API examples](API_DOCUMENTATION.md#examples)
- [Code examples](DEVELOPER_GUIDE.md)
- [Configuration reference](data-enrichment.conf)

---

**Last Updated:** January 2025  
**Maintained By:** EduGuide LS Team  
**Documentation Version:** 1.0
