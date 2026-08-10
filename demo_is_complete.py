#!/usr/bin/env python
"""
Demonstration script for Syllabus.is_complete() method.

This script shows how to use the is_complete() method to check if a syllabus
has all required sections filled and is ready for PDF generation.
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from adminpanel.models import Syllabus


def demonstrate_is_complete():
    """Demonstrate the is_complete() method with existing syllabi."""
    print("=" * 80)
    print("Syllabus Completeness Check Demo")
    print("=" * 80)
    print()
    
    syllabi = Syllabus.objects.all()[:5]  # Get first 5 syllabi
    
    if not syllabi:
        print("No syllabi found in database.")
        return
    
    for syllabus in syllabi:
        print(f"Syllabus: {syllabus}")
        print(f"Subject: {syllabus.subject.course_code} - {syllabus.subject.course_name}")
        print("-" * 80)
        
        is_complete, missing_fields = syllabus.is_complete()
        
        if is_complete:
            print("✓ Status: COMPLETE - Ready for PDF generation")
        else:
            print("✗ Status: INCOMPLETE - Missing required sections:")
            for field in missing_fields:
                print(f"  - {field}")
        
        print()
        print()


if __name__ == '__main__':
    demonstrate_is_complete()
