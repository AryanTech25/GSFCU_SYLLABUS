from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('', views.login_view, name='root_redirect'), # Redirect root to login
    path('logout/', views.logout_view, name='logout'),
    path('faculty/dashboard/', views.faculty_dashboard, name='faculty_dashboard'),
    path('faculty/syllabus-builder/', views.syllabus_builder, name='syllabus_builder'),
    path('faculty/validate-syllabus/', views.validate_syllabus_form, name='validate_syllabus'),
    path('faculty/drafts/', views.faculty_drafts, name='faculty_drafts'),
    path('faculty/generate-pdf/<int:syllabus_id>/', views.generate_pdf, name='generate_pdf'),
    path('faculty/render-preview/', views.render_preview, name='render_preview'),
    # Force reload
    path('semester/preview/<int:semester_id>/', views.preview_semester_merge, name='preview_semester_merge'),
    path('semester/generate/<int:semester_id>/', views.generate_semester_pdf, name='generate_semester_pdf'),

    # Task 8.3 – Audit Log views (Requirements: 2.1, 3.1)
    path('audit-logs/', views.audit_log_list, name='audit_log_list'),
    path('audit-logs/<int:log_id>/', views.audit_log_detail, name='audit_log_detail'),

    # ── Approval Workflow ─────────────────────────────────────────────────
    path('faculty/submit-for-review/<int:syllabus_id>/',
         views.submit_for_review, name='submit_for_review'),

    # ── Password Reset (Django built-in flow) ──────────────────────────────
    path('password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='accounts/password_reset_form.html',
             email_template_name='accounts/password_reset_email.txt',
             subject_template_name='accounts/password_reset_subject.txt',
             success_url='/password-reset/done/',
         ),
         name='password_reset'),

    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='accounts/password_reset_done.html',
         ),
         name='password_reset_done'),

    path('password-reset/confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='accounts/password_reset_confirm.html',
             success_url='/password-reset/complete/',
         ),
         name='password_reset_confirm'),

    path('password-reset/complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='accounts/password_reset_complete.html',
         ),
         name='password_reset_complete'),
]
