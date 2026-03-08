import sys
from unittest.mock import MagicMock

# Mock dependencies
for mod in ['fastapi', 'fastapi.middleware', 'fastapi.middleware.cors', 'fastapi.responses', 'fastapi.staticfiles',
            'dotenv', 'httpx', 'isodate', 'pgvector', 'pgvector.sqlalchemy']:
    sys.modules[mod] = MagicMock()

try:
    from backend import app
    print("Backend App imported successfully!")
except Exception as e:
    print(f"Error importing app: {e}")

try:
    from scraper import semantic_search
    print("Semantic Search imported successfully!")
except Exception as e:
    print(f"Error importing semantic_search: {e}")
