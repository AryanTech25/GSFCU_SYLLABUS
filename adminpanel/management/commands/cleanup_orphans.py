from django.core.management.base import BaseCommand
from django.db import transaction
from adminpanel.models import (
    Syllabus,
    CourseObjective,
    TheoryUnit,
    Practical,
    CourseOutcome,
    OutcomeMapping,
    LearningResource
)

class Command(BaseCommand):
    help = 'Cleans up orphan records in syllabus child tables where syllabus is NULL.'

    def handle(self, *args, **options):
        self.stdout.write("Starting cleanup of orphan records...")

        # Models that have a direct 'syllabus' FK
        child_models = [
            (CourseObjective, 'CourseObjective'),
            (TheoryUnit, 'TheoryUnit'),
            (Practical, 'Practical'),
            (LearningResource, 'LearningResource'),
            (CourseOutcome, 'CourseOutcome'),
        ]

        with transaction.atomic():
            for model, name in child_models:
                # Find records where syllabus is NULL
                orphans = model.objects.filter(syllabus__isnull=True)
                count = orphans.count()
                if count > 0:
                    self.stdout.write(f"Found {count} orphan {name} records. Deleting...")
                    orphans.delete()
                else:
                    self.stdout.write(f"No orphan {name} records found.")
            
            # OutcomeMapping depends on CourseOutcome
            # If CourseOutcomes were deleted/nullified, mappings might be orphan.
            # OutcomeMapping has course_outcome = OneToOneField(CourseOutcome, CASCADE)
            # If CourseOutcome is deleted, Mapping is deleted.
            # Check if any Mapping has course_outcome=None (shouldn't happen with CASCADE but good to check)
            orphans_mapping = OutcomeMapping.objects.filter(course_outcome__isnull=True)
            count_mapping = orphans_mapping.count()
            if count_mapping > 0:
                self.stdout.write(f"Found {count_mapping} orphan OutcomeMapping records. Deleting...")
                orphans_mapping.delete()
            else:
                self.stdout.write("No orphan OutcomeMapping records found.")

            self.stdout.write(self.style.SUCCESS('Cleanup complete successfully.'))
