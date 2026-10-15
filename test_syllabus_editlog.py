#!/usr/bin/env python
"""Test script to verify SyllabusEditLog model immutability."""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from accounts.models import SyllabusEditLog
from django.contrib.auth.models import User

def test_immutability():
    """Test that SyllabusEditLog entries cannot be updated."""
    print("Testing SyllabusEditLog immutability...")
    
    # Create a log entry
    log = SyllabusEditLog.objects.create(
        action_type='create',
        model_name='TestModel',
        description='Test log entry'
    )
    print(f"✓ Created log entry with ID: {log.id}")
    
    # Try to update it
    try:
        log.description = 'Updated description'
        log.save()
        print("✗ ERROR: Update succeeded (should have failed)")
        return False
    except ValueError as e:
        print(f"✓ SUCCESS: Update prevented - {str(e)}")
    
    # Clean up
    log.delete()
    print("✓ Test log entry cleaned up")
    
    return True

def test_fields():
    """Test that all required fields are present."""
    print("\nTesting SyllabusEditLog fields...")
    
    expected_fields = [
        'id', 'syllabus', 'user', 'timestamp', 'ip_address', 
        'action_type', 'model_name', 'record_id', 'field_name', 
        'old_value', 'new_value', 'description'
    ]
    
    actual_fields = [f.name for f in SyllabusEditLog._meta.get_fields()]
    
    for field in expected_fields:
        if field in actual_fields:
            print(f"✓ Field '{field}' exists")
        else:
            print(f"✗ Field '{field}' is missing")
            return False
    
    return True

def test_meta_options():
    """Test Meta class configuration."""
    print("\nTesting SyllabusEditLog Meta options...")
    
    # Check ordering
    ordering = SyllabusEditLog._meta.ordering
    if ordering == ['-timestamp']:
        print(f"✓ Ordering is correct: {ordering}")
    else:
        print(f"✗ Ordering is incorrect: {ordering}")
        return False
    
    # Check indexes
    indexes = SyllabusEditLog._meta.indexes
    print(f"✓ Model has {len(indexes)} indexes defined")
    
    # Check permissions
    permissions = [perm for perm in SyllabusEditLog._meta.permissions]
    if ('view_all_logs', 'Can view all audit logs') in permissions:
        print("✓ Custom permission 'view_all_logs' exists")
    else:
        print("✗ Custom permission 'view_all_logs' is missing")
        return False
    
    return True

if __name__ == '__main__':
    print("=" * 60)
    print("SyllabusEditLog Model Verification Tests")
    print("=" * 60)
    
    tests_passed = 0
    tests_total = 3
    
    if test_fields():
        tests_passed += 1
    
    if test_meta_options():
        tests_passed += 1
    
    if test_immutability():
        tests_passed += 1
    
    print("\n" + "=" * 60)
    print(f"Tests Passed: {tests_passed}/{tests_total}")
    print("=" * 60)
    
    if tests_passed == tests_total:
        print("✓ All tests passed!")
        exit(0)
    else:
        print("✗ Some tests failed")
        exit(1)
