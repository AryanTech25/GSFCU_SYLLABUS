# Admin Panel — Complete Flow Documentation

> **GSFC University Syllabus Management System**
> End-to-end flow for an Admin user — from faculty management to semester PDF generation.

---

## Table of Contents

1. [Login](#1-login)
2. [Admin Dashboard](#2-admin-dashboard)
3. [Faculty Management](#3-faculty-management)
   - 3.1 [Create Faculty](#31-create-faculty)
   - 3.2 [Edit Faculty](#32-edit-faculty)
   - 3.3 [Delete Faculty](#33-delete-faculty)
4. [Subject Management](#4-subject-management)
   - 4.1 [Create Subject](#41-create-subject)
   - 4.2 [Delete Subject](#42-delete-subject)
5. [Syllabus Management](#5-syllabus-management)
   - 5.1 [View All Syllabi](#51-view-all-syllabi)
   - 5.2 [Delete a Syllabus](#52-delete-a-syllabus)
6. [Semester Structure Management](#6-semester-structure-management)
   - 6.1 [Manage Semester Structure](#61-manage-semester-structure)
   - 6.2 [Preview Semester PDF](#62-preview-semester-pdf)
   - 6.3 [Generate and Download Semester PDF](#63-generate-and-download-semester-pdf)
   - 6.4 [View / Download Saved Semester PDF](#64-view--download-saved-semester-pdf)
   - 6.5 [Delete Semester PDF](#65-delete-semester-pdf)
   - 6.6 [Generate Full Program Syllabus](#66-generate-full-program-syllabus)
7. [Program Outcomes (PO) Management](#7-program-outcomes-po-management)
8. [Program Specific Outcomes (PSO) Management](#8-program-specific-outcomes-pso-management)
9. [Program Educational Objectives (PEO) Management](#9-program-educational-objectives-peo-management)
10. [Data Model Diagram (Admin Scope)](#10-data-model-diagram-admin-scope)
11. [URL Reference](#11-url-reference)
12. [Auto-Invalidation Logic (Signals)](#12-auto-invalidation-logic-signals)

---

## 1. Login

- **URL:** `/login/`
- **Template:** `accounts/templates/accounts/login.html`
- **View:** `accounts.views.login_view`

### Flow

1. Admin navigates to `/login/`.
2. Enters Django superuser / staff credentials.
3. Since `user.is_staff = True` → redirected to **Admin Dashboard** at `/dashboard/`.
4. Non-staff users (faculty) are redirected to `/faculty/dashboard/` instead.

> Admin accounts are Django staff accounts (`is_staff=True`). Created via `python manage.py createsuperuser` or Django Admin.

---

## 2. Admin Dashboard

- **URL:** `/dashboard/`
- **Template:** `adminpanel/templates/adminpanel/dashboard.html`
- **View:** `adminpanel.views.admin_dashboard`

### What Is Shown

| Section | Description |
|---------|-------------|
| Faculty List | All faculty accounts with their school/program/branch details |
| Subject List | All subjects in the system with their syllabus status |
| Filters | Filter subjects by School, Program, Branch, Semester |
| Quick Actions | Create Faculty, Create Subject, Manage Semester, Manage POs/PSOs/PEOs |
| Stats Strip | Counts of faculties, subjects, syllabi (draft/final) |

### Filtering Logic

Admin can filter the subject list by:
- **School** (dropdown, populated dynamically)
- **Program** (dynamic — updates when School is selected via AJAX)
- **Branch** (dynamic — updates when Program is selected via AJAX)
- **Semester** (static dropdown: Semester I through VIII etc.)

AJAX Endpoints:
- `GET /admin/api/get-programs/?school_id=N` → returns programs for a school
- `GET /admin/api/get-branches/?program_id=N` → returns branches for a program

---

## 3. Faculty Management

### 3.1 Create Faculty

- **URL:** `/admin/faculty/create/`
- **Template:** `adminpanel/templates/adminpanel/dashboard.html` (modal or section)
- **View:** `adminpanel.views.create_faculty`

#### Fields Required

| Field | Description |
|-------|-------------|
| Full Name | Faculty member's full name |
| Faculty ID | Unique institutional ID (e.g., FAC001) |
| Email | Faculty email address |
| Mobile | Contact number |
| Semester | Assigned teaching semester |
| School | School this faculty belongs to |
| Program | Program within the school |
| Branch | Branch / specialization |
| Academic Year | e.g., 2025-26 |
| Username | Login username for the faculty account |
| Password | Login password (set by admin) |

#### What Happens

1. Admin fills the create-faculty form and submits.
2. A Django `User` object is created (`is_staff=False`).
3. A `Faculty` record linked to that `User` is created with all the above fields.
4. Faculty can now log in with the given credentials.

---

### 3.2 Edit Faculty

- **URL:** `/admin/faculty/edit/<faculty_id>/`
- **Template:** `adminpanel/templates/adminpanel/edit_faculty.html`
- **View:** `adminpanel.views.edit_faculty`

- Admin can update all faculty fields including School, Program, Branch, and Academic Year.
- Username/password can also be updated here.
- Changes reflect immediately on the faculty's next login.

---

### 3.3 Delete Faculty

- **URL:** `/admin/faculty/delete/<faculty_id>/`
- **View:** `adminpanel.views.delete_faculty`

- Deletes the `Faculty` record and the associated `User` account.
- **Does NOT delete subjects** assigned to this faculty (subjects are global master data).
- Faculty-subject associations (`SubjectFaculty`) are cleared automatically.

---

## 4. Subject Management

### 4.1 Create Subject

- **URL:** `/admin/subject/create/`
- **View:** `adminpanel.views.create_subject`

#### Fields

| Field | Description |
|-------|-------------|
| Course Name | e.g., "Data Structures" |
| Course Code | e.g., "CS301" |
| Semester | Semester in which this subject is taught |
| Academic Year | e.g., 2025-26 |
| School | Owning school |
| Program | Owning program |
| Branch | Branch / specialization |
| Assigned Faculties | One or more faculty members (M2M) |

#### What Happens

1. A `Subject` record is created.
2. `SubjectFaculty` through-table entries are created linking the subject to selected faculty.
3. The subject now appears on the assigned faculty's dashboard.

---

### 4.2 Delete Subject

- **URL:** `/admin/subject/delete/<subject_id>/`
- **View:** `adminpanel.views.delete_subject`

- Permanently deletes the `Subject`.
- Cascades: deletes the `Syllabus` and all related data (TheoryUnits, Practicals, COs, etc.).
- **Auto-Invalidation Signal fires**: any `SemesterReference` (merged PDF) containing this subject is permanently deleted (both file and database record).

---

## 5. Syllabus Management

### 5.1 View All Syllabi

Visible on the Admin Dashboard subject list. For each subject the admin can see:
- Syllabus status: `No Syllabus` / `Draft` / `Final`
- PDF file status: `Generated` (with timestamp) / `Not Generated`
- Link to view the PDF inline

### 5.2 Delete a Syllabus

- **URL:** `/admin/syllabus/delete/<syllabus_id>/`
- **View:** `adminpanel.views.delete_syllabus`

- Deletes the `Syllabus` and all its children (Objectives, Units, Practicals, COs, Evaluation, Resources).
- Deletes the physical PDF file from disk.
- **Auto-Invalidation Signal fires**: any `SemesterReference` (merged PDF) containing this syllabus is permanently deleted.
- The parent `Subject` record is **not deleted** — only the syllabus content is removed.

---

## 6. Semester Structure Management

This is the core multi-course PDF pipeline, managed entirely by the Admin.

### 6.1 Manage Semester Structure

- **URL:** `/admin/semester/manage/`
- **Template:** `adminpanel/templates/adminpanel/manage_semester.html`
- **View:** `adminpanel.views.manage_semester_structure`

#### What Admin Does Here

1. **Select filters**: School, Program, Branch, Semester.
2. A list of subjects matching those filters is shown.
3. Admin can **assign subjects to the semester** (creates `Semester` and `SemesterSubject` records).
4. Admin can **reorder subjects** (sets the `sequence` field on `SemesterSubject`).
5. Admin can **remove a subject** from the semester structure.

#### Models Involved

```
Semester
  |-- program (FK to Program)
  |-- semester_number (e.g., "Semester V")
  |
  +-- SemesterSubject (through model)
        |-- subject (FK to Subject)
        +-- sequence (ordering integer)
```

---

### 6.2 Preview Semester PDF

- **URL:** `/admin/semester/preview-pdf/`
- **View:** `adminpanel.views.preview_semester_pdf`

1. Admin applies filters (School, Program, Branch, Semester) and clicks **Preview PDF**.
2. View finds all subjects with Final syllabi and existing PDFs for that filter set.
3. Calls `_create_summary_pdf()` (ReportLab) to build the Cover / Course Structure page.
4. Merges the Cover page with all individual syllabus PDFs using **pypdf**.
5. Streams the merged PDF back to the browser as inline display (no file saved).

---

### 6.3 Generate and Download Semester PDF

- **URL:** `/admin/semester/generate-pdf/`
- **View:** `adminpanel.views.generate_semester_pdf`

Similar to Preview, but:
1. Saves the merged PDF to `media/semester_pdfs/`.
2. Creates or updates a `SemesterReference` database record.
3. Returns the PDF as a file download response.

> If any source subject PDFs are missing or stale, those subjects are skipped and a warning message is shown.

---

### 6.4 View / Download Saved Semester PDF

- **URL (view inline):** `/admin/semester/view-pdf/?...filters...`
- **URL (download):** `/admin/semester/download-pdf/?...filters...`
- **Views:** `adminpanel.views.view_semester_pdf` · `adminpanel.views.download_semester_pdf`

- Retrieves the saved `SemesterReference` for the given filter set.
- Streams the stored PDF file back as inline view or forced download.

---

### 6.5 Delete Semester PDF

- **URL:** `/admin/semester/delete/`
- **View:** `adminpanel.views.delete_semester_pdf`

- Deletes the physical PDF file from disk.
- Deletes the `SemesterReference` database record.
- The underlying subjects/syllabi are NOT affected.

---

### 6.6 Generate Full Program Syllabus

- **URL:** `/admin/semester/generate-full/`
- **View:** `adminpanel.views.generate_full_program_syllabus`

- Generates a single mega-PDF covering **all semesters** of a program.
- Iterates over all `Semester` records for a program, runs the merge logic for each.
- Concatenates all semester PDFs into one file.
- Useful for producing a complete program-level syllabus booklet.

---

## 7. Program Outcomes (PO) Management

- **URL (list/create):** `/admin/program-outcomes/`
- **URL (edit):** `/admin/program-outcomes/<po_id>/edit/`
- **URL (delete):** `/admin/program-outcomes/<po_id>/delete/`
- **Template:** `adminpanel/templates/adminpanel/manage_program_outcomes.html`
- **Views:** `manage_program_outcomes` · `edit_program_outcome` · `delete_program_outcome`

### What Admin Does

1. Selects a **Program** from the dropdown.
2. Adds POs for that program: Code (e.g., PO1) + Description text + Display Order.
3. Each PO is linked to the program and displayed in the CO-PO mapping matrix inside the syllabus PDF.

### Model: `ProgramOutcome`

| Field | Description |
|-------|-------------|
| program | FK to Program |
| code | e.g., PO1, PO2 … PO12 |
| description | Full outcome statement |
| order | Display order in the matrix |

---

## 8. Program Specific Outcomes (PSO) Management

- **URL (list/create):** `/admin/program-specific-outcomes/`
- **URL (edit):** `/admin/program-specific-outcomes/<pso_id>/edit/`
- **URL (delete):** `/admin/program-specific-outcomes/<pso_id>/delete/`
- **Template:** `adminpanel/templates/adminpanel/manage_program_specific_outcomes.html`

### What Admin Does

1. Selects a **Branch** (PSOs are branch-specific, unlike POs which are program-wide).
2. Adds PSOs: Code (e.g., PSO1, PSO2) + Description + Order.

### Model: `ProgramSpecificOutcome`

| Field | Description |
|-------|-------------|
| branch | FK to Branch |
| code | e.g., PSO1, PSO2 |
| description | Full outcome statement |
| order | Display order |

---

## 9. Program Educational Objectives (PEO) Management

- **URL (list/create):** `/admin/program-educational-objectives/`
- **URL (edit):** `/admin/program-educational-objectives/<peo_id>/edit/`
- **URL (delete):** `/admin/program-educational-objectives/<peo_id>/delete/`
- **Template:** `adminpanel/templates/adminpanel/manage_program_educational_objectives.html`

### What Admin Does

1. Selects a **Program**.
2. Adds PEOs: Code (e.g., PEO1) + Description + Order.

### Model: `ProgramEducationalObjective`

| Field | Description |
|-------|-------------|
| program | FK to Program |
| code | e.g., PEO1, PEO2 |
| description | Full objective statement |
| order | Display order |

---

## 10. Data Model Diagram (Admin Scope)

```
School
  |-- code (unique)
  |-- name
  |
  +-- Program (1:N)
        |-- name
        |
        +-- Branch (1:N)
        |     |-- name
        |     |
        |     +-- ProgramSpecificOutcome (1:N)  [PSO1, PSO2 ...]
        |
        +-- ProgramOutcome (1:N)  [PO1 .. PO12]
        |
        +-- ProgramEducationalObjective (1:N)  [PEO1, PEO2 ...]
        |
        +-- Semester (1:N)
              |-- semester_number (e.g., "Semester V")
              |
              +-- SemesterSubject (1:N)   [ordered]
              |     |-- subject (FK)
              |     +-- sequence (int)
              |
              +-- SemesterFacultyAccess (1:N)
              |     +-- faculty (FK)
              |
              +-- SemesterReference (1:1 per branch)
                    |-- pdf_file (merged PDF)
                    |-- is_valid
                    +-- is_deleted

Faculty
  |-- User (1:1)
  |-- full_name, faculty_id, email, mobile
  |-- semester, academic_year
  |-- School (FK), Program (FK), Branch (FK)
  |
  +-- SubjectFaculty (M2M through)
        +-- Subject
              |-- course_name, course_code, semester, academic_year
              |-- School (FK), Program (FK), Branch (FK)
              |
              +-- Syllabus (1:1)
                    |-- Teaching Scheme fields (hours + credits)
                    |-- Category, Focus, Rationale, Prerequisites
                    |-- status: draft / final
                    |-- pdf_file, pdf_generated_at
                    |
                    |-- CourseObjective (1:N)
                    |-- TheoryUnit (1:N)
                    |-- Practical (1:N)
                    |-- EvaluationScheme (1:1)
                    |     |-- mid_sem, end_sem
                    |     |-- cec_attendance, cec_mcq, cec_assignment
                    |     +-- prac_attendance, prac_exam, prac_viva, prac_journal, prac_discipline
                    |
                    |-- CourseOutcome (1:N)
                    |     +-- OutcomeMapping (1:1) [po1..po12, pso1, pso2]
                    |
                    +-- LearningResource (1:N)
```

---

## 11. URL Reference

| URL | View Name | Description |
|-----|-----------|-------------|
| `/dashboard/` | `admin_dashboard` | Main admin dashboard |
| `/admin/faculty/create/` | `create_faculty` | Create a new faculty account |
| `/admin/faculty/edit/<id>/` | `edit_faculty` | Edit faculty details |
| `/admin/faculty/delete/<id>/` | `delete_faculty` | Delete a faculty account |
| `/admin/subject/create/` | `create_subject` | Create a new subject |
| `/admin/subject/delete/<id>/` | `delete_subject` | Delete a subject (cascades) |
| `/admin/syllabus/delete/<id>/` | `delete_syllabus` | Delete a syllabus (keeps subject) |
| `/admin/semester/manage/` | `manage_semester_structure` | Manage semester subject assignments |
| `/admin/semester/preview-pdf/` | `preview_semester_pdf` | Preview merged semester PDF |
| `/admin/semester/generate-pdf/` | `generate_semester_pdf` | Generate + download merged PDF |
| `/admin/semester/view-pdf/` | `view_semester_pdf` | View saved merged PDF inline |
| `/admin/semester/download-pdf/` | `download_semester_pdf` | Force-download saved merged PDF |
| `/admin/semester/delete/` | `delete_semester_pdf` | Delete a saved merged PDF |
| `/admin/semester/generate-full/` | `generate_full_program_syllabus` | Generate all-semester program PDF |
| `/admin/api/get-programs/` | `get_programs` | AJAX: programs for a school |
| `/admin/api/get-branches/` | `get_branches` | AJAX: branches for a program |
| `/admin/program-outcomes/` | `manage_program_outcomes` | Manage POs |
| `/admin/program-outcomes/<id>/edit/` | `edit_program_outcome` | Edit a PO |
| `/admin/program-outcomes/<id>/delete/` | `delete_program_outcome` | Delete a PO |
| `/admin/program-specific-outcomes/` | `manage_program_specific_outcomes` | Manage PSOs |
| `/admin/program-specific-outcomes/<id>/edit/` | `edit_program_specific_outcome` | Edit a PSO |
| `/admin/program-specific-outcomes/<id>/delete/` | `delete_program_specific_outcome` | Delete a PSO |
| `/admin/program-educational-objectives/` | `manage_program_educational_objectives` | Manage PEOs |
| `/admin/program-educational-objectives/<id>/edit/` | `edit_program_educational_objective` | Edit a PEO |
| `/admin/program-educational-objectives/<id>/delete/` | `delete_program_educational_objective` | Delete a PEO |

---

## 12. Auto-Invalidation Logic (Signals)

When any component of a merged semester PDF is modified or deleted, the stale PDF is automatically removed.

### Signal: `invalidate_semester_pdf`

**Triggered by:** `post_delete` on `Subject`, `Syllabus`, or `SemesterSubject`

| Trigger | Action |
|---------|--------|
| `Subject` deleted | Finds all `SemesterReference` containing this subject; deletes file + DB record |
| `Syllabus` deleted | Finds all `SemesterReference` containing the syllabus's subject; deletes file + DB record |
| `SemesterSubject` deleted | Finds `SemesterReference` for that semester; deletes file + DB record |

This ensures that the Admin is always shown fresh, valid merged PDFs and stale files are never served.

---

*Last updated: 2026-07-29 | GSFC University Syllabus Management System*
