import os
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
from .models import Subject, Syllabus, SemesterReference, SemesterSubject, Faculty

def invalidate_and_cleanup(semester):
    """
    Invalidates the SemesterReference for a given semester and deletes the physical PDF.
    """
    refs = SemesterReference.objects.filter(semester=semester)
    for ref in refs:
        if ref.pdf_file:
            # Delete physical file
            if os.path.isfile(ref.pdf_file.path):
                os.remove(ref.pdf_file.path)
            # Clear file field and mark invalid
            ref.pdf_file = None
            ref.is_valid = False
            ref.save()

@receiver(post_delete, sender=Subject)
@receiver(post_delete, sender=Syllabus)
@receiver(post_delete, sender=Faculty)
def handle_master_deletion(sender, instance, **kwargs):
    """
    When master data is deleted, invalidate all PDFs that might contain it.
    """
    if sender == Subject:
        # Invalidate all structures containing this subject
        sem_subs = SemesterSubject.objects.filter(subject=instance)
    elif sender == Syllabus:
        sem_subs = SemesterSubject.objects.filter(subject=instance.subject)
    elif sender == Faculty:
        # If a faculty is deleted, their subjects' syllabi might be affected
        # (Though signals usually cascade, we target the Semester PDF explicitly here)
        sem_subs = SemesterSubject.objects.filter(subject__faculties=instance)
    
    related_semesters = sem_subs.values_list('semester', flat=True).distinct()
    for sem_id in related_semesters:
        invalidate_and_cleanup(sem_id)

@receiver(post_delete, sender=SemesterSubject)
def handle_structure_change(sender, instance, **kwargs):
    """
    When a subject is removed from a semester structure, invalidate the final PDF.
    """
    invalidate_and_cleanup(instance.semester_id)
