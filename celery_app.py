from celery import Celery
import os
from dotenv import load_dotenv

load_dotenv()

celery = Celery(
    'edu_tasks',
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_BACKEND", "redis://localhost:6379/0")
)

celery.conf.timezone = 'Asia/Kolkata' 
