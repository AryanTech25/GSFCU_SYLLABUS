from django.core.management.base import BaseCommand
from adminpanel.models import Subject, Faculty

class Command(BaseCommand):
    help = 'Fixes Subject hierarchy (School, Program, Branch) based on assigned Faculty'

    def handle(self, *args, **options):
        subjects = Subject.objects.all()
        updated_count = 0
        skipped_count = 0

        self.stdout.write("Starting Subject hierarchy fix...")

        for sub in subjects:
            # If already set, skip (or optionally overwrite? strict fix implies we trust current, but user said "existing in DB created BEFORE migration", so they are likely NULL)
            if sub.school and sub.program and sub.branch:
                continue

            # Find a faculty member assigned to this subject
            # We try to find one with valid hierarchy
            faculty = sub.faculties.filter(school__isnull=False, program__isnull=False, branch__isnull=False).first()
            
            if faculty:
                sub.school = faculty.school
                sub.program = faculty.program
                sub.branch = faculty.branch
                sub.save()
                updated_count += 1
                self.stdout.write(f"Updated: {sub.course_name} -> {sub.school.code} / {sub.program.name} / {sub.branch.name}")
            else:
                # If no faculty or faculty has incomplete data, we can't infer.
                # Try finding ANY faculty
                faculty_any = sub.faculties.first()
                if faculty_any:
                     # Partial update if possible
                    if faculty_any.school: sub.school = faculty_any.school
                    if faculty_any.program: sub.program = faculty_any.program
                    if faculty_any.branch: sub.branch = faculty_any.branch
                    sub.save()
                    updated_count += 1
                    self.stdout.write(f"Partially Updated: {sub.course_name} (based on {faculty_any.full_name})")
                else:
                    skipped_count += 1
                    self.stdout.write(self.style.WARNING(f"Skipped: {sub.course_name} (No faculty assigned)"))

        self.stdout.write(self.style.SUCCESS(f"Done. Updated: {updated_count}, Skipped: {skipped_count}"))
