insert into public.subjects (code, name) values
  ('MATH', 'Mathematics'),
  ('ENG', 'English'),
  ('SES', 'Sesotho'),
  ('PHY', 'Physics'),
  ('CHEM', 'Chemistry'),
  ('BIO', 'Biology'),
  ('CS', 'Computer Science'),
  ('ACC', 'Accounting'),
  ('COM', 'Commerce'),
  ('HIST', 'History'),
  ('GEO', 'Geography'),
  ('AGR', 'Agriculture')
on conflict (code) do update set name = excluded.name;

insert into public.institutions (name, short_name, institution_type, district, website_url, verification_status) values
  ('National University of Lesotho', 'NUL', 'university', 'Maseru', 'https://nul.ls/', 'verified'),
  ('Limkokwing University Lesotho', 'LUCT', 'university', 'Maseru', 'https://www.portal.co.ls/apply/courses', 'verified'),
  ('Botho University Lesotho', 'Botho', 'university', 'Maseru', 'https://www.bothouniversity.com/lesotho/programmes', 'verified'),
  ('Lerotholi Polytechnic', 'LP', 'polytechnic', 'Maseru', 'https://www.lp.ac.ls/', 'verified'),
  ('Lesotho Agricultural College', 'LAC', 'college', 'Maseru', 'https://lac.org.ls/', 'verified'),
  ('Roma College of Nursing', 'RCN', 'college', 'Maseru', 'https://www.che.ac.ls/roma-college-of-nursing-rcn-accredited-programmes/', 'verified'),
  ('Centre for Accounting Studies', 'CAS', 'college', 'Maseru', 'https://cas.ac.ls/', 'verified'),
  ('Lesotho College of Education', 'LCE', 'college', null, 'https://mabumbe.com/official-lesotho-college-education-lce-courses/', 'needs_review'),
  ('Paray School of Nursing', 'Paray', 'college', null, 'https://www.scribd.com/document/763854725/2024-2025-Final-Prospectus', 'needs_review'),
  ('National Teachers Training College', 'NTTC', 'college', 'Maseru', 'https://www.africanadvice.com/1374130/Colleges/Lesotho/National_Teachers_Training_College/', 'needs_review'),
  ('Machabeng College', 'Machabeng', 'school', 'Maseru', 'https://machcoll.co.ls/', 'needs_review')
on conflict (name) do update set
  short_name = excluded.short_name,
  website_url = excluded.website_url,
  verification_status = excluded.verification_status;

insert into public.source_documents (name, source_type, url, trust_level) values
  ('National University of Lesotho homepage', 'official_website', 'https://nul.ls/', 'verified_core'),
  ('National University of Lesotho - Science and Technology', 'official_academic_programmes_page', 'https://nul.ls/faculty-of-science-and-technology/academic-programmes/', 'verified_core'),
  ('National University of Lesotho - Humanities', 'official_academic_programmes_page', 'https://nul.ls/humanities/academic-programmes/', 'verified_core'),
  ('National University of Lesotho - Law', 'official_academic_programmes_page', 'https://nul.ls/faculty-of-law/academic-programmes/', 'verified_core'),
  ('National University of Lesotho - Social Sciences', 'official_academic_programmes_page', 'https://nul.ls/faculty-of-social-sciences/academic-programmes/', 'verified_core'),
  ('National University of Lesotho - Education', 'official_academic_programmes_page', 'https://nul.ls/faculty-of-education/academic-programmes/', 'verified_core'),
  ('National University of Lesotho - Agriculture', 'official_academic_programmes_page', 'https://nul.ls/faculty-of-agriculture/academic-programmes/', 'verified_core'),
  ('National University of Lesotho - IEMS homepage', 'official_branch_page', 'https://nul.ls/iems-2/', 'verified_core'),
  ('National University of Lesotho - IEMS academic programmes', 'official_academic_programmes_page', 'https://nul.ls/iems-2/academic-programmes/', 'verified_core'),
  ('Limkokwing University Lesotho courses', 'official_course_portal', 'https://www.portal.co.ls/apply/courses', 'verified_core'),
  ('Limkokwing University Lesotho tuition', 'official_finance_portal', 'https://www.portal.co.ls/student-portal/finance/tuition', 'verified_core'),
  ('Botho University Lesotho programmes', 'official_programmes_page', 'https://www.bothouniversity.com/lesotho/programmes', 'verified_core'),
  ('Botho University Lesotho prospectus on Scribd', 'scribd_prospectus', 'https://www.scribd.com/document/846880410/Botho-University-Lesotho-Prospectus-2025-1', 'third_party'),
  ('National Teachers Training College profile', 'third_party_profile', 'https://www.africanadvice.com/1374130/Colleges/Lesotho/National_Teachers_Training_College/', 'third_party'),
  ('Lerotholi Polytechnic prospectus 2024-2025', 'prospectus_pdf', 'https://www.lp.ac.ls/wp-content/uploads/2024/02/lerotholi-prospectus-2024-2025-embed1.pdf', 'verified_core'),
  ('Lesotho College of Education courses', 'third_party_courses_page', 'https://mabumbe.com/official-lesotho-college-education-lce-courses/', 'third_party'),
  ('Paray School of Nursing prospectus', 'scribd_prospectus', 'https://www.scribd.com/document/763854725/2024-2025-Final-Prospectus', 'third_party'),
  ('Lesotho Agricultural College accredited programmes', 'official_regulator_page', 'https://www.che.ac.ls/lesotho-agricultural-college-lac-accredited-programmes/', 'verified_core'),
  ('Lesotho Agricultural College profile', 'official_regulator_page', 'https://www.che.ac.ls/lesotho-agricultural-college-profile/', 'verified_core'),
  ('Roma College of Nursing accredited programmes', 'official_regulator_page', 'https://www.che.ac.ls/roma-college-of-nursing-rcn-accredited-programmes/', 'verified_core'),
  ('Machabeng College homepage', 'official_website', 'https://machcoll.co.ls/', 'verified_core'),
  ('Machabeng College fee structure on Scribd', 'scribd_fee_document', 'https://www.scribd.com/document/997795506/Fee-Structure-2024-2024', 'third_party'),
  ('Centre for Accounting Studies', 'official_course_pages', 'https://cas.ac.ls/', 'verified_core'),
  ('Scribd home', 'document_search', 'https://www.scribd.com/home', 'third_party'),
  ('Lesotho Agricultural College prospectus 2026-2027', 'prospectus_pdf', 'https://lac.org.ls/wp-content/uploads/2026/01/LAC-2026-2027-PROSPECTUS.pdf', 'verified_core'),
  ('Lesotho Agricultural College school listing', 'third_party_profile', 'https://www.schoolandcollegelistings.com/LS/Maseru/105145030832776/Lesotho-Agricultural-College', 'third_party'),
  ('School and College Listings Lesotho', 'directory', 'https://www.schoolandcollegelistings.com/LS', 'third_party'),
  ('NMDS Government Bursary Service', 'government_service', 'https://www.gov.ls/eservice/ministry-of-finance-and-development-planning-23/', 'verified_core'),
  ('Lesotho Labour Force Survey 2024', 'government_report_pdf', 'https://finance.gov.ls/PDFDocuments/2024%20LFS%20REPORT%2002_JULY%202025%20608-638874863136847407.pdf', 'verified_core')
on conflict (url) do update set
  name = excluded.name,
  source_type = excluded.source_type,
  trust_level = excluded.trust_level;

insert into public.scholarships (name, provider, description, eligibility_summary, source_url, review_status, status) values
  (
    'NMDS Sponsorship/Bursary',
    'National Manpower Development Secretariat',
    'Government sponsorship pathway for eligible Lesotho students.',
    'Eligibility depends on academic, programme, application, and background factors. Final approval is not determined by EduGuide LS.',
    'https://www.gov.ls/eservice/ministry-of-finance-and-development-planning-23/',
    'approved',
    'approved'
  )
on conflict (provider, name) do update set
  description = excluded.description,
  eligibility_summary = excluded.eligibility_summary,
  source_url = excluded.source_url,
  review_status = excluded.review_status,
  status = excluded.status;
