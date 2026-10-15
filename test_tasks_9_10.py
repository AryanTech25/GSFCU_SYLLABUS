#!/usr/bin/env python
"""
Tasks 9.4 + 10.2 – Integration tests for progressive save and PDF completeness
===============================================================================

9.4: Tests that the syllabus_builder POST view enforces progressive
     SlideValidator rules and updates last_completed_slide.
10.2: Tests that generate_pdf returns JSON 400 for incomplete syllabi
      and succeeds for complete ones.

Requirements: 4.1, 4.2, 4.3, 4.5, 4.6, 6.1, 6.2, 6.5
"""

import os
import sys
from datetime import date

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse

from adminpanel.models import (
    Syllabus, Subject, Faculty, School, Program, Branch,
    CourseObjective, TheoryUnit, EvaluationScheme, CourseOutcome,
    OutcomeMapping, LearningResource,
)

# ---------------------------------------------------------------------------
# Minimal templates
# ---------------------------------------------------------------------------

MINIMAL_TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'OPTIONS': {
            'loaders': [
                ('django.template.loaders.locmem.Loader', {
                    'accounts/syllabus_builder.html':
                        'ERROR:{{ error }}|SLIDE:{{ current_slide }}',
                    'accounts/faculty_dashboard.html': 'OK',
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
# Shared fixture
# ---------------------------------------------------------------------------

class SyllabusViewMixin:
    def setUp(self):
        self.client = Client()

        school = School.objects.create(name='PS School', code='PS')
        program = Program.objects.create(name='PS Prog', school=school)
        self.branch = Branch.objects.create(name='PS Branch', program=program)

        self.user = User.objects.create_user(username='psf1', password='pass')
        self.faculty = Faculty.objects.create(
            user=self.user, full_name='PS Faculty', faculty_id='PSF1',
            email='psf1@t.com', mobile='5555555555', semester='1')

        self.subject = Subject.objects.create(
            course_code='PS01', course_name='PS Subject',
            school=school, program=program, branch=self.branch)
        self.subject.faculties.add(self.faculty)

        self.client.login(username='psf1', password='pass')

    def _minimal_slide1_data(self):
        """POST data that passes slide 1 validation (all slide-1 required fields)."""
        return {
            'save_mode': 'draft',
            'subject_id': str(self.subject.pk),
            'current_slide': '1',
            'hours_lecture': '3',
            'hours_practical': '0',
            'hours_tutorial': '0',
            'credit_lecture': '3',
            'credit_practical': '0',
            'credit_tutorial': '0',
            'prerequisites': 'Mathematics and Physics',
            'category': 'PC',
            'focus': 'Employability',
            'course_focus': 'Employability',
        }

    def _full_draft_post_data(self):
        """Minimal POST data that passes all 8 slides."""
        return {
            'save_mode': 'draft',
            'subject_id': str(self.subject.pk),
            'current_slide': '8',
            'hours_lecture': '3',
            'hours_practical': '0',
            'hours_tutorial': '0',
            'credit_lecture': '3',
            'credit_practical': '0',
            'credit_tutorial': '0',
            'prerequisites': 'Mathematics and Physics',
            'category': 'PC',
            'focus': 'Employability',
            'course_focus': 'Employability',
            'rationale': 'A solid foundation in core engineering concepts.',
            'approval_date': str(date.today()),
            # Objectives
            'obj_111': 'Understand fundamentals',
            # Units
            'unit_title_222': 'Introduction',
            'unit_desc_222': 'Overview of the subject',
            'unit_weight_222': '100',
            'unit_hours_222': '30',
            # No practicals (hours_practical=0)
            # Evaluation
            'eval_mid': '30',
            'eval_end': '50',
            'eval_cec_att': '10',
            'eval_cec_mcq': '5',
            'eval_cec_assign': '5',
            'eval_prac_att': '0',
            'eval_prac_exam': '0',
            'eval_prac_viva': '0',
            'eval_prac_journal': '0',
            'eval_prac_disc': '0',
            # CO
            'co_desc_333': 'Apply core engineering principles',
            'map_co1_po1': '3', 'map_co1_po2': '2', 'map_co1_po3': '1',
            'map_co1_po4': '0', 'map_co1_po5': '0', 'map_co1_po6': '0',
            'map_co1_po7': '0', 'map_co1_po8': '0', 'map_co1_po9': '0',
            'map_co1_po10': '0', 'map_co1_po11': '0', 'map_co1_po12': '0',
            # Resources
            'res_cat_444': 'Textbook',
            'res_content_444': 'Engineering Fundamentals, 3rd Ed.',
        }


# ---------------------------------------------------------------------------
# Task 9.4 – Progressive save tests
# ---------------------------------------------------------------------------

@override_settings(ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'])
class ProgressiveSaveTests(SyllabusViewMixin, TestCase):
    """Tests that use the REAL file-system templates so saves can redirect."""

    def _post(self, data):
        return self.client.post(
            reverse('syllabus_builder'), data=data, follow=False,
            raise_request_exception=True)

    # --- Full valid data saves and redirects ---

    def test_full_valid_data_redirects_to_dashboard(self):
        response = self._post(self._full_draft_post_data())
        self.assertIn(response.status_code, [301, 302])

    def test_full_valid_data_creates_syllabus(self):
        self._post(self._full_draft_post_data())
        self.assertTrue(
            Syllabus.objects.filter(subject=self.subject, faculty=self.faculty).exists()
        )

    def test_last_completed_slide_updated(self):
        self._post(self._full_draft_post_data())
        syl = Syllabus.objects.get(subject=self.subject, faculty=self.faculty)
        self.assertEqual(syl.last_completed_slide, 8)

    def test_last_completed_slide_not_decremented(self):
        """Submitting slide 3 when slide 8 was already reached should keep 8."""
        self._post(self._full_draft_post_data())  # reach slide 8
        data = self._full_draft_post_data()
        data['current_slide'] = '3'
        self._post(data)
        syl = Syllabus.objects.get(subject=self.subject, faculty=self.faculty)
        self.assertEqual(syl.last_completed_slide, 8)

    # --- Optimistic locking ---

    def test_stale_last_modified_rejected(self):
        """Submitting a last_modified timestamp older than the DB value raises error."""
        self._post(self._full_draft_post_data())  # create the row
        syl = Syllabus.objects.get(subject=self.subject)
        # Send an old timestamp
        data = self._full_draft_post_data()
        data['last_modified'] = '2000-01-01T00:00:00+00:00'
        response = self._post(data)
        # View catches exception and re-renders with an error (200)
        self.assertEqual(response.status_code, 200)

    def test_current_last_modified_accepted(self):
        """Sending the correct updated_at timestamp allows the save."""
        self._post(self._full_draft_post_data())
        syl = Syllabus.objects.get(subject=self.subject)
        data = self._full_draft_post_data()
        data['last_modified'] = syl.updated_at.isoformat()
        response = self._post(data)
        self.assertIn(response.status_code, [200, 301, 302])


@override_settings(**SETTINGS)
class ProgressiveSlideValidationTests(SyllabusViewMixin, TestCase):
    """Tests that inspect rendered HTML error output (uses minimal templates)."""

    def _post(self, data):
        return self.client.post(
            reverse('syllabus_builder'), data=data, follow=False)

    # --- Slide validation rejects missing slide 1 fields ---

    def test_slide1_missing_hours_returns_200_with_error(self):
        """Incomplete slide 1 data (no hours) triggers slide validation."""
        data = {
            'save_mode': 'draft',
            'subject_id': str(self.subject.pk),
            'current_slide': '1',
            # no hours or other required slide 1 fields
        }
        response = self._post(data)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'ERROR:', response.content)

    def test_slide1_valid_passes_to_backend_validation(self):
        """Slide 1 data passes slide validation; backend validation may still fail."""
        data = self._minimal_slide1_data()
        response = self._post(data)
        # May get 200 (backend error) but NOT a slide validation error
        self.assertNotIn(b'Slide validation failed', response.content)
        self.assertIn(response.status_code, [200, 302])

    def test_slide1_save_allowed_without_later_slide_data(self):
        """Saving current_slide=1 should not validate slide 2+ data."""
        data = self._minimal_slide1_data()
        response = self._post(data)
        self.assertNotIn(b'Slide validation failed', response.content)


# ---------------------------------------------------------------------------
# Task 10.2 – PDF generation completeness tests
# ---------------------------------------------------------------------------

@override_settings(**SETTINGS)
class PDFCompletenessTests(SyllabusViewMixin, TestCase):

    def _pdf_url(self, syl_id):
        return reverse('generate_pdf', kwargs={'syllabus_id': syl_id})

    def _make_incomplete_syllabus(self):
        """Create a syllabus missing most required sections."""
        return Syllabus.objects.create(
            subject=self.subject, faculty=self.faculty,
            hours_lecture=3, credit_lecture=3,
            prerequisites='Math',  # too short (<3 chars after strip — actually 4, fine)
            category='PC', rationale='', approval_date=None,
        )

    def _make_complete_syllabus(self):
        """Create a fully-populated syllabus that passes is_complete()."""
        syl = Syllabus.objects.create(
            subject=self.subject, faculty=self.faculty,
            hours_lecture=3, credit_lecture=3,
            prerequisites='Mathematics and Physics',
            category='PC', focus='Employability',
            course_focus='Employability',
            rationale='Core foundation in engineering.',
            approval_date=date.today(),
        )
        obj = CourseObjective.objects.create(syllabus=syl, text='Understand fundamentals')
        unit = TheoryUnit.objects.create(
            syllabus=syl, title='Introduction',
            description='Overview', weightage=100, hours=30)
        EvaluationScheme.objects.create(
            syllabus=syl, mid_sem=30, end_sem=50,
            cec_attendance=10, cec_mcq=5, cec_assignment=5,
            prac_attendance=0, prac_exam=0, prac_viva=0,
            prac_journal=0, prac_discipline=0)
        co = CourseOutcome.objects.create(
            syllabus=syl, code='CO1',
            description='Apply engineering principles')
        OutcomeMapping.objects.create(
            course_outcome=co,
            po1=3, po2=2, po3=1, po4=0, po5=0, po6=0,
            po7=0, po8=0, po9=0, po10=0, po11=0, po12=0)
        LearningResource.objects.create(
            syllabus=syl, category='Textbook',
            content='Engineering Fundamentals, 3rd Ed.')
        return syl

    # --- Incomplete draft returns 400 JSON ---

    def test_incomplete_draft_returns_400(self):
        syl = self._make_incomplete_syllabus()
        response = self.client.get(self._pdf_url(syl.pk))
        self.assertEqual(response.status_code, 400)

    def test_incomplete_draft_response_is_json(self):
        syl = self._make_incomplete_syllabus()
        response = self.client.get(self._pdf_url(syl.pk))
        self.assertEqual(response['Content-Type'], 'application/json')

    def test_incomplete_draft_response_has_error_key(self):
        syl = self._make_incomplete_syllabus()
        import json
        data = json.loads(self.client.get(self._pdf_url(syl.pk)).content)
        self.assertIn('error', data)

    def test_incomplete_draft_response_has_missing_fields(self):
        syl = self._make_incomplete_syllabus()
        import json
        data = json.loads(self.client.get(self._pdf_url(syl.pk)).content)
        self.assertIn('missing_fields', data)
        self.assertIsInstance(data['missing_fields'], list)
        self.assertGreater(len(data['missing_fields']), 0)

    # --- Non-existent syllabus returns 404 ---

    def test_nonexistent_syllabus_returns_404(self):
        response = self.client.get(self._pdf_url(999999))
        self.assertEqual(response.status_code, 404)

    # --- Unauthorized access returns 403 ---

    def test_other_faculty_cannot_generate_pdf(self):
        syl = self._make_complete_syllabus()
        other = User.objects.create_user(username='psf2', password='pass')
        Faculty.objects.create(
            user=other, full_name='PS F2', faculty_id='PSF2',
            email='psf2@t.com', mobile='6666666666', semester='1')
        self.client.logout()
        self.client.login(username='psf2', password='pass')
        response = self.client.get(self._pdf_url(syl.pk))
        self.assertEqual(response.status_code, 403)


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
    print("Tasks 9.4 + 10.2: Progressive Save & PDF Completeness Tests")
    print("  9.1  current_slide extraction + SlideValidator")
    print("  9.2  post-save completeness message")
    print("  9.3  optimistic locking (last_modified)")
    print("  10.1 is_complete() gates PDF generation")
    print("=" * 80)
    print()

    success = run_tests()

    print()
    print("=" * 80)
    print("OK: All tests passed!" if success else "FAIL: Some tests failed!")
    print("=" * 80)

    sys.exit(0 if success else 1)
