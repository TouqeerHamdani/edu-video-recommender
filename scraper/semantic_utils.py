'''from sentence_transformers import SentenceTransformer
import numpy as np

# Use a verified tiny SBERT model that actually exists
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")  # 384 dimensions, 90MB

def embed_text(text):
    return model.encode([text])[0]

def cosine_similarity(vec1, vec2):
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)) '''