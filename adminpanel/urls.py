from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('faculty/create/', views.create_faculty, name='create_faculty'),
    path('faculty/edit/<int:faculty_id>/', views.edit_faculty, name='edit_faculty'),
    path('faculty/delete/<int:faculty_id>/', views.delete_faculty, name='delete_faculty'),
    path('subject/create/', views.create_subject, name='create_subject'),
    path('subject/delete/<int:subject_id>/', views.delete_subject, name='delete_subject'),
    path('syllabus/delete/<int:syllabus_id>/', views.delete_syllabus, name='delete_syllabus'),
    path('semester/manage/', views.manage_semester_structure, name='manage_semester_structure'),
    path('semester/generate-pdf/', views.generate_semester_pdf, name='generate_semester_pdf'),
    path('semester/preview-pdf/', views.preview_semester_pdf, name='preview_semester_pdf'),
    path('semester/view-pdf/', views.view_semester_pdf, name='view_semester_pdf'),
    path('semester/download-pdf/', views.download_semester_pdf, name='download_semester_pdf'),
    path('semester/delete/', views.delete_semester_pdf, name='delete_semester_pdf'),
    path('semester/generate-full/', views.generate_full_program_syllabus, name='generate_full_program_syllabus'),

    path('api/get-programs/', views.get_programs, name='get_programs'),
    path('api/get-branches/', views.get_branches, name='get_branches'),

    # Program Outcomes (PO)
    path('program-outcomes/', views.manage_program_outcomes, name='manage_program_outcomes'),
    path('program-outcomes/<int:po_id>/edit/', views.edit_program_outcome, name='edit_program_outcome'),
    path('program-outcomes/<int:po_id>/delete/', views.delete_program_outcome, name='delete_program_outcome'),

    # Program Specific Outcomes (PSO)
    path('program-specific-outcomes/', views.manage_program_specific_outcomes, name='manage_program_specific_outcomes'),
    path('program-specific-outcomes/<int:pso_id>/edit/', views.edit_program_specific_outcome, name='edit_program_specific_outcome'),
    path('program-specific-outcomes/<int:pso_id>/delete/', views.delete_program_specific_outcome, name='delete_program_specific_outcome'),

    # Program Educational Objectives (PEO)
    path('program-educational-objectives/', views.manage_program_educational_objectives, name='manage_program_educational_objectives'),
    path('program-educational-objectives/<int:peo_id>/edit/', views.edit_program_educational_objective, name='edit_program_educational_objective'),
    path('program-educational-objectives/<int:peo_id>/delete/', views.delete_program_educational_objective, name='delete_program_educational_objective'),
]
