#!/usr/bin/env python
"""
Task 7.3 – Unit tests for AuditLogAccessController
====================================================

Covers:
  get_logs_for_user()
    - Admin sees all logs
    - Faculty sees only logs for their assigned subjects
    - Non-faculty, non-admin user sees nothing
    - subject_id / date_from / date_to filters
    - user_id filter (admin-only; silently ignored for faculty)
    - select_related attached (no extra DB hits per log)
    - Ordered by -timestamp

  can_view_log()
    - Admin always True
    - Faculty True for their subject, False otherwise
    - Faculty with null-syllabus log → False
    - Non-faculty user → False

Requirements: 2.1, 3.1, 3.3
"""

import os
import sys
from datetime import date, timedelta

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from accounts.access_controller import AuditLogAccessController
from accounts.audit_logger import AuditLogger
from accounts.models import SyllabusEditLog
from adminpanel.models import (
    Syllabus, Subject, Faculty, School, Program, Branch,
)


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

class AccessControllerTestMixin:
    """Creates two faculties each with their own subject & syllabus."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_ac', password='pass', is_staff=True)

        school = School.objects.create(name='AC School', code='AC')
        program = Program.objects.create(name='AC Prog', school=school)
        branch = Branch.objects.create(name='AC Branch', program=program)

        # Faculty A
        self.user_a = User.objects.create_user(username='faculty_a', password='pass')
        self.faculty_a = Faculty.objects.create(
            user=self.user_a, full_name='Faculty A', faculty_id='FA001',
            email='a@a.com', mobile='1111111111', semester='1')

        # Faculty B
        self.user_b = User.objects.create_user(username='faculty_b', password='pass')
        self.faculty_b = Faculty.objects.create(
            user=self.user_b, full_name='Faculty B', faculty_id='FB001',
            email='b@b.com', mobile='2222222222', semester='1')

        # Plain user (no faculty record)
        self.plain_user = User.objects.create_user(
            username='plain_user', password='pass')

        # Subjects
        self.subject_a = Subject.objects.create(
            course_code='SA01', course_name='Subject A',
            school=school, program=program, branch=branch)
        self.subject_b = Subject.objects.create(
            course_code='SB01', course_name='Subject B',
            school=school, program=program, branch=branch)

        # Assign subjects to faculties
        self.subject_a.faculties.add(self.faculty_a)
        self.subject_b.faculties.add(self.faculty_b)

        # Syllabi
        self.syllabus_a = Syllabus.objects.create(
            subject=self.subject_a, faculty=self.faculty_a,
            hours_lecture=3, credit_lecture=3,
            prerequisites='Maths', category='PC',
            rationale='Reason A', approval_date=date.today())
        self.syllabus_b = Syllabus.objects.create(
            subject=self.subject_b, faculty=self.faculty_b,
            hours_lecture=2, credit_lecture=2,
            prerequisites='Physics', category='BS',
            rationale='Reason B', approval_date=date.today())

        # Clear auto-generated signal logs
        SyllabusEditLog.objects.all().delete()

        # Create controlled logs
        self.log_a = AuditLogger.log_change(
            self.syllabus_a, self.user_a, '10.0.0.1',
            'Syllabus', self.syllabus_a.pk,
            'rationale', 'Old A', 'New A', 'update')
        self.log_b = AuditLogger.log_change(
            self.syllabus_b, self.user_b, '10.0.0.2',
            'Syllabus', self.syllabus_b.pk,
            'rationale', 'Old B', 'New B', 'update')


# ---------------------------------------------------------------------------
# Test class 1 – get_logs_for_user() role-based baseline
# ---------------------------------------------------------------------------

class GetLogsForUserRoleTests(AccessControllerTestMixin, TestCase):

    def test_admin_sees_all_logs(self):
        logs = AuditLogAccessController.get_logs_for_user(self.admin)
        pks = list(logs.values_list('pk', flat=True))
        self.assertIn(self.log_a.pk, pks)
        self.assertIn(self.log_b.pk, pks)

    def test_admin_count_equals_total(self):
        total = SyllabusEditLog.objects.count()
        logs = AuditLogAccessController.get_logs_for_user(self.admin)
        self.assertEqual(logs.count(), total)

    def test_faculty_a_sees_only_their_logs(self):
        logs = AuditLogAccessController.get_logs_for_user(self.user_a)
        pks = list(logs.values_list('pk', flat=True))
        self.assertIn(self.log_a.pk, pks)
        self.assertNotIn(self.log_b.pk, pks)

    def test_faculty_b_sees_only_their_logs(self):
        logs = AuditLogAccessController.get_logs_for_user(self.user_b)
        pks = list(logs.values_list('pk', flat=True))
        self.assertIn(self.log_b.pk, pks)
        self.assertNotIn(self.log_a.pk, pks)

    def test_non_faculty_user_sees_no_logs(self):
        logs = AuditLogAccessController.get_logs_for_user(self.plain_user)
        self.assertEqual(logs.count(), 0)

    def test_returns_queryset(self):
        from django.db.models import QuerySet
        logs = AuditLogAccessController.get_logs_for_user(self.admin)
        self.assertIsInstance(logs, QuerySet)

    def test_ordered_by_newest_first(self):
        # Create a second log for syllabus_a (will have later timestamp)
        log2 = AuditLogger.log_change(
            self.syllabus_a, self.user_a, '10.0.0.1',
            'Syllabus', self.syllabus_a.pk,
            'rationale', 'A', 'B', 'update')
        logs = list(AuditLogAccessController.get_logs_for_user(self.admin))
        # log2 is newer so should appear before log_a
        idx_log2 = next(i for i, l in enumerate(logs) if l.pk == log2.pk)
        idx_log_a = next(i for i, l in enumerate(logs) if l.pk == self.log_a.pk)
        self.assertLess(idx_log2, idx_log_a)

    def test_none_filters_does_not_crash(self):
        """Passing None as filters should work (treated as empty dict)."""
        logs = AuditLogAccessController.get_logs_for_user(self.admin, None)
        self.assertGreater(logs.count(), 0)

    def test_empty_filters_does_not_crash(self):
        logs = AuditLogAccessController.get_logs_for_user(self.admin, {})
        self.assertGreater(logs.count(), 0)


# ---------------------------------------------------------------------------
# Test class 2 – get_logs_for_user() optional filters
# ---------------------------------------------------------------------------

class GetLogsForUserFilterTests(AccessControllerTestMixin, TestCase):

    def test_filter_by_subject_id_admin(self):
        logs = AuditLogAccessController.get_logs_for_user(
            self.admin, {'subject_id': self.subject_a.pk})
        pks = list(logs.values_list('pk', flat=True))
        self.assertIn(self.log_a.pk, pks)
        self.assertNotIn(self.log_b.pk, pks)

    def test_filter_by_subject_id_faculty(self):
        """Faculty can further filter to their own subject (still restricted)."""
        logs = AuditLogAccessController.get_logs_for_user(
            self.user_a, {'subject_id': self.subject_a.pk})
        self.assertIn(self.log_a.pk, [l.pk for l in logs])

    def test_filter_by_date_from_excludes_older(self):
        future = timezone.now() + timedelta(days=1)
        logs = AuditLogAccessController.get_logs_for_user(
            self.admin, {'date_from': future})
        self.assertEqual(logs.count(), 0)

    def test_filter_by_date_from_includes_current(self):
        past = timezone.now() - timedelta(hours=1)
        logs = AuditLogAccessController.get_logs_for_user(
            self.admin, {'date_from': past})
        self.assertGreater(logs.count(), 0)

    def test_filter_by_date_to_excludes_future(self):
        past = timezone.now() - timedelta(days=1)
        logs = AuditLogAccessController.get_logs_for_user(
            self.admin, {'date_to': past})
        self.assertEqual(logs.count(), 0)

    def test_filter_by_date_to_includes_current(self):
        future = timezone.now() + timedelta(hours=1)
        logs = AuditLogAccessController.get_logs_for_user(
            self.admin, {'date_to': future})
        self.assertGreater(logs.count(), 0)

    def test_filter_by_user_id_admin(self):
        logs = AuditLogAccessController.get_logs_for_user(
            self.admin, {'user_id': self.user_a.pk})
        pks = list(logs.values_list('pk', flat=True))
        self.assertIn(self.log_a.pk, pks)
        self.assertNotIn(self.log_b.pk, pks)

    def test_filter_by_user_id_ignored_for_faculty(self):
        """Faculty cannot use user_id filter to access other users' logs."""
        # user_b's log is for subject_b — not assigned to faculty_a
        logs = AuditLogAccessController.get_logs_for_user(
            self.user_a, {'user_id': self.user_b.pk})
        pks = list(logs.values_list('pk', flat=True))
        # user_id filter ignored; faculty_a still only sees subject_a logs
        self.assertNotIn(self.log_b.pk, pks)

    def test_combined_subject_and_date_filter(self):
        past = timezone.now() - timedelta(hours=1)
        future = timezone.now() + timedelta(hours=1)
        logs = AuditLogAccessController.get_logs_for_user(
            self.admin,
            {'subject_id': self.subject_a.pk,
             'date_from': past,
             'date_to': future})
        pks = list(logs.values_list('pk', flat=True))
        self.assertIn(self.log_a.pk, pks)
        self.assertNotIn(self.log_b.pk, pks)

    def test_select_related_attached(self):
        """Queryset should have select_related for syllabus__subject and user."""
        logs = AuditLogAccessController.get_logs_for_user(self.admin)
        # Access related fields without triggering extra queries
        entry = logs.first()
        self.assertIsNotNone(entry)
        # These should not raise; they're pre-fetched
        _ = entry.user
        _ = entry.syllabus


# ---------------------------------------------------------------------------
# Test class 3 – can_view_log()
# ---------------------------------------------------------------------------

class CanViewLogTests(AccessControllerTestMixin, TestCase):

    def test_admin_can_view_any_log(self):
        self.assertTrue(
            AuditLogAccessController.can_view_log(self.admin, self.log_a))
        self.assertTrue(
            AuditLogAccessController.can_view_log(self.admin, self.log_b))

    def test_faculty_a_can_view_their_log(self):
        self.assertTrue(
            AuditLogAccessController.can_view_log(self.user_a, self.log_a))

    def test_faculty_a_cannot_view_faculty_b_log(self):
        self.assertFalse(
            AuditLogAccessController.can_view_log(self.user_a, self.log_b))

    def test_faculty_b_can_view_their_log(self):
        self.assertTrue(
            AuditLogAccessController.can_view_log(self.user_b, self.log_b))

    def test_faculty_b_cannot_view_faculty_a_log(self):
        self.assertFalse(
            AuditLogAccessController.can_view_log(self.user_b, self.log_a))

    def test_non_faculty_cannot_view_any_log(self):
        self.assertFalse(
            AuditLogAccessController.can_view_log(self.plain_user, self.log_a))
        self.assertFalse(
            AuditLogAccessController.can_view_log(self.plain_user, self.log_b))

    def test_returns_bool(self):
        result = AuditLogAccessController.can_view_log(self.admin, self.log_a)
        self.assertIsInstance(result, bool)

    def test_null_syllabus_log_denied_to_faculty(self):
        """Log whose syllabus FK is null is inaccessible to non-admin."""
        null_log = AuditLogger.log_change(
            None, self.user_a, '10.0.0.1',
            'Syllabus', None, '', None, None, 'create')
        self.assertFalse(
            AuditLogAccessController.can_view_log(self.user_a, null_log))

    def test_null_syllabus_log_accessible_to_admin(self):
        null_log = AuditLogger.log_change(
            None, self.user_a, '10.0.0.1',
            'Syllabus', None, '', None, None, 'create')
        self.assertTrue(
            AuditLogAccessController.can_view_log(self.admin, null_log))


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_tests():
    from django.test.runner import DiscoverRunner
    runner = DiscoverRunner(verbosity=2)
    suite = runner.test_loader.loadTestsFromName(__name__)
    result = runner.run_suite(suite)
    return result.wasSuccessful()


if __name__ == '__main__':
    print("=" * 80)
    print("Task 7.3: AuditLogAccessController Unit Tests")
    print("  7.1  get_logs_for_user() - role baseline + filters")
    print("  7.2  can_view_log() - per-entry permission check")
    print("=" * 80)
    print()

    success = run_tests()

    print()
    print("=" * 80)
    print("OK: All tests passed!" if success else "FAIL: Some tests failed!")
    print("=" * 80)

    sys.exit(0 if success else 1)
