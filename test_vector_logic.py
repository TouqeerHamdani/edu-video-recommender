import os
import sys

# Add current dir to path
sys.path.append(os.getcwd())

from collections import namedtuple
from unittest.mock import MagicMock, patch

# Mock dependencies to avoid actual DB connection failures or missing deps
sys.modules['backend'] = MagicMock()
sys.modules['backend.database'] = MagicMock()
sys.modules['backend.models'] = MagicMock()
sys.modules['sqlalchemy'] = MagicMock()
sys.modules['sqlalchemy.orm'] = MagicMock()

# Now import the scraper function we want to test
# We need to monkeypatch the imports INSIDE semantic_search.py because we haven't loaded it yet
with patch.dict('sys.modules', {
    'backend.database': MagicMock(),
    'backend.models': MagicMock(),
    'sqlalchemy': MagicMock(),
    'scraper.youtube_scraper': MagicMock()
}):
    # Manually import to control environment
    try:
        from scraper import semantic_search
        print("Imported semantic_search successfully")
    except ImportError as e:
        print(f"Import failed: {e}")
        sys.exit(1)

# Test 1: create_query_embedding (Should be None by default)
print("Test 1: Check default embedding creation")
emb = semantic_search.create_query_embedding("test")
if emb is None:
    print("PASS: Embedding is None by default (Phase 1 compliance)")
else:
    print("FAIL: Embedding should be None")

# Test 2: recommend() uses text search when embedding is None
print("Test 2: Check recommendation fallback logic")
# Reset mocks
semantic_search.text.reset_mock()

# Mock session and execute
mock_session = MagicMock()
semantic_search.get_session = MagicMock(return_value=mock_session)

# Mock result for SQL execution
MockRow = namedtuple(
    'Row', 
    [
        'youtube_id', 'title', 'description', 'thumbnail', 
        'duration', 'view_count', 'like_count', 'similarity'
    ]
)
mock_rows = [
    MockRow('vid1', 'Math Intro', 'Desc', 'url', 300, 1000, 100, 0.0),
    MockRow('vid2', 'Physics Intro', 'Desc', 'url', 600, 2000, 200, 0.0)
]
mock_session.execute.return_value = mock_rows

results = semantic_search.recommend("math", top_n=2)

# Check if text search SQL was definitely structured
# We check the arguments passed to 'text()' which generates the SQL
# inspect semantic_search.text directly as it is the object used
if semantic_search.text.called:
    # Get the last call to text()
    sql_arg = str(semantic_search.text.call_args[0][0])
    if "ILIKE" in sql_arg:
        print("PASS: Fallback uses ILIKE")
    else:
        print(f"FAIL: SQL does not look like text search: {sql_arg}")
else:
    print("FAIL: sqlalchemy.text() was not called")

# Test 3: recommend() uses vector search when embedding is PRESENT
print("Test 3: Check vector search logic")
# Reset mocks
semantic_search.text.reset_mock()

# Force embedding return
semantic_search.create_query_embedding = MagicMock(return_value=[0.1] * 384)

results_vector = semantic_search.recommend("math", top_n=2)

if semantic_search.text.called:
    sql_arg_vector = str(semantic_search.text.call_args[0][0])
    if "<=>" in sql_arg_vector:
         print("PASS: Vector search uses <=> operator")
    else:
         print(f"FAIL: SQL does not look like vector search: {sql_arg_vector}")
else:
    print("FAIL: sqlalchemy.text() not called for vector search")

print("Verification Complete")
