"""
Access Controller Component for the GSFC Syllabus Audit Log system.

Controls which SyllabusEditLog entries a given user is allowed to see.

Role logic
----------
- **Admin / staff**: sees every log entry across all syllabi.
- **Faculty**: sees only logs belonging to syllabi whose subject is in
  their assigned subject list (Faculty.subjects M2M).
- **Anyone else**: sees nothing (empty QuerySet).

Tasks implemented here
----------------------
7.1  AuditLogAccessController class + get_logs_for_user()   Requirements: 2.1, 3.1, 3.3
7.2  can_view_log()                                         Requirements: 3.3
"""

import logging

from .models import SyllabusEditLog

logger = logging.getLogger(__name__)


class AuditLogAccessController:
    """
    Stateless service for role-based filtering of SyllabusEditLog entries.

    All methods are @staticmethod — use them without instantiating the class:

        logs = AuditLogAccessController.get_logs_for_user(request.user, filters)
        allowed = AuditLogAccessController.can_view_log(request.user, log_entry)
    """

    # ------------------------------------------------------------------
    # Task 7.1 – get_logs_for_user()
    # ------------------------------------------------------------------

    @staticmethod
    def get_logs_for_user(user, filters=None):
        """
        Return the SyllabusEditLog QuerySet that ``user`` is authorised to see.

        **Admin / staff** → all log entries.
        **Faculty**       → only entries whose ``syllabus.subject`` is in
                            the faculty's assigned subject list.
        **Others**        → empty QuerySet.

        Optional ``filters`` dict may contain any combination of:

        =========  ================================================
        Key        Meaning
        =========  ================================================
        subject_id Filter to a single Subject PK.
        date_from  Include only entries with ``timestamp >= date_from``.
        date_to    Include only entries with ``timestamp <= date_to``.
        user_id    Filter to a specific user PK (admin-only; ignored
                   silently for non-admin callers).
        =========  ================================================

        All filters are applied after the role-based baseline query so that
        faculty members cannot bypass access control by supplying filters.

        The returned QuerySet is ordered by ``-timestamp`` (newest first) and
        uses ``select_related('syllabus__subject', 'user')`` for efficient
        template rendering without N+1 queries.

        Args:
            user:    A Django ``User`` instance (authenticated).
            filters: ``dict | None`` — optional filter parameters.

        Returns:
            QuerySet[SyllabusEditLog]: Filtered, ordered, with select_related.

        Requirements: 2.1, 3.1, 3.3
        """
        filters = filters or {}

        # --- Role-based baseline ---
        if user.is_staff:
            logs = SyllabusEditLog.objects.all()
        else:
            try:
                from adminpanel.models import Faculty
                faculty = Faculty.objects.get(user=user)
                subject_ids = faculty.subjects.values_list('id', flat=True)
                logs = SyllabusEditLog.objects.filter(
                    syllabus__subject_id__in=subject_ids
                )
            except Exception:
                # User is not a faculty member (or Faculty lookup failed)
                logs = SyllabusEditLog.objects.none()

        # --- Optional filters ---
        subject_id = filters.get('subject_id')
        if subject_id:
            logs = logs.filter(syllabus__subject_id=subject_id)

        date_from = filters.get('date_from')
        if date_from:
            logs = logs.filter(timestamp__gte=date_from)

        date_to = filters.get('date_to')
        if date_to:
            logs = logs.filter(timestamp__lte=date_to)

        # user_id filter is admin-only; silently ignored for non-admin users
        if user.is_staff:
            user_id = filters.get('user_id')
            if user_id:
                logs = logs.filter(user_id=user_id)

        return logs.select_related(
            'syllabus__subject', 'user', 'user__faculty'
        ).order_by('-timestamp')


    # ------------------------------------------------------------------
    # Task 7.2 – can_view_log()
    # ------------------------------------------------------------------

    @staticmethod
    def can_view_log(user, log_entry):
        """
        Check whether ``user`` is permitted to view a specific log entry.

        - Admin / staff → always allowed.
        - Faculty       → allowed only if the log's syllabus subject is
                          in their assigned subjects list.
        - Others        → denied.

        Args:
            user:      A Django ``User`` instance.
            log_entry: A ``SyllabusEditLog`` instance.

        Returns:
            bool: ``True`` if access is granted, ``False`` otherwise.

        Requirements: 3.3
        """
        if user.is_staff:
            return True

        try:
            from adminpanel.models import Faculty
            faculty = Faculty.objects.get(user=user)

            # A log entry whose syllabus has been deleted (null) cannot be
            # attributed to any subject — deny access for non-admins.
            if log_entry.syllabus is None:
                return False

            subject = log_entry.syllabus.subject
            return faculty.subjects.filter(pk=subject.pk).exists()

        except Exception:
            return False
