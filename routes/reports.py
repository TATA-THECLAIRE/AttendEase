from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import User, Course, Session, AttendanceRecord, Student, Enrollment, UserRole, AttendanceStatus
from app import db
import pandas as pd
import io
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/attendance/course/<int:course_id>/export', methods=['GET'])
@jwt_required()
def export_course_attendance(course_id):
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))  # Convert string back to int
        
        if not user or user.role not in [UserRole.LECTURER, UserRole.ADMIN]:
            return jsonify({'error': 'Unauthorized'}), 403
        
        course = Course.query.get(course_id)
        if not course:
            return jsonify({'error': 'Course not found'}), 404
        
        # Check if lecturer owns the course
        if user.role == UserRole.LECTURER and course.lecturer_id != int(current_user_id):  # Convert string back to int
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Get export format
        export_format = request.args.get('format', 'excel').lower()
        if export_format not in ['excel', 'csv', 'pdf']:
            return jsonify({'error': 'Invalid format. Use excel, csv, or pdf'}), 400
        
        # Get date range
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        # Build sessions query
        sessions_query = Session.query.filter_by(course_id=course_id)
        
        if date_from:
            try:
                from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
                sessions_query = sessions_query.filter(Session.session_date >= from_date)
            except ValueError:
                return jsonify({'error': 'Invalid date_from format'}), 400
        
        if date_to:
            try:
                to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
                sessions_query = sessions_query.filter(Session.session_date <= to_date)
            except ValueError:
                return jsonify({'error': 'Invalid date_to format'}), 400
        
        sessions = sessions_query.order_by(Session.session_date, Session.start_time).all()
        
        # Get enrolled students
        enrolled_students = Student.query.join(Enrollment).filter(
            Enrollment.course_id == course_id,
            Enrollment.is_active == True
        ).order_by(Student.student_id).all()
        
        # Get attendance records
        session_ids = [s.id for s in sessions]
        attendance_records = AttendanceRecord.query.filter(
            AttendanceRecord.session_id.in_(session_ids)
        ).all()
        
        # Create attendance matrix
        data = []
        for student in enrolled_students:
            row = {
                'Student ID': student.student_id,
                'First Name': student.user.first_name,
                'Last Name': student.user.last_name,
                'Department': student.department.value,
                'Year of Study': student.year_of_study
            }
            
            # Add attendance for each session
            for session in sessions:
                session_key = f"{session.session_date.strftime('%Y-%m-%d')} - {session.session_name}"
                attendance_record = next(
                    (record for record in attendance_records 
                     if record.student_id == student.id and record.session_id == session.id),
                    None
                )
                row[session_key] = attendance_record.status.value if attendance_record else 'ABSENT'
            
            # Calculate statistics
            student_records = [
                record for record in attendance_records if record.student_id == student.id
            ]
            present_count = len([r for r in student_records if r.status in [AttendanceStatus.PRESENT, AttendanceStatus.LATE]])
            total_sessions = len(sessions)
            attendance_rate = (present_count / total_sessions * 100) if total_sessions > 0 else 0
            
            row['Total Sessions'] = total_sessions
            row['Present/Late'] = present_count
            row['Absent'] = total_sessions - present_count
            row['Attendance Rate (%)'] = round(attendance_rate, 2)
            
            data.append(row)
        
        # Generate file based on format
        if export_format == 'csv':
            df = pd.DataFrame(data)
            output = io.StringIO()
            df.to_csv(output, index=False)
            output.seek(0)
            
            return send_file(
                io.BytesIO(output.getvalue().encode()),
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'{course.course_code}_attendance_report.csv'
            )
            
        elif export_format == 'excel':
            df = pd.DataFrame(data)
            output = io.BytesIO()
            
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Attendance Report', index=False)
                
                # Get workbook and worksheet
                workbook = writer.book
                worksheet = writer.sheets['Attendance Report']
                
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
                    worksheet.set_column(i, i, min(max_len + 2, 50))
            
            output.seek(0)
            
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=f'{course.course_code}_attendance_report.xlsx'
            )
            
        elif export_format == 'pdf':
            output = io.BytesIO()
            doc = SimpleDocTemplate(output, pagesize=A4)
            elements = []
            
            # Styles
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=16,
                spaceAfter=30,
                alignment=1  # Center alignment
            )
            
            # Title
            title = Paragraph(f"Attendance Report - {course.course_code}: {course.course_name}", title_style)
            elements.append(title)
            elements.append(Spacer(1, 12))
            
            # Course info
            course_info = f"""
            <b>Lecturer:</b> {course.lecturer.first_name} {course.lecturer.last_name}<br/>
            <b>Department:</b> {course.department.value}<br/>
            <b>Level:</b> {course.level}<br/>
            <b>Academic Year:</b> {course.academic_year or 'N/A'}<br/>
            <b>Semester:</b> {course.semester or 'N/A'}<br/>
            <b>Report Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            elements.append(Paragraph(course_info, styles['Normal']))
            elements.append(Spacer(1, 20))
            
            # Summary statistics
            total_students = len(enrolled_students)
            total_sessions = len(sessions)
            total_records = len(attendance_records)
            
            summary = f"""
            <b>Summary:</b><br/>
            Total Students: {total_students}<br/>
            Total Sessions: {total_sessions}<br/>
            Total Attendance Records: {total_records}
            """
            elements.append(Paragraph(summary, styles['Normal']))
            elements.append(Spacer(1, 20))
            
            # Attendance table (simplified for PDF)
            table_data = [['Student ID', 'Name', 'Department', 'Present/Late', 'Absent', 'Rate (%)']]
            
            for student in enrolled_students:
                student_records = [
                    record for record in attendance_records if record.student_id == student.id
                ]
                present_count = len([r for r in student_records if r.status in [AttendanceStatus.PRESENT, AttendanceStatus.LATE]])
                absent_count = total_sessions - present_count
                attendance_rate = (present_count / total_sessions * 100) if total_sessions > 0 else 0
                
                table_data.append([
                    student.student_id,
                    f"{student.user.first_name} {student.user.last_name}",
                    student.department.value,
                    str(present_count),
                    str(absent_count),
                    f"{attendance_rate:.1f}%"
                ])
            
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            elements.append(table)
            doc.build(elements)
            output.seek(0)
            
            return send_file(
                output,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f'{course.course_code}_attendance_report.pdf'
            )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@reports_bp.route('/attendance/student/<int:student_id>/export', methods=['GET'])
@jwt_required()
def export_student_attendance(student_id):
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))  # Convert string back to int
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check permissions
        if user.role == UserRole.STUDENT:
            if user.student_profile and user.student_profile.id != student_id:
                return jsonify({'error': 'Unauthorized'}), 403
        elif user.role not in [UserRole.LECTURER, UserRole.ADMIN]:
            return jsonify({'error': 'Unauthorized'}), 403
        
        student = Student.query.get(student_id)
        if not student:
            return jsonify({'error': 'Student not found'}), 404
        
        # Get export format
        export_format = request.args.get('format', 'excel').lower()
        if export_format not in ['excel', 'csv', 'pdf']:
            return jsonify({'error': 'Invalid format. Use excel, csv, or pdf'}), 400
        
        # Get query parameters
        course_id = request.args.get('course_id', type=int)
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        # Build attendance query
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
        
        # Prepare data
        data = []
        for record in attendance_records:
            data.append({
                'Date': record.session.session_date.strftime('%Y-%m-%d'),
                'Course Code': record.session.course.course_code,
                'Course Name': record.session.course.course_name,
                'Session Name': record.session.session_name,
                'Start Time': record.session.start_time.strftime('%H:%M'),
                'End Time': record.session.end_time.strftime('%H:%M'),
                'Location': record.session.location or 'N/A',
                'Status': record.status.value,
                'Marked At': record.marked_at.strftime('%Y-%m-%d %H:%M:%S'),
                'Notes': record.notes or ''
            })
        
        # Generate file based on format
        if export_format == 'csv':
            df = pd.DataFrame(data)
            output = io.StringIO()
            df.to_csv(output, index=False)
            output.seek(0)
            
            return send_file(
                io.BytesIO(output.getvalue().encode()),
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'{student.student_id}_attendance_history.csv'
            )
            
        elif export_format == 'excel':
            df = pd.DataFrame(data)
            output = io.BytesIO()
            
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Attendance History', index=False)
                
                # Get workbook and worksheet
                workbook = writer.book
                worksheet = writer.sheets['Attendance History']
                
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
                    worksheet.set_column(i, i, min(max_len + 2, 50))
            
            output.seek(0)
            
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=f'{student.student_id}_attendance_history.xlsx'
            )
            
        elif export_format == 'pdf':
            output = io.BytesIO()
            doc = SimpleDocTemplate(output, pagesize=A4)
            elements = []
            
            # Styles
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=16,
                spaceAfter=30,
                alignment=1
            )
            
            # Title
            title = Paragraph(f"Attendance History - {student.student_id}", title_style)
            elements.append(title)
            elements.append(Spacer(1, 12))
            
            # Student info
            student_info = f"""
            <b>Student Name:</b> {student.user.first_name} {student.user.last_name}<br/>
            <b>Student ID:</b> {student.student_id}<br/>
            <b>Department:</b> {student.department.value}<br/>
            <b>Year of Study:</b> {student.year_of_study}<br/>
            <b>Report Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            elements.append(Paragraph(student_info, styles['Normal']))
            elements.append(Spacer(1, 20))
            
            # Statistics
            total_records = len(attendance_records)
            present_count = len([r for r in attendance_records if r.status == AttendanceStatus.PRESENT])
            late_count = len([r for r in attendance_records if r.status == AttendanceStatus.LATE])
            absent_count = len([r for r in attendance_records if r.status == AttendanceStatus.ABSENT])
            attendance_rate = ((present_count + late_count) / total_records * 100) if total_records > 0 else 0
            
            stats = f"""
            <b>Statistics:</b><br/>
            Total Sessions: {total_records}<br/>
            Present: {present_count}<br/>
            Late: {late_count}<br/>
            Absent: {absent_count}<br/>
            Attendance Rate: {attendance_rate:.1f}%
            """
            elements.append(Paragraph(stats, styles['Normal']))
            elements.append(Spacer(1, 20))
            
            # Attendance table
            table_data = [['Date', 'Course', 'Session', 'Status', 'Time']]
            
            for record in attendance_records:
                table_data.append([
                    record.session.session_date.strftime('%Y-%m-%d'),
                    record.session.course.course_code,
                    record.session.session_name[:30] + '...' if len(record.session.session_name) > 30 else record.session.session_name,
                    record.status.value,
                    record.marked_at.strftime('%H:%M')
                ])
            
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            elements.append(table)
            doc.build(elements)
            output.seek(0)
            
            return send_file(
                output,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f'{student.student_id}_attendance_history.pdf'
            )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@reports_bp.route('/attendance/summary', methods=['GET'])
@jwt_required()
def get_attendance_summary():
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))  # Convert string back to int
        
        if not user or user.role not in [UserRole.LECTURER, UserRole.ADMIN]:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Get query parameters
        course_id = request.args.get('course_id', type=int)
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        # Build base queries
        if user.role == UserRole.LECTURER:
            courses_query = Course.query.filter_by(lecturer_id=int(current_user_id))  # Convert string back to int
            sessions_query = Session.query.join(Course).filter(Course.lecturer_id == int(current_user_id))  # Convert string back to int
        else:  # ADMIN
            courses_query = Course.query
            sessions_query = Session.query
        
        # Apply course filter
        if course_id:
            courses_query = courses_query.filter(Course.id == course_id)
            sessions_query = sessions_query.filter(Session.course_id == course_id)
        
        # Apply date filters
        if date_from:
            try:
                from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
                sessions_query = sessions_query.filter(Session.session_date >= from_date)
            except ValueError:
                return jsonify({'error': 'Invalid date_from format'}), 400
        
        if date_to:
            try:
                to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
                sessions_query = sessions_query.filter(Session.session_date <= to_date)
            except ValueError:
                return jsonify({'error': 'Invalid date_to format'}), 400
        
        # Get data
        courses = courses_query.all()
        sessions = sessions_query.all()
        session_ids = [s.id for s in sessions]
        
        # Get attendance records
        attendance_records = AttendanceRecord.query.filter(
            AttendanceRecord.session_id.in_(session_ids)
        ).all() if session_ids else []
        
        # Calculate summary statistics
        total_courses = len(courses)
        total_sessions = len(sessions)
        total_attendance_records = len(attendance_records)
        
        # Attendance by status
        present_count = len([r for r in attendance_records if r.status == AttendanceStatus.PRESENT])
        late_count = len([r for r in attendance_records if r.status == AttendanceStatus.LATE])
        absent_count = len([r for r in attendance_records if r.status == AttendanceStatus.ABSENT])
        excused_count = len([r for r in attendance_records if r.status == AttendanceStatus.EXCUSED])
        
        # Course-wise summary
        course_summaries = []
        for course in courses:
            course_sessions = [s for s in sessions if s.course_id == course.id]
            course_session_ids = [s.id for s in course_sessions]
            course_attendance = [r for r in attendance_records if r.session_id in course_session_ids]
            
            # Get enrolled students count
            enrolled_count = Enrollment.query.filter_by(
                course_id=course.id,
                is_active=True
            ).count()
            
            course_present = len([r for r in course_attendance if r.status == AttendanceStatus.PRESENT])
            course_late = len([r for r in course_attendance if r.status == AttendanceStatus.LATE])
            course_total_expected = len(course_sessions) * enrolled_count
            course_attendance_rate = ((course_present + course_late) / course_total_expected * 100) if course_total_expected > 0 else 0
            
            course_summaries.append({
                'course': course.to_dict(),
                'total_sessions': len(course_sessions),
                'enrolled_students': enrolled_count,
                'total_records': len(course_attendance),
                'present': course_present,
                'late': course_late,
                'absent': len(course_sessions) * enrolled_count - len(course_attendance),
                'attendance_rate': round(course_attendance_rate, 2)
            })
        
        return jsonify({
            'summary': {
                'total_courses': total_courses,
                'total_sessions': total_sessions,
                'total_attendance_records': total_attendance_records,
                'present': present_count,
                'late': late_count,
                'absent': absent_count,
                'excused': excused_count
            },
            'course_summaries': course_summaries,
            'filters': {
                'course_id': course_id,
                'date_from': date_from,
                'date_to': date_to
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
