from flask import Flask, request, jsonify
from flask_cors import CORS
from auth_utils import valid_api_key_required, extractUserEmailFromRequest, InvalidTokenError
from api_endpoints.handler import GenerateHandler
from database.db import get_db_connection, init_database

app = Flask(__name__)
CORS(app)

# Initialize database when app starts
init_database()

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "message": "Anote Synthetic Data API Server",
        "version": "1.0.0",
        "endpoints": {
            "generate": "/public/generate (POST)",
            "health": "/health (GET)",
            "database": "/database/query (GET)"
        }
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "message": "Server is running"})

@app.route('/database/query', methods=['GET'])
def query_database():
    """Query the database to see stored requests and generated data"""
    try:
        conn, cursor = get_db_connection()
        
        # Get recent requests
        cursor.execute('''
            SELECT 
                sr.id,
                sr.task_type,
                sr.prompt,
                sr.columns,
                sr.num_rows,
                sr.created,
                gd.data
            FROM synthetic_requests sr
            LEFT JOIN generated_data gd ON sr.id = gd.request_id
            ORDER BY sr.created DESC
            LIMIT 10
        ''')
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'request_id': row['id'],
                'task_type': row['task_type'],
                'prompt': row['prompt'],
                'columns': row['columns'],
                'num_rows': row['num_rows'],
                'created': row['created'],
                'generated_data': row['data']
            })
        
        conn.close()
        return jsonify({
            "message": "Database query successful",
            "count": len(results),
            "results": results
        })
        
    except Exception as e:
        return jsonify({"error": f"Database query failed: {str(e)}"}), 500

@app.route('/public/generate', methods=['POST'])
# @valid_api_key_required
def generate():
    try:
        # Temporarily disable authentication for testing
        user_email = "test@example.com"
        # user_email = extractUserEmailFromRequest(request)
    except InvalidTokenError:
        return jsonify({"error": "Invalid JWT"}), 401
    return GenerateHandler(request, user_email)
