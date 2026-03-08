
with open("scraper/semantic_search.py", "r") as f:
    content = f.read()

# Replace the create_query_embedding and create_query_embeddings functions
old_functions = """# Server-side embedding cache — keyed by query string, value is the raw float list.
# Embeddings are deterministic so no expiry is needed. Each 384-dim vector ≈ 1.5 KB,
# so 1,000 entries ≈ 1.5 MB. Shared across all requests in this process (report §2.1).
_embedding_cache: dict[str, list] = {}


async def create_query_embedding(query):
    \"\"\"
    Create query embedding using Cloudflare Workers AI bge-small-en-v1.5.
    Returns 384-dimensional embedding for vector search.
    Result is cached in-process to avoid repeated Cloudflare API calls (report §2.1).
    \"\"\"
    if query in _embedding_cache:
        return np.array(_embedding_cache[query], dtype=np.float32)

    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
        logging.warning("Cloudflare credentials not set. Vector search disabled.")
        return None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                CLOUDFLARE_BGE_URL,
                headers={"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}"},
                json={"text": query},
            )

        if response.status_code != 200:
            logging.error(f"Cloudflare API error: {response.status_code} - {response.text}")
            return None

        result = response.json()

        # Extract embedding from response
        if result.get("success") and result.get("result", {}).get("data"):
            embedding = result["result"]["data"][0]
            vector = np.array(embedding, dtype=np.float32)
            _embedding_cache[query] = embedding  # store raw list, not numpy array
            return vector
        else:
            logging.error(f"Unexpected Cloudflare response: {result}")
            return None

    except Exception as e:
        logging.error(f"Failed to create query embedding: {e}")
        return None


async def create_query_embeddings(queries):
    \"\"\"
    Batch-embed multiple queries in a single Cloudflare API call.
    Falls back to per-query calls on batch failure.
    Returns a list of numpy arrays (None entries filtered out).
    \"\"\"
    if not queries:
        return []
    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
        logging.warning("Cloudflare credentials not set. Vector search disabled.")
        return []

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                CLOUDFLARE_BGE_URL,
                headers={"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}"},
                json={"text": queries},
            )
        if response.status_code == 200:
            result = response.json()
            if result.get("success") and result.get("result", {}).get("data"):
                data = result["result"]["data"]
                return [np.array(emb, dtype=np.float32) for emb in data if emb]
    except Exception as e:
        logging.warning(f"Batch embedding failed, falling back to per-query: {e}")

    # Fallback: per-query calls
    embeddings = []
    for q in queries:
        emb = await create_query_embedding(q)
        if emb is not None:
            embeddings.append(emb)
    return embeddings"""

new_functions = """# Server-side embedding cache — keyed by query string, value is the raw float list.
# Embeddings are deterministic so no expiry is needed. Each 384-dim vector ≈ 1.5 KB,
# so 1,000 entries ≈ 1.5 MB. Shared across all requests in this process (report §2.1).
_embedding_cache: dict[str, list] = {}

# Global shared HTTP client for Cloudflare API calls.
# Reusing the client avoids connection setup overhead on every call.
_cf_http_client: httpx.AsyncClient | None = None

def _get_cf_client() -> httpx.AsyncClient:
    global _cf_http_client
    if _cf_http_client is None:
        _cf_http_client = httpx.AsyncClient(timeout=30)
    return _cf_http_client

async def create_query_embedding(query):
    \"\"\"
    Create query embedding using Cloudflare Workers AI bge-small-en-v1.5.
    Returns 384-dimensional embedding for vector search.
    Result is cached in-process to avoid repeated Cloudflare API calls (report §2.1).
    \"\"\"
    if query in _embedding_cache:
        return np.array(_embedding_cache[query], dtype=np.float32)

    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
        logging.warning("Cloudflare credentials not set. Vector search disabled.")
        return None

    try:
        client = _get_cf_client()
        response = await client.post(
            CLOUDFLARE_BGE_URL,
            headers={"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}"},
            json={"text": query},
            timeout=10
        )

        if response.status_code != 200:
            logging.error(f"Cloudflare API error: {response.status_code} - {response.text}")
            return None

        result = response.json()

        # Extract embedding from response
        if result.get("success") and result.get("result", {}).get("data"):
            embedding = result["result"]["data"][0]
            vector = np.array(embedding, dtype=np.float32)
            _embedding_cache[query] = embedding  # store raw list, not numpy array
            return vector
        else:
            logging.error(f"Unexpected Cloudflare response: {result}")
            return None

    except Exception as e:
        logging.error(f"Failed to create query embedding: {e}")
        return None


async def create_query_embeddings(queries):
    \"\"\"
    Batch-embed multiple queries in a single Cloudflare API call.
    Falls back to per-query calls on batch failure.
    Returns a list of numpy arrays (None entries filtered out).
    \"\"\"
    if not queries:
        return []
    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
        logging.warning("Cloudflare credentials not set. Vector search disabled.")
        return []

    try:
        client = _get_cf_client()
        response = await client.post(
            CLOUDFLARE_BGE_URL,
            headers={"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}"},
            json={"text": queries},
            timeout=30
        )
        if response.status_code == 200:
            result = response.json()
            if result.get("success") and result.get("result", {}).get("data"):
                data = result["result"]["data"]
                return [np.array(emb, dtype=np.float32) for emb in data if emb]
    except Exception as e:
        logging.warning(f"Batch embedding failed, falling back to per-query: {e}")

    # Fallback: per-query calls
    embeddings = []
    for q in queries:
        emb = await create_query_embedding(q)
        if emb is not None:
            embeddings.append(emb)
    return embeddings"""

if old_functions in content:
    content = content.replace(old_functions, new_functions)
    with open("scraper/semantic_search.py", "w") as f:
        f.write(content)
    print("Successfully replaced create_query_embedding")
else:
    print("Could not find old_functions in file")
