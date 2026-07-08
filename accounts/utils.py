from adminpanel.models import Syllabus, CourseObjective, TheoryUnit, Practical, CourseOutcome, LearningResource
from django.db import transaction
from django.db.models import Prefetch

def load_full_syllabus(syllabus_id):
    """
    Centralized loader for Syllabus to ensure all related data is fetched efficiently.
    Used for Edit, Preview, and PDF generation.
    """
    if not syllabus_id:
        return None
        
    try:
        return (
            Syllabus.objects
            .select_related("subject", "faculty", "evaluation_scheme", "faculty__school", "faculty__program", "faculty__branch")
            .prefetch_related(
                Prefetch("objectives", queryset=CourseObjective.objects.order_by('id')),
                Prefetch("theory_units", queryset=TheoryUnit.objects.order_by('id')),
                Prefetch("practicals", queryset=Practical.objects.order_by('id')),
                Prefetch("course_outcomes", queryset=CourseOutcome.objects.order_by('id')),
                "course_outcomes__mapping",
                Prefetch("learning_resources", queryset=LearningResource.objects.order_by('id'))
            )
            .get(id=syllabus_id)
        )
    except Syllabus.DoesNotExist:
        return None
