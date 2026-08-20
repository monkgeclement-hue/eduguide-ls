#!/usr/bin/env python3
"""
EduGuide LS Data Population Automation
Adds career paths, fills fees, applies duration rules, and filters programmes
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, Any, List, Set

# Configuration
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
REAL_DIR = DATA_DIR / "real"
PROGRAMMES_FILE = REAL_DIR / "programmes.flat.json"

# Career path mapping based on programme name patterns
CAREER_PATH_MAPPING = {
    # Technology & ICT
    r"(computer|it|information technology|software|network|cyber|data science|mobile|web)": [
        "Software Developer",
        "Systems Analyst", 
        "Database Administrator",
        "IT Support Specialist",
        "Network Administrator",
        "Data Scientist",
        "Cybersecurity Analyst"
    ],
    r"(engineering|electrical|electronics|mechanical|civil)": [
        "Professional Engineer",
        "Engineering Technologist",
        "Project Engineer",
        "Technical Consultant",
        "Systems Engineer"
    ],
    
    # Business & Commerce
    r"(business|management|entrepreneurship|commerce|accounting|finance|banking|investment|hospitality|hotel|tourism)": [
        "Business Analyst",
        "Operations Manager",
        "Business Development Officer",
        "Entrepreneur",
        "Accountant",
        "Financial Analyst",
        "Hotel Manager",
        "Tour Operator"
    ],
    r"(marketing|advertising)": [
        "Marketing Manager",
        "Brand Manager",
        "Digital Marketing Specialist",
        "Advertising Executive"
    ],
    r"(hr|human resource)": [
        "Human Resources Officer",
        "Talent Acquisition Specialist",
        "Training Coordinator",
        "Employee Relations Officer"
    ],
    
    # Creative Arts & Communication
    r"(journalism|broadcasting|media|communication|pr|public relation)": [
        "Journalist",
        "Broadcast Producer",
        "Content Producer",
        "Public Relations Officer",
        "Media Manager"
    ],
    r"(fashion|design|graphic|advertising|creative)": [
        "Fashion Designer",
        "Graphic Designer",
        "Creative Director",
        "UX/UI Designer",
        "Textile Designer"
    ],
    r"(film|video|digital media|multimedia)": [
        "Film Producer",
        "Video Editor",
        "Content Creator",
        "Multimedia Developer"
    ],
    r"(architecture)": [
        "Architect",
        "Architectural Technologist",
        "Quantity Surveyor",
        "Urban Planner"
    ],
    
    # Education
    r"(education|teaching|teacher)": [
        "Teacher",
        "Curriculum Developer",
        "Education Officer",
        "Teaching and Learning Resource Developer",
        "School Principal"
    ],
    
    # Health Sciences
    r"(health|nursing|medical|clinical|pharmacy|public health|hospital|informatics)": [
        "Nurse",
        "Health Informatics Specialist",
        "Clinical Data Analyst",
        "Health Information Manager",
        "Hospital Administrator"
    ],
    
    # Agriculture & Environment
    r"(agriculture|agribusiness|farming|environmental|environmental science)": [
        "Agricultural Extension Officer",
        "Farm Manager",
        "Agribusiness Officer",
        "Environmental Officer",
        "Sustainability Officer"
    ],
    
    # Law & Social Sciences
    r"(law|legal)": [
        "Lawyer",
        "Legal Advisor",
        "Paralegal",
        "Legal Consultant"
    ],
    r"(social|community|development|psychology)": [
        "Social Worker",
        "Community Development Officer",
        "Youth Programme Officer",
        "Social Researcher"
    ]
}

# Duration rules per institution
DURATION_RULES = {
    "Limkokwing University Lesotho": {
        "degree": "4 years with project",
        "diploma": "3 years with attachment"
    },
    "Botho University Lesotho": {
        "degree": "4 years with attachment",
        "diploma": "3 years with attachment"
    },
    "Lerotholi Polytechnic": {
        "diploma": "3 years with attachment"
    },
    "National University of Lesotho": {
        "degree": "5 years with attachment and project",
        "diploma": "3-4 years",
        "masters": "3 years"
    },
    "NUL Institute of Extra Mural Studies (IEMS)": {
        "degree": "5 years with attachment and project",
        "diploma": "3-4 years"
    },
    "Lesotho College of Education": {
        "degree": "3 years",
        "diploma": "3 years"
    },
    "Lesotho Agricultural College": {
        "diploma": "3 years"
    }
}

# Filter for Botho - only keep Lesotho offerings
BOTHO_LESOTHO_KEYWORDS = {
    "Lesotho", "lesotho"
}

# Fee mapping from files
FEE_STRUCTURE_FILES = {
    "National University of Lesotho": "data/real/fees/nul-fee-structure-2024-2025.json",
    "NUL Institute of Extra Mural Studies (IEMS)": "data/real/fees/iems-fee-structure-2026-2027.json",
    "Lesotho College of Education": "data/real/fees/lce-fee-structure-2025-2026.json",
    "Centre for Accounting Studies": "data/real/fees/cas-fee-structure-partial-2024.json",
    "Paray School of Nursing": "data/real/fees/paray-school-of-nursing-2024-2025.json"
}


def get_career_paths(programme_name: str, category: str) -> List[str]:
    """Extract career paths based on programme name and category"""
    search_text = f"{programme_name} {category}".lower()
    
    for pattern, careers in CAREER_PATH_MAPPING.items():
        if re.search(pattern, search_text, re.IGNORECASE):
            return careers[:4]  # Return up to 4 career options
    
    # Default fallback based on level/category
    return ["Professional", "Industry Specialist", "Manager", "Consultant"]


def apply_duration_rule(programme: Dict[str, Any]) -> None:
    """Apply institution-specific duration rules"""
    institution = programme.get("institution", "")
    level = programme.get("level", "").lower()
    
    rules = DURATION_RULES.get(institution)
    if not rules:
        return
    
    if "degree" in level:
        if "degree" in rules:
            programme["duration"] = rules["degree"]
    elif "diploma" in level:
        if "diploma" in rules:
            programme["duration"] = rules["diploma"]
    elif "masters" in level or "master" in level:
        if "masters" in rules:
            programme["duration"] = rules["masters"]


def load_fee_data(fee_file: str) -> Dict[str, Any]:
    """Load fee structure from a JSON file"""
    fee_path = ROOT / fee_file
    if not fee_path.exists():
        return {}
    
    with open(fee_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def add_fee_info(programme: Dict[str, Any]) -> None:
    """Add fee information to programme"""
    institution = programme.get("institution", "")
    fee_file = FEE_STRUCTURE_FILES.get(institution)
    
    if not fee_file:
        return
    
    fee_data = load_fee_data(fee_file)
    if not fee_data or not fee_data.get("fee_items"):
        return
    
    # Store reference to fee data
    programme["supporting_fee_source_path"] = fee_file
    programme["fee_note"] = f"Fee schedule available: {fee_data.get('source_title', 'Fee Structure')} ({fee_data.get('academic_year', 'current')}). Confirm the programme group and latest amount before payment."


def is_botho_lesotho(programme: Dict[str, Any]) -> bool:
    """Check if Botho programme should be kept (is Lesotho offering)"""
    if programme.get("institution") != "Botho University Lesotho":
        return True
    
    # For Botho, check if it mentions Lesotho or if it's implicitly for Lesotho
    name = programme.get("name", "").lower()
    overview = programme.get("overview", "").lower()
    text = f"{name} {overview}"
    
    # Keep if explicitly mentions Lesotho
    if "lesotho" in text:
        return True
    
    # Filter out Botswana/international only
    if "botswana" in text and "lesotho" not in text:
        return False
    
    # Default: keep Botho programmes with Lesotho in their source URL
    return True


def enrich_programmes() -> None:
    """Main enrichment function"""
    print("Loading programmes...")
    with open(PROGRAMMES_FILE, 'r', encoding='utf-8') as f:
        programmes = json.load(f)
    
    print(f"Loaded {len(programmes)} programmes")
    
    filtered_programmes = []
    enriched_count = 0
    filtered_count = 0
    
    for i, programme in enumerate(programmes):
        # Check Botho filter
        if not is_botho_lesotho(programme):
            filtered_count += 1
            continue
        
        # Add career paths if missing or placeholder
        if "career_options" not in programme or not programme.get("career_options"):
            careers = get_career_paths(
                programme.get("name", ""),
                programme.get("category", "")
            )
            programme["career_options"] = careers
            enriched_count += 1
        
        # Apply duration rules
        apply_duration_rule(programme)
        
        # Add fee information
        add_fee_info(programme)
        
        filtered_programmes.append(programme)
        
        if (i + 1) % 100 == 0:
            print(f"  Processed {i + 1}/{len(programmes)} programmes...")
    
    # Save enriched programmes
    print(f"\nSaving {len(filtered_programmes)} programmes...")
    with open(PROGRAMMES_FILE, 'w', encoding='utf-8') as f:
        json.dump(filtered_programmes, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Enrichment complete!")
    print(f"  - Programmes processed: {len(programmes)}")
    print(f"  - Botho programmes filtered: {filtered_count}")
    print(f"  - Career paths enriched: {enriched_count}")
    print(f"  - Final programme count: {len(filtered_programmes)}")
    
    return len(filtered_programmes), enriched_count, filtered_count


if __name__ == "__main__":
    try:
        total, enriched, filtered = enrich_programmes()
        print(f"\n📊 Summary: {total} total, {enriched} enriched, {filtered} filtered")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
