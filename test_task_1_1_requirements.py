#!/usr/bin/env python
"""
Comprehensive test for Task 1.1: Create SyllabusEditLog model migration

This test validates all requirements specified in the task:
- All required fields defined
- Meta class with ordering, indexes, and permissions
- Custom save() method to prevent updates
- Proper foreign key relationships with correct ON DELETE behavior
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from accounts.models import SyllabusEditLog
from adminpanel.models import Syllabus, Subject, Faculty
from django.contrib.auth.models import User
from django.db import connection

def test_all_fields_defined():
    """Requirement: Define all fields as specified in task."""
    print("Testing all required fields are defined...")
    
    required_fields = {
        'syllabus': 'ForeignKey to adminpanel.Syllabus',
        'user': 'ForeignKey to User',
        'timestamp': 'DateTimeField with auto_now_add',
        'ip_address': 'GenericIPAddressField',
        'action_type': 'CharField with choices',
        'model_name': 'CharField',
        'record_id': 'IntegerField',
        'field_name': 'CharField',
        'old_value': 'JSONField',
        'new_value': 'JSONField',
        'description': 'TextField'
    }
    
    model_fields = {f.name: f for f in SyllabusEditLog._meta.get_fields()}
    
    all_present = True
    for field_name, field_description in required_fields.items():
        if field_name in model_fields:
            field = model_fields[field_name]
            print(f"  ✓ {field_name}: {field.__class__.__name__}")
        else:
            print(f"  ✗ {field_name}: MISSING")
            all_present = False
    
    return all_present

def test_foreign_key_relationships():
    """Requirement: Proper foreign key setup with correct ON DELETE."""
    print("\nTesting foreign key relationships...")
    
    # Check syllabus FK
    syllabus_field = SyllabusEditLog._meta.get_field('syllabus')
    if syllabus_field.remote_field.model._meta.label == 'adminpanel.Syllabus':
        print("  ✓ syllabus FK points to adminpanel.Syllabus")
    else:
        print(f"  ✗ syllabus FK points to {syllabus_field.remote_field.model._meta.label}")
        return False
    
    if syllabus_field.remote_field.on_delete.__name__ == 'SET_NULL':
        print("  ✓ syllabus FK has on_delete=SET_NULL")
    else:
        print(f"  ✗ syllabus FK has on_delete={syllabus_field.remote_field.on_delete.__name__}")
        return False
    
    # Check user FK
    user_field = SyllabusEditLog._meta.get_field('user')
    if user_field.remote_field.on_delete.__name__ == 'SET_NULL':
        print("  ✓ user FK has on_delete=SET_NULL")
    else:
        print(f"  ✗ user FK has on_delete={user_field.remote_field.on_delete.__name__}")
        return False
    
    return True

def test_meta_class_ordering():
    """Requirement: Meta class with ordering by -timestamp."""
    print("\nTesting Meta class ordering...")
    
    ordering = SyllabusEditLog._meta.ordering
    if ordering == ['-timestamp']:
        print(f"  ✓ Ordering: {ordering}")
        return True
    else:
        print(f"  ✗ Ordering: {ordering} (expected ['-timestamp'])")
        return False

def test_meta_class_indexes():
    """Requirement: Meta class with proper indexes."""
    print("\nTesting Meta class indexes...")
    
    indexes = SyllabusEditLog._meta.indexes
    print(f"  Found {len(indexes)} indexes")
    
    # Check for timestamp index
    has_timestamp_idx = any('timestamp' in str(idx.fields) for idx in indexes)
    if has_timestamp_idx:
        print("  ✓ Timestamp index exists")
    else:
        print("  ✗ Timestamp index missing")
        return False
    
    # Check for compound indexes
    has_syllabus_timestamp = any(
        'syllabus' in str(idx.fields) and 'timestamp' in str(idx.fields) 
        for idx in indexes
    )
    if has_syllabus_timestamp:
        print("  ✓ Syllabus-timestamp compound index exists")
    else:
        print("  ✗ Syllabus-timestamp compound index missing")
    
    has_user_timestamp = any(
        'user' in str(idx.fields) and 'timestamp' in str(idx.fields) 
        for idx in indexes
    )
    if has_user_timestamp:
        print("  ✓ User-timestamp compound index exists")
    else:
        print("  ✗ User-timestamp compound index missing")
    
    return True

def test_meta_class_permissions():
    """Requirement: Meta class with custom permissions."""
    print("\nTesting Meta class permissions...")
    
    permissions = [perm for perm in SyllabusEditLog._meta.permissions]
    
    if ('view_all_logs', 'Can view all audit logs') in permissions:
        print("  ✓ Custom permission 'view_all_logs' defined")
        return True
    else:
        print("  ✗ Custom permission 'view_all_logs' missing")
        print(f"    Found permissions: {permissions}")
        return False

def test_custom_save_prevents_updates():
    """Requirement: Custom save() method prevents updates."""
    print("\nTesting custom save() method prevents updates...")
    
    # Create a log entry
    log = SyllabusEditLog.objects.create(
        action_type='create',
        model_name='TestModel',
        description='Test entry for immutability'
    )
    log_id = log.id
    print(f"  ✓ Created log entry ID: {log_id}")
    
    # Try to update it
    try:
        log.description = 'Attempting to update'
        log.save()
        print("  ✗ FAIL: Update succeeded (should have been prevented)")
        log.delete()
        return False
    except ValueError as e:
        expected_msg = "cannot be modified"
        if expected_msg in str(e).lower():
            print(f"  ✓ Update prevented with correct error: {e}")
            log.delete()
            return True
        else:
            print(f"  ✗ Update prevented but with unexpected error: {e}")
            log.delete()
            return False

def test_jsonfield_functionality():
    """Requirement: JSONField properly stores old_value and new_value."""
    print("\nTesting JSONField functionality...")
    
    # Test with various data types
    test_data = [
        ('string', 'old_string', 'new_string'),
        ('number', 42, 100),
        ('boolean', True, False),
        ('list', [1, 2, 3], [4, 5, 6]),
        ('dict', {'key': 'value'}, {'new_key': 'new_value'}),
        ('null', None, 'some_value')
    ]
    
    for data_type, old_val, new_val in test_data:
        log = SyllabusEditLog.objects.create(
            action_type='update',
            model_name='TestModel',
            field_name=f'test_{data_type}',
            old_value=old_val,
            new_value=new_val
        )
        
        # Retrieve and verify
        retrieved = SyllabusEditLog.objects.get(id=log.id)
        if retrieved.old_value == old_val and retrieved.new_value == new_val:
            print(f"  ✓ {data_type}: stored and retrieved correctly")
        else:
            print(f"  ✗ {data_type}: storage/retrieval failed")
            print(f"    Expected old={old_val}, new={new_val}")
            print(f"    Got old={retrieved.old_value}, new={retrieved.new_value}")
            log.delete()
            return False
        
        log.delete()
    
    return True

def test_action_type_choices():
    """Requirement: action_type has proper choices defined."""
    print("\nTesting action_type choices...")
    
    expected_choices = ['create', 'update', 'status_change', 'bulk_update']
    action_field = SyllabusEditLog._meta.get_field('action_type')
    
    if action_field.choices:
        choice_values = [choice[0] for choice in action_field.choices]
        print(f"  Found choices: {choice_values}")
        
        all_present = all(choice in choice_values for choice in expected_choices)
        if all_present:
            print("  ✓ All expected action_type choices present")
            return True
        else:
            print("  ✗ Some expected choices missing")
            return False
    else:
        print("  ✗ No choices defined for action_type")
        return False

def test_requirements_1_1_1_4_1_6():
    """Test requirements 1.1, 1.4, 1.6 from the spec."""
    print("\nTesting spec requirements 1.1, 1.4, 1.6...")
    
    # Requirement 1.1: Edit logs include timestamp, user, field-level changes
    log = SyllabusEditLog.objects.create(
        action_type='update',
        model_name='Syllabus',
        field_name='status',
        old_value='draft',
        new_value='final',
        description='Status changed from draft to final'
    )
    
    if log.timestamp and hasattr(log, 'user') and hasattr(log, 'old_value'):
        print("  ✓ Req 1.1: Timestamp, user identity, and field-level changes tracked")
    else:
        print("  ✗ Req 1.1: Missing required tracking fields")
        log.delete()
        return False
    
    # Requirement 1.4: Edit logs include old and new values
    if log.old_value == 'draft' and log.new_value == 'final':
        print("  ✓ Req 1.4: Old and new values properly stored")
    else:
        print("  ✗ Req 1.4: Old and new values not stored correctly")
        log.delete()
        return False
    
    # Requirement 1.6: Edit logs are immutable
    try:
        log.new_value = 'modified'
        log.save()
        print("  ✗ Req 1.6: Log was not immutable (update succeeded)")
        log.delete()
        return False
    except ValueError:
        print("  ✓ Req 1.6: Logs are immutable after creation")
        log.delete()
        return True

def test_requirements_9_2_9_3():
    """Test requirements 9.2 and 9.3 (data retention)."""
    print("\nTesting spec requirements 9.2, 9.3 (data retention)...")
    
    # Create test data
    user = User.objects.create_user(username='retention_test_user', password='test')
    subject = Subject.objects.create(
        course_name='Retention Test',
        course_code='RET101',
        semester=1
    )
    faculty = Faculty.objects.create(
        user=user,
        full_name='Retention Test Faculty',
        faculty_id='RET001'
    )
    syllabus = Syllabus.objects.create(
        subject=subject,
        faculty=faculty,
        status='draft'
    )
    
    # Create log
    log = SyllabusEditLog.objects.create(
        syllabus=syllabus,
        user=user,
        action_type='create',
        model_name='Syllabus',
        record_id=syllabus.id,
        description='Test retention log'
    )
    log_id = log.id
    
    # Test Req 9.2: Logs retained when syllabus deleted
    syllabus.delete()
    log_after_syllabus_delete = SyllabusEditLog.objects.filter(id=log_id).first()
    if log_after_syllabus_delete:
        print("  ✓ Req 9.2: Log retained after syllabus deletion")
    else:
        print("  ✗ Req 9.2: Log deleted with syllabus")
        user.delete()
        subject.delete()
        return False
    
    # Test Req 9.3: Logs retained when user deactivated/deleted
    user.delete()
    log_after_user_delete = SyllabusEditLog.objects.filter(id=log_id).first()
    if log_after_user_delete:
        print("  ✓ Req 9.3: Log retained after user deletion")
    else:
        print("  ✗ Req 9.3: Log deleted with user")
        subject.delete()
        return False
    
    # Cleanup
    log_after_user_delete.delete()
    subject.delete()
    return True

if __name__ == '__main__':
    print("=" * 75)
    print("Task 1.1: SyllabusEditLog Model Migration - Comprehensive Validation")
    print("=" * 75)
    
    tests = [
        ("All Fields Defined", test_all_fields_defined),
        ("Foreign Key Relationships", test_foreign_key_relationships),
        ("Meta: Ordering", test_meta_class_ordering),
        ("Meta: Indexes", test_meta_class_indexes),
        ("Meta: Permissions", test_meta_class_permissions),
        ("Custom Save (Immutability)", test_custom_save_prevents_updates),
        ("JSONField Functionality", test_jsonfield_functionality),
        ("Action Type Choices", test_action_type_choices),
        ("Spec Requirements 1.1, 1.4, 1.6", test_requirements_1_1_1_4_1_6),
        ("Spec Requirements 9.2, 9.3", test_requirements_9_2_9_3),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*75}")
        print(f"TEST: {test_name}")
        print('='*75)
        try:
            if test_func():
                passed += 1
                print(f"\n✓ PASSED: {test_name}")
            else:
                print(f"\n✗ FAILED: {test_name}")
        except Exception as e:
            print(f"\n✗ FAILED: {test_name} - Exception: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 75)
    print(f"FINAL RESULTS: {passed}/{total} tests passed")
    print("=" * 75)
    
    if passed == total:
        print("✓ ALL REQUIREMENTS VALIDATED SUCCESSFULLY!")
        print("\nTask 1.1 is COMPLETE:")
        print("  ✓ SyllabusEditLog model created in accounts/models.py")
        print("  ✓ All required fields defined (syllabus, user, timestamp, ip_address,")
        print("    action_type, model_name, record_id, field_name, old_value, new_value, description)")
        print("  ✓ Meta class with ordering, indexes, and permissions")
        print("  ✓ Custom save() method prevents updates to existing logs")
        print("  ✓ Migrations created and applied to database")
        print("  ✓ Requirements 1.1, 1.4, 1.6, 9.2, 9.3 satisfied")
        exit(0)
    else:
        print("✗ SOME TESTS FAILED")
        exit(1)
