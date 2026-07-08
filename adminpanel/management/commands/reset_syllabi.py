from django.core.management.base import BaseCommand
from adminpanel.models import Syllabus, SemesterReference, SemesterSubject, Subject
import os
import shutil
from django.conf import settings

class Command(BaseCommand):
    help = 'TOTAL RESET: Deletes all Subjects, Syllabi, Semester Structures, and ALL PDF files.'

    def handle(self, *args, **options):
        self.stdout.write('Starting Aggressive Cleanup...')

        # 1. Delete all Subjects (Master Data)
        # This will cascade to Syllabi, SemesterSubject, etc.
        self.stdout.write('Deleting all Subjects (and cascading data)...')
        Subject.objects.all().delete()

        # 2. Delete all Semester Merged PDFs (SemesterReference)
        self.stdout.write('Deleting all Semester Merged PDF records...')
        SemesterReference.objects.all().delete()

        # 3. Wipe the syllabus_pdfs directory
        self.stdout.write('Wiping physical PDF directory...')
        media_path = settings.MEDIA_ROOT
        if os.path.exists(media_path):
            count = 0
            for filename in os.listdir(media_path):
                file_path = os.path.join(media_path, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                        count += 1
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                        count += 1
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'Failed to delete {file_path}. Reason: {e}'))
            self.stdout.write(f'Deleted {count} files/folders from {media_path}')

        self.stdout.write(self.style.SUCCESS('TOTAL RESET COMPLETE. System is now empty and ready for fresh data!'))
