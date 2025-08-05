from sentence_transformers import SentenceTransformer
import numpy as np

# Use a lighter model for Render compatibility
model = SentenceTransformer("nreimers/tiny-sbert-nli")  # swapped for minimal memory

def embed_text(text):
    return model.encode([text])[0]

def cosine_similarity(vec1, vec2):
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)) 