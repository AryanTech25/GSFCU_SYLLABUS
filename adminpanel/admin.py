from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from .models import School, Program, Branch, Faculty, Subject

# Register models to make them visible in the admin panel
admin.site.register(School)
admin.site.register(Program)
admin.site.register(Branch)
admin.site.register(Subject)

class FacultyInline(admin.StackedInline):
    model = Faculty
    can_delete = False
    verbose_name_plural = 'Faculty Profile'
    fk_name = 'user'

class CustomUserAdmin(UserAdmin):
    inlines = (FacultyInline, )
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_school', 'get_program', 'get_branch')
    
    def get_school(self, instance):
        if hasattr(instance, 'faculty') and instance.faculty.school:
            return instance.faculty.school.name
        return '-'
    get_school.short_description = 'School'
    
    def get_program(self, instance):
        if hasattr(instance, 'faculty') and instance.faculty.program:
            return instance.faculty.program.name
        return '-'
    get_program.short_description = 'Program'
    
    def get_branch(self, instance):
        if hasattr(instance, 'faculty') and instance.faculty.branch:
            return instance.faculty.branch.name
        return '-'
    get_branch.short_description = 'Branch'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('faculty__school', 'faculty__program', 'faculty__branch')

# Re-register UserAdmin
if admin.site.is_registered(User):
    admin.site.unregister(User)

admin.site.register(User, CustomUserAdmin)

@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'faculty_id', 'school', 'program', 'branch', 'email')
    list_filter = ('school', 'program', 'branch')
    search_fields = ('full_name', 'faculty_id', 'email')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('school', 'program', 'branch')
