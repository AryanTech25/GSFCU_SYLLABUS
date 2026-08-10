from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator


class School(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.code} - {self.name}"


class Program(models.Model):
    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name='programs'
    )
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name} ({self.school.code})"


class Branch(models.Model):
    program = models.ForeignKey(
        Program,
        on_delete=models.CASCADE,
        related_name='branches'
    )
    name = models.CharField(max_length=150)

    def __str__(self):
        return f"{self.name} - {self.program.name}"


class Faculty(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    full_name = models.CharField(max_length=150)
    faculty_id = models.CharField(max_length=50, unique=True)
    email = models.EmailField()
    mobile = models.CharField(max_length=15)
    semester = models.CharField(max_length=20)

    school = models.ForeignKey(School, on_delete=models.SET_NULL, null=True)
    program = models.ForeignKey(Program, on_delete=models.SET_NULL, null=True)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True)
    academic_year = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.full_name} ({self.faculty_id})"


class Subject(models.Model):
    course_name = models.CharField(max_length=150)
    course_code = models.CharField(max_length=50)
    semester = models.CharField(max_length=20, blank=True, null=True)
    academic_year = models.CharField(
        max_length=20,
        default="2025-26",
        help_text="Format: YYYY-YY (e.g. 2025-26)"
    )
    description = models.TextField(blank=True)
    
    school = models.ForeignKey(School, on_delete=models.CASCADE, null=True, blank=True)
    program = models.ForeignKey(Program, on_delete=models.CASCADE, null=True, blank=True)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, null=True, blank=True)

    # --- MASTER DATA: EXPICIT OWNERSHIP RULES ---
    # Subjects are global master data.
    # They must NOT be auto-deleted when:
    # - Faculty is deleted
    # - User is deleted
    # - Syllabus is deleted
    # Deletion Policy: Only Admin can delete subjects explicitly.
    faculties = models.ManyToManyField(
        Faculty,
        related_name='subjects',
        blank=True,
        through='SubjectFaculty'
    )

    @property
    def safe_syllabus(self):
        try:
            return self.syllabus
        except:
            return None

    def __str__(self):
        return f"{self.course_name} ({self.course_code})"


class SubjectFaculty(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('subject', 'faculty')

    def __str__(self):
        return f"{self.subject.course_name} - {self.faculty.full_name}"


# --- Syllabus Builder Models ---

class Syllabus(models.Model):
    CATEGORY_CHOICES = [
        ('HS', 'HS'),
        ('BS', 'BS'),
        ('ES', 'ES'),
        ('PC', 'PC'),
        ('PE', 'PE'),
        ('OE', 'OE'),
        ('IP', 'IP'),
        ('NC', 'NC'),
    ]
    FOCUS_CHOICES = [
        ('HS', 'Humanities and Social Sciences (HS)'),
        ('BS', 'Basic Sciences (BS)'),
        ('ES', 'Engineering Sciences (ES)'),
        ('PC', 'Professional Subjects – Core (PC)'),
        ('PE', 'Professional Subjects – Electives (PE)'),
        ('OE', 'Open Subjects – Electives (OE)'),
        ('IP', 'Project Work / Seminar / Internship'),
        ('NC', 'Mandatory Courses – Non Credit'),
        ('VAC', 'Value Added Courses'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('final', 'Final Submission'),
    ]
    COURSE_FOCUS_CHOICES = [
        ('Employability', 'Employability'),
        ('Entrepreneurship', 'Entrepreneurship'),
        ('Skill Development', 'Skill Development'),
    ]

    subject = models.OneToOneField(Subject, on_delete=models.CASCADE, related_name='syllabus')
    faculty = models.ForeignKey(Faculty, on_delete=models.SET_NULL, null=True, related_name='syllabi')
    
    hours_lecture = models.PositiveIntegerField(default=0)
    hours_practical = models.PositiveIntegerField(default=0)
    hours_tutorial = models.PositiveIntegerField(default=0)
    
    credit_lecture = models.PositiveIntegerField(default=0)
    credit_practical = models.PositiveIntegerField(default=0)
    credit_tutorial = models.PositiveIntegerField(default=0)
    
    prerequisites = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='HS')
    focus = models.CharField(max_length=150, choices=FOCUS_CHOICES, default='HS', verbose_name="Course Category Title")
    course_focus = models.CharField(max_length=50, choices=COURSE_FOCUS_CHOICES, default='Employability')
    
    approval_date = models.DateField(null=True, blank=True)
    rationale = models.TextField(blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    last_completed_slide = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # PDF Output
    pdf_file = models.FileField(upload_to='', null=True, blank=True)
    pdf_generated_at = models.DateTimeField(null=True, blank=True)

    def is_complete(self):
        """
        Determine if all required sections are filled for PDF generation.
        Returns: (is_complete: bool, missing_fields: list)
        
        Validates:
        - Requirements 5.1: Check all required fields are filled
        - Requirements 5.2: Validate required section completeness
        - Requirements 5.3: Ensure CO-PO mappings exist for each course outcome
        - Requirements 6.5: Ensure theory unit weightage sums to 100%
        """
        missing = []
        
        # Check basic fields (contact hours - at least one must be non-zero)
        if not self.hours_lecture and not self.hours_practical:
            missing.append('Contact Hours')
        
        # Check credits (at least one must be non-zero)
        if not self.credit_lecture and not self.credit_practical:
            missing.append('Credits')
        
        # Check prerequisites (at least 3 characters)
        if not self.prerequisites or len(self.prerequisites.strip()) < 3:
            missing.append('Prerequisites')
        
        # Check category
        if not self.category:
            missing.append('Category')
        
        # Check rationale
        if not self.rationale:
            missing.append('Rationale')
        
        # Check approval date
        if not self.approval_date:
            missing.append('Approval Date')
        
        # Check course objectives (at least 1)
        if not self.objectives.exists():
            missing.append('Course Objectives')
        
        # Check theory units
        units = self.theory_units.all()
        if not units.exists():
            missing.append('Theory Units')
        else:
            # Check theory unit weightage sums to 100% (within 0.1% tolerance)
            total_weight = sum(u.weightage for u in units)
            if abs(total_weight - 100) > 0.1:
                missing.append(f'Theory Unit Weightage (current: {total_weight}%, required: 100%)')
        
        # Check evaluation scheme
        if not hasattr(self, 'evaluation_scheme'):
            missing.append('Evaluation Scheme')
        
        # Check course outcomes (at least 1)
        outcomes = self.course_outcomes.all()
        if not outcomes.exists():
            missing.append('Course Outcomes')
        else:
            # Check CO-PO mappings exist for each course outcome
            for outcome in outcomes:
                if not hasattr(outcome, 'mapping'):
                    missing.append(f'CO-PO Mapping for {outcome.code}')
                    break
        
        # Check learning resources (at least 1)
        if not self.learning_resources.exists():
            missing.append('Learning Resources')
        
        is_complete = len(missing) == 0
        return is_complete, missing

    def get_completion_percentage(self):
        """
        Calculate the completion percentage of this syllabus based on required sections.
        Reuses is_complete() to determine how many required section checks are missing,
        then returns an integer in the range 0-100.

        The total number of distinct required-section checks matches the maximum number
        of entries that is_complete() can add to its `missing` list (11 checks):
          1. Contact Hours
          2. Credits
          3. Prerequisites
          4. Category
          5. Rationale
          6. Approval Date
          7. Course Objectives
          8. Theory Units (existence)
          9. Theory Unit Weightage (sums to 100%)
         10. Evaluation Scheme
         11. Course Outcomes (existence)
         12. CO-PO Mapping (at least one outcome missing mapping)
         13. Learning Resources

        Returns:
            int: Completion percentage (0-100)

        Requirements: 7.5
        """
        TOTAL_CHECKS = 13  # Maximum distinct entries that is_complete() can add to missing

        _, missing = self.is_complete()
        completed = TOTAL_CHECKS - len(missing)
        # Clamp to [0, TOTAL_CHECKS] in case of edge cases, then scale to 100
        completed = max(0, min(completed, TOTAL_CHECKS))
        return round((completed / TOTAL_CHECKS) * 100)

    def __str__(self):
        return f"Syllabus for {self.subject.course_name}"


class CourseObjective(models.Model):
    BLOOMS_DOMAIN_CHOICES = [
        ('Cognitive', 'Cognitive'),
        ('Affective', 'Affective'),
        ('Psychomotor', 'Psychomotor'),
    ]

    syllabus = models.ForeignKey(Syllabus, on_delete=models.CASCADE, related_name='objectives')
    text = models.TextField()
    blooms_domain = models.CharField(
        max_length=20, choices=BLOOMS_DOMAIN_CHOICES,
        blank=True, null=True,
        verbose_name="Bloom's Taxonomy Domain"
    )
    blooms_subdomain = models.CharField(
        max_length=60,
        blank=True, null=True,
        verbose_name="Bloom's Taxonomy Subdomain"
    )

    def __str__(self):
        return f"Objective: {self.text[:50]}"


class TheoryUnit(models.Model):
    syllabus = models.ForeignKey(Syllabus, on_delete=models.CASCADE, related_name='theory_units')
    title = models.CharField(max_length=200)
    description = models.TextField()
    weightage = models.PositiveIntegerField(help_text="Percentage weightage")
    hours = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.title} ({self.weightage}%)"


class Practical(models.Model):
    syllabus = models.ForeignKey(Syllabus, on_delete=models.CASCADE, related_name='practicals')
    description = models.TextField()
    weightage = models.PositiveIntegerField(help_text="Percentage weightage")
    hours = models.PositiveIntegerField()

    def __str__(self):
        return f"Practical: {self.description[:50]}..."


class EvaluationScheme(models.Model):
    syllabus = models.OneToOneField(Syllabus, on_delete=models.CASCADE, related_name='evaluation_scheme')
    
    mid_sem = models.PositiveIntegerField(default=0)
    end_sem = models.PositiveIntegerField(default=0)
    
    # CEC Components
    cec_attendance = models.PositiveIntegerField(default=0)
    cec_mcq = models.PositiveIntegerField(default=0)
    cec_assignment = models.PositiveIntegerField(default=0)
    
    # Practical Components
    prac_attendance = models.PositiveIntegerField(default=0)
    prac_exam = models.PositiveIntegerField(default=0)
    prac_viva = models.PositiveIntegerField(default=0)
    prac_journal = models.PositiveIntegerField(default=0)
    prac_discipline = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Evaluation Scheme for {self.syllabus.subject.course_name}"


class CourseOutcome(models.Model):
    syllabus = models.ForeignKey(Syllabus, on_delete=models.CASCADE, related_name='course_outcomes')
    code = models.CharField(max_length=20)  # CO1, CO2
    description = models.TextField()

    def __str__(self):
        return f"{self.code}: {self.description[:50]}"


class OutcomeMapping(models.Model):
    PO_CHOICES = [(i, str(i)) for i in range(4)]  # 0, 1, 2, 3

    course_outcome = models.OneToOneField(CourseOutcome, on_delete=models.CASCADE, related_name='mapping')
    
    # PO1 to PO12
    po1 = models.PositiveIntegerField(default=0, choices=PO_CHOICES)
    po2 = models.PositiveIntegerField(default=0, choices=PO_CHOICES)
    po3 = models.PositiveIntegerField(default=0, choices=PO_CHOICES)
    po4 = models.PositiveIntegerField(default=0, choices=PO_CHOICES)
    po5 = models.PositiveIntegerField(default=0, choices=PO_CHOICES)
    po6 = models.PositiveIntegerField(default=0, choices=PO_CHOICES)
    po7 = models.PositiveIntegerField(default=0, choices=PO_CHOICES)
    po8 = models.PositiveIntegerField(default=0, choices=PO_CHOICES)
    po9 = models.PositiveIntegerField(default=0, choices=PO_CHOICES)
    po10 = models.PositiveIntegerField(default=0, choices=PO_CHOICES)
    po11 = models.PositiveIntegerField(default=0, choices=PO_CHOICES)
    po12 = models.PositiveIntegerField(default=0, choices=PO_CHOICES)
    
    # PSO1, PSO2
    pso1 = models.PositiveIntegerField(default=0, choices=PO_CHOICES)
    pso2 = models.PositiveIntegerField(default=0, choices=PO_CHOICES)

    def __str__(self):
        return f"Mapping for {self.course_outcome.code}"


class LearningResource(models.Model):
    syllabus = models.ForeignKey(Syllabus, on_delete=models.CASCADE, related_name="learning_resources")
    category = models.CharField(max_length=100)
    content = models.TextField()

    def __str__(self):
        return f"{self.category} - {self.syllabus}"


class Semester(models.Model):
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='semesters')
    semester_number = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('program', 'semester_number')

    def __str__(self):
        return f"{self.program.name} - {self.semester_number}"


class SemesterSubject(models.Model):
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='semester_subjects')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='semester_allocations')
    sequence = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('semester', 'subject')
        ordering = ['sequence']

    def __str__(self):
        return f"{self.subject.course_name} in Sequence {self.sequence}"


class SemesterFacultyAccess(models.Model):
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='faculty_access')
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name='semester_access')

    def __str__(self):
        return f"{self.faculty.full_name} -> {self.semester}"


class SemesterReference(models.Model):
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='generated_pdfs')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, null=True, blank=True)
    pdf_file = models.FileField(upload_to='semester_pdfs/')
    created_at = models.DateTimeField(auto_now=True)
    is_valid = models.BooleanField(default=True)  # Tracks if source PDFs still exist
    is_deleted = models.BooleanField(default=False)

    class Meta:
        unique_together = ('semester', 'branch')

    def __str__(self):
        return f"PDF for {self.semester} - {self.branch.name if self.branch else 'Common'}"



# --- Program Outcomes ---

class ProgramOutcome(models.Model):
    program = models.ForeignKey(
        Program,
        on_delete=models.CASCADE,
        related_name='program_outcomes'
    )
    code = models.CharField(max_length=20, help_text="e.g. PO1, PO2, ...")
    description = models.TextField(help_text="Outcome description")
    order = models.PositiveIntegerField(default=0, help_text="Display order")

    class Meta:
        ordering = ['order', 'id']
        unique_together = ('program', 'code')

    def __str__(self):
        return f"{self.code} – {self.program.name}"


# --- Program Specific Outcomes ---

class ProgramSpecificOutcome(models.Model):
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='program_specific_outcomes'
    )
    code = models.CharField(max_length=20, help_text="e.g. PSO1, PSO2, ...")
    description = models.TextField(help_text="Outcome description")
    order = models.PositiveIntegerField(default=0, help_text="Display order")

    class Meta:
        ordering = ['order', 'id']
        unique_together = ('branch', 'code')

    def __str__(self):
        return f"{self.code} – {self.branch.name}"


# --- Program Educational Objectives ---

class ProgramEducationalObjective(models.Model):
    program = models.ForeignKey(
        Program,
        on_delete=models.CASCADE,
        related_name='program_educational_objectives'
    )
    code = models.CharField(max_length=20, help_text="e.g. PEO1, PEO2, ...")
    description = models.TextField(help_text="Objective description")
    order = models.PositiveIntegerField(default=0, help_text="Display order")

    class Meta:
        ordering = ['order', 'id']
        unique_together = ('program', 'code')

    def __str__(self):
        return f"{self.code} – {self.program.name}"


# --- SIGNALS FOR DYNAMIC INVALIDATION ---
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
import os

@receiver(post_delete, sender=Syllabus)
@receiver(post_delete, sender=Subject)
@receiver(post_delete, sender=SemesterSubject)
def invalidate_semester_pdf(sender, instance, **kwargs):
    """
    CRITICAL: Permanently delete physical semester PDFs and database records 
    if any component (Subject, Syllabus, or allocation) is deleted.
    """
    if sender == Subject:
        # If subject is deleted, any semester reference containing it must be deleted
        refs = SemesterReference.objects.filter(semester__semester_subjects__subject=instance)
    elif sender == Syllabus:
        # If syllabus is deleted, the merged PDF containing it is stale
        refs = SemesterReference.objects.filter(semester__semester_subjects__subject=instance.subject)
    elif sender == SemesterSubject:
        # If allocation changes, the merged PDF is stale
        refs = SemesterReference.objects.filter(semester=instance.semester)
    else:
        return

    for ref in refs:
        # Delete physical file
        if ref.pdf_file:
            try:
                if os.path.exists(ref.pdf_file.path):
                    os.remove(ref.pdf_file.path)
            except:
                pass
            ref.pdf_file.delete(save=False)
        
        # Delete the database record (Permanent deletion as requested)
        ref.delete()

