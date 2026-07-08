from django.urls import path
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

]
