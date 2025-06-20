from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import User, Course, Announcement, UserRole, Enrollment
from app import db

announcements_bp = Blueprint('announcements', __name__)

@announcements_bp.route('', methods=['POST'])
@jwt_required()
def create_announcement():
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))  # Convert string back to int
        
        if not user or user.role not in [UserRole.ADMIN, UserRole.LECTURER]:
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['title', 'content']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        course_id = data.get('course_id')
        is_global = data.get('is_global', False)
        
        # If not global, course_id is required
        if not is_global and not course_id:
            return jsonify({'error': 'course_id is required for course-specific announcements'}), 400
        
        # If course_id provided, check if course exists and user has access
        if course_id:
            course = Course.query.get(course_id)
            if not course:
                return jsonify({'error': 'Course not found'}), 404
            
            # Check if lecturer owns the course
            if user.role == UserRole.LECTURER and course.lecturer_id != int(current_user_id):  # Convert string back to int
                return jsonify({'error': 'Unauthorized - not your course'}), 403
        
        # Only admins can create global announcements
        if is_global and user.role != UserRole.ADMIN:
            return jsonify({'error': 'Only admins can create global announcements'}), 403
        
        announcement = Announcement(
            title=data['title'],
            content=data['content'],
            author_id=int(current_user_id),  # Convert string back to int
            course_id=course_id,
            is_global=is_global,
            priority=data.get('priority', 'normal')
        )
        
        db.session.add(announcement)
        db.session.commit()
        
        return jsonify({
            'message': 'Announcement created successfully',
            'announcement': announcement.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@announcements_bp.route('', methods=['GET'])
@jwt_required()
def get_announcements():
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))  # Convert string back to int
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        course_id = request.args.get('course_id', type=int)
        priority = request.args.get('priority')
        
        # Build query based on user role
        if user.role == UserRole.STUDENT:
            # Students see global announcements and announcements for their enrolled courses
            if user.student_profile:
                enrolled_course_ids = [e.course_id for e in user.student_profile.enrollments if e.is_active]
            else:
                enrolled_course_ids = []
            
            query = Announcement.query.filter(
                db.or_(
                    Announcement.is_global == True,
                    Announcement.course_id.in_(enrolled_course_ids)
                ),
                Announcement.is_active == True
            )
            
        elif user.role == UserRole.LECTURER:
            # Lecturers see global announcements and announcements for their courses
            taught_course_ids = [c.id for c in user.taught_courses]
            
            query = Announcement.query.filter(
                db.or_(
                    Announcement.is_global == True,
                    Announcement.course_id.in_(taught_course_ids),
                    Announcement.author_id == int(current_user_id)  # Convert string back to int
                ),
                Announcement.is_active == True
            )
            
        else:  # ADMIN
            query = Announcement.query.filter(Announcement.is_active == True)
        
        # Apply filters
        if course_id:
            query = query.filter(Announcement.course_id == course_id)
        
        if priority:
            query = query.filter(Announcement.priority == priority)
        
        # Order by priority and creation date
        priority_order = db.case(
            (Announcement.priority == 'high', 1),
            (Announcement.priority == 'medium', 2),
            (Announcement.priority == 'normal', 3),
            else_=4
        )
        query = query.order_by(priority_order, Announcement.created_at.desc())
        
        # Paginate results
        announcements = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'announcements': [announcement.to_dict() for announcement in announcements.items],
            'total': announcements.total,
            'pages': announcements.pages,
            'current_page': page,
            'per_page': per_page
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@announcements_bp.route('/<int:announcement_id>', methods=['GET'])
@jwt_required()
def get_announcement(announcement_id):
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))  # Convert string back to int
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        announcement = Announcement.query.get(announcement_id)
        if not announcement:
            return jsonify({'error': 'Announcement not found'}), 404
        
        # Check access permissions
        if user.role == UserRole.STUDENT:
            # Check if announcement is global or for an enrolled course
            if not announcement.is_global:
                if user.student_profile:
                    enrolled_course_ids = [e.course_id for e in user.student_profile.enrollments if e.is_active]
                    if announcement.course_id not in enrolled_course_ids:
                        return jsonify({'error': 'Unauthorized'}), 403
                else:
                    return jsonify({'error': 'Student profile not found'}), 403
                    
        elif user.role == UserRole.LECTURER:
            # Check if announcement is global, for their course, or created by them
            if not announcement.is_global:
                taught_course_ids = [c.id for c in user.taught_courses]
                if announcement.course_id not in taught_course_ids and announcement.author_id != int(current_user_id):  # Convert string back to int
                    return jsonify({'error': 'Unauthorized'}), 403
        
        return jsonify(announcement.to_dict()), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@announcements_bp.route('/<int:announcement_id>', methods=['PUT'])
@jwt_required()
def update_announcement(announcement_id):
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))  # Convert string back to int
        
        if not user or user.role not in [UserRole.ADMIN, UserRole.LECTURER]:
            return jsonify({'error': 'Unauthorized'}), 403
        
        announcement = Announcement.query.get(announcement_id)
        if not announcement:
            return jsonify({'error': 'Announcement not found'}), 404
        
        # Check if user can edit this announcement
        if user.role == UserRole.LECTURER:
            if announcement.author_id != int(current_user_id):  # Convert string back to int
                return jsonify({'error': 'Can only edit your own announcements'}), 403
        
        data = request.get_json()
        
        # Update announcement fields
        if 'title' in data:
            announcement.title = data['title']
        if 'content' in data:
            announcement.content = data['content']
        if 'priority' in data:
            announcement.priority = data['priority']
        if 'is_active' in data:
            announcement.is_active = data['is_active']
        
        db.session.commit()
        
        return jsonify({
            'message': 'Announcement updated successfully',
            'announcement': announcement.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@announcements_bp.route('/<int:announcement_id>', methods=['DELETE'])
@jwt_required()
def delete_announcement(announcement_id):
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))  # Convert string back to int
        
        if not user or user.role not in [UserRole.ADMIN, UserRole.LECTURER]:
            return jsonify({'error': 'Unauthorized'}), 403
        
        announcement = Announcement.query.get(announcement_id)
        if not announcement:
            return jsonify({'error': 'Announcement not found'}), 404
        
        # Check if user can delete this announcement
        if user.role == UserRole.LECTURER:
            if announcement.author_id != int(current_user_id):  # Convert string back to int
                return jsonify({'error': 'Can only delete your own announcements'}), 403
        
        # Soft delete by setting is_active to False
        announcement.is_active = False
        db.session.commit()
        
        return jsonify({'message': 'Announcement deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@announcements_bp.route('/course/<int:course_id>', methods=['GET'])
@jwt_required()
def get_course_announcements(course_id):
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
            if user.student_profile:
                enrollment = Enrollment.query.filter_by(
                    student_id=user.student_profile.id,
                    course_id=course_id,
                    is_active=True
                ).first()
                if not enrollment:
                    return jsonify({'error': 'Not enrolled in this course'}), 403
            else:
                return jsonify({'error': 'Student profile not found'}), 403
                
        elif user.role == UserRole.LECTURER:
            # Check if lecturer teaches this course
            if course.lecturer_id != int(current_user_id):  # Convert string back to int
                return jsonify({'error': 'Unauthorized'}), 403
        
        # Get announcements for this course
        announcements = Announcement.query.filter_by(
            course_id=course_id,
            is_active=True
        ).order_by(Announcement.created_at.desc()).all()
        
        return jsonify({
            'course': course.to_dict(),
            'announcements': [announcement.to_dict() for announcement in announcements]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
