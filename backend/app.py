from flask import Flask, request, jsonify
from flask_cors import CORS
from scraper.semantic_search import recommend
from scraper.semantic_search import recommend, log_search

app = Flask(__name__)
CORS(app)  # Allow frontend requests from any domain (you can restrict later)

@app.route("/")
def home():
    return {"status": "ok", "message": "Edu Video Recommender API"}


@app.route("/api/recommend", methods=["GET"])
def get_recommendations():
    query = request.args.get("query", "")
    user = request.args.get("user", "guest")

    if not query:
        return jsonify({"error": "Missing query"}), 400

    try:
        log_search(query, user_id=user)
        results = recommend(query, top_n=5, user_id=user)
        return jsonify({"results": results})
    except Exception as e:
        print("❌ Error in /api/recommend:", e)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
