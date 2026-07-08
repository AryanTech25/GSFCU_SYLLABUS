from django.core.management.base import BaseCommand
from adminpanel.models import School, Program, Branch, Semester
from django.db import transaction

class Command(BaseCommand):
    help = 'Seeds GSFC University academic master data: Schools, Programs, Branches, and Semesters'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Seeding GSFC University master data...'))

        data = {
            'SOT': {
                'name': 'School of Technology',
                'programs': {
                    'B.Tech': {
                        'semesters': 8,
                        'branches': [
                            'Chemical Engineering',
                            'Computer Science & Engineering',
                            'Electronics & Communication Engineering',
                            'Fire & Environment, Health & Safety Engineering'
                        ]
                    },
                    'B.Tech (Lateral Entry)': {
                        'semesters': 8,
                        'branches': [
                            'Chemical Engineering',
                            'Computer Science & Engineering',
                            'Fire & Environment, Health & Safety Engineering'
                        ]
                    },
                    'BCA': {
                        'semesters': 8,
                        'branches': [
                            'Computer Applications'
                        ]
                    },
                    'M.Tech': {
                        'semesters': 4,
                        'branches': [
                            'Computer Science & Engineering'
                        ]
                    },
                    'Ph.D': {
                        'semesters': 0,
                        'branches': [
                            'Computer Science & Engineering'
                        ]
                    },
                    'PG Diploma': {
                        'semesters': 4,
                        'branches': [
                            'Industrial Safety'
                        ]
                    }
                }
            },
            'SOS': {
                'name': 'School of Science',
                'programs': {
                    'B.Sc. (Hons.)': {
                        'semesters': 6,
                        'branches': [
                            'Biotechnology',
                            'Chemistry',
                            'Microbiology'
                        ]
                    },
                    'Integrated B.Sc. (Hons.) - M.Sc.': {
                        'semesters': 10,
                        'branches': [
                            'Chemistry',
                            'Data Science'
                        ]
                    },
                    'Integrated BS - MS': {
                        'semesters': 10,
                        'branches': [
                            'Pharmaceutical Science'
                        ]
                    },
                    'M.Sc.': {
                        'semesters': 4,
                        'branches': [
                            'Biotechnology',
                            'Chemistry',
                            'Microbiology',
                            'Data Science'
                        ]
                    },
                    'Ph.D': {
                        'semesters': 0,
                        'branches': [
                            'Biotechnology',
                            'Chemistry',
                            'Microbiology',
                            'Mathematics'
                        ]
                    }
                }
            },
            'SOM': {
                'name': 'School of Management & Entrepreneurship',
                'programs': {
                    'BBA': {
                        'semesters': 6,
                        'branches': [
                            'General',
                            'Business Analytics'
                        ]
                    },
                    'BBA (Hons.)': {
                        'semesters': 6,
                        'branches': [
                            'General',
                            'Business Analytics'
                        ]
                    },
                    'Integrated BBA - MBA': {
                        'semesters': 10,
                        'branches': [
                            'Management'
                        ]
                    },
                    'MBA': {
                        'semesters': 4,
                        'branches': [
                            'Management'
                        ]
                    },
                    'Ph.D': {
                        'semesters': 0,
                        'branches': [
                            'Management'
                        ]
                    }
                }
            }
        }

        schools_created = 0
        programs_created = 0
        branches_created = 0
        semesters_created = 0

        with transaction.atomic():
            for school_code, school_data in data.items():
                school, created = School.objects.get_or_create(
                    code=school_code,
                    defaults={'name': school_data['name']}
                )
                if not created and school.name != school_data['name']:
                    school.name = school_data['name']
                    school.save()
                    self.stdout.write(f"Updated School name to: {school.name}")
                
                if created:
                    schools_created += 1
                    self.stdout.write(f"Created School: {school_code} - {school.name}")
                else:
                    self.stdout.write(f"Reused School: {school_code}")

                for program_name, program_data in school_data['programs'].items():
                    program, created = Program.objects.get_or_create(
                        school=school,
                        name=program_name
                    )
                    if created:
                        programs_created += 1
                        self.stdout.write(f"  Created Program: {program_name}")
                    else:
                        self.stdout.write(f"  Reused Program: {program_name}")

                    # Semesters creation
                    num_semesters = program_data['semesters']
                    for sem_num in range(1, num_semesters + 1):
                        semester, created = Semester.objects.get_or_create(
                            program=program,
                            semester_number=str(sem_num)
                        )
                        if created:
                            semesters_created += 1
                    
                    # Branches creation
                    for branch_name in program_data['branches']:
                        branch, created = Branch.objects.get_or_create(
                            program=program,
                            name=branch_name
                        )
                        if created:
                            branches_created += 1
                            self.stdout.write(f"    Created Branch: {branch_name}")
                        else:
                            self.stdout.write(f"    Reused Branch: {branch_name}")

        self.stdout.write(self.style.SUCCESS('Master data seeding completed successfully!'))
        self.stdout.write(f"Schools created/updated: {schools_created} (Total: {School.objects.count()})")
        self.stdout.write(f"Programs created: {programs_created} (Total: {Program.objects.count()})")
        self.stdout.write(f"Branches created: {branches_created} (Total: {Branch.objects.count()})")
        self.stdout.write(f"Semesters created: {semesters_created} (Total: {Semester.objects.count()})")
