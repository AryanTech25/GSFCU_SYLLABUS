#!/usr/bin/env python
"""Verify the database schema for SyllabusEditLog model."""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.db import connection
from accounts.models import SyllabusEditLog

def check_table_exists():
    """Check if the table exists in the database."""
    print("Checking table existence...")
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'accounts_syllabuseditlog'
            );
        """)
        exists = cursor.fetchone()[0]
        if exists:
            print("✓ Table 'accounts_syllabuseditlog' exists")
            return True
        else:
            print("✗ Table 'accounts_syllabuseditlog' does not exist")
            return False

def check_columns():
    """Check all columns exist with correct types."""
    print("\nChecking columns...")
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'accounts_syllabuseditlog'
            ORDER BY ordinal_position;
        """)
        columns = cursor.fetchall()
        
        expected_columns = {
            'id': 'bigint',
            'syllabus_id': 'bigint',
            'user_id': 'integer',
            'timestamp': 'timestamp',
            'ip_address': 'inet',
            'action_type': 'character varying',
            'model_name': 'character varying',
            'record_id': 'integer',
            'field_name': 'character varying',
            'old_value': 'jsonb',
            'new_value': 'jsonb',
            'description': 'text'
        }
        
        for col_name, data_type, is_nullable in columns:
            if col_name in expected_columns:
                expected_type = expected_columns[col_name]
                if data_type.startswith(expected_type) or expected_type.startswith(data_type):
                    nullable_str = 'NULL' if is_nullable == 'YES' else 'NOT NULL'
                    print(f"✓ Column '{col_name}' ({data_type}, {nullable_str})")
                else:
                    print(f"✗ Column '{col_name}' has type '{data_type}', expected '{expected_type}'")
            else:
                print(f"? Unexpected column '{col_name}' ({data_type})")
        
        return True

def check_indexes():
    """Check that all indexes are created."""
    print("\nChecking indexes...")
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'accounts_syllabuseditlog'
            ORDER BY indexname;
        """)
        indexes = cursor.fetchall()
        
        print(f"Found {len(indexes)} indexes:")
        for idx_name, idx_def in indexes:
            print(f"  ✓ {idx_name}")
            if 'timestamp' in idx_def.lower():
                print(f"    - Includes timestamp field")
            if 'syllabus' in idx_def.lower():
                print(f"    - Includes syllabus foreign key")
            if 'user' in idx_def.lower():
                print(f"    - Includes user foreign key")
        
        return True

def check_foreign_keys():
    """Check foreign key constraints."""
    print("\nChecking foreign key constraints...")
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                tc.constraint_name,
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name,
                rc.delete_rule
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            JOIN information_schema.referential_constraints AS rc
                ON tc.constraint_name = rc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_name = 'accounts_syllabuseditlog';
        """)
        fks = cursor.fetchall()
        
        for constraint_name, table, column, ref_table, ref_column, delete_rule in fks:
            print(f"✓ FK: {column} → {ref_table}({ref_column})")
            print(f"  ON DELETE: {delete_rule}")
        
        return True

def check_permissions():
    """Check custom permissions."""
    print("\nChecking custom permissions...")
    from django.contrib.contenttypes.models import ContentType
    from django.contrib.auth.models import Permission
    
    content_type = ContentType.objects.get_for_model(SyllabusEditLog)
    permissions = Permission.objects.filter(content_type=content_type)
    
    for perm in permissions:
        print(f"✓ Permission: {perm.codename} - {perm.name}")
    
    if permissions.filter(codename='view_all_logs').exists():
        print("✓ Custom permission 'view_all_logs' exists")
        return True
    else:
        print("✗ Custom permission 'view_all_logs' not found")
        return False

if __name__ == '__main__':
    print("=" * 70)
    print("SyllabusEditLog Database Schema Verification")
    print("=" * 70)
    
    all_passed = True
    
    if not check_table_exists():
        all_passed = False
        exit(1)
    
    if not check_columns():
        all_passed = False
    
    if not check_indexes():
        all_passed = False
    
    if not check_foreign_keys():
        all_passed = False
    
    if not check_permissions():
        all_passed = False
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✓ All schema checks passed!")
        print("=" * 70)
        exit(0)
    else:
        print("✗ Some schema checks failed")
        print("=" * 70)
        exit(1)
