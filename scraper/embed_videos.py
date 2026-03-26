"""
Batch embedding job for videos.
Generates embeddings using bge-small-en-v1.5 model (384 dimensions).

Usage:
    python scraper/embed_videos.py

Requirements:
    pip install sentence-transformers torch
"""

import json
import time
from pathlib import Path

import torch
from sentence_transformers import SentenceTransformer
from sqlalchemy import text

from backend.database import get_session
from backend.models import Video

# Configuration
CHECKPOINT_FILE = Path(__file__).parent / "embed_checkpoint.json"
MODEL_NAME = "BAAI/bge-small-en-v1.5"
BATCH_SIZE = 50  # Process 50 videos at a time
EMBEDDING_DIM = 384


def load_checkpoint():
    """Load progress from checkpoint file."""
    if CHECKPOINT_FILE.exists():
        try:
            with open(CHECKPOINT_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, KeyError):
            print("Warning: Corrupted checkpoint file, starting fresh")
    return {"last_processed_id": 0, "total_embedded": 0}

def save_checkpoint(data):
    """Save progress to checkpoint file."""
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_device():
    """Get the best available device (GPU if available)."""
    if torch.cuda.is_available():
        return "cuda"
    elif torch.backends.mps.is_available():
        return "mps"  # Apple Silicon
    return "cpu"


def run_embedding_job():
    """Main embedding job function."""
    print("=" * 60)
    print("Embedding Job - bge-small-en-v1.5")
    print("=" * 60)
    
    # Check device
    device = get_device()
    print(f"Device: {device.upper()}")
    
    # Load model
    print(f"Loading model: {MODEL_NAME}")
    start_load = time.time()
    model = SentenceTransformer(MODEL_NAME, device=device)
    print(f"Model loaded in {time.time() - start_load:.1f}s")
    
    # Load checkpoint
    checkpoint = load_checkpoint()
    last_id = checkpoint.get("last_processed_id", 0)
    total_embedded = checkpoint.get("total_embedded", 0)
    
    # Get database session
    session_gen = get_session()
    session = next(session_gen)
    
    try:
        # Count videos needing embeddings
        total_count = session.query(Video).count()
        already_done = session.query(Video).filter(
            Video.embedding.isnot(None)
        ).count()
        pending_count = session.query(Video).filter(
            Video.embedding.is_(None),
            Video.id > last_id
        ).count()
        
        print(f"Total videos: {total_count}")
        print(f"Already embedded: {already_done}")
        print(f"Pending: {pending_count}")        
        print("-" * 60)
        
        if pending_count == 0:
            print("All videos already have embeddings!")
            return
        
        # Process in batches
        processed = 0
        start_time = time.time()
        
        while True:
            # Fetch batch of videos without embeddings
            videos = session.query(Video).filter(
                Video.embedding.is_(None),
                Video.id > last_id
            ).order_by(Video.id).limit(BATCH_SIZE).all()
            
            if not videos:
                break
            
            # Prepare texts for embedding (title + description)
            texts = []
            for v in videos:
                text_content = f"{v.title}. {v.description or ''}"
                texts.append(text_content[:512])  # Truncate to 512 chars
            
            # Generate embeddings
            embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
            
            # Update database
            for video, embedding in zip(videos, embeddings, strict=False):
                # Convert numpy array to list for pgvector
                embedding_list = embedding.tolist()
                
                # Use raw SQL for efficient update
                session.execute(
                    text("UPDATE videos SET embedding = :emb WHERE id = :vid"),
                    {"emb": str(embedding_list), "vid": video.id}
                )
                last_id = video.id
            
            session.commit()
            processed += len(videos)
            total_embedded += len(videos)
            
            # Save checkpoint
            save_checkpoint({
                "last_processed_id": last_id,
                "total_embedded": total_embedded
            })
            
            # Progress update
            elapsed = time.time() - start_time
            rate = processed / elapsed if elapsed > 0 else 0
            remaining = (pending_count - processed) / rate if rate > 0 else 0
            
            print(f"Processed: {processed}/{pending_count} ({rate:.1f} videos/sec, ~{remaining:.0f}s remaining)")
        
        print("\n" + "=" * 60)
        print("Embedding job complete!")
        print(f"  Total processed this run: {processed}")
        print(f"  Total embedded overall: {total_embedded}")
        print(f"  Time taken: {time.time() - start_time:.1f}s")
        print("=" * 60)
        
    finally:
        session_gen.close()


if __name__ == "__main__":
    run_embedding_job()
