import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from accounts.models import SyllabusEditLog
from adminpanel.models import Syllabus, Faculty, Subject
from django.contrib.auth.models import User
from django.db import connection

print('Checking CASCADE and SET NULL behavior...\n')

# Check what Django thinks the on_delete rules are
syllabus_field = SyllabusEditLog._meta.get_field('syllabus')
user_field = SyllabusEditLog._meta.get_field('user')

print(f'Django Model Configuration:')
print(f'  syllabus FK on_delete: {syllabus_field.remote_field.on_delete.__name__}')
print(f'  user FK on_delete: {user_field.remote_field.on_delete.__name__}')

# Check actual PostgreSQL constraints
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT
            con.conname AS constraint_name,
            att.attname AS column_name,
            con.confdeltype AS delete_action
        FROM pg_constraint con
        JOIN pg_attribute att ON att.attnum = ANY(con.conkey) AND att.attrelid = con.conrelid
        WHERE con.contype = 'f'
        AND con.conrelid = 'accounts_syllabuseditlog'::regclass;
    """)
    
    constraints = cursor.fetchall()
    print(f'\nPostgreSQL Constraint Configuration:')
    for constraint in constraints:
        delete_action_map = {
            'a': 'NO ACTION',
            'r': 'RESTRICT', 
            'c': 'CASCADE',
            'n': 'SET NULL',
            'd': 'SET DEFAULT'
        }
        action = delete_action_map.get(constraint[2], 'UNKNOWN')
        print(f'  {constraint[0]}: column={constraint[1]}, on_delete={action}')

print('\n✓ Constraint check complete')
