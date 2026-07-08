-- Database Verification Commands for Admin
-- Run these queries directly in your PostgreSQL database tool (e.g., pgAdmin, psql) 
-- to verify the state of Master Data vs. Faculty Data.

-- 1. VIEW MASTER SUBJECTS (Global List)
-- These are the ground truth subjects. They persist even if faculty are deleted.
SELECT id, course_name, course_code, semester 
FROM adminpanel_subject;

-- 2. VIEW SYLLABUS ENTRIES
-- These are the syllabus documents attached to subjects.
-- If a Subject is deleted, the corresponding row here should disappear.
SELECT id, subject_id, status, created_at 
FROM adminpanel_syllabus;

-- 3. VIEW FACULTY MEMBERS
-- Staff who can be assigned to subjects.
SELECT id, faculty_id, full_name, user_id 
FROM adminpanel_faculty;

-- 4. VIEW SUBJECT-FACULTY MAPPINGS
-- Connects a Master Subject to a Faculty Member.
-- Deleting a Faculty member deletes rows here, BUT NOT the Subject.
SELECT id, subject_id, faculty_id 
FROM adminpanel_subjectfaculty;

-- 5. CHECK FOR ORPHAN SUBJECTS (Subjects with NO Faculty)
-- These subjects exist but are not assigned to anyone.
-- They can be deleted securely if not needed.
SELECT * FROM adminpanel_subject 
WHERE id NOT IN (SELECT subject_id FROM adminpanel_subjectfaculty);
