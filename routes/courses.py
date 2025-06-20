from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import User, Course, Enrollment, Student, UserRole, CourseStatus, Department
from app import db

courses_bp = Blueprint('courses', __name__)

@courses_bp.route('', methods=['POST'])
@jwt_required()
def create_course():
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))  # Convert string back to int
        
        if not user or user.role not in [UserRole.ADMIN, UserRole.LECTURER]:
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['course_code', 'course_name', 'level', 'department']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Check if course code already exists
        if Course.query.filter_by(course_code=data['course_code']).first():
            return jsonify({'error': 'Course code already exists'}), 400
        
        # Validate department
        try:
            department = Department(data['department'].upper())
        except ValueError:
            return jsonify({'error': 'Invalid department'}), 400
        
        # Validate level
        if data['level'] not in [200, 300, 400, 500]:
            return jsonify({'error': 'Level must be 200, 300, 400, or 500'}), 400
        
        course = Course(
            course_code=data['course_code'],
            course_name=data['course_name'],
            description=data.get('description'),
            lecturer_id=int(current_user_id),  # Convert string back to int
            credits=data.get('credits', 3),
            semester=data.get('semester'),
            academic_year=data.get('academic_year'),
            level=data['level'],
            department=department
        )
        
        db.session.add(course)
        db.session.commit()
        
        return jsonify({
            'message': 'Course created successfully',
            'course': course.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@courses_bp.route('', methods=['GET'])
@jwt_required()
def get_courses():
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))  # Convert string back to int
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        department = request.args.get('department')
        level = request.args.get('level', type=int)
        status = request.args.get('status')
        
        # Build query based on user role
        if user.role == UserRole.STUDENT:
            # Get courses the student is enrolled in
            query = Course.query.join(Enrollment).filter(
                Enrollment.student_id == user.student_profile.id,
                Enrollment.is_active == True
            )
        elif user.role == UserRole.LECTURER:
            # Get courses taught by the lecturer
            query = Course.query.filter_by(lecturer_id=int(current_user_id))  # Convert string back to int
        else:  # ADMIN
            # Get all courses
            query = Course.query
        
        # Apply filters
        if department:
            try:
                dept_enum = Department(department.upper())
                query = query.filter(Course.department == dept_enum)
            except ValueError:
                return jsonify({'error': 'Invalid department'}), 400
        
        if level:
            query = query.filter(Course.level == level)
        
        if status:
            try:
                status_enum = CourseStatus(status.upper())
                query = query.filter(Course.status == status_enum)
            except ValueError:
                return jsonify({'error': 'Invalid status'}), 400
        
        # Paginate results
        courses = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'courses': [course.to_dict() for course in courses.items],
            'total': courses.total,
            'pages': courses.pages,
            'current_page': page,
            'per_page': per_page
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@courses_bp.route('/<int:course_id>', methods=['GET'])
@jwt_required()
def get_course(course_id):
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))  # Convert string back to int
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        course = Course.query.get(course_id)
        if not course:
            return jsonify({'error': 'Course not found'}), 404
        
        # Check access permissions
        if user.role == UserRole.STUDENT:
            # Check if student is enrolled
            enrollment = Enrollment.query.filter_by(
                student_id=user.student_profile.id,
                course_id=course_id,
                is_active=True
            ).first()
            if not enrollment:
                return jsonify({'error': 'Not enrolled in this course'}), 403
        elif user.role == UserRole.LECTURER:
            # Check if lecturer teaches this course
            if course.lecturer_id != int(current_user_id):  # Convert string back to int
                return jsonify({'error': 'Unauthorized'}), 403
        
        return jsonify(course.to_dict()), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@courses_bp.route('/<int:course_id>', methods=['PUT'])
@jwt_required()
def update_course(course_id):
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))  # Convert string back to int
        
        if not user or user.role not in [UserRole.ADMIN, UserRole.LECTURER]:
            return jsonify({'error': 'Unauthorized'}), 403
        
        course = Course.query.get(course_id)
        if not course:
            return jsonify({'error': 'Course not found'}), 404
        
        # Check if lecturer owns this course
        if user.role == UserRole.LECTURER and course.lecturer_id != int(current_user_id):  # Convert string back to int
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.get_json()
        
        # Update course fields
        if 'course_name' in data:
            course.course_name = data['course_name']
        if 'description' in data:
            course.description = data['description']
        if 'credits' in data:
            course.credits = data['credits']
        if 'semester' in data:
            course.semester = data['semester']
        if 'academic_year' in data:
            course.academic_year = data['academic_year']
        if 'status' in data:
            try:
                course.status = CourseStatus(data['status'].upper())
            except ValueError:
                return jsonify({'error': 'Invalid status'}), 400
        
        db.session.commit()
        
        return jsonify({
            'message': 'Course updated successfully',
            'course': course.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@courses_bp.route('/<int:course_id>/students', methods=['GET'])
@jwt_required()
def get_course_students(course_id):
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))  # Convert string back to int
        
        if not user or user.role not in [UserRole.ADMIN, UserRole.LECTURER]:
            return jsonify({'error': 'Unauthorized'}), 403
        
        course = Course.query.get(course_id)
        if not course:
            return jsonify({'error': 'Course not found'}), 404
        
        # Check if lecturer owns this course
        if user.role == UserRole.LECTURER and course.lecturer_id != int(current_user_id):  # Convert string back to int
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Get enrolled students
        enrollments = Enrollment.query.filter_by(
            course_id=course_id,
            is_active=True
        ).all()
        
        students = []
        for enrollment in enrollments:
            student_data = enrollment.student.to_dict()
            student_data['enrollment_date'] = enrollment.enrolled_at.isoformat()
            students.append(student_data)
        
        return jsonify({
            'course': course.to_dict(),
            'students': students,
            'total_students': len(students)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@courses_bp.route('/<int:course_id>/enroll', methods=['POST'])
@jwt_required()
def enroll_student(course_id):
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))  # Convert string back to int
        
        if not user or user.role != UserRole.STUDENT:
            return jsonify({'error': 'Only students can enroll'}), 403

        if not user.student_profile:
            return jsonify({'error': 'Student profile not found'}), 404
        
        course = Course.query.get(course_id)
        if not course:
            return jsonify({'error': 'Course not found'}), 404
        
        if course.status != CourseStatus.ACTIVE:
            return jsonify({'error': 'Course is not active'}), 400
        
        # Check if already enrolled
        existing_enrollment = Enrollment.query.filter_by(
            student_id=user.student_profile.id,
            course_id=course_id
        ).first()
        
        if existing_enrollment:
            if existing_enrollment.is_active:
                return jsonify({'error': 'Already enrolled in this course'}), 400
            else:
                # Reactivate enrollment
                existing_enrollment.is_active = True
                db.session.commit()
                return jsonify({'message': 'Enrollment reactivated'}), 200
        
        # Create new enrollment
        enrollment = Enrollment(
            student_id=user.student_profile.id,
            course_id=course_id
        )
        
        db.session.add(enrollment)
        db.session.commit()
        
        return jsonify({
            'message': 'Enrolled successfully',
            'enrollment': enrollment.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
