# Data Shortages After Current Scrape

Generated after scraping the provided institution links.

## Strong Extracts

- Limkokwing University Lesotho: 29 programmes from the official course portal. Missing durations and fees.
- Botho University Lesotho: 21 programmes from the official programme bundle. Missing fees and needs Lesotho-campus confirmation.
- Lerotholi Polytechnic: 22 programmes from the official prospectus PDF. Needs deeper requirements parsing and fees.
- Centre for Accounting Studies: 8 course/programme records from official course pages. Some requirements captured; application fee and acceptance fee are now confirmed manually.
- Centre for Accounting Studies handbook: programme levels, progression rules, registration rules, and fee policy captured manually. CAS application fee is M450 and acceptance fee is M1200. Tuition-per-module and professional-body fee amounts are still missing.
- National University of Lesotho: 129 programme-like records from official faculty pages after splitting IEMS into its own institution. Needs duplicate/context cleanup. NUL 2024/25 and 2026/27 fee tables have now been captured.
- NUL Institute of Extra Mural Studies (IEMS): 7 programme-like records split out from NUL, plus 2026/27 IEMS-ODL fee rows captured from the NUL prospectus DOCX.
- Lesotho College of Education: 6 records now captured. The 2 new B.Ed programmes include duration, entry requirements, delivery mode, careers, and B.Ed fees from official local PDFs.
- Paray School of Nursing: 3 records captured from the supplied text-readable 2024/25 prospectus PDF. Durations, entry requirements, fees, modules, NMDS note, and contact details were available.

## Partial Extracts

- Lesotho College of Education legacy programmes: 4 older diploma/certificate names remain from a third-party page. Their requirements and current status still need official confirmation.
- Lesotho Agricultural College: 5 programme names from CHE pages. LAC prospectus PDF blocked/timed out, so requirements and fees are missing.
- Roma College of Nursing: 2 accredited programme names from CHE page. Missing requirements, duration, and fees.

## Manual Collection Needed

- National Teachers Training College: provided link is only a contact/profile listing. Need official programme list/prospectus.
- Machabeng College: provided site is school/admissions focused, not a higher-education programme catalogue. Needs scope decision.
- LUCT tuition: finance page loads but fee values are not exposed in static HTML. Need portal interaction/login/manual capture.
- Imperial Business College: BBA and BHCM were visually extracted from the supplied outlined-font PDF, but the institution is in Kathmandu, Nepal and needs a scope decision before being treated as a normal Lesotho recommendation source. Fees were not found.
- Scribd documents: useful for cross-checking, but the viewer pages do not expose reliable document text to the scraper.

## Manual Data Added

- NUL Fee Structure 2024/25: faculty/programme fee bands captured for Local & SADC and International students.
- NUL Prospectus 2026/27 DOCX: official grade scale and detailed NUL/IEMS fee tables captured for Local & SADC and International students.
- Paray School of Nursing Prospectus 2024/25: Certificate in Nursing Assistant, Diploma in Nursing, Diploma in Midwifery, requirements, fees, modules, and NMDS note captured from supplied local PDF.
- Imperial Business College Prospectus 2018/19: BBA and BHCM programme records added for admin review from visual PDF extraction; automated text extraction cannot read the outlined content.
- CAS Student Handbook Volume 4: ACCA/CIMA/CIPFA structure, entry rules, attendance, registration, fee policy, M450 application fee, and M1200 acceptance fee captured. Exact module and professional-body fee amounts still needed from CAS Accounts Office or fee schedule.
- LCE B.Ed programme PDF and 2025/26 fee structure: new B.Ed Primary Education and B.Ed Preschool/Foundation Phase Education added alongside older LCE records. Application fee discrepancy is flagged for review.
