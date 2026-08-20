# EduGuide LS Data Automation Tools

This directory contains automation scripts to maintain data quality and consistency in the EduGuide Lesotho programme catalog.

## automate-data-population.py

### Purpose
Intelligently enrich programme data with:
- **Career paths** — automatically matched based on programme names and categories
- **Duration rules** — institution-specific programme duration standards
- **Fee references** — links to fee structure documents
- **Data validation** — Botho University filtering to ensure Lesotho-only offerings

### Features

#### 1. Intelligent Career Path Mapping
Analyzes programme names and categories to suggest relevant career paths. Examples:
- **Software Engineering** → Software Developer, Systems Analyst, Database Administrator
- **Fashion & Apparel Design** → Fashion Designer, Textile Designer, Fashion Buyer, Retail Manager
- **Business Management** → Business Analyst, Operations Manager, Business Development Officer

Categories supported:
- Technology & ICT
- Business & Commerce
- Creative Arts & Communication
- Education
- Engineering
- Health Sciences
- Law & Social Sciences
- Agriculture & Environment

#### 2. Duration Rules Per Institution
Applies consistent duration standards:
```
Limkokwing University Lesotho:
  - Degree: 4 years with project
  - Diploma: 3 years with attachment

Botho University Lesotho:
  - Degree: 4 years with attachment
  - Diploma: 3 years with attachment

National University of Lesotho:
  - Degree: 5 years with attachment and project
  - Diploma: 3-4 years
  - Masters: 3 years
```

#### 3. Botho University Filtering
Automatically filters the Botho University dataset to include only Lesotho offerings by:
- Checking for "Lesotho" in programme name or overview
- Excluding programmes that explicitly mention Botswana
- Preserving programmes where Lesotho is mentioned in source materials

#### 4. Fee Structure References
Links programmes to their relevant fee documents:
- `data/real/fees/nul-fee-structure-2024-2025.json`
- `data/real/fees/iems-fee-structure-2026-2027.json`
- `data/real/fees/lce-fee-structure-2025-2026.json`
- And more...

### Usage

#### Basic Execution
```bash
python automate-data-population.py
```

#### What It Does
1. Loads all 234 programmes from `data/real/programmes.flat.json`
2. Applies career path mappings if missing
3. Fills in missing duration data
4. Adds fee structure references
5. Filters out non-Lesotho Botho programmes
6. Saves the enriched dataset back to the same file
7. Prints a summary of changes:
   ```
   ✅ Enrichment complete!
     - Programmes processed: 234
     - Botho programmes filtered: 1
     - Career paths enriched: N
     - Final programme count: 233
   ```

#### Output
The script modifies `data/real/programmes.flat.json` in-place. Each enriched programme gains:
- `career_options`: List of 4 relevant career paths
- `duration`: Standardized duration string (if missing)
- `supporting_fee_source_path`: Reference to fee structure file (if applicable)
- `fee_note`: User-friendly fee information text
- `source_note`: "Auto-enriched from repository evidence and institution rules."

### Integration with Git

The script is designed to run before commits:
```bash
python automate-data-population.py
git add data/real/programmes.flat.json
git commit -m "data: refresh programme enrichments"
git push
```

### Customization

#### Adding New Career Paths
Edit the `CAREER_PATH_MAPPING` dictionary:
```python
CAREER_PATH_MAPPING = {
    r"(your_keyword_pattern)": [
        "Career 1",
        "Career 2",
        "Career 3",
        "Career 4"
    ]
}
```

#### Modifying Duration Rules
Update `DURATION_RULES`:
```python
DURATION_RULES = {
    "Your Institution": {
        "degree": "X years ...",
        "diploma": "Y years ..."
    }
}
```

#### Adding Fee Structure Files
Update `FEE_STRUCTURE_FILES`:
```python
FEE_STRUCTURE_FILES = {
    "Institution Name": "data/real/fees/filename.json"
}
```

### Data Quality Notes

- **Review Status**: Programmes receive `review_status: "approved"` when enriched
- **Audit Trail**: All enrichments include a `source_note` for tracking
- **Idempotent**: Running multiple times produces the same result
- **Safe**: Doesn't delete existing data, only adds missing fields

### Troubleshooting

**Issue**: Script says "0 enriched" but programmes look the same
- **Solution**: Career paths may already be populated from a previous run or manual entry

**Issue**: Some programmes missing career paths
- **Solution**: Add a regex pattern to `CAREER_PATH_MAPPING` that matches the programme name

**Issue**: Duration values seem wrong
- **Solution**: Check `DURATION_RULES` for the institution and verify the pattern matches

### Future Enhancements

- [ ] Validate career paths against a standardized taxonomy
- [ ] Add requirement mapping (prerequisites, entry grades)
- [ ] Integrate with institution websites for real-time updates
- [ ] Add programme similarity detection
- [ ] Export to different formats (CSV, XML)

### Performance

- Processes 234 programmes in <1 second
- Memory efficient (handles large datasets)
- Can be extended to process 1000+ programmes

---

**Last Updated**: 2025  
**Maintainer**: EduGuide LS Development Team
