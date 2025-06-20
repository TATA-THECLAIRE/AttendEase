from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from config import config
import os

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
cors = CORS()
jwt = JWTManager()

def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app)
    jwt.init_app(app)
    
    # JWT Configuration - Fix the subject string issue
    @jwt.user_identity_loader
    def user_identity_lookup(user):
        """Convert user ID to string for JWT subject"""
        return str(user)
    
    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        """Load user from JWT data"""
        from models import User
        identity = jwt_data["sub"]
        return User.query.filter_by(id=int(identity)).one_or_none()
    
    # Create upload directory
    upload_dir = app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    
    # Register blueprints
    from routes.auth import auth_bp
    from routes.users import users_bp
    from routes.courses import courses_bp
    from routes.sessions import sessions_bp
    from routes.attendance import attendance_bp
    from routes.announcements import announcements_bp
    from routes.reports import reports_bp
    from routes.uploads import uploads_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(courses_bp, url_prefix='/api/courses')
    app.register_blueprint(sessions_bp, url_prefix='/api/sessions')
    app.register_blueprint(attendance_bp, url_prefix='/api/attendance')
    app.register_blueprint(announcements_bp, url_prefix='/api/announcements')
    app.register_blueprint(reports_bp, url_prefix='/api/reports')
    app.register_blueprint(uploads_bp, url_prefix='/api/uploads')
    
    # Health check endpoint
    @app.route('/api/health')
    def health_check():
        return {'status': 'healthy', 'message': 'AttendEase API is running'}
    
    return app

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)
