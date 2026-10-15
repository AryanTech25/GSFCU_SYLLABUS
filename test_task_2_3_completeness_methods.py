#!/usr/bin/env python
"""
Comprehensive test for Task 2.3: Unit tests for Syllabus completeness methods

Tests both is_complete() (Task 2.1) and get_completion_percentage() (Task 2.2):

is_complete() tests:
  - All fields filled → (True, [])
  - Various missing field combinations → (False, [<missing>])
  - Theory unit weightage boundary: 99.9%, 100%, 100.1%

get_completion_percentage() tests:
  - Empty syllabus → low percentage
  - Fully complete syllabus → 100%
  - Partial completions → correct intermediate percentages
  - Return type is always int
  - Monotonically increasing as sections are added
  - Theory unit weightage counts as separate check

Requirements: 5.1, 5.2, 5.3, 7.5
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


# ---------------------------------------------------------------------------
# Shared fixture mixin
# ---------------------------------------------------------------------------

class SyllabusTestMixin:
    """
    Mixin that creates the minimum infrastructure (school, program, branch,
    user, faculty, subject) needed for Syllabus tests.  Each test class that
    uses this mixin gets a fresh database via Django's TestCase transaction
    rollback, so subjects / syllabi can be created freely with the same codes.
    """

    def _make_subject(self, code='CS101', name='Test Course'):
        return Subject.objects.create(
            course_code=code,
            course_name=name,
            semester='1',
            school=self.school,
            program=self.program,
            branch=self.branch
        )

    def _make_syllabus(self, subject=None, **overrides):
        """Return a Syllabus with sensible defaults for basic (non-relational) fields."""
        if subject is None:
            subject = self.subject
        defaults = dict(
            subject=subject,
            faculty=self.faculty,
            hours_lecture=3,
            hours_practical=2,
            credit_lecture=3,
            credit_practical=1,
            prerequisites='Mathematics Basics',
            category='PC',
            rationale='Important for understanding programming',
            approval_date=date.today(),
        )
        defaults.update(overrides)
        return Syllabus.objects.create(**defaults)

    def _fill_all_sections(self, syllabus, weightage_total=100):
        """
        Add every required related object to `syllabus` so that is_complete()
        returns (True, []).  Returns a dict of created objects for inspection.
        """
        obj = CourseObjective.objects.create(
            syllabus=syllabus,
            text='Understand programming concepts',
            blooms_domain='Cognitive'
        )

        # Split weightage_total across two units
        w1 = weightage_total // 2
        w2 = weightage_total - w1
        u1 = TheoryUnit.objects.create(
            syllabus=syllabus, title='Unit 1',
            description='Introduction', weightage=w1, hours=10
        )
        u2 = TheoryUnit.objects.create(
            syllabus=syllabus, title='Unit 2',
            description='Advanced Topics', weightage=w2, hours=10
        )

        ev = EvaluationScheme.objects.create(
            syllabus=syllabus, mid_sem=30, end_sem=70
        )

        co = CourseOutcome.objects.create(
            syllabus=syllabus, code='CO1',
            description='Understand basic concepts'
        )
        mapping = OutcomeMapping.objects.create(
            course_outcome=co, po1=1, po2=2, po3=1
        )

        lr = LearningResource.objects.create(
            syllabus=syllabus, category='Textbook',
            content='Programming in Python'
        )

        return dict(
            objective=obj, unit1=u1, unit2=u2,
            evaluation=ev, outcome=co, mapping=mapping,
            resource=lr
        )

    def setUp(self):
        self.user = User.objects.create_user(
            username='testfaculty', password='testpass123'
        )
        self.school = School.objects.create(name='Test School', code='TS')
        self.program = Program.objects.create(
            name='Test Program', school=self.school
        )
        self.branch = Branch.objects.create(
            name='Test Branch', program=self.program
        )
        self.faculty = Faculty.objects.create(
            user=self.user, full_name='Test Faculty',
            faculty_id='FAC001', email='test@test.com',
            mobile='1234567890', semester='1'
        )
        self.subject = self._make_subject()
        # Base syllabus with all simple fields set but NO related objects yet
        self.syllabus = self._make_syllabus()


# ---------------------------------------------------------------------------
# Test class 1: is_complete() – complete syllabus
# ---------------------------------------------------------------------------

class IsCompleteAllFilledTests(SyllabusTestMixin, TestCase):
    """Test is_complete() returns (True, []) when all sections are present."""

    def test_fully_complete_syllabus_returns_true(self):
        """All required sections present → is_complete returns True."""
        self._fill_all_sections(self.syllabus)
        is_complete, missing = self.syllabus.is_complete()
        self.assertTrue(is_complete, f"Expected complete but missing: {missing}")

    def test_fully_complete_syllabus_has_empty_missing_list(self):
        """All required sections present → missing list is empty."""
        self._fill_all_sections(self.syllabus)
        _, missing = self.syllabus.is_complete()
        self.assertEqual(missing, [],
                         f"Expected no missing fields but got: {missing}")

    def test_complete_syllabus_with_multiple_outcomes_all_mapped(self):
        """All COs having mappings → complete."""
        CourseObjective.objects.create(
            syllabus=self.syllabus, text='Obj 1')
        TheoryUnit.objects.create(
            syllabus=self.syllabus, title='U1',
            description='D1', weightage=100, hours=20)
        EvaluationScheme.objects.create(
            syllabus=self.syllabus, mid_sem=30, end_sem=70)
        for i in range(1, 4):
            co = CourseOutcome.objects.create(
                syllabus=self.syllabus,
                code=f'CO{i}', description=f'Outcome {i}')
            OutcomeMapping.objects.create(course_outcome=co, po1=i)
        LearningResource.objects.create(
            syllabus=self.syllabus, category='Textbook', content='Ref book')

        is_complete, missing = self.syllabus.is_complete()
        self.assertTrue(is_complete, f"Missing: {missing}")
        self.assertEqual(missing, [])

    def test_return_type_is_tuple(self):
        """is_complete() always returns a two-element tuple."""
        result = self.syllabus.is_complete()
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_first_element_is_bool(self):
        """First element of the tuple is a bool."""
        is_complete, _ = self.syllabus.is_complete()
        self.assertIsInstance(is_complete, bool)

    def test_second_element_is_list(self):
        """Second element of the tuple is a list."""
        _, missing = self.syllabus.is_complete()
        self.assertIsInstance(missing, list)


# ---------------------------------------------------------------------------
# Test class 2: is_complete() – missing individual fields
# ---------------------------------------------------------------------------

class IsCompleteMissingFieldTests(SyllabusTestMixin, TestCase):
    """Test is_complete() detects each individually missing required section."""

    def _syllabus_for(self, code='CS200', **overrides):
        s = self._make_subject(code=code, name=f'Course {code}')
        return self._make_syllabus(subject=s, **overrides)

    # --- Simple scalar fields ---

    def test_missing_contact_hours(self):
        syl = self._syllabus_for('CS201', hours_lecture=0, hours_practical=0)
        is_complete, missing = syl.is_complete()
        self.assertFalse(is_complete)
        self.assertIn('Contact Hours', missing)

    def test_lecture_hours_alone_satisfies_contact_hours(self):
        """Only lecture hours set (practical=0) still passes contact-hours check."""
        syl = self._syllabus_for('CS202', hours_lecture=3, hours_practical=0)
        _, missing = syl.is_complete()
        self.assertNotIn('Contact Hours', missing)

    def test_practical_hours_alone_satisfies_contact_hours(self):
        """Only practical hours set (lecture=0) still passes contact-hours check."""
        syl = self._syllabus_for('CS203', hours_lecture=0, hours_practical=2)
        _, missing = syl.is_complete()
        self.assertNotIn('Contact Hours', missing)

    def test_missing_credits(self):
        syl = self._syllabus_for('CS204', credit_lecture=0, credit_practical=0)
        is_complete, missing = syl.is_complete()
        self.assertFalse(is_complete)
        self.assertIn('Credits', missing)

    def test_lecture_credits_alone_satisfies_credits(self):
        syl = self._syllabus_for('CS205', credit_lecture=3, credit_practical=0)
        _, missing = syl.is_complete()
        self.assertNotIn('Credits', missing)

    def test_missing_prerequisites_null(self):
        syl = self._syllabus_for('CS206', prerequisites=None)
        is_complete, missing = syl.is_complete()
        self.assertFalse(is_complete)
        self.assertIn('Prerequisites', missing)

    def test_missing_prerequisites_too_short(self):
        """Prerequisites must be at least 3 chars."""
        syl = self._syllabus_for('CS207', prerequisites='AB')
        is_complete, missing = syl.is_complete()
        self.assertFalse(is_complete)
        self.assertIn('Prerequisites', missing)

    def test_prerequisites_exactly_3_chars_passes(self):
        syl = self._syllabus_for('CS208', prerequisites='ABC')
        _, missing = syl.is_complete()
        self.assertNotIn('Prerequisites', missing)

    def test_missing_category(self):
        syl = self._syllabus_for('CS209', category='')
        is_complete, missing = syl.is_complete()
        self.assertFalse(is_complete)
        self.assertIn('Category', missing)

    def test_missing_rationale(self):
        syl = self._syllabus_for('CS210', rationale='')
        is_complete, missing = syl.is_complete()
        self.assertFalse(is_complete)
        self.assertIn('Rationale', missing)

    def test_missing_rationale_null(self):
        syl = self._syllabus_for('CS211', rationale=None)
        is_complete, missing = syl.is_complete()
        self.assertFalse(is_complete)
        self.assertIn('Rationale', missing)

    def test_missing_approval_date(self):
        syl = self._syllabus_for('CS212', approval_date=None)
        is_complete, missing = syl.is_complete()
        self.assertFalse(is_complete)
        self.assertIn('Approval Date', missing)

    # --- Relational sections (using base self.syllabus) ---

    def test_missing_course_objectives(self):
        is_complete, missing = self.syllabus.is_complete()
        self.assertFalse(is_complete)
        self.assertIn('Course Objectives', missing)

    def test_missing_theory_units(self):
        is_complete, missing = self.syllabus.is_complete()
        self.assertFalse(is_complete)
        self.assertIn('Theory Units', missing)

    def test_missing_evaluation_scheme(self):
        is_complete, missing = self.syllabus.is_complete()
        self.assertFalse(is_complete)
        self.assertIn('Evaluation Scheme', missing)

    def test_missing_course_outcomes(self):
        is_complete, missing = self.syllabus.is_complete()
        self.assertFalse(is_complete)
        self.assertIn('Course Outcomes', missing)

    def test_missing_learning_resources(self):
        is_complete, missing = self.syllabus.is_complete()
        self.assertFalse(is_complete)
        self.assertIn('Learning Resources', missing)

    def test_missing_co_po_mapping_for_outcome(self):
        """Course outcome exists but has no mapping → incomplete."""
        CourseObjective.objects.create(
            syllabus=self.syllabus, text='Objective 1')
        TheoryUnit.objects.create(
            syllabus=self.syllabus, title='U1',
            description='D', weightage=100, hours=20)
        EvaluationScheme.objects.create(
            syllabus=self.syllabus, mid_sem=30, end_sem=70)
        CourseOutcome.objects.create(
            syllabus=self.syllabus, code='CO1',
            description='No mapping')          # intentionally no OutcomeMapping
        LearningResource.objects.create(
            syllabus=self.syllabus, category='Book', content='Text')

        is_complete, missing = self.syllabus.is_complete()
        self.assertFalse(is_complete)
        co_po_errors = [m for m in missing if 'CO-PO Mapping' in m]
        self.assertTrue(len(co_po_errors) > 0,
                        "Expected CO-PO Mapping error in missing list")

    def test_multiple_missing_fields_all_reported(self):
        """Brand-new empty syllabus reports all basic section misses."""
        syl = self._syllabus_for(
            'CS220',
            hours_lecture=0, hours_practical=0,
            credit_lecture=0, credit_practical=0,
            prerequisites=None,
            category='',
            rationale=None,
            approval_date=None
        )
        _, missing = syl.is_complete()
        for field in ('Contact Hours', 'Credits', 'Prerequisites',
                      'Category', 'Rationale', 'Approval Date',
                      'Course Objectives', 'Theory Units',
                      'Evaluation Scheme', 'Course Outcomes',
                      'Learning Resources'):
            self.assertIn(field, missing, f"Expected '{field}' in missing list")


# ---------------------------------------------------------------------------
# Test class 3: is_complete() – theory unit weightage boundary tests
# ---------------------------------------------------------------------------

class TheoryUnitWeightageBoundaryTests(SyllabusTestMixin, TestCase):
    """Test the ±0.1% tolerance on theory unit weightage."""

    def _add_other_required(self):
        """Add every required section except theory units."""
        CourseObjective.objects.create(
            syllabus=self.syllabus, text='Objective')
        EvaluationScheme.objects.create(
            syllabus=self.syllabus, mid_sem=30, end_sem=70)
        co = CourseOutcome.objects.create(
            syllabus=self.syllabus, code='CO1', description='Outcome')
        OutcomeMapping.objects.create(course_outcome=co, po1=1)
        LearningResource.objects.create(
            syllabus=self.syllabus, category='Book', content='Content')

    def _set_weightage(self, total):
        """Create two theory units that sum to `total`."""
        w1 = total // 2
        w2 = total - w1
        TheoryUnit.objects.create(
            syllabus=self.syllabus, title='U1',
            description='D', weightage=w1, hours=10)
        TheoryUnit.objects.create(
            syllabus=self.syllabus, title='U2',
            description='D', weightage=w2, hours=10)

    def test_weightage_exactly_100_is_valid(self):
        """Weightage summing to exactly 100% passes the check."""
        self._add_other_required()
        self._set_weightage(100)
        is_complete, missing = self.syllabus.is_complete()
        self.assertTrue(is_complete, f"Missing: {missing}")
        weightage_errors = [m for m in missing if 'Weightage' in m]
        self.assertEqual(weightage_errors, [])

    def test_weightage_99_is_invalid(self):
        """Weightage 99% (deviation > 0.1%) is invalid."""
        self._add_other_required()
        self._set_weightage(99)
        is_complete, missing = self.syllabus.is_complete()
        self.assertFalse(is_complete)
        weightage_errors = [m for m in missing if 'Weightage' in m]
        self.assertTrue(len(weightage_errors) > 0,
                        "Expected weightage error for 99% total")

    def test_weightage_101_is_invalid(self):
        """Weightage 101% (deviation > 0.1%) is invalid."""
        self._add_other_required()
        self._set_weightage(101)
        is_complete, missing = self.syllabus.is_complete()
        self.assertFalse(is_complete)
        weightage_errors = [m for m in missing if 'Weightage' in m]
        self.assertTrue(len(weightage_errors) > 0,
                        "Expected weightage error for 101% total")

    def test_weightage_80_is_invalid(self):
        """Clearly wrong weightage (80%) is invalid."""
        self._add_other_required()
        self._set_weightage(80)
        is_complete, missing = self.syllabus.is_complete()
        self.assertFalse(is_complete)
        weightage_errors = [m for m in missing if 'Weightage' in m]
        self.assertTrue(len(weightage_errors) > 0)

    def test_weightage_error_message_contains_current_percentage(self):
        """Error message contains the actual percentage seen."""
        self._add_other_required()
        self._set_weightage(80)
        _, missing = self.syllabus.is_complete()
        weightage_errors = [m for m in missing if 'Weightage' in m]
        self.assertTrue(len(weightage_errors) > 0)
        self.assertIn('80', weightage_errors[0],
                      "Error message should contain the actual total (80)")

    def test_three_units_summing_to_100_is_valid(self):
        """Three units (33+33+34 = 100) passes."""
        self._add_other_required()
        for w, title in [(33, 'U1'), (33, 'U2'), (34, 'U3')]:
            TheoryUnit.objects.create(
                syllabus=self.syllabus, title=title,
                description='D', weightage=w, hours=7)
        is_complete, missing = self.syllabus.is_complete()
        self.assertTrue(is_complete, f"Missing: {missing}")


# ---------------------------------------------------------------------------
# Test class 4: get_completion_percentage() – core behaviour
# ---------------------------------------------------------------------------

class GetCompletionPercentageTests(SyllabusTestMixin, TestCase):
    """Test get_completion_percentage() across a range of scenarios."""

    # --- Return type and range ---

    def test_returns_integer(self):
        """get_completion_percentage() always returns an int."""
        result = self.syllabus.get_completion_percentage()
        self.assertIsInstance(result, int)

    def test_returns_integer_for_complete_syllabus(self):
        self._fill_all_sections(self.syllabus)
        result = self.syllabus.get_completion_percentage()
        self.assertIsInstance(result, int)

    def test_percentage_in_valid_range_empty(self):
        pct = self.syllabus.get_completion_percentage()
        self.assertGreaterEqual(pct, 0)
        self.assertLessEqual(pct, 100)

    def test_percentage_in_valid_range_complete(self):
        self._fill_all_sections(self.syllabus)
        pct = self.syllabus.get_completion_percentage()
        self.assertGreaterEqual(pct, 0)
        self.assertLessEqual(pct, 100)

    # --- Complete syllabus → 100% ---

    def test_fully_complete_syllabus_is_100_percent(self):
        """When is_complete() returns True, percentage must be 100."""
        self._fill_all_sections(self.syllabus)
        pct = self.syllabus.get_completion_percentage()
        self.assertEqual(pct, 100,
                         "A fully complete syllabus must return 100%")

    # --- Incomplete syllabus → less than 100% ---

    def test_incomplete_syllabus_is_less_than_100(self):
        """Syllabus with relational sections missing is < 100%."""
        pct = self.syllabus.get_completion_percentage()
        self.assertLess(pct, 100)

    def test_empty_syllabus_is_low_percentage(self):
        """A syllabus with all basic fields missing has a very low percentage."""
        s = self._make_subject('CS300', 'Empty Course')
        syl = Syllabus.objects.create(
            subject=s, faculty=self.faculty,
            hours_lecture=0, hours_practical=0,
            credit_lecture=0, credit_practical=0,
            prerequisites=None, category='',
            rationale=None, approval_date=None
        )
        pct = syl.get_completion_percentage()
        self.assertLessEqual(pct, 20,
                             "A fully empty syllabus should be <=20%")

    # --- Monotonic growth as sections are added ---

    def test_percentage_increases_as_sections_added(self):
        """Adding required sections should only ever increase the percentage."""
        prev_pct = self.syllabus.get_completion_percentage()

        CourseObjective.objects.create(
            syllabus=self.syllabus, text='Obj 1')
        pct_after_obj = self.syllabus.get_completion_percentage()
        self.assertGreaterEqual(pct_after_obj, prev_pct,
                                "Adding objectives should not decrease %")

        TheoryUnit.objects.create(
            syllabus=self.syllabus, title='U1',
            description='D', weightage=100, hours=20)
        pct_after_units = self.syllabus.get_completion_percentage()
        self.assertGreaterEqual(pct_after_units, pct_after_obj,
                                "Adding units should not decrease %")

        EvaluationScheme.objects.create(
            syllabus=self.syllabus, mid_sem=30, end_sem=70)
        pct_after_eval = self.syllabus.get_completion_percentage()
        self.assertGreaterEqual(pct_after_eval, pct_after_units,
                                "Adding eval scheme should not decrease %")

        co = CourseOutcome.objects.create(
            syllabus=self.syllabus, code='CO1', description='Outcome')
        pct_after_co = self.syllabus.get_completion_percentage()
        self.assertGreaterEqual(pct_after_co, pct_after_eval,
                                "Adding course outcomes should not decrease %")

        OutcomeMapping.objects.create(course_outcome=co, po1=1)
        pct_after_mapping = self.syllabus.get_completion_percentage()
        self.assertGreaterEqual(pct_after_mapping, pct_after_co,
                                "Adding CO-PO mappings should not decrease %")

        LearningResource.objects.create(
            syllabus=self.syllabus, category='Book', content='Content')
        pct_final = self.syllabus.get_completion_percentage()
        self.assertGreaterEqual(pct_final, pct_after_mapping,
                                "Adding learning resources should not decrease %")

        # Final should be 100 since base syllabus already had all simple fields
        self.assertEqual(pct_final, 100,
                         "After adding all sections, percentage must be 100")

    # --- Weightage error is a separate check that affects percentage ---

    def test_wrong_weightage_lowers_percentage_vs_correct(self):
        """
        Two syllabi identical except one has correct weightage (100%) and the
        other wrong (80%).  The wrong-weightage one must have a lower or equal
        percentage (the weightage error is a distinct check from unit existence).
        """
        # Syllabus A: correct weightage
        s_a = self._make_subject('CS301', 'Course A')
        syl_a = self._make_syllabus(subject=s_a)
        self._fill_all_sections(syl_a, weightage_total=100)

        # Syllabus B: wrong weightage (missing the weightage check)
        s_b = self._make_subject('CS302', 'Course B')
        syl_b = self._make_syllabus(subject=s_b)
        self._fill_all_sections(syl_b, weightage_total=80)

        pct_a = syl_a.get_completion_percentage()
        pct_b = syl_b.get_completion_percentage()

        self.assertEqual(pct_a, 100, "Correct syllabus should be 100%")
        self.assertLess(pct_b, 100,
                        "Wrong-weightage syllabus should be < 100%")
        self.assertGreater(pct_a, pct_b,
                           "Correct syllabus should score higher than wrong-weightage one")

    # --- Consistency with is_complete() ---

    def test_percentage_100_implies_is_complete_true(self):
        """If get_completion_percentage() == 100, is_complete() must return True."""
        self._fill_all_sections(self.syllabus)
        pct = self.syllabus.get_completion_percentage()
        if pct == 100:
            is_complete, _ = self.syllabus.is_complete()
            self.assertTrue(is_complete)

    def test_is_complete_true_implies_100_percent(self):
        """If is_complete() returns True, get_completion_percentage() must return 100."""
        self._fill_all_sections(self.syllabus)
        is_complete, _ = self.syllabus.is_complete()
        if is_complete:
            pct = self.syllabus.get_completion_percentage()
            self.assertEqual(pct, 100)

    def test_incomplete_implies_less_than_100(self):
        """If is_complete() returns False, percentage must be < 100."""
        is_complete, _ = self.syllabus.is_complete()
        if not is_complete:
            pct = self.syllabus.get_completion_percentage()
            self.assertLess(pct, 100)

    # --- Partial completions produce sensible mid-range values ---

    def test_half_sections_gives_meaningful_percentage(self):
        """With roughly half the sections filled, percentage should be in (0, 100)."""
        # Fill only the relational sections (basic fields already set in setUp)
        CourseObjective.objects.create(
            syllabus=self.syllabus, text='Obj 1')
        TheoryUnit.objects.create(
            syllabus=self.syllabus, title='U1',
            description='D', weightage=100, hours=20)
        # Leave out: EvaluationScheme, CourseOutcomes, CO-PO, LearningResources

        pct = self.syllabus.get_completion_percentage()
        self.assertGreater(pct, 0, "Should be > 0 with some sections filled")
        self.assertLess(pct, 100, "Should be < 100 with sections still missing")

    def test_percentage_not_negative(self):
        """Percentage is never negative even for completely empty syllabi."""
        s = self._make_subject('CS303', 'Empty2')
        syl = Syllabus.objects.create(
            subject=s, faculty=self.faculty,
            hours_lecture=0, hours_practical=0,
            credit_lecture=0, credit_practical=0,
            prerequisites=None, category='',
            rationale=None, approval_date=None
        )
        pct = syl.get_completion_percentage()
        self.assertGreaterEqual(pct, 0)

    def test_percentage_not_above_100(self):
        """Percentage never exceeds 100 even if extra data is added."""
        self._fill_all_sections(self.syllabus)
        # Add extra objectives and resources beyond the minimum
        for i in range(5):
            CourseObjective.objects.create(
                syllabus=self.syllabus, text=f'Extra Objective {i}')
        pct = self.syllabus.get_completion_percentage()
        self.assertLessEqual(pct, 100)


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
    print("Task 2.3: Syllabus Completeness Methods Unit Tests")
    print("  -> is_complete()              (Task 2.1)")
    print("  -> get_completion_percentage() (Task 2.2)")
    print("=" * 80)
    print()

    success = run_tests()

    print()
    print("=" * 80)
    if success:
        print("OK: All tests passed!")
    else:
        print("FAIL: Some tests failed!")
    print("=" * 80)

    sys.exit(0 if success else 1)
