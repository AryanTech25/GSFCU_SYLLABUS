import os
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.http import JsonResponse, FileResponse
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.contrib import messages
from .models import School, Program, Branch, Faculty, Subject, Syllabus, Semester, SemesterSubject, ProgramOutcome, ProgramSpecificOutcome, ProgramEducationalObjective
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
    


    return render(request, 'adminpanel/edit_faculty.html', {
        'faculty': faculty,
        'schools': schools,
        'programs': programs,
        'branches': branches,
        'semesters': semesters,
        'selected_semester': faculty.semester
    })


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


def _create_summary_pdf(school, program, branch_name, semester_val, qs, output_path, academic_year=None, is_preview=False):
    """
    Helper to create the professional summary page using ReportLab.
    Ensures Preview and Final PDF look identical.
    """
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, KeepTogether
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from datetime import datetime
    import os
    from django.conf import settings

    # Layout Constants — Portrait A4
    page_width, page_height = A4
    left_margin = 0.5 * inch
    right_margin = 0.5 * inch
    available_width = page_width - left_margin - right_margin

    doc = SimpleDocTemplate(output_path, pagesize=A4,
                           topMargin=0.4*inch, bottomMargin=0.4*inch,
                           leftMargin=left_margin, rightMargin=right_margin)
    elements = []
    styles = getSampleStyleSheet()

    # Logo Path
    logo_path = os.path.join(settings.BASE_DIR, "static", "images", "gsfc_logo.png")
    
    header_style = styles['Heading1'].clone('header_style')
    header_style.fontSize = 18
    header_style.textColor = colors.black
    header_style.alignment = TA_LEFT
    header_style.fontName = 'Helvetica-Bold'
    header_style.leading = 22
    
    subheader_style = styles['Normal'].clone('subheader_style')
    subheader_style.fontSize = 12
    subheader_style.alignment = TA_LEFT
    subheader_style.fontName = 'Helvetica-Bold'
    subheader_style.leading = 14

    # Create a header table to hold text and logo
    logo_img = ""
    if os.path.exists(logo_path):
        logo_img = Image(logo_path, width=1.6*inch, height=0.8*inch)
        logo_img.hAlign = 'RIGHT'

    info_text = [
        [Paragraph(school.name.upper(), header_style), logo_img],
        [Paragraph(f"PROGRAM: {program.name} ({branch_name})", subheader_style), ""],
        [Paragraph(f"SEMESTER: {semester_val} – COURSE STRUCTURE" + (" (PREVIEW)" if is_preview else ""), subheader_style), ""]
    ]
    
    # Dynamically scale header table
    header_table = Table(info_text, colWidths=[available_width - 1.7*inch, 1.7*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('SPAN', (1, 0), (1, 2)),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(header_table)

    # Academic Year
    academic_year_display = academic_year or "Academic Year Not Defined"
    info_style = styles['Normal'].clone('info_style')
    info_style.fontSize = 11
    info_style.alignment = TA_LEFT
    elements.append(Paragraph(f"Academic Year: {academic_year_display}", info_style))
    elements.append(Spacer(1, 0.15*inch))

    # --- TWO-TABLE STRUCTURE ---
    # Box 1: Sr No | Course Code | Course Name | Sem | TS: L P T Total | TC: L P T Total
    table_data_1 = [
        ['Sr.\nNo.', 'Course\nCode', 'Course Name', 'Sem', 'Teaching Scheme (Hours/Week)', '', '', '', 'Teaching Credit', '', '', ''],
        ['', '', '', '', 'L', 'P', 'T', 'Total', 'L', 'P', 'T', 'Total']
    ]
    
    # Box 2: Sr No | Course Code | Course Name | MS | CEC | ES | Theory Total | Prac | Grand
    table_data_2 = [
        ['Sr.\nNo.', 'Course\nCode', 'Course Name', 'Theory:\nMS Marks', 'Theory:\nCEC Marks', 'Theory:\nES Marks', 'Theory\nMarks', 'Practical\nMarks', 'Total\nMarks']
    ]

    # Define style for wrapping course names with 0 margin/space
    course_name_style = styles['Normal'].clone('course_name_style')
    course_name_style.fontSize = 8
    course_name_style.leading = 10
    course_name_style.alignment = TA_LEFT
    course_name_style.spaceBefore = 0
    course_name_style.spaceAfter = 0

    for idx, item in enumerate(qs, 1):
        subject = item.subject
        syllabus = subject.syllabus if hasattr(subject, 'syllabus') else None
        
        l = syllabus.hours_lecture if syllabus else 0
        p = syllabus.hours_practical if syllabus else 0
        t = syllabus.hours_tutorial if syllabus else 0
        ts_total = l + p + t
        
        cl = syllabus.credit_lecture if syllabus else 0
        cp = syllabus.credit_practical if syllabus else 0
        ct = syllabus.credit_tutorial if syllabus else 0
        tc_total = cl + cp + ct
        
        ms = 0; cec = 0; es = 0; theory_total = 0; prac_total = 0; grand_total = 0
        if syllabus and hasattr(syllabus, 'evaluation_scheme'):
            ev = syllabus.evaluation_scheme
            ms = ev.mid_sem
            cec = ev.cec_attendance + ev.cec_mcq + ev.cec_assignment
            es = ev.end_sem
            theory_total = ms + cec + es
            prac_total = (ev.prac_attendance + ev.prac_exam + ev.prac_viva + ev.prac_journal + ev.prac_discipline)
            grand_total = theory_total + prac_total
        
        # Use Paragraph to support multi-line wrapping and auto-height
        course_name_para_1 = Paragraph(subject.course_name, course_name_style)
        course_name_para_2 = Paragraph(subject.course_name, course_name_style)
        
        # Strip "Semester " prefix so the Sem column only shows the numeral (e.g. "V", "III")
        raw_sem = str(subject.semester) if hasattr(subject, 'semester') else ''
        sem_val = raw_sem.replace('Semester ', '').replace('semester ', '').strip()
        table_data_1.append([
            str(idx), subject.course_code, course_name_para_1,
            sem_val,
            str(l), str(p), str(t), str(ts_total),
            str(cl), str(cp), str(ct), str(tc_total)
        ])
        
        table_data_2.append([
            str(idx), subject.course_code, course_name_para_2,
            str(ms), str(cec), str(es), str(theory_total), str(prac_total), str(grand_total)
        ])

    # --- Fixed portrait-width column distribution ---
    # A4 portrait available ≈ 7.27 inch (8.27 - 0.5 - 0.5 margins).
    # All columns are FIXED so Course Name never auto-expands beyond ~26%.
    #
    # Box 1: 12 cols — Sr No | Code | Name | Sem | L | P | T | Tot | L | P | T | Tot
    #   Sem is now 0.28" (just wide enough for a Roman numeral like "VIII"), saving
    #   0.14" vs the old 0.42", which goes directly to Course Name.
    #   0.36 + 0.88 + Name + 0.28 + (0.44×6) + (0.55×2) = available_width
    #   fixed_sum_excl_name = 0.36+0.88+0.28+2.64+1.10 = 5.26 → Name ≈ 2.01"
    fixed_excl_name_1 = (
        0.36 + 0.88 +              # Sr No, Code
        0.28 +                     # Sem (narrow — numeral only)
        0.44 + 0.44 + 0.44 + 0.55 +  # TS: L, P, T, Total
        0.44 + 0.44 + 0.44 + 0.55    # TC: L, P, T, Total
    ) * inch
    col_widths_1 = [
        0.36 * inch,   # Sr No
        0.88 * inch,   # Course Code
        available_width - fixed_excl_name_1,  # Course Name (~28%, wraps)
        0.28 * inch,   # Sem (numeral only, e.g. "V")
        0.44 * inch, 0.44 * inch, 0.44 * inch, 0.55 * inch,  # TS: L, P, T, Total
        0.44 * inch, 0.44 * inch, 0.44 * inch, 0.55 * inch,  # TC: L, P, T, Total
    ]

    # Box 2: 9 cols — Sr No | Code | Name | MS | CEC | ES | Theory | Prac | Grand
    #   0.36 + 0.88 + Name + (0.68×6) = available_width
    #   fixed_sum_excl_name = 0.36+0.88+4.08 = 5.32 → Name ≈ 1.95"
    fixed_excl_name_2 = (
        0.36 + 0.88 +              # Sr No, Code
        0.68 + 0.68 + 0.68 +      # MS, CEC, ES Marks
        0.68 + 0.68 + 0.68        # Theory Total, Practical, Grand Total
    ) * inch
    col_widths_2 = [
        0.36 * inch,   # Sr No
        0.88 * inch,   # Course Code
        available_width - fixed_excl_name_2,  # Course Name (~26%, wraps)
        0.68 * inch,   # MS Marks
        0.68 * inch,   # CEC Marks
        0.68 * inch,   # ES Marks
        0.68 * inch,   # Theory Total
        0.68 * inch,   # Practical Marks
        0.68 * inch,   # Grand Total
    ]

    table_1 = Table(table_data_1, colWidths=col_widths_1, repeatRows=2)
    table_2 = Table(table_data_2, colWidths=col_widths_2, repeatRows=1)
    
    table_style_1 = [
        # --- BASE STYLE ---
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING', (0,0), (-1,-1), 2),
        ('RIGHTPADDING', (0,0), (-1,-1), 2),
        
        # --- ACADEMIC HEADER STYLE (MATCHING SYLLABUS PAGES) ---
        ('BACKGROUND', (0,0), (-1,1), colors.HexColor('#d3d3d3')), # Official Grey
        ('TEXTCOLOR', (0,0), (-1,1), colors.black),
        ('FONTNAME', (0,0), (-1,1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,1), 8),
        ('TOPPADDING', (0,0), (-1,1), 3),
        ('BOTTOMPADDING', (0,0), (-1,1), 3),

        # --- DATA ROW STYLE ---
        ('BACKGROUND', (0, 2), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 2), (-1, -1), colors.black),

        # --- HEADER SPANNING (12-col: Sr|Code|Name|Sem|L|P|T|Tot|L|P|T|Tot) ---
        ('SPAN', (0,0), (0,1)),   # Sr No spans 2 rows
        ('SPAN', (1,0), (1,1)),   # Course Code spans 2 rows
        ('SPAN', (2,0), (2,1)),   # Course Name spans 2 rows
        ('SPAN', (3,0), (3,1)),   # Sem spans 2 rows
        ('SPAN', (4,0), (7,0)),   # Teaching Scheme group header
        ('SPAN', (8,0), (11,0)),  # Teaching Credit group header

        ('ALIGN', (2, 2), (2, -1), 'LEFT'),
        ('LEFTPADDING', (2, 2), (2, -1), 4),
    ]
    table_1.setStyle(TableStyle(table_style_1))

    table_style_2 = [
        # --- BASE STYLE ---
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING', (0,0), (-1,-1), 2),
        ('RIGHTPADDING', (0,0), (-1,-1), 2),
        
        # --- ACADEMIC HEADER STYLE ---
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#d3d3d3')), # Official Grey
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('TOPPADDING', (0,0), (-1,0), 3),
        ('BOTTOMPADDING', (0,0), (-1,0), 3),

        # --- DATA ROW STYLE ---
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),

        ('ALIGN', (2, 1), (2, -1), 'LEFT'),
        ('LEFTPADDING', (2, 1), (2, -1), 4),
    ]
    table_2.setStyle(TableStyle(table_style_2))

    section_label_style = styles['Normal'].clone('section_label_style')
    section_label_style.fontSize = 10
    section_label_style.alignment = TA_LEFT
    section_label_style.fontName = 'Helvetica-Bold'
    section_label_style.leading = 12
    section_label_style.textColor = colors.black
    section_label_style.spaceBefore = 0
    section_label_style.spaceAfter = 0

    # Append Box 1 (Teaching Scheme & Credit) wrapped in KeepTogether to prevent orphans
    elements.append(KeepTogether([
        Paragraph("Teaching Scheme & Credit", section_label_style),
        Spacer(1, 0.04*inch),
        table_1
    ]))
    
    # Append Box 2 (Evaluation Scheme) wrapped in KeepTogether to prevent orphans
    elements.append(Spacer(1, 0.12*inch))
    elements.append(KeepTogether([
        Paragraph("Evaluation Scheme", section_label_style),
        Spacer(1, 0.04*inch),
        table_2
    ]))

    # Footer - Compact
    elements.append(Spacer(1, 0.1*inch))
    footer_style = styles['Normal'].clone('footer_style')
    footer_style.fontSize = 8
    footer_style.textColor = colors.grey
    footer_style.alignment = TA_CENTER
    elements.append(Paragraph(f"Academic Year: {academic_year_display} | Generated on {timezone.now().strftime('%B %d, %Y')} | GSFC University Syllabus Management System", footer_style))

    doc.build(elements)
    return output_path


@never_cache
@login_required
@user_passes_test(is_admin, login_url='/login/')
def generate_semester_pdf(request):
    """
    Admin-only view to generate combined PDF from currently displayed subjects.
    Works with any filter combination - generates PDF for whatever is shown on screen.
    """
    # Get filter values (same as manage_semester_structure view)
    selected_school_id = request.GET.get('school_id') or None
    selected_program_id = request.GET.get('program_id') or None
    selected_branch_id = request.GET.get('branch_id') or None
    selected_semester = request.GET.get('semester') or None

    try:
        from pypdf import PdfWriter, PdfReader
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.units import inch
        import os
        from django.conf import settings
        from django.core.files import File
        import hashlib
        from datetime import datetime
        
    except ImportError as e:
        messages.error(request, f"Required library not available: {str(e)}")
        return redirect('manage_semester_structure')

    try:
        # Build query for subjects based on selected filters (same logic as display)
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
                 q_filters &= (Q(semester=selected_semester) | Q(semester=mapped_sem))
             else:
                 q_filters &= Q(semester=selected_semester)

        # Get all matching subjects (same as what's displayed)
        all_subjects = Subject.objects.filter(q_filters).select_related(
            'school', 'program', 'branch', 'syllabus', 'syllabus__evaluation_scheme'
        ).order_by('course_code')
        
        if not all_subjects.exists():
            messages.warning(request, "No subjects match the current filters.")
            return redirect('manage_semester_structure')
        
        # Filter to only subjects WITH PDFs
        subjects_with_pdfs = [
            subj for subj in all_subjects 
            if hasattr(subj, 'syllabus') and subj.syllabus and subj.syllabus.pdf_file
        ]
        
        if not subjects_with_pdfs:
            messages.error(request, "None of the displayed subjects have PDF files generated yet.")
            return redirect('manage_semester_structure')
        
        # Get metadata for PDF generation
        school = subjects_with_pdfs[0].school
        program = subjects_with_pdfs[0].program
        branch_name = subjects_with_pdfs[0].branch.name if subjects_with_pdfs[0].branch else "Mixed"
        semester_val = selected_semester if selected_semester else "Mixed Semesters"
        
        # Check for mixed contexts
        schools_set = set(s.school.code for s in subjects_with_pdfs)
        programs_set = set(s.program.name for s in subjects_with_pdfs)
        branches_set = set(s.branch.name if s.branch else "Common" for s in subjects_with_pdfs)
        semesters_set = set(s.semester for s in subjects_with_pdfs)
        
        # Update metadata for mixed contexts
        if len(schools_set) > 1:
            school.name = "Multiple Schools"
            school.code = "MIXED"
        if len(programs_set) > 1:
            program.name = "Multiple Programs"
        if len(branches_set) > 1:
            branch_name = "Mixed Branches"
        if len(semesters_set) > 1:
            semester_val = "Mixed Semesters"
        
        # === STEP 1: Generate Summary Page ===
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        # Use timestamp for unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        summary_path = os.path.join(temp_dir, f'summary_{timestamp}.pdf')
        
        # Get academic year from first subject
        academic_year = "Academic Year Not Defined"
        # Get academic year from first subject
        academic_year = "Academic Year Not Defined"
        for subj in subjects_with_pdfs:
            # Use Subject Academic Year (NEW)
            if hasattr(subj, 'academic_year') and subj.academic_year:
                academic_year = subj.academic_year
                break
                
            if hasattr(subj, 'syllabus') and subj.syllabus.faculty:
                if subj.syllabus.faculty.academic_year:
                    academic_year = subj.syllabus.faculty.academic_year
                    break
        
        # Create wrapper objects that match the _create_summary_pdf expectation
        class SubjectWrapper:
            def __init__(self, subject):
                self.subject = subject
        
        wrapped_subjects = [SubjectWrapper(s) for s in subjects_with_pdfs]
        _create_summary_pdf(school, program, branch_name, semester_val, wrapped_subjects, 
                          summary_path, academic_year=academic_year, is_preview=False)
        
        # === STEP 2: Merge PDFs ===
        merger = PdfWriter()
        
        try:
            # Add summary as first page
            with open(summary_path, 'rb') as summary_file:
                summary_reader = PdfReader(summary_file)
                merger.append_pages_from_reader(summary_reader)
            
            # Add subject PDFs in order
            pdf_count = 0
            skipped_pdfs = []
            
            for subject in subjects_with_pdfs:
                try:
                    file_path = subject.syllabus.pdf_file.path
                    if os.path.exists(file_path):
                        with open(file_path, 'rb') as f:
                            reader = PdfReader(f)
                            merger.append_pages_from_reader(reader)
                            pdf_count += 1
                    else:
                        skipped_pdfs.append(subject.course_code)
                except Exception as e:
                    skipped_pdfs.append(f"{subject.course_code} (Error: {str(e)})")
                    continue
            
            if skipped_pdfs:
                messages.warning(
                    request,
                    f"Some subject PDFs had errors and were skipped: {', '.join(skipped_pdfs)}"
                )
            
            if pdf_count == 0:
                messages.error(request, "No subject PDFs could be merged.")
                raise Exception("No PDFs to merge")
            
            # === STEP 3: Generate filename and save ===
            # Create descriptive filename based on filters
            filename_parts = []
            if selected_school_id and len(schools_set) == 1:
                filename_parts.append(school.code)
            if selected_program_id and len(programs_set) == 1:
                filename_parts.append(program.name.replace(' ', '_'))
            if selected_branch_id and len(branches_set) == 1:
                filename_parts.append(branch_name.replace(' ', '_'))
            if selected_semester and len(semesters_set) == 1:
                filename_parts.append(semester_val.replace(' ', '_'))
            
            if not filename_parts:
                filename_parts.append("Combined")
            
            filename_parts.append(f"Syllabus_{timestamp}")
            filename = "_".join(filename_parts) + ".pdf"
            filename = "".join([c if c.isalnum() or c in ('_','-','.') else '_' for c in filename])
            
            # Write merged PDF to temp file
            temp_merged_path = os.path.join(temp_dir, filename)
            with open(temp_merged_path, 'wb') as output_file:
                merger.write(output_file)
            
            # Clean up summary temp file
            try:
                os.remove(summary_path)
            except:
                pass
            
            # Serve the file for download
            from django.http import FileResponse
            
            response = FileResponse(
                open(temp_merged_path, 'rb'),
                content_type='application/pdf'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            # Note: temp file will be cleaned up after response is sent
            # Django handles this automatically with FileResponse
            return response
        
        except Exception as inner_error:
            # Clean up temp files on error
            try:
                os.remove(summary_path)
            except:
                pass
            try:
                if os.path.exists(temp_merged_path):
                    os.remove(temp_merged_path)
            except:
                pass
            raise inner_error

    except Exception as e:
        messages.error(request, f"Error generating PDF: {str(e)}")
        import traceback
        print(traceback.format_exc())  # For debugging
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
        from pypdf import PdfWriter, PdfReader
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.units import inch
        from io import BytesIO
        import os
        from django.conf import settings
        
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

        # === Generate Summary Page (PREVIEW) ===
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        summary_path = os.path.join(temp_dir, f'preview_summary_{sem_obj.id}_{branch_id or "common"}.pdf')
        
        academic_year = _get_academic_year_from_qs(qs)
        _create_summary_pdf(school, program, branch_name, semester_val, qs, summary_path, academic_year=academic_year, is_preview=True)
        
        # === Merge PDFs ===
        merger = PdfWriter()
        files_opened = []
        
        try:
            # Add summary
            with open(summary_path, 'rb') as summary_file:
                summary_reader = PdfReader(summary_file)
                merger.append_pages_from_reader(summary_reader)
            
            pdf_count = 0
            for item in qs:
                try:
                    if hasattr(item.subject, 'syllabus') and item.subject.syllabus.pdf_file:
                        file_path = item.subject.syllabus.pdf_file.path
                        if os.path.exists(file_path):
                            with open(file_path, 'rb') as f:
                                reader = PdfReader(f)
                                merger.append_pages_from_reader(reader)
                                pdf_count += 1
                except:
                    continue
            
            if pdf_count == 0:
                messages.error(request, "No subject syllabus PDFs available to preview.")
                raise Exception("No PDFs to merge")
            
            # Write to BytesIO
            buffer = BytesIO()
            merger.write(buffer)
            buffer.seek(0)
            
            # Clean up temp summary file
            try:
                os.remove(summary_path)
            except:
                pass
            
            # Return PDF
            download_mode = request.GET.get('download') == '1'
            filename = f"{school.code}_{program.name}_{branch_name}_{semester_val}_Preview.pdf"
            filename = "".join([c if c.isalnum() or c in ('_','-','.') else '_' for c in filename])
            
            response = FileResponse(buffer, content_type='application/pdf')
            disposition = 'attachment' if download_mode else 'inline'
            response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
            return response
            
        except Exception as e:
            # Clean up on error
            try:
                os.remove(summary_path)
            except:
                pass
            raise e

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
        from pypdf import PdfWriter
        import os
        from django.conf import settings
        from .models import SemesterReference, Semester, Branch, School, Program

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

        # 2. Setup storage
        final_dir = os.path.join(settings.MEDIA_ROOT, 'final_syllabus')
        os.makedirs(final_dir, exist_ok=True)
        
        safe_program = "".join([c if c.isalnum() else "_" for c in program.name])
        safe_branch = "".join([c if c.isalnum() else "_" for c in branch_name])
        filename = f"{school.name[:3].upper()}_{safe_program}_{safe_branch}_FULL_SYLLABUS.pdf"
        output_path = os.path.join(final_dir, filename)

        # 3. Create Cover Page
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        cover_path = os.path.join(temp_dir, f"cover_{program.id}_{branch_id or 'all'}.pdf")
        
        # Get Academic Year from first available ref
        academic_year = "Not Defined"
        # Try to find a real AY from the first ref's subjects
        from .models import SemesterSubject
        first_ref_sem = sem_refs.first().semester
        qs = SemesterSubject.objects.filter(semester=first_ref_sem)
        if branch:
            qs = qs.filter(subject__branch=branch)
        if qs.exists():
            academic_year = _get_academic_year_from_qs(qs)

        _create_full_syllabus_cover(school, program, branch_name, academic_year, cover_path)

        # 4. Merge PDFs
        merger = PdfWriter()
        files_to_close = []

        try:
            # Add Cover
            f_cover = open(cover_path, 'rb')
            merger.append(f_cover)
            files_to_close.append(f_cover)

            # Add Semester PDFs
            for ref in sem_refs:
                if ref.pdf_file and os.path.exists(ref.pdf_file.path):
                    f = open(ref.pdf_file.path, 'rb')
                    merger.append(f)
                    files_to_close.append(f)

            # Save Final
            with open(output_path, 'wb') as f_out:
                merger.write(f_out)

        finally:
            for f in files_to_close:
                f.close()
            if os.path.exists(cover_path):
                os.remove(cover_path)

        # 5. Serve for Download
        response = FileResponse(open(output_path, 'rb'), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        messages.error(request, f"Error generating full syllabus: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return redirect(f"{reverse('manage_semester_structure')}?school_id={school_id}&program_id={program_id}&branch_id={branch_id or ''}")


def _create_full_syllabus_cover(school, program, branch_name, academic_year, output_path):
    """
    Helper to create a professional cover page for the Full Program Syllabus.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER
    import os
    from django.conf import settings

    doc = SimpleDocTemplate(output_path, pagesize=A4,
                           topMargin=1*inch, bottomMargin=1*inch,
                           leftMargin=1*inch, rightMargin=1*inch)
    elements = []
    styles = getSampleStyleSheet()

    # Logo
    logo_path = os.path.join(settings.BASE_DIR, "static", "images", "gsfc_logo.png")
    if os.path.exists(logo_path):
        logo_img = Image(logo_path, width=3*inch, height=1.5*inch)
        logo_img.hAlign = 'CENTER'
        elements.append(logo_img)
        elements.append(Spacer(1, 1*inch))

    # University Name
    univ_style = ParagraphStyle('UnivStyle', parent=styles['Heading1'], fontSize=24, alignment=TA_CENTER, spaceAfter=20)
    elements.append(Paragraph("GSFC UNIVERSITY", univ_style))
    elements.append(Spacer(1, 0.5*inch))

    # Syllabus Title
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=20, alignment=TA_CENTER, spaceAfter=30, textColor=colors.HexColor('#1b4332'))
    elements.append(Paragraph("FULL PROGRAM SYLLABUS", title_style))
    elements.append(Spacer(1, 0.5*inch))

    # Info Style
    info_style = ParagraphStyle('InfoStyle', parent=styles['Normal'], fontSize=14, alignment=TA_CENTER, leading=20)
    
    elements.append(Paragraph(f"<b>School:</b> {school.name}", info_style))
    elements.append(Paragraph(f"<b>Program:</b> {program.name}", info_style))
    if branch_name:
        elements.append(Paragraph(f"<b>Branch:</b> {branch_name}", info_style))
    elements.append(Paragraph(f"<b>Academic Year:</b> {academic_year}", info_style))
    
    elements.append(Spacer(1, 1.5*inch))
    
    # Generated Date
    date_style = ParagraphStyle('DateStyle', parent=styles['Normal'], fontSize=10, alignment=TA_CENTER, textColor=colors.grey)
    elements.append(Paragraph(f"Includes All Semester Syllabus Combined", info_style))
    elements.append(Spacer(1, 0.2*inch))
    elements.append(Paragraph(f"Generated On: {datetime.now().strftime('%B %d, %Y')}", date_style))

    doc.build(elements)
    return output_path


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
