"""
Slide Validator Component for the GSFC Syllabus Management System.

Implements progressive validation: only slides that the faculty member has
already visited/submitted are validated.  Future slides are intentionally
skipped so incomplete drafts can be saved at any stage.

Tasks implemented here
----------------------
6.1  SlideValidator class + SLIDES config     Requirements: 4.1, 4.4
6.2  validate_slide()                         Requirements: 4.1, 4.3, 5.2
6.3  validate_up_to_slide()                   Requirements: 4.1, 4.2
"""


class SlideValidator:
    """
    Validates syllabus multi-step form data progressively by slide.

    Each slide has a set of *required* field names and an optional dict of
    field-level *validators* (callables that accept the field value and return
    True when valid).

    Usage::

        ok, errors = SlideValidator.validate_slide(1, form_data)
        ok, all_errors, first_bad = SlideValidator.validate_up_to_slide(3, form_data)
    """

    # ------------------------------------------------------------------
    # Task 6.1 – SLIDES configuration
    # ------------------------------------------------------------------

    #: Slide definitions.  Keys are slide numbers (1-8).
    #: Each value is a dict with:
    #:   'required'   – list of field names that must be present and truthy.
    #:   'validators' – dict mapping field name → callable(value) → bool.
    #:                  A validator is only called when its key IS present in data.
    #:                  Returning False or raising an exception is treated as invalid.
    SLIDES = {
        1: {
            # Basic Information slide
            'required': [
                'hours_lecture', 'hours_practical', 'hours_tutorial',
                'credit_lecture', 'credit_practical', 'credit_tutorial',
                'prerequisites', 'category', 'focus', 'course_focus',
            ],
            'validators': {
                # prerequisites must be at least 3 meaningful characters
                'prerequisites': lambda v: len(str(v).strip()) >= 3,
                # numeric hour/credit fields must be >= 0
                'hours_lecture':    lambda v: float(v) >= 0,
                'hours_practical':  lambda v: float(v) >= 0,
                'hours_tutorial':   lambda v: float(v) >= 0,
                'credit_lecture':   lambda v: float(v) >= 0,
                'credit_practical': lambda v: float(v) >= 0,
                'credit_tutorial':  lambda v: float(v) >= 0,
            },
        },
        2: {
            # Course Objectives slide
            'required': ['objectives'],
            'validators': {
                # At least one objective must be provided
                'objectives': lambda objs: len(objs) > 0,
            },
        },
        3: {
            # Theory Units slide
            'required': ['theory_units'],
            'validators': {
                # At least one unit
                'theory_units': lambda units: len(units) > 0,
                # Weightages must sum to exactly 100 % (within 0.1 % tolerance)
                'theory_weightage': lambda units: (
                    abs(sum(float(u.get('weightage', 0)) for u in units) - 100) < 0.1
                ),
            },
        },
        4: {
            # Practicals slide – entirely optional
            'required': [],
            'validators': {},
        },
        5: {
            # Evaluation Scheme slide
            'required': ['evaluation'],
            'validators': {},
        },
        6: {
            # Course Outcomes & CO-PO Mapping slide
            'required': ['course_outcomes', 'outcome_mappings'],
            'validators': {
                # At least one course outcome required
                'course_outcomes': lambda cos: len(cos) > 0,
            },
        },
        7: {
            # Learning Resources slide
            'required': ['learning_resources'],
            'validators': {
                # At least one learning resource required
                'learning_resources': lambda res: len(res) > 0,
            },
        },
        8: {
            # Rationale & Approval slide
            'required': ['rationale', 'approval_date'],
            'validators': {
                # Rationale must be a substantive sentence (>= 10 chars)
                'rationale': lambda v: len(str(v).strip()) >= 10,
            },
        },
    }

    # ------------------------------------------------------------------
    # Task 6.2 – validate_slide()
    # ------------------------------------------------------------------

    @classmethod
    def validate_slide(cls, slide_number, data):
        """
        Validate the form data for a single slide.

        Unknown slide numbers (outside 1–8) are considered trivially valid
        so callers never need to guard against out-of-range slide numbers.

        Required-field check
        --------------------
        A field fails the required check if it is absent from ``data`` *or* if
        its value is falsy (None, empty string, empty list, 0-length sequence,
        etc.).  Note that the integer ``0`` is falsy in Python; numeric fields
        that are legitimately zero should be passed as the *string* ``'0'`` or
        included in the data dict under a different key.

        Custom validator check
        ----------------------
        A custom validator is invoked only when its key IS present in ``data``.
        If it returns ``False`` OR raises any exception, an error is recorded.

        Special case – ``theory_weightage``
        ------------------------------------
        The weightage validator on slide 3 is keyed as ``'theory_weightage'``
        but reads its data from ``data['theory_units']``.  It is therefore
        called whenever ``'theory_units'`` is present in data.  The validator
        callable receives the ``theory_units`` list directly.

        Args:
            slide_number (int): Slide to validate (1–8).
            data (dict):        Form data dict.  Values may be any type that
                                matches what the validator expects (strings for
                                text fields, lists for multi-value fields, etc.).

        Returns:
            tuple[bool, dict]:  ``(is_valid, errors)`` where ``errors`` maps
                                field names to human-readable error messages.

        Requirements: 4.1, 4.3, 5.2
        """
        if slide_number not in cls.SLIDES:
            return True, {}

        config = cls.SLIDES[slide_number]
        errors = {}

        # --- Required-field presence check ---
        for field in config['required']:
            if field not in data or not data[field]:
                label = field.replace('_', ' ').title()
                errors[field] = f"{label} is required"

        # --- Custom validators ---
        for field, validator in config['validators'].items():
            # The weightage validator reads theory_units; skip if not present.
            if field == 'theory_weightage':
                source = data.get('theory_units')
                if source is None:
                    continue
                value = source
            else:
                if field not in data:
                    continue
                value = data[field]

            try:
                if not validator(value):
                    label = field.replace('_', ' ').title()
                    errors[field] = f"Invalid value for {label}"
            except Exception as exc:
                label = field.replace('_', ' ').title()
                errors[field] = f"Validation error: {exc}"

        return len(errors) == 0, errors

    # ------------------------------------------------------------------
    # Task 6.3 – validate_up_to_slide()
    # ------------------------------------------------------------------

    @classmethod
    def validate_up_to_slide(cls, current_slide, data):
        """
        Validate all slides from 1 up to and including ``current_slide``.

        This implements the progressive-validation contract: slides the
        faculty hasn't reached yet are left unchecked so drafts can be saved
        at any stage.

        Args:
            current_slide (int): The highest slide that should be validated.
                                 Slides > current_slide are skipped.
            data (dict):         Form data dict (same as validate_slide).

        Returns:
            tuple[bool, dict, int | None]:
                - ``is_valid`` (bool): True only if ALL validated slides pass.
                - ``all_errors`` (dict): Keyed by ``'slide_N'``; value is the
                  errors dict returned by validate_slide for that slide.
                - ``first_invalid_slide`` (int | None): The lowest slide number
                  that has at least one error, or None if all slides are valid.

        Requirements: 4.1, 4.2
        """
        all_errors = {}
        first_invalid = None

        for slide_num in range(1, current_slide + 1):
            is_valid, slide_errors = cls.validate_slide(slide_num, data)
            if not is_valid:
                all_errors[f'slide_{slide_num}'] = slide_errors
                if first_invalid is None:
                    first_invalid = slide_num

        return len(all_errors) == 0, all_errors, first_invalid
