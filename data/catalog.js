window.EDUGUIDE_DATA = {
  subjects: [
    { code: "MATH", name: "Mathematics" },
    { code: "ENG", name: "English" },
    { code: "SES", name: "Sesotho" },
    { code: "PSCI", name: "Physical Science" },
    { code: "CSK", name: "Computer Skills" },
    { code: "ACC", name: "Accounting" },
    { code: "BIO", name: "Biology" },
    { code: "AGR", name: "Agriculture" },
    { code: "FNU", name: "Food & Nutrition" },
    { code: "REL", name: "Religious Knowledge" },
    { code: "HIST", name: "History" },
    { code: "GEO", name: "Geography" },
    { code: "PHY", name: "Physics" },
    { code: "CHEM", name: "Chemistry" },
    { code: "ECON", name: "Economics" },
    { code: "LIT", name: "English Literature" }
  ],
  interests: [
    "Technology & IT",
    "Health & Medicine",
    "Business & Finance",
    "Education & Teaching",
    "Agriculture",
    "Law & Government",
    "Engineering",
    "Arts & Design",
    "Social Work",
    "Natural Sciences"
  ],
  sources: [
    {
      name: "National University of Lesotho",
      type: "Official website",
      status: "verified-core",
      url: "https://nul.ls/",
      tags: ["programmes", "requirements", "institution"]
    },
    {
      name: "Limkokwing University Lesotho",
      type: "Official course portal",
      status: "verified-core",
      url: "https://www.portal.co.ls/apply/courses",
      tags: ["programmes", "fees", "requirements"]
    },
    {
      name: "Botho University Lesotho",
      type: "Official programmes page",
      status: "verified-core",
      url: "https://www.bothouniversity.com/lesotho/programmes",
      tags: ["programmes", "institution"]
    },
    {
      name: "Lerotholi Polytechnic",
      type: "Prospectus PDF",
      status: "verified-core",
      url: "https://www.lp.ac.ls/wp-content/uploads/2024/02/lerotholi-prospectus-2024-2025-embed1.pdf",
      tags: ["programmes", "requirements", "duration"]
    },
    {
      name: "Lesotho Agricultural College",
      type: "Prospectus PDF",
      status: "verified-core",
      url: "https://lac.org.ls/wp-content/uploads/2026/01/LAC-2026-2027-PROSPECTUS.pdf",
      tags: ["programmes", "agriculture"]
    },
    {
      name: "NMDS Government Bursary Service",
      type: "Government service page",
      status: "verified-core",
      url: "https://www.gov.ls/eservice/ministry-of-finance-and-development-planning-23/",
      tags: ["scholarships", "bursary", "NMDS"]
    },
    {
      name: "Lesotho Labour Force Survey 2024",
      type: "Official report PDF",
      status: "verified-core",
      url: "https://finance.gov.ls/PDFDocuments/2024%20LFS%20REPORT%2002_JULY%202025%20608-638874863136847407.pdf",
      tags: ["labour", "employment", "sectors"]
    }
  ],
  programmes: [
    {
      id: "nul-bsc-computer-science",
      title: "BSc Computer Science",
      institution: "National University of Lesotho",
      shortInstitution: "NUL",
      faculty: "Science & Technology",
      level: "Degree",
      duration: "4 years",
      status: "approved",
      source: "https://nul.ls/",
      subjects: ["MATH", "ENG", "PSCI"],
      interests: ["Technology & IT", "Natural Sciences"],
      requirements: ["Mathematics A-C", "English A-C", "Physical Science A-C"],
      careers: ["Software Developer", "Data Analyst", "Systems Analyst", "Cybersecurity Analyst"],
      skills: ["Programming", "Problem solving", "Database management", "Networking"],
      labourSector: "Information & Communications Technology",
      nmdsPriority: 86
    },
    {
      id: "luct-bsc-information-technology",
      title: "BSc Information Technology",
      institution: "Limkokwing University Lesotho",
      shortInstitution: "LUCT",
      faculty: "ICT",
      level: "Degree",
      duration: "3 years",
      status: "approved",
      source: "https://www.portal.co.ls/apply/courses",
      subjects: ["MATH", "ENG", "PSCI"],
      interests: ["Technology & IT", "Arts & Design"],
      requirements: ["Mathematics A-D", "English A-C", "Computer Studies recommended"],
      careers: ["IT Support Specialist", "Web Developer", "Network Administrator"],
      skills: ["Web development", "IT support", "Project management"],
      labourSector: "Information & Communications Technology",
      nmdsPriority: 76
    },
    {
      id: "nul-beng-electrical-engineering",
      title: "BEng Electrical Engineering",
      institution: "National University of Lesotho",
      shortInstitution: "NUL",
      faculty: "Engineering",
      level: "Degree",
      duration: "4 years",
      status: "approved",
      source: "https://nul.ls/",
      subjects: ["MATH", "ENG", "PSCI"],
      interests: ["Engineering", "Natural Sciences"],
      requirements: ["Mathematics A-B", "Physical Science A-B", "English A-C"],
      careers: ["Electrical Engineer", "Telecoms Engineer", "Project Engineer"],
      skills: ["Circuit design", "Mathematics", "Technical drawing", "Problem solving"],
      labourSector: "Engineering & Construction",
      nmdsPriority: 88
    },
    {
      id: "nul-bcom-accounting-finance",
      title: "BCom Accounting & Finance",
      institution: "National University of Lesotho",
      shortInstitution: "NUL",
      faculty: "Commerce",
      level: "Degree",
      duration: "3 years",
      status: "approved",
      source: "https://nul.ls/",
      subjects: ["MATH", "ENG", "ACC", "ECON"],
      interests: ["Business & Finance"],
      requirements: ["Mathematics A-C", "Accounting A-C", "English A-C"],
      careers: ["Accountant", "Financial Analyst", "Auditor", "Banking Officer"],
      skills: ["Accounting", "Financial reporting", "Data analysis", "Ethics"],
      labourSector: "Financial Services",
      nmdsPriority: 72
    },
    {
      id: "lac-diploma-agriculture",
      title: "Diploma in Agriculture",
      institution: "Lesotho Agricultural College",
      shortInstitution: "LAC",
      faculty: "Agriculture",
      level: "Diploma",
      duration: "3 years",
      status: "approved",
      source: "https://lac.org.ls/wp-content/uploads/2026/01/LAC-2026-2027-PROSPECTUS.pdf",
      subjects: ["ENG", "BIO", "PSCI", "AGR"],
      interests: ["Agriculture", "Natural Sciences"],
      requirements: ["English A-D", "Biology or Agriculture A-D", "Chemistry recommended"],
      careers: ["Agricultural Extension Officer", "Farm Manager", "Agribusiness Officer"],
      skills: ["Crop production", "Soil management", "Agribusiness", "Field research"],
      labourSector: "Agriculture",
      nmdsPriority: 80
    },
    {
      id: "rcn-diploma-nursing",
      title: "Diploma in General Nursing",
      institution: "Roma College of Nursing",
      shortInstitution: "RCN",
      faculty: "Health Sciences",
      level: "Diploma",
      duration: "3 years",
      status: "approved",
      source: "https://www.che.ac.ls/roma-college-of-nursing-rcn-accredited-programmes/",
      subjects: ["ENG", "BIO", "PSCI", "MATH"],
      interests: ["Health & Medicine", "Social Work"],
      requirements: ["English A-C", "Biology A-C", "Chemistry or Physical Science A-C"],
      careers: ["Registered Nurse", "Community Health Nurse", "Clinic Officer"],
      skills: ["Patient care", "Communication", "Biology", "Record keeping"],
      labourSector: "Health & Social Services",
      nmdsPriority: 86
    }
  ],
  labourNotes: [
    {
      sector: "Information & Communications Technology",
      note: "Government e-services, banking systems, telecoms, and school digitisation create steady demand for practical IT skills."
    },
    {
      sector: "Engineering & Construction",
      note: "Infrastructure, energy, roads, water projects, and telecoms can support engineering pathways when technical requirements are strong."
    },
    {
      sector: "Financial Services",
      note: "Banking, insurance, accounting, and fintech roles are concentrated around Maseru and require strong numeracy."
    },
    {
      sector: "Agriculture",
      note: "Food systems, extension services, climate adaptation, and agribusiness make agriculture useful beyond traditional farming."
    },
    {
      sector: "Health & Social Services",
      note: "Health programmes align with public clinics, hospitals, community health work, and NGO services."
    }
  ]
};
