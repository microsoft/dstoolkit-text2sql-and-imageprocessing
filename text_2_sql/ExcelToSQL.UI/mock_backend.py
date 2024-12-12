from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Mock storage for uploaded files
mock_files = []

@app.route('/api/upload', methods=['POST'])
def upload_file():
    # Mock file upload response
    file_info = {
        "id": f"file_{len(mock_files) + 1}",
        "name": request.files.get('file', type=str) or "example.xlsx",
        "uploadDate": datetime.now().isoformat()
    }
    mock_files.append(file_info)
    return jsonify(file_info)

@app.route('/api/query', methods=['POST'])
def query():
    # Mock query response
    return jsonify({
        "sql": "SELECT region, SUM(sales) as total_sales FROM sales GROUP BY region",
        "results": [
            {"region": "North", "total_sales": 1000},
            {"region": "South", "total_sales": 2000},
            {"region": "East", "total_sales": 1500},
            {"region": "West", "total_sales": 1800}
        ],
        "explanation": "Here's the breakdown of sales by region..."
    })

@app.route('/api/files', methods=['GET'])
def get_files():
    return jsonify(mock_files)

if __name__ == '__main__':
    print("Starting Flask server at http://localhost:5000")
    app.run(port=5000)
