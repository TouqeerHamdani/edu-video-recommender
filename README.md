# AI-Powered Educational Video Recommender 🎓🔍

This project is an intelligent educational video recommender system that fetches videos from YouTube and ranks them using semantic search. It helps students find relevant content based on subject, topic, and video duration.

## 📌 Features
- 🔎 Search for educational content using natural language queries
- 📹 YouTube API integration for real-time video data
- 🤖 Semantic search using Sentence-BERT embeddings
- 🧠 Smart ranking based on meaning, not just keywords
- 🗂 Background video scraping and database caching
- 🧾 Simple UI using HTML, CSS, and JavaScript

## 🧱 Project Structure
```
edu-video-recommender/
├── backend/         # Flask API
├── scraper/         # YouTube data fetching and embedding
├── frontend/        # HTML, CSS, JS frontend
├── .env             # API keys (not committed)
├── requirements.txt # Python dependencies
└── README.md
```

## 🧪 Getting Started

1. Clone this repo:
```bash
git clone https://github.com/yourusername/edu-video-recommender.git
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Add your `.env` file with your YouTube API key:
```env
YOUTUBE_API_KEY=your_key_here
```

4. Run the scraper:
```bash
python scraper/youtube_scraper.py
```

## 🔧 To Do
- [ ] PostgreSQL integration
- [ ] Embedding + semantic similarity
- [ ] Flask API
- [ ] Frontend UI
