from flask import Flask, request, jsonify
from flask_cors import CORS
from scraper.semantic_search import recommend, log_search
from backend.auth import auth_bp  # Import the auth blueprint

app = Flask(__name__)
CORS(app)  # Allow frontend requests from any domain (you can restrict later)

# Register the authentication blueprint
app.register_blueprint(auth_bp)

@app.route("/")
def home():
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
