# Edu Video Recommender

A full-stack application for recommending educational YouTube videos using semantic search, user authentication, and personalized features.

## Features
- User registration and login (JWT authentication)
- Personalized video recommendations
- Duration and topic filtering
- Watch history and user search logging
- Modern frontend with login/register page
- Background scraping and semantic ranking

## Setup Instructions

### 1. Clone the repository
```sh
git clone <your-repo-url>
cd edu-video-recommender
```

### 2. Install Python dependencies
```sh
pip install -r requirements.txt
```

### 3. Set up the database
- Create a PostgreSQL database and user.
- Run the provided SQL to create tables (`users`, `videos`, `user_searches`, etc.).

### 4. Environment Variables
Create a `.env` file in the root directory with:
```
YOUTUBE_API_KEY=your_youtube_api_key
DB_NAME=your_db_name
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432
JWT_SECRET=your_jwt_secret
```

### 5. Run the backend
```sh
python backend/app.py
```

### 6. Run the frontend
- Open `frontend/project.html` or `frontend/auth.html` in your browser.

## Authentication
- Register or log in at `/frontend/auth.html`.
- JWT token is stored in localStorage and used for protected endpoints.

## API Endpoints
- `POST /api/register` — Register a new user
- `POST /api/login` — Log in and receive a JWT token
- `GET /api/protected` — Example protected endpoint (requires JWT)
- `GET /api/recommend` — Get video recommendations

## Requirements
See `requirements.txt` for all Python dependencies.

## Contributing
Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.

## License
[MIT](LICENSE)
