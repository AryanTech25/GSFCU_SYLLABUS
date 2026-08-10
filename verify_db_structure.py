import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.db import connection
from accounts.models import SyllabusEditLog

print('Verifying SyllabusEditLog database structure...\n')

# Check table exists and get columns
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = 'accounts_syllabuseditlog'
        ORDER BY ordinal_position;
    """)
    columns = cursor.fetchall()
    
    print('Table Columns:')
    print('-' * 80)
    for col in columns:
        print(f'  {col[0]:20} | {col[1]:20} | Nullable: {col[2]:3} | Default: {col[3]}')
    
    print('\n' + '=' * 80)
    
    # Check indexes
    cursor.execute("""
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = 'accounts_syllabuseditlog';
    """)
    indexes = cursor.fetchall()
    
    print('\nIndexes:')
    print('-' * 80)
    for idx in indexes:
        print(f'  {idx[0]}')
        print(f'    {idx[1]}')
        print()
    
    print('=' * 80)
    
    # Check foreign keys
    cursor.execute("""
        SELECT
            tc.constraint_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name,
            rc.update_rule,
            rc.delete_rule
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
        JOIN information_schema.referential_constraints AS rc
            ON tc.constraint_name = rc.constraint_name
        WHERE tc.table_name = 'accounts_syllabuseditlog'
        AND tc.constraint_type = 'FOREIGN KEY';
    """)
    foreign_keys = cursor.fetchall()
    
    print('\nForeign Keys:')
    print('-' * 80)
    for fk in foreign_keys:
        print(f'  {fk[0]}')
        print(f'    Column: {fk[1]} -> {fk[2]}.{fk[3]}')
        print(f'    On Update: {fk[4]}, On Delete: {fk[5]}')
        print()

print('\n✓ Database structure verification complete')
