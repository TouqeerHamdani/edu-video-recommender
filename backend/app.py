from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from scraper.semantic_search import recommend, log_search
from backend.auth import auth_bp  # Import the auth blueprint
import os

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)  # Allow frontend requests from any domain (you can restrict later)

# Register the authentication blueprint
app.register_blueprint(auth_bp)

@app.route("/")
def home():
    return send_from_directory(app.static_folder, 'project.html')

@app.route("/auth")
def auth():
    return send_from_directory(app.static_folder, 'auth.html')

@app.route("/results")
def results():
    return send_from_directory(app.static_folder, 'results.html')

@app.route("/video")
def video():
    return send_from_directory(app.static_folder, 'video.html')

@app.route("/api/health")
def health():
    return {"status": "ok", "message": "Edu Video Recommender API"}


@app.route("/api/recommend", methods=["GET"])
def get_recommendations():
    query = request.args.get("query", "")
    user = request.args.get("user", "guest")
    duration = request.args.get("duration", "medium")
    allowed_durations = {"any", "short", "medium", "long"}
    duration = duration.lower()
    if duration not in allowed_durations:
        print(f"Invalid duration: {duration}. Defaulting to 'medium'.")
        duration = "medium"

    if not query:
        return jsonify({"error": "Missing query"}), 400

    try:
        log_search(query, user_id=user)
        results = recommend(query, top_n=10, user_id=user, video_duration=duration)
        return jsonify({"results": results})
    except Exception as e:
        print("❌ Error in /api/recommend:", e)
        return jsonify({"error": str(e)}), 500

# Catch-all route for static files
@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

# WSGI application for Vercel
app.debug = True
