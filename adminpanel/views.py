import os
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.http import JsonResponse, FileResponse
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.contrib import messages
from .models import School, Program, Branch, Faculty, Subject, SubjectFaculty, Syllabus, Semester, SemesterSubject, ProgramOutcome, ProgramSpecificOutcome, ProgramEducationalObjective
from django.db.models import Q
from django.db import transaction
from django.utils import timezone
from datetime import datetime

def is_admin(user):
    return user.is_authenticated and user.is_staff

@never_cache
@user_passes_test(is_admin, login_url='/login/')
def admin_dashboard(request):
    faculties = Faculty.objects.select_related('school', 'program', 'branch').prefetch_related('subjects__syllabus').all()
    schools = School.objects.all()
    
    # Search functionality
    query = request.GET.get('q')
    if query:
        faculties = faculties.filter(
            Q(full_name__icontains=query) |
            Q(faculty_id__icontains=query) |
            Q(subjects__course_name__icontains=query)
        ).distinct()

    return render(request, 'adminpanel/dashboard.html', {
        'faculties': faculties,
        'schools': schools,
        'query': query
    })



@never_cache
@user_passes_test(is_admin, login_url='/login/')
@require_POST
def create_faculty(request):
    try:
        full_name = request.POST.get('full_name')
        faculty_id = request.POST.get('faculty_id')
        email = request.POST.get('email')
        mobile = request.POST.get('mobile')
        # semester = request.POST.get('semester') # Removed
        school_id = request.POST.get('school')
        # program_id = request.POST.get('program') # Removed
        # branch_id = request.POST.get('branch') # Removed
        password = request.POST.get('password')
        # academic_year = request.POST.get('academic_year') # Removed

        if User.objects.filter(username=faculty_id).exists():
            messages.error(request, f'User with ID {faculty_id} already exists.')
            return redirect('admin_dashboard')

        user = User.objects.create_user(username=faculty_id, email=email, password=password)
        user.is_staff = False
        user.save()

        Faculty.objects.create(
            user=user,
            full_name=full_name,
            faculty_id=faculty_id,
            email=email,
            mobile=mobile,
            semester="-",  # Default as field is removed from form
            school_id=school_id,
            program_id=None,  # Field removed
            branch_id=None,   # Field removed
            academic_year=None # Field removed
        )
        messages.success(request, 'Faculty created successfully.')
    except Exception as e:
        messages.error(request, f'Error creating faculty: {str(e)}')
    
    return redirect('admin_dashboard')

@never_cache
@user_passes_test(is_admin, login_url='/login/')
@require_POST
def create_subject(request):
    try:
        course_name = request.POST.get('course_name')
        course_code = request.POST.get('course_code')
        semester = request.POST.get('semester')
        description = request.POST.get('description')
        faculty_ids = request.POST.getlist('faculties')
        
        if not faculty_ids:
            messages.error(request, 'Please select at least one faculty member.')
            return redirect('admin_dashboard')
        
        # Verify faculties exist (optional but good practice)
        # faculties = Faculty.objects.filter(id__in=faculty_ids)

        school_id = request.POST.get('school')
        program_id = request.POST.get('program')
        branch_id = request.POST.get('branch')

        if not (school_id and program_id and branch_id):
            messages.error(request, 'School, Program, and Branch are required.')
            return redirect('admin_dashboard')

        academic_year = request.POST.get('academic_year')
        if not academic_year:
             messages.error(request, 'Academic Year is required.')
             return redirect('admin_dashboard')

        subject = Subject.objects.create(
            course_name=course_name,
            course_code=course_code,
            semester=semester,
            description=description,
            school_id=school_id,
            program_id=program_id,
            branch_id=branch_id,
            academic_year=academic_year
        )
        
        subject.faculties.set(faculty_ids)
        
        messages.success(request, 'Subject created successfully.')
    except Exception as e:
        messages.error(request, f'Error creating subject: {str(e)}')

    return redirect('admin_dashboard')

@never_cache
@login_required
def get_programs(request):
    school_id = request.GET.get('school_id')
    programs = list(Program.objects.filter(school_id=school_id).values('id', 'name'))
    return JsonResponse({'programs': programs})

@never_cache
@login_required
def get_branches(request):
    program_id = request.GET.get('program_id')
    branches = list(Branch.objects.filter(program_id=program_id).values('id', 'name'))
    
    # Fetch semesters for this program
    sem_objects = Semester.objects.filter(program_id=program_id)
    # Sort them numerically (since semester_number is stored as character/digit string)
    sorted_sems = sorted(sem_objects, key=lambda x: int(x.semester_number) if x.semester_number.isdigit() else 999)
    
    roman_map = {
        '1': 'Semester I',
        '2': 'Semester II',
        '3': 'Semester III',
        '4': 'Semester IV',
        '5': 'Semester V',
        '6': 'Semester VI',
        '7': 'Semester VII',
        '8': 'Semester VIII',
        '9': 'Semester IX',
        '10': 'Semester X',
    }
    semesters = []
    for sem in sorted_sems:
        num = sem.semester_number
        display = roman_map.get(num, f"Semester {num}")
        semesters.append({
            'value': display,
            'display': display
        })
        
    return JsonResponse({
        'branches': branches,
        'semesters': semesters
    })

@never_cache
@user_passes_test(is_admin, login_url='/login/')
@require_POST
def delete_faculty(request, faculty_id):
    try:
        faculty = get_object_or_404(Faculty, id=faculty_id)
        user = faculty.user
        # Deleting the user will cascade delete the faculty profile due to on_delete=CASCADE on the User OneToOneField? 
        # Actually in models.py: user = models.OneToOneField(User, on_delete=models.CASCADE)
        # So deleting User deletes Faculty. Correct.
        user.delete()
        messages.success(request, 'Faculty member deleted successfully.')
    except Exception as e:
        messages.error(request, f'Error deleting faculty: {str(e)}')
    return redirect('admin_dashboard')

@never_cache
@user_passes_test(is_admin, login_url='/login/')
def edit_faculty(request, faculty_id):
    faculty = get_object_or_404(Faculty.objects.select_related('school', 'program', 'branch'), id=faculty_id)
    schools = School.objects.all()

    semesters = [
        "Semester I", "Semester II", "Semester III", "Semester IV",
        "Semester V", "Semester VI", "Semester VII", "Semester VIII"
    ]
    
    # Pre-fetch programs and branches for the selected school/program
    programs = Program.objects.filter(school=faculty.school) if faculty.school else []
    branches = Branch.objects.filter(program=faculty.program) if faculty.program else []

    if request.method == 'POST':
        try:
            full_name = request.POST.get('full_name')
            new_faculty_id = request.POST.get('faculty_id')
            email = request.POST.get('email')
            mobile = request.POST.get('mobile')
            semester = request.POST.get('semester')
            school_id = request.POST.get('school')
            program_id = request.POST.get('program')
            branch_id = request.POST.get('branch')
            password = request.POST.get('password')
            academic_year = request.POST.get('academic_year')

            # Update User fields
            user_changed = False
            if new_faculty_id != faculty.user.username:
                if User.objects.filter(username=new_faculty_id).exists():
                    messages.error(request, f'User with ID {new_faculty_id} already exists.')
                    return render(request, 'adminpanel/edit_faculty.html', {
                        'faculty': faculty, 'schools': schools, 'programs': programs, 'branches': branches,
                        'semesters': semesters,
                        'selected_semester': faculty.semester
                    })
                faculty.user.username = new_faculty_id
                user_changed = True
            
            if email != faculty.user.email:
                faculty.user.email = email
                user_changed = True

            if password:
                faculty.user.set_password(password)
                user_changed = True
            
            if user_changed:
                faculty.user.save()

            # Update Faculty fields
            faculty.full_name = full_name
            faculty.faculty_id = new_faculty_id
            faculty.email = email
            faculty.mobile = mobile
            faculty.semester = semester
            faculty.school_id = school_id
            faculty.program_id = program_id
            faculty.branch_id = branch_id
            faculty.academic_year = academic_year
            faculty.save()

            messages.success(request, 'Faculty updated successfully.')
            return redirect('admin_dashboard')

        except Exception as e:
            messages.error(request, f'Error updating faculty: {str(e)}')
    


    assigned_subject_ids = list(
        SubjectFaculty.objects.filter(faculty=faculty).values_list('subject_id', flat=True)
    )
    assigned_subjects = Subject.objects.filter(id__in=assigned_subject_ids).order_by('course_name')
    available_subjects = Subject.objects.exclude(id__in=assigned_subject_ids).order_by('course_name')

    return render(request, 'adminpanel/edit_faculty.html', {
        'faculty': faculty,
        'schools': schools,
        'programs': programs,
        'branches': branches,
        'semesters': semesters,
        'selected_semester': faculty.semester,
        'assigned_subjects': assigned_subjects,
        'available_subjects': available_subjects,
    })


@never_cache
@login_required
@user_passes_test(is_admin, login_url='/login/')
@require_POST
def assign_subject_to_faculty(request, faculty_id):
    faculty = get_object_or_404(Faculty, id=faculty_id)
    subject_id = request.POST.get('subject_id')
    if not subject_id:
        return JsonResponse({'ok': False, 'error': 'subject_id is required.'}, status=400)
    subject = get_object_or_404(Subject, id=subject_id)
    try:
        SubjectFaculty.objects.create(faculty=faculty, subject=subject)
        return JsonResponse({
            'ok': True,
            'subject': {
                'id': subject.id,
                'course_name': subject.course_name,
                'course_code': subject.course_code,
                'semester': subject.semester or '',
            },
        })
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Subject already assigned to this faculty.'}, status=409)


@never_cache
@login_required
@user_passes_test(is_admin, login_url='/login/')
@require_POST
def unassign_subject_from_faculty(request, faculty_id):
    faculty = get_object_or_404(Faculty, id=faculty_id)
    subject_id = request.POST.get('subject_id')
    if not subject_id:
        return JsonResponse({'ok': False, 'error': 'subject_id is required.'}, status=400)
    deleted, _ = SubjectFaculty.objects.filter(faculty=faculty, subject_id=subject_id).delete()
    if deleted:
        return JsonResponse({'ok': True})
    return JsonResponse({'ok': False, 'error': 'Assignment not found.'}, status=404)


@never_cache
@login_required
@user_passes_test(is_admin, login_url='/login/')
@require_POST
def delete_syllabus(request, syllabus_id):
    syllabus = get_object_or_404(Syllabus, id=syllabus_id)
    try:
        with transaction.atomic():
            if syllabus.pdf_file:
                syllabus.pdf_file.delete(save=False)
            syllabus.delete()
        messages.success(request, 'Syllabus deleted successfully.')
    except Exception as e:
        messages.error(request, f'Error deleting syllabus: {str(e)}')
    return redirect('admin_dashboard')


@never_cache
@login_required
@user_passes_test(is_admin, login_url='/login/')
@require_POST
def delete_subject(request, subject_id):
    """
    Explicit Subject Deletion.
    - Only Admin can delete.
    - Deletes related Syllabus and physical PDFs.
    - Deletes related SemesterReference (Merged PDFs) containing this subject.
    - Deletes Subject (Master Data).
    """
    from .models import SemesterReference
    subject = get_object_or_404(Subject, id=subject_id)
    try:
        with transaction.atomic():
            # 1. Clear related Semester Merged PDFs (Signals might not fire on CASCADE)
            # Find all SemesterReferences that include this subject
            related_refs = SemesterReference.objects.filter(semester__semester_subjects__subject=subject)
            for ref in related_refs:
                if ref.pdf_file:
                    try:
                        if os.path.exists(ref.pdf_file.path):
                            os.remove(ref.pdf_file.path)
                    except:
                        pass
                    ref.pdf_file.delete(save=False)
                ref.delete()

            # 2. Check for related syllabus and delete PDF
            if hasattr(subject, 'syllabus'):
                if subject.syllabus.pdf_file:
                    try:
                        if os.path.exists(subject.syllabus.pdf_file.path):
                            os.remove(subject.syllabus.pdf_file.path)
                    except:
                        pass
                    subject.syllabus.pdf_file.delete(save=False)
                
                # Delete Syllabus
                subject.syllabus.delete()
            
            # 3. Delete Subject (Cascade will handle SemesterSubject mappings)
            subject.delete()
        
        messages.success(request, f'Subject "{subject.course_name}" and all related merged PDFs deleted permanently.')
    except Exception as e:
        messages.error(request, f'Error deleting subject: {str(e)}')
    
    return redirect('admin_dashboard')



@never_cache
@login_required
@user_passes_test(is_admin, login_url='/login/')
def manage_semester_structure(request):
    """
    NEW: Implements "unselected = all" filter logic.
    Shows aggregated semester structures across all matching filters.
    """
    schools = School.objects.all()
    
    # Define semesters: value (what's in DB) -> display (what user sees)
    # Database stores: '1', '2', '3', etc.
    # User sees: Roman numerals I, II, III, etc.
    semesters = [
        {'value': '1', 'display': 'Semester I'},
        {'value': '2', 'display': 'Semester II'},
        {'value': '3', 'display': 'Semester III'},
        {'value': '4', 'display': 'Semester IV'},
        {'value': '5', 'display': 'Semester V'},
        {'value': '6', 'display': 'Semester VI'},
        {'value': '7', 'display': 'Semester VII'},
        {'value': '8', 'display': 'Semester VIII'},
    ]
    
    # Get filter values (empty = show all)
    selected_school_id = request.GET.get('school_id') or None
    selected_program_id = request.GET.get('program_id') or None
    selected_branch_id = request.GET.get('branch_id') or None
    selected_semester = request.GET.get('semester') or None
    
    # Cascade dropdowns for UI
    programs = []
    if selected_school_id:
        programs = Program.objects.filter(school_id=selected_school_id)
    else:
        programs = Program.objects.all()
    
    branches = []
    if selected_program_id:
        branches = Branch.objects.filter(program_id=selected_program_id)
    elif selected_school_id:
        # Show all branches in selected school
        branches = Branch.objects.filter(program__school_id=selected_school_id)
    else:
        branches = Branch.objects.all()
    
    # Mapping for DB mismatch "1" <-> "Semester I"
    semester_map = {
        '1': 'Semester I',
        '2': 'Semester II',
        '3': 'Semester III',
        '4': 'Semester IV',
        '5': 'Semester V',
        '6': 'Semester VI',
        '7': 'Semester VII',
        '8': 'Semester VIII',
    }
    
    # NEW: Build query for subjects using Q objects to handle mixed types
    q_filters = Q()
    if selected_school_id:
        q_filters &= Q(school_id=selected_school_id)
    if selected_program_id:
        q_filters &= Q(program_id=selected_program_id)
    if selected_branch_id:
        q_filters &= Q(branch_id=selected_branch_id)
    if selected_semester:
        mapped_sem = semester_map.get(selected_semester)
        if mapped_sem:
            # Match either "1" OR "Semester I"
            q_filters &= (Q(semester=selected_semester) | Q(semester=mapped_sem))
        else:
            q_filters &= Q(semester=selected_semester)
    
    # Get all matching subjects sorted by course code
    all_subjects_raw = Subject.objects.filter(q_filters).select_related(
        'school', 'program', 'branch', 'syllabus'
    )
    
    # Annotate and sort: PDF available first, then unavailable
    all_subjects = []
    subjects_with_pdf = []
    subjects_without_pdf = []
    
    for subject in all_subjects_raw:
        has_pdf = (hasattr(subject, 'syllabus') and 
                  subject.syllabus and 
                  subject.syllabus.pdf_file and 
                  subject.syllabus.pdf_file.name)
        
        subject.has_pdf = has_pdf  # Add attribute
        
        if has_pdf:
            subjects_with_pdf.append(subject)
        else:
            subjects_without_pdf.append(subject)
    
    # Sort each group by course_code
    subjects_with_pdf.sort(key=lambda x: x.course_code)
    subjects_without_pdf.sort(key=lambda x: x.course_code)
    
    # Combine: PDF available first
    all_subjects = subjects_with_pdf + subjects_without_pdf
    
    # Get existing semester structures for these subjects if program + semester selected
    assigned_subjects = []
    if selected_program_id and selected_semester:
        # Get specific semester
        # Get specific semester
        # Try both numeric and string representation
        sem_obj = Semester.objects.filter(
            program_id=selected_program_id, 
            semester_number=selected_semester
        ).first()

        if not sem_obj:
             mapped = semester_map.get(selected_semester)
             if mapped:
                 sem_obj = Semester.objects.filter(
                    program_id=selected_program_id, 
                    semester_number=mapped
                ).first()
        
        if sem_obj:
            qs = SemesterSubject.objects.filter(semester=sem_obj).select_related(
                'subject', 'subject__syllabus'
            )
            if selected_branch_id:
                qs = qs.filter(subject__branch_id=selected_branch_id)
            
            # Get subjects in saved order
            all_assigned = list(qs.order_by('sequence'))
            
            # Separate by PDF availability
            assigned_with_pdf = []
            assigned_without_pdf = []
            
            for item in all_assigned:
                has_pdf = (hasattr(item.subject, 'syllabus') and 
                          item.subject.syllabus and 
                          item.subject.syllabus.pdf_file and 
                          item.subject.syllabus.pdf_file.name)
                
                item.subject.has_pdf = has_pdf  # Annotate
                
                if has_pdf:
                    assigned_with_pdf.append(item)
                else:
                    assigned_without_pdf.append(item)
            
            # Combine: PDFs first (keeping their sequence), then unavailable at end
            assigned_subjects = assigned_with_pdf + assigned_without_pdf


    # Context for template
    # Check if PDF exists for current selection
    pdf_generated = False
    if selected_program_id and selected_semester:
        try:
            # Try getting semester object with fallback logic
            sem_obj = Semester.objects.filter(program_id=selected_program_id, semester_number=selected_semester).first()
            if not sem_obj:
                 mapped = semester_map.get(selected_semester)
                 if mapped:
                     sem_obj = Semester.objects.filter(program_id=selected_program_id, semester_number=mapped).first()
            
            if not sem_obj:
                 raise Exception("Semester not found") # skip to except block

            branch_obj = Branch.objects.get(id=selected_branch_id) if selected_branch_id else None
            from .models import SemesterReference
            ref = SemesterReference.objects.filter(
                semester=sem_obj, 
                branch=branch_obj
            ).first()
            if ref and ref.pdf_file and ref.is_valid and not ref.is_deleted:
                pdf_generated = True
        except:
            pass


    return render(request, 'adminpanel/manage_semester.html', {
        'schools': schools,
        'semesters': semesters,
        'programs': programs,
        'branches': branches,
        'selected_school_id': selected_school_id,
        'selected_program_id': selected_program_id,
        'selected_branch_id': selected_branch_id,
        'selected_semester': selected_semester,
        'all_subjects': all_subjects,
        'assigned_subjects': assigned_subjects,
        'pdf_generated': pdf_generated
    })



def _get_academic_year_from_qs(qs):
    """
    Finds the first non-empty academic year from the faculties assigned to subjects in the structure.
    """
    for item in qs:
        # Check Subject academic year first (NEW PRIORITY)
        if hasattr(item.subject, 'academic_year') and item.subject.academic_year:
            return item.subject.academic_year
        
        # Fallback to Faculty academic year (deprecated but kept for safety)
        if hasattr(item.subject, 'syllabus') and item.subject.syllabus.faculty:
            if item.subject.syllabus.faculty.academic_year:
                return item.subject.syllabus.faculty.academic_year
    return "Academic Year Not Defined"


@never_cache
@login_required
@user_passes_test(is_admin, login_url='/login/')
def generate_semester_pdf(request):
    """
    Admin-only view to generate combined PDF from currently displayed subjects.
    Works with any filter combination - generates PDF for whatever is shown on screen.
    """
    selected_school_id = request.GET.get('school_id') or None
    selected_program_id = request.GET.get('program_id') or None
    selected_branch_id = request.GET.get('branch_id') or None
    selected_semester = request.GET.get('semester') or None

    try:
        import os
        from django.conf import settings
        from django.core.files import File
        from datetime import datetime
        from django.template.loader import render_to_string
        from io import BytesIO
        from xhtml2pdf import pisa
        from django.http import HttpResponse
        
    except ImportError as e:
        messages.error(request, f"Required library not available: {str(e)}")
        return redirect('manage_semester_structure')

    try:
        semester_map = {
            '1': 'Semester I', '2': 'Semester II', '3': 'Semester III', '4': 'Semester IV',
            '5': 'Semester V', '6': 'Semester VI', '7': 'Semester VII', '8': 'Semester VIII',
        }
    
        q_filters = Q()
        if selected_school_id: q_filters &= Q(school_id=selected_school_id)
        if selected_program_id: q_filters &= Q(program_id=selected_program_id)
        if selected_branch_id: q_filters &= Q(branch_id=selected_branch_id)
        if selected_semester:
             mapped_sem = semester_map.get(selected_semester)
             if mapped_sem:
                 q_filters &= (Q(semester=selected_semester) | Q(semester=mapped_sem))
             else:
                 q_filters &= Q(semester=selected_semester)

        all_subjects = Subject.objects.filter(q_filters).select_related(
            'school', 'program', 'branch', 'syllabus', 'syllabus__evaluation_scheme'
        ).order_by('course_code')
        
        if not all_subjects.exists():
            messages.warning(request, "No subjects match the current filters.")
            return redirect('manage_semester_structure')
        
        # Filter to only subjects WITH syllabuses
        subjects_with_pdfs = [
            subj for subj in all_subjects 
            if hasattr(subj, 'syllabus') and subj.syllabus and subj.syllabus.pdf_file
        ]
        
        if not subjects_with_pdfs:
            messages.error(request, "None of the displayed subjects have PDF files generated yet.")
            return redirect('manage_semester_structure')
        
        # Get metadata
        school = subjects_with_pdfs[0].school
        program = subjects_with_pdfs[0].program
        branch_name = subjects_with_pdfs[0].branch.name if subjects_with_pdfs[0].branch else "Mixed"
        semester_val = selected_semester if selected_semester else "Mixed Semesters"
        
        schools_set = set(s.school.code for s in subjects_with_pdfs)
        programs_set = set(s.program.name for s in subjects_with_pdfs)
        branches_set = set(s.branch.name if s.branch else "Common" for s in subjects_with_pdfs)
        semesters_set = set(s.semester for s in subjects_with_pdfs)
        
        school_name = school.name
        program_name = program.name
        if len(schools_set) > 1:
            school_name = "Multiple Schools"
        if len(programs_set) > 1:
            program_name = "Multiple Programs"
        if len(branches_set) > 1:
            branch_name = "Mixed Branches"
        if len(semesters_set) > 1:
            semester_val = "Mixed Semesters"
        
        academic_year = "Academic Year Not Defined"
        for subj in subjects_with_pdfs:
            if hasattr(subj, 'academic_year') and subj.academic_year:
                academic_year = subj.academic_year
                break
            if hasattr(subj, 'syllabus') and subj.syllabus.faculty:
                if subj.syllabus.faculty.academic_year:
                    academic_year = subj.syllabus.faculty.academic_year
                    break

        summary_rows = []
        evaluation_summary_rows = []
        for sequence, subject in enumerate(subjects_with_pdfs, start=1):
            syllabus = subject.syllabus
            semester_val_for_row = subject.semester if subject.semester else "Semester Not Defined"
            row = {
                'sr_no': sequence,
                'semester': str(semester_val_for_row).replace('Semester ', '').replace('Sem ', ''),
                'code': subject.course_code,
                'name': subject.course_name,
                'L': syllabus.hours_lecture,
                'P': syllabus.hours_practical,
                'T': syllabus.hours_tutorial,
                'hours_total': syllabus.hours_lecture + syllabus.hours_practical + syllabus.hours_tutorial,
                'cL': syllabus.credit_lecture,
                'cP': syllabus.credit_practical,
                'cT': syllabus.credit_tutorial,
                'credits_total': syllabus.credit_lecture + syllabus.credit_practical + syllabus.credit_tutorial
            }
            summary_rows.append(row)
            
            eval_scheme = getattr(syllabus, 'evaluation_scheme', None)
            if eval_scheme:
                theory_marks = eval_scheme.mid_sem + eval_scheme.cec_attendance + eval_scheme.cec_mcq + eval_scheme.cec_assignment + eval_scheme.end_sem
                prac_marks = eval_scheme.prac_attendance + eval_scheme.prac_exam + eval_scheme.prac_viva + eval_scheme.prac_journal + eval_scheme.prac_discipline
                eval_row = {
                    'sr_no': sequence,
                    'code': subject.course_code,
                    'name': subject.course_name,
                    'ms': eval_scheme.mid_sem,
                    'cec': eval_scheme.cec_attendance + eval_scheme.cec_mcq + eval_scheme.cec_assignment,
                    'es': eval_scheme.end_sem,
                    'theory_total': theory_marks,
                    'practical_total': prac_marks,
                    'total': theory_marks + prac_marks
                }
            else:
                eval_row = {
                    'sr_no': sequence, 'code': subject.course_code, 'name': subject.course_name,
                    'ms': '-', 'cec': '-', 'es': '-', 'theory_total': '-', 'practical_total': '-', 'total': '-'
                }
            evaluation_summary_rows.append(eval_row)

        syllabi_list = []
        for subject in subjects_with_pdfs:
            syllabus = subject.syllabus
            syllabi_list.append({
                'syllabus': syllabus,
                'total_hours': syllabus.hours_lecture + syllabus.hours_practical + syllabus.hours_tutorial,
                'total_credits': syllabus.credit_lecture + syllabus.credit_practical + syllabus.credit_tutorial,
                'semester_name': subject.semester if subject.semester else "Semester Not Defined"
            })

        logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'gsfc_logo.png')
        
        context = {
            'school_name': school_name,
            'program_name': program_name,
            'branch_name': branch_name,
            'academic_year': academic_year,
            'logo_path': logo_path,
            'generated_date': datetime.now().strftime('%B %d, %Y'),
            'summary_rows': summary_rows,
            'evaluation_summary_rows': evaluation_summary_rows,
            'syllabi_list': syllabi_list,
            'is_full_program': False
        }

        html_string = render_to_string('pdf/combined_syllabus.html', context)

        result = BytesIO()
        pdf = pisa.pisaDocument(BytesIO(html_string.encode("UTF-8")), result)
        
        if not pdf.err:
            filename_parts = []
            if selected_school_id and len(schools_set) == 1: filename_parts.append(school.code)
            if selected_program_id and len(programs_set) == 1: filename_parts.append(program.name.replace(' ', '_'))
            if selected_branch_id and len(branches_set) == 1: filename_parts.append(branch_name.replace(' ', '_'))
            if selected_semester and len(semesters_set) == 1: filename_parts.append(semester_val.replace(' ', '_'))
            
            if not filename_parts: filename_parts.append("Combined")
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename_parts.append(f"Syllabus_{timestamp}")
            filename = "_".join(filename_parts) + ".pdf"
            filename = "".join([c if c.isalnum() or c in ('_','-','.') else '_' for c in filename])

            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
            
        return HttpResponse(f"PDF Generation Error: {pdf.err}")

    except Exception as e:
        messages.error(request, f"Error generating PDF: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return redirect('manage_semester_structure')


@never_cache
@login_required
@user_passes_test(is_admin, login_url='/login/')
def preview_semester_pdf(request):
    """
    Admin-only preview of merged semester PDF.
    Does NOT save to database - temporary merge only.
    """
    school_id = request.GET.get('school_id')
    program_id = request.GET.get('program_id')
    branch_id = request.GET.get('branch_id')
    semester_val = request.GET.get('semester')

    if not (school_id and program_id and semester_val):
        messages.error(request, "Missing selection criteria.")
        return redirect('manage_semester_structure')

    try:
        from io import BytesIO
        import os
        from django.conf import settings
        from django.template.loader import render_to_string
        from xhtml2pdf import pisa
        from django.http import HttpResponse, FileResponse
        from datetime import datetime
        
    except ImportError as e:
        messages.error(request, f"Required library not available: {str(e)}")
        return redirect('manage_semester_structure')

    try:
        program = get_object_or_404(Program, id=program_id)
        school = get_object_or_404(School, id=school_id)
        
        branch_name = "Common"
        if branch_id:
            branch = get_object_or_404(Branch, id=branch_id)
            branch_name = branch.name
        
        # Fetch semester structure
        sem_obj = get_object_or_404(Semester, program_id=program_id, semester_number=semester_val)
        
        qs = SemesterSubject.objects.filter(semester=sem_obj).select_related(
            'subject', 'subject__syllabus', 'subject__syllabus__evaluation_scheme'
        ).order_by('sequence')
        
        if branch_id:
            qs = qs.filter(subject__branch_id=branch_id)
            
        if not qs.exists():
            messages.warning(request, "No subjects assigned to this semester structure.")
            base_url = reverse('manage_semester_structure')
            query = f"?school_id={school_id}&program_id={program_id}&branch_id={branch_id or ''}&semester={semester_val}"
            return redirect(base_url + query)

        # Build summary and syllabi list
        summary_rows = []
        evaluation_summary_rows = []
        syllabi_list = []
        
        for sequence, item in enumerate(qs, start=1):
            subject = item.subject
            syllabus = getattr(subject, 'syllabus', None)
            semester_val_for_row = subject.semester if subject.semester else sem_obj.semester_number
            row = {
                'sr_no': sequence,
                'semester': str(semester_val_for_row).replace('Semester ', '').replace('Sem ', ''),
                'code': subject.course_code,
                'name': subject.course_name,
            }
            if syllabus:
                row['L'] = syllabus.hours_lecture
                row['P'] = syllabus.hours_practical
                row['T'] = syllabus.hours_tutorial
                row['hours_total'] = syllabus.hours_lecture + syllabus.hours_practical + syllabus.hours_tutorial
                row['cL'] = syllabus.credit_lecture
                row['cP'] = syllabus.credit_practical
                row['cT'] = syllabus.credit_tutorial
                row['credits_total'] = syllabus.credit_lecture + syllabus.credit_practical + syllabus.credit_tutorial
                
                syllabi_list.append({
                    'syllabus': syllabus,
                    'total_hours': row['hours_total'],
                    'total_credits': row['credits_total'],
                    'semester_name': semester_val_for_row
                })
                
                eval_scheme = getattr(syllabus, 'evaluation_scheme', None)
                if eval_scheme:
                    theory_marks = eval_scheme.mid_sem + eval_scheme.cec_attendance + eval_scheme.cec_mcq + eval_scheme.cec_assignment + eval_scheme.end_sem
                    prac_marks = eval_scheme.prac_attendance + eval_scheme.prac_exam + eval_scheme.prac_viva + eval_scheme.prac_journal + eval_scheme.prac_discipline
                    eval_row = {
                        'sr_no': sequence, 'code': subject.course_code, 'name': subject.course_name,
                        'ms': eval_scheme.mid_sem, 'cec': eval_scheme.cec_attendance + eval_scheme.cec_mcq + eval_scheme.cec_assignment,
                        'es': eval_scheme.end_sem, 'theory_total': theory_marks, 'practical_total': prac_marks, 'total': theory_marks + prac_marks
                    }
                else:
                    eval_row = {'sr_no': sequence, 'code': subject.course_code, 'name': subject.course_name, 'ms': '-', 'cec': '-', 'es': '-', 'theory_total': '-', 'practical_total': '-', 'total': '-'}
            else:
                row.update({'L':'-','P':'-','T':'-','hours_total':'-','cL':'-','cP':'-','cT':'-','credits_total':'-'})
                eval_row = {'sr_no': sequence, 'code': subject.course_code, 'name': subject.course_name, 'ms': '-', 'cec': '-', 'es': '-', 'theory_total': '-', 'practical_total': '-', 'total': '-'}
            
            summary_rows.append(row)
            evaluation_summary_rows.append(eval_row)
            
        if not syllabi_list:
            messages.error(request, "No subject syllabus PDFs available to preview.")
            return redirect('manage_semester_structure')
            
        academic_year = _get_academic_year_from_qs(qs)
        
        context = {
            'school_name': school.name,
            'program_name': program.name,
            'branch_name': branch_name,
            'academic_year': academic_year,
            'logo_path': os.path.join(settings.BASE_DIR, 'static', 'images', 'gsfc_logo.png'),
            'generated_date': datetime.now().strftime('%B %d, %Y'),
            'summary_rows': summary_rows,
            'evaluation_summary_rows': evaluation_summary_rows,
            'syllabi_list': syllabi_list,
            'is_full_program': False
        }

        html_string = render_to_string('pdf/combined_syllabus.html', context)

        buffer = BytesIO()
        pdf = pisa.pisaDocument(BytesIO(html_string.encode("UTF-8")), buffer)
        
        if not pdf.err:
            buffer.seek(0)
            download_mode = request.GET.get('download') == '1'
            filename = f"{school.code}_{program.name}_{branch_name}_{semester_val}_Preview.pdf"
            filename = "".join([c if c.isalnum() or c in ('_','-','.') else '_' for c in filename])
            
            response = FileResponse(buffer, content_type='application/pdf')
            disposition = 'attachment' if download_mode else 'inline'
            response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
            return response
            
        return HttpResponse(f"PDF Generation Error: {pdf.err}")

    except Exception as e:
        messages.error(request, f"Error generating preview: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return redirect('manage_semester_structure')


@never_cache
@login_required
@user_passes_test(is_admin, login_url='/login/')
def view_semester_pdf(request):
    """
    Serves the pre-generated semester PDF from database.
    Admin-only access.
    """
    school_id = request.GET.get('school_id')
    program_id = request.GET.get('program_id')
    branch_id = request.GET.get('branch_id')
    semester_val = request.GET.get('semester')
    
    if not (school_id and program_id and semester_val):
        messages.error(request, "Invalid request parameters.")
        return redirect('manage_semester_structure')
        
    try:
        from .models import SemesterReference
        
        # Fetch semester object
        sem_obj = get_object_or_404(Semester, program_id=program_id, semester_number=semester_val)
        
        branch_obj = None
        if branch_id:
            branch_obj = get_object_or_404(Branch, id=branch_id)
        
        # Fetch semester PDF from database
        try:
            semester_ref = SemesterReference.objects.get(
                semester=sem_obj,
                branch=branch_obj
            )
            
            if semester_ref.is_deleted:
                messages.error(request, "This semester syllabus has been deleted.")
                return redirect('manage_semester_structure')
            
            if not semester_ref.is_valid:
                messages.warning(
                    request,
                    "⚠️ Semester syllabus outdated. Please regenerate."
                )
                base_url = reverse('manage_semester_structure')
                query = f"?school_id={school_id}&program_id={program_id}&branch_id={branch_id or ''}&semester={semester_val}"
                return redirect(base_url + query)
            
            if semester_ref.pdf_file:
                response = FileResponse(
                    semester_ref.pdf_file.open('rb'),
                    content_type='application/pdf'
                )
                response['Content-Disposition'] = f'inline; filename="{semester_ref.pdf_file.name.split("/")[-1]}"'
                return response
            else:
                messages.error(request, "PDF file not found in database.")
                
        except SemesterReference.DoesNotExist:
            messages.error(request, "Final PDF not generated yet. Please click 'Generate Final Semester PDF' first.")
            
    except Exception as e:
        messages.error(request, f"Error viewing PDF: {str(e)}")
    
    base_url = reverse('manage_semester_structure')
    query = f"?school_id={school_id}&program_id={program_id}&branch_id={branch_id or ''}&semester={semester_val}"
    return redirect(base_url + query)


@never_cache
@login_required
@user_passes_test(is_admin, login_url='/login/')
def download_semester_pdf(request):
    """
    Forces download of the saved semester PDF.
    Admin-only access.
    """
    school_id = request.GET.get('school_id')
    program_id = request.GET.get('program_id')
    branch_id = request.GET.get('branch_id')
    semester_val = request.GET.get('semester')
    
    if not (school_id and program_id and semester_val):
        messages.error(request, "Invalid request parameters.")
        return redirect('manage_semester_structure')
        
    try:
        from .models import SemesterReference
        
        # Fetch semester object
        sem_obj = get_object_or_404(Semester, program_id=program_id, semester_number=semester_val)
        
        branch_obj = None
        if branch_id:
            branch_obj = get_object_or_404(Branch, id=branch_id)
        
        # Fetch semester PDF from database
        try:
            semester_ref = SemesterReference.objects.get(
                semester=sem_obj,
                branch=branch_obj
            )
            
            if semester_ref.is_deleted:
                messages.error(request, "This semester syllabus has been deleted.")
                return redirect('manage_semester_structure')
            
            if not semester_ref.is_valid:
                messages.warning(
                    request,
                    "⚠️ Semester syllabus outdated. Please regenerate."
                )
                base_url = reverse('manage_semester_structure')
                query = f"?school_id={school_id}&program_id={program_id}&branch_id={branch_id or ''}&semester={semester_val}"
                return redirect(base_url + query)
            
            if semester_ref.pdf_file:
                response = FileResponse(
                    semester_ref.pdf_file.open('rb'),
                    content_type='application/pdf'
                )
                # Force download instead of inline view
                filename = semester_ref.pdf_file.name.split("/")[-1]
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response
            else:
                messages.error(request, "PDF file not found in database.")
                
        except SemesterReference.DoesNotExist:
            messages.error(request, "Final PDF not generated yet. Please generate it first.")
            
    except Exception as e:
        messages.error(request, f"Error downloading PDF: {str(e)}")
    
    base_url = reverse('manage_semester_structure')
    query = f"?school_id={school_id}&program_id={program_id}&branch_id={branch_id or ''}&semester={semester_val}"
    return redirect(base_url + query)




@never_cache
@login_required
@user_passes_test(is_admin, login_url='/login/')
@require_POST
def delete_semester_pdf(request):
    """
    Safely deletes a semester syllabus PDF and its associated structure.
    Implements soft delete as recommended for audit trail/recovery.
    """
    school_id = request.POST.get('school_id')
    program_id = request.POST.get('program_id')
    branch_id = request.POST.get('branch_id')
    semester_val = request.POST.get('semester')

    if not (program_id and semester_val):
        messages.error(request, "Missing selection criteria for deletion.")
        return redirect('manage_semester_structure')

    try:
        from .models import SemesterReference, Semester, SemesterSubject
        import logging
        logger = logging.getLogger(__name__)

        with transaction.atomic():
            # 1. Fetch Semester
            sem_obj = get_object_or_404(Semester, program_id=program_id, semester_number=semester_val)
            branch_obj = None
            if branch_id:
                branch_obj = get_object_or_404(Branch, id=branch_id)

            # 2. Get and Soft Delete the Reference (PDF Record)
            try:
                ref = SemesterReference.objects.get(semester=sem_obj, branch=branch_obj)
                
                # Mark as deleted instead of hard removing record
                ref.is_deleted = True
                ref.save()
                
                # Physical file deletion is optional if we want full recovery
                # BUT to avoid "orphan files" and satisfy Requirement 3 partially:
                # we delete the physical file but keep the record marked is_deleted.
                if ref.pdf_file:
                    ref.pdf_file.delete(save=False)
                
                logger.info(f"Soft deleted SemesterReference ID {ref.id} for {sem_obj} by {request.user.username}")

            except SemesterReference.DoesNotExist:
                messages.warning(request, "Semester PDF reference not found.")

            # 3. Handle Associated Subject References (Hard delete as requested)
            ss_qs = SemesterSubject.objects.filter(semester=sem_obj)
            if branch_id:
                ss_qs = ss_qs.filter(subject__branch_id=branch_id)
            
            count = ss_qs.count()
            ss_qs.delete()
            
            logger.info(f"Permanently deleted {count} SemesterSubject entries for {sem_obj} Branch {branch_id}")

        messages.success(request, 'Semester syllabus deleted successfully.')
    except Exception as e:
        messages.error(request, f'Error deleting semester: {str(e)}')
    
    # Redirect back with filters
    base_url = reverse('manage_semester_structure')
    query = f"?school_id={school_id or ''}&program_id={program_id or ''}&branch_id={branch_id or ''}"
    return redirect(base_url + query)


@never_cache
@login_required
@user_passes_test(is_admin, login_url='/login/')
def generate_full_program_syllabus(request):
    """
    Combines all semester PDFs for a program/branch into one final document.
    """
    school_id = request.GET.get('school_id')
    program_id = request.GET.get('program_id')
    branch_id = request.GET.get('branch_id')

    if not (school_id and program_id):
        messages.error(request, "Invalid parameters for full syllabus generation.")
        return redirect('manage_semester_structure')

    try:
        import os
        from django.conf import settings
        from .models import SemesterReference, Semester, Branch, School, Program, SemesterSubject
        from django.template.loader import render_to_string
        from xhtml2pdf import pisa
        from io import BytesIO
        from django.http import FileResponse
        from datetime import datetime

        school = get_object_or_404(School, id=school_id)
        program = get_object_or_404(Program, id=program_id)
        branch = None
        branch_name = "Common"
        if branch_id:
            branch = get_object_or_404(Branch, id=branch_id)
            branch_name = branch.name

        # 1. Fetch all Semester PDFs for this program/branch
        # Sort by semester number (Semester I, II, etc.)
        sem_refs = SemesterReference.objects.filter(
            semester__program=program,
            branch=branch,
            is_deleted=False
        ).select_related('semester').order_by('semester__semester_number')

        if not sem_refs.exists():
            messages.warning(request, "No semester PDFs found to combine.")
            return redirect(f"{reverse('manage_semester_structure')}?school_id={school_id}&program_id={program_id}&branch_id={branch_id or ''}")

        # Try to find a real AY from the first ref's subjects
        academic_year = "Not Defined"
        first_ref_sem = sem_refs.first().semester
        qs_sem = SemesterSubject.objects.filter(semester=first_ref_sem)
        if branch:
            qs_sem = qs_sem.filter(subject__branch=branch)
        if qs_sem.exists():
            academic_year = _get_academic_year_from_qs(qs_sem)

        # 2. Gather all subjects from all semesters
        summary_rows = []
        evaluation_summary_rows = []
        syllabi_list = []
        global_sequence = 1
        
        for sem_ref in sem_refs:
            sem_obj = sem_ref.semester
            qs = SemesterSubject.objects.filter(semester=sem_obj).select_related(
                'subject', 'subject__syllabus', 'subject__syllabus__evaluation_scheme'
            ).order_by('sequence')
            
            if branch_id:
                qs = qs.filter(subject__branch_id=branch_id)
                
            for item in qs:
                subject = item.subject
                syllabus = getattr(subject, 'syllabus', None)
                semester_val_for_row = subject.semester if subject.semester else sem_obj.semester_number
                row = {
                    'sr_no': global_sequence,
                    'semester': str(semester_val_for_row).replace('Semester ', '').replace('Sem ', ''),
                    'code': subject.course_code,
                    'name': subject.course_name,
                }
                
                if syllabus:
                    row['L'] = syllabus.hours_lecture
                    row['P'] = syllabus.hours_practical
                    row['T'] = syllabus.hours_tutorial
                    row['hours_total'] = syllabus.hours_lecture + syllabus.hours_practical + syllabus.hours_tutorial
                    row['cL'] = syllabus.credit_lecture
                    row['cP'] = syllabus.credit_practical
                    row['cT'] = syllabus.credit_tutorial
                    row['credits_total'] = syllabus.credit_lecture + syllabus.credit_practical + syllabus.credit_tutorial
                    
                    syllabi_list.append({
                        'syllabus': syllabus,
                        'total_hours': row['hours_total'],
                        'total_credits': row['credits_total'],
                        'semester_name': semester_val_for_row
                    })
                    
                    eval_scheme = getattr(syllabus, 'evaluation_scheme', None)
                    if eval_scheme:
                        theory_marks = eval_scheme.mid_sem + eval_scheme.cec_attendance + eval_scheme.cec_mcq + eval_scheme.cec_assignment + eval_scheme.end_sem
                        prac_marks = eval_scheme.prac_attendance + eval_scheme.prac_exam + eval_scheme.prac_viva + eval_scheme.prac_journal + eval_scheme.prac_discipline
                        eval_row = {
                            'sr_no': global_sequence, 'code': subject.course_code, 'name': subject.course_name,
                            'ms': eval_scheme.mid_sem, 'cec': eval_scheme.cec_attendance + eval_scheme.cec_mcq + eval_scheme.cec_assignment,
                            'es': eval_scheme.end_sem, 'theory_total': theory_marks, 'practical_total': prac_marks, 'total': theory_marks + prac_marks
                        }
                    else:
                        eval_row = {'sr_no': global_sequence, 'code': subject.course_code, 'name': subject.course_name, 'ms': '-', 'cec': '-', 'es': '-', 'theory_total': '-', 'practical_total': '-', 'total': '-'}
                else:
                    row.update({'L':'-','P':'-','T':'-','hours_total':'-','cL':'-','cP':'-','cT':'-','credits_total':'-'})
                    eval_row = {'sr_no': global_sequence, 'code': subject.course_code, 'name': subject.course_name, 'ms': '-', 'cec': '-', 'es': '-', 'theory_total': '-', 'practical_total': '-', 'total': '-'}
                
                summary_rows.append(row)
                evaluation_summary_rows.append(eval_row)
                global_sequence += 1

        if not syllabi_list:
            messages.warning(request, "No subjects found in the selected semesters.")
            return redirect(f"{reverse('manage_semester_structure')}?school_id={school_id}&program_id={program_id}&branch_id={branch_id or ''}")

        context = {
            'school_name': school.name,
            'program_name': program.name,
            'branch_name': branch_name,
            'academic_year': academic_year,
            'logo_path': os.path.join(settings.BASE_DIR, 'static', 'images', 'gsfc_logo.png'),
            'generated_date': datetime.now().strftime('%B %d, %Y'),
            'summary_rows': summary_rows,
            'evaluation_summary_rows': evaluation_summary_rows,
            'syllabi_list': syllabi_list,
            'is_full_program': True
        }

        html_string = render_to_string('pdf/combined_syllabus.html', context)

        # 3. Setup storage
        final_dir = os.path.join(settings.MEDIA_ROOT, 'final_syllabus')
        os.makedirs(final_dir, exist_ok=True)
        
        safe_program = "".join([c if c.isalnum() else "_" for c in program.name])
        safe_branch = "".join([c if c.isalnum() else "_" for c in branch_name])
        filename = f"{school.name[:3].upper()}_{safe_program}_{safe_branch}_FULL_SYLLABUS.pdf"
        output_path = os.path.join(final_dir, filename)

        with open(output_path, "w+b") as result_file:
            pdf = pisa.pisaDocument(BytesIO(html_string.encode("UTF-8")), result_file)
            
        if pdf.err:
            raise Exception(f"PDF Generation Error: {pdf.err}")

        # 5. Serve for Download
        response = FileResponse(open(output_path, 'rb'), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        messages.error(request, f"Error generating full syllabus: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return redirect(f"{reverse('manage_semester_structure')}?school_id={school_id}&program_id={program_id}&branch_id={branch_id or ''}")


# ─────────────────────────────────────────────────────────────────────────────
# PROGRAM OUTCOMES (PO) MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

@never_cache
@login_required
@user_passes_test(is_admin, login_url='/login/')
def manage_program_outcomes(request):
    """
    Main PO management page.
    - GET: renders page with optional school/program filter applied.
    - POST (action=add): creates a new PO for the selected program.
    """
    schools = School.objects.all().order_by('name')

    selected_school_id = request.GET.get('school_id') or request.POST.get('school_id') or ''
    selected_program_id = request.GET.get('program_id') or request.POST.get('program_id') or ''

    programs = []
    if selected_school_id:
        programs = Program.objects.filter(school_id=selected_school_id).order_by('name')

    selected_program = None
    existing_pos = []
    if selected_program_id:
        selected_program = Program.objects.filter(id=selected_program_id).first()
        if selected_program:
            existing_pos = ProgramOutcome.objects.filter(program=selected_program).order_by('order', 'id')

    # Handle ADD
    if request.method == 'POST' and request.POST.get('action') == 'add':
        code = request.POST.get('po_code', '').strip()
        description = request.POST.get('po_description', '').strip()
        order_val = request.POST.get('po_order', '0').strip() or '0'

        if not code or not description:
            messages.error(request, 'PO Code and Description are required.')
        elif not selected_program:
            messages.error(request, 'Please select a valid Program.')
        elif ProgramOutcome.objects.filter(program=selected_program, code__iexact=code).exists():
            messages.error(request, f'"{code}" already exists for this program.')
        else:
            try:
                ProgramOutcome.objects.create(
                    program=selected_program,
                    code=code,
                    description=description,
                    order=int(order_val),
                )
                messages.success(request, f'Program Outcome "{code}" added successfully.')
            except Exception as e:
                messages.error(request, f'Error adding PO: {str(e)}')

        return redirect(
            f"{request.path}?school_id={selected_school_id}&program_id={selected_program_id}"
        )

    return render(request, 'adminpanel/manage_program_outcomes.html', {
        'schools': schools,
        'programs': programs,
        'selected_school_id': str(selected_school_id),
        'selected_program_id': str(selected_program_id),
        'selected_program': selected_program,
        'existing_pos': existing_pos,
    })


@never_cache
@login_required
@user_passes_test(is_admin, login_url='/login/')
def edit_program_outcome(request, po_id):
    """
    Edit a single ProgramOutcome entry.
    GET  → render edit form
    POST → save changes and redirect back to PO list for that program
    """
    po = get_object_or_404(ProgramOutcome, id=po_id)

    if request.method == 'POST':
        code = request.POST.get('po_code', '').strip()
        description = request.POST.get('po_description', '').strip()
        order_val = request.POST.get('po_order', '0').strip() or '0'

        if not code or not description:
            messages.error(request, 'PO Code and Description are required.')
        else:
            # Check duplicate code for same program (excluding self)
            duplicate = ProgramOutcome.objects.filter(
                program=po.program, code__iexact=code
            ).exclude(id=po.id).exists()

            if duplicate:
                messages.error(request, f'"{code}" already exists for this program.')
            else:
                try:
                    po.code = code
                    po.description = description
                    po.order = int(order_val)
                    po.save()
                    messages.success(request, f'Program Outcome "{code}" updated successfully.')
                    from django.urls import reverse
                    redirect_url = (
                        reverse('manage_program_outcomes')
                        + f"?school_id={po.program.school_id}&program_id={po.program_id}"
                    )
                    return redirect(redirect_url)
                except Exception as e:
                    messages.error(request, f'Error updating PO: {str(e)}')

    return render(request, 'adminpanel/edit_program_outcome.html', {
        'po': po,
    })


@never_cache
@login_required
@user_passes_test(is_admin, login_url='/login/')
@require_POST
def delete_program_outcome(request, po_id):
    """
    Delete a single ProgramOutcome.
    Always redirects back to PO list for the same program.
    """
    po = get_object_or_404(ProgramOutcome, id=po_id)
    school_id = po.program.school_id
    program_id = po.program_id
    code = po.code
    try:
        po.delete()
        messages.success(request, f'Program Outcome "{code}" deleted successfully.')
    except Exception as e:
        messages.error(request, f'Error deleting PO: {str(e)}')

    from django.urls import reverse
    return redirect(
        reverse('manage_program_outcomes')
        + f"?school_id={school_id}&program_id={program_id}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# PROGRAM SPECIFIC OUTCOMES (PSO) MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

@never_cache
@login_required
@user_passes_test(is_admin, login_url='/login/')
def manage_program_specific_outcomes(request):
    """
    Main PSO management page.
    Hierarchy: School → Program → Branch
    - GET: renders page with optional school/program/branch filter applied.
    - POST (action=add): creates a new PSO for the selected branch.
    """
    schools = School.objects.all().order_by('name')

    selected_school_id  = request.GET.get('school_id')  or request.POST.get('school_id')  or ''
    selected_program_id = request.GET.get('program_id') or request.POST.get('program_id') or ''
    selected_branch_id  = request.GET.get('branch_id')  or request.POST.get('branch_id')  or ''

    programs = []
    if selected_school_id:
        programs = Program.objects.filter(school_id=selected_school_id).order_by('name')

    branches = []
    if selected_program_id:
        branches = Branch.objects.filter(program_id=selected_program_id).order_by('name')

    selected_branch = None
    existing_psos = []
    if selected_branch_id:
        selected_branch = Branch.objects.filter(id=selected_branch_id).first()
        if selected_branch:
            existing_psos = ProgramSpecificOutcome.objects.filter(
                branch=selected_branch
            ).order_by('order', 'id')

    # Handle ADD
    if request.method == 'POST' and request.POST.get('action') == 'add':
        code        = request.POST.get('pso_code',        '').strip()
        description = request.POST.get('pso_description', '').strip()
        order_val   = request.POST.get('pso_order',       '0').strip() or '0'

        if not code or not description:
            messages.error(request, 'PSO Code and Description are required.')
        elif not selected_branch:
            messages.error(request, 'Please select a valid Branch.')
        elif ProgramSpecificOutcome.objects.filter(branch=selected_branch, code__iexact=code).exists():
            messages.error(request, f'"{code}" already exists for this branch.')
        else:
            try:
                ProgramSpecificOutcome.objects.create(
                    branch=selected_branch,
                    code=code,
                    description=description,
                    order=int(order_val),
                )
                messages.success(request, f'Program Specific Outcome "{code}" added successfully.')
            except Exception as e:
                messages.error(request, f'Error adding PSO: {str(e)}')

        return redirect(
            f"{request.path}?school_id={selected_school_id}&program_id={selected_program_id}&branch_id={selected_branch_id}"
        )

    return render(request, 'adminpanel/manage_program_specific_outcomes.html', {
        'schools':             schools,
        'programs':            programs,
        'branches':            branches,
        'selected_school_id':  str(selected_school_id),
        'selected_program_id': str(selected_program_id),
        'selected_branch_id':  str(selected_branch_id),
        'selected_branch':     selected_branch,
        'existing_psos':       existing_psos,
    })


@never_cache
@login_required
@user_passes_test(is_admin, login_url='/login/')
def edit_program_specific_outcome(request, pso_id):
    """
    Edit a single ProgramSpecificOutcome entry.
    GET  → render edit form
    POST → save changes and redirect back to PSO list for that branch
    """
    pso = get_object_or_404(ProgramSpecificOutcome, id=pso_id)

    if request.method == 'POST':
        code        = request.POST.get('pso_code',        '').strip()
        description = request.POST.get('pso_description', '').strip()
        order_val   = request.POST.get('pso_order',       '0').strip() or '0'

        if not code or not description:
            messages.error(request, 'PSO Code and Description are required.')
        else:
            duplicate = ProgramSpecificOutcome.objects.filter(
                branch=pso.branch, code__iexact=code
            ).exclude(id=pso.id).exists()

            if duplicate:
                messages.error(request, f'"{code}" already exists for this branch.')
            else:
                try:
                    pso.code        = code
                    pso.description = description
                    pso.order       = int(order_val)
                    pso.save()
                    messages.success(request, f'Program Specific Outcome "{code}" updated successfully.')
                    redirect_url = (
                        reverse('manage_program_specific_outcomes')
                        + f"?school_id={pso.branch.program.school_id}"
                        + f"&program_id={pso.branch.program_id}"
                        + f"&branch_id={pso.branch_id}"
                    )
                    return redirect(redirect_url)
                except Exception as e:
                    messages.error(request, f'Error updating PSO: {str(e)}')

    return render(request, 'adminpanel/edit_program_specific_outcome.html', {
        'pso': pso,
    })


@never_cache
@login_required
@user_passes_test(is_admin, login_url='/login/')
@require_POST
def delete_program_specific_outcome(request, pso_id):
    """
    Delete a single ProgramSpecificOutcome.
    Always redirects back to PSO list for the same branch.
    """
    pso        = get_object_or_404(ProgramSpecificOutcome, id=pso_id)
    school_id  = pso.branch.program.school_id
    program_id = pso.branch.program_id
    branch_id  = pso.branch_id
    code       = pso.code
    try:
        pso.delete()
        messages.success(request, f'Program Specific Outcome "{code}" deleted successfully.')
    except Exception as e:
        messages.error(request, f'Error deleting PSO: {str(e)}')

    return redirect(
        reverse('manage_program_specific_outcomes')
        + f"?school_id={school_id}&program_id={program_id}&branch_id={branch_id}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# PROGRAM EDUCATIONAL OBJECTIVES (PEO) MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

@never_cache
@login_required
@user_passes_test(is_admin, login_url='/login/')
def manage_program_educational_objectives(request):
    """
    Main PEO management page.
    Hierarchy: School → Program  (same level as PO)
    - GET: renders page with optional school/program filter applied.
    - POST (action=add): creates a new PEO for the selected program.
    """
    schools = School.objects.all().order_by('name')

    selected_school_id  = request.GET.get('school_id')  or request.POST.get('school_id')  or ''
    selected_program_id = request.GET.get('program_id') or request.POST.get('program_id') or ''

    programs = []
    if selected_school_id:
        programs = Program.objects.filter(school_id=selected_school_id).order_by('name')

    selected_program = None
    existing_peos = []
    if selected_program_id:
        selected_program = Program.objects.filter(id=selected_program_id).first()
        if selected_program:
            existing_peos = ProgramEducationalObjective.objects.filter(
                program=selected_program
            ).order_by('order', 'id')

    # Handle ADD
    if request.method == 'POST' and request.POST.get('action') == 'add':
        code        = request.POST.get('peo_code',        '').strip()
        description = request.POST.get('peo_description', '').strip()
        order_val   = request.POST.get('peo_order',       '0').strip() or '0'

        if not code or not description:
            messages.error(request, 'PEO Code and Description are required.')
        elif not selected_program:
            messages.error(request, 'Please select a valid Program.')
        elif ProgramEducationalObjective.objects.filter(program=selected_program, code__iexact=code).exists():
            messages.error(request, f'"{code}" already exists for this program.')
        else:
            try:
                ProgramEducationalObjective.objects.create(
                    program=selected_program,
                    code=code,
                    description=description,
                    order=int(order_val),
                )
                messages.success(request, f'Program Educational Objective "{code}" added successfully.')
            except Exception as e:
                messages.error(request, f'Error adding PEO: {str(e)}')

        return redirect(
            f"{request.path}?school_id={selected_school_id}&program_id={selected_program_id}"
        )

    return render(request, 'adminpanel/manage_program_educational_objectives.html', {
        'schools':             schools,
        'programs':            programs,
        'selected_school_id':  str(selected_school_id),
        'selected_program_id': str(selected_program_id),
        'selected_program':    selected_program,
        'existing_peos':       existing_peos,
    })


@never_cache
@login_required
@user_passes_test(is_admin, login_url='/login/')
def edit_program_educational_objective(request, peo_id):
    """
    Edit a single ProgramEducationalObjective entry.
    GET  → render edit form
    POST → save changes and redirect back to PEO list for that program
    """
    peo = get_object_or_404(ProgramEducationalObjective, id=peo_id)

    if request.method == 'POST':
        code        = request.POST.get('peo_code',        '').strip()
        description = request.POST.get('peo_description', '').strip()
        order_val   = request.POST.get('peo_order',       '0').strip() or '0'

        if not code or not description:
            messages.error(request, 'PEO Code and Description are required.')
        else:
            duplicate = ProgramEducationalObjective.objects.filter(
                program=peo.program, code__iexact=code
            ).exclude(id=peo.id).exists()

            if duplicate:
                messages.error(request, f'"{code}" already exists for this program.')
            else:
                try:
                    peo.code        = code
                    peo.description = description
                    peo.order       = int(order_val)
                    peo.save()
                    messages.success(request, f'Program Educational Objective "{code}" updated successfully.')
                    redirect_url = (
                        reverse('manage_program_educational_objectives')
                        + f"?school_id={peo.program.school_id}"
                        + f"&program_id={peo.program_id}"
                    )
                    return redirect(redirect_url)
                except Exception as e:
                    messages.error(request, f'Error updating PEO: {str(e)}')

    return render(request, 'adminpanel/edit_program_educational_objective.html', {
        'peo': peo,
    })


@never_cache
@login_required
@user_passes_test(is_admin, login_url='/login/')
@require_POST
def delete_program_educational_objective(request, peo_id):
    """
    Delete a single ProgramEducationalObjective.
    Always redirects back to PEO list for the same program.
    """
    peo        = get_object_or_404(ProgramEducationalObjective, id=peo_id)
    school_id  = peo.program.school_id
    program_id = peo.program_id
    code       = peo.code
    try:
        peo.delete()
        messages.success(request, f'Program Educational Objective "{code}" deleted successfully.')
    except Exception as e:
        messages.error(request, f'Error deleting PEO: {str(e)}')

    return redirect(
        reverse('manage_program_educational_objectives')
        + f"?school_id={school_id}&program_id={program_id}"
    )
