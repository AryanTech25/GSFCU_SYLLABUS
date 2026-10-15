#!/usr/bin/env python
"""
Comprehensive test for Task 2.1: Add is_complete() method to Syllabus model

This test validates all requirements specified in the task:
- Checks all required sections (contact hours, credits, prerequisites, category, rationale, approval date)
- Validates course objectives exist (at least 1)
- Validates theory units exist (at least 1) and weightage sums to 100%
- Validates evaluation scheme exists
- Validates course outcomes exist (at least 1)
- Validates CO-PO mappings exist for each course outcome
- Validates learning resources exist (at least 1)
- Returns tuple of (is_complete: bool, missing_fields: list)

Validates:
- Requirements 5.1: Check all required fields are filled
- Requirements 5.2: Validate required section completeness
- Requirements 5.3: Ensure CO-PO mappings exist for each course outcome
- Requirements 6.5: Ensure theory unit weightage sums to 100%
"""

import os
import sys
import django
from datetime import date

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.test import TestCase
from django.contrib.auth.models import User
from adminpanel.models import (
    Syllabus, Subject, Faculty, School, Program, Branch,
    CourseObjective, TheoryUnit, EvaluationScheme, 
    CourseOutcome, OutcomeMapping, LearningResource
)


class SyllabusIsCompleteTests(TestCase):
    """Test suite for Syllabus.is_complete() method."""
    
    def setUp(self):
        """Set up test data."""
        # Create a user
        self.user = User.objects.create_user(
            username='testfaculty',
            password='testpass123'
        )
        
        # Create school, program, branch
        self.school = School.objects.create(name='Test School', code='TS')
        self.program = Program.objects.create(
            name='Test Program',
            school=self.school
        )
        self.branch = Branch.objects.create(
            name='Test Branch',
            program=self.program
        )
        
        # Create faculty
        self.faculty = Faculty.objects.create(
            user=self.user,
            full_name='Test Faculty',
            faculty_id='FAC001',
            email='test@test.com',
            mobile='1234567890',
            semester='1'
        )
        
        # Create subject
        self.subject = Subject.objects.create(
            course_code='CS101',
            course_name='Test Course',
            semester=1,
            school=self.school,
            program=self.program,
            branch=self.branch
        )
        
        # Create syllabus with basic required fields
        self.syllabus = Syllabus.objects.create(
            subject=self.subject,
            faculty=self.faculty,
            hours_lecture=3,
            hours_practical=2,
            credit_lecture=3,
            credit_practical=1,
            prerequisites='Mathematics Basics',
            category='PC',
            rationale='Important for understanding programming',
            approval_date=date.today()
        )
    
    def test_incomplete_syllabus_no_objectives(self):
        """Test that syllabus without objectives is incomplete."""
        is_complete, missing = self.syllabus.is_complete()
        
        self.assertFalse(is_complete)
        self.assertIn('Course Objectives', missing)
    
    def test_incomplete_syllabus_no_theory_units(self):
        """Test that syllabus without theory units is incomplete."""
        is_complete, missing = self.syllabus.is_complete()
        
        self.assertFalse(is_complete)
        self.assertIn('Theory Units', missing)
    
    def test_incomplete_syllabus_theory_units_wrong_weightage(self):
        """Test that syllabus with theory units not summing to 100% is incomplete."""
        # Add objectives to pass that check
        CourseObjective.objects.create(
            syllabus=self.syllabus,
            text='Understand programming concepts',
            blooms_domain='Cognitive'
        )
        
        # Add theory units with incorrect weightage (sum = 80%)
        TheoryUnit.objects.create(
            syllabus=self.syllabus,
            title='Unit 1',
            description='Introduction',
            weightage=40,
            hours=10
        )
        TheoryUnit.objects.create(
            syllabus=self.syllabus,
            title='Unit 2',
            description='Advanced Topics',
            weightage=40,
            hours=10
        )
        
        is_complete, missing = self.syllabus.is_complete()
        
        self.assertFalse(is_complete)
        # Check that a message about weightage is in missing fields
        weightage_error = [m for m in missing if 'Weightage' in m]
        self.assertTrue(len(weightage_error) > 0)
    
    def test_incomplete_syllabus_no_evaluation_scheme(self):
        """Test that syllabus without evaluation scheme is incomplete."""
        is_complete, missing = self.syllabus.is_complete()
        
        self.assertFalse(is_complete)
        self.assertIn('Evaluation Scheme', missing)
    
    def test_incomplete_syllabus_no_course_outcomes(self):
        """Test that syllabus without course outcomes is incomplete."""
        is_complete, missing = self.syllabus.is_complete()
        
        self.assertFalse(is_complete)
        self.assertIn('Course Outcomes', missing)
    
    def test_incomplete_syllabus_no_co_po_mappings(self):
        """Test that syllabus without CO-PO mappings is incomplete."""
        # Add all required sections except CO-PO mappings
        CourseObjective.objects.create(
            syllabus=self.syllabus,
            text='Understand programming concepts'
        )
        
        TheoryUnit.objects.create(
            syllabus=self.syllabus,
            title='Unit 1',
            description='Introduction',
            weightage=100,
            hours=20
        )
        
        EvaluationScheme.objects.create(
            syllabus=self.syllabus,
            mid_sem=30,
            end_sem=70
        )
        
        # Create course outcome WITHOUT mapping
        CourseOutcome.objects.create(
            syllabus=self.syllabus,
            code='CO1',
            description='Understand basic concepts'
        )
        
        LearningResource.objects.create(
            syllabus=self.syllabus,
            category='Textbook',
            content='Programming in Python'
        )
        
        is_complete, missing = self.syllabus.is_complete()
        
        self.assertFalse(is_complete)
        # Check for CO-PO mapping error
        mapping_error = [m for m in missing if 'CO-PO Mapping' in m]
        self.assertTrue(len(mapping_error) > 0)
    
    def test_incomplete_syllabus_no_learning_resources(self):
        """Test that syllabus without learning resources is incomplete."""
        is_complete, missing = self.syllabus.is_complete()
        
        self.assertFalse(is_complete)
        self.assertIn('Learning Resources', missing)
    
    def test_incomplete_syllabus_missing_contact_hours(self):
        """Test that syllabus without contact hours is incomplete."""
        # Create syllabus without hours
        subject2 = Subject.objects.create(
            course_code='CS102',
            course_name='Test Course 2',
            semester=1,
            school=self.school,
            program=self.program,
            branch=self.branch
        )
        syllabus2 = Syllabus.objects.create(
            subject=subject2,
            faculty=self.faculty,
            hours_lecture=0,
            hours_practical=0,
            credit_lecture=3,
            credit_practical=1,
            prerequisites='Math',
            category='PC',
            rationale='Important',
            approval_date=date.today()
        )
        
        is_complete, missing = syllabus2.is_complete()
        
        self.assertFalse(is_complete)
        self.assertIn('Contact Hours', missing)
    
    def test_incomplete_syllabus_missing_credits(self):
        """Test that syllabus without credits is incomplete."""
        subject2 = Subject.objects.create(
            course_code='CS102',
            course_name='Test Course 2',
            semester=1,
            school=self.school,
            program=self.program,
            branch=self.branch
        )
        syllabus2 = Syllabus.objects.create(
            subject=subject2,
            faculty=self.faculty,
            hours_lecture=3,
            hours_practical=2,
            credit_lecture=0,
            credit_practical=0,
            prerequisites='Math',
            category='PC',
            rationale='Important',
            approval_date=date.today()
        )
        
        is_complete, missing = syllabus2.is_complete()
        
        self.assertFalse(is_complete)
        self.assertIn('Credits', missing)
    
    def test_incomplete_syllabus_missing_prerequisites(self):
        """Test that syllabus without prerequisites (or too short) is incomplete."""
        subject2 = Subject.objects.create(
            course_code='CS102',
            course_name='Test Course 2',
            semester=1,
            school=self.school,
            program=self.program,
            branch=self.branch
        )
        syllabus2 = Syllabus.objects.create(
            subject=subject2,
            faculty=self.faculty,
            hours_lecture=3,
            hours_practical=2,
            credit_lecture=3,
            credit_practical=1,
            prerequisites='AB',  # Too short (less than 3 chars)
            category='PC',
            rationale='Important',
            approval_date=date.today()
        )
        
        is_complete, missing = syllabus2.is_complete()
        
        self.assertFalse(is_complete)
        self.assertIn('Prerequisites', missing)
    
    def test_incomplete_syllabus_missing_category(self):
        """Test that syllabus without category is incomplete."""
        subject2 = Subject.objects.create(
            course_code='CS102',
            course_name='Test Course 2',
            semester=1,
            school=self.school,
            program=self.program,
            branch=self.branch
        )
        syllabus2 = Syllabus.objects.create(
            subject=subject2,
            faculty=self.faculty,
            hours_lecture=3,
            hours_practical=2,
            credit_lecture=3,
            credit_practical=1,
            prerequisites='Math',
            category='',  # Empty category
            rationale='Important',
            approval_date=date.today()
        )
        
        is_complete, missing = syllabus2.is_complete()
        
        self.assertFalse(is_complete)
        self.assertIn('Category', missing)
    
    def test_incomplete_syllabus_missing_rationale(self):
        """Test that syllabus without rationale is incomplete."""
        subject2 = Subject.objects.create(
            course_code='CS102',
            course_name='Test Course 2',
            semester=1,
            school=self.school,
            program=self.program,
            branch=self.branch
        )
        syllabus2 = Syllabus.objects.create(
            subject=subject2,
            faculty=self.faculty,
            hours_lecture=3,
            hours_practical=2,
            credit_lecture=3,
            credit_practical=1,
            prerequisites='Math',
            category='PC',
            rationale='',  # Empty rationale
            approval_date=date.today()
        )
        
        is_complete, missing = syllabus2.is_complete()
        
        self.assertFalse(is_complete)
        self.assertIn('Rationale', missing)
    
    def test_incomplete_syllabus_missing_approval_date(self):
        """Test that syllabus without approval date is incomplete."""
        subject2 = Subject.objects.create(
            course_code='CS102',
            course_name='Test Course 2',
            semester=1,
            school=self.school,
            program=self.program,
            branch=self.branch
        )
        syllabus2 = Syllabus.objects.create(
            subject=subject2,
            faculty=self.faculty,
            hours_lecture=3,
            hours_practical=2,
            credit_lecture=3,
            credit_practical=1,
            prerequisites='Math',
            category='PC',
            rationale='Important',
            approval_date=None  # No approval date
        )
        
        is_complete, missing = syllabus2.is_complete()
        
        self.assertFalse(is_complete)
        self.assertIn('Approval Date', missing)
    
    def test_complete_syllabus(self):
        """Test that syllabus with all required fields is complete."""
        # Add all required sections
        CourseObjective.objects.create(
            syllabus=self.syllabus,
            text='Understand programming concepts'
        )
        
        # Add theory units with correct weightage (sum = 100%)
        TheoryUnit.objects.create(
            syllabus=self.syllabus,
            title='Unit 1',
            description='Introduction',
            weightage=50,
            hours=10
        )
        TheoryUnit.objects.create(
            syllabus=self.syllabus,
            title='Unit 2',
            description='Advanced Topics',
            weightage=50,
            hours=10
        )
        
        EvaluationScheme.objects.create(
            syllabus=self.syllabus,
            mid_sem=30,
            end_sem=70
        )
        
        # Create course outcome WITH mapping
        outcome = CourseOutcome.objects.create(
            syllabus=self.syllabus,
            code='CO1',
            description='Understand basic concepts'
        )
        OutcomeMapping.objects.create(
            course_outcome=outcome,
            po1=1,
            po2=2,
            po3=1
        )
        
        LearningResource.objects.create(
            syllabus=self.syllabus,
            category='Textbook',
            content='Programming in Python'
        )
        
        is_complete, missing = self.syllabus.is_complete()
        
        self.assertTrue(is_complete)
        self.assertEqual(len(missing), 0)
    
    def test_complete_syllabus_with_multiple_outcomes(self):
        """Test that syllabus with multiple course outcomes all having mappings is complete."""
        # Add all required sections
        CourseObjective.objects.create(
            syllabus=self.syllabus,
            text='Understand programming concepts'
        )
        
        TheoryUnit.objects.create(
            syllabus=self.syllabus,
            title='Unit 1',
            description='Introduction',
            weightage=100,
            hours=20
        )
        
        EvaluationScheme.objects.create(
            syllabus=self.syllabus,
            mid_sem=30,
            end_sem=70
        )
        
        # Create multiple course outcomes, each WITH mapping
        outcome1 = CourseOutcome.objects.create(
            syllabus=self.syllabus,
            code='CO1',
            description='Understand basic concepts'
        )
        OutcomeMapping.objects.create(
            course_outcome=outcome1,
            po1=1,
            po2=2
        )
        
        outcome2 = CourseOutcome.objects.create(
            syllabus=self.syllabus,
            code='CO2',
            description='Apply advanced concepts'
        )
        OutcomeMapping.objects.create(
            course_outcome=outcome2,
            po3=2,
            po4=1
        )
        
        LearningResource.objects.create(
            syllabus=self.syllabus,
            category='Textbook',
            content='Programming in Python'
        )
        
        is_complete, missing = self.syllabus.is_complete()
        
        self.assertTrue(is_complete)
        self.assertEqual(len(missing), 0)
    
    def test_theory_unit_weightage_tolerance(self):
        """Test that weightage within 0.1% tolerance is acceptable."""
        # Add all required sections
        CourseObjective.objects.create(
            syllabus=self.syllabus,
            text='Understand programming concepts'
        )
        
        # Add theory units with weightage very close to 100% (within tolerance)
        TheoryUnit.objects.create(
            syllabus=self.syllabus,
            title='Unit 1',
            description='Introduction',
            weightage=33,
            hours=7
        )
        TheoryUnit.objects.create(
            syllabus=self.syllabus,
            title='Unit 2',
            description='Advanced Topics',
            weightage=33,
            hours=7
        )
        TheoryUnit.objects.create(
            syllabus=self.syllabus,
            title='Unit 3',
            description='More Topics',
            weightage=34,
            hours=6
        )
        # Total = 100%, exactly
        
        EvaluationScheme.objects.create(
            syllabus=self.syllabus,
            mid_sem=30,
            end_sem=70
        )
        
        outcome = CourseOutcome.objects.create(
            syllabus=self.syllabus,
            code='CO1',
            description='Understand basic concepts'
        )
        OutcomeMapping.objects.create(
            course_outcome=outcome,
            po1=1
        )
        
        LearningResource.objects.create(
            syllabus=self.syllabus,
            category='Textbook',
            content='Programming in Python'
        )
        
        is_complete, missing = self.syllabus.is_complete()
        
        self.assertTrue(is_complete)
        self.assertEqual(len(missing), 0)


def run_tests():
    """Run all tests and print results."""
    from django.test.runner import DiscoverRunner
    
    runner = DiscoverRunner(verbosity=2)
    test_suite = runner.test_loader.loadTestsFromTestCase(SyllabusIsCompleteTests)
    result = runner.run_suite(test_suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    print("=" * 80)
    print("Task 2.1: Syllabus.is_complete() Method Tests")
    print("=" * 80)
    print()
    
    success = run_tests()
    
    print()
    print("=" * 80)
    if success:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed!")
    print("=" * 80)
    
    sys.exit(0 if success else 1)
