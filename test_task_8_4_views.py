#!/usr/bin/env python
"""
Task 8.4 – Integration tests for audit log views
=================================================

Tests audit_log_list and audit_log_detail views end-to-end using Django's
test Client.  Minimal in-memory templates render log PKs into the body so
we can assert content without relying on response.context (which is None
when locmem.Loader is used, because the template_rendered signal isn't wired
to the test runner in that configuration).

Requirements: 2.1, 2.2, 2.3, 2.4, 3.3
"""

import os
import sys
from datetime import date, timedelta

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from accounts.audit_logger import AuditLogger
from accounts.models import SyllabusEditLog
from adminpanel.models import Syllabus, Subject, Faculty, School, Program, Branch


# ---------------------------------------------------------------------------
# Minimal in-memory templates
# Each log's PK is rendered into the body so assertContains works.
# ---------------------------------------------------------------------------

MINIMAL_TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'OPTIONS': {
            'loaders': [
                ('django.template.loaders.locmem.Loader', {
                    'accounts/audit_log_list.html':
                        '{% for log in logs %}PK:{{ log.pk }} {% endfor %}',
                    'accounts/audit_log_detail.html':
                        'PK:{{ log.pk }}',
                }),
            ],
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    }
]

SETTINGS = dict(
    TEMPLATES=MINIMAL_TEMPLATES,
    ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'],
)


# ---------------------------------------------------------------------------
# Shared fixture mixin
# ---------------------------------------------------------------------------

class ViewTestMixin:
    def setUp(self):
        self.client = Client()

        # Admin
        self.admin = User.objects.create_user(
            username='view_admin', password='pass', is_staff=True)

        school = School.objects.create(name='VT School', code='VT')
        program = Program.objects.create(name='VT Prog', school=school)
        branch = Branch.objects.create(name='VT Branch', program=program)

        # Faculty A
        self.user_a = User.objects.create_user(username='view_fa', password='pass')
        self.faculty_a = Faculty.objects.create(
            user=self.user_a, full_name='View FA', faculty_id='VFA',
            email='vfa@t.com', mobile='3333333333', semester='1')

        # Faculty B
        self.user_b = User.objects.create_user(username='view_fb', password='pass')
        self.faculty_b = Faculty.objects.create(
            user=self.user_b, full_name='View FB', faculty_id='VFB',
            email='vfb@t.com', mobile='4444444444', semester='1')

        # Plain user (no Faculty record)
        self.plain_user = User.objects.create_user(
            username='view_plain', password='pass')

        # Subjects
        self.subject_a = Subject.objects.create(
            course_code='VA01', course_name='View Subject A',
            school=school, program=program, branch=branch)
        self.subject_b = Subject.objects.create(
            course_code='VB01', course_name='View Subject B',
            school=school, program=program, branch=branch)

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

        # Clear signal-generated logs; create controlled ones
        SyllabusEditLog.objects.all().delete()
        self.log_a = AuditLogger.log_change(
            self.syllabus_a, self.user_a, '10.0.0.1',
            'Syllabus', self.syllabus_a.pk, 'rationale', 'Old', 'New', 'update')
        self.log_b = AuditLogger.log_change(
            self.syllabus_b, self.user_b, '10.0.0.2',
            'Syllabus', self.syllabus_b.pk, 'rationale', 'Old', 'New', 'update')

    def _pk_str(self, log):
        """Return the string fragment our templates render for a log entry."""
        return f'PK:{log.pk}'


# ---------------------------------------------------------------------------
# Test class 1 – audit_log_list view
# ---------------------------------------------------------------------------

@override_settings(**SETTINGS)
class AuditLogListViewTests(ViewTestMixin, TestCase):

    def _url(self, **params):
        url = reverse('audit_log_list')
        if params:
            qs = '&'.join(f'{k}={v}' for k, v in params.items())
            url = f'{url}?{qs}'
        return url

    # --- Authentication ---

    def test_redirects_anonymous_to_login(self):
        response = self.client.get(self._url())
        self.assertIn(response.status_code, [301, 302])
        self.assertIn('login', response['Location'])

    # --- Status codes ---

    def test_admin_gets_200(self):
        self.client.login(username='view_admin', password='pass')
        self.assertEqual(self.client.get(self._url()).status_code, 200)

    def test_faculty_gets_200(self):
        self.client.login(username='view_fa', password='pass')
        self.assertEqual(self.client.get(self._url()).status_code, 200)

    def test_plain_user_gets_200(self):
        """Plain user gets 200 but sees empty list."""
        self.client.login(username='view_plain', password='pass')
        self.assertEqual(self.client.get(self._url()).status_code, 200)

    # --- Content: admin sees all logs ---

    def test_admin_sees_log_a(self):
        self.client.login(username='view_admin', password='pass')
        response = self.client.get(self._url())
        self.assertContains(response, self._pk_str(self.log_a))

    def test_admin_sees_log_b(self):
        self.client.login(username='view_admin', password='pass')
        response = self.client.get(self._url())
        self.assertContains(response, self._pk_str(self.log_b))

    # --- Content: faculty sees only their own logs ---

    def test_faculty_a_sees_log_a(self):
        self.client.login(username='view_fa', password='pass')
        response = self.client.get(self._url())
        self.assertContains(response, self._pk_str(self.log_a))

    def test_faculty_a_does_not_see_log_b(self):
        self.client.login(username='view_fa', password='pass')
        response = self.client.get(self._url())
        self.assertNotContains(response, self._pk_str(self.log_b))

    def test_faculty_b_sees_log_b(self):
        self.client.login(username='view_fb', password='pass')
        response = self.client.get(self._url())
        self.assertContains(response, self._pk_str(self.log_b))

    def test_faculty_b_does_not_see_log_a(self):
        self.client.login(username='view_fb', password='pass')
        response = self.client.get(self._url())
        self.assertNotContains(response, self._pk_str(self.log_a))

    # --- Content: plain user sees nothing ---

    def test_plain_user_sees_no_log_pks(self):
        self.client.login(username='view_plain', password='pass')
        response = self.client.get(self._url())
        self.assertNotContains(response, self._pk_str(self.log_a))
        self.assertNotContains(response, self._pk_str(self.log_b))

    # --- Filtering ---

    def test_filter_by_subject_a_shows_log_a(self):
        self.client.login(username='view_admin', password='pass')
        response = self.client.get(self._url(subject=self.subject_a.pk))
        self.assertContains(response, self._pk_str(self.log_a))
        self.assertNotContains(response, self._pk_str(self.log_b))

    def test_filter_by_subject_b_shows_log_b(self):
        self.client.login(username='view_admin', password='pass')
        response = self.client.get(self._url(subject=self.subject_b.pk))
        self.assertContains(response, self._pk_str(self.log_b))
        self.assertNotContains(response, self._pk_str(self.log_a))

    def test_filter_by_date_from_future_shows_no_logs(self):
        tomorrow = (timezone.now() + timedelta(days=1)).date().isoformat()
        self.client.login(username='view_admin', password='pass')
        response = self.client.get(self._url(date_from=tomorrow))
        self.assertNotContains(response, self._pk_str(self.log_a))
        self.assertNotContains(response, self._pk_str(self.log_b))

    def test_filter_by_date_to_past_shows_no_logs(self):
        yesterday = (timezone.now() - timedelta(days=1)).date().isoformat()
        self.client.login(username='view_admin', password='pass')
        response = self.client.get(self._url(date_to=yesterday))
        self.assertNotContains(response, self._pk_str(self.log_a))
        self.assertNotContains(response, self._pk_str(self.log_b))

    def test_filter_by_date_range_current_shows_logs(self):
        past = (timezone.now() - timedelta(hours=1)).date().isoformat()
        future = (timezone.now() + timedelta(hours=1)).date().isoformat()
        self.client.login(username='view_admin', password='pass')
        response = self.client.get(
            self._url(date_from=past, date_to=future))
        self.assertContains(response, self._pk_str(self.log_a))

    # --- Faculty cannot escape their subject filter via GET params ---

    def test_faculty_a_cannot_see_log_b_via_subject_filter(self):
        """Faculty filtering to subject_b is allowed but still yields no logs
        (subject_b is not in their assigned subjects)."""
        self.client.login(username='view_fa', password='pass')
        response = self.client.get(self._url(subject=self.subject_b.pk))
        self.assertNotContains(response, self._pk_str(self.log_b))

    # --- Pagination ---

    def test_pagination_page_1_returns_200(self):
        self.client.login(username='view_admin', password='pass')
        self.assertEqual(self.client.get(self._url(page=1)).status_code, 200)

    def test_pagination_beyond_last_page_returns_200(self):
        """Django's get_page() clamps out-of-range pages to last page."""
        self.client.login(username='view_admin', password='pass')
        self.assertEqual(self.client.get(self._url(page=9999)).status_code, 200)


# ---------------------------------------------------------------------------
# Test class 2 – audit_log_detail view
# ---------------------------------------------------------------------------

@override_settings(**SETTINGS)
class AuditLogDetailViewTests(ViewTestMixin, TestCase):

    def _url(self, log_id):
        return reverse('audit_log_detail', kwargs={'log_id': log_id})

    # --- Authentication ---

    def test_redirects_anonymous_to_login(self):
        response = self.client.get(self._url(self.log_a.pk))
        self.assertIn(response.status_code, [301, 302])

    # --- Status codes ---

    def test_admin_can_view_log_a(self):
        self.client.login(username='view_admin', password='pass')
        self.assertEqual(self.client.get(self._url(self.log_a.pk)).status_code, 200)

    def test_admin_can_view_log_b(self):
        self.client.login(username='view_admin', password='pass')
        self.assertEqual(self.client.get(self._url(self.log_b.pk)).status_code, 200)

    def test_faculty_a_can_view_their_log(self):
        self.client.login(username='view_fa', password='pass')
        self.assertEqual(self.client.get(self._url(self.log_a.pk)).status_code, 200)

    def test_faculty_a_gets_403_for_faculty_b_log(self):
        self.client.login(username='view_fa', password='pass')
        self.assertEqual(self.client.get(self._url(self.log_b.pk)).status_code, 403)

    def test_plain_user_gets_403(self):
        self.client.login(username='view_plain', password='pass')
        self.assertEqual(self.client.get(self._url(self.log_a.pk)).status_code, 403)

    def test_nonexistent_log_returns_404(self):
        self.client.login(username='view_admin', password='pass')
        self.assertEqual(self.client.get(self._url(999999)).status_code, 404)

    # --- Content ---

    def test_admin_detail_contains_pk(self):
        self.client.login(username='view_admin', password='pass')
        response = self.client.get(self._url(self.log_a.pk))
        self.assertContains(response, self._pk_str(self.log_a))

    def test_faculty_a_detail_contains_pk(self):
        self.client.login(username='view_fa', password='pass')
        response = self.client.get(self._url(self.log_a.pk))
        self.assertContains(response, self._pk_str(self.log_a))

    def test_403_response_does_not_contain_log_pk(self):
        """When faculty_a is denied access to log_b, body must not contain log_b PK."""
        self.client.login(username='view_fa', password='pass')
        response = self.client.get(self._url(self.log_b.pk))
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(
            str(self.log_b.pk).encode(), response.content,
            "Forbidden response must not reveal the denied log's PK"
        )


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
    print("Task 8.4: Audit Log View Integration Tests")
    print("  8.1  audit_log_list  - list, filter, paginate, role access")
    print("  8.2  audit_log_detail - per-entry permission + content")
    print("  8.3  URL patterns registered")
    print("=" * 80)
    print()

    success = run_tests()

    print()
    print("=" * 80)
    print("OK: All tests passed!" if success else "FAIL: Some tests failed!")
    print("=" * 80)

    sys.exit(0 if success else 1)
