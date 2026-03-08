import ast
import sys

try:
    with open('backend/app.py', 'r') as f:
        ast.parse(f.read())
    print("Syntax OK")
except Exception as e:
    print(f"Syntax Error: {e}")
    sys.exit(1)
