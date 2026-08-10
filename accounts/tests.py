import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from adminpanel.models import Syllabus, Subject, Faculty, School, Program, Branch
from .models import SyllabusEditLog


class SyllabusEditLogModelTests(TestCase):
    """Test suite for SyllabusEditLog model."""
    
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
        
        # Create syllabus
        self.syllabus = Syllabus.objects.create(
            subject=self.subject,
            faculty=self.faculty,
            status='draft'
        )
    
    def test_create_edit_log(self):
        """Test creating a new edit log entry."""
        log = SyllabusEditLog.objects.create(
            syllabus=self.syllabus,
            user=self.user,
            ip_address='127.0.0.1',
            action_type='update',
            model_name='Syllabus',
            record_id=self.syllabus.id,
            field_name='status',
            old_value='draft',
            new_value='final',
            description='Changed status from draft to final'
        )
        
        self.assertIsNotNone(log.id)
        self.assertEqual(log.syllabus, self.syllabus)
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.action_type, 'update')
        self.assertEqual(log.model_name, 'Syllabus')
        self.assertEqual(log.field_name, 'status')
        self.assertEqual(log.old_value, 'draft')
        self.assertEqual(log.new_value, 'final')
    
    def test_edit_log_immutability(self):
        """Test that existing log entries cannot be modified."""
        log = SyllabusEditLog.objects.create(
            syllabus=self.syllabus,
            user=self.user,
            action_type='create',
            model_name='Syllabus',
            record_id=self.syllabus.id,
            description='Initial creation'
        )
        
        # Attempt to modify the log entry
        log.description = 'Modified description'
        
        with self.assertRaises(ValueError) as context:
            log.save()
        
        self.assertIn('cannot be modified', str(context.exception))
    
    def test_edit_log_with_json_values(self):
        """Test storing complex JSON data in old_value and new_value fields."""
        old_objectives = ['Objective 1', 'Objective 2']
        new_objectives = ['Objective 1', 'Objective 2', 'Objective 3']
        
        log = SyllabusEditLog.objects.create(
            syllabus=self.syllabus,
            user=self.user,
            action_type='update',
            model_name='CourseObjective',
            field_name='objectives',
            old_value=old_objectives,
            new_value=new_objectives,
            description='Added a new course objective'
        )
        
        self.assertEqual(log.old_value, old_objectives)
        self.assertEqual(log.new_value, new_objectives)
        self.assertIsInstance(log.old_value, list)
        self.assertIsInstance(log.new_value, list)
    
    def test_edit_log_ordering(self):
        """Test that logs are ordered by timestamp descending."""
        # Create multiple log entries
        log1 = SyllabusEditLog.objects.create(
            syllabus=self.syllabus,
            user=self.user,
            action_type='create',
            model_name='Syllabus',
            description='First log'
        )
        
        log2 = SyllabusEditLog.objects.create(
            syllabus=self.syllabus,
            user=self.user,
            action_type='update',
            model_name='Syllabus',
            description='Second log'
        )
        
        log3 = SyllabusEditLog.objects.create(
            syllabus=self.syllabus,
            user=self.user,
            action_type='update',
            model_name='Syllabus',
            description='Third log'
        )
        
        # Retrieve all logs
        logs = SyllabusEditLog.objects.all()
        
        # Check ordering (most recent first)
        self.assertEqual(logs[0], log3)
        self.assertEqual(logs[1], log2)
        self.assertEqual(logs[2], log1)
    
    def test_edit_log_user_deletion(self):
        """Test that logs are preserved when user is deleted."""
        log = SyllabusEditLog.objects.create(
            syllabus=self.syllabus,
            user=self.user,
            action_type='update',
            model_name='Syllabus',
            description='Test log'
        )
        
        # Delete the user
        user_id = self.user.id
        self.user.delete()
        
        # Log should still exist but user should be None
        log.refresh_from_db()
        self.assertIsNone(log.user)
        self.assertIsNotNone(log.id)
    
    def test_edit_log_syllabus_retention(self):
        """Test that logs are preserved when syllabus is deleted."""
        log = SyllabusEditLog.objects.create(
            syllabus=self.syllabus,
            user=self.user,
            action_type='create',
            model_name='Syllabus',
            description='Test log'
        )
        
        log_id = log.id
        
        # Delete the syllabus
        self.syllabus.delete()
        
        # Log should still exist but syllabus should be None
        log = SyllabusEditLog.objects.get(id=log_id)
        self.assertIsNone(log.syllabus)
    
    def test_edit_log_action_types(self):
        """Test all action type choices are valid."""
        action_types = ['create', 'update', 'status_change', 'bulk_update']
        
        for action_type in action_types:
            log = SyllabusEditLog.objects.create(
                syllabus=self.syllabus,
                user=self.user,
                action_type=action_type,
                model_name='Syllabus',
                description=f'Test {action_type}'
            )
            self.assertEqual(log.action_type, action_type)
    
    def test_edit_log_ip_address_formats(self):
        """Test that both IPv4 and IPv6 addresses are accepted."""
        # Test IPv4
        log_ipv4 = SyllabusEditLog.objects.create(
            syllabus=self.syllabus,
            user=self.user,
            ip_address='192.168.1.1',
            action_type='update',
            model_name='Syllabus',
            description='IPv4 test'
        )
        self.assertEqual(log_ipv4.ip_address, '192.168.1.1')
        
        # Test IPv6
        log_ipv6 = SyllabusEditLog.objects.create(
            syllabus=self.syllabus,
            user=self.user,
            ip_address='2001:0db8:85a3:0000:0000:8a2e:0370:7334',
            action_type='update',
            model_name='Syllabus',
            description='IPv6 test'
        )
        self.assertEqual(log_ipv6.ip_address, '2001:0db8:85a3:0000:0000:8a2e:0370:7334')
    
    def test_edit_log_string_representation(self):
        """Test the __str__ method of SyllabusEditLog."""
        log = SyllabusEditLog.objects.create(
            syllabus=self.syllabus,
            user=self.user,
            action_type='update',
            model_name='Syllabus',
            description='Test log'
        )
        
        str_repr = str(log)
        self.assertIn('update', str_repr)
        self.assertIn('testfaculty', str_repr)
    
    def test_edit_log_without_user(self):
        """Test creating log entry without user (system action)."""
        log = SyllabusEditLog.objects.create(
            syllabus=self.syllabus,
            user=None,
            action_type='update',
            model_name='Syllabus',
            description='System automated change'
        )
        
        self.assertIsNone(log.user)
        str_repr = str(log)
        self.assertIn('Unknown User', str_repr)
    
    def test_edit_log_related_name_syllabus(self):
        """Test accessing logs through syllabus.edit_logs."""
        SyllabusEditLog.objects.create(
            syllabus=self.syllabus,
            user=self.user,
            action_type='create',
            model_name='Syllabus',
            description='Log 1'
        )
        
        SyllabusEditLog.objects.create(
            syllabus=self.syllabus,
            user=self.user,
            action_type='update',
            model_name='Syllabus',
            description='Log 2'
        )
        
        # Access logs through reverse relation
        logs = self.syllabus.edit_logs.all()
        descriptions = set(logs.values_list('description', flat=True))
        self.assertGreaterEqual(logs.count(), 2)
        self.assertIn('Log 1', descriptions)
        self.assertIn('Log 2', descriptions)
    
    def test_edit_log_related_name_user(self):
        """Test accessing logs through user.syllabus_edits."""
        SyllabusEditLog.objects.create(
            syllabus=self.syllabus,
            user=self.user,
            action_type='create',
            model_name='Syllabus',
            description='User edit 1'
        )
        
        # Access logs through user's reverse relation
        logs = self.user.syllabus_edits.all()
        self.assertEqual(logs.count(), 1)
