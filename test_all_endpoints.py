import requests
import json
import time
from datetime import datetime, date, timedelta
import sys
import os

class AttendEaseAPITester:
    def __init__(self, base_url="http://localhost:5000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.tokens = {}
        self.test_data = {}
        self.results = {
            'passed': 0,
            'failed': 0,
            'errors': [],
            'warnings': []
        }
    
    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
    
    def make_request(self, method, endpoint, data=None, headers=None, expected_status=200, timeout=30):
        """Make HTTP request and validate response"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            if headers is None:
                headers = {}
        
            response = self.session.request(method, url, json=data, headers=headers, timeout=timeout)
        
            # Log request details
            self.log(f"{method} {endpoint} - Status: {response.status_code}")
        
            if response.status_code == expected_status:
                self.results['passed'] += 1
                try:
                    return response.json() if response.content else {}
                except:
                    return {}
            else:
                self.results['failed'] += 1
                error_msg = f"{method} {endpoint} - Expected {expected_status}, got {response.status_code}"
            
                # Try to get detailed error message
                try:
                    if response.content:
                        error_data = response.json()
                        if isinstance(error_data, dict):
                            error_detail = error_data.get('error', error_data.get('message', error_data.get('msg', 'Unknown error')))
                            error_msg += f" - {error_detail}"
                        else:
                            error_msg += f" - {str(error_data)[:200]}"
                    else:
                        error_msg += " - No response content"
                except:
                    error_msg += f" - Response: {response.text[:200]}"
            
                self.results['errors'].append(error_msg)
                self.log(error_msg, "ERROR")
                return None
            
        except requests.exceptions.Timeout:
            self.results['failed'] += 1
            error_msg = f"{method} {endpoint} - Request timeout after {timeout}s"
            self.results['errors'].append(error_msg)
            self.log(error_msg, "ERROR")
            return None
        except Exception as e:
            self.results['failed'] += 1
            error_msg = f"{method} {endpoint} - Exception: {str(e)}"
            self.results['errors'].append(error_msg)
            self.log(error_msg, "ERROR")
            return None
    
    def get_auth_headers(self, user_type="admin"):
        """Get authorization headers for different user types"""
        token = self.tokens.get(user_type)
        if token:
            return {"Authorization": f"Bearer {token}"}
        else:
            self.log(f"No token available for {user_type}", "WARNING")
            return {}
    
    def test_health_check(self):
        """Test health check endpoint"""
        self.log("=== Testing Health Check ===")
        response = self.make_request("GET", "/api/health")
        if response:
            self.log("✓ Health check passed")
            return True
        return False
    
    def test_auth_endpoints(self):
        """Test authentication endpoints"""
        self.log("=== Testing Authentication Endpoints ===")
        
        # Generate unique emails to avoid conflicts
        timestamp = str(int(time.time()))
        
        # Test admin registration
        admin_data = {
            "email": f"admin_{timestamp}@attendease.com",
            "password": "admin123456",
            "first_name": "Admin",
            "last_name": "User",
            "role": "ADMIN"
        }
        
        response = self.make_request("POST", "/api/auth/register", admin_data, expected_status=201)
        if response and 'access_token' in response:
            self.tokens['admin'] = response.get('access_token')
            self.test_data['admin_id'] = response.get('user', {}).get('id')
            self.test_data['admin_email'] = admin_data['email']
            self.log("✓ Admin registration successful")
        else:
            self.log("✗ Admin registration failed", "ERROR")
            return False
        
        # Test lecturer registration
        lecturer_data = {
            "email": f"lecturer_{timestamp}@attendease.com",
            "password": "lecturer123456",
            "first_name": "John",
            "last_name": "Lecturer",
            "role": "LECTURER"
        }
        
        response = self.make_request("POST", "/api/auth/register", lecturer_data, expected_status=201)
        if response and 'access_token' in response:
            self.tokens['lecturer'] = response.get('access_token')
            self.test_data['lecturer_id'] = response.get('user', {}).get('id')
            self.test_data['lecturer_email'] = lecturer_data['email']
            self.log("✓ Lecturer registration successful")
        else:
            self.log("✗ Lecturer registration failed", "ERROR")
            return False
        
        # Test student registration
        student_data = {
            "email": f"student_{timestamp}@attendease.com",
            "password": "student123456",
            "first_name": "Jane",
            "last_name": "Student",
            "role": "STUDENT",
            "student_data": {
                "student_id": f"FE22A{timestamp[-3:]}",
                "department": "COMPUTER_SOFTWARE",
                "year_of_study": 300
            }
        }
        
        response = self.make_request("POST", "/api/auth/register", student_data, expected_status=201)
        if response and 'access_token' in response:
            self.tokens['student'] = response.get('access_token')
            self.test_data['student_id'] = response.get('user', {}).get('id')
            self.test_data['student_email'] = student_data['email']
            # Get student profile ID properly
            user_data = response.get('user', {})
            if 'student_profile' in user_data and user_data['student_profile']:
                self.test_data['student_profile_id'] = user_data['student_profile']['id']
            else:
                self.test_data['student_profile_id'] = None
            self.log("✓ Student registration successful")
            self.log(f"Student profile ID: {self.test_data.get('student_profile_id')}")
        else:
            self.log("✗ Student registration failed", "ERROR")
            return False
        
        # Test login
        login_data = {
            "email": self.test_data.get('admin_email'),
            "password": "admin123456"
        }
        
        response = self.make_request("POST", "/api/auth/login", login_data)
        if response and 'access_token' in response:
            self.tokens['admin'] = response.get('access_token')
            self.log("✓ Admin login successful")
        else:
            self.log("✗ Admin login failed", "ERROR")
            return False
        
        # Test get current user
        response = self.make_request("GET", "/api/auth/me", headers=self.get_auth_headers('admin'))
        if response:
            self.log("✓ Get current user successful")
        else:
            self.log("✗ Get current user failed", "ERROR")
        
        return True
    
    def test_user_endpoints(self):
        """Test user management endpoints"""
        self.log("=== Testing User Management Endpoints ===")
        
        # Test get profile
        response = self.make_request("GET", "/api/users/profile", headers=self.get_auth_headers('admin'))
        if response:
            self.log("✓ Get profile successful")
        
        # Test update profile
        update_data = {
            "first_name": "Updated Admin",
            "phone": "+237123456789"
        }
        response = self.make_request("PUT", "/api/users/profile", update_data, headers=self.get_auth_headers('admin'))
        if response:
            self.log("✓ Update profile successful")
        
        # Test change password
        password_data = {
            "current_password": "admin123456",
            "new_password": "newadmin123456"
        }
        response = self.make_request("POST", "/api/users/change-password", password_data, headers=self.get_auth_headers('admin'))
        if response:
            self.log("✓ Change password successful")
        
        # Test get students
        response = self.make_request("GET", "/api/users/students", headers=self.get_auth_headers('admin'))
        if response:
            self.log("✓ Get students successful")
        
        # Test get students with filter
        response = self.make_request("GET", "/api/users/students?department=COMPUTER_SOFTWARE", headers=self.get_auth_headers('admin'))
        if response:
            self.log("✓ Get students with filter successful")
        
        return True
    
    def test_course_endpoints(self):
        """Test course management endpoints"""
        self.log("=== Testing Course Management Endpoints ===")
        
        # Test create course
        course_data = {
            "course_code": f"TEST{datetime.now().strftime('%H%M%S')}",
            "course_name": "Test Course for API Testing",
            "description": "A comprehensive test course for API validation",
            "level": 300,
            "department": "COMPUTER_SOFTWARE",
            "credits": 3,
            "semester": "Fall",
            "academic_year": "2023-2024"
        }
        
        response = self.make_request("POST", "/api/courses", course_data, headers=self.get_auth_headers('lecturer'), expected_status=201)
        if response and 'course' in response:
            self.test_data['course_id'] = response.get('course', {}).get('id')
            self.log("✓ Course creation successful")
        else:
            self.log("✗ Course creation failed", "ERROR")
            return False
        
        # Test get courses
        response = self.make_request("GET", "/api/courses", headers=self.get_auth_headers('lecturer'))
        if response:
            self.log("✓ Get courses successful")
        
        # Test get courses with filter
        response = self.make_request("GET", "/api/courses?department=COMPUTER_SOFTWARE", headers=self.get_auth_headers('lecturer'))
        if response:
            self.log("✓ Get courses with filter successful")
        
        # Test get specific course
        if 'course_id' in self.test_data:
            course_id = self.test_data['course_id']
            response = self.make_request("GET", f"/api/courses/{course_id}", headers=self.get_auth_headers('lecturer'))
            if response:
                self.log("✓ Get specific course successful")
            
            # Test update course
            update_data = {
                "description": "Updated course description for testing",
                "credits": 4
            }
            response = self.make_request("PUT", f"/api/courses/{course_id}", update_data, headers=self.get_auth_headers('lecturer'))
            if response:
                self.log("✓ Update course successful")
            
            # Test get course students
            response = self.make_request("GET", f"/api/courses/{course_id}/students", headers=self.get_auth_headers('lecturer'))
            if response:
                self.log("✓ Get course students successful")
        
        # Test student enrollment
        if 'course_id' in self.test_data:
            response = self.make_request("POST", f"/api/courses/{self.test_data['course_id']}/enroll", headers=self.get_auth_headers('student'), expected_status=201)
            if response:
                self.log("✓ Student enrollment successful")
            else:
                self.log("✗ Student enrollment failed", "ERROR")
        
        return True
    
    def test_session_endpoints(self):
        """Test session management endpoints"""
        self.log("=== Testing Session Management Endpoints ===")
        
        if 'course_id' not in self.test_data:
            self.log("Skipping session tests - no course available", "WARNING")
            return False
        
        # Test create session
        session_data = {
            "course_id": self.test_data['course_id'],
            "session_name": "Introduction to Software Testing",
            "session_date": (date.today() + timedelta(days=1)).strftime('%Y-%m-%d'),
            "start_time": "10:00",
            "end_time": "12:00",
            "location": "Room A101"
        }
        
        response = self.make_request("POST", "/api/sessions", session_data, headers=self.get_auth_headers('lecturer'), expected_status=201)
        if response and 'session' in response:
            self.test_data['session_id'] = response.get('session', {}).get('id')
            self.log("✓ Session creation successful")
        else:
            self.log("✗ Session creation failed", "ERROR")
            return False
        
        # Test get sessions
        response = self.make_request("GET", "/api/sessions", headers=self.get_auth_headers('lecturer'))
        if response:
            self.log("✓ Get sessions successful")
        
        # Test get sessions with filter
        response = self.make_request("GET", f"/api/sessions?course_id={self.test_data['course_id']}", headers=self.get_auth_headers('lecturer'))
        if response:
            self.log("✓ Get sessions with filter successful")
        
        # Test get specific session
        if 'session_id' in self.test_data:
            session_id = self.test_data['session_id']
            response = self.make_request("GET", f"/api/sessions/{session_id}", headers=self.get_auth_headers('lecturer'))
            if response:
                self.log("✓ Get specific session successful")
            
            # Test update session
            update_data = {
                "session_name": "Updated Session Name for Testing",
                "location": "Room B202"
            }
            response = self.make_request("PUT", f"/api/sessions/{session_id}", update_data, headers=self.get_auth_headers('lecturer'))
            if response:
                self.log("✓ Update session successful")
            
            # Test start session
            response = self.make_request("POST", f"/api/sessions/{session_id}/start", headers=self.get_auth_headers('lecturer'))
            if response:
                self.log("✓ Start session successful")
            
            # Test end session
            response = self.make_request("POST", f"/api/sessions/{session_id}/end", headers=self.get_auth_headers('lecturer'))
            if response:
                self.log("✓ End session successful")
        
        return True
    
    def test_attendance_endpoints(self):
        """Test attendance management endpoints"""
        self.log("=== Testing Attendance Management Endpoints ===")
        
        if 'session_id' not in self.test_data:
            self.log("Skipping attendance tests - no session available", "WARNING")
            return False
        
        session_id = self.test_data['session_id']
        
        # First, start the session for attendance
        response = self.make_request("POST", f"/api/sessions/{session_id}/start", headers=self.get_auth_headers('lecturer'))
        if response:
            self.log("✓ Session started for attendance")
        
        # Test student check-in
        checkin_data = {
            "session_id": session_id
        }
        response = self.make_request("POST", "/api/attendance/checkin", checkin_data, headers=self.get_auth_headers('student'), expected_status=201)
        if response:
            self.log("✓ Student check-in successful")
        else:
            self.log("✗ Student check-in failed", "ERROR")
        
        # Test get session attendance (as lecturer)
        response = self.make_request("GET", f"/api/attendance/session/{session_id}", headers=self.get_auth_headers('lecturer'))
        if response:
            self.log("✓ Get session attendance successful")
        
        # Test get student attendance
        if self.test_data.get('student_profile_id'):
            student_profile_id = self.test_data['student_profile_id']
            response = self.make_request("GET", f"/api/attendance/student/{student_profile_id}", headers=self.get_auth_headers('admin'))
            if response:
                self.log("✓ Get student attendance successful")
        else:
            self.log("Skipping student attendance test - no student profile ID", "WARNING")
        
        # Test get course attendance
        if 'course_id' in self.test_data:
            response = self.make_request("GET", f"/api/attendance/course/{self.test_data['course_id']}", headers=self.get_auth_headers('lecturer'))
            if response:
                self.log("✓ Get course attendance successful")
        
        # Test mark attendance (lecturer)
        if self.test_data.get('student_profile_id'):
            mark_data = {
                "session_id": session_id,
                "student_id": self.test_data['student_profile_id'],
                "status": "PRESENT",
                "notes": "Test attendance marking via API"
            }
            response = self.make_request("POST", "/api/attendance/mark", mark_data, headers=self.get_auth_headers('lecturer'))
            if response:
                self.log("✓ Mark attendance successful")
        else:
            self.log("Skipping mark attendance test - no student profile ID", "WARNING")
        
        return True
    
    def test_announcement_endpoints(self):
        """Test announcement management endpoints"""
        self.log("=== Testing Announcement Management Endpoints ===")
        
        # Test create global announcement (admin only)
        global_announcement = {
            "title": "Global Test Announcement",
            "content": "This is a comprehensive test global announcement for API validation",
            "is_global": True,
            "priority": "high"
        }
        
        response = self.make_request("POST", "/api/announcements", global_announcement, headers=self.get_auth_headers('admin'), expected_status=201)
        if response and 'announcement' in response:
            self.test_data['global_announcement_id'] = response.get('announcement', {}).get('id')
            self.log("✓ Global announcement creation successful")
        else:
            self.log("✗ Global announcement creation failed", "ERROR")
        
        # Test create course announcement
        if 'course_id' in self.test_data:
            course_announcement = {
                "title": "Course Test Announcement",
                "content": "This is a comprehensive test course announcement for API validation",
                "course_id": self.test_data['course_id'],
                "priority": "medium"
            }
            
            response = self.make_request("POST", "/api/announcements", course_announcement, headers=self.get_auth_headers('lecturer'), expected_status=201)
            if response and 'announcement' in response:
                self.test_data['course_announcement_id'] = response.get('announcement', {}).get('id')
                self.log("✓ Course announcement creation successful")
            else:
                self.log("✗ Course announcement creation failed", "ERROR")
        
        # Test get announcements
        response = self.make_request("GET", "/api/announcements", headers=self.get_auth_headers('student'))
        if response:
            self.log("✓ Get announcements successful")
        
        # Test get announcements with filter
        response = self.make_request("GET", "/api/announcements?priority=high", headers=self.get_auth_headers('student'))
        if response:
            self.log("✓ Get announcements with filter successful")
        
        # Test get specific announcement
        if 'global_announcement_id' in self.test_data:
            announcement_id = self.test_data['global_announcement_id']
            response = self.make_request("GET", f"/api/announcements/{announcement_id}", headers=self.get_auth_headers('student'))
            if response:
                self.log("✓ Get specific announcement successful")
            
            # Test update announcement
            update_data = {
                "title": "Updated Global Test Announcement",
                "priority": "normal"
            }
            response = self.make_request("PUT", f"/api/announcements/{announcement_id}", update_data, headers=self.get_auth_headers('admin'))
            if response:
                self.log("✓ Update announcement successful")
        
        # Test get course announcements
        if 'course_id' in self.test_data:
            response = self.make_request("GET", f"/api/announcements/course/{self.test_data['course_id']}", headers=self.get_auth_headers('student'))
            if response:
                self.log("✓ Get course announcements successful")
        
        return True
    
    def test_report_endpoints(self):
        """Test report generation endpoints"""
        self.log("=== Testing Report Generation Endpoints ===")
        
        # Test attendance summary
        response = self.make_request("GET", "/api/reports/attendance/summary", headers=self.get_auth_headers('lecturer'))
        if response:
            self.log("✓ Attendance summary successful")
        
        if 'course_id' in self.test_data:
            course_id = self.test_data['course_id']
            
            # Test course attendance export (different formats)
            response = self.make_request("GET", f"/api/reports/attendance/course/{course_id}/export?format=csv", headers=self.get_auth_headers('lecturer'))
            if response is not None:  # Could be binary data
                self.log("✓ Course attendance export (CSV) successful")
            
            response = self.make_request("GET", f"/api/reports/attendance/course/{course_id}/export?format=excel", headers=self.get_auth_headers('lecturer'))
            if response is not None:
                self.log("✓ Course attendance export (Excel) successful")
            
            response = self.make_request("GET", f"/api/reports/attendance/course/{course_id}/export?format=pdf", headers=self.get_auth_headers('lecturer'))
            if response is not None:
                self.log("✓ Course attendance export (PDF) successful")
        
        # Test student attendance export
        if self.test_data.get('student_profile_id'):
            student_profile_id = self.test_data['student_profile_id']
            response = self.make_request("GET", f"/api/reports/attendance/student/{student_profile_id}/export?format=excel", headers=self.get_auth_headers('admin'))
            if response is not None:
                self.log("✓ Student attendance export successful")
        else:
            self.log("Skipping student attendance export - no student profile ID", "WARNING")
        
        return True
    
    def test_upload_endpoints(self):
        """Test file upload endpoints"""
        self.log("=== Testing Upload Endpoints ===")
        
        # Test download student template
        response = self.make_request("GET", "/api/uploads/students/template", headers=self.get_auth_headers('lecturer'))
        if response is not None:
            self.log("✓ Download student template successful")
        
        self.log("Note: File upload testing requires actual files - skipping detailed upload tests", "WARNING")
        return True
    
    def test_error_scenarios(self):
        """Test various error scenarios"""
        self.log("=== Testing Error Scenarios ===")
        
        # Test unauthorized access
        response = self.make_request("GET", "/api/users/profile", expected_status=401)
        if response is None:  # Expected to fail
            self.log("✓ Unauthorized access properly blocked")
        
        # Test invalid endpoints
        response = self.make_request("GET", "/api/nonexistent", expected_status=404)
        if response is None:  # Expected to fail
            self.log("✓ Invalid endpoint properly handled")
        
        # Test invalid data
        invalid_course = {
            "course_code": "",  # Empty required field
            "course_name": "Test Course"
        }
        response = self.make_request("POST", "/api/courses", invalid_course, headers=self.get_auth_headers('lecturer'), expected_status=400)
        if response is None:  # Expected to fail
            self.log("✓ Invalid data properly rejected")
        
        # Test access control
        response = self.make_request("GET", "/api/users/students", headers=self.get_auth_headers('student'), expected_status=403)
        if response is None:  # Expected to fail
            self.log("✓ Access control properly enforced")
        
        return True
    
    def cleanup_test_data(self):
        """Clean up test data (optional)"""
        self.log("=== Cleaning Up Test Data ===")
        
        # Delete test announcements
        if 'global_announcement_id' in self.test_data:
            response = self.make_request("DELETE", f"/api/announcements/{self.test_data['global_announcement_id']}", headers=self.get_auth_headers('admin'))
            if response:
                self.log("✓ Global announcement deleted")
        
        if 'course_announcement_id' in self.test_data:
            response = self.make_request("DELETE", f"/api/announcements/{self.test_data['course_announcement_id']}", headers=self.get_auth_headers('lecturer'))
            if response:
                self.log("✓ Course announcement deleted")
        
        self.log("Cleanup completed")
    
    def check_database_users(self):
        """Check if test users were created in database"""
        self.log("=== Checking Database Users ===")
        
        # Get all users to verify they were created
        response = self.make_request("GET", "/api/users/students", headers=self.get_auth_headers('admin'))
        if response and 'students' in response:
            students = response['students']
            self.log(f"✓ Found {len(students)} students in database")
            for student in students:
                self.log(f"  - Student: {student.get('student_id')} - {student.get('user', {}).get('first_name')} {student.get('user', {}).get('last_name')}")
        
        # Check admin and lecturer profiles
        response = self.make_request("GET", "/api/users/profile", headers=self.get_auth_headers('admin'))
        if response:
            self.log(f"✓ Admin profile: {response.get('first_name')} {response.get('last_name')} ({response.get('email')})")
        
        response = self.make_request("GET", "/api/users/profile", headers=self.get_auth_headers('lecturer'))
        if response:
            self.log(f"✓ Lecturer profile: {response.get('first_name')} {response.get('last_name')} ({response.get('email')})")
        
        response = self.make_request("GET", "/api/users/profile", headers=self.get_auth_headers('student'))
        if response:
            self.log(f"✓ Student profile: {response.get('first_name')} {response.get('last_name')} ({response.get('email')})")
    
    def run_all_tests(self, cleanup=False):
        """Run all endpoint tests"""
        self.log("Starting comprehensive API endpoint testing...")
        start_time = time.time()
        
        try:
            # Test endpoints in logical order
            tests = [
                ("Health Check", self.test_health_check),
                ("Authentication", self.test_auth_endpoints),
                ("User Management", self.test_user_endpoints),
                ("Course Management", self.test_course_endpoints),
                ("Session Management", self.test_session_endpoints),
                ("Attendance Management", self.test_attendance_endpoints),
                ("Announcement Management", self.test_announcement_endpoints),
                ("Report Generation", self.test_report_endpoints),
                ("Upload Endpoints", self.test_upload_endpoints),
                ("Error Scenarios", self.test_error_scenarios)
            ]
            
            for test_name, test_func in tests:
                self.log(f"\n{'='*60}")
                self.log(f"Running {test_name} Tests")
                self.log(f"{'='*60}")
                
                try:
                    test_func()
                except Exception as e:
                    self.log(f"Error in {test_name}: {str(e)}", "ERROR")
                    self.results['errors'].append(f"{test_name}: {str(e)}")
            
            # Check database users
            self.check_database_users()
            
            # Optional cleanup
            if cleanup:
                self.cleanup_test_data()
            
        except KeyboardInterrupt:
            self.log("Testing interrupted by user", "WARNING")
        except Exception as e:
            self.log(f"Unexpected error during testing: {str(e)}", "ERROR")
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Print summary
        return self.print_summary(duration)
    
    def print_summary(self, duration):
        """Print test results summary"""
        total_tests = self.results['passed'] + self.results['failed']
        success_rate = (self.results['passed'] / total_tests * 100) if total_tests > 0 else 0
        
        print("\n" + "="*80)
        print("ATTENDEASE API TESTING SUMMARY")
        print("="*80)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {self.results['passed']}")
        print(f"Failed: {self.results['failed']}")
        print(f"Success Rate: {success_rate:.1f}%")
        print(f"Duration: {duration:.2f} seconds")
        
        # Print test data summary
        print(f"\nTest Data Created:")
        print(f"- Admin ID: {self.test_data.get('admin_id', 'N/A')}")
        print(f"- Lecturer ID: {self.test_data.get('lecturer_id', 'N/A')}")
        print(f"- Student ID: {self.test_data.get('student_id', 'N/A')}")
        print(f"- Student Profile ID: {self.test_data.get('student_profile_id', 'N/A')}")
        print(f"- Course ID: {self.test_data.get('course_id', 'N/A')}")
        print(f"- Session ID: {self.test_data.get('session_id', 'N/A')}")
        
        if self.results['warnings']:
            print(f"\nWarnings ({len(self.results['warnings'])}):")
            print("-" * 40)
            for i, warning in enumerate(self.results['warnings'], 1):
                print(f"{i}. {warning}")
        
        if self.results['errors']:
            print(f"\nErrors ({len(self.results['errors'])}):")
            print("-" * 40)
            for i, error in enumerate(self.results['errors'], 1):
                print(f"{i}. {error}")
        
        print("\n" + "="*80)
        
        # Return exit code based on results
        return 0 if self.results['failed'] == 0 else 1

def main():
    """Main function to run the tests"""
    import argparse
    
    parser = argparse.ArgumentParser(description='AttendEase API Comprehensive Endpoint Tester')
    parser.add_argument('--url', default='http://localhost:5000', help='Base URL of the API (default: http://localhost:5000)')
    parser.add_argument('--cleanup', action='store_true', help='Clean up test data after testing')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    
    args = parser.parse_args()
    
    # Create and run tester
    tester = AttendEaseAPITester(base_url=args.url)
    exit_code = tester.run_all_tests(cleanup=args.cleanup)
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main()