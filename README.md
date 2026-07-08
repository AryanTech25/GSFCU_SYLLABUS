# GSFC University — Syllabus Management Portal

> A full-stack Django web application for managing university course syllabi — built for faculty, designed for administrators, and engineered for reliability.

---

## 📋 Table of Contents

1. [Project Overview](#-project-overview)
2. [Key Features](#-key-features)
3. [Technology Stack](#-technology-stack)
4. [Data Model Overview](#-data-model-overview)
5. [Project Structure](#-project-structure)
6. [Installation & Setup](#-installation--setup)
7. [Environment Configuration](#-environment-configuration)
8. [Running the Application](#-running-the-application)
9. [User Roles & Workflows](#-user-roles--workflows)
10. [PDF Generation System](#-pdf-generation-system)
11. [Security Architecture](#-security-architecture)
12. [Database Integrity Rules](#-database-integrity-rules)
13. [Usage Notes](#-usage-notes)

---

## 🎯 Project Overview

The **GSFC University Syllabus Management Portal** is a centralised academic document management system. It enables faculty members to digitally build, save, and submit structured course syllabi through a guided multi-step form, and empowers administrators to organise, validate, and generate professional PDF books for entire semesters and programs.

The system follows a strict **Role-Based Access Control (RBAC)** model with two user types:
- **Administrators** — manage the full academic hierarchy and PDF generation pipelines.
- **Faculty Members** — assigned specific subjects and build syllabi through a structured workflow.

---

## 🚀 Key Features

### 👩‍💼 Administrator Features

| Feature | Description |
|---|---|
| **Dashboard** | Live overview of all faculty, subjects, and semester assignments |
| **Faculty Management** | Create, edit, assign subjects to, and delete faculty profiles |
| **Subject Management** | Create subjects linked to Schools, Programs, Branches, and Academic Years |
| **Semester Structure** | Organise subjects into numbered semesters under specific Programs |
| **Bulk PDF Generation** | Merge individual subject syllabi into one professionally formatted semester PDF book |
| **Combined Program PDF** | Generate a single comprehensive PDF for an entire Program/Branch with a university cover page |
| **PDF Invalidation** | Stale merged PDFs are automatically deleted when source content changes |
| **Data Integrity** | Cascading deletion logic ensures no orphaned records in the database |

### 👨‍🏫 Faculty Features

| Feature | Description |
|---|---|
| **Multi-Step Syllabus Builder** | Guided form with 5 progressive steps |
| **Draft Saving** | Save progress at any point and resume later |
| **Real-Time Preview** | Preview the final syllabus layout in-browser before PDF generation |
| **PDF Download** | Generate and download the official subject syllabus PDF |
| **Auto-Scroll Validation** | On validation failure, the form scrolls to and highlights the first incomplete field |

---

## 🛠 Technology Stack

### Backend

| Technology | Version | Purpose |
|---|---|---|
| **Python** | 3.12+ | Core programming language |
| **Django** | 5.0.1 | Web framework (MVT architecture) |
| **PostgreSQL** | 14+ (recommended) | Relational database |
| **psycopg2** | Latest | PostgreSQL database adapter for Python |

### PDF Generation

| Library | Purpose |
|---|---|
| **ReportLab** | Programmatic PDF generation for complex layouts (cover pages, tables, watermarks) |
| **xhtml2pdf (pisa)** | HTML-to-PDF rendering for template-based syllabus documents |

### Frontend

| Technology | Purpose |
|---|---|
| **HTML5** | Semantic document structure |
| **Vanilla CSS** | Custom global design system with CSS variables, responsive layouts |
| **Vanilla JavaScript** | Form interactivity, step navigation, auto-scroll to error fields |
| **FontAwesome / SVG** | Icons and visual elements |

### Django Packages & Middleware

| Package | Purpose |
|---|---|
| `django.contrib.auth` | Built-in user authentication system |
| `django.contrib.sessions` | Session-based login management |
| `django.middleware.security` | Security headers (XSS, content-type sniffing) |
| `django.middleware.csrf` | Cross-Site Request Forgery protection |
| `django.db.models.signals` | Post-delete signals for automatic PDF invalidation |

---

## 🗃 Data Model Overview

The application uses a hierarchical academic model:

```
School
 └── Program
      └── Branch
           └── Semester
                └── SemesterSubject  ←→  Subject  ←→  Faculty
                                              └── Syllabus
                                                   ├── TheoryUnit
                                                   ├── PracticalUnit
                                                   ├── CourseObjective
                                                   ├── CourseOutcome
                                                   │    └── OutcomeMapping (PO/PSO)
                                                   └── LearningResource
```

### Core Models (in `adminpanel/models.py`)

| Model | Description |
|---|---|
| `School` | Top-level academic unit (e.g., School of Engineering) |
| `Program` | Degree program under a school (e.g., B.Tech) |
| `Branch` | Specialisation under a program (e.g., Computer Science) |
| `Faculty` | Faculty profile linked 1:1 to a Django `User` account |
| `Subject` | A course/paper — global master data, only admin can delete |
| `Syllabus` | The structured content document created by a faculty member for a subject |
| `TheoryUnit` | A unit of the theory portion of the syllabus |
| `PracticalUnit` | A lab or experiment entry |
| `CourseObjective` | Objective statement for the course |
| `CourseOutcome` | Expected learning outcome (CO) |
| `OutcomeMapping` | Maps Course Outcomes to Program Outcomes (PO) and PSOs |
| `LearningResource` | Books, websites, references categorised under a syllabus |
| `Semester` | A named semester (e.g., Sem-1) linked to a Program |
| `SemesterSubject` | Join table linking subjects to semesters in a defined sequence |
| `SemesterFacultyAccess` | Controls which faculty can see which semester |
| `SemesterReference` | Tracks the generated merged PDF for a `Semester + Branch` pair |

---

## 📂 Project Structure

```
gfsc_portal/
│
├── core/                         # Django project configuration
│   ├── settings.py               # All settings: DB, auth, static, media
│   ├── urls.py                   # Root URL dispatcher
│   ├── wsgi.py                   # WSGI entry point (production)
│   └── asgi.py                   # ASGI entry point (async capable)
│
├── accounts/                     # Faculty-facing application
│   ├── views.py                  # Login, logout, syllabus builder, PDF download
│   ├── urls.py                   # Faculty URL routes
│   ├── utils.py                  # PDF generation helpers
│   └── templates/accounts/       # Faculty HTML templates
│
├── adminpanel/                   # Administrator-facing application
│   ├── models.py                 # All core data models
│   ├── views.py                  # Admin CRUD, PDF merge, program PDF generation
│   ├── urls.py                   # Admin URL routes
│   ├── admin.py                  # Django admin panel registrations
│   ├── signals.py                # Post-delete signals for PDF invalidation
│   ├── migrations/               # Database schema migrations
│   └── templates/adminpanel/     # Admin HTML templates (dashboard, forms)
│
├── templates/                    # Shared base templates
│
├── static/                       # Global static assets
│   ├── css/                      # Global design system CSS
│   ├── js/                       # JavaScript utilities
│   └── images/                   # Branding assets (university logo, etc.)
│
├── syllabus_pdfs/                # Media root — generated PDF files are stored here
│   └── semester_pdfs/            # Merged semester PDF books
│
├── DB_VERIFICATION.sql           # SQL queries for manual database verification
├── manage.py                     # Django management script
├── requirements.txt              # Full Python dependency list
└── requirements_lite.txt         # Stripped-down dependency list
```

---

## ⚙️ Installation & Setup

### Prerequisites

Make sure the following are installed on your system before proceeding:

- **Python** 3.12 or higher → [python.org](https://www.python.org/downloads/)
- **PostgreSQL** 14 or higher → [postgresql.org](https://www.postgresql.org/download/)
- **pip** (comes with Python)
- **Git** → [git-scm.com](https://git-scm.com/)

---

### Step 1 — Clone the Repository

```bash
git clone <repository-url>
cd gfsc_portal
```

---

### Step 2 — Create a Virtual Environment

```bash
# Create the environment
python -m venv venv

# Activate it — Windows
.\venv\Scripts\activate

# Activate it — Linux / macOS
source venv/bin/activate
```

---

### Step 3 — Install Dependencies

```bash
pip install -r requirements.txt
```

> **Tip:** If you are setting up a lightweight environment without AI/ML packages, use `requirements_lite.txt` instead.

---

### Step 4 — Set Up the PostgreSQL Database

Open **pgAdmin** or the **psql** command-line tool and run:

```sql
CREATE DATABASE gfsc_db;
CREATE USER postgres WITH PASSWORD 'postgres123';
GRANT ALL PRIVILEGES ON DATABASE gfsc_db TO postgres;
```

> You can use any username/password — just make sure they match what you configure in `settings.py` (Step 5).

---

### Step 5 — Configure `core/settings.py`

Open `core/settings.py` and update the `DATABASES` section:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'gsfc_db',        # Your database name
        'USER': 'postgres',        # Your PostgreSQL username
        'PASSWORD': 'postgres123', # Your PostgreSQL password
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

---

### Step 6 — Run Database Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

This will create all necessary tables in your database.

---

### Step 7 — Create the Superuser (Admin Account)

```bash
python manage.py createsuperuser
```

You will be prompted to enter a **username**, **email**, and **password**. This account is used to log in as an Administrator.

---

### Step 8 — Collect Static Files (Production Only)

```bash
python manage.py collectstatic
```

> Skip this step for local development — static files are served automatically in `DEBUG=True` mode.

---

## 🌐 Running the Application

### Development Server

```bash
python manage.py runserver
```

The application will be accessible at:

```
http://127.0.0.1:8000/
```

### Default Login Routes

| Role | URL |
|---|---|
| Login Page | `http://127.0.0.1:8000/login/` |
| Admin Dashboard | `http://127.0.0.1:8000/admin/dashboard/` |
| Faculty Dashboard | `http://127.0.0.1:8000/faculty/dashboard/` |

---

## 👥 User Roles & Workflows

### Administrator Workflow

```
1. Log in → Admin Dashboard
2. Create Schools, Programs, Branches (academic hierarchy)
3. Create Faculty accounts and assign them subjects + semesters
4. Create Subjects and link them to Schools/Programs/Branches
5. Set up Semester structure and assign subjects in sequence
6. Once faculty submit syllabi → Merge into semester PDF book
7. Generate final Combined Program PDF with university cover page
```

### Faculty Workflow

```
1. Log in → Faculty Dashboard (sees assigned subjects)
2. Click a subject → Launch Syllabus Builder
3. Fill in all 5 steps:
   Step 1: Course Info & Objectives
   Step 2: Theory Units
   Step 3: Practical / Lab Experiments
   Step 4: Course Outcomes + PO/PSO Mapping
   Step 5: Learning Resources (Books, Journals, Links)
4. Save as Draft (can edit later)
5. Preview the syllabus
6. Generate & Download the final PDF
```

---

## 📄 PDF Generation System

The portal uses a **dual-engine PDF system**:

| Engine | Used For |
|---|---|
| **xhtml2pdf (pisa)** | Individual subject syllabus PDFs rendered from HTML templates |
| **ReportLab** | Programmatically generated semester books and program PDFs (cover pages, summary tables, page numbers, watermarks) |

### PDF Types Generated

1. **Subject Syllabus PDF** — Generated by faculty. Includes all theory units, practicals, COs, PO mapping, and resources.
2. **Semester PDF Book** — Generated by admin. Merges all subject syllabi for a semester into one document with an auto-generated **Course Structure Summary Page**.
3. **Combined Program PDF** — Merges all semesters for a Program/Branch into one PDF with a **University Cover Page** and section headers.

### PDF Storage

All generated PDFs are stored under:

```
syllabus_pdfs/
└── semester_pdfs/    ← Merged semester/program PDFs
```

> ⚠️ **Do NOT manually rename or move files** in `syllabus_pdfs/`. The `SemesterReference` model stores exact file paths and file renames will break download links.

---

## 🔒 Security Architecture

| Mechanism | Implementation |
|---|---|
| **Role-Based Access Control** | `@user_passes_test` decorator strictly separates admin and faculty views |
| **Anti-Cache on Sensitive Pages** | `@never_cache` prevents sensitive data exposure via browser "Back" button after logout |
| **CSRF Protection** | Django's built-in `CsrfViewMiddleware` protects all POST forms |
| **Session Security** | `LOGIN_URL` enforces authentication; sessions expire cleanly on logout |
| **Path Traversal Prevention** | File downloads use `FileResponse` with PK validation — no raw path input accepted from users |
| **Password Validation** | Django's built-in validators enforce password strength |

### Recommended Production Settings

Update `core/settings.py` before deploying to production:

```python
DEBUG = False
ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com']
SECRET_KEY = '<generate-a-new-secure-key>'

# Security Headers
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

> Generate a new `SECRET_KEY` for production using:
> ```bash
> python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
> ```

---

## 🛡 Database Integrity Rules

The system enforces several data integrity rules automatically:

| Rule | Trigger | Behaviour |
|---|---|---|
| **Cascade Deletion** | Admin deletes a `Subject` | All associated `Syllabus`, `TheoryUnit`, `PracticalUnit`, `CourseOutcome` records are deleted |
| **PDF Invalidation** | A `Subject`, `Syllabus`, or `SemesterSubject` is deleted | The merged `SemesterReference` PDF (physical file + DB record) is permanently deleted via Django signal |
| **Unique Semester PDFs** | `SemesterReference` model | Enforces `unique_together = ('semester', 'branch')` — only one merged PDF per semester/branch pair |
| **Subject Ownership** | Subjects are global master data | Subjects are **not** deleted when a Faculty or Syllabus is deleted — only Admin can delete subjects explicitly |
| **Faculty Account Link** | `Faculty` is linked 1:1 to Django `User` | Deleting the `User` cascades to deleting the `Faculty` profile |

---

## 📝 Usage Notes

- **Academic Year**: The system reads the Academic Year from the **Subject model**. Ensure this field is filled in for each subject to avoid `"Academic Year Not Defined"` appearing in PDF headers.
- **PDF Paths**: Do not manually rename or move files inside the `syllabus_pdfs/` directory. The database stores exact relative paths.
- **Faculty Semester Assignment**: Faculty must be explicitly granted access to semesters via `SemesterFacultyAccess` for the correct subjects to appear on their dashboard.
- **Superuser vs Admin Panel**: The Django built-in `/django-admin/` route is **disabled** in this project. All administration is done through the custom `/admin/` interface.
- **Database Verification**: Use the queries in `DB_VERIFICATION.sql` to manually inspect table states during development or troubleshooting.

---

## 🧰 Useful Management Commands

```bash
# Start development server
python manage.py runserver

# Apply database schema changes
python manage.py makemigrations && python manage.py migrate

# Create an admin user
python manage.py createsuperuser

# Open Django interactive shell
python manage.py shell

# Check for project configuration issues
python manage.py check

# Clear all sessions (useful during testing)
python manage.py clearsessions
```

---

*Developed for **GSFC University** — Academic Document Management System.*
