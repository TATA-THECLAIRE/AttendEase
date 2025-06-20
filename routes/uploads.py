from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import User, Course, Student, Enrollment, UserRole, Department
from app import db
import pandas as pd
import os
from werkzeug.utils import secure_filename
import re

uploads_bp = Blueprint('uploads', __name__)

ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_student_id(student_id):
    # Format: FE22A111 (FE + year + A + 3 digits)
    pattern = r'^FE\d{2}A\d{3}$'
    return re.match(pattern, student_id) is not None

def parse_student_id(student_id):
    # Extract year from student ID (e.g., FE22A111 -> 2022)
    if validate_student_id(student_id):
        year_part = student_id[2:4]
        return 2000 + int(year_part)
    return None

@uploads_bp.route('/students', methods=['POST'])
@jwt_required()
def upload_students():
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user or user.role != UserRole.LECTURER:
            return jsonify({'error': 'Only lecturers can upload student lists'}), 403
        
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file format. Use Excel (.xlsx, .xls) or CSV (.csv)'}), 400
        
        # Get course ID
        course_id = request.form.get('course_id')
        if not course_id:
            return jsonify({'error': 'course_id is required'}), 400
        
        try:
            course_id = int(course_id)
        except ValueError:
            return jsonify({'error': 'Invalid course_id'}), 400
        
        # Check if course exists and lecturer owns it
        course = Course.query.get(course_id)
        if not course:
            return jsonify({'error': 'Course not found'}), 404
        
        if course.lecturer_id != current_user_id:
            return jsonify({'error': 'Unauthorized - not your course'}), 403
        
        # Save file temporarily
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            # Read file based on extension
            file_ext = filename.rsplit('.', 1)[1].lower()
            if file_ext == 'csv':
                df = pd.read_csv(filepath)
            else:  # Excel files
                df = pd.read_excel(filepath)
            
            # Validate required columns
            required_columns = ['student_id', 'first_name', 'last_name', 'email']
            optional_columns = ['phone', 'department', 'year_of_study']
            
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                return jsonify({
                    'error': f'Missing required columns: {", ".join(missing_columns)}',
                    'required_columns': required_columns,
                    'optional_columns': optional_columns
                }), 400
            
            # Process students
            results = {
                'total_rows': len(df),
                'successful': 0,
                'failed': 0,
                'errors': [],
                'created_students': [],
                'enrolled_students': []
            }
            
            for index, row in df.iterrows():
                try:
                    # Validate student ID
                    student_id = str(row['student_id']).strip()
                    if not validate_student_id(student_id):
                        results['errors'].append({
                            'row': index + 1,
                            'student_id': student_id,
                            'error': 'Invalid student ID format (should be FE22A111)'
                        })
                        results['failed'] += 1
                        continue
                    
                    # Extract enrollment year
                    enrollment_year = parse_student_id(student_id)
                    
                    # Validate email
                    email = str(row['email']).strip().lower()
                    if not email or '@' not in email:
                        results['errors'].append({
                            'row': index + 1,
                            'student_id': student_id,
                            'error': 'Invalid email address'
                        })
                        results['failed'] += 1
                        continue
                    
                    # Get or determine department
                    department = None
                    if 'department' in row and pd.notna(row['department']):
                        try:
                            department = Department(str(row['department']).strip().upper())
                        except ValueError:
                            # Use course department as fallback
                            department = course.department
                    else:
                        department = course.department
                    
                    # Get or determine year of study
                    year_of_study = None
                    if 'year_of_study' in row and pd.notna(row['year_of_study']):
                        try:
                            year_of_study = int(row['year_of_study'])
                            if year_of_study not in [200, 300, 400, 500]:
                                year_of_study = course.level
                        except (ValueError, TypeError):
                            year_of_study = course.level
                    else:
                        year_of_study = course.level
                    
                    # Check if student already exists
                    existing_student = Student.query.filter_by(student_id=student_id).first()
                    
                    if existing_student:
                        # Check if already enrolled in this course
                        existing_enrollment = Enrollment.query.filter_by(
                            student_id=existing_student.id,
                            course_id=course_id
                        ).first()
                        
                        if existing_enrollment:
                            if not existing_enrollment.is_active:
                                # Reactivate enrollment
                                existing_enrollment.is_active = True
                                results['enrolled_students'].append({
                                    'student_id': student_id,
                                    'action': 'reactivated_enrollment'
                                })
                            else:
                                results['errors'].append({
                                    'row': index + 1,
                                    'student_id': student_id,
                                    'error': 'Already enrolled in this course'
                                })
                                results['failed'] += 1
                                continue
                        else:
                            # Create new enrollment
                            enrollment = Enrollment(
                                student_id=existing_student.id,
                                course_id=course_id
                            )
                            db.session.add(enrollment)
                            results['enrolled_students'].append({
                                'student_id': student_id,
                                'action': 'enrolled_existing_student'
                            })
                    else:
                        # Check if user with email exists
                        existing_user = User.query.filter_by(email=email).first()
                        
                        if existing_user:
                            if existing_user.role != UserRole.STUDENT:
                                results['errors'].append({
                                    'row': index + 1,
                                    'student_id': student_id,
                                    'error': 'Email belongs to non-student user'
                                })
                                results['failed'] += 1
                                continue
                            
                            # Create student profile for existing user
                            student = Student(
                                user_id=existing_user.id,
                                student_id=student_id,
                                department=department,
                                year_of_study=year_of_study,
                                enrollment_year=enrollment_year
                            )
                            db.session.add(student)
                            db.session.flush()  # Get student ID
                            
                            # Create enrollment
                            enrollment = Enrollment(
                                student_id=student.id,
                                course_id=course_id
                            )
                            db.session.add(enrollment)
                            
                            results['created_students'].append({
                                'student_id': student_id,
                                'action': 'created_profile_for_existing_user'
                            })
                        else:
                            # Create new user and student
                            new_user = User(
                                email=email,
                                first_name=str(row['first_name']).strip(),
                                last_name=str(row['last_name']).strip(),
                                role=UserRole.STUDENT,
                                phone=str(row['phone']).strip() if 'phone' in row and pd.notna(row['phone']) else None,
                                is_verified=True
                            )
                            # Set default password (student should change it)
                            new_user.set_password('password123')
                            
                            db.session.add(new_user)
                            db.session.flush()  # Get user ID
                            
                            # Create student profile
                            student = Student(
                                user_id=new_user.id,
                                student_id=student_id,
                                department=department,
                                year_of_study=year_of_study,
                                enrollment_year=enrollment_year
                            )
                            db.session.add(student)
                            db.session.flush()  # Get student ID
                            
                            # Create enrollment
                            enrollment = Enrollment(
                                student_id=student.id,
                                course_id=course_id
                            )
                            db.session.add(enrollment)
                            
                            results['created_students'].append({
                                'student_id': student_id,
                                'action': 'created_new_user_and_student'
                            })
                    
                    results['successful'] += 1
                    
                except Exception as e:
                    results['errors'].append({
                        'row': index + 1,
                        'student_id': str(row.get('student_id', 'N/A')),
                        'error': str(e)
                    })
                    results['failed'] += 1
            
            # Commit all changes
            db.session.commit()
            
            return jsonify({
                'message': 'Student upload completed',
                'results': results
            }), 200
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Error processing file: {str(e)}'}), 500
        
        finally:
            # Clean up temporary file
            if os.path.exists(filepath):
                os.remove(filepath)
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@uploads_bp.route('/students/template', methods=['GET'])
@jwt_required()
def download_student_template():
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user or user.role != UserRole.LECTURER:
            return jsonify({'error': 'Only lecturers can download templates'}), 403
        
        # Create sample data
        sample_data = [
            {
                'student_id': 'FE22A001',
                'first_name': 'John',
                'last_name': 'Doe',
                'email': 'john.doe@example.com',
                'phone': '+237123456789',
                'department': 'COMPUTER_SOFTWARE',
                'year_of_study': 200
            },
            {
                'student_id': 'FE22A002',
                'first_name': 'Jane',
                'last_name': 'Smith',
                'email': 'jane.smith@example.com',
                'phone': '+237987654321',
                'department': 'COMPUTER_NETWORK',
                'year_of_study': 300
            }
        ]
        
        # Create DataFrame
        df = pd.DataFrame(sample_data)
        
        # Create Excel file in memory
        output = pd.io.common.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Students', index=False)
            
            # Get workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets['Students']
            
            # Add formatting
            header_format = workbook.add_format({
                'bold': True,
                'text_wrap': True,
                'valign': 'top',
                'fg_color': '#D7E4BC',
                'border': 1
            })
            
            # Write headers with formatting
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            # Auto-adjust column widths
            for i, col in enumerate(df.columns):
                max_len = max(df[col].astype(str).map(len).max(), len(col))
                worksheet.set_column(i, i, max_len + 2)
            
            # Add instructions sheet
            instructions = [
                ['Field', 'Description', 'Required', 'Format/Options'],
                ['student_id', 'Student matricule number', 'Yes', 'FE22A111 (FE + year + A + 3 digits)'],
                ['first_name', 'Student first name', 'Yes', 'Text'],
                ['last_name', 'Student last name', 'Yes', 'Text'],
                ['email', 'Student email address', 'Yes', 'Valid email format'],
                ['phone', 'Student phone number', 'No', 'Text (e.g., +237123456789)'],
                ['department', 'Student department', 'No', 'COMPUTER_SOFTWARE, COMPUTER_NETWORK, TELECOMMUNICATION_CE, ELECTRICAL_POWER, ELECTRICAL_TELECOM, CIVIL, MECHANICAL, CHEMICAL'],
                ['year_of_study', 'Current year of study', 'No', '200, 300, 400, 500']
            ]
            
            instructions_df = pd.DataFrame(instructions[1:], columns=instructions[0])
            instructions_df.to_excel(writer, sheet_name='Instructions', index=False)
            
            # Format instructions sheet
            instructions_worksheet = writer.sheets['Instructions']
            for col_num, value in enumerate(instructions[0]):
                instructions_worksheet.write(0, col_num, value, header_format)
            
            for i, col in enumerate(instructions_df.columns):
                max_len = max(instructions_df[col].astype(str).map(len).max(), len(col))
                instructions_worksheet.set_column(i, i, min(max_len + 2, 50))
        
        output.seek(0)
        
        from flask import send_file
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='student_upload_template.xlsx'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500