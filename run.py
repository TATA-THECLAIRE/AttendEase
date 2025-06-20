from app import create_app, db
from models import *

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        # Create all database tables
        db.create_all()
        print("Database tables created successfully!")
    
    # Run the application
    app.run(debug=True, host='0.0.0.0', port=5000)