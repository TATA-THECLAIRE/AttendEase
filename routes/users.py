from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import User, Student, UserRole
from app import db

users_bp = Blueprint('users', __name__)

@users_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))  # Convert string back to int
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        profile_data = user.to_dict()
        
        # Add student profile if user is a student
        if user.role == UserRole.STUDENT and user.student_profile:
            profile_data['student_profile'] = user.student_profile.to_dict()
        
        return jsonify(profile_data), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@users_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))  # Convert string back to int
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        
        # Update user fields
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'phone' in data:
            user.phone = data['phone']
        
        # Update student profile if user is a student
        if user.role == UserRole.STUDENT and user.student_profile:
            student_data = data.get('student_profile', {})
            student = user.student_profile
            
            if 'department' in student_data:
                try:
                    from models import Department
                    student.department = Department(student_data['department'].upper())
                except ValueError:
                    return jsonify({'error': 'Invalid department'}), 400
            
            if 'year_of_study' in student_data:
                student.year_of_study = student_data['year_of_study']
        
        db.session.commit()
        
        profile_data = user.to_dict()
        if user.role == UserRole.STUDENT and user.student_profile:
            profile_data['student_profile'] = user.student_profile.to_dict()
        
        return jsonify({
            'message': 'Profile updated successfully',
            'profile': profile_data
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@users_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))  # Convert string back to int
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        
        if not data.get('current_password') or not data.get('new_password'):
            return jsonify({'error': 'Current password and new password are required'}), 400
        
        if not user.check_password(data['current_password']):
            return jsonify({'error': 'Current password is incorrect'}), 400
        
        if len(data['new_password']) < 6:
            return jsonify({'error': 'New password must be at least 6 characters long'}), 400
        
        user.set_password(data['new_password'])
        db.session.commit()
        
        return jsonify({'message': 'Password changed successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@users_bp.route('/students', methods=['GET'])
@jwt_required()
def get_students():
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))  # Convert string back to int
        
        if not user or user.role not in [UserRole.ADMIN, UserRole.LECTURER]:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        department = request.args.get('department')
        year_of_study = request.args.get('year_of_study', type=int)
        
        # Build query
        query = Student.query.join(User)
        
        if department:
            from models import Department
            try:
                dept_enum = Department(department.upper())
                query = query.filter(Student.department == dept_enum)
            except ValueError:
                return jsonify({'error': 'Invalid department'}), 400
        
        if year_of_study:
            query = query.filter(Student.year_of_study == year_of_study)
        
        # Paginate results
        students = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'students': [student.to_dict() for student in students.items],
            'total': students.total,
            'pages': students.pages,
            'current_page': page,
            'per_page': per_page
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
