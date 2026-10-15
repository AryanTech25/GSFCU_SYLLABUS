# Requirements Document

## Introduction

This document specifies requirements for two new features in the GSFC Syllabus Management System: an edit history and audit logging system for syllabus modifications, and an enhanced draft-saving mechanism that allows faculty to save incomplete drafts at any moment during multi-step syllabus creation.

## Glossary

- **System**: The GSFC Syllabus Management System
- **Admin_User**: A staff user with is_staff=True who has access to all system logs
- **Faculty_User**: A non-staff user with is_staff=False who can create and edit syllabi for assigned subjects
- **Syllabus_Record**: A database record representing a syllabus with status of 'draft' or 'final'
- **Edit_Log**: An audit trail entry recording timestamp, user identity, and modification details
- **Draft_Status_Manager**: The component that manages draft completeness states
- **Incomplete_Draft**: A syllabus draft saved at any stage before all required fields are completed
- **Complete_Draft**: A syllabus draft where all required sections are filled and ready for PDF generation
- **PDF_Generator**: The component that generates PDF output from syllabus data
- **Multi_Step_Form**: The syllabus creation form with multiple subpages/slides
- **Required_Section**: A mandatory field or section that must be filled for PDF generation
- **Audit_Logger**: The component responsible for recording edit operations to the audit log
- **Access_Controller**: The component that filters audit logs based on user role and permissions

## Requirements

### Requirement 1: Edit History Logging

**User Story:** As a system administrator, I want all syllabus edits to be logged with timestamp, user identity, and change details, so that I can maintain an audit trail for compliance and troubleshooting.

#### Acceptance Criteria

1. WHEN a Faculty_User modifies a Syllabus_Record, THE Audit_Logger SHALL create an Edit_Log entry with timestamp, user identity, and field-level changes
2. WHEN an Admin_User modifies a Syllabus_Record, THE Audit_Logger SHALL create an Edit_Log entry with timestamp, user identity, and field-level changes
3. WHEN a Syllabus_Record status transitions from 'draft' to 'final', THE Audit_Logger SHALL record the status change in the Edit_Log
4. THE Edit_Log SHALL include the previous value and new value for each modified field
5. THE Edit_Log SHALL include the IP address of the user making the modification
6. THE Edit_Log SHALL be immutable after creation

### Requirement 2: Admin Audit Log Access

**User Story:** As an administrator, I want to view all edit logs for all syllabi, so that I can monitor system-wide activity and investigate issues.

#### Acceptance Criteria

1. WHEN an Admin_User requests audit logs, THE Access_Controller SHALL return all Edit_Log entries across all subjects
2. THE System SHALL provide filtering by date range, user identity, and subject
3. THE System SHALL display Edit_Log entries in reverse chronological order by default
4. THE System SHALL paginate Edit_Log results with a maximum of 50 entries per page
5. WHEN an Admin_User views an Edit_Log entry, THE System SHALL display timestamp, faculty name, subject name, field changed, old value, and new value

### Requirement 3: Faculty Audit Log Access

**User Story:** As a faculty member, I want to view edit history for my assigned subjects, so that I can track my own modifications and review past changes.

#### Acceptance Criteria

1. WHEN a Faculty_User requests audit logs, THE Access_Controller SHALL return only Edit_Log entries for subjects assigned to that Faculty_User
2. THE System SHALL display the Faculty_User's own edits and edits made by other faculty members on shared subjects
3. WHEN a Faculty_User attempts to access logs for unassigned subjects, THE Access_Controller SHALL deny access and return an error message
4. THE System SHALL provide filtering by date range and subject within the Faculty_User's assigned subjects

### Requirement 4: Progressive Draft Saving with Validation

**User Story:** As a faculty member, I want to save my work at any moment during syllabus creation, so that I don't lose progress when working through the multi-step form, while ensuring data quality through progressive validation.

#### Acceptance Criteria

1. WHEN a Faculty_User clicks save on any slide of the Multi_Step_Form, THE Draft_Status_Manager SHALL validate only the fields on slides that have been completed up to and including the current slide
2. WHEN validation for the current and previous slides passes, THE System SHALL save all entered data as an Incomplete_Draft or Complete_Draft based on overall completeness
3. WHEN validation fails on the current slide, THE System SHALL display error messages and prevent saving until errors are corrected
4. THE System SHALL allow saving without validating fields on slides that have not yet been visited or completed
5. WHEN an Incomplete_Draft is saved, THE System SHALL preserve partial data for all form fields
6. WHEN a Faculty_User returns to edit an Incomplete_Draft, THE System SHALL restore all previously saved field values and maintain validation state for each slide

### Requirement 5: Complete Draft Identification

**User Story:** As a faculty member, I want the system to distinguish between incomplete and complete drafts, so that I know which drafts are ready for PDF generation.

#### Acceptance Criteria

1. WHEN all Required_Section fields in a Syllabus_Record are filled, THE Draft_Status_Manager SHALL mark the draft as a Complete_Draft
2. THE System SHALL validate Required_Section completeness before marking a draft as Complete_Draft
3. THE Required_Section fields SHALL include: course objectives, theory units with 100% weightage total, evaluation scheme, course outcomes, CO-PO mappings, and learning resources
4. WHEN a Complete_Draft has any Required_Section field removed or emptied, THE Draft_Status_Manager SHALL revert the draft to Incomplete_Draft status
5. THE System SHALL recalculate draft completeness status after each save operation

### Requirement 6: PDF Generation Restriction

**User Story:** As a system designer, I want PDF generation to be restricted to complete drafts only, so that incomplete syllabi are not exported to PDF format.

#### Acceptance Criteria

1. WHEN a Faculty_User attempts to generate a PDF from an Incomplete_Draft, THE PDF_Generator SHALL reject the request with an error message
2. WHEN a Faculty_User attempts to generate a PDF from a Complete_Draft, THE PDF_Generator SHALL proceed with PDF creation
3. THE System SHALL display a visual indicator on the drafts page showing which drafts are Complete_Draft and which are Incomplete_Draft
4. THE System SHALL disable the PDF generation button for Incomplete_Draft entries on the drafts page
5. THE System SHALL display a list of missing Required_Section fields when PDF generation is attempted on an Incomplete_Draft

### Requirement 7: Draft List Differentiation

**User Story:** As a faculty member, I want to see at a glance which of my drafts are complete and ready for PDF generation, so that I can prioritize completing unfinished work.

#### Acceptance Criteria

1. WHEN a Faculty_User views the drafts page, THE System SHALL display a completeness status indicator for each draft
2. THE System SHALL use distinct visual styling for Complete_Draft and Incomplete_Draft entries
3. WHEN a Faculty_User hovers over an Incomplete_Draft, THE System SHALL display a tooltip showing which Required_Section fields are missing
4. THE System SHALL sort drafts by status (Complete_Draft first) and then by last modified timestamp
5. THE System SHALL display a progress percentage for Incomplete_Draft entries showing how many Required_Section fields are completed

### Requirement 8: Change Tracking Granularity

**User Story:** As an administrator, I want to see which specific fields were changed in each edit, so that I can understand the scope and nature of modifications.

#### Acceptance Criteria

1. WHEN a Faculty_User modifies course objectives, THE Audit_Logger SHALL record each objective added, modified, or deleted as separate Edit_Log entries
2. WHEN a Faculty_User modifies theory units, THE Audit_Logger SHALL record changes to unit title, description, weightage, and hours separately
3. WHEN a Faculty_User modifies CO-PO mappings, THE Audit_Logger SHALL record the specific mapping cell changed
4. THE Audit_Logger SHALL record bulk operations (such as deleting all objectives) as a single Edit_Log entry with details of all affected items
5. THE Audit_Logger SHALL NOT log auto-save operations or intermediate states during form navigation

### Requirement 9: Audit Log Data Retention

**User Story:** As a compliance officer, I want audit logs to be retained permanently, so that historical records are available for audits and investigations.

#### Acceptance Criteria

1. THE System SHALL NOT automatically delete Edit_Log entries
2. WHEN a Syllabus_Record is deleted, THE System SHALL retain all associated Edit_Log entries
3. WHEN a Faculty_User account is deactivated, THE System SHALL retain all Edit_Log entries created by that user
4. THE System SHALL support manual archival of Edit_Log entries older than a configurable retention period
5. WHEN Edit_Log entries are archived, THE System SHALL maintain data integrity and referential relationships

### Requirement 10: Save Draft Button Accessibility

**User Story:** As a faculty member, I want a save draft button available on every slide of the syllabus form, so that I can save my work without navigating to the end.

#### Acceptance Criteria

1. THE Multi_Step_Form SHALL display a "Save Draft" button on every slide
2. WHEN a Faculty_User clicks "Save Draft" on any slide, THE System SHALL save all data entered across all slides
3. THE System SHALL provide visual feedback indicating successful save completion
4. WHEN a save operation fails, THE System SHALL display an error message and retain the user's entered data
5. THE System SHALL preserve the user's current slide position after a successful save operation
