"""
Audit Logger Component for the GSFC Syllabus Management System.

Provides a centralised, stateless service (AuditLogger) for creating
SyllabusEditLog entries.  All methods are static so the class can be used
without instantiation from anywhere in the codebase.

Tasks implemented here
----------------------
3.1  AuditLogger class + get_client_ip()          Requirements: 1.5
3.2  log_change()                                 Requirements: 1.1, 1.2, 1.4, 8.1-8.3
3.3  log_bulk_change()                            Requirements: 8.4, 8.5
"""

import logging

from .models import SyllabusEditLog

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Centralised service for recording syllabus audit-log entries.

    All methods are @staticmethod so the class is used without instantiation:

        AuditLogger.log_change(syllabus, user, ip, ...)
        AuditLogger.log_bulk_change(syllabus, user, ip, ...)
    """

    # ------------------------------------------------------------------
    # Task 3.1 – get_client_ip()
    # ------------------------------------------------------------------

    @staticmethod
    def get_client_ip(request):
        """
        Extract the real client IP address from a Django request object.

        Handles the common reverse-proxy case where the actual IP is in the
        X-Forwarded-For header.  When multiple proxies are chained the header
        contains a comma-separated list; only the *first* (leftmost) address
        is used as that is the originating client.

        Args:
            request: Django HttpRequest object.

        Returns:
            str | None: Dotted-decimal IP address string, or None if it
                        cannot be determined.

        Requirements: 1.5
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Take only the first address (client), strip whitespace
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip or None

    # ------------------------------------------------------------------
    # Task 3.2 – log_change()
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_value(val):
        """
        Convert a Python value to a JSON-serialisable form suitable for
        storage in SyllabusEditLog.old_value / new_value (JSONField).

        Supported types are passed through unchanged; everything else is
        coerced to its string representation so nothing is silently lost.

        Args:
            val: Any Python value.

        Returns:
            JSON-serialisable scalar, list, dict, or None.
        """
        if val is None:
            return None
        if isinstance(val, bool):          # bool check MUST come before int
            return val
        if isinstance(val, (int, float, str)):
            return val
        if isinstance(val, (list, dict)):
            return val
        # Fallback: coerce to string (covers date, datetime, Decimal, etc.)
        return str(val)

    @staticmethod
    def _build_description(action_type, field_name, model_name,
                           old_value, new_value):
        """
        Generate a concise human-readable sentence describing the change.

        Args:
            action_type (str): One of 'create', 'update', 'status_change',
                               'bulk_update'.
            field_name (str): Name of the field that changed.
            model_name (str): Django model class name.
            old_value: Previous field value (already serialised).
            new_value: New field value (already serialised).

        Returns:
            str: Human-readable description.
        """
        if action_type == 'create':
            return f"Created {model_name} record"
        if action_type == 'status_change':
            return (
                f"Status changed from '{old_value}' to '{new_value}'"
                f" on {model_name}"
            )
        if action_type == 'bulk_update':
            return f"Bulk update on {model_name}"
        # Default: update
        if field_name:
            return f"Updated '{field_name}' on {model_name}"
        return f"Updated {model_name} record"

    @staticmethod
    def log_change(
        syllabus,
        user,
        ip_address,
        model_name,
        record_id,
        field_name,
        old_value,
        new_value,
        action_type='update',
    ):
        """
        Create a single-field audit-log entry for a syllabus modification.

        Serialisation of old_value / new_value is handled internally so
        callers can pass raw Python objects (strings, numbers, booleans,
        lists, dicts, dates, …).

        Audit-log failures are intentionally non-fatal: any exception is
        caught, logged to the Django error log, and swallowed so that the
        main save operation is never blocked (Requirement 1.1, 1.2).

        Args:
            syllabus:    Syllabus instance the change belongs to
                         (may be None when the syllabus itself is being
                         created for the first time).
            user:        Django User instance (or None for system actions).
            ip_address:  String IP address from AuditLogger.get_client_ip().
            model_name:  Class name of the model being changed, e.g.
                         'Syllabus', 'CourseObjective'.
            record_id:   Primary key of the record being changed (int | None).
            field_name:  Name of the field that changed (empty string for
                         whole-record create/delete actions).
            old_value:   Value before the change (any serialisable type).
            new_value:   Value after the change (any serialisable type).
            action_type: One of 'create', 'update', 'status_change',
                         'bulk_update'.  Defaults to 'update'.

        Returns:
            SyllabusEditLog | None: The created log entry, or None if an
                                    error occurred.

        Requirements: 1.1, 1.2, 1.4, 8.1, 8.2, 8.3
        """
        try:
            serialised_old = AuditLogger._serialize_value(old_value)
            serialised_new = AuditLogger._serialize_value(new_value)

            description = AuditLogger._build_description(
                action_type, field_name, model_name,
                serialised_old, serialised_new
            )

            return SyllabusEditLog.objects.create(
                syllabus=syllabus,
                user=user,
                ip_address=ip_address,
                action_type=action_type,
                model_name=model_name,
                record_id=record_id,
                field_name=field_name or '',
                old_value=serialised_old,
                new_value=serialised_new,
                description=description,
            )
        except Exception as exc:
            # Audit failures must never block the main save operation.
            logger.error(
                "AuditLogger.log_change failed: %s | syllabus=%s "
                "model=%s record_id=%s field=%s",
                exc, syllabus, model_name, record_id, field_name,
                exc_info=True,
            )
            return None

    # ------------------------------------------------------------------
    # Task 3.3 – log_bulk_change()
    # ------------------------------------------------------------------

    @staticmethod
    def log_bulk_change(syllabus, user, ip_address, model_name, changes):
        """
        Create a single audit-log entry that summarises a bulk operation,
        e.g. "delete all course objectives" or "replace all theory units".

        The full list of affected changes is stored as a JSON array in
        old_value so the exact set of affected records is preserved.

        Each item in ``changes`` is expected to be a dict with at least:
            - 'action'    (str)  : 'create' | 'update' | 'delete'
            - 'record_id' (int)  : PK of the affected record (may be None)
            - 'data'      (dict) : Field-level snapshot of the affected record

        Audit failures are non-fatal (same policy as log_change).

        Args:
            syllabus:   Syllabus instance (may be None).
            user:       Django User instance (or None).
            ip_address: Client IP string.
            model_name: Class name of the model being bulk-changed.
            changes:    List[dict] – one entry per affected record.

        Returns:
            SyllabusEditLog | None: The created log entry, or None on error.

        Requirements: 8.4, 8.5
        """
        try:
            count = len(changes) if changes else 0
            description = (
                f"Bulk operation on {model_name}: {count} item(s) affected"
            )

            return SyllabusEditLog.objects.create(
                syllabus=syllabus,
                user=user,
                ip_address=ip_address,
                action_type='bulk_update',
                model_name=model_name,
                record_id=None,
                field_name='',
                old_value=changes,   # full list stored for auditability
                new_value=None,
                description=description,
            )
        except Exception as exc:
            logger.error(
                "AuditLogger.log_bulk_change failed: %s | syllabus=%s "
                "model=%s count=%s",
                exc, syllabus, model_name, len(changes) if changes else 0,
                exc_info=True,
            )
            return None
