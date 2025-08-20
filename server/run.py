#!/usr/bin/env python3
"""
Run script for the Anote Synthetic Data API server
"""

from app import app
from database.db import init_database

if __name__ == "__main__":
    print("Starting Anote Synthetic Data API server...")
    print("Initializing database...")
    init_database()
    print("Database initialized successfully!")
    print("Server will be available at: http://localhost:5000")
    print("API endpoint: http://localhost:5000/public/generate")
    print("Press Ctrl+C to stop the server")
    
    # Run the Flask app in debug mode for development
    app.run(debug=True, host='0.0.0.0', port=5000) 