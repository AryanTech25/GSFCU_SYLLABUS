# Implementation Plan: Syllabus Audit and Draft Enhancements

## Overview

This implementation plan breaks down the development of two key features:
1. **Edit History Logging System**: Comprehensive audit trail for all syllabus modifications with timestamp, user identity, IP address, and field-level change tracking
2. **Progressive Draft Saving**: Enhanced draft management with slide-based validation, completeness tracking, and PDF generation restrictions

The implementation follows a logical sequence: database foundations → backend components → view layer → UI integration → access control → testing.

## Tasks

- [ ] 1. Set up database migrations and models
  - [ ] 1.1 Create SyllabusEditLog model migration
    - Create new `SyllabusEditLog` model in `accounts/models.py`
    - Define all fields: syllabus (FK), user (FK), timestamp, ip_address, action_type, model_name, record_id, field_name, old_value (JSONField), new_value (JSONField), description
    - Add Meta class with ordering, indexes, and permissions
    - Implement custom save() method to prevent updates to existing logs
    - _Requirements: 1.1, 1.4, 1.6, 9.2, 9.3_

  - [ ] 1.2 Create Syllabus model enhancement migration
    - Add `last_completed_slide` IntegerField to Syllabus model with default=0
    - Generate and apply Django migration
    - _Requirements: 4.6_

  - [x] 1.3 Add database constraints for log immutability
    - Add CHECK constraint in migration to prevent updates at database level
    - Test constraint enforcement with direct SQL update attempts
    - _Requirements: 1.6, 9.1_

- [ ] 2. Implement Syllabus completeness tracking
  - [ ] 2.1 Add is_complete() method to Syllabus model
    - Implement method that checks all required sections (contact hours, credits, prerequisites, category, rationale, approval date, objectives, theory units, evaluation scheme, course outcomes, CO-PO mappings, learning resources)
    - Return tuple of (is_complete: bool, missing_fields: list)
    - Add logic to validate theory unit weightage sums to 100%
    - _Requirements: 5.1, 5.2, 5.3, 6.5_

  - [x] 2.2 Add get_completion_percentage() method to Syllabus model
    - Calculate percentage based on completed vs. required sections
    - Return integer percentage (0-100)
    - _Requirements: 7.5_

  - [x] 2.3 Write unit tests for completeness methods
    - Test is_complete() with all fields filled (should return True, [])
    - Test is_complete() with various missing field combinations
    - Test get_completion_percentage() accuracy
    - Test theory unit weightage validation (99.9%, 100%, 100.1%)
    - _Requirements: 5.1, 5.2, 5.3_

- [ ] 3. Create Audit Logger component
  - [x] 3.1 Create audit_logger.py module
    - Create `accounts/audit_logger.py` file
    - Implement AuditLogger class with static methods
    - Add get_client_ip() method to extract IP from request (handle X-Forwarded-For header)
    - _Requirements: 1.5_

  - [x] 3.2 Implement log_change() method
    - Add method signature: log_change(syllabus, user, ip_address, model_name, record_id, field_name, old_value, new_value, action_type)
    - Implement value serialization for strings, numbers, booleans, lists, dicts
    - Create SyllabusEditLog entry with all parameters
    - Generate human-readable description based on action_type
    - _Requirements: 1.1, 1.2, 1.4, 8.1, 8.2, 8.3_

  - [x] 3.3 Implement log_bulk_change() method
    - Add method for logging bulk operations
    - Accept list of changes with action, record_id, and data
    - Create single Edit_Log entry for bulk operations
    - _Requirements: 8.4, 8.5_

  - [x] 3.4 Write unit tests for AuditLogger
    - Test get_client_ip() with and without X-Forwarded-For header
    - Test log_change() creates correct log entry with all field types
    - Test value serialization for various data types
    - Test log_bulk_change() for bulk operations
    - Test error handling when log creation fails
    - _Requirements: 1.1, 1.4, 1.5_

- [ ] 4. Implement Django signals for automatic audit logging
  - [x] 4.1 Create signal handlers for Syllabus model
    - Create `accounts/signals.py` file
    - Implement post_save signal receiver for Syllabus model
    - Use pre_save to capture old values before save
    - Store old values in thread-local or instance attribute
    - Wrap audit logging in try-except to prevent blocking main operation
    - Log audit failures to Django error log but allow save to succeed
    - _Requirements: 1.1, 1.2, 1.3, 8.5_

  - [x] 4.2 Create signal handlers for related models
    - Implement post_save/post_delete signals for CourseObjective, TheoryUnit, Practical, CourseOutcome, OutcomeMapping, EvaluationScheme, LearningResource
    - Extract syllabus reference from each related model
    - Call AuditLogger.log_change() with appropriate model_name and record_id
    - _Requirements: 8.1, 8.2, 8.3_

  - [x] 4.3 Register signals in AppConfig
    - Import signals in accounts/apps.py ready() method
    - Ensure signals are registered on application startup
    - _Requirements: 1.1, 1.2_

  - [x] 4.4 Write integration tests for signal handlers
    - Test that Syllabus save creates audit log entry
    - Test that CourseObjective creation creates audit log
    - Test that bulk delete creates appropriate log entries
    - Test concurrent modifications with select_for_update()
    - _Requirements: 1.1, 1.2, 8.4_

- [x] 5. Checkpoint - Ensure audit logging is functional
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement Slide Validator component
  - [x] 6.1 Create validators.py module with SlideValidator class
    - Create `accounts/validators.py` file
    - Define SLIDES dictionary mapping slide numbers (1-8) to required fields and validators
    - Slide 1: Basic Information (hours, credits, prerequisites, category)
    - Slide 2: Course Objectives
    - Slide 3: Theory Units (including 100% weightage validation)
    - Slide 4: Practicals (optional)
    - Slide 5: Evaluation Scheme
    - Slide 6: Course Outcomes & CO-PO Mapping
    - Slide 7: Learning Resources
    - Slide 8: Rationale & Approval
    - _Requirements: 4.1, 4.4_

  - [x] 6.2 Implement validate_slide() method
    - Add method signature: validate_slide(slide_number, data)
    - Check all required fields for the specified slide
    - Run custom validators for each field
    - Return tuple of (is_valid: bool, errors: dict)
    - _Requirements: 4.1, 4.3, 5.2_

  - [x] 6.3 Implement validate_up_to_slide() method
    - Add method to validate all slides from 1 to current_slide
    - Aggregate errors across all slides
    - Return tuple of (is_valid: bool, all_errors: dict, first_invalid_slide: int)
    - _Requirements: 4.1, 4.2_

  - [x] 6.4 Write unit tests for SlideValidator
    - Test validate_slide() for each slide (1-8) with valid data
    - Test validate_slide() for each slide with missing required fields
    - Test validate_slide() for each slide with invalid data
    - Test validate_up_to_slide() progressive validation
    - Test theory unit weightage validation (99%, 100%, 101%)
    - Test numeric field validation (negative values should fail)
    - _Requirements: 4.1, 4.3, 5.2_

- [ ] 7. Implement Access Controller component
  - [x] 7.1 Create AuditLogAccessController class
    - Add AuditLogAccessController class in `accounts/views.py` or separate module
    - Implement get_logs_for_user() static method
    - Filter logs: Admin sees all, Faculty sees only assigned subjects
    - Apply optional filters: subject_id, date_from, date_to, user_id (admin only)
    - Use select_related() for efficient queries
    - _Requirements: 2.1, 3.1, 3.3_

  - [x] 7.2 Implement can_view_log() method
    - Add method signature: can_view_log(user, log_entry)
    - Return True for admin users
    - For faculty, check if log's syllabus subject is in their assigned subjects
    - _Requirements: 3.3_

  - [x] 7.3 Write unit tests for AuditLogAccessController
    - Test get_logs_for_user() for admin returns all logs
    - Test get_logs_for_user() for faculty returns only assigned subject logs
    - Test filtering by subject_id, date_from, date_to
    - Test can_view_log() permission checking
    - Test access denial for unassigned subjects
    - _Requirements: 2.1, 3.1, 3.3_

- [ ] 8. Create view functions for audit logs
  - [x] 8.1 Implement audit_log_list view
    - Create view function in `accounts/views.py`
    - Extract filter parameters from request.GET (subject, date_from, date_to, user)
    - Call AuditLogAccessController.get_logs_for_user() with filters
    - Implement pagination (50 entries per page)
    - Get available subjects for filter dropdown (all for admin, assigned for faculty)
    - Pass logs, subjects, and filters to template context
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.4_

  - [x] 8.2 Implement audit_log_detail view
    - Create view to display single log entry details
    - Use get_object_or_404 to retrieve log entry
    - Check permissions with AuditLogAccessController.can_view_log()
    - Return HttpResponseForbidden if user lacks permission
    - _Requirements: 2.5, 3.3_

  - [x] 8.3 Add URL patterns for audit log views
    - Add URL routes in `accounts/urls.py`
    - Route for list view: `/audit-logs/`
    - Route for detail view: `/audit-logs/<int:log_id>/`
    - Add @login_required decorator to views
    - _Requirements: 2.1, 3.1_

  - [x] 8.4 Write integration tests for audit log views
    - Test audit_log_list as admin returns all logs
    - Test audit_log_list as faculty returns filtered logs
    - Test filtering by date range and subject
    - Test pagination
    - Test audit_log_detail permission checks
    - Test 403 response for unauthorized access
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.3_

- [x] 9. Update syllabus save view for progressive validation
  - [x] 9.1 Modify syllabus builder save endpoint
  - [x] 9.2 Add draft status calculation after save
  - [x] 9.3 Handle concurrent modification with optimistic locking
  - [x] 9.4 Write integration tests for progressive save

- [x] 10. Update PDF generation view to enforce completeness
  - [x] 10.1 Add completeness check to PDF generation endpoint
  - [x] 10.2 Write integration tests for PDF generation restriction

- [x] 11. Checkpoint - Ensure backend logic is complete
  - All backend tests pass (tasks 8.4 ✓, 9.4 ✓, 10.2 ✓).

- [x] 12. Create audit log UI templates
  - [x] 12.1 Create audit_log_list.html template
  - [x] 12.2 Create audit_log_detail.html template
  - [x] 12.3 Add navigation link to audit logs

- [x] 13. Update drafts page UI for completeness indicators
  - [x] 13.1 Add completeness status column to drafts table
  - [x] 13.2 Add tooltip showing missing fields for incomplete drafts
  - [x] 13.3 Add visual distinction between complete and incomplete drafts
  - [x] 13.4 Disable PDF generation button for incomplete drafts
  - [x] 13.5 Update drafts queryset to include completeness data

- [x] 14. Update syllabus builder UI for progressive saving
  - [x] 14.1 Add "Save Draft" button to every slide (sticky floating bar)
  - [x] 14.2 Implement JavaScript AJAX save draft functionality
  - [x] 14.3 Add visual feedback (spinner, success/error toast)
  - [x] 14.4 Preserve slide position after save (AJAX stays on slide)
  - [x] 14.5 Display completeness indicator (progress bar in save bar)

- [x] 15. Add error handling and user feedback
  - [x] 15.1 Graceful audit logging failure (already in audit_logger.py try/except + logger.error)
  - [x] 15.2 User-friendly validation error messages (toast + inline highlighting)
  - [x] 15.3 PDF error handling (JSON 400 with missing_fields; frontend updates PDF URL on AJAX save)

- [x] 16. Implement access control and permissions
  - [x] 16.1 @login_required on all audit log views
  - [x] 16.2 Log unauthorized access attempts via accounts.audit_access logger
  - [x] 16.3 view_all_logs permission check in audit_log_list view

- [ ] 17. Final integration and end-to-end testing
  - [ ]* 17.1 Test complete syllabus creation workflow
    - Create new syllabus starting from slide 1
    - Save draft at each slide and verify progressive validation
    - Complete all required sections
    - Verify draft marked as complete
    - Generate PDF successfully
    - Check audit log entries created for all saves
    - _Requirements: 1.1, 4.1, 4.2, 5.1, 6.2, 7.1_

  - [ ]* 17.2 Test admin audit log access
    - Login as admin user
    - View all audit logs across all subjects
    - Filter by subject, date range, and user
    - Verify pagination works correctly
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 17.3 Test faculty audit log access with permission restrictions
    - Login as faculty user
    - Verify only assigned subject logs are visible
    - Attempt to access unassigned subject log (should fail)
    - Filter by date range and assigned subjects
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ]* 17.4 Test concurrent editing and conflict detection
    - Open same syllabus in two browser sessions
    - Edit and save in both sessions
    - Verify second save detects conflict
    - _Requirements: 4.6_

  - [ ]* 17.5 Test PDF generation restriction
    - Attempt to generate PDF from incomplete draft (should fail)
    - Complete all required sections
    - Generate PDF successfully
    - Verify error messages for incomplete draft
    - _Requirements: 6.1, 6.2, 6.5_

  - [ ]* 17.6 Test audit log immutability
    - Attempt to update existing audit log entry (should raise ValueError)
    - Attempt to delete syllabus and verify logs are retained
    - Deactivate faculty user and verify logs are retained
    - _Requirements: 1.6, 9.2, 9.3_

- [ ] 18. Final checkpoint - Complete implementation review
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional testing tasks and can be skipped for faster MVP
- Each task references specific requirements from the requirements document for traceability
- The implementation uses Python and Django framework as specified in the design document
- Checkpoints ensure incremental validation at logical breakpoints
- Testing tasks are complementary to implementation tasks and provide confidence in correctness
- Signal handlers are used for automatic audit logging to decouple logging from business logic
- Progressive validation allows flexible draft saving while maintaining data quality
- Access control is enforced at multiple layers (view, controller, database) for security

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "3.1"] },
    { "id": 3, "tasks": ["3.2", "3.3"] },
    { "id": 4, "tasks": ["3.4", "4.1"] },
    { "id": 5, "tasks": ["4.2", "4.3"] },
    { "id": 6, "tasks": ["4.4", "6.1"] },
    { "id": 7, "tasks": ["6.2", "6.3"] },
    { "id": 8, "tasks": ["6.4", "7.1"] },
    { "id": 9, "tasks": ["7.2", "7.3"] },
    { "id": 10, "tasks": ["8.1", "8.2", "8.3"] },
    { "id": 11, "tasks": ["8.4", "9.1"] },
    { "id": 12, "tasks": ["9.2", "9.3"] },
    { "id": 13, "tasks": ["9.4", "10.1"] },
    { "id": 14, "tasks": ["10.2", "12.1", "12.2"] },
    { "id": 15, "tasks": ["12.3", "13.1"] },
    { "id": 16, "tasks": ["13.2", "13.3", "13.4", "13.5"] },
    { "id": 17, "tasks": ["14.1", "14.2"] },
    { "id": 18, "tasks": ["14.3", "14.4", "14.5"] },
    { "id": 19, "tasks": ["15.1", "15.2", "15.3"] },
    { "id": 20, "tasks": ["16.1", "16.2", "16.3"] },
    { "id": 21, "tasks": ["17.1", "17.2", "17.3", "17.4", "17.5", "17.6"] }
  ]
}
```
