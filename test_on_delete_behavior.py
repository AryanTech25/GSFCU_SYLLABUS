#!/usr/bin/env python
"""Test ON DELETE behavior for SyllabusEditLog foreign keys."""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from accounts.models import SyllabusEditLog
from adminpanel.models import Syllabus, Subject, Faculty
from django.contrib.auth.models import User
from django.db import transaction

def test_syllabus_deletion_preserves_logs():
    """Test that deleting a syllabus preserves audit logs with SET_NULL."""
    print("Testing syllabus deletion (should preserve logs with NULL syllabus)...")
    
    # Get or create a test user
    user = User.objects.filter(username='test_user').first()
    if not user:
        user = User.objects.create_user(username='test_user', password='testpass')
    
    # Get or create a test subject
    subject = Subject.objects.filter(course_name='Test Course').first()
    if not subject:
        subject = Subject.objects.create(
            course_name='Test Course',
            course_code='TEST101',
            semester=1
        )
    
    # Get or create faculty
    faculty = Faculty.objects.filter(user=user).first()
    if not faculty:
        faculty = Faculty.objects.create(
            user=user,
            full_name='Test Faculty',
            faculty_id='FAC001'
        )
    
    # Create a test syllabus
    syllabus = Syllabus.objects.create(
        subject=subject,
        faculty=faculty,
        status='draft'
    )
    syllabus_id = syllabus.id
    print(f"✓ Created test syllabus with ID: {syllabus_id}")
    
    # Create an audit log for this syllabus
    log = SyllabusEditLog.objects.create(
        syllabus=syllabus,
        user=user,
        action_type='create',
        model_name='Syllabus',
        record_id=syllabus_id,
        description='Test log entry'
    )
    log_id = log.id
    print(f"✓ Created audit log with ID: {log_id}")
    
    # Delete the syllabus
    syllabus.delete()
    print(f"✓ Deleted syllabus {syllabus_id}")
    
    # Check if the log still exists
    try:
        log = SyllabusEditLog.objects.get(id=log_id)
        if log.syllabus is None:
            print(f"✓ SUCCESS: Audit log preserved with syllabus=NULL")
            print(f"  Log still contains: user={log.user}, action={log.action_type}, description={log.description}")
            
            # Clean up
            log.delete()
            print("✓ Cleaned up test log")
            return True
        else:
            print(f"✗ FAIL: Audit log still references syllabus (expected NULL)")
            return False
    except SyllabusEditLog.DoesNotExist:
        print(f"✗ FAIL: Audit log was deleted (should be preserved)")
        return False
    finally:
        # Clean up test data
        if Subject.objects.filter(id=subject.id).exists():
            subject.delete()
        if User.objects.filter(id=user.id).exists():
            user.delete()

def test_user_deletion_preserves_logs():
    """Test that deleting a user preserves audit logs with SET_NULL."""
    print("\nTesting user deletion (should preserve logs with NULL user)...")
    
    # Create a test user
    user = User.objects.create_user(username='temp_test_user', password='testpass')
    user_id = user.id
    print(f"✓ Created test user with ID: {user_id}")
    
    # Create an audit log for this user
    log = SyllabusEditLog.objects.create(
        user=user,
        action_type='update',
        model_name='Test',
        description='Test log entry for user deletion'
    )
    log_id = log.id
    print(f"✓ Created audit log with ID: {log_id}")
    
    # Delete the user
    user.delete()
    print(f"✓ Deleted user {user_id}")
    
    # Check if the log still exists
    try:
        log = SyllabusEditLog.objects.get(id=log_id)
        if log.user is None:
            print(f"✓ SUCCESS: Audit log preserved with user=NULL")
            print(f"  Log still contains: action={log.action_type}, description={log.description}")
            
            # Clean up
            log.delete()
            print("✓ Cleaned up test log")
            return True
        else:
            print(f"✗ FAIL: Audit log still references user (expected NULL)")
            return False
    except SyllabusEditLog.DoesNotExist:
        print(f"✗ FAIL: Audit log was deleted (should be preserved)")
        return False

if __name__ == '__main__':
    print("=" * 70)
    print("SyllabusEditLog ON DELETE Behavior Tests")
    print("=" * 70)
    
    tests_passed = 0
    tests_total = 2
    
    try:
        if test_syllabus_deletion_preserves_logs():
            tests_passed += 1
    except Exception as e:
        print(f"✗ Test failed with exception: {e}")
    
    try:
        if test_user_deletion_preserves_logs():
            tests_passed += 1
    except Exception as e:
        print(f"✗ Test failed with exception: {e}")
    
    print("\n" + "=" * 70)
    print(f"Tests Passed: {tests_passed}/{tests_total}")
    print("=" * 70)
    
    if tests_passed == tests_total:
        print("✓ All ON DELETE tests passed!")
        exit(0)
    else:
        print("✗ Some ON DELETE tests failed")
        exit(1)
