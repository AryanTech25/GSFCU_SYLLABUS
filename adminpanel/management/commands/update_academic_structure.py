from django.core.management.base import BaseCommand
from adminpanel.models import School, Program, Branch, Subject, Semester, SemesterSubject
from django.db import transaction

class Command(BaseCommand):
    help = 'Updates programs, branches, and creates subjects according to seed_data.py'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Starting academic structure migration...'))
        
        # Define the structure from seed_data.py (SOM maps to SOMLA)
        data = {
            'SOT': {
                'name': 'School of Technology',
                'programs': {
                    'BTech': {
                        'semesters': 8,
                        'branches': [
                            'Computer Science and Engineering',
                            'Chemical Engineering',
                            'Data Science',
                            'Artificial Intelligence & Machine Learning',
                            'IoT Automation',
                            'Cyber Security',
                            'Fire Environment Health & Safety'
                        ]
                    },
                    'BCA': {
                        'semesters': 6,
                        'branches': ['Bachelor of Computer Applications']
                    },
                    'MTech': {
                        'semesters': 4,
                        'branches': [
                            'Industrial Safety & Engineering',
                            'Computer Science & Engineering'
                        ]
                    },
                    'PhD': {
                        'semesters': 8,
                        'branches': ['Computer Science & Engineering']
                    }
                }
            },
            'SOS': {
                'name': 'School of Science',
                'programs': {
                    'B.Sc': {
                        'semesters': 6,
                        'branches': [
                            'Biotechnology', 'Chemistry', 'Microbiology', 'Data Science'
                        ]
                    },
                    'M.Sc': {
                        'semesters': 4,
                        'branches': [
                            'Biotechnology', 'Chemistry (Organic & Analytical)', 
                            'Industrial Microbiology', 'Data Science'
                        ]
                    },
                    'PhD': {
                        'semesters': 8,
                        'branches': [
                            'Biotechnology', 'Chemistry', 'Mathematics', 'Microbiology'
                        ]
                    },
                    'PG Diploma': {
                        'semesters': 2,
                        'branches': ['Industrial Safety']
                    }
                }
            },
            'SOMLA': {  # Maps to SOM in seed_data.py
                'name': 'School of Management and Liberal Arts',
                'programs': {
                    'BBA': {
                        'semesters': 6,
                        'branches': [
                            'HR', 'Marketing', 'Finance', 'IT', 'Business Analytics'
                        ]
                    },
                    'B.A': {
                        'semesters': 6,
                        'branches': ['Economics (Hons.)']
                    },
                    'B.Com': {
                        'semesters': 6,
                        'branches': ['Commerce (Hons.)']
                    },
                    'MBA': {
                        'semesters': 4,
                        'branches': [
                            'HR', 'Marketing', 'Finance', 'Business Analytics'
                        ]
                    },
                    'PhD': {
                        'semesters': 8,
                        'branches': ['Management']
                    }
                }
            }
        }

        with transaction.atomic():
            # Step 1: Delete all existing programs (CASCADE will handle branches, subjects, etc.)
            self.stdout.write('Deleting existing programs and branches...')
            deleted_count = Program.objects.all().delete()[0]
            self.stdout.write(self.style.SUCCESS(f'Deleted {deleted_count} objects'))

            # Step 2: Create new structure
            for school_code, school_data in data.items():
                school = School.objects.get(code=school_code)
                self.stdout.write(f'\nProcessing {school_code}...')
                
                for prog_name, prog_data in school_data['programs'].items():
                    program, _ = Program.objects.get_or_create(
                        school=school,
                        name=prog_name
                    )
                    self.stdout.write(f'  Created program: {prog_name}')
                    
                    # Create semesters for this program
                    num_semesters = prog_data['semesters']
                    for sem_num in range(1, num_semesters + 1):
                        semester, _ = Semester.objects.get_or_create(
                            program=program,
                            semester_number=str(sem_num)
                        )
                    
                    # Create branches
                    for branch_name in prog_data['branches']:
                        branch, _ = Branch.objects.get_or_create(
                            program=program,
                            name=branch_name
                        )
                        self.stdout.write(f'    - Branch: {branch_name}')
                        
                        # Create 2 subjects per semester for this branch
                        for sem_num in range(1, num_semesters + 1):
                            semester = Semester.objects.get(
                                program=program,
                                semester_number=str(sem_num)
                            )
                            
                            # Generate meaningful subject names based on branch and semester
                            subjects = self.generate_subjects(program, branch, sem_num)
                            
                            for idx, subject_name in enumerate(subjects, 1):
                                course_code = f"{school_code}{prog_name[:2].upper()}{sem_num:02d}{idx:02d}"
                                
                                subject = Subject.objects.create(
                                    course_name=subject_name,
                                    course_code=course_code,
                                    semester=str(sem_num),
                                    school=school,
                                    program=program,
                                    branch=branch,
                                    is_active=False
                                )
                                
                                # Link subject to semester
                                SemesterSubject.objects.create(
                                    semester=semester,
                                    subject=subject,
                                    sequence=idx
                                )

            self.stdout.write(self.style.SUCCESS('\n✓ Migration completed successfully!'))
            
            # Display statistics
            self.stdout.write('\n=== Statistics ===')
            self.stdout.write(f'Programs: {Program.objects.count()}')
            self.stdout.write(f'Branches: {Branch.objects.count()}')
            self.stdout.write(f'Subjects: {Subject.objects.count()}')
            self.stdout.write(f'Semesters: {Semester.objects.count()}')

    def generate_subjects(self, program, branch, sem_num):
        """Generate 2 meaningful subject names based on program, branch, and semester"""
        
        # Core subjects that appear in early semesters across programs
        if sem_num == 1:
            return [
                f"Introduction to {branch.name}",
                "Mathematics I"
            ]
        elif sem_num == 2:
            return [
                f"Fundamentals of {branch.name}",
                "Mathematics II"
            ]
        
        # Program-specific subjects
        prog_name = program.name.upper()
        
        if 'TECH' in prog_name or 'BCA' in prog_name:
            subjects = [
                f"{branch.name} - Theory {sem_num}",
                f"{branch.name} - Laboratory {sem_num}"
            ]
        elif 'SC' in prog_name:
            subjects = [
                f"Advanced {branch.name} {sem_num}",
                f"{branch.name} Practical {sem_num}"
            ]
        elif 'BBA' in prog_name or 'MBA' in prog_name:
            subjects = [
                f"{branch.name} Management {sem_num}",
                f"Strategic {branch.name} {sem_num}"
            ]
        elif 'B.A' in prog_name or 'B.COM' in prog_name:
            subjects = [
                f"{branch.name} - Core {sem_num}",
                f"{branch.name} - Elective {sem_num}"
            ]
        elif 'PHD' in prog_name:
            subjects = [
                f"Research Methodology in {branch.name} {sem_num}",
                f"Advanced Topics in {branch.name} {sem_num}"
            ]
        else:
            subjects = [
                f"{branch.name} - Course {sem_num}A",
                f"{branch.name} - Course {sem_num}B"
            ]
        
        return subjects
