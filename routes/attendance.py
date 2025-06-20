from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import User, Session, AttendanceRecord, Student, Enrollment, UserRole, AttendanceStatus
from app import db
from datetime import datetime

attendance_bp = Blueprint('attendance', __name__)

@attendance_bp.route('/checkin', methods=['POST'])
@jwt_required()
def checkin():
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user or user.role != UserRole.STUDENT:
            return jsonify({'error': 'Only students can check in'}), 403

        if not user.student_profile:
            return jsonify({'error': 'Student profile not found'}), 404
        
        data = request.get_json()
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({'error': 'session_id is required'}), 400
        
        session = Session.query.get(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        if not session.attendance_open:
            return jsonify({'error': 'Attendance is not open for this session'}), 400
        
        # Check if student is enrolled in the course
        enrollment = Enrollment.query.filter_by(
            student_id=user.student_profile.id,
            course_id=session.course_id,
            is_active=True
        ).first()
        
        if not enrollment:
            return jsonify({'error': 'Not enrolled in this course'}), 403
        
        # Check if already checked in
        existing_record = AttendanceRecord.query.filter_by(
            session_id=session_id,
            student_id=user.student_profile.id
        ).first()
        
        if existing_record:
            return jsonify({
                'error': 'Already checked in',
                'attendance': existing_record.to_dict()
            }), 400
        
        # Determine attendance status based on time
        now = datetime.now().time()
        status = AttendanceStatus.PRESENT
        
        # If checking in after session start time, mark as late
        if now > session.start_time:
            status = AttendanceStatus.LATE
        
        # Create attendance record
        attendance = AttendanceRecord(
            session_id=session_id,
            student_id=user.student_profile.id,
            status=status,
            marked_by=current_user_id
        )
        
        db.session.add(attendance)
        db.session.commit()
        
        return jsonify({
            'message': 'Checked in successfully',
            'attendance': attendance.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@attendance_bp.route('/session/<int:session_id>', methods=['GET'])
@jwt_required()
def get_session_attendance(session_id):
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        session = Session.query.get(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        # Check access permissions
        if user.role == UserRole.STUDENT:
            # Students can only see their own attendance
            enrollment = Enrollment.query.filter_by(
                student_id=user.student_profile.id,
                course_id=session.course_id,
                is_active=True
            ).first()
            if not enrollment:
                return jsonify({'error': 'Not enrolled in this course'}), 403
            
            attendance = AttendanceRecord.query.filter_by(
                session_id=session_id,
                student_id=user.student_profile.id
            ).first()
            
            return jsonify({
                'session': session.to_dict(),
                'attendance': attendance.to_dict() if attendance else None
            }), 200
            
        elif user.role == UserRole.LECTURER:
            # Check if lecturer owns the course
            if session.course.lecturer_id != int(current_user_id):
                return jsonify({'error': 'Unauthorized'}), 403
            
            # Get all attendance records for this session
            attendance_records = AttendanceRecord.query.filter_by(
                session_id=session_id
            ).all()
            
            # Get all enrolled students for comparison
            enrolled_students = Student.query.join(Enrollment).filter(
                Enrollment.course_id == session.course_id,
                Enrollment.is_active == True
            ).all()
            
            # Create attendance summary
            attendance_list = []
            for student in enrolled_students:
                attendance_record = next(
                    (record for record in attendance_records if record.student_id == student.id),
                    None
                )
                
                attendance_list.append({
                    'student': student.to_dict(),
                    'attendance': attendance_record.to_dict() if attendance_record else {
                        'status': 'ABSENT',
                        'marked_at': None
                    }
                })
            
            return jsonify({
                'session': session.to_dict(),
                'attendance_records': attendance_list,
                'total_enrolled': len(enrolled_students),
                'total_present': len([r for r in attendance_records if r.status in [AttendanceStatus.PRESENT, AttendanceStatus.LATE]]),
                'total_absent': len(enrolled_students) - len(attendance_records)
            }), 200
        
        else:  # ADMIN
            attendance_records = AttendanceRecord.query.filter_by(
                session_id=session_id
            ).all()
            
            return jsonify({
                'session': session.to_dict(),
                'attendance_records': [record.to_dict() for record in attendance_records]
            }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@attendance_bp.route('/student/<int:student_id>', methods=['GET'])
@jwt_required()
def get_student_attendance(student_id):
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check permissions
        if user.role == UserRole.STUDENT:
            # Students can only see their own attendance
            if user.student_profile.id != student_id:
                return jsonify({'error': 'Unauthorized'}), 403
        
        student = Student.query.get(student_id)
        if not student:
            return jsonify({'error': 'Student not found'}), 404
        
        # Get query parameters
        course_id = request.args.get('course_id', type=int)
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        # Build query
        query = AttendanceRecord.query.filter_by(student_id=student_id)
        
        if course_id:
            query = query.join(Session).filter(Session.course_id == course_id)
        
        if date_from:
            try:
                from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
                query = query.join(Session).filter(Session.session_date >= from_date)
            except ValueError:
                return jsonify({'error': 'Invalid date_from format'}), 400
        
        if date_to:
            try:
                to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
                query = query.join(Session).filter(Session.session_date <= to_date)
            except ValueError:
                return jsonify({'error': 'Invalid date_to format'}), 400
        
        attendance_records = query.all()
        
        # Calculate statistics
        total_sessions = len(attendance_records)
        present_count = len([r for r in attendance_records if r.status == AttendanceStatus.PRESENT])
        late_count = len([r for r in attendance_records if r.status == AttendanceStatus.LATE])
        absent_count = len([r for r in attendance_records if r.status == AttendanceStatus.ABSENT])
        excused_count = len([r for r in attendance_records if r.status == AttendanceStatus.EXCUSED])
        
        attendance_rate = ((present_count + late_count) / total_sessions * 100) if total_sessions > 0 else 0
        
        return jsonify({
            'student': student.to_dict(),
            'attendance_records': [record.to_dict() for record in attendance_records],
            'statistics': {
                'total_sessions': total_sessions,
                'present': present_count,
                'late': late_count,
                'absent': absent_count,
                'excused': excused_count,
                'attendance_rate': round(attendance_rate, 2)
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@attendance_bp.route('/course/<int:course_id>', methods=['GET'])
@jwt_required()
def get_course_attendance(course_id):
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user or user.role not in [UserRole.LECTURER, UserRole.ADMIN]:
            return jsonify({'error': 'Unauthorized'}), 403
        
        from models import Course
        course = Course.query.get(course_id)
        if not course:
            return jsonify({'error': 'Course not found'}), 404
        
        # Check if lecturer owns the course
        if user.role == UserRole.LECTURER and course.lecturer_id != current_user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Get all sessions for this course
        sessions = Session.query.filter_by(course_id=course_id).all()
        
        # Get all enrolled students
        enrolled_students = Student.query.join(Enrollment).filter(
            Enrollment.course_id == course_id,
            Enrollment.is_active == True
        ).all()
        
        # Get all attendance records for this course
        attendance_records = AttendanceRecord.query.join(Session).filter(
            Session.course_id == course_id
        ).all()
        
        # Create attendance matrix
        attendance_matrix = []
        for student in enrolled_students:
            student_attendance = {
                'student': student.to_dict(),
                'sessions': []
            }
            
            for session in sessions:
                attendance_record = next(
                    (record for record in attendance_records 
                     if record.student_id == student.id and record.session_id == session.id),
                    None
                )
                
                student_attendance['sessions'].append({
                    'session': session.to_dict(),
                    'attendance': attendance_record.to_dict() if attendance_record else {
                        'status': 'ABSENT',
                        'marked_at': None
                    }
                })
            
            # Calculate student statistics
            student_records = [s['attendance'] for s in student_attendance['sessions']]
            present_count = len([r for r in student_records if r['status'] in ['PRESENT', 'LATE']])
            total_sessions = len(sessions)
            attendance_rate = (present_count / total_sessions * 100) if total_sessions > 0 else 0
            
            student_attendance['statistics'] = {
                'total_sessions': total_sessions,
                'present': len([r for r in student_records if r['status'] == 'PRESENT']),
                'late': len([r for r in student_records if r['status'] == 'LATE']),
                'absent': len([r for r in student_records if r['status'] == 'ABSENT']),
                'attendance_rate': round(attendance_rate, 2)
            }
            
            attendance_matrix.append(student_attendance)
        
        return jsonify({
            'course': course.to_dict(),
            'sessions': [session.to_dict() for session in sessions],
            'attendance_matrix': attendance_matrix,
            'summary': {
                'total_students': len(enrolled_students),
                'total_sessions': len(sessions),
                'total_records': len(attendance_records)
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@attendance_bp.route('/mark', methods=['POST'])
@jwt_required()
def mark_attendance():
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user or user.role != UserRole.LECTURER:
            return jsonify({'error': 'Only lecturers can mark attendance'}), 403
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['session_id', 'student_id', 'status']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        session = Session.query.get(data['session_id'])
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        # Check if lecturer owns the course
        if session.course.lecturer_id != int(current_user_id):
            return jsonify({'error': 'Unauthorized'}), 403
        
        student = Student.query.get(data['student_id'])
        if not student:
            return jsonify({'error': 'Student not found'}), 404
        
        # Validate status
        try:
            status = AttendanceStatus(data['status'].upper())
        except ValueError:
            return jsonify({'error': 'Invalid status'}), 400
        
        # Check if student is enrolled
        enrollment = Enrollment.query.filter_by(
            student_id=data['student_id'],
            course_id=session.course_id,
            is_active=True
        ).first()
        
        if not enrollment:
            return jsonify({'error': 'Student not enrolled in this course'}), 403
        
        # Check if attendance already exists
        existing_record = AttendanceRecord.query.filter_by(
            session_id=data['session_id'],
            student_id=data['student_id']
        ).first()
        
        if existing_record:
            # Update existing record
            existing_record.status = status
            existing_record.marked_by = current_user_id
            existing_record.marked_at = datetime.utcnow()
            existing_record.notes = data.get('notes')
            
            db.session.commit()
            
            return jsonify({
                'message': 'Attendance updated successfully',
                'attendance': existing_record.to_dict()
            }), 200
        else:
            # Create new record
            attendance = AttendanceRecord(
                session_id=data['session_id'],
                student_id=data['student_id'],
                status=status,
                marked_by=current_user_id,
                notes=data.get('notes')
            )
            
            db.session.add(attendance)
            db.session.commit()
            
            return jsonify({
                'message': 'Attendance marked successfully',
                'attendance': attendance.to_dict()
            }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
