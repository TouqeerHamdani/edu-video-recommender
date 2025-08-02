from sentence_transformers import SentenceTransformer
import numpy as np

# Use a lighter model for Render compatibility
model = SentenceTransformer("paraphrase-MiniLM-L3-v2")  # ~61MB vs ~100MB

def embed_text(text):
    return model.encode([text])[0]

def cosine_similarity(vec1, vec2):
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)) 