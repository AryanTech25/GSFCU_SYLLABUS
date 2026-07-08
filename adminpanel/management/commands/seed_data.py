from django.core.management.base import BaseCommand
from adminpanel.models import School, Program, Branch

class Command(BaseCommand):
    help = 'Seeds the database with Schools, Programs, and Branches'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding data...')
        
        data = {
            'SOT': {
                'name': 'School of Technology',
                'programs': {
                    'BTech': [
                        'Computer Science and Engineering',
                        'Chemical Engineering',
                        'Data Science',
                        'Artificial Intelligence & Machine Learning',
                        'IoT Automation',
                        'Cyber Security',
                        'Fire Environment Health & Safety'
                    ],
                    'BCA': ['Bachelor of Computer Applications'],
                    'MTech': [
                        'Industrial Safety & Engineering',
                        'Computer Science & Engineering'
                    ],
                    'PhD': ['Computer Science & Engineering']
                }
            },
            'SOS': {
                'name': 'School of Science',
                'programs': {
                    'B.Sc': [
                        'Biotechnology', 'Chemistry', 'Microbiology', 'Data Science'
                    ],
                    'M.Sc': [
                        'Biotechnology', 'Chemistry (Organic & Analytical)', 'Industrial Microbiology', 'Data Science'
                    ],
                    'PhD': [
                        'Biotechnology', 'Chemistry', 'Mathematics', 'Microbiology'
                    ],
                    'PG Diploma': ['Industrial Safety']
                }
            },
            'SOM': {
                'name': 'School of Management',
                'programs': {
                    'BBA': [
                        'HR', 'Marketing', 'Finance', 'IT', 'Business Analytics'
                    ],
                    'B.A': ['Economics (Hons.)'],
                    'B.Com': ['Commerce (Hons.)'],
                    'MBA': [
                        'HR', 'Marketing', 'Finance', 'Business Analytics'
                    ],
                    'PhD': ['Management']
                }
            }
        }

        for school_code, school_data in data.items():
            school, created = School.objects.get_or_create(
                code=school_code, 
                defaults={'name': school_data['name']}
            )
            if created:
                self.stdout.write(f'Created School: {school_code}')
            
            for prog_name, branches in school_data['programs'].items():
                program, p_created = Program.objects.get_or_create(
                    school=school,
                    name=prog_name
                )
                
                for branch_name in branches:
                    Branch.objects.get_or_create(
                        program=program,
                        name=branch_name
                    )
        
        self.stdout.write(self.style.SUCCESS('Data seeding completed successfully!'))
