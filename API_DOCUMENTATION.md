# EduGuide LS API Documentation

## Overview

The EduGuide API provides access to Lesotho's education programme database through a RESTful interface built with FastAPI.

**Base URL**: `http://localhost:8765` (development) | `https://eduguide-ls.onrender.com` (production)

## Authentication

EduGuide LS uses authenticated sessions for protected API resources.

Public resources include the application shell, static catalogue
assets, and the minimal /health readiness endpoint.

Student-specific resources such as AI guidance, documents, account
data, and shared application state require an authenticated user.

Administrative endpoints, including database diagnostics, catalogue
management, reporting, user administration, and protected state
changes, require an administrator account.

## Response Format

All responses are JSON with standard HTTP status codes:

```json
{
  "status": "success|error",
  "data": {},
  "error": null,
  "timestamp": "2025-01-20T10:30:00Z"
}
```

## Endpoints

### GET /

Returns the HTML homepage.

**Response**: HTML document

---

### GET /api/programmes

Returns all programmes or filtered results.

**Parameters:**
```
GET /api/programmes
GET /api/programmes?institution=National%20University%20of%20Lesotho
GET /api/programmes?level=degree
GET /api/programmes?category=Technology
GET /api/programmes?institution=NUL&level=degree
```

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `institution` | string | Filter by institution name | `National University of Lesotho` |
| `level` | string | Filter by level (degree/diploma) | `degree` |
| `category` | string | Filter by category | `Technology & ICT` |
| `limit` | integer | Max results (default: all) | `10` |
| `offset` | integer | Skip first N results (default: 0) | `20` |

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "id": "nul-ba-international-relations",
      "institution": "National University of Lesotho",
      "name": "BA in International Relations",
      "category": "Law & Social Sciences",
      "level": "degree",
      "duration": "5 years with attachment and project",
      "career_options": ["Diplomat", "UN Official", "Policy Analyst", "International NGO Officer"],
      "requirements_summary": "5 O-level passes including English and Mathematics",
      "review_status": "approved",
      "source_url": "https://nul.ls/programmes/ba-international-relations"
    }
  ],
  "count": 42,
  "total": 233
}
```

**Status Codes:**
- `200 OK` — Success
- `400 Bad Request` — Invalid parameters
- `404 Not Found` — No results

---

### GET /api/programmes/:id

Returns a single programme by ID.

**Parameters:**
```
GET /api/programmes/nul-ba-international-relations
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Programme ID (kebab-case) |

**Response:**
```json
{
  "status": "success",
  "data": {
    "id": "nul-ba-international-relations",
    "institution": "National University of Lesotho",
    "name": "BA in International Relations",
    "category": "Law & Social Sciences",
    "level": "degree",
    "duration": "5 years with attachment and project",
    "requirements_summary": "5 O-level passes...",
    "career_options": [
      "Diplomat",
      "UN Official",
      "Policy Analyst",
      "International NGO Officer"
    ],
    "source_url": "https://nul.ls/programmes/ba-international-relations",
    "review_status": "approved",
    "supporting_fee_source_path": "data/real/fees/nul-fee-structure-2024-2025.json",
    "fee_note": "Fee schedule available in supporting fee source",
    "source_note": "Auto-enriched from repository evidence and institution rules."
  }
}
```

**Status Codes:**
- `200 OK` — Success
- `404 Not Found` — Programme not found

---

### GET /api/institutions

Returns all institutions in the database.

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "name": "National University of Lesotho",
      "code": "nul",
      "acronym": "NUL",
      "website": "https://nul.ls",
      "programme_count": 54,
      "levels": ["degree", "diploma", "masters"]
    },
    {
      "name": "Limkokwing University Lesotho",
      "code": "limkokwing",
      "acronym": "LUMO",
      "website": "https://lesotho.limkokwing.net",
      "programme_count": 38,
      "levels": ["degree", "diploma"]
    }
  ],
  "count": 12
}
```

**Status Codes:**
- `200 OK` — Success

---

### GET /api/institutions/:code

Returns details for a single institution.

**Parameters:**
```
GET /api/institutions/nul
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `code` | string | Institution code (lowercase) |

**Response:**
```json
{
  "status": "success",
  "data": {
    "name": "National University of Lesotho",
    "code": "nul",
    "acronym": "NUL",
    "website": "https://nul.ls",
    "phone": "+266 2231 5000",
    "email": "info@nul.ls",
    "programmes": [
      {
        "id": "nul-ba-international-relations",
        "name": "BA in International Relations",
        "level": "degree"
      }
    ],
    "programme_count": 54,
    "levels": ["degree", "diploma", "masters"]
  }
}
```

---

### GET /api/search

Full-text search across programmes and institutions.

**Parameters:**
```
GET /api/search?q=software
GET /api/search?q=engineering&type=programme
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `q` | string | Search query (required) |
| `type` | string | Filter by type: `programme`, `institution`, or both (default) |
| `limit` | integer | Max results (default: 20) |

**Response:**
```json
{
  "status": "success",
  "data": {
    "programmes": [
      {
        "id": "limkokwing-bsc-software-engineering",
        "name": "BSc Software Engineering",
        "institution": "Limkokwing University Lesotho",
        "category": "Technology & ICT"
      }
    ],
    "institutions": [
      {
        "name": "Limkokwing University Lesotho",
        "code": "limkokwing"
      }
    ]
  }
}
```

---

### GET /api/categories

Returns all programme categories.

**Response:**
```json
{
  "status": "success",
  "data": [
    "Technology & ICT",
    "Business & Commerce",
    "Creative Arts & Communication",
    "Education",
    "Engineering",
    "Health Sciences",
    "Law & Social Sciences",
    "Agriculture & Environment"
  ],
  "count": 8
}
```

---

### GET /api/careers

Returns all career paths in the database.

**Response:**
```json
{
  "status": "success",
  "data": [
    "Software Developer",
    "Systems Analyst",
    "Database Administrator",
    "IT Support Specialist",
    "Business Analyst",
    "Project Manager",
    "Teacher",
    "Healthcare Officer"
  ],
  "count": 156
}
```

---

### GET /api/programmes-by-career/:career

Returns all programmes for a specific career path.

**Parameters:**
```
GET /api/programmes-by-career/Software%20Developer
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `career` | string | Career path name (URL-encoded) |

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "id": "limkokwing-bsc-software-engineering",
      "name": "BSc Software Engineering",
      "institution": "Limkokwing University Lesotho",
      "career_options": ["Software Developer", "Systems Analyst", "Database Administrator", "IT Support Specialist"]
    }
  ],
  "count": 12
}
```

---

### GET /api/statistics

Returns database statistics.

**Response:**
```json
{
  "status": "success",
  "data": {
    "total_programmes": 233,
    "total_institutions": 12,
    "total_categories": 8,
    "total_careers": 156,
    "by_level": {
      "degree": 145,
      "diploma": 78,
      "certificate": 10
    },
    "by_institution": {
      "National University of Lesotho": 54,
      "Limkokwing University Lesotho": 38
    },
    "enrichment_status": {
      "total_with_career_paths": 233,
      "total_with_duration": 233,
      "total_with_fees": 95,
      "total_approved": 233
    }
  }
}
```

---

## Error Responses

### 400 Bad Request
```json
{
  "status": "error",
  "error": "Invalid query parameter 'level': must be 'degree' or 'diploma'",
  "data": null
}
```

### 404 Not Found
```json
{
  "status": "error",
  "error": "Programme with ID 'invalid-id' not found",
  "data": null
}
```

### 500 Internal Server Error
```json
{
  "status": "error",
  "error": "Internal server error. Please try again later.",
  "data": null
}
```

---

## Rate Limiting

Currently no rate limiting. Production deployment may implement:
- 100 requests per minute per IP
- 10 requests per second per IP

---

## CORS Headers

Enabled for all origins:
```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, OPTIONS
Access-Control-Allow-Headers: Content-Type
```

---

## Examples

### Search for Software Engineering programmes
```bash
curl "http://localhost:8765/api/programmes?category=Technology%20%26%20ICT&level=degree"
```

### Get all programmes from NUL
```bash
curl "http://localhost:8765/api/programmes?institution=National%20University%20of%20Lesotho"
```

### Search for programmes leading to Software Developer career
```bash
curl "http://localhost:8765/api/programmes-by-career/Software%20Developer"
```

### Get database statistics
```bash
curl "http://localhost:8765/api/statistics"
```

---

## Pagination

For large result sets, use `limit` and `offset`:

```bash
# Get first 20 results
/api/programmes?limit=20&offset=0

# Get next 20 results
/api/programmes?limit=20&offset=20

# Get results 40-59
/api/programmes?limit=20&offset=40
```

---

## Filtering Combinations

You can combine multiple filters:

```bash
# Degree programmes in Technology from NUL
/api/programmes?institution=NUL&level=degree&category=Technology%20%26%20ICT

# All diploma programmes with career guidance
/api/programmes?level=diploma
# (all returned will have career_options populated)
```

---

## Data Consistency

- All institution names are standardized
- All level values: `degree`, `diploma`, `certificate`, `masters`
- All categories follow a predefined list
- All career paths are from a standardized taxonomy
- All programmes marked `review_status: "approved"` are production-ready

---

## Caching

Recommended client-side caching:
- **Institutions**: Cache indefinitely (changes rarely)
- **Programmes**: Cache 24 hours (updated daily)
- **Statistics**: Cache 1 hour (updated frequently)
- **Search results**: Cache 1 hour (based on query)

---

## Support

For API issues:
1. Check this documentation
2. Review error response messages
3. Check application logs: `server.py` output
4. Submit issue on GitHub

---

**API Version**: 1.0  
**Last Updated**: 2025  
**Status**: Production Ready
