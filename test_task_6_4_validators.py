#!/usr/bin/env python
"""
Task 6.4 – Unit tests for SlideValidator
=========================================

Covers:
  validate_slide()           — each of slides 1-8 with valid data
  validate_slide()           — each slide with missing required fields
  validate_slide()           — custom validator failures (invalid values)
  validate_up_to_slide()     — progressive validation aggregation
  Theory-unit weightage      — 99 % / 100 % / 101 %
  Numeric field validation   — negative values
  Edge cases                 — slide 4 (always valid), out-of-range slide

Requirements: 4.1, 4.3, 5.2
"""

import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# SlideValidator has no Django-model dependencies, so we only need minimal setup.
import django
django.setup()

from django.test import SimpleTestCase
from accounts.validators import SlideValidator


# ---------------------------------------------------------------------------
# Helper: minimal valid data per slide
# ---------------------------------------------------------------------------

def _slide1_valid():
    return {
        'hours_lecture': '3', 'hours_practical': '2', 'hours_tutorial': '1',
        'credit_lecture': '3', 'credit_practical': '0', 'credit_tutorial': '0',
        'prerequisites': 'Basic Maths',
        'category': 'PC',
        'focus': 'Theory',
        'course_focus': 'Employability',
    }


def _slide2_valid():
    return {'objectives': ['Understand signals', 'Apply theory']}


def _slide3_valid():
    return {
        'theory_units': [
            {'title': 'Unit 1', 'weightage': 50},
            {'title': 'Unit 2', 'weightage': 50},
        ],
        'theory_weightage': None,  # computed from theory_units, not from data directly
    }


def _slide4_valid():
    # Slide 4 is optional — empty data is fine
    return {}


def _slide5_valid():
    return {'evaluation': {'mid_sem': 30, 'end_sem': 70}}


def _slide6_valid():
    return {
        'course_outcomes': [{'code': 'CO1', 'desc': 'Know basics'}],
        'outcome_mappings': [{'co': 'CO1', 'po1': 2}],
    }


def _slide7_valid():
    return {'learning_resources': [{'type': 'Textbook', 'title': 'Python 3'}]}


def _slide8_valid():
    return {'rationale': 'This course is important for all engineers.',
            'approval_date': '2025-01-01'}


# ---------------------------------------------------------------------------
# Test class 1: valid data on each slide passes
# ---------------------------------------------------------------------------

class ValidateSlideValidDataTests(SimpleTestCase):
    """validate_slide() returns (True, {}) for fully valid data."""

    def test_slide1_valid(self):
        ok, errors = SlideValidator.validate_slide(1, _slide1_valid())
        self.assertTrue(ok, f"Slide 1 should pass; errors: {errors}")
        self.assertEqual(errors, {})

    def test_slide2_valid(self):
        ok, errors = SlideValidator.validate_slide(2, _slide2_valid())
        self.assertTrue(ok)
        self.assertEqual(errors, {})

    def test_slide3_valid(self):
        ok, errors = SlideValidator.validate_slide(3, _slide3_valid())
        self.assertTrue(ok, f"Slide 3 should pass; errors: {errors}")
        self.assertEqual(errors, {})

    def test_slide4_always_valid_empty_data(self):
        """Slide 4 has no required fields so empty data is valid."""
        ok, errors = SlideValidator.validate_slide(4, {})
        self.assertTrue(ok)
        self.assertEqual(errors, {})

    def test_slide4_valid_with_practical_data(self):
        ok, errors = SlideValidator.validate_slide(4, {'practicals': [{'desc': 'Lab'}]})
        self.assertTrue(ok)

    def test_slide5_valid(self):
        ok, errors = SlideValidator.validate_slide(5, _slide5_valid())
        self.assertTrue(ok)
        self.assertEqual(errors, {})

    def test_slide6_valid(self):
        ok, errors = SlideValidator.validate_slide(6, _slide6_valid())
        self.assertTrue(ok, f"Slide 6 should pass; errors: {errors}")
        self.assertEqual(errors, {})

    def test_slide7_valid(self):
        ok, errors = SlideValidator.validate_slide(7, _slide7_valid())
        self.assertTrue(ok)
        self.assertEqual(errors, {})

    def test_slide8_valid(self):
        ok, errors = SlideValidator.validate_slide(8, _slide8_valid())
        self.assertTrue(ok, f"Slide 8 should pass; errors: {errors}")
        self.assertEqual(errors, {})

    def test_out_of_range_slide_returns_valid(self):
        """Slide numbers outside 1-8 return (True, {}) without error."""
        ok, errors = SlideValidator.validate_slide(99, {})
        self.assertTrue(ok)
        self.assertEqual(errors, {})

    def test_slide0_returns_valid(self):
        ok, errors = SlideValidator.validate_slide(0, {})
        self.assertTrue(ok)

    def test_negative_slide_returns_valid(self):
        ok, errors = SlideValidator.validate_slide(-1, {})
        self.assertTrue(ok)


# ---------------------------------------------------------------------------
# Test class 2: missing required fields per slide
# ---------------------------------------------------------------------------

class ValidateSlideMissingFieldsTests(SimpleTestCase):
    """Omitting required fields must produce errors and is_valid=False."""

    # --- Slide 1 ---

    def _slide1_minus(self, *remove_fields):
        d = _slide1_valid()
        for f in remove_fields:
            d.pop(f)
        return d

    def test_slide1_missing_hours_lecture(self):
        ok, errors = SlideValidator.validate_slide(1, self._slide1_minus('hours_lecture'))
        self.assertFalse(ok)
        self.assertIn('hours_lecture', errors)

    def test_slide1_missing_prerequisites(self):
        ok, errors = SlideValidator.validate_slide(1, self._slide1_minus('prerequisites'))
        self.assertFalse(ok)
        self.assertIn('prerequisites', errors)

    def test_slide1_missing_category(self):
        ok, errors = SlideValidator.validate_slide(1, self._slide1_minus('category'))
        self.assertFalse(ok)
        self.assertIn('category', errors)

    def test_slide1_missing_focus(self):
        ok, errors = SlideValidator.validate_slide(1, self._slide1_minus('focus'))
        self.assertFalse(ok)
        self.assertIn('focus', errors)

    def test_slide1_missing_course_focus(self):
        ok, errors = SlideValidator.validate_slide(1, self._slide1_minus('course_focus'))
        self.assertFalse(ok)
        self.assertIn('course_focus', errors)

    def test_slide1_multiple_missing_fields(self):
        ok, errors = SlideValidator.validate_slide(
            1, self._slide1_minus('hours_lecture', 'category', 'prerequisites'))
        self.assertFalse(ok)
        self.assertIn('hours_lecture', errors)
        self.assertIn('category', errors)
        self.assertIn('prerequisites', errors)

    # --- Slide 2 ---

    def test_slide2_missing_objectives(self):
        ok, errors = SlideValidator.validate_slide(2, {})
        self.assertFalse(ok)
        self.assertIn('objectives', errors)

    # --- Slide 3 ---

    def test_slide3_missing_theory_units(self):
        ok, errors = SlideValidator.validate_slide(3, {})
        self.assertFalse(ok)
        self.assertIn('theory_units', errors)

    # --- Slide 4 ---

    def test_slide4_no_required_fields(self):
        """Slide 4 has no required fields — any data (or empty) is fine."""
        ok, errors = SlideValidator.validate_slide(4, {})
        self.assertTrue(ok)
        self.assertEqual(errors, {})

    # --- Slide 5 ---

    def test_slide5_missing_evaluation(self):
        ok, errors = SlideValidator.validate_slide(5, {})
        self.assertFalse(ok)
        self.assertIn('evaluation', errors)

    # --- Slide 6 ---

    def test_slide6_missing_course_outcomes(self):
        d = _slide6_valid()
        d.pop('course_outcomes')
        ok, errors = SlideValidator.validate_slide(6, d)
        self.assertFalse(ok)
        self.assertIn('course_outcomes', errors)

    def test_slide6_missing_outcome_mappings(self):
        d = _slide6_valid()
        d.pop('outcome_mappings')
        ok, errors = SlideValidator.validate_slide(6, d)
        self.assertFalse(ok)
        self.assertIn('outcome_mappings', errors)

    # --- Slide 7 ---

    def test_slide7_missing_learning_resources(self):
        ok, errors = SlideValidator.validate_slide(7, {})
        self.assertFalse(ok)
        self.assertIn('learning_resources', errors)

    # --- Slide 8 ---

    def test_slide8_missing_rationale(self):
        ok, errors = SlideValidator.validate_slide(8, {'approval_date': '2025-01-01'})
        self.assertFalse(ok)
        self.assertIn('rationale', errors)

    def test_slide8_missing_approval_date(self):
        ok, errors = SlideValidator.validate_slide(8, {'rationale': 'Long enough rationale text here'})
        self.assertFalse(ok)
        self.assertIn('approval_date', errors)

    def test_slide8_missing_both(self):
        ok, errors = SlideValidator.validate_slide(8, {})
        self.assertFalse(ok)
        self.assertIn('rationale', errors)
        self.assertIn('approval_date', errors)


# ---------------------------------------------------------------------------
# Test class 3: custom validator failures
# ---------------------------------------------------------------------------

class ValidateSlideCustomValidatorTests(SimpleTestCase):
    """Field-level validators catch semantically invalid values."""

    # --- Slide 1: prerequisites length ---

    def test_slide1_prerequisites_too_short(self):
        d = _slide1_valid()
        d['prerequisites'] = 'ab'   # < 3 chars
        ok, errors = SlideValidator.validate_slide(1, d)
        self.assertFalse(ok)
        self.assertIn('prerequisites', errors)

    def test_slide1_prerequisites_exactly_3_chars_passes(self):
        d = _slide1_valid()
        d['prerequisites'] = 'abc'
        ok, errors = SlideValidator.validate_slide(1, d)
        self.assertTrue(ok, f"3-char prerequisites should pass; errors: {errors}")

    def test_slide1_prerequisites_whitespace_only_fails(self):
        d = _slide1_valid()
        d['prerequisites'] = '   '  # whitespace only
        ok, errors = SlideValidator.validate_slide(1, d)
        self.assertFalse(ok)
        self.assertIn('prerequisites', errors)

    # --- Slide 1: negative numeric fields ---

    def test_slide1_negative_hours_lecture_fails(self):
        d = _slide1_valid()
        d['hours_lecture'] = '-1'
        ok, errors = SlideValidator.validate_slide(1, d)
        self.assertFalse(ok)
        self.assertIn('hours_lecture', errors)

    def test_slide1_negative_hours_practical_fails(self):
        d = _slide1_valid()
        d['hours_practical'] = '-0.5'
        ok, errors = SlideValidator.validate_slide(1, d)
        self.assertFalse(ok)
        self.assertIn('hours_practical', errors)

    def test_slide1_zero_hours_passes(self):
        """Zero is a valid value (lecture hours can be 0 for practical-only subjects)."""
        d = _slide1_valid()
        d['hours_lecture'] = '0'
        ok, errors = SlideValidator.validate_slide(1, d)
        # hours_lecture passes validator (0 >= 0), but hours_lecture is still
        # in 'required' — and '0' is truthy as a non-empty string.
        self.assertTrue(ok, f"Zero hours_lecture should pass; errors: {errors}")

    # --- Slide 2: empty objectives list ---

    def test_slide2_empty_objectives_list_fails(self):
        ok, errors = SlideValidator.validate_slide(2, {'objectives': []})
        self.assertFalse(ok)
        self.assertIn('objectives', errors)

    def test_slide2_single_objective_passes(self):
        ok, errors = SlideValidator.validate_slide(2, {'objectives': ['Learn X']})
        self.assertTrue(ok)

    # --- Slide 3: weightage validation ---

    def test_slide3_weightage_exactly_100_passes(self):
        d = {'theory_units': [{'weightage': 100}]}
        ok, errors = SlideValidator.validate_slide(3, d)
        self.assertTrue(ok, f"100% weightage should pass; errors: {errors}")

    def test_slide3_weightage_99_fails(self):
        d = {'theory_units': [{'weightage': 99}]}
        ok, errors = SlideValidator.validate_slide(3, d)
        self.assertFalse(ok)
        self.assertIn('theory_weightage', errors)

    def test_slide3_weightage_101_fails(self):
        d = {'theory_units': [{'weightage': 101}]}
        ok, errors = SlideValidator.validate_slide(3, d)
        self.assertFalse(ok)
        self.assertIn('theory_weightage', errors)

    def test_slide3_weightage_80_fails(self):
        d = {'theory_units': [{'weightage': 50}, {'weightage': 30}]}
        ok, errors = SlideValidator.validate_slide(3, d)
        self.assertFalse(ok)
        self.assertIn('theory_weightage', errors)

    def test_slide3_three_units_summing_to_100_passes(self):
        d = {'theory_units': [
            {'weightage': 33}, {'weightage': 33}, {'weightage': 34}
        ]}
        ok, errors = SlideValidator.validate_slide(3, d)
        self.assertTrue(ok, f"33+33+34=100 should pass; errors: {errors}")

    def test_slide3_empty_units_list_fails_both_checks(self):
        d = {'theory_units': []}
        ok, errors = SlideValidator.validate_slide(3, d)
        self.assertFalse(ok)
        # Empty list fails the 'theory_units' required validator
        self.assertIn('theory_units', errors)

    # --- Slide 6: empty course outcomes ---

    def test_slide6_empty_outcomes_list_fails(self):
        d = {'course_outcomes': [], 'outcome_mappings': [{'co': 'CO1'}]}
        ok, errors = SlideValidator.validate_slide(6, d)
        self.assertFalse(ok)
        self.assertIn('course_outcomes', errors)

    # --- Slide 7: empty resources list ---

    def test_slide7_empty_resources_list_fails(self):
        ok, errors = SlideValidator.validate_slide(7, {'learning_resources': []})
        self.assertFalse(ok)
        self.assertIn('learning_resources', errors)

    # --- Slide 8: rationale too short ---

    def test_slide8_rationale_too_short_fails(self):
        d = _slide8_valid()
        d['rationale'] = 'Short'   # < 10 chars
        ok, errors = SlideValidator.validate_slide(8, d)
        self.assertFalse(ok)
        self.assertIn('rationale', errors)

    def test_slide8_rationale_exactly_10_chars_passes(self):
        d = _slide8_valid()
        d['rationale'] = '1234567890'  # exactly 10 chars
        ok, errors = SlideValidator.validate_slide(8, d)
        self.assertTrue(ok, f"10-char rationale should pass; errors: {errors}")

    def test_slide8_rationale_whitespace_padding_fails(self):
        """Stripped length must be >= 10; padding spaces don't count."""
        d = _slide8_valid()
        d['rationale'] = '   Short   '   # stripped = 'Short' (5 chars)
        ok, errors = SlideValidator.validate_slide(8, d)
        self.assertFalse(ok)
        self.assertIn('rationale', errors)


# ---------------------------------------------------------------------------
# Test class 4: return type contracts
# ---------------------------------------------------------------------------

class ValidateSlideReturnTypeTests(SimpleTestCase):
    """validate_slide() always returns (bool, dict)."""

    def test_returns_tuple_of_two(self):
        result = SlideValidator.validate_slide(1, _slide1_valid())
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_first_element_is_bool(self):
        ok, _ = SlideValidator.validate_slide(1, _slide1_valid())
        self.assertIsInstance(ok, bool)

    def test_second_element_is_dict(self):
        _, errors = SlideValidator.validate_slide(1, _slide1_valid())
        self.assertIsInstance(errors, dict)

    def test_errors_empty_on_valid_data(self):
        _, errors = SlideValidator.validate_slide(1, _slide1_valid())
        self.assertEqual(errors, {})

    def test_errors_non_empty_on_invalid_data(self):
        _, errors = SlideValidator.validate_slide(2, {})
        self.assertGreater(len(errors), 0)


# ---------------------------------------------------------------------------
# Test class 5: validate_up_to_slide()
# ---------------------------------------------------------------------------

class ValidateUpToSlideTests(SimpleTestCase):
    """Progressive multi-slide validation."""

    @staticmethod
    def _full_valid():
        d = {}
        d.update(_slide1_valid())
        d.update(_slide2_valid())
        d.update(_slide3_valid())
        d.update(_slide5_valid())
        d.update(_slide6_valid())
        d.update(_slide7_valid())
        d.update(_slide8_valid())
        return d

    def test_returns_three_tuple(self):
        result = SlideValidator.validate_up_to_slide(1, _slide1_valid())
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 3)

    def test_first_element_is_bool(self):
        ok, _, __ = SlideValidator.validate_up_to_slide(1, _slide1_valid())
        self.assertIsInstance(ok, bool)

    def test_second_element_is_dict(self):
        _, errors, __ = SlideValidator.validate_up_to_slide(1, _slide1_valid())
        self.assertIsInstance(errors, dict)

    def test_third_element_is_none_or_int(self):
        _, __, first = SlideValidator.validate_up_to_slide(1, _slide1_valid())
        self.assertTrue(first is None or isinstance(first, int))

    def test_valid_single_slide(self):
        ok, errors, first = SlideValidator.validate_up_to_slide(1, _slide1_valid())
        self.assertTrue(ok)
        self.assertEqual(errors, {})
        self.assertIsNone(first)

    def test_invalid_single_slide(self):
        ok, errors, first = SlideValidator.validate_up_to_slide(1, {})
        self.assertFalse(ok)
        self.assertIn('slide_1', errors)
        self.assertEqual(first, 1)

    def test_all_slides_valid(self):
        ok, errors, first = SlideValidator.validate_up_to_slide(8, self._full_valid())
        self.assertTrue(ok, f"All slides with full valid data; errors: {errors}")
        self.assertEqual(errors, {})
        self.assertIsNone(first)

    def test_slide4_skipped_from_required_check(self):
        """Even without slide 4 data, validate_up_to_slide(4) passes (slide 4 optional)."""
        d = {}
        d.update(_slide1_valid())
        d.update(_slide2_valid())
        d.update(_slide3_valid())
        ok, errors, _ = SlideValidator.validate_up_to_slide(4, d)
        self.assertTrue(ok, f"Slides 1-4 with slide 4 optional; errors: {errors}")

    def test_first_invalid_slide_reported_correctly(self):
        """first_invalid_slide is the lowest failing slide number."""
        d = {}
        # Only slide 3 data provided — slides 1 & 2 will fail
        d.update(_slide3_valid())
        _, _, first = SlideValidator.validate_up_to_slide(3, d)
        self.assertEqual(first, 1, "Slide 1 should be the first invalid slide")

    def test_later_slide_errors_do_not_affect_earlier_first_invalid(self):
        """first_invalid_slide stays at slide 1 even if slide 2 also fails."""
        ok, errors, first = SlideValidator.validate_up_to_slide(2, {})
        self.assertFalse(ok)
        self.assertEqual(first, 1)

    def test_errors_keyed_by_slide_number(self):
        """all_errors keys are in the form 'slide_N'."""
        _, errors, _ = SlideValidator.validate_up_to_slide(2, {})
        for key in errors:
            self.assertTrue(key.startswith('slide_'), f"Unexpected key: {key}")

    def test_validates_only_up_to_given_slide(self):
        """Slides beyond current_slide are NOT validated."""
        # Slide 1 valid, slides 2-8 missing — but only validate up to 1
        ok, errors, _ = SlideValidator.validate_up_to_slide(1, _slide1_valid())
        self.assertTrue(ok)
        # Slide 2 errors should not appear
        self.assertNotIn('slide_2', errors)

    def test_validate_up_to_0_always_valid(self):
        """Validating up to slide 0 means no slides checked — always passes."""
        ok, errors, first = SlideValidator.validate_up_to_slide(0, {})
        self.assertTrue(ok)
        self.assertEqual(errors, {})
        self.assertIsNone(first)


# ---------------------------------------------------------------------------
# Test class 6: SLIDES structure integrity
# ---------------------------------------------------------------------------

class SlidesConfigTests(SimpleTestCase):
    """Sanity checks on the SLIDES class variable."""

    def test_slides_covers_1_to_8(self):
        for i in range(1, 9):
            self.assertIn(i, SlideValidator.SLIDES, f"Slide {i} missing from SLIDES")

    def test_each_slide_has_required_key(self):
        for num, cfg in SlideValidator.SLIDES.items():
            self.assertIn('required', cfg, f"Slide {num} missing 'required'")

    def test_each_slide_has_validators_key(self):
        for num, cfg in SlideValidator.SLIDES.items():
            self.assertIn('validators', cfg, f"Slide {num} missing 'validators'")

    def test_required_is_list(self):
        for num, cfg in SlideValidator.SLIDES.items():
            self.assertIsInstance(cfg['required'], list, f"Slide {num} 'required' is not a list")

    def test_validators_is_dict(self):
        for num, cfg in SlideValidator.SLIDES.items():
            self.assertIsInstance(cfg['validators'], dict, f"Slide {num} 'validators' is not a dict")

    def test_slide4_has_no_required_fields(self):
        self.assertEqual(SlideValidator.SLIDES[4]['required'], [])

    def test_slide4_has_no_validators(self):
        self.assertEqual(SlideValidator.SLIDES[4]['validators'], {})


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
    print("Task 6.4: SlideValidator Unit Tests")
    print("  6.1  SLIDES configuration structure")
    print("  6.2  validate_slide() per-slide with valid/invalid/missing data")
    print("  6.3  validate_up_to_slide() progressive validation")
    print("=" * 80)
    print()

    success = run_tests()

    print()
    print("=" * 80)
    print("OK: All tests passed!" if success else "FAIL: Some tests failed!")
    print("=" * 80)

    sys.exit(0 if success else 1)
