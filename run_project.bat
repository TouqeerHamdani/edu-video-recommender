@echo off
start cmd /k "python -m backend.app"
start cmd /k "cd frontend && python -m http.server 8000"