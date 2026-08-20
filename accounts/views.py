from django.shortcuts import render, redirect, get_object_or_404
import re
import os
from datetime import datetime
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
            # 1. Prefer a syllabus owned by THIS faculty
            draft = Syllabus.objects.filter(faculty=faculty, subject=sub).first()

            # 2. Fallback: any existing syllabus on the subject (created by another faculty)
            #    so we never show "Create New Syllabus" when one already exists.
            other_syllabus = None
            if draft is None:
                other_syllabus = Syllabus.objects.filter(subject=sub).first()

            effective = draft or other_syllabus
            subjects_data.append({
                'subject': sub,
                'has_draft': effective is not None,
                'draft_id': effective.id if effective else None,
                'has_pdf': bool(effective and effective.pdf_file),
                'pdf_url': effective.pdf_file.url if (effective and effective.pdf_file) else None,
                'is_own': draft is not None,       # True = this faculty owns it (can edit)
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
        drafts = Syllabus.objects.filter(
            faculty=faculty, status='draft'
        ).select_related('subject').order_by('-updated_at')
    except Faculty.DoesNotExist:
        faculty = None
        drafts = []

    # Task 13.5: annotate each draft with completeness data (Requirements: 7.1, 7.4, 7.5)
    drafts_data = []
    for draft in drafts:
        try:
            complete, missing = draft.is_complete()
            pct = draft.get_completion_percentage()
        except Exception:
            complete, missing, pct = False, [], 0
        drafts_data.append({
            'draft': draft,
            'is_complete': complete,
            'pct': pct,
            'missing': missing,
        })

    return render(request, 'accounts/faculty_drafts.html', {
        'drafts': drafts,          # kept for backwards compat
        'drafts_data': drafts_data,
    })


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
        # Task 9.1 – extract current slide for progressive validation
        try:
            current_slide = int(request.POST.get('current_slide', 8))
        except (ValueError, TypeError):
            current_slide = 8

        if save_mode == 'draft':
            # --- Task 9.1: Progressive slide validation ---
            # SlideValidator expects structured keys. Convert raw POST → structured dict.
            from .validators import SlideValidator
            def _build_slide_data(post):
                """Map raw HTML form POST to the structured keys SlideValidator expects.
                post.get(k) returns a scalar string (not a list) on Django QueryDict.
                """
                # Slide 1: scalar fields that validators call float() on
                slide1_fields = [
                    'hours_lecture', 'hours_practical', 'hours_tutorial',
                    'credit_lecture', 'credit_practical', 'credit_tutorial',
                    'prerequisites', 'category', 'focus', 'course_focus',
                ]
                d = {f: post.get(f, '') for f in slide1_fields}
                d['focus'] = d.get('focus') or 'Employability'
                d['course_focus'] = d.get('course_focus') or 'Employability'
                # Slide 2: objectives list
                obj_keys = sorted([
                    k for k in post if k.startswith('obj_')
                    and not k.startswith('obj_domain_')
                    and not k.startswith('obj_subdomain_')
                ])
                d['objectives'] = [
                    post.get(k, '') for k in obj_keys
                    if post.get(k, '').strip()
                ]
                # Slide 3: theory_units list
                u_ids = sorted(set(k.split('_')[2] for k in post if k.startswith('unit_title_')))
                d['theory_units'] = [
                    {'title': post.get(f'unit_title_{uid}', ''),
                     'weightage': post.get(f'unit_weight_{uid}', post.get(f'unit_weightage_{uid}', 0))}
                    for uid in u_ids if post.get(f'unit_title_{uid}', '').strip()
                ]
                # Slide 5: evaluation (any truthy value signals presence)
                eval_keys = ['eval_mid', 'eval_end', 'eval_cec_att', 'eval_cec_mcq', 'eval_cec_assign']
                d['evaluation'] = {k: post.get(k, 0) for k in eval_keys if post.get(k)}
                # Slide 6: course_outcomes + outcome_mappings
                co_keys = sorted([k for k in post if k.startswith('co_desc_')])
                d['course_outcomes'] = [
                    post.get(k, '') for k in co_keys if post.get(k, '').strip()
                ]
                if any(k.startswith('map_co') for k in post):
                    d['outcome_mappings'] = {'present': True}
                # Slide 7: learning_resources
                res_ids = sorted(set(k.split('_')[2] for k in post if k.startswith('res_cat_')))
                d['learning_resources'] = [
                    {'category': post.get(f'res_cat_{rid}', '')}
                    for rid in res_ids if post.get(f'res_cat_{rid}', '').strip()
                ]
                # Slide 8: rationale + approval_date
                d['rationale'] = post.get('rationale', '')
                d['approval_date'] = post.get('approval_date', '')
                return d

            slide_data = _build_slide_data(request.POST)
            slide_is_valid, slide_errors, first_invalid_slide = (
                SlideValidator.validate_up_to_slide(current_slide, slide_data)
            )
            if not slide_is_valid:
                parts = []
                for slide_key, errs in slide_errors.items():
                    msgs = '; '.join(errs.values())
                    parts.append(f'{slide_key}: {msgs}')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'ok': False,
                        'error': 'Slide validation failed: ' + ' | '.join(parts),
                        'errors': slide_errors,
                        'current_slide': first_invalid_slide or current_slide,
                    }, status=400)
                context = {
                    'faculty': faculty,
                    'semesters': semesters,
                    'selected_subject': get_object_or_404(Subject, id=subject_id) if subject_id else None,
                    'saved_syllabus': None,
                    'savedDraftData': None,
                    'error': 'Slide validation failed: ' + ' | '.join(parts),
                    'first_invalid_field': None,
                    'current_slide': first_invalid_slide or current_slide,
                }
                return render(request, 'accounts/syllabus_builder.html', context)


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
                'prerequisites', 'category', 'focus', 'course_focus', 'rationale', 'approval_date'
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
            obj_keys = sorted([k for k in request.POST.keys() if k.startswith('obj_') and not k.startswith('obj_domain_') and not k.startswith('obj_subdomain_')])
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
                    if not (request.POST.get(f'unit_desc_{uid}', '') or request.POST.get(f'unit_description_{uid}', '')).strip(): add_error("All Unit Topics must be filled.", f'unit_desc_{uid}')
                    
                    # Numeric
                    err_w = check_num(request.POST.get(f'unit_weight_{uid}', request.POST.get(f'unit_weightage_{uid}', 0)), "Unit Weightage")
                    if err_w: add_error(err_w, f'unit_weight_{uid}')
                    err_h = check_num(request.POST.get(f'unit_hours_{uid}', 0), "Unit Hours")
                    if err_h: add_error(err_h, f'unit_hours_{uid}')
                
                # Total Weight Check
                total_weight = 0
                for k in unit_keys:
                    uid = k.split('_')[2]
                    try:
                        total_weight += float(request.POST.get(f'unit_weight_{uid}', request.POST.get(f'unit_weightage_{uid}', 0)))
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
                err_w = check_num(request.POST.get(f'prac_weight_{uid}', request.POST.get(f'prac_weightage_{uid}', 0)), "Practical Weightage")
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

            # Draft saves are progressive; final completeness is reported after
            # saving instead of blocking partial work here.
            errors = []
            first_invalid_field = None

            if errors:
                # --- HYDRATE FROM POST (ERROR STATE) ---
                draft_data = {}
                
                # Objectives
                draft_data['objectives'] = []
                for k in obj_keys:
                    uid = k[4:]
                    draft_data['objectives'].append({
                        'text': request.POST.get(k),
                        'domain': request.POST.get(f'obj_domain_{uid}', ''),
                        'subdomain': request.POST.get(f'obj_subdomain_{uid}', ''),
                    })
                
                # Units
                draft_data['units'] = []
                # Re-gather ids
                u_ids = sorted(list(set(k.split('_')[2] for k in unit_keys)))
                for uid in u_ids:
                    draft_data['units'].append({
                        'title': request.POST.get(f'unit_title_{uid}'),
                        'description': request.POST.get(f'unit_desc_{uid}', request.POST.get(f'unit_description_{uid}', '')),
                        'weightage': request.POST.get(f'unit_weight_{uid}', request.POST.get(f'unit_weightage_{uid}', '')),
                        'hours': request.POST.get(f'unit_hours_{uid}')
                    })

                # Practicals
                draft_data['practicals'] = []
                p_ids = sorted(list(set(k.split('_')[2] for k in prac_keys)))
                for uid in p_ids:
                    draft_data['practicals'].append({
                        'description': request.POST.get(f'prac_desc_{uid}'),
                        'weightage': request.POST.get(f'prac_weight_{uid}', request.POST.get(f'prac_weightage_{uid}', '')),
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

                     # --- Task 9.3: Optimistic locking via last_modified timestamp ---
                     client_last_modified = request.POST.get('last_modified')
                     existing = Syllabus.objects.filter(subject=subject).first()
                     if existing and client_last_modified:
                         try:
                             from django.utils.dateparse import parse_datetime
                             client_ts = parse_datetime(client_last_modified)
                             if client_ts and existing.updated_at and existing.updated_at > client_ts:
                                 raise Exception(
                                     'This syllabus was modified by someone else since you loaded it. '
                                     'Please reload and try again.'
                                 )
                         except ValueError:
                             pass  # Malformed timestamp; skip the check
                     
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
                     # 3. Update Fields — cast to proper Python types so the
                     # pre_save snapshot comparison never produces false positives.
                     syllabus.hours_lecture    = int(request.POST.get("hours_lecture") or 0)
                     syllabus.hours_practical  = int(request.POST.get("hours_practical") or 0)
                     syllabus.hours_tutorial   = int(request.POST.get("hours_tutorial") or 0)
                     syllabus.credit_lecture   = int(request.POST.get("credit_lecture") or 0)
                     syllabus.credit_practical = int(request.POST.get("credit_practical") or 0)
                     syllabus.credit_tutorial  = int(request.POST.get("credit_tutorial") or 0)
                     syllabus.prerequisites = request.POST.get("prerequisites", "")
                     syllabus.category     = request.POST.get("category", "Core")
                     syllabus.focus        = request.POST.get("focus", "Employability")
                     syllabus.course_focus = request.POST.get("course_focus", "Employability")

                     app_date_str = request.POST.get('approval_date', '').strip()
                     if app_date_str:
                         from django.utils.dateparse import parse_date
                         parsed = parse_date(app_date_str)
                         if parsed:
                             syllabus.approval_date = parsed
                     syllabus.rationale = request.POST.get("rationale", "")
                     from accounts.signals import set_current_user
                     set_current_user(request.user)
                     syllabus.save()

                     # --- Task 9.1: Update last_completed_slide ---
                     current_slide = int(request.POST.get('current_slide', 0))
                     if current_slide > syllabus.last_completed_slide:
                         syllabus.last_completed_slide = current_slide
                         Syllabus.objects.filter(pk=syllabus.pk).update(
                             last_completed_slide=current_slide
                         )

                     # ── Imports for suppression + audit ───────────────────
                     from accounts.signals import suppress_child_signals
                     from accounts.audit_logger import AuditLogger as _AL
                     _ip = _AL.get_client_ip(request)

                     def safe_int(v): return int(v) if v else 0

                     # ── Snapshot OLD child data before deletion ───────────
                     old_objs  = list(syllabus.objectives.values('text', 'blooms_domain', 'blooms_subdomain'))
                     old_units = list(syllabus.theory_units.values('title', 'description', 'weightage', 'hours'))
                     old_pracs = list(syllabus.practicals.values('description', 'weightage', 'hours'))
                     old_cos   = list(syllabus.course_outcomes.values('code', 'description'))
                     old_res   = list(syllabus.learning_resources.values('category', 'content'))
                     try:
                         _es = syllabus.evaluation_scheme
                         old_eval = {f: getattr(_es, f) for f in (
                             'mid_sem','end_sem','cec_attendance','cec_mcq','cec_assignment',
                             'prac_attendance','prac_exam','prac_viva','prac_journal','prac_discipline')}
                     except Exception:
                         old_eval = {}

                     # ── Suppress per-row signals during bulk cycle ────────
                     with suppress_child_signals():

                         # DELETE
                         syllabus.objectives.all().delete()
                         syllabus.theory_units.all().delete()
                         syllabus.practicals.all().delete()
                         syllabus.course_outcomes.all().delete()
                         if hasattr(syllabus, 'evaluation_scheme'):
                             try:
                                 syllabus.evaluation_scheme.delete()
                             except Exception:
                                 pass
                         syllabus.learning_resources.all().delete()

                         # RECREATE: Objectives
                         obj_keys = sorted([k for k in request.POST.keys()
                                            if k.startswith('obj_')
                                            and not k.startswith('obj_domain_')
                                            and not k.startswith('obj_subdomain_')])
                         objs = []
                         for k in obj_keys:
                             text = request.POST[k].strip()
                             if text:
                                 uid = k[4:]
                                 domain    = request.POST.get(f'obj_domain_{uid}', '').strip()
                                 subdomain = request.POST.get(f'obj_subdomain_{uid}', '').strip()
                                 objs.append(CourseObjective(
                                     syllabus=syllabus, text=text,
                                     blooms_domain=domain or None,
                                     blooms_subdomain=subdomain or None,
                                 ))
                         CourseObjective.objects.bulk_create(objs)

                         # RECREATE: Theory Units
                         unit_keys = sorted([k for k in request.POST.keys() if k.startswith('unit_title_')])
                         processed_units = set()
                         for k in unit_keys:
                             uid = k.split('_')[2]
                             if uid in processed_units: continue
                             processed_units.add(uid)
                             title = request.POST.get(f'unit_title_{uid}')
                             if title:
                                 TheoryUnit.objects.create(
                                     syllabus=syllabus, title=title,
                                     description=request.POST.get(f'unit_desc_{uid}', request.POST.get(f'unit_description_{uid}', '')),
                                     weightage=request.POST.get(f'unit_weight_{uid}', request.POST.get(f'unit_weightage_{uid}', 0)) or 0,
                                     hours=request.POST.get(f'unit_hours_{uid}') or 0
                                 )

                         # RECREATE: Practicals
                         prac_keys = sorted([k for k in request.POST.keys() if k.startswith('prac_desc_')])
                         processed_pracs = set()
                         for k in prac_keys:
                             uid = k.split('_')[2]
                             if uid in processed_pracs: continue
                             processed_pracs.add(uid)
                             desc = request.POST.get(f'prac_desc_{uid}')
                             if desc:
                                 Practical.objects.create(
                                     syllabus=syllabus, description=desc,
                                     weightage=request.POST.get(f'prac_weight_{uid}', request.POST.get(f'prac_weightage_{uid}', 0)) or 0,
                                     hours=request.POST.get(f'prac_hours_{uid}') or 0
                                 )

                         # RECREATE: Course Outcomes + Mappings
                         co_keys = sorted([k for k in request.POST.keys() if k.startswith('co_desc_')])
                         processed_cos = set()
                         co_idx = 1
                         for k in co_keys:
                             uid = k.split('_')[2]
                             if uid in processed_cos: continue
                             processed_cos.add(uid)
                             desc = request.POST.get(f'co_desc_{uid}')
                             if desc:
                                 co = CourseOutcome.objects.create(
                                     syllabus=syllabus, code=f'CO{co_idx}', description=desc)
                                 map_defaults = {f'po{i}': request.POST.get(f'map_co{co_idx}_po{i}') or 0 for i in range(1, 13)}
                                 OutcomeMapping.objects.create(course_outcome=co, **map_defaults)
                                 co_idx += 1

                         # RECREATE: Evaluation Scheme
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

                         # RECREATE: Learning Resources
                         res_keys = sorted([k for k in request.POST.keys() if k.startswith('res_cat_')])
                         processed_res = set()
                         for k in res_keys:
                             uid = k.split('_')[2]
                             if uid in processed_res: continue
                             processed_res.add(uid)
                             cat     = request.POST.get(f'res_cat_{uid}')
                             content = request.POST.get(f'res_content_{uid}')
                             if cat and content:
                                 LearningResource.objects.create(syllabus=syllabus, category=cat, content=content)

                     # ── ONE consolidated diff log per changed section ─────
                     new_objs  = list(syllabus.objectives.values('text', 'blooms_domain', 'blooms_subdomain'))
                     new_units = list(syllabus.theory_units.values('title', 'description', 'weightage', 'hours'))
                     new_pracs = list(syllabus.practicals.values('description', 'weightage', 'hours'))
                     new_cos   = list(syllabus.course_outcomes.values('code', 'description'))
                     new_res   = list(syllabus.learning_resources.values('category', 'content'))
                     try:
                         _es2 = syllabus.evaluation_scheme
                         new_eval = {f: getattr(_es2, f) for f in (
                             'mid_sem','end_sem','cec_attendance','cec_mcq','cec_assignment',
                             'prac_attendance','prac_exam','prac_viva','prac_journal','prac_discipline')}
                     except Exception:
                         new_eval = {}

                     for _model, _old, _new in [
                         ('CourseObjective',  old_objs,  new_objs),
                         ('TheoryUnit',       old_units, new_units),
                         ('Practical',        old_pracs, new_pracs),
                         ('CourseOutcome',    old_cos,   new_cos),
                         ('EvaluationScheme', old_eval,  new_eval),
                         ('LearningResource', old_res,   new_res),
                     ]:
                         if _old != _new:
                             _AL.log_change(
                                 syllabus=syllabus, user=request.user,
                                 ip_address=_ip, model_name=_model,
                                 record_id=syllabus.pk, field_name='',
                                 old_value=_old, new_value=_new,
                                 action_type='update',
                             )

                # --- Task 9.2 / 14.3: Post-save completeness status ---
                try:
                    is_done, missing = syllabus.is_complete()
                    pct = syllabus.get_completion_percentage()
                    if is_done:
                        msg = f'Draft saved successfully. Syllabus is complete ({pct}%) and ready for PDF generation.'
                    else:
                        missing_str = ', '.join(missing[:3])
                        more = f' (+{len(missing) - 3} more)' if len(missing) > 3 else ''
                        msg = f'Draft saved ({pct}% complete). Still missing: {missing_str}{more}.'
                except Exception:
                    is_done, pct, missing, msg = False, 0, [], 'Draft saved successfully.'

                # --- Task 14.2/14.4: AJAX save stays on slide; regular POST redirects ---
                is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                if is_ajax:
                    return JsonResponse({
                        'ok': True,
                        'message': msg,
                        'is_complete': is_done,
                        'pct': pct,
                        'missing': missing,
                        'syllabus_id': syllabus.pk,
                        'updated_at': syllabus.updated_at.isoformat(),
                    })
                messages.success(request, msg)
                return redirect('faculty_dashboard')

            except Exception as e:
                import traceback
                traceback.print_exc()
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                   return JsonResponse({'ok': False, 'error': str(e)}, status=400)
                return render(request, 'accounts/syllabus_builder.html', {
                   'faculty': faculty,
                   'semesters': semesters,
                   'selected_subject': selected_subject,
                   'error': f"Error saving draft: {str(e)}",
                   'saved_syllabus': None
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
        draft_data['objectives'] = [{
            'text': o.text,
            'domain': o.blooms_domain or '',
            'subdomain': o.blooms_subdomain or '',
        } for o in saved_objectives]
        
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
    for k in sorted(request.POST.keys()):
        if k.startswith('obj_') and not k.startswith('obj_domain_') and not k.startswith('obj_subdomain_'):
            uid = k[4:]
            objs.append(MockObj(
                text=request.POST[k],
                blooms_domain=request.POST.get(f'obj_domain_{uid}', ''),
                blooms_subdomain=request.POST.get(f'obj_subdomain_{uid}', ''),
            ))
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
            po10=get(f'map_co{idx}_po10',0), po11=get(f'map_co{idx}_po11',0), po12=get(f'map_co{idx}_po12',0)
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
        course_focus=get('course_focus'),
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

    # --- Task 10.1: Completeness check before PDF generation ---
    # Requirements: 6.1, 6.2, 6.5
    is_done, missing_fields = syllabus.is_complete()
    if not is_done:
        return JsonResponse(
            {
                'error': 'Cannot generate PDF: syllabus is incomplete.',
                'missing_fields': missing_fields,
            },
            status=400,
        )
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
    pdf = pisa.pisaDocument(BytesIO(html_string.encode('UTF-8')), result)

    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        course_code = syllabus.subject.course_code if syllabus.subject and syllabus.subject.course_code else str(syllabus_id)
        safe_code = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in course_code)
        response['Content-Disposition'] = (
            f'attachment; filename="Syllabus_{safe_code}.pdf"'
        )
        return response

    return HttpResponse(f'PDF Generation Error: {pdf.err}')


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
    syllabi_list = []
    
    for item in structure:
        subject = item.subject
        syllabus = getattr(subject, 'syllabus', None)
        _raw_sem = str(subject.semester) if hasattr(subject, 'semester') and subject.semester else ''
        row = { 'sr_no': item.sequence, 'code': subject.course_code, 'name': subject.course_name,
                'sem': _raw_sem.replace('Semester ', '').replace('semester ', '').strip() }
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
                'semester_name': subject.semester if subject.semester else "Semester Not Defined"
            })
            
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
             row.update({'L':'-','P':'-','T':'-','hours_total':'-','cL':'-','cP':'-','cT':'-','credits_total':'-','mid':'-','cec':'-','end':'-','theory_total':'-','prac_marks':'-','grand_total':'-'})
        table_rows.append(row)

    # Academic Year
    academic_year = "Academic Year Not Defined"
    for item in structure:
        if hasattr(item.subject, 'academic_year') and item.subject.academic_year:
            academic_year = item.subject.academic_year
            break
        if hasattr(item.subject, 'syllabus') and item.subject.syllabus.faculty:
            if item.subject.syllabus.faculty.academic_year:
                academic_year = item.subject.syllabus.faculty.academic_year
                break
    
    school_name = semester.program.school.name
    program_name = semester.program.name
    
    context = {
        'school_name': school_name,
        'program_name': program_name,
        'academic_year': academic_year,
        'logo_path': os.path.join(settings.BASE_DIR, 'static', 'images', 'gsfc_logo.png'),
        'generated_date': datetime.now().strftime('%B %d, %Y'),
        'summary_rows': table_rows,
        'syllabi_list': syllabi_list,
        'is_full_program': False,
        'branch_name': ''
    }

    html_string = render_to_string('pdf/combined_syllabus.html', context)
    
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html_string.encode("UTF-8")), result)
    
    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Merged_Semester_{semester.semester_number}.pdf"'
        return response
        
    return HttpResponse(f"PDF Generation Error: {pdf.err}")


# -----------------------------------------------------------------------
# Task 8.1 - audit_log_list
# -----------------------------------------------------------------------

@login_required
def audit_log_list(request):
    """
    Paginated, filterable list of SyllabusEditLog entries.
    Role-gated: admin sees all, faculty sees only their assigned subjects.
    GET params: subject, date_from, date_to (YYYY-MM-DD), user, page.
    Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.4
    """
    from django.core.paginator import Paginator
    from django.utils.dateparse import parse_date
    from django.utils.timezone import make_aware
    from datetime import datetime, time as dt_time
    from .access_controller import AuditLogAccessController

    def _date_from(s):
        d = parse_date(s) if s else None
        return make_aware(datetime.combine(d, dt_time.min)) if d else None

    def _date_to(s):
        d = parse_date(s) if s else None
        return make_aware(datetime.combine(d, dt_time.max)) if d else None

    raw_filters = {
        'subject_id': request.GET.get('subject'),
        'date_from':  _date_from(request.GET.get('date_from')),
        'date_to':    _date_to(request.GET.get('date_to')),
        # Task 16.3: user filter only for staff or explicit view_all_logs perm (Req 2.1)
        'user_id':    request.GET.get('user') if (
            request.user.is_staff or
            request.user.has_perm('accounts.view_all_logs')
        ) else None,
    }
    filters = {k: v for k, v in raw_filters.items() if v}

    logs = AuditLogAccessController.get_logs_for_user(request.user, filters)

    paginator = Paginator(logs, 50)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    if request.user.is_staff:
        available_subjects = Subject.objects.all().order_by('course_name')
        all_faculty = Faculty.objects.select_related('user').order_by('full_name')
    else:
        try:
            faculty = Faculty.objects.get(user=request.user)
            available_subjects = faculty.subjects.all().order_by('course_name')
        except Faculty.DoesNotExist:
            available_subjects = Subject.objects.none()
        all_faculty = []

    return render(request, 'accounts/audit_log_list.html', {
        'logs': page_obj,
        'available_subjects': available_subjects,
        'all_faculty': all_faculty if request.user.is_staff else [],
        'filters': filters,
    })



# -----------------------------------------------------------------------
# Task 8.2 - audit_log_detail
# -----------------------------------------------------------------------

@login_required
def audit_log_detail(request, log_id):
    """
    Single SyllabusEditLog detail view.
    Returns HTTP 403 if the user lacks permission.
    Requirements: 2.5, 3.3, 16.1, 16.2
    """
    import logging as _logging
    _audit_access_log = _logging.getLogger('accounts.audit_access')
    from .access_controller import AuditLogAccessController
    from .models import SyllabusEditLog

    log_entry = get_object_or_404(
        SyllabusEditLog.objects.select_related('syllabus__subject', 'user'),
        pk=log_id,
    )

    if not AuditLogAccessController.can_view_log(request.user, log_entry):
        # Task 16.2: Log unauthorized access attempts (Requirements: 3.3)
        _audit_access_log.warning(
            'Unauthorized audit log access: user=%s (id=%s) tried to view '
            'log_entry=%s at %s',
            request.user.username, request.user.pk, log_id,
            __import__('django.utils.timezone', fromlist=['now']).now().isoformat(),
        )
        return HttpResponseForbidden(
            'You do not have permission to view this audit log entry.'
        )

    return render(request, 'accounts/audit_log_detail.html', {'log': log_entry})
