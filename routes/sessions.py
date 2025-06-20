from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import User, Course, Session, UserRole
from app import db
from datetime import datetime, date, time

sessions_bp = Blueprint('sessions', __name__)

@sessions_bp.route('', methods=['POST'])
@jwt_required()
def create_session():
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))  # Convert string back to int
        
        if not user or user.role != UserRole.LECTURER:
            return jsonify({'error': 'Only lecturers can create sessions'}), 403
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['course_id', 'session_name', 'session_date', 'start_time', 'end_time']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Check if course exists and lecturer owns it
        course = Course.query.get(data['course_id'])
        if not course:
            return jsonify({'error': 'Course not found'}), 404
        
        if course.lecturer_id != int(current_user_id):  # Convert string back to int
            return jsonify({'error': 'Unauthorized - not your course'}), 403
        
        # Parse date and time
        try:
            session_date = datetime.strptime(data['session_date'], '%Y-%m-%d').date()
            start_time = datetime.strptime(data['start_time'], '%H:%M').time()
            end_time = datetime.strptime(data['end_time'], '%H:%M').time()
        except ValueError:
            return jsonify({'error': 'Invalid date/time format'}), 400
        
        # Validate time logic
        if start_time >= end_time:
            return jsonify({'error': 'Start time must be before end time'}), 400
        
        session = Session(
            course_id=data['course_id'],
            session_name=data['session_name'],
            session_date=session_date,
            start_time=start_time,
            end_time=end_time,
            location=data.get('location')
        )
        
        db.session.add(session)
        db.session.commit()
        
        return jsonify({
            'message': 'Session created successfully',
            'session': session.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@sessions_bp.route('', methods=['GET'])
@jwt_required()
def get_sessions():
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))  # Convert string back to int
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        course_id = request.args.get('course_id', type=int)
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        # Build query based on user role
        if user.role == UserRole.STUDENT:
            # Get sessions for courses the student is enrolled in
            from models import Enrollment
            if user.student_profile:
                query = Session.query.join(Course).join(Enrollment).filter(
                    Enrollment.student_id == user.student_profile.id,
                    Enrollment.is_active == True
                )
            else:
                # No student profile, return empty result
                return jsonify({
                    'sessions': [],
                    'total': 0,
                    'pages': 0,
                    'current_page': page,
                    'per_page': per_page
                }), 200
        elif user.role == UserRole.LECTURER:
            # Get sessions for courses taught by the lecturer
            query = Session.query.join(Course).filter(
                Course.lecturer_id == int(current_user_id)  # Convert string back to int
            )
        else:  # ADMIN
            query = Session.query
        
        # Apply filters
        if course_id:
            query = query.filter(Session.course_id == course_id)
        
        if date_from:
            try:
                from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
                query = query.filter(Session.session_date >= from_date)
            except ValueError:
                return jsonify({'error': 'Invalid date_from format'}), 400
        
        if date_to:
            try:
                to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
                query = query.filter(Session.session_date <= to_date)
            except ValueError:
                return jsonify({'error': 'Invalid date_to format'}), 400
        
        # Order by date and time
        query = query.order_by(Session.session_date.desc(), Session.start_time.desc())
        
        # Paginate results
        sessions = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'sessions': [session.to_dict() for session in sessions.items],
            'total': sessions.total,
            'pages': sessions.pages,
            'current_page': page,
            'per_page': per_page
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@sessions_bp.route('/<int:session_id>', methods=['GET'])
@jwt_required()
def get_session(session_id):
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))  # Convert string back to int
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        session = Session.query.get(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        # Check access permissions
        if user.role == UserRole.STUDENT:
            # Check if student is enrolled in the course
            from models import Enrollment
            if user.student_profile:
                enrollment = Enrollment.query.filter_by(
                    student_id=user.student_profile.id,
                    course_id=session.course_id,
                    is_active=True
                ).first()
                if not enrollment:
                    return jsonify({'error': 'Not enrolled in this course'}), 403
            else:
                return jsonify({'error': 'Student profile not found'}), 403
        elif user.role == UserRole.LECTURER:
            # Check if lecturer owns the course
            if session.course.lecturer_id != int(current_user_id):  # Convert string back to int
                return jsonify({'error': 'Unauthorized'}), 403
        
        return jsonify(session.to_dict()), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@sessions_bp.route('/<int:session_id>/start', methods=['POST'])
@jwt_required()
def start_session(session_id):
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))  # Convert string back to int
        
        if not user or user.role != UserRole.LECTURER:
            return jsonify({'error': 'Only lecturers can start sessions'}), 403
        
        session = Session.query.get(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        # Check if lecturer owns the course
        if session.course.lecturer_id != int(current_user_id):  # Convert string back to int
            return jsonify({'error': 'Unauthorized'}), 403
        
        if session.attendance_open:
            return jsonify({'error': 'Session already started'}), 400
        
        # Start the session
        session.attendance_open = True
        db.session.commit()
        
        return jsonify({
            'message': 'Session started successfully',
            'session': session.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@sessions_bp.route('/<int:session_id>/end', methods=['POST'])
@jwt_required()
def end_session(session_id):
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))  # Convert string back to int
        
        if not user or user.role != UserRole.LECTURER:
            return jsonify({'error': 'Only lecturers can end sessions'}), 403
        
        session = Session.query.get(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        # Check if lecturer owns the course
        if session.course.lecturer_id != int(current_user_id):  # Convert string back to int
            return jsonify({'error': 'Unauthorized'}), 403
        
        if not session.attendance_open:
            return jsonify({'error': 'Session not started yet'}), 400
        
        # End the session
        session.attendance_open = False
        db.session.commit()
        
        return jsonify({
            'message': 'Session ended successfully',
            'session': session.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@sessions_bp.route('/<int:session_id>', methods=['PUT'])
@jwt_required()
def update_session(session_id):
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))  # Convert string back to int
        
        if not user or user.role != UserRole.LECTURER:
            return jsonify({'error': 'Only lecturers can update sessions'}), 403
        
        session = Session.query.get(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        # Check if lecturer owns the course
        if session.course.lecturer_id != int(current_user_id):  # Convert string back to int
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.get_json()
        
        # Update session fields
        if 'session_name' in data:
            session.session_name = data['session_name']
        
        if 'session_date' in data:
            try:
                session.session_date = datetime.strptime(data['session_date'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'error': 'Invalid date format'}), 400
        
        if 'start_time' in data:
            try:
                session.start_time = datetime.strptime(data['start_time'], '%H:%M').time()
            except ValueError:
                return jsonify({'error': 'Invalid start_time format'}), 400
        
        if 'end_time' in data:
            try:
                session.end_time = datetime.strptime(data['end_time'], '%H:%M').time()
            except ValueError:
                return jsonify({'error': 'Invalid end_time format'}), 400
        
        if 'location' in data:
            session.location = data['location']
        
        # Validate time logic
        if session.start_time >= session.end_time:
            return jsonify({'error': 'Start time must be before end time'}), 400
        
        db.session.commit()
        
        return jsonify({
            'message': 'Session updated successfully',
            'session': session.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@sessions_bp.route('/<int:session_id>', methods=['DELETE'])
@jwt_required()
def delete_session(session_id):
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))  # Convert string back to int
        
        if not user or user.role != UserRole.LECTURER:
            return jsonify({'error': 'Only lecturers can delete sessions'}), 403
        
        session = Session.query.get(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        # Check if lecturer owns the course
        if session.course.lecturer_id != int(current_user_id):  # Convert string back to int
            return jsonify({'error': 'Unauthorized'}), 403
        
        db.session.delete(session)
        db.session.commit()
        
        return jsonify({'message': 'Session deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
