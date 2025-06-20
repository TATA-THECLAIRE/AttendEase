from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from models import User, Student, UserRole, Department
from app import db
import re

auth_bp = Blueprint('auth', __name__)

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_student_id(student_id):
    # Format: FE22A111 (FE + year + A + 3 digits)
    pattern = r'^FE\d{2}A\d{3}$'
    return re.match(pattern, student_id) is not None

@auth_bp.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['email', 'password', 'first_name', 'last_name', 'role']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Validate email format
        if not validate_email(data['email']):
            return jsonify({'error': 'Invalid email format'}), 400
        
        # Check if user already exists
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already registered'}), 400
        
        # Validate role
        try:
            role = UserRole(data['role'].upper())
        except ValueError:
            return jsonify({'error': 'Invalid role'}), 400
        
        # Create user
        user = User(
            email=data['email'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            role=role,
            phone=data.get('phone'),
            is_verified=True  # Auto-verify for now
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.flush()  # Get user ID
        
        # If student, create student profile
        if role == UserRole.STUDENT:
            student_data = data.get('student_data', {})
            
            # Validate student ID
            student_id = student_data.get('student_id')
            if not student_id or not validate_student_id(student_id):
                return jsonify({'error': 'Invalid student ID format (should be FE22A111)'}), 400
            
            # Check if student ID already exists
            if Student.query.filter_by(student_id=student_id).first():
                return jsonify({'error': 'Student ID already exists'}), 400
            
            # Extract year from student ID
            enrollment_year = 2000 + int(student_id[2:4])
            
            # Validate department
            try:
                department = Department(student_data.get('department', '').upper())
            except ValueError:
                return jsonify({'error': 'Invalid department'}), 400
            
            student = Student(
                user_id=user.id,
                student_id=student_id,
                department=department,
                year_of_study=student_data.get('year_of_study', 200),
                enrollment_year=enrollment_year
            )
            db.session.add(student)
        
        db.session.commit()
        
        # Create tokens - Convert user ID to string
        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))
        
        return jsonify({
            'message': 'User registered successfully',
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        
        if not data.get('email') or not data.get('password'):
            return jsonify({'error': 'Email and password are required'}), 400
        
        user = User.query.filter_by(email=data['email']).first()
        
        if not user or not user.check_password(data['password']):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        if not user.is_active:
            return jsonify({'error': 'Account is deactivated'}), 401
        
        # Create tokens - Convert user ID to string
        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))
        
        # Get student profile if user is a student
        student_profile = None
        if user.role == UserRole.STUDENT and user.student_profile:
            student_profile = user.student_profile.to_dict()
        
        return jsonify({
            'message': 'Login successful',
            'user': user.to_dict(),
            'student_profile': student_profile,
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))  # Convert string back to int
        
        if not user or not user.is_active:
            return jsonify({'error': 'User not found or inactive'}), 404
        
        access_token = create_access_token(identity=current_user_id)  # Keep as string
        
        return jsonify({
            'access_token': access_token
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))  # Convert string back to int
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get student profile if user is a student
        student_profile = None
        if user.role == UserRole.STUDENT and user.student_profile:
            student_profile = user.student_profile.to_dict()
        
        return jsonify({
            'user': user.to_dict(),
            'student_profile': student_profile
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
