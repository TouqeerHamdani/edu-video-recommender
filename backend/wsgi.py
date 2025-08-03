from backend.app import app

# This is what gunicorn looks for
application = app

# Production WSGI configuration
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug) 