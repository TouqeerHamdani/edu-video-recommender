from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from scraper.semantic_search import recommend, log_search
from backend.auth import auth_bp  # Import the auth blueprint
import os
import logging
from logging.handlers import RotatingFileHandler
from config import config

def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'production')
    
    app = Flask(__name__, static_folder='../frontend', static_url_path='')
    app.config.from_object(config[config_name])
    
    CORS(app)  # Allow frontend requests from any domain (you can restrict later)
    
    # Configure logging
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/edu_video_recommender.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Edu Video Recommender startup')
    
    # Database connection error handling
    def check_db_connection():
        try:
            from scraper.db import get_connection
            conn = get_connection()
            conn.close()
            return True
        except Exception as e:
            app.logger.error(f"Database connection failed: {e}")
            return False
    
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
        db_status = "connected" if check_db_connection() else "disconnected"
        return {
            "status": "ok", 
            "message": "Edu Video Recommender API",
            "database": db_status,
            "environment": app.config['FLASK_ENV']
        }
    
    @app.route("/api/recommend", methods=["GET"])
    def get_recommendations():
        query = request.args.get("query", "")
        user = request.args.get("user", "guest")
        duration = request.args.get("duration", "medium")
        allowed_durations = {"any", "short", "medium", "long"}
        duration = duration.lower()
        if duration not in allowed_durations:
            app.logger.warning(f"Invalid duration: {duration}. Defaulting to 'medium'.")
            duration = "medium"
    
        if not query:
            return jsonify({"error": "Missing query"}), 400
    
        try:
            # Check database connection first
            if not check_db_connection():
                return jsonify({"error": "Database connection unavailable"}), 503
            
            log_search(query, user_id=user)
            results = recommend(query, top_n=10, user_id=user, video_duration=duration)
            return jsonify({"results": results})
        except Exception as e:
            app.logger.error(f"Error in /api/recommend: {e}")
            return jsonify({"error": "Internal server error"}), 500
    
    # Catch-all route for static files
    @app.route("/<path:filename>")
    def static_files(filename):
        return send_from_directory(app.static_folder, filename)
    
    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify({"error": "Not found"}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Internal server error: {error}")
        return jsonify({"error": "Internal server error"}), 500
    
    # Add startup health check
    @app.before_first_request
    def startup_health_check():
        app.logger.info("Starting health check...")
        if not check_db_connection():
            app.logger.error("Database connection failed during startup")
        else:
            app.logger.info("Database connection successful")
    
    return app

# Create the app instance
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
