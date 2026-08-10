import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from accounts.models import SyllabusEditLog
from adminpanel.models import Syllabus
from django.contrib.auth.models import User

# Get test data
user = User.objects.first()
syllabus = Syllabus.objects.first()

if not user or not syllabus:
    print('No user or syllabus found for testing')
    exit(1)

# Test creating a log entry
print('Testing SyllabusEditLog immutability...')
log = SyllabusEditLog.objects.create(
    syllabus=syllabus,
    user=user,
    action_type='create',
    model_name='Test',
    description='Test log for immutability check'
)
print(f'✓ Created log with ID: {log.id}')

# Test updating an existing log (should fail)
log.description = 'Attempt to update'
try:
    log.save()
    print('✗ ERROR: Update was allowed! Immutability check failed.')
except ValueError as e:
    print(f'✓ SUCCESS: Update prevented - {e}')

# Cleanup
log.delete()
print('✓ Test cleanup complete')
