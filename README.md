# AttendEase - Flask Backend API

A comprehensive Flask-based REST API for a mobile attendance system with geofencing and facial recognition capabilities (to be implemented later).

## Features

### Core Functionality
- **User Management**: Registration, login, profile management for Students, Lecturers, and Admins
- **Course Management**: Create, update, and manage courses with department and level organization
- **Session Management**: Lecturers can create and manage class sessions
- **Attendance Tracking**: Real-time check-in system for students
- **Announcements**: Course-specific and global announcements
- **Reports & Export**: Comprehensive attendance reports in Excel, CSV, and PDF formats
- **Student Upload**: Bulk student enrollment via Excel/CSV upload

### User Roles
- **Students**: Check-in to sessions, view attendance history, receive announcements
- **Lecturers**: Manage courses, create sessions, track attendance, make announcements, upload student lists
- **Admins**: Full system access and management

### Department Structure
- Computer Engineering (Software & Network)
- Electrical Engineering (Power Systems & Telecommunications)
- Civil Engineering
- Mechanical Engineering
- Chemical Engineering

### Course Naming Convention
- Course codes follow department prefixes: CEF (Computer), EEF (Electrical), CIV (Civil), MEF (Mechanical), CMF (Chemical)
- Level indication: 200, 300, 400, 500 (first digit after department prefix)
- Example: CEF210 (Computer Engineering, Level 200), EEF321 (Electrical Engineering, Level 300)

### Student ID Format
- Format: FE22A111
- FE: Institution prefix
- 22: Enrollment year (2022)
- A: Standard identifier
- 111: Sequential number

## API Endpoints

### Authentication
- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - User login
- `POST /api/auth/refresh` - Refresh access token
- `GET /api/auth/me` - Get current user info

### User Management
- `GET /api/users/profile` - Get user profile
- `PUT /api/users/profile` - Update user profile
- `POST /api/users/change-password` - Change password
- `GET /api/users/students` - Get students list (Admin/Lecturer)

### Course Management
- `POST /api/courses` - Create course (Lecturer/Admin)
- `GET /api/courses` - Get courses
- `GET /api/courses/<id>` - Get specific course
- `PUT /api/courses/<id>` - Update course
- `GET /api/courses/<id>/students` - Get course students
- `POST /api/courses/<id>/enroll` - Enroll in course (Student)

###  Session Management
- `POST /api/sessions` - Create session (Lecturer)
- `GET /api/sessions` - Get sessions
- `GET /api/sessions/<id>` - Get specific session
- `PUT /api/sessions/<id>` - Update session
- `DELETE /api/sessions/<id>` - Delete session
- `POST /api/sessions/<id>/start` - Start session attendance
- `POST /api/sessions/<id>/end` - End session attendance

### Attendance
- `POST /api/attendance/checkin` - Student check-in
- `GET /api/attendance/session/<id>` - Get session attendance
- `GET /api/attendance/student/<id>` - Get student attendance history
- `GET /api/attendance/course/<id>` - Get course attendance matrix
- `POST /api/attendance/mark` - Mark attendance (Lecturer)

### Announcements
- `POST /api/announcements` - Create announcement
- `GET /api/announcements` - Get announcements
- `GET /api/announcements/<id>` - Get specific announcement
- `PUT /api/announcements/<id>` - Update announcement
- `DELETE /api/announcements/<id>` - Delete announcement
- `GET /api/announcements/course/<id>` - Get course announcements

### Reports & Export
- `GET /api/reports/attendance/course/<id>/export` - Export course attendance
- `GET /api/reports/attendance/student/<id>/export` - Export student attendance
- `GET /api/reports/attendance/summary` - Get attendance summary

### File Upload
- `POST /api/uploads/students` - Upload student list (Excel/CSV)
- `GET /api/uploads/students/template` - Download student upload template

## Database Configuration

The system uses PostgreSQL with the following credentials:
- **Host**: localhost
- **Port**: 5432
- **Database**: AttendEaseg7
- **Username**: postgres
- **Password**: pgsql149

## Installation & Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Setup**:
   - Copy `.env.example` to `.env`
   - Update database credentials if needed

3. **Database Setup**:
   - Ensure PostgreSQL is running
   - Create database `AttendEaseg7`
   - Run the application to auto-create tables

4. **Run Application**:
   ```bash
   python run.py
   ```

The API will be available at `http://localhost:5000`

## Authentication

The API uses JWT (JSON Web Tokens) for authentication. Include the access token in the Authorization header:

```
Authorization: Bearer <access_token>
```

## File Upload Format

### Student Upload Template
Required columns:
- `student_id`: Student matricule (FE22A111 format)
- `first_name`: Student first name
- `last_name`: Student last name  
- `email`: Valid email address

Optional columns:
- `phone`: Phone number
- `department`: Department enum value
- `year_of_study`: 200, 300, 400, or 500

## Export Formats

Reports can be exported in three formats:
- **Excel** (.xlsx): Full formatting with multiple sheets
- **CSV** (.csv): Simple comma-separated values
- **PDF** (.pdf): Professional formatted reports

## Error Handling

The API returns consistent error responses:
```json
{
  "error": "Error message description"
}
```

HTTP status codes follow REST conventions:
- 200: Success
- 201: Created
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 500: Internal Server Error

## Future Enhancements

- Geofencing integration for location-based attendance
- Facial recognition for automated check-in
- Real-time notifications
- Mobile app integration
- Advanced analytics and reporting
- Attendance prediction algorithms

## Security Features

- Password hashing using Werkzeug
- JWT token-based authentication
- Role-based access control
- Input validation and sanitization
- SQL injection prevention through SQLAlchemy ORM
- File upload security with type validation

## Development Notes

- The system is designed to be modular and extensible
- Database models support future feature additions
- API endpoints follow RESTful conventions
- Comprehensive error handling and logging
- Scalable architecture for production deployment