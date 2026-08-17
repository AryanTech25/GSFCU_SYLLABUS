"""
Django signal handlers for automatic audit logging of all syllabus modifications.

Design principles
-----------------
- Audit logging is *non-fatal*: every handler wraps its work in try/except.
- Old values are captured in pre_save via instance._pre_save_snapshot.
- Child model signals (CourseObjective, TheoryUnit, etc.) are suppressed when
  the view performs its own bulk delete-and-recreate cycle.  The view takes
  responsibility for writing a single consolidated diff log entry instead.
  Suppression is controlled via the thread-local flag
  ``audit_suppress.active`` set by the ``suppress_child_signals`` context
  manager exported from this module.
- IP address is unavailable in signals; the view layer passes it explicitly
  when calling AuditLogger directly.

Tasks: 4.1, 4.2, 4.3   Requirements: 1.1-1.3, 8.1-8.5
"""

import logging
import threading

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .audit_logger import AuditLogger

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thread-local suppression flag
# ---------------------------------------------------------------------------

_suppress = threading.local()
_tl_user = threading.local()


def is_suppressed():
    """Return True when child-model signals should be silenced."""
    return getattr(_suppress, 'active', False)


def set_current_user(user):
    """
    Store the Django User making the current request in thread-local storage
    so signal handlers can record the correct faculty without a request object.
    Call this in the view immediately before syllabus.save().
    """
    _tl_user.value = user


def get_current_user():
    """Return the thread-local user, or None if not set."""
    return getattr(_tl_user, 'value', None)


class suppress_child_signals:
    """
    Context manager used by the view's bulk delete-and-recreate cycle.

    with suppress_child_signals():
        syllabus.objectives.all().delete()
        CourseObjective.objects.bulk_create(objs)
        # … no per-row signal noise logged
    """
    def __enter__(self):
        _suppress.active = True
        return self

    def __exit__(self, *args):
        _suppress.active = False


# ---------------------------------------------------------------------------
# Tracked fields on the Syllabus model
# ---------------------------------------------------------------------------

_SYLLABUS_TRACKED_FIELDS = [
    'hours_lecture', 'hours_practical', 'hours_tutorial',
    'credit_lecture', 'credit_practical', 'credit_tutorial',
    'prerequisites', 'category', 'focus', 'course_focus',
    'approval_date', 'rationale', 'status', 'last_completed_slide',
]


def _get_syllabus_from_instance(instance):
    return getattr(instance, 'syllabus', None)


# ---------------------------------------------------------------------------
# Task 4.1 – Syllabus model signal handlers
# ---------------------------------------------------------------------------

@receiver(pre_save, sender='adminpanel.Syllabus')
def capture_syllabus_pre_save(sender, instance, **kwargs):
    """Snapshot current DB state before the save so post_save can diff."""
    try:
        if instance.pk:
            db_instance = sender.objects.get(pk=instance.pk)
            instance._pre_save_snapshot = {
                field: getattr(db_instance, field)
                for field in _SYLLABUS_TRACKED_FIELDS
            }
        else:
            instance._pre_save_snapshot = {}
    except Exception as exc:
        logger.error(
            "capture_syllabus_pre_save: could not snapshot syllabus pk=%s: %s",
            instance.pk, exc, exc_info=True,
        )
        instance._pre_save_snapshot = {}


@receiver(post_save, sender='adminpanel.Syllabus')
def log_syllabus_change(sender, instance, created, **kwargs):
    """
    On creation: one 'create' entry.
    On update: one 'update' entry per field that actually changed.
    Child-model noise is handled separately via suppress_child_signals.
    """
    try:
        snapshot = getattr(instance, '_pre_save_snapshot', {})

        _user = get_current_user()

        if created:
            AuditLogger.log_change(
                syllabus=instance,
                user=_user,
                ip_address=None,
                model_name='Syllabus',
                record_id=instance.pk,
                field_name='',
                old_value=None,
                new_value=None,
                action_type='create',
            )
            return

        for field in _SYLLABUS_TRACKED_FIELDS:
            old_val = snapshot.get(field)
            new_val = getattr(instance, field, None)
            # Serialize both sides before comparing so type differences (e.g.
            # int vs str, datetime.date vs "YYYY-MM-DD") never cause false
            # positives — only genuine value changes produce a log entry.
            old_ser = AuditLogger._serialize_value(old_val)
            new_ser = AuditLogger._serialize_value(new_val)
            if old_ser == new_ser:
                continue
            action = 'status_change' if field == 'status' else 'update'
            AuditLogger.log_change(
                syllabus=instance,
                user=_user,
                ip_address=None,
                model_name='Syllabus',
                record_id=instance.pk,
                field_name=field,
                old_value=old_val,
                new_value=new_val,
                action_type=action,
            )

    except Exception as exc:
        logger.error(
            "log_syllabus_change: audit logging failed for syllabus pk=%s: %s",
            instance.pk, exc, exc_info=True,
        )


# ---------------------------------------------------------------------------
# Task 4.2 – Signal handlers for related (child) models
# ---------------------------------------------------------------------------

def _log_related_save(instance, model_name, created):
    if is_suppressed():
        return
    try:
        syllabus = _get_syllabus_from_instance(instance)
        AuditLogger.log_change(
            syllabus=syllabus,
            user=get_current_user(),
            ip_address=None,
            model_name=model_name,
            record_id=instance.pk,
            field_name='',
            old_value=None,
            new_value=None,
            action_type='create' if created else 'update',
        )
    except Exception as exc:
        logger.error(
            "_log_related_save: audit logging failed for %s pk=%s: %s",
            model_name, instance.pk, exc, exc_info=True,
        )


def _log_related_delete(instance, model_name):
    if is_suppressed():
        return
    try:
        syllabus = _get_syllabus_from_instance(instance)
        AuditLogger.log_bulk_change(
            syllabus=syllabus,
            user=get_current_user(),
            ip_address=None,
            model_name=model_name,
            changes=[{'action': 'delete', 'record_id': instance.pk, 'data': {'pk': instance.pk}}],
        )
    except Exception as exc:
        logger.error(
            "_log_related_delete: audit logging failed for %s pk=%s: %s",
            model_name, instance.pk, exc, exc_info=True,
        )


# --- CourseObjective ---

@receiver(post_save, sender='adminpanel.CourseObjective')
def log_course_objective_save(sender, instance, created, **kwargs):
    _log_related_save(instance, 'CourseObjective', created)


@receiver(post_delete, sender='adminpanel.CourseObjective')
def log_course_objective_delete(sender, instance, **kwargs):
    _log_related_delete(instance, 'CourseObjective')


# --- TheoryUnit ---

@receiver(post_save, sender='adminpanel.TheoryUnit')
def log_theory_unit_save(sender, instance, created, **kwargs):
    _log_related_save(instance, 'TheoryUnit', created)


@receiver(post_delete, sender='adminpanel.TheoryUnit')
def log_theory_unit_delete(sender, instance, **kwargs):
    _log_related_delete(instance, 'TheoryUnit')


# --- Practical ---

@receiver(post_save, sender='adminpanel.Practical')
def log_practical_save(sender, instance, created, **kwargs):
    _log_related_save(instance, 'Practical', created)


@receiver(post_delete, sender='adminpanel.Practical')
def log_practical_delete(sender, instance, **kwargs):
    _log_related_delete(instance, 'Practical')


# --- EvaluationScheme ---

@receiver(post_save, sender='adminpanel.EvaluationScheme')
def log_evaluation_scheme_save(sender, instance, created, **kwargs):
    _log_related_save(instance, 'EvaluationScheme', created)


@receiver(post_delete, sender='adminpanel.EvaluationScheme')
def log_evaluation_scheme_delete(sender, instance, **kwargs):
    _log_related_delete(instance, 'EvaluationScheme')


# --- CourseOutcome ---

@receiver(post_save, sender='adminpanel.CourseOutcome')
def log_course_outcome_save(sender, instance, created, **kwargs):
    _log_related_save(instance, 'CourseOutcome', created)


@receiver(post_delete, sender='adminpanel.CourseOutcome')
def log_course_outcome_delete(sender, instance, **kwargs):
    _log_related_delete(instance, 'CourseOutcome')


# --- OutcomeMapping ---

@receiver(post_save, sender='adminpanel.OutcomeMapping')
def log_outcome_mapping_save(sender, instance, created, **kwargs):
    if is_suppressed():
        return
    try:
        co = getattr(instance, 'course_outcome', None)
        syllabus = getattr(co, 'syllabus', None) if co else None
        AuditLogger.log_change(
            syllabus=syllabus,
            user=None,
            ip_address=None,
            model_name='OutcomeMapping',
            record_id=instance.pk,
            field_name='',
            old_value=None,
            new_value=None,
            action_type='create' if created else 'update',
        )
    except Exception as exc:
        logger.error("log_outcome_mapping_save: audit failed pk=%s: %s", instance.pk, exc, exc_info=True)


@receiver(post_delete, sender='adminpanel.OutcomeMapping')
def log_outcome_mapping_delete(sender, instance, **kwargs):
    if is_suppressed():
        return
    try:
        co = getattr(instance, 'course_outcome', None)
        syllabus = getattr(co, 'syllabus', None) if co else None
        AuditLogger.log_bulk_change(
            syllabus=syllabus,
            user=None,
            ip_address=None,
            model_name='OutcomeMapping',
            changes=[{'action': 'delete', 'record_id': instance.pk, 'data': {'pk': instance.pk}}],
        )
    except Exception as exc:
        logger.error("log_outcome_mapping_delete: audit failed pk=%s: %s", instance.pk, exc, exc_info=True)


# --- LearningResource ---

@receiver(post_save, sender='adminpanel.LearningResource')
def log_learning_resource_save(sender, instance, created, **kwargs):
    _log_related_save(instance, 'LearningResource', created)


@receiver(post_delete, sender='adminpanel.LearningResource')
def log_learning_resource_delete(sender, instance, **kwargs):
    _log_related_delete(instance, 'LearningResource')
