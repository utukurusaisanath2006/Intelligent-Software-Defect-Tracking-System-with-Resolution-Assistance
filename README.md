# IntelliTrack — Intelligent Software Defect Tracking System with Resolution Assistance

IntelliTrack is a full-stack web application built with **Python 3 / Flask** and **Vanilla HTML5 / CSS3 / ES6+ JavaScript** that centralizes software defect reporting, deterministic classification, prioritization, workflow lifecycle management, collaboration, sprint planning, and quality analytics.

---

## Key Features

- **Role-Based Workspaces & Access Control (RBAC)**
  - **Admin**: System overview, user & role administration (with last-admin protection), project lifecycle & archiving, sprint planning, analytics charts, CSV export, audit logs, and system configuration.
  - **Developer**: Focused work queue, assigned/in-progress/critical metrics, investigation notes (root cause & resolution), workflow state transitions, and deterministic resolution assistance.
  - **Reporter / QA**: Issue reporting (bugs, feature requests, enhancements, technical debt) with file attachments, awaiting-verification tracking, collaborative commenting, and fix verification / reopening.
- **Centralized Workflow Engine**
  - Server-enforced lifecycle transitions: `Reported → Triaging → Assigned → In Progress → Code Review → QA Verification → Resolved → Closed` (with `Reopened` and QA return paths).
  - Atomic database commits recording issue state updates, chronological audit trail entries (`Activity`), and in-app `Notification` records together.
- **Explainable Classification & Resolution Assistant**
  - Deterministic Python rule engine (`ClassificationService` & `ResolutionAssistant`) recommending category, severity, and priority with explicit reasons and confidence scores.
  - Interactive suggestion preview on issue creation (explicit accept/dismiss; never silently overwrites user choices).
  - Context-aware debugging checklists and potential duplicate/related issue detection.
- **Analytics & Reporting**
  - Real-time database-backed metrics: status/severity/category distributions, 30-day defect trends, average & median resolution times, backlog health score, developer workload, and project comparisons.
  - Chart.js visualizations styled to match the design system plus one-click CSV report export.
- **Sprint Planning**
  - Sprint creation, status progression (`Planning → Active → Completed`), project backlog assignment, and live completion metrics.
- **Swiss Grid × Industrial Instrument UI**
  - Warm off-white (`#F4F1E9` / `#FBFAF6`) editorial palette, signal orange (`#E76F32`) accents, semantic status badges with text labels, monospaced technical identifiers, responsive mobile drawer, and reduced-motion support.

---

## Technology Stack

- **Backend**: Python 3, Flask, Flask-SQLAlchemy, Flask-Login, Flask-WTF (CSRF), Werkzeug password hashing, SQLite (PostgreSQL-compatible via `DATABASE_URL`)
- **Frontend**: HTML5, CSS3 (custom design tokens, zero CSS frameworks), Vanilla ES6+ JavaScript, Jinja2 templates, Chart.js 4, inline SVGs
- **Testing**: Pytest + Flask test client with isolated in-memory SQLite database

---

## Architecture & Directory Structure

```text
Browser → Flask Routes & REST API (/api/v1) → Business Services → SQLAlchemy Models → SQLite / PostgreSQL
```

```text
Info-B5-G3-ISDTS-/
├── app.py                     # Flask app factory, CLI commands, error handlers, security headers
├── config.py                  # Development, Testing, and Production config classes
├── extensions.py              # SQLAlchemy, LoginManager, and CSRFProtect instances
├── seed.py                    # Repeatable demo data seeder
├── requirements.txt           # Python dependencies
├── .env.example               # Environment configuration template
├── models/
│   ├── __init__.py
│   ├── user.py                # User model with password hashing & RBAC helpers
│   ├── project.py             # Project & ProjectMembership models
│   ├── issue.py               # Core Issue model with lifecycle & metadata
│   ├── comment.py             # Issue discussion comments
│   ├── activity.py            # Chronological audit log
│   ├── attachment.py          # File attachment metadata
│   ├── sprint.py              # Agile sprints
│   ├── release.py             # Software releases / milestones
│   └── notification.py        # In-app user notifications
├── services/
│   ├── workflow_service.py    # Centralized state machine & role transition rules
│   ├── issue_service.py       # Issue CRUD, filtering, pagination, duplicate search
│   ├── classification_service.py # Explainable keyword/matrix categorization & priority
│   ├── resolution_assistant.py   # Debugging checklists & related issue suggestions
│   ├── analytics_service.py   # Database-backed quality metrics & workload queries
│   └── notification_service.py   # In-app notification dispatch & read tracking
├── routes/
│   ├── __init__.py
│   ├── auth.py                # Login, registration, logout
│   ├── dashboard.py           # Role-aware dashboard routing
│   ├── issues.py              # Issue list, create, detail, comments, transitions, uploads
│   ├── projects.py            # Project list & detail views
│   ├── sprints.py             # Sprint list, detail, creation, backlog assignment
│   ├── admin.py               # User/project admin, analytics, CSV export, audit log, settings
│   └── api.py                 # JSON REST API (/api/v1/...)
├── templates/
│   ├── base.html              # Shared authenticated shell (sidebar, topbar, search, notifications)
│   ├── base_unauth.html       # Minimal shell for auth & error pages
│   ├── auth/                  # login.html, register.html
│   ├── dashboards/            # reporter.html, developer.html
│   ├── issues/                # list.html, create.html, detail.html
│   ├── projects/              # list.html, detail.html
│   ├── sprints/               # list.html, detail.html
│   ├── admin/                 # overview, users, user_form, projects, project_form, analytics, activity, settings
│   ├── components/            # pagination.html, empty_state.html
│   └── errors/                # 403.html, 404.html, 500.html
├── static/
│   ├── css/                   # tokens.css, layout.css, components.css
│   ├── js/                    # app.js, issues.js, dashboard.js
│   └── uploads/               # Uploaded issue attachments
└── tests/
    ├── conftest.py
    ├── test_auth.py
    ├── test_issues.py
    ├── test_workflow.py
    ├── test_permissions.py
    └── test_api.py
```

---

## Local Setup & Execution (Windows PowerShell)

### 1. Create and Activate Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure Environment Variables

```powershell
Copy-Item .env.example .env
```

Edit `.env` to set a strong `SECRET_KEY` (and optional PostgreSQL `DATABASE_URL` when deploying beyond SQLite).

### 4. Initialize and Seed Database

```powershell
$env:FLASK_APP = "app.py"
flask init-db
flask seed-db
```

### 5. Run the Application Locally

```powershell
python app.py
```

Open **http://127.0.0.1:5000** in your browser.

> **Production Note**: Do not use Flask's built-in development server in production. Use a WSGI server such as **Waitress** (Windows) or **Gunicorn** (Linux) behind a reverse proxy with HTTPS enabled.

---

## Demo Development Accounts

After running `flask seed-db`, the following local development accounts are available. All account credentials in `seed.py` are securely pre-hashed using industry-standard Werkzeug scrypt hashing—no raw plaintext passwords are ever hardcoded in the codebase:

| Role | Email | Password |
| :--- | :--- | :--- |
| **Admin** | `admin@intellitrack.dev` | `admin123` |
| **Developer** | `dev@intellitrack.dev` | `dev123` |
| **Developer** | `sarah@intellitrack.dev` | `dev123` |
| **Reporter / QA** | `reporter@intellitrack.dev` | `reporter123` |

> **Security Note**: In compliance with secure coding standards, passwords are never hardcoded as plaintext in source code or the database. In `seed.py`, user records use pre-computed cryptographic password hashes. You can also customize seed passwords dynamically via the `SEED_ADMIN_PASSWORD`, `SEED_DEV_PASSWORD`, and `SEED_REPORTER_PASSWORD` environment variables.

---

## Enterprise Security Architecture

IntelliTrack implements proactive multi-layered security controls aligned with the **OWASP Top 10**:

1. **Cryptographic Password Hashing & Write-Only Attributes**: Passwords use Werkzeug's `scrypt` key derivation function with random salt. The `User.password` attribute is strictly write-only, preventing plaintext exposure in logs or code.
2. **Brute-Force Login Rate Limiting**: The `/auth/login` endpoint enforces a sliding-window rate limit (max 5 requests/minute per client IP) that returns HTTP 429 upon abuse.
3. **Session Cookie Hardening**: Cookies are configured with `HttpOnly` (preventing XSS cookie theft), `SameSite=Lax` (defending against CSRF leaks), and `Secure` flags.
4. **Sliding Session Expiration**: Configured with a 60-minute rolling lifetime that invalidates idle sessions on unattended devices.
5. **Content Security Policy (CSP) & Defense-in-Depth Headers**: Responses inject strict headers including `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `X-XSS-Protection: 1; mode=block`, and `Referrer-Policy: strict-origin-when-cross-origin`.
6. **File Upload Magic-Byte Validation**: Beyond file extension checks, file headers are verified against true binary signatures to block disguised executables and malicious scripts.
7. **Safe File Download Dispositions**: Attachments are delivered with forced `Content-Disposition: attachment`, `nosniff`, and `noopen` to prevent stored XSS via browser rendering.
8. **Structured Security Auditing**: Security alerts (failed authentication, rate-limiting triggers, 403 authorization rejections) are logged with client IP addresses and timestamps.

---

## Running Automated Tests

```powershell
python -m pytest -v
```

The comprehensive test suite (79 tests) runs against an isolated in-memory SQLite database (`TestingConfig`) and verifies authentication, RBAC, project-level authorization (IDOR protection), issue CRUD, attachments, workflow state enforcement, classification, resolution suggestions, REST API responses, analytics queries, CSV export, and enterprise security hardening.
