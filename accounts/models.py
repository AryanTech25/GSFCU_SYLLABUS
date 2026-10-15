from django.db import models
from django.contrib.auth.models import User


class SyllabusEditLog(models.Model):
    """
    Immutable audit log for tracking all syllabus modifications.
    Records timestamp, user identity, IP address, and field-level changes.
    """
    
    ACTION_TYPE_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('status_change', 'Status Change'),
        ('bulk_update', 'Bulk Update'),
    ]
    
    # Core identifiers
    syllabus = models.ForeignKey(
        'adminpanel.Syllabus',
        on_delete=models.SET_NULL,
        null=True,
        related_name='edit_logs',
        help_text='The syllabus being modified (preserved even if syllabus is deleted)'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='syllabus_edits',
        help_text='User who made the change (preserved even if user is deleted)'
    )
    
    # Audit metadata
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text='When the change was made'
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text='IP address of the user making the change'
    )
    
    # Change tracking
    action_type = models.CharField(
        max_length=20,
        choices=ACTION_TYPE_CHOICES,
        help_text='Type of action performed'
    )
    model_name = models.CharField(
        max_length=100,
        help_text='Name of the model being changed (e.g., Syllabus, CourseObjective)'
    )
    record_id = models.IntegerField(
        null=True,
        blank=True,
        help_text='ID of the specific record that was modified'
    )
    field_name = models.CharField(
        max_length=100,
        blank=True,
        help_text='Name of the field that was changed'
    )
    old_value = models.JSONField(
        null=True,
        blank=True,
        help_text='Previous value before the change'
    )
    new_value = models.JSONField(
        null=True,
        blank=True,
        help_text='New value after the change'
    )
    
    # Additional context
    description = models.TextField(
        blank=True,
        help_text='Human-readable description of the change'
    )
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['syllabus', '-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['timestamp']),
        ]
        permissions = [
            ('view_all_logs', 'Can view all audit logs'),
        ]
        verbose_name = 'Syllabus Edit Log'
        verbose_name_plural = 'Syllabus Edit Logs'
    
    def save(self, *args, **kwargs):
        """
        Custom save method to prevent updates to existing log entries.
        Audit logs must be immutable to maintain integrity.
        """
        if self.pk is not None:
            raise ValueError("SyllabusEditLog entries cannot be modified after creation")
        super().save(*args, **kwargs)
    
    def __str__(self):
        user_name = self.user.username if self.user else 'Unknown User'
        return f"{self.action_type} by {user_name} on {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
