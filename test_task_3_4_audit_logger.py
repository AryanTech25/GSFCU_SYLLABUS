#!/usr/bin/env python
"""
Task 3.4 - Unit tests for AuditLogger class
============================================

Covers:
  - get_client_ip()  with and without X-Forwarded-For header
  - log_change()     creates correct SyllabusEditLog with all field types
  - _serialize_value() for various data types (indirect via log_change)
  - log_bulk_change() for bulk operations
  - Error handling   when log creation fails (non-fatal)

Requirements: 1.1, 1.4, 1.5
"""

import os
import sys
import django
from datetime import date, datetime
from unittest.mock import MagicMock, patch

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User

from accounts.audit_logger import AuditLogger
from accounts.models import SyllabusEditLog
from adminpanel.models import (
    Syllabus, Subject, Faculty, School, Program, Branch
)


# ---------------------------------------------------------------------------
# Shared fixture mixin (same pattern as 2.3 tests)
# ---------------------------------------------------------------------------

class AuditLoggerTestMixin:
    """Creates minimum DB objects needed by every AuditLogger test."""

    def setUp(self):
        self.factory = RequestFactory()

        self.user = User.objects.create_user(
            username='logtest', password='pass123'
        )
        school = School.objects.create(name='Test School', code='TS')
        program = Program.objects.create(name='Test Prog', school=school)
        branch = Branch.objects.create(name='Test Branch', program=program)
        faculty = Faculty.objects.create(
            user=self.user, full_name='Test Faculty',
            faculty_id='FAC001', email='t@t.com',
            mobile='0000000000', semester='1'
        )
        subject = Subject.objects.create(
            course_code='CS001', course_name='Test Course',
            semester='1', school=school, program=program, branch=branch
        )
        self.syllabus = Syllabus.objects.create(
            subject=subject, faculty=faculty,
            hours_lecture=3, credit_lecture=3,
            prerequisites='Maths', category='PC',
            rationale='Important', approval_date=date.today()
        )
        self.ip = '192.168.1.1'


# ---------------------------------------------------------------------------
# Test class 1 – get_client_ip()
# ---------------------------------------------------------------------------

class GetClientIpTests(AuditLoggerTestMixin, TestCase):
    """Tests for AuditLogger.get_client_ip()."""

    def _req(self, remote_addr=None, x_forwarded_for=None):
        """Build a fake request with the given META values."""
        req = self.factory.get('/')
        if remote_addr is not None:
            req.META['REMOTE_ADDR'] = remote_addr
        if x_forwarded_for is not None:
            req.META['HTTP_X_FORWARDED_FOR'] = x_forwarded_for
        return req

    def test_returns_remote_addr_when_no_forwarded_for(self):
        """Without X-Forwarded-For, REMOTE_ADDR is returned."""
        req = self._req(remote_addr='10.0.0.5')
        ip = AuditLogger.get_client_ip(req)
        self.assertEqual(ip, '10.0.0.5')

    def test_returns_first_ip_from_x_forwarded_for(self):
        """With X-Forwarded-For set, first address is returned."""
        req = self._req(
            remote_addr='10.0.0.1',
            x_forwarded_for='203.0.113.1, 10.0.0.2, 10.0.0.3'
        )
        ip = AuditLogger.get_client_ip(req)
        self.assertEqual(ip, '203.0.113.1')

    def test_strips_whitespace_from_x_forwarded_for(self):
        """Leading/trailing whitespace around addresses is stripped."""
        req = self._req(
            x_forwarded_for=' 203.0.113.1 , 10.0.0.2'
        )
        ip = AuditLogger.get_client_ip(req)
        self.assertEqual(ip, '203.0.113.1')

    def test_single_ip_in_x_forwarded_for(self):
        """Single IP in X-Forwarded-For is returned correctly."""
        req = self._req(x_forwarded_for='203.0.113.50')
        ip = AuditLogger.get_client_ip(req)
        self.assertEqual(ip, '203.0.113.50')

    def test_returns_none_when_no_ip_available(self):
        """Returns None when no REMOTE_ADDR and no X-Forwarded-For."""
        req = self.factory.get('/')
        req.META.pop('REMOTE_ADDR', None)
        req.META.pop('HTTP_X_FORWARDED_FOR', None)
        ip = AuditLogger.get_client_ip(req)
        self.assertIsNone(ip)

    def test_ipv6_address_passthrough(self):
        """IPv6 addresses are returned as-is."""
        req = self._req(remote_addr='::1')
        ip = AuditLogger.get_client_ip(req)
        self.assertEqual(ip, '::1')

    def test_x_forwarded_for_takes_priority_over_remote_addr(self):
        """X-Forwarded-For is preferred over REMOTE_ADDR when both present."""
        req = self._req(
            remote_addr='10.0.0.1',
            x_forwarded_for='203.0.113.99'
        )
        ip = AuditLogger.get_client_ip(req)
        self.assertEqual(ip, '203.0.113.99')


# ---------------------------------------------------------------------------
# Test class 2 – log_change() creates correct DB records
# ---------------------------------------------------------------------------

class LogChangeCreatesRecordTests(AuditLoggerTestMixin, TestCase):
    """Verify that log_change() writes the correct SyllabusEditLog row."""

    def _log(self, **kwargs):
        """Call log_change with sensible defaults, overridden by kwargs."""
        defaults = dict(
            syllabus=self.syllabus,
            user=self.user,
            ip_address=self.ip,
            model_name='Syllabus',
            record_id=self.syllabus.pk,
            field_name='rationale',
            old_value='Old rationale',
            new_value='New rationale',
            action_type='update',
        )
        defaults.update(kwargs)
        return AuditLogger.log_change(**defaults)

    # --- Basic creation ---

    def test_log_change_creates_one_entry(self):
        """log_change() creates exactly one SyllabusEditLog row."""
        before = SyllabusEditLog.objects.count()
        self._log()
        self.assertEqual(SyllabusEditLog.objects.count(), before + 1)

    def test_log_change_returns_log_entry(self):
        """log_change() returns the created SyllabusEditLog instance."""
        entry = self._log()
        self.assertIsInstance(entry, SyllabusEditLog)
        self.assertIsNotNone(entry.pk)

    # --- Field values ---

    def test_syllabus_fk_set_correctly(self):
        entry = self._log()
        self.assertEqual(entry.syllabus, self.syllabus)

    def test_user_fk_set_correctly(self):
        entry = self._log()
        self.assertEqual(entry.user, self.user)

    def test_ip_address_stored(self):
        entry = self._log(ip_address='10.20.30.40')
        self.assertEqual(entry.ip_address, '10.20.30.40')

    def test_model_name_stored(self):
        entry = self._log(model_name='CourseObjective')
        self.assertEqual(entry.model_name, 'CourseObjective')

    def test_record_id_stored(self):
        entry = self._log(record_id=42)
        self.assertEqual(entry.record_id, 42)

    def test_field_name_stored(self):
        entry = self._log(field_name='title')
        self.assertEqual(entry.field_name, 'title')

    def test_action_type_default_is_update(self):
        entry = self._log()
        self.assertEqual(entry.action_type, 'update')

    def test_action_type_create(self):
        entry = self._log(action_type='create')
        self.assertEqual(entry.action_type, 'create')

    def test_action_type_status_change(self):
        entry = self._log(action_type='status_change',
                          old_value='draft', new_value='final')
        self.assertEqual(entry.action_type, 'status_change')

    def test_timestamp_is_set(self):
        entry = self._log()
        self.assertIsNotNone(entry.timestamp)

    # --- Description generation ---

    def test_description_for_update(self):
        entry = self._log(action_type='update', field_name='rationale')
        self.assertIn('rationale', entry.description.lower())

    def test_description_for_create(self):
        entry = self._log(action_type='create', field_name='')
        self.assertIn('created', entry.description.lower())

    def test_description_for_status_change(self):
        entry = self._log(action_type='status_change',
                          old_value='draft', new_value='final')
        self.assertIn('status', entry.description.lower())
        self.assertIn('draft', entry.description.lower())
        self.assertIn('final', entry.description.lower())

    # --- None syllabus (allowed for first-creation edge case) ---

    def test_none_syllabus_allowed(self):
        entry = self._log(syllabus=None)
        self.assertIsNone(entry.syllabus)

    def test_none_user_allowed(self):
        entry = self._log(user=None)
        self.assertIsNone(entry.user)


# ---------------------------------------------------------------------------
# Test class 3 – _serialize_value() via log_change()
# ---------------------------------------------------------------------------

class SerializeValueTests(AuditLoggerTestMixin, TestCase):
    """
    Tests for _serialize_value() exercised indirectly through log_change().
    Verifies that the stored old_value / new_value is JSON-serialisable and
    has the expected Python type.
    """

    def _log_vals(self, old, new):
        entry = AuditLogger.log_change(
            syllabus=self.syllabus, user=self.user,
            ip_address=self.ip, model_name='Syllabus',
            record_id=1, field_name='test_field',
            old_value=old, new_value=new,
        )
        return entry.old_value, entry.new_value

    def test_none_values_stored_as_none(self):
        old, new = self._log_vals(None, None)
        self.assertIsNone(old)
        self.assertIsNone(new)

    def test_string_values_stored_as_strings(self):
        old, new = self._log_vals('hello', 'world')
        self.assertEqual(old, 'hello')
        self.assertEqual(new, 'world')

    def test_integer_values_stored_as_integers(self):
        old, new = self._log_vals(10, 20)
        self.assertEqual(old, 10)
        self.assertEqual(new, 20)

    def test_float_values_stored_as_floats(self):
        old, new = self._log_vals(3.14, 2.71)
        self.assertAlmostEqual(old, 3.14)
        self.assertAlmostEqual(new, 2.71)

    def test_boolean_true_stored(self):
        old, new = self._log_vals(True, False)
        self.assertIs(old, True)
        self.assertIs(new, False)

    def test_boolean_false_not_confused_with_zero(self):
        """False must stay False, not be coerced to 0."""
        old, _ = self._log_vals(False, None)
        self.assertIs(old, False)

    def test_list_values_stored_as_lists(self):
        old, new = self._log_vals([1, 2, 3], ['a', 'b'])
        self.assertEqual(old, [1, 2, 3])
        self.assertEqual(new, ['a', 'b'])

    def test_dict_values_stored_as_dicts(self):
        old, new = self._log_vals({'k': 1}, {'k': 2, 'x': 'y'})
        self.assertEqual(old, {'k': 1})
        self.assertEqual(new, {'k': 2, 'x': 'y'})

    def test_date_coerced_to_string(self):
        """date objects are not JSON-serialisable natively; must be stringified."""
        d = date(2025, 1, 15)
        old, _ = self._log_vals(d, None)
        self.assertIsInstance(old, str)
        self.assertIn('2025', old)

    def test_nested_list_of_dicts_stored(self):
        val = [{'id': 1, 'name': 'Unit 1'}, {'id': 2, 'name': 'Unit 2'}]
        old, _ = self._log_vals(val, None)
        self.assertEqual(old, val)

    def test_empty_string_stored_as_empty_string(self):
        old, _ = self._log_vals('', None)
        self.assertEqual(old, '')

    def test_zero_integer_stored_correctly(self):
        old, _ = self._log_vals(0, None)
        self.assertEqual(old, 0)


# ---------------------------------------------------------------------------
# Test class 4 – log_bulk_change()
# ---------------------------------------------------------------------------

class LogBulkChangeTests(AuditLoggerTestMixin, TestCase):
    """Tests for AuditLogger.log_bulk_change()."""

    def _make_changes(self, n=3):
        return [
            {'action': 'delete', 'record_id': i, 'data': {'title': f'Unit {i}'}}
            for i in range(1, n + 1)
        ]

    def test_creates_one_log_entry(self):
        """log_bulk_change() creates exactly one SyllabusEditLog row."""
        before = SyllabusEditLog.objects.count()
        AuditLogger.log_bulk_change(
            self.syllabus, self.user, self.ip,
            'TheoryUnit', self._make_changes(5)
        )
        self.assertEqual(SyllabusEditLog.objects.count(), before + 1)

    def test_returns_log_entry(self):
        entry = AuditLogger.log_bulk_change(
            self.syllabus, self.user, self.ip,
            'TheoryUnit', self._make_changes(2)
        )
        self.assertIsInstance(entry, SyllabusEditLog)
        self.assertIsNotNone(entry.pk)

    def test_action_type_is_bulk_update(self):
        entry = AuditLogger.log_bulk_change(
            self.syllabus, self.user, self.ip,
            'CourseObjective', self._make_changes(3)
        )
        self.assertEqual(entry.action_type, 'bulk_update')

    def test_model_name_stored(self):
        entry = AuditLogger.log_bulk_change(
            self.syllabus, self.user, self.ip,
            'CourseObjective', self._make_changes()
        )
        self.assertEqual(entry.model_name, 'CourseObjective')

    def test_changes_stored_in_old_value(self):
        """The full changes list is persisted in old_value."""
        changes = self._make_changes(3)
        entry = AuditLogger.log_bulk_change(
            self.syllabus, self.user, self.ip,
            'TheoryUnit', changes
        )
        self.assertEqual(entry.old_value, changes)

    def test_new_value_is_none(self):
        entry = AuditLogger.log_bulk_change(
            self.syllabus, self.user, self.ip,
            'TheoryUnit', self._make_changes()
        )
        self.assertIsNone(entry.new_value)

    def test_record_id_is_none(self):
        """Bulk operations don't reference a single record_id."""
        entry = AuditLogger.log_bulk_change(
            self.syllabus, self.user, self.ip,
            'TheoryUnit', self._make_changes()
        )
        self.assertIsNone(entry.record_id)

    def test_description_mentions_model_and_count(self):
        entry = AuditLogger.log_bulk_change(
            self.syllabus, self.user, self.ip,
            'TheoryUnit', self._make_changes(7)
        )
        self.assertIn('TheoryUnit', entry.description)
        self.assertIn('7', entry.description)

    def test_empty_changes_list_allowed(self):
        """An empty change list is valid (e.g., bulk clear that found nothing)."""
        entry = AuditLogger.log_bulk_change(
            self.syllabus, self.user, self.ip,
            'CourseObjective', []
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry.old_value, [])

    def test_syllabus_and_user_set(self):
        entry = AuditLogger.log_bulk_change(
            self.syllabus, self.user, self.ip,
            'LearningResource', self._make_changes()
        )
        self.assertEqual(entry.syllabus, self.syllabus)
        self.assertEqual(entry.user, self.user)

    def test_ip_address_set(self):
        entry = AuditLogger.log_bulk_change(
            self.syllabus, self.user, '172.16.0.1',
            'LearningResource', self._make_changes()
        )
        self.assertEqual(entry.ip_address, '172.16.0.1')


# ---------------------------------------------------------------------------
# Test class 5 – Error handling: audit failures are non-fatal
# ---------------------------------------------------------------------------

class AuditLoggerErrorHandlingTests(AuditLoggerTestMixin, TestCase):
    """
    Audit failures must never raise to the caller.
    Instead they log to Django's error log and return None.

    Requirements: 1.1, 1.2
    """

    def test_log_change_returns_none_on_db_error(self):
        """When DB creation raises, log_change() returns None (not raises)."""
        with patch(
            'accounts.audit_logger.SyllabusEditLog.objects.create',
            side_effect=Exception("DB error")
        ):
            result = AuditLogger.log_change(
                self.syllabus, self.user, self.ip,
                'Syllabus', 1, 'title', 'old', 'new'
            )
        self.assertIsNone(result)

    def test_log_change_logs_error_on_failure(self):
        """When DB creation fails, the error is logged."""
        with patch(
            'accounts.audit_logger.SyllabusEditLog.objects.create',
            side_effect=Exception("DB error")
        ), patch('accounts.audit_logger.logger.error') as mock_log:
            AuditLogger.log_change(
                self.syllabus, self.user, self.ip,
                'Syllabus', 1, 'title', 'old', 'new'
            )
            mock_log.assert_called_once()

    def test_log_bulk_change_returns_none_on_db_error(self):
        """When DB creation raises, log_bulk_change() returns None."""
        with patch(
            'accounts.audit_logger.SyllabusEditLog.objects.create',
            side_effect=Exception("DB error")
        ):
            result = AuditLogger.log_bulk_change(
                self.syllabus, self.user, self.ip,
                'TheoryUnit', [{'action': 'delete', 'record_id': 1, 'data': {}}]
            )
        self.assertIsNone(result)

    def test_log_bulk_change_logs_error_on_failure(self):
        """When DB creation fails, the bulk error is logged."""
        with patch(
            'accounts.audit_logger.SyllabusEditLog.objects.create',
            side_effect=Exception("DB error")
        ), patch('accounts.audit_logger.logger.error') as mock_log:
            AuditLogger.log_bulk_change(
                self.syllabus, self.user, self.ip,
                'TheoryUnit', [{'action': 'delete', 'record_id': 1, 'data': {}}]
            )
            mock_log.assert_called_once()

    def test_log_change_does_not_raise_on_error(self):
        """Calling log_change() when creation fails never propagates an exception."""
        with patch(
            'accounts.audit_logger.SyllabusEditLog.objects.create',
            side_effect=RuntimeError("unexpected")
        ):
            try:
                AuditLogger.log_change(
                    self.syllabus, self.user, self.ip,
                    'Syllabus', 1, 'f', 'a', 'b'
                )
            except Exception as exc:
                self.fail(f"log_change() raised unexpectedly: {exc}")


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
    print("Task 3.4: AuditLogger Unit Tests")
    print("  3.1 get_client_ip()")
    print("  3.2 log_change()  +  _serialize_value()")
    print("  3.3 log_bulk_change()")
    print("  Error handling (non-fatal audit failures)")
    print("=" * 80)
    print()

    success = run_tests()

    print()
    print("=" * 80)
    print("OK: All tests passed!" if success else "FAIL: Some tests failed!")
    print("=" * 80)

    sys.exit(0 if success else 1)
