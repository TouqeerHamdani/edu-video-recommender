from backend.app import app

# This is what gunicorn looks for
application = app

if __name__ == "__main__":
    app.run() 