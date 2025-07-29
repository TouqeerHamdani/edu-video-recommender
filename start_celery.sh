#!/bin/bash
# Load environment variables from config.env, excluding comments
export $(grep -v '^#' config.env | xargs)
celery -A celery_app.celery worker --loglevel=info
