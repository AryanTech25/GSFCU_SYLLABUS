# Faculty Panel — Complete Flow Documentation

> **GSFC University Syllabus Management System**
> End-to-end flow for a Faculty user — from login to syllabus submission and PDF generation.

---

## Table of Contents

1. [Login](#1-login)
2. [Faculty Dashboard](#2-faculty-dashboard)
3. [Syllabus Builder](#3-syllabus-builder)
   - 3.1 [Teaching Scheme and Credit](#31-teaching-scheme-and-credit)
   - 3.2 [Course Meta Info](#32-course-meta-info)
   - 3.3 [Course Objectives](#33-course-objectives)
   - 3.4 [Theory Units (Course Content)](#34-theory-units-course-content)
   - 3.5 [Practicals / Experiments](#35-practicals--experiments)
   - 3.6 [Evaluation Scheme](#36-evaluation-scheme)
   - 3.7 [Course Outcomes (COs)](#37-course-outcomes-cos)
   - 3.8 [CO-PO Mapping](#38-co-po-mapping)
   - 3.9 [Learning Resources](#39-learning-resources)
4. [Draft Management](#4-draft-management)
5. [Live Syllabus Preview](#5-live-syllabus-preview)
6. [Individual Syllabus PDF Generation](#6-individual-syllabus-pdf-generation)
7. [Semester Merge PDF](#7-semester-merge-pdf)
8. [Data Model Diagram](#8-data-model-diagram)
9. [URL Reference](#9-url-reference)

---

## 1. Login

- **URL:** `/login/`
- **Template:** `accounts/templates/accounts/login.html`
- **View:** `accounts.views.login_view`

### Flow

1. Faculty goes to `/login/`.
2. Enters **username** and **password** (credentials created by Admin — faculty cannot self-register).
3. On success → redirected to **Faculty Dashboard** at `/faculty/dashboard/`.
4. On failure → error message on the same page.
5. If the logged-in user is **staff/admin** → redirected to Admin Dashboard at `/dashboard/`.

---

## 2. Faculty Dashboard

- **URL:** `/faculty/dashboard/`
- **Template:** `accounts/templates/accounts/faculty_dashboard.html`
- **View:** `accounts.views.faculty_dashboard`

### What Is Shown

| Area | Description |
|------|-------------|
| Assigned Subjects | All subjects assigned to this faculty by the Admin |
| Syllabus Status Badge | `No Syllabus` / `Draft` / `Final Submission` per subject |
| Action Buttons | Build Syllabus, Edit, Generate PDF, View PDF |
| Semester Merge Button | Appears when Admin has configured a semester structure |

### Key Info Per Subject Card

- Course Code, Course Name, Semester
- School > Program > Branch hierarchy
- Syllabus completion status
- Last PDF generation timestamp

---

## 3. Syllabus Builder

- **URL:** `/faculty/syllabus-builder/?subject_id=<id>`
- **Template:** `accounts/templates/accounts/syllabus_builder.html`
- **View:** `accounts.views.syllabus_builder`

The Syllabus Builder is a **multi-section single-page form**. Sections are filled sequentially. The form can be saved as a Draft at any point, or submitted as Final.

---

### 3.1 Teaching Scheme and Credit

| Field | Description |
|-------|-------------|
| Hours – Lecture (L) | Contact hours/week for lectures |
| Hours – Practical (P) | Contact hours/week for practicals |
| Hours – Tutorial (T) | Contact hours/week for tutorials |
| Credit – Lecture (L) | Credit points for lectures |
| Credit – Practical (P) | Credit points for practicals |
| Credit – Tutorial (T) | Credit points for tutorials |

> Total Hours = L + P + T (auto-computed). Same for Total Credits.

---

### 3.2 Course Meta Info

| Field | Description |
|-------|-------------|
| Prerequisites | Prerequisite courses or knowledge required |
| Category | HS / BS / ES / PC / PE / OE / IP / NC |
| Course Category Title | Expanded label matching category (e.g., "Professional Subjects – Core (PC)") |
| Course Focus | Employability / Entrepreneurship / Skill Development |
| Rationale | Why this course exists (free-form paragraph) |
| Approval / Revision Date | Date this syllabus was approved |

---

### 3.3 Course Objectives

- Faculty adds multiple text objectives (no hard cap; minimum ~3 expected).
- Each objective is a statement starting with an action verb (e.g., "To enable students to...").
- Stored in `CourseObjective` model, linked to `Syllabus`.

---

### 3.4 Theory Units (Course Content)

Each Theory Unit contains:

| Field | Description |
|-------|-------------|
| Unit Title | Name / topic of the unit |
| Description | Detailed sub-topics and content |
| Weightage (%) | Exam weightage for this unit |
| Contact Hours | Hours allocated to teach this unit |

- Multiple units added via the "Add Unit" button (JavaScript-driven).
- Stored in `TheoryUnit` model.

---

### 3.5 Practicals / Experiments

Each Practical entry contains:

| Field | Description |
|-------|-------------|
| Description | What the experiment/practical involves |
| Weightage (%) | Weightage in practical evaluation |
| Hours | Duration allocated |

- Multiple entries added dynamically.
- Stored in `Practical` model.

---

### 3.6 Evaluation Scheme

**Theory Components:**

| Component | Description |
|-----------|-------------|
| Mid Semester (MS) | Internal / mid-term marks |
| End Semester (ES) | External / end-term marks |
| CEC – Attendance | Marks for attendance |
| CEC – MCQ/Quiz | Marks for quizzes |
| CEC – Assignment | Marks for assignments |

**Practical Components:**

| Component | Description |
|-----------|-------------|
| Attendance | Practical attendance marks |
| Exam / Performance | Practical exam marks |
| Viva | Viva marks |
| Journal | Journal marks |
| Discipline | Discipline marks |

- All stored in `EvaluationScheme` model (OneToOne with `Syllabus`).

---

### 3.7 Course Outcomes (COs)

| Field | Description |
|-------|-------------|
| CO Code | Auto-generated: CO1, CO2, CO3 … |
| Description | Bloom's taxonomy outcome statement |

- Stored in `CourseOutcome` model.

---

### 3.8 CO-PO Mapping

Faculty fills a matrix mapping each CO to PO1–PO12 (and PSO1, PSO2):

| Correlation Value | Meaning |
|-------------------|---------|
| 0 | No Correlation |
| 1 | Low |
| 2 | Medium |
| 3 | High |

- Stored in `OutcomeMapping` model (OneToOne with `CourseOutcome`).
- Rendered as a matrix table on a **landscape page** in the PDF.

---

### 3.9 Learning Resources

| Field | Description |
|-------|-------------|
| Category | Text Books / Reference Books / Online Resources / etc. |
| Content | Full citation, URL, or description |

- Multiple resources per category.
- Stored in `LearningResource` model.

---

## 4. Draft Management

- **URL:** `/faculty/drafts/`
- **Template:** `accounts/templates/accounts/faculty_drafts.html`
- **View:** `accounts.views.faculty_drafts`

### Status Lifecycle

```
[No Syllabus] --> [Draft] --> [Final Submission] --> [PDF Generated]
```

### Rules

- **Save as Draft**: Faculty can save incomplete forms at any time. Partial data is accepted.
- **Draft**: Editable. PDF generation NOT allowed.
- **Final Submission**: Form is locked. PDF generation IS allowed.
- **Resuming a Draft**: Faculty can re-open any draft from the Drafts page.

---

## 5. Live Syllabus Preview

- **URL:** `/faculty/render-preview/` (POST request)
- **View:** `accounts.views.render_preview`

- Faculty clicks **"Preview"** inside the Syllabus Builder.
- Current form data is POSTed to this endpoint.
- Rendered into `templates/pdf/syllabus_canonical.html` and returned as HTML.
- Displayed in the browser — shows exactly how the PDF will look.

---

## 6. Individual Syllabus PDF Generation

- **URL:** `/faculty/generate-pdf/<syllabus_id>/`
- **View:** `accounts.views.generate_pdf`

### Step-by-Step Flow

1. Faculty clicks **"Generate PDF"** (only available for Final syllabi).
2. View fetches all related data: Syllabus, TheoryUnits, Practicals, CourseOutcomes, EvaluationScheme, LearningResources.
3. Renders `templates/pdf/syllabus_canonical.html` with full context.
4. **xhtml2pdf (pisa)** library converts the HTML+CSS to a PDF binary.
5. PDF saved to `syllabus_pdfs/` directory.
6. `Syllabus.pdf_file` and `Syllabus.pdf_generated_at` are updated in the database.
7. Faculty can view (inline) or download the PDF.

### PDF Page Structure (in order)

| Page / Section | Content |
|----------------|---------|
| Every page header | School Name · Program · Academic Year · University Logo |
| Page 1 – Course Info | Course Code / Course Name / Semester (3-column grey header) |
| Page 1 – Teaching Scheme | 8-column table: TEACHING SCHEME (L/P/T/Total) + TEACHING CREDIT (L/P/T/Total) side by side |
| Page 1 – Meta Info | Prerequisites, Category, Course Focus, Rationale, Approval Date, Objectives |
| Next pages – Theory Content | Unit-wise table: Topic/Module · Weightage % · Contact Hours |
| – Practicals | Numbered table: Sr No · Description · Weightage % · Hours |
| – Course Outcomes | Table: CO Code · Description |
| – CO-PO Mapping (landscape) | Matrix: COs as rows, PO1–PO12 as columns, correlation values |
| – Evaluation Scheme | Component-wise breakdown: Theory (MS/CEC/ES) and Practical |
| – Learning Resources | Numbered list grouped by category |
| Every page footer | Page number (right-aligned) |

---

## 7. Semester Merge PDF

- **URL (Preview):** `/semester/preview/<semester_id>/`
- **URL (Generate):** `/semester/generate/<semester_id>/`
- **Views:** `accounts.views.preview_semester_merge` · `accounts.views.generate_semester_pdf`

> **Note:** This is the faculty-accessible merge path. Admin has an independent path at `/admin/semester/generate-pdf/`.

### Flow

1. Admin configures a Semester Structure (assigns subjects to a semester).
2. Faculty sees the "Generate Merged PDF" button on their dashboard.
3. Faculty clicks **Preview** → browser shows the combined PDF preview.
4. Faculty clicks **Generate** → combined PDF is created and downloaded.

### Combined PDF Structure

```
Page 1: Combined Course Structure (Portrait A4)
+---------------------------------------------------------+
| Box 1: Teaching Scheme & Credit                         |
| Sr | Code | Course Name | Sem | L | P | T | Tot | ...   |
+---------------------------------------------------------+
| Box 2: Evaluation Scheme                                |
| Sr | Code | Course Name | MS | CEC | ES | Theory | ...  |
+---------------------------------------------------------+

Page 2+: Individual course syllabus (one per subject)
  -- same as individual PDF format above --
```

### Merge Inclusion Rules

- Only subjects with **status = Final** AND an existing **PDF file** are included.
- Subjects with missing/stale PDFs are skipped with a warning.
- The "Sem" column displays only the numeral (e.g., "V" not "Semester V").

---

## 8. Data Model Diagram

```
User (Django built-in)
  |
  +-- Faculty (1:1)
        |-- School (FK)
        |-- Program (FK)
        |-- Branch (FK)
        |
        +-- SubjectFaculty (M2M through table)
              |
              +-- Subject
                    |-- School (FK)
                    |-- Program (FK)
                    |-- Branch (FK)
                    |
                    +-- Syllabus (1:1)
                          |-- hours_lecture, hours_practical, hours_tutorial
                          |-- credit_lecture, credit_practical, credit_tutorial
                          |-- status: draft / final
                          |-- pdf_file (FileField)
                          |
                          |-- CourseObjective (1:N)
                          |-- TheoryUnit (1:N)
                          |-- Practical (1:N)
                          |-- EvaluationScheme (1:1)
                          |-- CourseOutcome (1:N)
                          |     +-- OutcomeMapping (1:1)  [po1..po12, pso1, pso2]
                          +-- LearningResource (1:N)
```

---

## 9. URL Reference

| URL | View Name | Description |
|-----|-----------|-------------|
| `/login/` | `login` | Login page |
| `/logout/` | `logout` | Logout |
| `/faculty/dashboard/` | `faculty_dashboard` | Faculty home dashboard |
| `/faculty/syllabus-builder/?subject_id=N` | `syllabus_builder` | Build/edit a syllabus |
| `/faculty/validate-syllabus/` | `validate_syllabus` | AJAX validation endpoint |
| `/faculty/drafts/` | `faculty_drafts` | View/manage draft syllabi |
| `/faculty/render-preview/` | `render_preview` | Live preview (POST) |
| `/faculty/generate-pdf/<id>/` | `generate_pdf` | Generate individual PDF |
| `/semester/preview/<id>/` | `preview_semester_merge` | Preview merged semester PDF |
| `/semester/generate/<id>/` | `generate_semester_pdf` | Download merged semester PDF |

---

*Last updated: 2026-07-29 | GSFC University Syllabus Management System*
