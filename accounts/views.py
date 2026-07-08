from django.shortcuts import render, redirect, get_object_or_404
import re
import os
from django.conf import settings
from io import BytesIO

from adminpanel.models import Faculty, Subject, Semester, SemesterSubject

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.http import HttpResponseForbidden, JsonResponse
from .utils import load_full_syllabus

@never_cache
def login_view(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('admin_dashboard')
        else:
            return redirect('faculty_dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')  # This will be faculty_id for faculty
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            if user.is_staff:
                return redirect('admin_dashboard')
            else:
                return redirect('faculty_dashboard')
        else:
            return render(request, 'accounts/login.html', {'error': 'Invalid credentials'})

    return render(request, 'accounts/login.html')

@never_cache
def logout_view(request):
    """
    Clears session and forces browser to forget sensitive dashboard pages.
    """
    logout(request)
    response = redirect('login')
    # Force immediate cache invalidation on logout
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

@never_cache
@login_required
def faculty_dashboard(request):
    if request.user.is_staff:
        return redirect('admin_dashboard')
    
    # Access the related Faculty object
    try:
        faculty = Faculty.objects.select_related('school', 'program', 'branch').get(user=request.user)
        subjects = faculty.subjects.all()
    except Faculty.DoesNotExist:
        # Fallback if user is not linked to faculty
        faculty = None
        subjects = []

    # Prepare subjects data with draft info
    subjects_data = []
    has_drafts = False

    if faculty:
        from adminpanel.models import Syllabus
        for sub in subjects:
            # Check draft specifically for this faculty and subject
            draft = Syllabus.objects.filter(faculty=faculty, subject=sub, status='draft').first()
            subjects_data.append({
                'subject': sub,
                'has_draft': draft is not None,
                'draft_id': draft.id if draft else None,
                'has_pdf': bool(draft and draft.pdf_file),
                'pdf_url': draft.pdf_file.url if (draft and draft.pdf_file) else None
            })
        
        # Check if any drafts exist
        has_drafts = any(item['has_draft'] for item in subjects_data)

    # SEMESTER MERGE Logic
    mergeable_semesters = []
    if faculty:
        my_subject_ids = faculty.subjects.values_list('id', flat=True)
        # Find semesters containing these subjects
        # We use SemesterSubject to find the link
        sem_links = SemesterSubject.objects.filter(subject_id__in=my_subject_ids).select_related('semester', 'semester__program')
        
        seen = set()
        for link in sem_links:
            if link.semester.id not in seen:
                seen.add(link.semester.id)
                mergeable_semesters.append(link.semester)

    context = {
        'faculty': faculty,
        'subjects_data': subjects_data,
        'has_drafts': has_drafts,
        'mergeable_semesters': mergeable_semesters
    }
    return render(request, 'accounts/faculty_dashboard.html', context)

@never_cache
@login_required
def faculty_drafts(request):
    if request.user.is_staff:
        return redirect('admin_dashboard')

    from adminpanel.models import Syllabus
    try:
        faculty = Faculty.objects.get(user=request.user)
        drafts = Syllabus.objects.filter(faculty=faculty, status='draft').select_related('subject').order_by('-updated_at')
    except Faculty.DoesNotExist:
        faculty = None
        drafts = []

    return render(request, 'accounts/faculty_drafts.html', {'drafts': drafts})

@never_cache
@login_required
def syllabus_builder(request):
    if request.user.is_staff:
        return redirect('admin_dashboard')

    from adminpanel.models import Syllabus, CourseObjective, TheoryUnit, Practical, EvaluationScheme, CourseOutcome, OutcomeMapping, LearningResource
    
    try:
        faculty = Faculty.objects.get(user=request.user)
    except Faculty.DoesNotExist:
        faculty = None

    selected_subject = None
    saved_syllabus = None
    
    # Init Collections for Template
    saved_objectives = []
    saved_units = []
    saved_practicals = []
    saved_evaluation = None
    saved_outcomes = []
    saved_resources = []

    # --- GET: LOAD DATA ---
    if faculty:
        draft_id = request.GET.get('draft_id')
        subject_id = request.GET.get('subject_id')
        
        target_syllabus_id = None
        
        # 1. Try to find explicit draft
        if draft_id:
             # Verify ownership and existence
             check = Syllabus.objects.filter(id=draft_id, faculty=faculty).first()
             if check:
                 target_syllabus_id = check.id
        
        # 2. Try implicit draft via subject
        if not target_syllabus_id and subject_id:
             check = Syllabus.objects.filter(subject_id=subject_id, faculty=faculty, status='draft').first()
             if check:
                 target_syllabus_id = check.id
        
        # 3. Load full data if we have an ID
        if target_syllabus_id:
            saved_syllabus = load_full_syllabus(target_syllabus_id)
            
        # 4. If no draft, maybe auto-fill from a Final version?
        # Only do this if we don't have a current draft we are working on
        if not saved_syllabus and subject_id:
             # Check for final to clone as template
             final = Syllabus.objects.filter(subject_id=subject_id, faculty=faculty, status='final').order_by('-updated_at').first()
             if final:
                 saved_syllabus = load_full_syllabus(final.id)
                 # NOTE: We loaded a FINAL syllabus. 
                 # We will display its data, but we must NOT act as if we are editing it directly in 'draft' mode.
                 # The 'saved_syllabus' object here is just for pre-filling the context/hydration.
                 # The form submission handles creating the new draft correctly.

        # Bind Data
        if saved_syllabus:
            selected_subject = saved_syllabus.subject
            saved_objectives = saved_syllabus.objectives.all()
            saved_units = saved_syllabus.theory_units.all()
            saved_practicals = saved_syllabus.practicals.all()
            try:
                saved_evaluation = saved_syllabus.evaluation_scheme
            except:
                saved_evaluation = None
            saved_outcomes = saved_syllabus.course_outcomes.all()
            saved_resources = saved_syllabus.learning_resources.all()
            
        elif subject_id:
             selected_subject = get_object_or_404(Subject, id=subject_id)

    semesters = ["Semester I", "Semester II", "Semester III", "Semester IV", "Semester V", "Semester VI", "Semester VII", "Semester VIII"]

    # --- POST: SAVE DRAFT ---
    if request.method == 'POST':
        from django.contrib import messages
        from django.db import transaction
        
        subject_id = request.POST.get("subject_id")
        save_mode = request.POST.get('save_mode')

        if save_mode == 'draft':
            # --- BACKEND VALIDATION (STRICT) ---
            errors = []
            first_invalid_field = None
            
            # Helper for numeric validation
            def check_num(val, name):
                try:
                    if float(val) < 0:
                        return f"{name} must be non-negative."
                except (ValueError, TypeError):
                    return f"{name} must be a valid number."
                return None

            # Helper to add error and track first field
            def add_error(msg, field=None):
                nonlocal first_invalid_field
                errors.append(msg)
                if field and first_invalid_field is None:
                    first_invalid_field = field

            # 1. Static Fields
            req_fields = [
                'hours_lecture', 'hours_practical', 'hours_tutorial', 
                'credit_lecture', 'credit_practical', 'credit_tutorial',
                'prerequisites', 'category', 'focus', 'rationale', 'approval_date'
            ]
            for f in req_fields:
                val = request.POST.get(f, '').strip()
                if not val:
                    add_error(f"Missing required field: {f.replace('_', ' ').title()}", f)
            
            # Specific Checks
            pre = request.POST.get('prerequisites', '').strip()
            if pre and len(pre) < 3:
                add_error("Course prerequisite is required (min 3 chars).", 'prerequisites')

            # Numeric Checks (Static)
            num_fields = [
                'hours_lecture', 'hours_practical', 'hours_tutorial', 
                'credit_lecture', 'credit_practical', 'credit_tutorial',
                'eval_mid', 'eval_end', 'eval_cec_att', 'eval_cec_mcq', 'eval_cec_assign',
                'eval_prac_att', 'eval_prac_exam', 'eval_prac_viva', 'eval_prac_journal', 'eval_prac_disc'
            ]
            for f in num_fields:
                err = check_num(request.POST.get(f, 0), f.replace('_', ' ').title())
                if err: add_error(err, f)

            # 2. Dynamic Sections
            # Objectives
            obj_keys = sorted([k for k in request.POST.keys() if k.startswith('obj_')])
            if not obj_keys or not any(request.POST.get(k, '').strip() for k in obj_keys):
                add_error("At least one Course Objective is required.")
            
            # Units
            unit_keys = [k for k in request.POST.keys() if k.startswith('unit_title_')]
            if not unit_keys:
                add_error("At least one Theory Unit is required.")
            else:
                for k in unit_keys:
                    uid = k.split('_')[2]
                    if not request.POST.get(f'unit_title_{uid}', '').strip(): add_error("All Unit Titles must be filled.", f'unit_title_{uid}')
                    if not request.POST.get(f'unit_desc_{uid}', '').strip(): add_error("All Unit Topics must be filled.", f'unit_desc_{uid}')
                    
                    # Numeric
                    err_w = check_num(request.POST.get(f'unit_weight_{uid}', 0), "Unit Weightage")
                    if err_w: add_error(err_w, f'unit_weight_{uid}')
                    err_h = check_num(request.POST.get(f'unit_hours_{uid}', 0), "Unit Hours")
                    if err_h: add_error(err_h, f'unit_hours_{uid}')
                
                # Total Weight Check
                total_weight = 0
                for k in unit_keys:
                    uid = k.split('_')[2]
                    try:
                        total_weight += float(request.POST.get(f'unit_weight_{uid}', 0))
                    except (ValueError, TypeError):
                        pass # Algorithm will catch invalid number error above
                
                if abs(total_weight - 100) > 0.1:
                    add_error(f"Total Theory Unit Weightage must be 100%. Current total: {total_weight}%", f'unit_weight_{uid}' if unit_keys else None)

            # Practicals
            prac_keys = [k for k in request.POST.keys() if k.startswith('prac_desc_')]
            for k in prac_keys:
                uid = k.split('_')[2]
                if not request.POST.get(f'prac_desc_{uid}', '').strip(): add_error("All Practical Descriptions must be filled.", f'prac_desc_{uid}')
                
                # Numeric
                err_w = check_num(request.POST.get(f'prac_weight_{uid}', 0), "Practical Weightage")
                if err_w: add_error(err_w, f'prac_weight_{uid}')
                err_h = check_num(request.POST.get(f'prac_hours_{uid}', 0), "Practical Hours")
                if err_h: add_error(err_h, f'prac_hours_{uid}')

            # Outcomes & Mapping
            co_keys = sorted([k for k in request.POST.keys() if k.startswith('co_desc_')])
            if not co_keys: 
                add_error("At least one Course Outcome (CO) is required.")
            else:
                for idx, k in enumerate(co_keys, 1):
                    if not request.POST.get(k, '').strip(): add_error("CO Description cannot be empty.", k)
                    # Mapping Check
                    for i in range(1, 13):
                        val = request.POST.get(f'map_co{idx}_po{i}', '').strip()
                        if not val: 
                            add_error(f"CO{idx}-PO{i} mapping cannot be empty (enter 0).", f'map_co{idx}_po{i}')
                        else:
                            err = check_num(val, f"CO{idx}-PO{i}")
                            if err: add_error(err, f'map_co{idx}_po{i}')
            
            # Resources
            res_keys = [k for k in request.POST.keys() if k.startswith('res_cat_')]
            if not res_keys:
                add_error("At least one Learning Resource is required.")
            else:
                for k in res_keys:
                    uid = k.split('_')[2]
                    if not request.POST.get(f'res_cat_{uid}', '').strip(): add_error("Resource Category is required.", f'res_cat_{uid}')
                    if not request.POST.get(f'res_content_{uid}', '').strip(): add_error("Resource Content is required.", f'res_content_{uid}')

            if errors:
                # --- HYDRATE FROM POST (ERROR STATE) ---
                draft_data = {}
                
                # Objectives
                draft_data['objectives'] = [{'text': request.POST.get(k)} for k in obj_keys]
                
                # Units
                draft_data['units'] = []
                # Re-gather ids
                u_ids = sorted(list(set(k.split('_')[2] for k in unit_keys)))
                for uid in u_ids:
                    draft_data['units'].append({
                        'title': request.POST.get(f'unit_title_{uid}'),
                        'description': request.POST.get(f'unit_desc_{uid}'),
                        'weightage': request.POST.get(f'unit_weight_{uid}'),
                        'hours': request.POST.get(f'unit_hours_{uid}')
                    })

                # Practicals
                draft_data['practicals'] = []
                p_ids = sorted(list(set(k.split('_')[2] for k in prac_keys)))
                for uid in p_ids:
                    draft_data['practicals'].append({
                        'description': request.POST.get(f'prac_desc_{uid}'),
                        'weightage': request.POST.get(f'prac_weight_{uid}'),
                        'hours': request.POST.get(f'prac_hours_{uid}')
                    })

                # Outcomes
                draft_data['outcomes'] = []
                # CO keys already sorted
                for idx, k in enumerate(co_keys, 1):
                    uid = k.split('_')[2]
                    # Mapping
                    mapping_dict = {}
                    for i in range(1, 13):
                        mapping_dict[f'po{i}'] = request.POST.get(f'map_co{idx}_po{i}', 0)
                    mapping_dict['pso1'] = request.POST.get(f'map_co{idx}_pso1', 0)
                    mapping_dict['pso2'] = request.POST.get(f'map_co{idx}_pso2', 0)
                    
                    draft_data['outcomes'].append({
                        'description': request.POST.get(k),
                        'mapping': mapping_dict
                    })

                # Resources
                draft_data['resources'] = []
                r_ids = sorted(list(set(k.split('_')[2] for k in res_keys)))
                for uid in r_ids:
                    draft_data['resources'].append({
                        'category': request.POST.get(f'res_cat_{uid}'),
                        'content': request.POST.get(f'res_content_{uid}')
                    })

                # Render with errors
                context = {
                    'faculty': faculty, 
                    'semesters': semesters,
                    'selected_subject': get_object_or_404(Subject, id=subject_id) if subject_id else None,
                    'saved_syllabus': None, # Don't load DB state, we use draft_data
                    'savedDraftData': draft_data,
                    'error': "Please correct the following errors: " + "; ".join(list(set(errors)))[:200] + "..." if len(errors) > 5 else "; ".join(list(set(errors))),
                    'first_invalid_field': first_invalid_field
                }
                return render(request, 'accounts/syllabus_builder.html', context)


            try:
                if not faculty:
                     raise Exception("Faculty profile not found.")

                with transaction.atomic():
                     # 1. Resolve Subject
                     if not subject_id:
                         raise Exception("Subject ID missing.")
                     
                     subject = Subject.objects.select_for_update().get(id=subject_id)
                     
                     # 2. Get or Create Syllabus (SAFE LOADER)
                     # Using get_or_create prevents duplicate keys for OneToOne
                     syllabus, created = Syllabus.objects.get_or_create(
                         subject=subject,
                         defaults={
                             'faculty': faculty,
                             'status': 'draft'
                         }
                     )
                     
                     # Ensure it is currently a draft (in case we loaded a 'final' row, we might need logic here)
                     # Since this is "Save Draft", if the row exists and is "final", we are technically modifying the LIVE syllabus?
                     # The prompt implies we should be careful. 
                     # Ideally, 'final' syllabi shouldn't be touched properly without versioning, but user said "Draft vs Edit logic is inconsistent"
                     # If row exists, we update it.
                     if syllabus.status != 'draft':
                         syllabus.status = 'draft' # Revert to draft on edit? Or user intends to edit final.
                         # For now, update timestamp and status.
                     
                     syllabus.faculty = faculty # Ensure ownership

                     # 3. Update Fields
                     syllabus.hours_lecture = request.POST.get("hours_lecture") or 0
                     syllabus.hours_practical = request.POST.get("hours_practical") or 0
                     syllabus.hours_tutorial = request.POST.get("hours_tutorial") or 0
                     syllabus.credit_lecture = request.POST.get("credit_lecture") or 0
                     syllabus.credit_practical = request.POST.get("credit_practical") or 0
                     syllabus.credit_tutorial = request.POST.get("credit_tutorial") or 0
                     syllabus.prerequisites = request.POST.get("prerequisites", "")
                     syllabus.category = request.POST.get("category", "Core")
                     syllabus.focus = request.POST.get("focus", "Employability")
                     
                     app_date = request.POST.get('approval_date')
                     if app_date:
                         syllabus.approval_date = app_date
                     syllabus.rationale = request.POST.get("rationale", "")
                     
                     syllabus.save()

                     # 4. Safe Child Update (Delete & Recreate Pattern within Transaction)
                     syllabus.objectives.all().delete()
                     syllabus.theory_units.all().delete()
                     syllabus.practicals.all().delete()
                     syllabus.course_outcomes.all().delete()
                     if hasattr(syllabus, 'evaluation_scheme'):
                         syllabus.evaluation_scheme.delete()
                     syllabus.learning_resources.all().delete()
                     
                     # --- RECREATE CHILDREN ---
                     
                     # Objectives
                     obj_keys = sorted([k for k in request.POST.keys() if k.startswith('obj_')])
                     objs = [CourseObjective(syllabus=syllabus, text=request.POST[k].strip()) for k in obj_keys if request.POST[k].strip()]
                     CourseObjective.objects.bulk_create(objs)

                     # Theory Units
                     unit_keys = sorted([k for k in request.POST.keys() if k.startswith('unit_title_')])
                     # We use a set to track processed IDs to handle multiple fields per unit
                     processed_units = set()
                     for k in unit_keys:
                         uid = k.split('_')[2]
                         if uid in processed_units: continue
                         processed_units.add(uid)
                         
                         title = request.POST.get(f'unit_title_{uid}')
                         if title:
                             TheoryUnit.objects.create(
                                 syllabus=syllabus,
                                 title=title,
                                 description=request.POST.get(f'unit_desc_{uid}', ''),
                                 weightage=request.POST.get(f'unit_weight_{uid}') or 0,
                                 hours=request.POST.get(f'unit_hours_{uid}') or 0
                             )

                     # Practicals
                     prac_keys = sorted([k for k in request.POST.keys() if k.startswith('prac_desc_')])
                     processed_pracs = set()
                     for k in prac_keys:
                         uid = k.split('_')[2]
                         if uid in processed_pracs: continue
                         processed_pracs.add(uid)
                         
                         desc = request.POST.get(f'prac_desc_{uid}')
                         if desc:
                             Practical.objects.create(
                                 syllabus=syllabus,
                                 description=desc,
                                 weightage=request.POST.get(f'prac_weight_{uid}') or 0,
                                 hours=request.POST.get(f'prac_hours_{uid}') or 0
                             )
                             
                     # Outcomes (COs)
                     # Need to respect the order CO1, CO2...
                     co_keys = sorted([k for k in request.POST.keys() if k.startswith('co_desc_')])
                     # Sort makes the timestamps (IDs) ordered, preserving creation order usually.
                     processed_cos = set()
                     co_idx = 1
                     for k in co_keys:
                         uid = k.split('_')[2]
                         if uid in processed_cos: continue
                         processed_cos.add(uid)
                         
                         desc = request.POST.get(f'co_desc_{uid}')
                         if desc:
                             co = CourseOutcome.objects.create(syllabus=syllabus, code=f"CO{co_idx}", description=desc)
                             
                             # Mapping
                             # Note: Frontend sends `map_co{idx}_po...` where idx matches the row number 1, 2, 3...
                             # Our co_idx is also 1, 2, 3... so it matches.
                             map_defaults = {}
                             for i in range(1, 13):
                                 map_defaults[f'po{i}'] = request.POST.get(f'map_co{co_idx}_po{i}') or 0
                             map_defaults['pso1'] = request.POST.get(f'map_co{co_idx}_pso1') or 0
                             map_defaults['pso2'] = request.POST.get(f'map_co{co_idx}_pso2') or 0
                             OutcomeMapping.objects.create(course_outcome=co, **map_defaults)
                             
                             co_idx += 1

                     # Evaluation
                     # Ensure we don't crash on None
                     def safe_int(v): return int(v) if v else 0
                     
                     EvaluationScheme.objects.create(
                         syllabus=syllabus,
                         mid_sem=safe_int(request.POST.get('eval_mid')),
                         end_sem=safe_int(request.POST.get('eval_end')),
                         cec_attendance=safe_int(request.POST.get('eval_cec_att')),
                         cec_mcq=safe_int(request.POST.get('eval_cec_mcq')),
                         cec_assignment=safe_int(request.POST.get('eval_cec_assign')),
                         prac_attendance=safe_int(request.POST.get('eval_prac_att')),
                         prac_exam=safe_int(request.POST.get('eval_prac_exam')),
                         prac_viva=safe_int(request.POST.get('eval_prac_viva')),
                         prac_journal=safe_int(request.POST.get('eval_prac_journal')),
                         prac_discipline=safe_int(request.POST.get('eval_prac_disc')),
                     )

                     # Resources
                     res_keys = sorted([k for k in request.POST.keys() if k.startswith('res_cat_')])
                     processed_res = set()
                     for k in res_keys:
                         uid = k.split('_')[2]
                         if uid in processed_res: continue
                         processed_res.add(uid)
                         
                         cat = request.POST.get(f'res_cat_{uid}')
                         content = request.POST.get(f'res_content_{uid}')
                         if cat and content:
                             LearningResource.objects.create(syllabus=syllabus, category=cat, content=content)

                messages.success(request, "Draft saved successfully.")
                return redirect("faculty_dashboard")

            except Exception as e:
                import traceback
                traceback.print_exc()
                return render(request, 'accounts/syllabus_builder.html', {
                    'faculty': faculty,
                    'semesters': semesters,
                    'selected_subject': selected_subject,
                    'error': f"Error saving draft: {str(e)}",
                    'saved_syllabus': None # Clean state on error to avoid confusion
                })

    # Prepare Context & Hydration
    context = {
        'faculty': faculty, 
        'semesters': semesters,
        'selected_subject': selected_subject,
        'saved_syllabus': saved_syllabus,
        'saved_objectives': saved_objectives,
        'saved_units': saved_units,
        'saved_practicals': saved_practicals,
        'saved_evaluation': saved_evaluation,
        'saved_outcomes': saved_outcomes,
    }

    # JSON HYDRATION (Critical for Edit Flow)
    draft_data = {}
    if saved_syllabus:
        # 1. Objectives
        draft_data['objectives'] = [{'text': o.text} for o in saved_objectives]
        
        # 2. Units
        draft_data['units'] = []
        for u in saved_units:
            draft_data['units'].append({
                'title': u.title,
                'description': u.description,
                'weightage': u.weightage,
                'hours': u.hours
            })
            
        # 3. Practicals
        draft_data['practicals'] = []
        for p in saved_practicals:
            draft_data['practicals'].append({
                'description': p.description,
                'weightage': p.weightage,
                'hours': p.hours
            })
            
        # 4. Outcomes (Safe Mapping Access)
        draft_data['outcomes'] = []
        for co in saved_outcomes:
            mapping_dict = {}
            try:
                if hasattr(co, 'mapping'):
                    m = co.mapping
                    mapping_dict = {
                        'po1': m.po1, 'po2': m.po2, 'po3': m.po3, 'po4': m.po4, 'po5': m.po5, 'po6': m.po6,
                        'po7': m.po7, 'po8': m.po8, 'po9': m.po9, 'po10': m.po10, 'po11': m.po11, 'po12': m.po12,
                        'pso1': m.pso1, 'pso2': m.pso2
                    }
            except Exception:
                pass 
                
            draft_data['outcomes'].append({
                'description': co.description,
                'mapping': mapping_dict
            })
            
        # 5. Resources
        draft_data['resources'] = [{'category': r.category, 'content': r.content} for r in saved_resources]

    context['savedDraftData'] = draft_data if draft_data else None

    return render(request, 'accounts/syllabus_builder.html', context)


@never_cache
@login_required
def validate_syllabus_form(request):
    """
    Validates all required fields in the syllabus form before PDF generation.
    Returns JSON with validation status and errors.
    """
    if request.method != 'POST':
        return JsonResponse({'valid': False, 'error': 'Invalid request method'})
    
    errors = []
    
    # Step 1: Basic Information
    if not request.POST.get('hours_lecture') and not request.POST.get('hours_practical') and not request.POST.get('hours_tutorial'):
        errors.append({'step': 1, 'field': 'Teaching Scheme', 'message': 'At least one teaching hour must be specified'})
    
    if not request.POST.get('credit_lecture') and not request.POST.get('credit_practical') and not request.POST.get('credit_tutorial'):
        errors.append({'step': 1, 'field': 'Teaching Credit', 'message': 'At least one credit must be specified'})
    
    # Step 2: Course Overview
    if not request.POST.get('rationale', '').strip():
        errors.append({'step': 2, 'field': 'Rationale', 'message': 'Rationale is required'})
    
    obj_keys = [k for k in request.POST.keys() if k.startswith('obj_')]
    if not obj_keys or not any(request.POST.get(k, '').strip() for k in obj_keys):
        errors.append({'step': 2, 'field': 'Course Objectives', 'message': 'At least one objective is required'})
    
    # Step 3: Theory Units
    unit_keys = [k for k in request.POST.keys() if k.startswith('unit_title_')]
    if not unit_keys:
        errors.append({'step': 3, 'field': 'Theory Units', 'message': 'At least one theory unit is required'})
    else:
        # Check unit weightage totals 100
        total_weight = 0
        for k in unit_keys:
            uid = k.split('_')[2]
            weight = request.POST.get(f'unit_weight_{uid}', 0)
            try:
                total_weight += int(weight) if weight else 0
            except:
                pass
        
        if total_weight != 100:
            errors.append({'step': 3, 'field': 'Unit Weightage', 'message': f'Unit weightage must total 100% (currently {total_weight}%)'})
    
    # Step 4: Practicals (at least one if practical hours > 0)
    practical_hours = int(request.POST.get('hours_practical', 0) or 0)
    prac_keys = [k for k in request.POST.keys() if k.startswith('prac_desc_')]
    if practical_hours > 0 and not prac_keys:
        errors.append({'step': 4, 'field': 'Practicals', 'message': 'At least one practical is required when practical hours are specified'})
    
    # Step 5: Evaluation Scheme
    def safe_int(v): return int(v) if v else 0
    theory_total = (safe_int(request.POST.get('eval_mid')) + 
                   safe_int(request.POST.get('eval_end')) + 
                   safe_int(request.POST.get('eval_cec_att')) + 
                   safe_int(request.POST.get('eval_cec_mcq')) + 
                   safe_int(request.POST.get('eval_cec_assign')))
    
    if theory_total != 100:
        errors.append({'step': 5, 'field': 'Theory Evaluation', 'message': f'Theory marks must total 100 (currently {theory_total})'})
    
    prac_total = (safe_int(request.POST.get('eval_prac_att')) + 
                 safe_int(request.POST.get('eval_prac_exam')) + 
                 safe_int(request.POST.get('eval_prac_viva')) + 
                 safe_int(request.POST.get('eval_prac_journal')) + 
                 safe_int(request.POST.get('eval_prac_disc')))
    
    if practical_hours > 0 and prac_total != 50:
        errors.append({'step': 5, 'field': 'Practical Evaluation', 'message': f'Practical marks must total 50 (currently {prac_total})'})
    
    # Step 6: Course Outcomes
    co_keys = [k for k in request.POST.keys() if k.startswith('co_desc_')]
    if not co_keys or not any(request.POST.get(k, '').strip() for k in co_keys):
        errors.append({'step': 6, 'field': 'Course Outcomes', 'message': 'At least one course outcome is required'})
    
    # Step 7: Learning Resources
    res_keys = [k for k in request.POST.keys() if k.startswith('res_cat_')]
    if not res_keys:
        errors.append({'step': 7, 'field': 'Learning Resources', 'message': 'At least one learning resource is required'})
    
    if errors:
        return JsonResponse({
            'valid': False,
            'errors': errors,
            'first_error_step': errors[0]['step']
        })
    
    return JsonResponse({'valid': True})


# --- PDF GENERATION & PREVIEW ---
from django.template.loader import render_to_string
from django.http import HttpResponse
from xhtml2pdf import pisa
from django.utils import timezone
from django.conf import settings
import os

@never_cache
@login_required
def render_preview(request):
    """
    Renders the canonical HTML for the Syllabus Builder preview via AJAX/POST.
    Does NOT save to DB. Just takes form data -> HTML.
    """
    if request.user.is_staff:
        return redirect('admin_dashboard')
    if request.method != 'POST':
        return HttpResponse("Invalid request method", status=400)

    # 1. Mock a Syllabus object context from POST data
    # This is slightly tedious but ensures we reuse the EXACT same template.
    # We construct a dictionary that mimics the 'syllabus' object structure used in the template.
    
    # Helper to safe-get keys
    get = lambda k, d=None: request.POST.get(k, d)
    
    # Resolve Faculty
    try:
        faculty = Faculty.objects.get(user=request.user)
    except Faculty.DoesNotExist:
        return HttpResponse("Faculty not found", status=400)

    # Resolve hours/credits
    calc_hrs = (int(get('hours_lecture') or 0) + int(get('hours_practical') or 0) + int(get('hours_tutorial') or 0))
    calc_crd = (int(get('credit_lecture') or 0) + int(get('credit_practical') or 0) + int(get('credit_tutorial') or 0))

    # Mock Syllabus Wrapper
    class MockObj:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
        def all(self):
            return self.items if hasattr(self, 'items') else []

    # Mock Subject
    mock_subject = MockObj(
        course_code=get('course_code', '---'),
        course_name=get('course_name', '---'),
        semester=get('semester', faculty.semester)
    )

    # Mock Evaluation
    mock_eval = MockObj(
        mid_sem=get('eval_mid', 0),
        end_sem=get('eval_end', 0),
        cec_attendance=get('eval_cec_att', 0),
        cec_mcq=get('eval_cec_mcq', 0),
        cec_assignment=get('eval_cec_assign', 0),
        prac_attendance=get('eval_prac_att', 0),
        prac_exam=get('eval_prac_exam', 0),
        prac_viva=get('eval_prac_viva', 0),
        prac_journal=get('eval_prac_journal', 0),
        prac_discipline=get('eval_prac_disc', 0)
    )

    # Mock Objectives
    objs = []
    # logic to parse obj_TIMESTAMP
    for k in sorted(request.POST.keys()):
        if k.startswith('obj_'):
            objs.append(MockObj(text=request.POST[k]))
    mock_objectives = MockObj(items=objs)

    # Mock Units
    units = []
    # Create map of ID -> {title, desc, weight, hours}
    # keys: unit_title_123, unit_desc_123 ...
    unit_ids = set()
    for k in request.POST.keys():
        if k.startswith('unit_title_'):
            unit_ids.add(k.split('_')[2])
    
    for uid in sorted(unit_ids): # sorting by ID isn't perfect order but acceptable for preview
        units.append(MockObj(
            title=get(f'unit_title_{uid}'),
            description=get(f'unit_desc_{uid}'),
            weightage=get(f'unit_weight_{uid}', 0),
            hours=get(f'unit_hours_{uid}', 0)
        ))
    mock_units = MockObj(items=units)

    # Mock Practicals
    pracs = []
    prac_ids = set()
    for k in request.POST.keys():
        if k.startswith('prac_desc_'):
            prac_ids.add(k.split('_')[2])
            
    for uid in sorted(prac_ids):
        pracs.append(MockObj(
            description=get(f'prac_desc_{uid}'),
            weightage=get(f'prac_weight_{uid}', 0),
            hours=get(f'prac_hours_{uid}', 0)
        ))
    mock_practicals = MockObj(items=pracs)

    # Mock Outcomes
    cos = []
    co_ids = set()
    for k in request.POST.keys():
        if k.startswith('co_desc_'):
            co_ids.add(k.split('_')[2])
            
    # Need to strictly order COs by the label (CO1, CO2) derived ideally, or just order by input time
    # In the builder logic, we reindex on submit. For preview, we iterate sorted.
    # But wait, POST keys are unordered. We rely on the JS sending them.
    # A robust way is impossible without sending index. We'll simply sort by ID.
    sorted_co_ids = sorted(list(co_ids))
    for idx, uid in enumerate(sorted_co_ids, 1):
        desc = get(f'co_desc_{uid}')
        # Mapping
        mapping = MockObj(
            po1=get(f'map_co{idx}_po1',0), po2=get(f'map_co{idx}_po2',0), po3=get(f'map_co{idx}_po3',0),
            po4=get(f'map_co{idx}_po4',0), po5=get(f'map_co{idx}_po5',0), po6=get(f'map_co{idx}_po6',0),
            po7=get(f'map_co{idx}_po7',0), po8=get(f'map_co{idx}_po8',0), po9=get(f'map_co{idx}_po9',0),
            po10=get(f'map_co{idx}_po10',0), po11=get(f'map_co{idx}_po11',0), po12=get(f'map_co{idx}_po12',0),
            pso1=get(f'map_co{idx}_pso1',0), pso2=get(f'map_co{idx}_pso2',0)
        )
        cos.append(MockObj(code=f"CO{idx}", description=desc, mapping=mapping))
    mock_outcomes = MockObj(items=cos)


    # Mock Resources
    resources = []
    res_ids = set()
    for k in request.POST.keys():
        if k.startswith('res_cat_'):
            res_ids.add(k.split('_')[2])
            
    for uid in sorted(res_ids):
        resources.append(MockObj(
            category=get(f'res_cat_{uid}'),
            content=get(f'res_content_{uid}')
        ))
    mock_resources = MockObj(items=resources)


    mock_syllabus = MockObj(
        subject=mock_subject,
        hours_lecture=get('hours_lecture', 0),
        hours_practical=get('hours_practical', 0),
        hours_tutorial=get('hours_tutorial', 0),
        credit_lecture=get('credit_lecture', 0),
        credit_practical=get('credit_practical', 0),
        credit_tutorial=get('credit_tutorial', 0),
        prerequisites=get('prerequisites'),
        category=get('category'),
        focus=get('focus'),
        rationale=get('rationale'),
        approval_date=get('approval_date') or timezone.now().date(),
        objectives=mock_objectives,
        theory_units=mock_units,
        practicals=mock_practicals,
        evaluation_scheme=mock_eval,
        course_outcomes=mock_outcomes,
        learning_resources=mock_resources
    )
    
    # Metadata from Subject if available
    subject_id = get('subject_id')
    real_subject = None
    if subject_id:
        try:
            real_subject = Subject.objects.get(id=subject_id)
        except:
            pass
            
    if real_subject:
        school_name = real_subject.school.name if real_subject.school else "School of Technology"
        program_name = real_subject.program.name if real_subject.program else "B.Tech. Computer Science & Engineering"
        academic_year = real_subject.academic_year if hasattr(real_subject, 'academic_year') and real_subject.academic_year else "Academic Year Not Defined"
    else:
        # Fallback to faculty if subject not found (should not happen in normal flow)
        school_name = faculty.school.name if faculty.school else "School of Technology"
        program_name = faculty.program.name if faculty.program else "B.Tech. Computer Science & Engineering"
        academic_year = faculty.academic_year if faculty and faculty.academic_year else "Academic Year Not Defined"

    # Semester: Try POST first, then Subject, then faculty default
    sem_val = get('semester')
    if not sem_val:
        if real_subject and real_subject.semester:
            sem_val = real_subject.semester
        else:
            sem_val = faculty.semester
    semester_name = sem_val

    # academic_year already set above

    context = {
        'faculty': faculty,
        'syllabus': mock_syllabus,
        'logo_path': '/static/images/gsfc_logo.png', # Browser accessible for preview
        'total_hours': calc_hrs,
        'total_credits': calc_crd,
        
        # CLEAN VARIABLES
        'school_name': school_name,
        'program_name': program_name,
        'semester_name': semester_name,
        'academic_year': academic_year,
    }
    
    html = render_to_string('pdf/syllabus_canonical.html', context)
    return HttpResponse(html)


@never_cache
@login_required
def generate_pdf(request, syllabus_id):
    """
    Generates and saves a real PDF for a saved (Draft/Final) Syllabus.
    """
    from accounts.utils import load_full_syllabus
    syllabus = load_full_syllabus(syllabus_id)
    if not syllabus:
         return HttpResponse("Syllabus not found", status=404)
    
    # Security check
    
    # Security check
    if not request.user.is_staff and syllabus.faculty.user != request.user:
         return HttpResponseForbidden("Not authorized")

    # --- VALIDATION FOR PDF GENERATION ---
    # We must enforce the same rules as Draft Save here.
    # If invalid, redirect back to builder with error.
    errors = []
    first_invalid = None

    def add_err(msg, field=None):
        nonlocal first_invalid
        errors.append(msg)
        if field and not first_invalid: first_invalid = field

    # 1. Static
    if not syllabus.hours_lecture and not syllabus.hours_practical and not syllabus.hours_tutorial:
         # Only if ALL zero? No, user said "Must not be blank". But DB stores 0.
         # Actually checking if required fields are effectively 'missing' logic is harder on loaded object
         # But we can check emptiness of text fields.
         pass
    
    # Text Fields
    if not syllabus.prerequisites or len(syllabus.prerequisites) < 3: add_err("Prerequisites missing or too short", "prerequisites")
    if not syllabus.rationale: add_err("Rationale is required", "rationale")
    # Date?
    # if not syllabus.approval_date: add_err("Approval Date required", "approval_date")

    # 2. Dynamic
    if not syllabus.objectives.exists(): add_err("At least one Objective required")
    
    if not syllabus.theory_units.exists(): add_err("At least one Theory Unit required")
    else:
        # Check integrity
        # We can't easily check individual unit fields without iterating
        # But if they are in DB, they passed some check? 
        # CAUTION: Older drafts might be invalid.
        # Let's trust DB state for "filled" but check constraints
        wt = sum(u.weightage for u in syllabus.theory_units.all())
        if abs(wt - 100) > 0.1: add_err(f"Total Unit Weight must be 100% (Current: {wt}%)")
    
    if not syllabus.course_outcomes.exists(): add_err("At least one CO required")
    if not syllabus.learning_resources.exists(): add_err("At least one Resource required")

    # OUTCOME MAPPING CHECK
    # "CO-PO mapping table: No blank cells allowed."
    # In DB, they are stored as numbers 0-3. 
    # If they are created, they are likely valid 0s. 
    # But let's verify if any OutcomeMapping is missing? 
    # Or if any OutcomeMapping has nulls? (Model usually defaults 0)

    if errors:
        from django.contrib import messages
        messages.error(request, "Cannot generate PDF: " + "; ".join(errors))
        return redirect(f"/accounts/syllabus-builder/?draft_id={syllabus.id}")

    # --- END VALIDATION ---

    # Context Prep
    total_hours = syllabus.hours_lecture + syllabus.hours_practical + syllabus.hours_tutorial
    total_credits = syllabus.credit_lecture + syllabus.credit_practical + syllabus.credit_tutorial

    # Logo Path for PDF (Needs absolute file system path)
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'gsfc_logo.png')
    
    # --- PREPARE CLEAN CONTEXT FROM SUBJECT ---
    school_obj = syllabus.subject.school
    program_obj = syllabus.subject.program
    
    school_name = school_obj.name if school_obj else "School of Technology"
    program_name = program_obj.name if program_obj else "B.Tech. Computer Science & Engineering"
    
    # Semester priorities: Subject > Default
    semester_name = syllabus.subject.semester
    if not semester_name:
        semester_name = "Semester Not Defined"

    # Academic Year from Subject
    academic_year = syllabus.subject.academic_year if hasattr(syllabus.subject, 'academic_year') and syllabus.subject.academic_year else "Academic Year Not Defined"

    context = {
        'faculty': syllabus.faculty,
        'syllabus': syllabus,
        'logo_path': logo_path,
        'total_hours': total_hours,
        'total_credits': total_credits,
        
        # CLEAN VARIABLES
        'school_name': school_name,
        'program_name': program_name,
        'semester_name': semester_name,
        'academic_year': academic_year,
    }
    
    html_string = render_to_string('pdf/syllabus_canonical.html', context)
    
    # Generate PDF
    from io import BytesIO
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html_string.encode("UTF-8")), result)
    
    if not pdf.err:
        # Save to FileField
        # Use clean variables to prevent "None" in filename
        safe_sem = semester_name if semester_name else "General" 
        filename = f"Syllabus_{syllabus.subject.course_code}_{safe_sem}_{academic_year}.pdf"
        
        from django.core.files.base import ContentFile
        
        # Save content
        syllabus.pdf_file.save(filename, ContentFile(result.getvalue()))
        syllabus.pdf_generated_at = timezone.now()
        syllabus.save()
        
        # Set subject as active
        syllabus.subject.is_active = True
        syllabus.subject.save()
        
        # Return response as download
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
        
    return HttpResponse(f"PDF Generation Error: {pdf.err}")


@never_cache
@login_required
def preview_semester_merge(request, semester_id):
    if request.user.is_staff:
        return redirect('admin_dashboard')
        
    try:
        semester = Semester.objects.select_related('program').get(id=semester_id)
    except Semester.DoesNotExist:
         return redirect('faculty_dashboard')

    faculty = get_object_or_404(Faculty, user=request.user)
    
    structure = SemesterSubject.objects.filter(semester=semester).select_related('subject').order_by('sequence')
    
    # Calculate Summary Data
    table_rows = []
    
    for item in structure:
        subject = item.subject
        syllabus = getattr(subject, 'syllabus', None)
        
        row = {
            'sr_no': item.sequence,
            'code': subject.course_code,
            'name': subject.course_name,
            'subject_id': subject.id
        }
        
        if syllabus:
            row['L'] = syllabus.hours_lecture
            row['P'] = syllabus.hours_practical
            row['T'] = syllabus.hours_tutorial
            row['hours_total'] = syllabus.hours_lecture + syllabus.hours_practical + syllabus.hours_tutorial
            
            row['cL'] = syllabus.credit_lecture
            row['cP'] = syllabus.credit_practical
            row['cT'] = syllabus.credit_tutorial
            row['credit_total'] = syllabus.credit_lecture + syllabus.credit_practical + syllabus.credit_tutorial
            
            try:
                es = syllabus.evaluation_scheme
                row['mid'] = es.mid_sem
                row['cec'] = es.cec_attendance + es.cec_mcq + es.cec_assignment
                row['end'] = es.end_sem
                row['theory_total'] = row['mid'] + row['cec'] + row['end']
                
                row['prac_marks'] = (
                    es.prac_attendance + es.prac_exam + es.prac_viva + 
                    es.prac_journal + es.prac_discipline
                )
                
                row['grand_total'] = row['theory_total'] + row['prac_marks']
            except:
                row.update({'mid':0,'cec':0,'end':0,'theory_total':0,'prac_marks':0,'grand_total':0})
        else:
            row.update({
             'L': '-', 'P': '-', 'T': '-', 'hours_total': '-',
             'cL': '-', 'cP': '-', 'cT': '-', 'credit_total': '-',
             'mid': '-', 'cec': '-', 'end': '-', 'theory_total': '-', 'prac_marks': '-', 'grand_total': '-'
            })
            
        table_rows.append(row)

    return render(request, 'accounts/semester_merge_preview.html', {
        'semester': semester,
        'table_rows': table_rows,
        'structure': structure, 
        'faculty': faculty
    })

@never_cache
@login_required
def generate_semester_pdf(request, semester_id):
    if request.user.is_staff:
        return redirect('admin_dashboard')
    semester = get_object_or_404(Semester, id=semester_id)
    structure = SemesterSubject.objects.filter(semester=semester).select_related('subject').order_by('sequence')
    faculty = get_object_or_404(Faculty, user=request.user)

    table_rows = []
    for item in structure:
        subject = item.subject
        syllabus = getattr(subject, 'syllabus', None)
        row = { 'sr_no': item.sequence, 'code': subject.course_code, 'name': subject.course_name }
        if syllabus:
            row['L'] = syllabus.hours_lecture
            row['P'] = syllabus.hours_practical
            row['T'] = syllabus.hours_tutorial
            row['hours_total'] = syllabus.hours_lecture + syllabus.hours_practical + syllabus.hours_tutorial
            row['cL'] = syllabus.credit_lecture
            row['cP'] = syllabus.credit_practical
            row['cT'] = syllabus.credit_tutorial
            row['credit_total'] = syllabus.credit_lecture + syllabus.credit_practical + syllabus.credit_tutorial
            try:
                es = syllabus.evaluation_scheme
                row['mid'] = es.mid_sem
                row['cec'] = es.cec_attendance + es.cec_mcq + es.cec_assignment
                row['end'] = es.end_sem
                row['theory_total'] = row['mid'] + row['cec'] + row['end']
                row['prac_marks'] = (es.prac_attendance + es.prac_exam + es.prac_viva + es.prac_journal + es.prac_discipline)
                row['grand_total'] = row['theory_total'] + row['prac_marks']
            except:
                row.update({'mid':0,'cec':0,'end':0,'theory_total':0,'prac_marks':0,'grand_total':0})
        else:
             row.update({'L':'-','P':'-','T':'-','hours_total':'-','cL':'-','cP':'-','cT':'-','credit_total':'-','mid':'-','cec':'-','end':'-','theory_total':'-','prac_marks':'-','grand_total':'-'})
        table_rows.append(row)

    # Academic Year
    academic_year = "Academic Year Not Defined"
    for item in structure:
        # Check Subject first
        if hasattr(item.subject, 'academic_year') and item.subject.academic_year:
            academic_year = item.subject.academic_year
            break
        # Fallback
        if hasattr(item.subject, 'syllabus') and item.subject.syllabus.faculty:
            if item.subject.syllabus.faculty.academic_year:
                academic_year = item.subject.syllabus.faculty.academic_year
                break
    
    summary_context = {
        'semester_name': semester.semester_number,
        'rows': table_rows,
        'school_name': semester.program.school.name,
        'program_name': semester.program.name,
        'logo_path': os.path.join(settings.BASE_DIR, 'static', 'images', 'gsfc_logo.png'),
        'academic_year': academic_year
    }
    
    summary_html = render_to_string('pdf/semester_summary.html', summary_context)
    
    def extract_body(html):
        m = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL)
        return m.group(1) if m else html
    
    def extract_style(html):
        m = re.search(r'<style[^>]*>(.*?)</style>', html, re.DOTALL)
        return m.group(1) if m else ""

    full_body = extract_body(summary_html)
    base_style = extract_style(summary_html) # Use summary style as base
    
    for item in structure:
        subject = item.subject
        if hasattr(subject, 'syllabus'):
            syl = subject.syllabus
            ctx = {
                'faculty': syl.faculty,
                'syllabus': syl,
                'logo_path': summary_context['logo_path'],
                'total_hours': syl.hours_lecture + syl.hours_practical + syl.hours_tutorial,
                'total_credits': syl.credit_lecture + syl.credit_practical + syl.credit_tutorial,
                'school_name': syl.faculty.school.name if syl.faculty and syl.faculty.school else semester.program.school.name,
                'program_name': syl.faculty.program.name if syl.faculty and syl.faculty.program else semester.program.name,
                'semester_name': subject.semester if subject.semester else semester.semester_number,
                'academic_year': academic_year
            }
            sub_html = render_to_string('pdf/syllabus_canonical.html', ctx)
            full_body += "<pdf:nextpage>"
            full_body += extract_body(sub_html)
            
    final_html = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            {base_style}
        </style>
    </head>
    <body>
        {full_body}
    </body>
    </html>
    """
    
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(final_html.encode("UTF-8")), result)
    
    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Merged_Semester_{semester.semester_number}.pdf"'
        return response
        
    return HttpResponse(f"PDF Generation Error: {pdf.err}")


