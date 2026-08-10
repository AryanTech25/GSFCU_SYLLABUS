# Design Document: Syllabus Audit and Draft Enhancements

## Overview

This design document outlines the technical approach for implementing two key features in the GSFC Syllabus Management System:

1. **Edit History Logging**: A comprehensive audit trail system that records all modifications to syllabus records with timestamp, user identity, IP address, and field-level change details.
2. **Progressive Draft Saving**: An enhanced draft management system allowing faculty to save incomplete drafts at any stage with slide-based validation, completeness tracking, and PDF generation restrictions.

### Design Goals

- **Audit Compliance**: Provide immutable, permanent audit logs suitable for compliance audits and investigations
- **Data Quality**: Ensure data integrity through progressive validation while allowing flexible draft saving
- **User Experience**: Enable faculty to save work at any moment without losing progress
- **Role-Based Access**: Implement secure, role-appropriate access to audit logs
- **Performance**: Minimize impact on syllabus save operations while maintaining comprehensive logging

### Key Design Decisions

1. **Separate Audit Model**: Create `SyllabusEditLog` as a dedicated model rather than using Django's generic audit framework to maintain control over data structure and retention
2. **Field-Level Granularity**: Track changes at the individual field level for related models (objectives, units, outcomes) rather than bulk change records
3. **Slide-Based Validation**: Implement progressive validation that validates only completed slides, not the entire form
4. **Completeness as Computed Property**: Calculate draft completeness on-demand rather than storing as a database field to ensure accuracy
5. **Immutable Logs**: Use database constraints and model design to prevent modification or deletion of audit logs
6. **JSONField for Change Tracking**: Use PostgreSQL's JSONField to store old/new values with flexibility for various data types


## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        Presentation Layer                         │
│  ┌─────────────────┐  ┌──────────────────┐  ┌─────────────────┐ │
│  │ Syllabus Builder│  │   Drafts Page    │  │  Audit Log UI   │ │
│  │   Multi-Step    │  │  (Completeness)  │  │  (Admin/Faculty)│ │
│  │      Form       │  │                  │  │                 │ │
│  └────────┬────────┘  └─────────┬────────┘  └────────┬────────┘ │
└───────────┼───────────────────────┼────────────────────┼──────────┘
            │                       │                    │
┌───────────┼───────────────────────┼────────────────────┼──────────┐
│           │        Business Logic Layer                │          │
│  ┌────────▼────────┐  ┌──────────▼────────┐  ┌────────▼────────┐ │
│  │ Slide Validator │  │  Draft Status     │  │ Audit Logger    │ │
│  │   Component     │  │    Manager        │  │   Component     │ │
│  └────────┬────────┘  └──────────┬────────┘  └────────┬────────┘ │
│           │                       │                    │          │
│  ┌────────▼───────────────────────▼────────────────────▼────────┐ │
│  │               Access Controller Component                     │ │
│  │          (Role-Based Log Filtering & Permissions)             │ │
│  └───────────────────────────────┬───────────────────────────────┘ │
└────────────────────────────────────┼─────────────────────────────────┘
                                     │
┌────────────────────────────────────┼─────────────────────────────────┐
│                      Data Layer (PostgreSQL)                        │
│  ┌─────────────┐  ┌───────────────┐  ┌──────────────────────────┐  │
│  │  Syllabus   │  │ Course        │  │   SyllabusEditLog        │  │
│  │   (Main)    │  │ Objectives,   │  │   (Audit Trail)          │  │
│  │             │  │ Units, etc.   │  │   - timestamp            │  │
│  │ - status    │  │               │  │   - user_id              │  │
│  │ - is_valid  │  │               │  │   - changes (JSON)       │  │
│  └─────────────┘  └───────────────┘  │   - ip_address           │  │
│                                       └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Interactions

1. **Syllabus Builder → Slide Validator**: User submits form from any slide → Validator checks only completed slides
2. **Slide Validator → Draft Status Manager**: Validation passes → Manager calculates completeness
3. **Draft Status Manager → Data Layer**: Saves syllabus with appropriate status
4. **Data Layer → Audit Logger**: Post-save signal triggers → Logger creates immutable audit record
5. **Audit Log UI → Access Controller**: User requests logs → Controller filters by role
6. **Access Controller → Data Layer**: Queries filtered log entries → Returns to UI


## Components and Interfaces

### 1. SyllabusEditLog Model (New)

**Purpose**: Store immutable audit trail entries for all syllabus modifications.

**Database Schema**:
```python
class SyllabusEditLog(models.Model):
    # Core identifiers
    syllabus = models.ForeignKey(
        'Syllabus', 
        on_delete=models.CASCADE,  # Keep logs even if syllabus deleted
        related_name='edit_logs'
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL,
        null=True,  # Preserve log even if user deleted
        related_name='syllabus_edits'
    )
    
    # Audit metadata
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Change tracking
    action_type = models.CharField(
        max_length=20,
        choices=[
            ('create', 'Create'),
            ('update', 'Update'),
            ('status_change', 'Status Change'),
            ('bulk_update', 'Bulk Update'),
        ]
    )
    model_name = models.CharField(max_length=100)  # e.g., 'Syllabus', 'CourseObjective'
    record_id = models.IntegerField(null=True)  # ID of the modified record
    field_name = models.CharField(max_length=100, blank=True)
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    
    # Additional context
    description = models.TextField(blank=True)  # Human-readable change description
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['syllabus', '-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['timestamp']),
        ]
        # Prevent updates/deletes
        permissions = [
            ('view_all_logs', 'Can view all audit logs'),
        ]
    
    def save(self, *args, **kwargs):
        # Prevent updates to existing logs
        if self.pk is not None:
            raise ValueError("SyllabusEditLog entries cannot be modified")
        super().save(*args, **kwargs)
```

**Key Design Points**:
- `on_delete=models.CASCADE` for syllabus to maintain referential integrity but keep logs
- JSONField for flexible storage of old/new values (handles strings, numbers, lists, dicts)
- Compound indexes for efficient querying by syllabus/user and timestamp
- Model-level protection against updates via custom save() method


### 2. Draft Completeness Tracking (Syllabus Model Enhancement)

**Purpose**: Track which syllabus drafts are ready for PDF generation.

**Model Enhancement**:
```python
class Syllabus(models.Model):
    # ... existing fields ...
    
    # New field for validation tracking
    last_completed_slide = models.IntegerField(default=0)  # Track validation progress
    
    def is_complete(self):
        """
        Determine if all required sections are filled for PDF generation.
        Returns: (is_complete: bool, missing_fields: list)
        """
        missing = []
        
        # Check basic fields
        if not self.hours_lecture and not self.hours_practical:
            missing.append('Contact Hours')
        if not self.credit_lecture and not self.credit_practical:
            missing.append('Credits')
        if not self.prerequisites or len(self.prerequisites.strip()) < 3:
            missing.append('Prerequisites')
        if not self.category:
            missing.append('Category')
        if not self.rationale:
            missing.append('Rationale')
        if not self.approval_date:
            missing.append('Approval Date')
        
        # Check course objectives (at least 1)
        if not self.objectives.exists():
            missing.append('Course Objectives')
        
        # Check theory units
        units = self.theory_units.all()
        if not units.exists():
            missing.append('Theory Units')
        else:
            total_weight = sum(u.weightage for u in units)
            if abs(total_weight - 100) > 0.1:
                missing.append(f'Theory Unit Weightage (current: {total_weight}%, required: 100%)')
        
        # Check evaluation scheme
        if not hasattr(self, 'evaluation_scheme'):
            missing.append('Evaluation Scheme')
        
        # Check course outcomes (at least 1)
        outcomes = self.course_outcomes.all()
        if not outcomes.exists():
            missing.append('Course Outcomes')
        else:
            # Check CO-PO mappings exist
            for outcome in outcomes:
                if not hasattr(outcome, 'mapping'):
                    missing.append(f'CO-PO Mapping for {outcome.code}')
                    break
        
        # Check learning resources (at least 1)
        if not self.learning_resources.exists():
            missing.append('Learning Resources')
        
        is_complete = len(missing) == 0
        return is_complete, missing
    
    def get_completion_percentage(self):
        """Calculate percentage of required sections completed."""
        required_sections = [
            'hours', 'credits', 'prerequisites', 'category', 'rationale', 
            'approval_date', 'objectives', 'units', 'evaluation', 
            'outcomes', 'mappings', 'resources'
        ]
        _, missing = self.is_complete()
        completed = len(required_sections) - len(missing)
        return int((completed / len(required_sections)) * 100)
```


### 3. Audit Logger Component

**Purpose**: Centralized logging service that creates audit entries for all syllabus modifications.

**Implementation**: `accounts/audit_logger.py` (new file)

```python
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from adminpanel.models import (
    Syllabus, CourseObjective, TheoryUnit, Practical, 
    CourseOutcome, OutcomeMapping, EvaluationScheme, LearningResource
)
from .models import SyllabusEditLog
import json

class AuditLogger:
    """Service for creating audit log entries."""
    
    @staticmethod
    def get_client_ip(request):
        """Extract client IP from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    @staticmethod
    def log_change(syllabus, user, ip_address, model_name, record_id, 
                   field_name, old_value, new_value, action_type='update'):
        """
        Create an audit log entry.
        
        Args:
            syllabus: Syllabus instance being modified
            user: User making the change
            ip_address: IP address of the user
            model_name: Name of the model being changed
            record_id: ID of the specific record
            field_name: Name of the field being changed
            old_value: Previous value (will be JSON serialized)
            new_value: New value (will be JSON serialized)
            action_type: Type of action (create/update/status_change/bulk_update)
        """
        # Serialize values
        def serialize_value(val):
            if val is None:
                return None
            if isinstance(val, (str, int, float, bool)):
                return val
            if isinstance(val, (list, dict)):
                return val
            return str(val)
        
        description = f"Changed {field_name} in {model_name}"
        if action_type == 'create':
            description = f"Created {model_name}"
        elif action_type == 'status_change':
            description = f"Changed status from {old_value} to {new_value}"
        
        SyllabusEditLog.objects.create(
            syllabus=syllabus,
            user=user,
            ip_address=ip_address,
            action_type=action_type,
            model_name=model_name,
            record_id=record_id,
            field_name=field_name,
            old_value=serialize_value(old_value),
            new_value=serialize_value(new_value),
            description=description
        )
    
    @staticmethod
    def log_bulk_change(syllabus, user, ip_address, model_name, changes):
        """
        Log bulk operations (e.g., deleting all objectives).
        
        Args:
            changes: List of dicts with 'action', 'record_id', 'data' keys
        """
        SyllabusEditLog.objects.create(
            syllabus=syllabus,
            user=user,
            ip_address=ip_address,
            action_type='bulk_update',
            model_name=model_name,
            old_value=changes,
            new_value=None,
            description=f"Bulk operation on {model_name}: {len(changes)} items affected"
        )
```


### 4. Slide Validator Component

**Purpose**: Implement progressive validation that only checks completed slides.

**Implementation**: `accounts/validators.py` (new file)

```python
class SlideValidator:
    """Validates syllabus form data progressively by slide."""
    
    # Define slide structure and required fields
    SLIDES = {
        1: {  # Basic Information
            'required': ['hours_lecture', 'hours_practical', 'hours_tutorial',
                        'credit_lecture', 'credit_practical', 'credit_tutorial',
                        'prerequisites', 'category', 'focus', 'course_focus'],
            'validators': {
                'prerequisites': lambda v: len(v.strip()) >= 3,
                'hours_lecture': lambda v: float(v) >= 0,
                'hours_practical': lambda v: float(v) >= 0,
                # ... additional field validators
            }
        },
        2: {  # Course Objectives
            'required': ['objectives'],
            'validators': {
                'objectives': lambda objs: len(objs) > 0,
            }
        },
        3: {  # Theory Units
            'required': ['theory_units'],
            'validators': {
                'theory_units': lambda units: len(units) > 0,
                'theory_weightage': lambda units: abs(sum(u['weightage'] for u in units) - 100) < 0.1,
            }
        },
        4: {  # Practicals
            'required': [],  # Optional
            'validators': {}
        },
        5: {  # Evaluation Scheme
            'required': ['evaluation'],
            'validators': {}
        },
        6: {  # Course Outcomes & CO-PO Mapping
            'required': ['course_outcomes', 'outcome_mappings'],
            'validators': {
                'course_outcomes': lambda cos: len(cos) > 0,
            }
        },
        7: {  # Learning Resources
            'required': ['learning_resources'],
            'validators': {
                'learning_resources': lambda res: len(res) > 0,
            }
        },
        8: {  # Rationale & Approval
            'required': ['rationale', 'approval_date'],
            'validators': {
                'rationale': lambda v: len(v.strip()) >= 10,
            }
        }
    }
    
    @classmethod
    def validate_slide(cls, slide_number, data):
        """
        Validate data for a specific slide.
        
        Args:
            slide_number: Integer slide number (1-8)
            data: Dict containing form data
            
        Returns:
            (is_valid: bool, errors: dict)
        """
        if slide_number not in cls.SLIDES:
            return True, {}
        
        slide_config = cls.SLIDES[slide_number]
        errors = {}
        
        # Check required fields
        for field in slide_config['required']:
            if field not in data or not data[field]:
                errors[field] = f"{field.replace('_', ' ').title()} is required"
        
        # Run custom validators
        for field, validator in slide_config['validators'].items():
            if field in data:
                try:
                    if not validator(data[field]):
                        errors[field] = f"Invalid value for {field.replace('_', ' ').title()}"
                except Exception as e:
                    errors[field] = f"Validation error: {str(e)}"
        
        return len(errors) == 0, errors
    
    @classmethod
    def validate_up_to_slide(cls, current_slide, data):
        """
        Validate all slides up to and including the current slide.
        
        Returns:
            (is_valid: bool, errors: dict, first_invalid_slide: int)
        """
        all_errors = {}
        first_invalid = None
        
        for slide_num in range(1, current_slide + 1):
            is_valid, slide_errors = cls.validate_slide(slide_num, data)
            if not is_valid:
                all_errors[f'slide_{slide_num}'] = slide_errors
                if first_invalid is None:
                    first_invalid = slide_num
        
        return len(all_errors) == 0, all_errors, first_invalid
```


### 5. Access Controller Component

**Purpose**: Filter audit logs based on user role and permissions.

**Implementation**: Extension to `accounts/views.py`

```python
class AuditLogAccessController:
    """Controls access to audit logs based on user role."""
    
    @staticmethod
    def get_logs_for_user(user, filters=None):
        """
        Retrieve audit logs appropriate for the user's role.
        
        Args:
            user: User instance
            filters: Dict with optional keys: 'subject_id', 'date_from', 'date_to', 'user_id'
            
        Returns:
            QuerySet of SyllabusEditLog entries
        """
        from adminpanel.models import SyllabusEditLog, Faculty, Subject
        
        # Admin sees all logs
        if user.is_staff:
            logs = SyllabusEditLog.objects.all()
        else:
            # Faculty sees only logs for their assigned subjects
            try:
                faculty = Faculty.objects.get(user=user)
                subject_ids = faculty.subjects.values_list('id', flat=True)
                logs = SyllabusEditLog.objects.filter(
                    syllabus__subject_id__in=subject_ids
                )
            except Faculty.DoesNotExist:
                logs = SyllabusEditLog.objects.none()
        
        # Apply filters
        if filters:
            if 'subject_id' in filters:
                logs = logs.filter(syllabus__subject_id=filters['subject_id'])
            if 'date_from' in filters:
                logs = logs.filter(timestamp__gte=filters['date_from'])
            if 'date_to' in filters:
                logs = logs.filter(timestamp__lte=filters['date_to'])
            if 'user_id' in filters and user.is_staff:
                logs = logs.filter(user_id=filters['user_id'])
        
        return logs.select_related('syllabus__subject', 'user').order_by('-timestamp')
    
    @staticmethod
    def can_view_log(user, log_entry):
        """Check if user has permission to view a specific log entry."""
        if user.is_staff:
            return True
        
        try:
            faculty = Faculty.objects.get(user=user)
            return log_entry.syllabus.subject in faculty.subjects.all()
        except Faculty.DoesNotExist:
            return False
```

### 6. View Functions

**New Views for Audit Logs**:

```python
@login_required
def audit_log_list(request):
    """Display audit logs with filtering and pagination."""
    filters = {
        'subject_id': request.GET.get('subject'),
        'date_from': request.GET.get('date_from'),
        'date_to': request.GET.get('date_to'),
        'user_id': request.GET.get('user') if request.user.is_staff else None,
    }
    # Remove None values
    filters = {k: v for k, v in filters.items() if v}
    
    logs = AuditLogAccessController.get_logs_for_user(request.user, filters)
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get available subjects for filter dropdown
    if request.user.is_staff:
        subjects = Subject.objects.all()
    else:
        faculty = Faculty.objects.get(user=request.user)
        subjects = faculty.subjects.all()
    
    context = {
        'logs': page_obj,
        'subjects': subjects,
        'filters': filters,
    }
    return render(request, 'accounts/audit_log_list.html', context)
```


## Data Models

### Database Schema Changes

**New Table: `accounts_syllabuseditlog`**

```sql
CREATE TABLE accounts_syllabuseditlog (
    id SERIAL PRIMARY KEY,
    syllabus_id INTEGER NOT NULL REFERENCES adminpanel_syllabus(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES auth_user(id) ON DELETE SET NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    ip_address INET,
    action_type VARCHAR(20) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    record_id INTEGER,
    field_name VARCHAR(100),
    old_value JSONB,
    new_value JSONB,
    description TEXT,
    CONSTRAINT no_updates CHECK (false)  -- Prevent updates at DB level
);

CREATE INDEX idx_editlog_syllabus_timestamp ON accounts_syllabuseditlog(syllabus_id, timestamp DESC);
CREATE INDEX idx_editlog_user_timestamp ON accounts_syllabuseditlog(user_id, timestamp DESC);
CREATE INDEX idx_editlog_timestamp ON accounts_syllabuseditlog(timestamp DESC);
```

**Modified Table: `adminpanel_syllabus`**

```sql
ALTER TABLE adminpanel_syllabus 
ADD COLUMN last_completed_slide INTEGER DEFAULT 0;
```

### Entity Relationships

```
┌──────────────────┐
│   auth_user      │
│  - id (PK)       │
│  - username      │
│  - is_staff      │
└────────┬─────────┘
         │ 1
         │
         │ N
┌────────▼──────────┐          ┌─────────────────────┐
│  adminpanel_      │          │  accounts_syllabus  │
│  faculty          │          │  editlog            │
│  - user_id (FK)   │          │  - id (PK)          │
│  - faculty_id     │          │  - syllabus_id (FK) │
└────────┬──────────┘          │  - user_id (FK)     │
         │ N                   │  - timestamp        │
         │                     │  - ip_address       │
         │ N                   │  - action_type      │
┌────────▼──────────┐          │  - model_name       │
│  adminpanel_      │ 1     N  │  - record_id        │
│  subject          ├──────────▶  - field_name       │
│  - id (PK)        │          │  - old_value (JSON) │
└────────┬──────────┘          │  - new_value (JSON) │
         │ 1                   │  - description      │
         │                     └─────────────────────┘
         │ 1
┌────────▼──────────┐
│  adminpanel_      │
│  syllabus         │
│  - id (PK)        │
│  - subject_id (FK)│
│  - faculty_id (FK)│
│  - status         │
│  - last_completed │
│    _slide         │
└────────┬──────────┘
         │ 1
         │
         │ N
┌────────▼──────────┐
│  Course           │
│  Objectives,      │
│  Units, etc.      │
└───────────────────┘
```


## Error Handling

### Error Scenarios and Handling Strategy

#### 1. Audit Logging Failures

**Scenario**: Database write fails when creating audit log entry

**Handling**:
- Use Django signals with `post_save` rather than inline logging to avoid blocking main operation
- Wrap audit logging in try-except to prevent audit failures from blocking syllabus saves
- Log audit failures to Django's error logging system
- Implement retry mechanism with exponential backoff for transient failures

```python
@receiver(post_save, sender=Syllabus)
def log_syllabus_change(sender, instance, created, **kwargs):
    try:
        # Audit logging logic
        pass
    except Exception as e:
        logger.error(f"Audit log failed for syllabus {instance.id}: {e}")
        # Don't raise - allow main operation to succeed
```

#### 2. Concurrent Modification

**Scenario**: Two users edit the same syllabus simultaneously

**Handling**:
- Use `select_for_update()` in transaction to prevent race conditions
- Implement optimistic locking with timestamp checking
- Display warning if syllabus was modified since page load
- Preserve user's unsaved changes in case of conflict

```python
with transaction.atomic():
    syllabus = Syllabus.objects.select_for_update().get(id=syllabus_id)
    if syllabus.updated_at > last_loaded_timestamp:
        raise ConcurrentModificationError()
    # Proceed with save
```

#### 3. Incomplete Data During Progressive Save

**Scenario**: User saves draft with missing required fields on future slides

**Handling**:
- Allow save to succeed (this is intentional for draft functionality)
- Mark draft as incomplete
- Do not raise validation errors for unvisited slides
- Display clear visual indicators of incompleteness


#### 4. PDF Generation on Incomplete Draft

**Scenario**: User attempts to generate PDF from incomplete draft

**Handling**:
- Check completeness before allowing PDF generation
- Return HTTP 400 with clear error message listing missing fields
- Disable PDF button in UI for incomplete drafts (client-side prevention)
- Server-side validation as final safeguard

```python
def generate_pdf(request, syllabus_id):
    syllabus = get_object_or_404(Syllabus, id=syllabus_id)
    is_complete, missing = syllabus.is_complete()
    
    if not is_complete:
        return JsonResponse({
            'error': 'Cannot generate PDF for incomplete draft',
            'missing_fields': missing
        }, status=400)
    
    # Proceed with PDF generation
```

#### 5. Invalid Slide Validation Data

**Scenario**: Malformed or missing data in validation request

**Handling**:
- Validate slide number is within valid range (1-8)
- Return structured error response with field-level details
- Preserve user input even on validation failure
- Highlight first invalid field in UI

#### 6. Access Denied to Audit Logs

**Scenario**: Faculty attempts to access logs for unassigned subjects

**Handling**:
- Check permissions at view level
- Return HTTP 403 with clear error message
- Log unauthorized access attempts
- Redirect to error page or show modal with explanation

```python
def audit_log_detail(request, log_id):
    log_entry = get_object_or_404(SyllabusEditLog, id=log_id)
    
    if not AuditLogAccessController.can_view_log(request.user, log_entry):
        return HttpResponseForbidden("You don't have permission to view this log entry")
    
    # Display log details
```

#### 7. Database Connection Failure During Audit

**Scenario**: Database unavailable when attempting to write audit log

**Handling**:
- Queue audit logs in Redis/memory cache if database is unavailable
- Implement background worker to retry failed audit writes
- Alert administrators of audit logging failures
- Maintain operation continuity (syllabus save succeeds)


## Testing Strategy

### Overview

This feature does not use property-based testing because it primarily involves:
- Database CRUD operations (Django ORM)
- Side-effect operations (audit logging to database)
- UI form validation and state management
- Configuration and status checking

These are best tested with **unit tests**, **integration tests**, and **end-to-end tests** rather than property-based testing.

### Unit Tests

**Test Coverage Areas**:

1. **Model Tests** (`tests/test_models.py`)
   - Test `SyllabusEditLog` immutability (cannot update existing entries)
   - Test `Syllabus.is_complete()` method with various missing field combinations
   - Test `Syllabus.get_completion_percentage()` calculation accuracy
   - Test model field validation (CharField max_length, JSONField serialization)

2. **Validator Tests** (`tests/test_validators.py`)
   - Test `SlideValidator.validate_slide()` for each slide with valid data
   - Test `SlideValidator.validate_slide()` for each slide with invalid data
   - Test `SlideValidator.validate_up_to_slide()` with progressive validation
   - Test theory unit weightage validation (must sum to 100%)
   - Test numeric field validation (non-negative values)

3. **Audit Logger Tests** (`tests/test_audit_logger.py`)
   - Test `AuditLogger.log_change()` creates correct log entry
   - Test `AuditLogger.get_client_ip()` extracts IP correctly
   - Test value serialization for different data types
   - Test `log_bulk_change()` for bulk operations
   - Test error handling when audit logging fails

4. **Access Controller Tests** (`tests/test_access_controller.py`)
   - Test `get_logs_for_user()` for admin (returns all logs)
   - Test `get_logs_for_user()` for faculty (returns only assigned subject logs)
   - Test `get_logs_for_user()` with various filters
   - Test `can_view_log()` permission checking

**Example Unit Test**:

```python
class SyllabusCompletenessTests(TestCase):
    def setUp(self):
        self.faculty = Faculty.objects.create(...)
        self.subject = Subject.objects.create(...)
        self.syllabus = Syllabus.objects.create(
            subject=self.subject,
            faculty=self.faculty,
            status='draft'
        )
    
    def test_incomplete_draft_missing_objectives(self):
        """Test that syllabus without objectives is marked incomplete."""
        is_complete, missing = self.syllabus.is_complete()
        
        self.assertFalse(is_complete)
        self.assertIn('Course Objectives', missing)
    
    def test_complete_draft_all_fields_present(self):
        """Test that syllabus with all required fields is marked complete."""
        # Create all required related objects
        CourseObjective.objects.create(syllabus=self.syllabus, text="Test")
        TheoryUnit.objects.create(syllabus=self.syllabus, weightage=100, ...)
        # ... create all other required objects
        
        is_complete, missing = self.syllabus.is_complete()
        
        self.assertTrue(is_complete)
        self.assertEqual(len(missing), 0)
    
    def test_completion_percentage_calculation(self):
        """Test completion percentage is calculated correctly."""
        # Start with empty syllabus (0%)
        self.assertEqual(self.syllabus.get_completion_percentage(), 0)
        
        # Add some fields
        CourseObjective.objects.create(syllabus=self.syllabus, text="Test")
        self.syllabus.prerequisites = "None"
        self.syllabus.save()
        
        # Should be approximately 16% (2 of 12 sections)
        self.assertGreater(self.syllabus.get_completion_percentage(), 10)
        self.assertLess(self.syllabus.get_completion_percentage(), 25)
```


### Integration Tests

**Test Coverage Areas**:

1. **View Integration Tests** (`tests/test_views_integration.py`)
   - Test complete syllabus save flow with audit logging
   - Test draft save from each slide with progressive validation
   - Test PDF generation rejection for incomplete drafts
   - Test audit log list view with filtering and pagination
   - Test concurrent modification detection

2. **Signal Integration Tests** (`tests/test_signals.py`)
   - Test that syllabus save triggers audit log creation
   - Test that related model changes (objectives, units) trigger logs
   - Test that status change triggers specific log entry
   - Test signal failure handling (audit log fails but save succeeds)

3. **Access Control Integration Tests**
   - Test admin can view all logs across all subjects
   - Test faculty can view logs for assigned subjects only
   - Test faculty cannot view logs for unassigned subjects
   - Test faculty cannot view logs after subject is unassigned

**Example Integration Test**:

```python
class AuditLoggingIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.faculty_user = User.objects.create_user('faculty1', password='test')
        self.faculty = Faculty.objects.create(user=self.faculty_user, ...)
        self.subject = Subject.objects.create(...)
        self.subject.faculties.add(self.faculty)
    
    def test_syllabus_save_creates_audit_logs(self):
        """Test that saving syllabus creates appropriate audit log entries."""
        self.client.login(username='faculty1', password='test')
        
        # Create new syllabus
        response = self.client.post('/syllabus-builder/', {
            'subject_id': self.subject.id,
            'save_mode': 'draft',
            'hours_lecture': 3,
            'hours_practical': 2,
            # ... other required fields
        })
        
        # Check syllabus was created
        syllabus = Syllabus.objects.get(subject=self.subject)
        
        # Check audit logs were created
        logs = SyllabusEditLog.objects.filter(syllabus=syllabus)
        self.assertGreater(logs.count(), 0)
        
        # Check log contains correct information
        create_log = logs.filter(action_type='create').first()
        self.assertIsNotNone(create_log)
        self.assertEqual(create_log.user, self.faculty_user)
        self.assertEqual(create_log.model_name, 'Syllabus')
    
    def test_progressive_validation_allows_partial_save(self):
        """Test that user can save draft with only first slide completed."""
        self.client.login(username='faculty1', password='test')
        
        # Save with only slide 1 data (basic information)
        response = self.client.post('/syllabus-builder/', {
            'subject_id': self.subject.id,
            'save_mode': 'draft',
            'current_slide': 1,
            'hours_lecture': 3,
            'hours_practical': 0,
            'hours_tutorial': 0,
            'credit_lecture': 3,
            'credit_practical': 0,
            'credit_tutorial': 0,
            'prerequisites': 'None',
            'category': 'PC',
            'focus': 'PC',
            'course_focus': 'Employability',
        })
        
        # Save should succeed
        self.assertEqual(response.status_code, 302)  # Redirect to dashboard
        
        # Syllabus should exist and be incomplete
        syllabus = Syllabus.objects.get(subject=self.subject)
        is_complete, missing = syllabus.is_complete()
        self.assertFalse(is_complete)
        self.assertIn('Course Objectives', missing)
```


### End-to-End Tests

**Test Coverage Areas**:

1. **Complete Draft Workflow**
   - User logs in → navigates to syllabus builder → fills all slides → saves draft → verifies completeness indicator → generates PDF
   
2. **Partial Draft Workflow**
   - User logs in → fills slides 1-3 → saves draft → logs out → logs back in → draft restored → continues from slide 4
   
3. **Audit Trail Workflow**
   - Admin creates syllabus → faculty modifies it → admin views audit logs → verifies all changes logged
   
4. **Access Control Workflow**
   - Faculty A views own logs → attempts to view Faculty B's logs → receives access denied

**Testing Tools**:
- Selenium or Playwright for browser automation
- Django's LiveServerTestCase for end-to-end testing
- pytest-django for test organization

### Performance Tests

**Test Coverage Areas**:

1. **Audit Log Query Performance**
   - Create 10,000 audit log entries
   - Measure query time for filtered logs
   - Verify pagination performance
   - Target: < 200ms for paginated query with filters

2. **Concurrent Save Performance**
   - Simulate 10 concurrent users saving different syllabi
   - Verify no deadlocks or race conditions
   - Measure average save time under load

3. **Completeness Check Performance**
   - Create syllabus with maximum related objects (20 objectives, 10 units, etc.)
   - Measure `is_complete()` execution time
   - Target: < 50ms for completeness check

### Test Data Strategy

**Fixtures**:
- `test_users.json`: Admin and faculty users
- `test_subjects.json`: Sample subjects across schools/programs
- `test_syllabi.json`: Complete and incomplete syllabus examples
- `test_audit_logs.json`: Historical audit log samples

**Factory Pattern**:
```python
class SyllabusFactory:
    @staticmethod
    def create_complete_syllabus(faculty, subject):
        """Create a fully complete syllabus for testing."""
        syllabus = Syllabus.objects.create(
            subject=subject,
            faculty=faculty,
            hours_lecture=3,
            # ... all required fields
        )
        CourseObjective.objects.create(syllabus=syllabus, text="Test objective")
        TheoryUnit.objects.create(syllabus=syllabus, weightage=100, ...)
        # ... create all required related objects
        return syllabus
    
    @staticmethod
    def create_incomplete_syllabus(faculty, subject, missing_sections=None):
        """Create an incomplete syllabus for testing."""
        syllabus = Syllabus.objects.create(
            subject=subject,
            faculty=faculty,
            status='draft'
        )
        # Only create sections not in missing_sections list
        return syllabus
```

### Test Execution Strategy

1. **Pre-commit**: Run unit tests (fast, < 5 seconds)
2. **Pull Request**: Run unit + integration tests (< 30 seconds)
3. **Pre-deployment**: Run full test suite including E2E (< 5 minutes)
4. **Nightly**: Run performance and stress tests


## UI/UX Design Considerations

### Audit Log Display

**List View** (`accounts/templates/accounts/audit_log_list.html`):
```html
<div class="audit-log-container">
    <div class="filters">
        <form method="get">
            <select name="subject">
                <option value="">All Subjects</option>
                {% for subject in subjects %}
                <option value="{{ subject.id }}">{{ subject.course_name }}</option>
                {% endfor %}
            </select>
            <input type="date" name="date_from" placeholder="From Date">
            <input type="date" name="date_to" placeholder="To Date">
            {% if user.is_staff %}
            <select name="user">
                <option value="">All Users</option>
                <!-- User options -->
            </select>
            {% endif %}
            <button type="submit">Filter</button>
        </form>
    </div>
    
    <table class="audit-log-table">
        <thead>
            <tr>
                <th>Timestamp</th>
                <th>User</th>
                <th>Subject</th>
                <th>Action</th>
                <th>Field</th>
                <th>Old Value</th>
                <th>New Value</th>
            </tr>
        </thead>
        <tbody>
            {% for log in logs %}
            <tr>
                <td>{{ log.timestamp|date:"Y-m-d H:i:s" }}</td>
                <td>{{ log.user.get_full_name }}</td>
                <td>{{ log.syllabus.subject.course_name }}</td>
                <td><span class="badge badge-{{ log.action_type }}">{{ log.get_action_type_display }}</span></td>
                <td>{{ log.field_name }}</td>
                <td><code>{{ log.old_value|truncate:50 }}</code></td>
                <td><code>{{ log.new_value|truncate:50 }}</code></td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    
    <!-- Pagination -->
    <div class="pagination">
        {% if logs.has_previous %}
        <a href="?page={{ logs.previous_page_number }}">Previous</a>
        {% endif %}
        <span>Page {{ logs.number }} of {{ logs.paginator.num_pages }}</span>
        {% if logs.has_next %}
        <a href="?page={{ logs.next_page_number }}">Next</a>
        {% endif %}
    </div>
</div>
```

### Draft Completeness Indicators

**Drafts Page** (`accounts/templates/accounts/faculty_drafts.html`):
```html
{% for draft in drafts %}
<div class="draft-card">
    <div class="draft-header">
        <h3>{{ draft.subject.course_name }}</h3>
        {% if draft.is_complete.0 %}
        <span class="badge badge-success">
            <i class="icon-check"></i> Complete
        </span>
        {% else %}
        <span class="badge badge-warning">
            <i class="icon-clock"></i> {{ draft.get_completion_percentage }}% Complete
        </span>
        {% endif %}
    </div>
    
    <div class="draft-body">
        <p>Last updated: {{ draft.updated_at|timesince }} ago</p>
        
        {% if not draft.is_complete.0 %}
        <div class="missing-fields" title="Missing sections">
            <i class="icon-info"></i>
            <span>Missing: {{ draft.is_complete.1|join:", " }}</span>
        </div>
        {% endif %}
    </div>
    
    <div class="draft-actions">
        <a href="{% url 'syllabus_builder' %}?draft_id={{ draft.id }}" class="btn btn-primary">
            <i class="icon-edit"></i> Continue Editing
        </a>
        
        {% if draft.is_complete.0 %}
        <button onclick="generatePDF({{ draft.id }})" class="btn btn-success">
            <i class="icon-download"></i> Generate PDF
        </button>
        {% else %}
        <button class="btn btn-secondary" disabled title="Complete all sections to generate PDF">
            <i class="icon-download"></i> Generate PDF
        </button>
        {% endif %}
    </div>
</div>
{% endfor %}
```


### Syllabus Builder Enhancements

**Save Draft Button on Each Slide**:
```html
<!-- Add to each slide in syllabus_builder.html -->
<div class="slide-footer">
    <button type="button" class="btn btn-secondary" onclick="previousSlide()">
        <i class="icon-arrow-left"></i> Previous
    </button>
    
    <button type="button" class="btn btn-info" onclick="saveDraft()">
        <i class="icon-save"></i> Save Draft
    </button>
    
    <button type="button" class="btn btn-primary" onclick="nextSlide()">
        Next <i class="icon-arrow-right"></i>
    </button>
</div>

<script>
function saveDraft() {
    const currentSlide = getCurrentSlideNumber();
    const formData = new FormData(document.getElementById('syllabusForm'));
    formData.append('save_mode', 'draft');
    formData.append('current_slide', currentSlide);
    
    // Show loading indicator
    showLoadingIndicator();
    
    fetch('/syllabus-builder/', {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': getCsrfToken()
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showSuccessMessage('Draft saved successfully');
            // Update completion indicator
            updateCompletionIndicator(data.completion_percentage);
        } else {
            showErrorMessage(data.errors);
        }
    })
    .catch(error => {
        showErrorMessage('Failed to save draft. Please try again.');
    })
    .finally(() => {
        hideLoadingIndicator();
    });
}
</script>
```

### Visual Design

**Color Scheme**:
- Complete Draft Badge: Green (#28a745)
- Incomplete Draft Badge: Amber (#ffc107)
- Audit Log Action Types:
  - Create: Blue (#007bff)
  - Update: Orange (#fd7e14)
  - Status Change: Purple (#6f42c1)
  - Bulk Update: Teal (#20c997)

**Responsive Design**:
- Mobile: Stack audit log table vertically with accordion pattern
- Tablet: 2-column draft card layout
- Desktop: 3-column draft card layout

## Security Considerations

### Audit Log Security

1. **Immutability Enforcement**:
   - Database constraint prevents updates: `CONSTRAINT no_updates CHECK (false)`
   - Model-level protection via custom `save()` method
   - No admin interface for editing logs (view-only)

2. **Access Control**:
   - Django permission: `view_all_logs` for admins
   - Faculty can only view logs for assigned subjects
   - Implement row-level security in queries

3. **Data Sanitization**:
   - Escape HTML in old/new values when displaying in UI
   - Prevent XSS via JSON value injection
   - Use Django's template escaping: `{{ log.new_value|escape }}`

### Draft Saving Security

1. **Authorization**:
   - Verify user owns the subject before allowing save
   - Check faculty-subject assignment in `SubjectFaculty` table
   - Prevent CSRF with Django's CSRF token

2. **Input Validation**:
   - Server-side validation for all fields (don't trust client-side)
   - Sanitize user input to prevent SQL injection
   - Use Django ORM's parameterized queries

3. **Rate Limiting**:
   - Implement rate limiting for draft saves (max 10 per minute per user)
   - Prevent abuse of audit logging system

### IP Address Privacy

- Store IP addresses for audit trail compliance
- Hash IP addresses after 90 days to protect user privacy
- Comply with GDPR/data protection regulations
- Provide mechanism for IP address anonymization on request


## Performance Optimization

### Database Optimization

1. **Audit Log Indexing**:
   ```sql
   CREATE INDEX idx_editlog_syllabus_timestamp ON accounts_syllabuseditlog(syllabus_id, timestamp DESC);
   CREATE INDEX idx_editlog_user_timestamp ON accounts_syllabuseditlog(user_id, timestamp DESC);
   CREATE INDEX idx_editlog_timestamp ON accounts_syllabuseditlog(timestamp DESC);
   ```

2. **Query Optimization**:
   - Use `select_related()` for foreign key relationships
   - Use `prefetch_related()` for many-to-many relationships
   - Implement database-level pagination with `LIMIT/OFFSET`

3. **Audit Log Partitioning** (for future scalability):
   - Partition audit logs by month: `accounts_syllabuseditlog_2025_01`, etc.
   - Implement automatic partition creation via cron job
   - Archive old partitions to separate storage

### Caching Strategy

1. **Completeness Calculation Caching**:
   ```python
   from django.core.cache import cache
   
   def get_completion_percentage(self):
       cache_key = f'syllabus_completion_{self.id}_{self.updated_at.timestamp()}'
       percentage = cache.get(cache_key)
       
       if percentage is None:
           # Calculate completion
           percentage = self._calculate_completion()
           cache.set(cache_key, percentage, timeout=3600)  # 1 hour
       
       return percentage
   ```

2. **Audit Log Count Caching**:
   - Cache total log count per subject
   - Invalidate on new log creation
   - Reduces query load on audit log list page

### Asynchronous Processing

1. **Background Audit Logging**:
   - Use Celery for asynchronous audit log creation
   - Queue audit logs during peak hours
   - Process queue during off-peak hours

2. **Bulk Audit Log Creation**:
   - Batch multiple related changes into single transaction
   - Use `bulk_create()` for creating multiple logs efficiently

## Migration Strategy

### Database Migrations

**Migration 1**: Create SyllabusEditLog model
```python
# adminpanel/migrations/00XX_create_syllabuseditlog.py
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ('adminpanel', '00XX_previous_migration'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='SyllabusEditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('action_type', models.CharField(max_length=20, choices=[...])),
                ('model_name', models.CharField(max_length=100)),
                ('record_id', models.IntegerField(null=True)),
                ('field_name', models.CharField(max_length=100, blank=True)),
                ('old_value', models.JSONField(blank=True, null=True)),
                ('new_value', models.JSONField(blank=True, null=True)),
                ('description', models.TextField(blank=True)),
                ('syllabus', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='edit_logs', to='adminpanel.syllabus')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='syllabus_edits', to='auth.user')),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='syllabuseditlog',
            index=models.Index(fields=['syllabus', '-timestamp'], name='idx_editlog_syl_ts'),
        ),
        migrations.AddIndex(
            model_name='syllabuseditlog',
            index=models.Index(fields=['user', '-timestamp'], name='idx_editlog_usr_ts'),
        ),
    ]
```

**Migration 2**: Add last_completed_slide to Syllabus
```python
# adminpanel/migrations/00XX_add_last_completed_slide.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('adminpanel', '00XX_create_syllabuseditlog'),
    ]

    operations = [
        migrations.AddField(
            model_name='syllabus',
            name='last_completed_slide',
            field=models.IntegerField(default=0),
        ),
    ]
```


### Deployment Steps

1. **Pre-deployment**:
   - Back up production database
   - Test migrations on staging environment
   - Verify rollback procedures

2. **Deployment**:
   ```bash
   # 1. Run migrations
   python manage.py migrate
   
   # 2. Collect static files (if UI changes)
   python manage.py collectstatic --noinput
   
   # 3. Restart application server
   systemctl restart gunicorn
   
   # 4. Clear cache
   python manage.py clear_cache
   ```

3. **Post-deployment**:
   - Verify audit logging is working (create test syllabus)
   - Check that existing drafts load correctly
   - Monitor error logs for 24 hours
   - Verify database indexes are created

4. **Rollback Plan**:
   - Revert to previous code version
   - Run reverse migrations if needed
   - Audit logs created during deployment window will remain (no data loss)

## Documentation Requirements

### Developer Documentation

1. **Audit Logger Usage Guide**:
   - How to log custom events
   - Field-level vs bulk logging
   - Best practices for log descriptions

2. **Validator Extension Guide**:
   - How to add new validation rules
   - Slide configuration structure
   - Custom validator functions

3. **Testing Guide**:
   - Running test suite
   - Creating test fixtures
   - Mocking audit logs in tests

### User Documentation

1. **Faculty User Guide**:
   - How to save drafts at any stage
   - Understanding completeness indicators
   - Viewing edit history for own syllabi
   - Progressive validation explanation

2. **Admin User Guide**:
   - Accessing audit logs
   - Filtering and searching logs
   - Understanding log entries
   - Interpreting change data
   - Exporting audit reports

3. **FAQs**:
   - "Why can't I generate PDF?" → Draft incomplete
   - "Where are my draft changes?" → Saved locally, visible in edit history
   - "Can I see who modified my syllabus?" → Yes, via audit logs

## Monitoring and Observability

### Metrics to Track

1. **Audit Log Metrics**:
   - Audit log creation rate (logs/minute)
   - Audit log creation failures
   - Average audit log write time
   - Audit log storage growth rate

2. **Draft Management Metrics**:
   - Percentage of complete vs incomplete drafts
   - Average time to complete a draft
   - Draft save frequency per user
   - Draft abandonment rate

3. **Validation Metrics**:
   - Validation failure rate by slide
   - Most common validation errors
   - Average time spent per slide

### Logging

```python
import logging

logger = logging.getLogger(__name__)

# Log audit failures
logger.error(f"Audit log creation failed for syllabus {syllabus_id}: {error}")

# Log access denials
logger.warning(f"User {user_id} attempted to access unauthorized log {log_id}")

# Log performance issues
logger.info(f"Completeness check took {duration}ms for syllabus {syllabus_id}")
```

### Alerting

1. **Critical Alerts**:
   - Audit log creation failures > 5% of attempts
   - Database connection failures
   - Concurrent modification conflicts

2. **Warning Alerts**:
   - Audit log query time > 500ms
   - Draft save failures > 1% of attempts
   - Completeness check time > 100ms

3. **Info Alerts**:
   - New audit log created (for monitoring)
   - Draft completeness reached 100%
   - PDF generation requested


## Future Enhancements

### Phase 2 Features (Post-MVP)

1. **Advanced Audit Analysis**:
   - Generate audit reports (PDF/Excel export)
   - Visualization of editing patterns
   - Statistical analysis of modification frequency
   - Comparison view showing before/after states

2. **Draft Collaboration**:
   - Allow multiple faculty to edit same draft (with conflict resolution)
   - Real-time notifications when another user is editing
   - Comment threads on specific sections
   - Approval workflows for draft reviews

3. **Enhanced Validation**:
   - AI-powered content suggestions
   - Plagiarism detection for course descriptions
   - Consistency checking across related syllabi
   - Auto-completion for common fields

4. **Version Control**:
   - Git-like version history for syllabi
   - Branching and merging for experimental changes
   - Rollback to previous versions
   - Diff view between versions

5. **Audit Log Search**:
   - Full-text search across change descriptions
   - Advanced filtering (by field name, value ranges)
   - Saved search queries
   - Custom audit log views

### Technical Debt

1. **Audit Log Archival**:
   - Implement automated archival of logs older than 2 years
   - Compress archived logs
   - Provide restore mechanism for archived logs

2. **Performance Optimization**:
   - Implement read replicas for audit log queries
   - Add Redis caching layer
   - Optimize N+1 queries in related models

3. **Code Refactoring**:
   - Extract validation logic from views to dedicated service layer
   - Implement repository pattern for data access
   - Add type hints throughout codebase

## Appendix

### A. Configuration Variables

```python
# settings.py

# Audit Logging
AUDIT_LOG_RETENTION_DAYS = 730  # 2 years
AUDIT_LOG_IP_HASH_AFTER_DAYS = 90
AUDIT_LOG_ENABLE_ASYNC = True

# Draft Management
DRAFT_SAVE_RATE_LIMIT = 10  # per minute per user
DRAFT_AUTO_SAVE_INTERVAL = 300  # 5 minutes (future feature)
DRAFT_COMPLETION_CACHE_TIMEOUT = 3600  # 1 hour

# Validation
VALIDATION_STRICT_MODE = False  # If True, require all fields before save
VALIDATION_THEORY_WEIGHTAGE_TOLERANCE = 0.1  # Allow 99.9% - 100.1%

# UI
AUDIT_LOG_PAGE_SIZE = 50
DRAFT_LIST_PAGE_SIZE = 20
```

### B. API Endpoints

```python
# urls.py additions

urlpatterns = [
    # Existing patterns...
    
    # Audit Logs
    path('audit-logs/', views.audit_log_list, name='audit_log_list'),
    path('audit-logs/<int:log_id>/', views.audit_log_detail, name='audit_log_detail'),
    path('audit-logs/export/', views.audit_log_export, name='audit_log_export'),
    
    # Draft Management
    path('drafts/', views.faculty_drafts, name='faculty_drafts'),
    path('drafts/<int:draft_id>/completeness/', views.draft_completeness_check, name='draft_completeness'),
    path('drafts/<int:draft_id>/validate-slide/', views.validate_slide, name='validate_slide'),
    
    # Existing syllabus builder
    path('syllabus-builder/', views.syllabus_builder, name='syllabus_builder'),
]
```

### C. Database Schema Summary

```
SyllabusEditLog
├── id (PK)
├── syllabus_id (FK → Syllabus)
├── user_id (FK → User, nullable)
├── timestamp (indexed)
├── ip_address
├── action_type (create/update/status_change/bulk_update)
├── model_name
├── record_id
├── field_name
├── old_value (JSONB)
├── new_value (JSONB)
└── description

Syllabus (modifications)
├── ... (existing fields)
└── last_completed_slide (new)
```

### D. Change Log Format

**Audit Log Entry Example**:
```json
{
  "id": 12345,
  "syllabus_id": 42,
  "user_id": 7,
  "timestamp": "2025-01-15T14:30:00Z",
  "ip_address": "192.168.1.100",
  "action_type": "update",
  "model_name": "TheoryUnit",
  "record_id": 89,
  "field_name": "weightage",
  "old_value": 25,
  "new_value": 30,
  "description": "Changed weightage in TheoryUnit"
}
```

**Bulk Change Example**:
```json
{
  "id": 12346,
  "syllabus_id": 42,
  "user_id": 7,
  "timestamp": "2025-01-15T14:31:00Z",
  "ip_address": "192.168.1.100",
  "action_type": "bulk_update",
  "model_name": "CourseObjective",
  "record_id": null,
  "field_name": null,
  "old_value": [
    {"id": 10, "action": "delete", "text": "Old objective 1"},
    {"id": 11, "action": "delete", "text": "Old objective 2"}
  ],
  "new_value": null,
  "description": "Bulk operation on CourseObjective: 2 items affected"
}
```

---

**Document Version**: 1.0  
**Last Updated**: 2025-01-15  
**Author**: Kiro AI Development System  
**Status**: Ready for Review

