import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

def get_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
'''if __name__ == "__main__":
    try:
        conn = get_connection()
        print(" Connected to PostgreSQL successfully!")
        conn.close()
    except Exception as e:
        print(" Failed to connect to PostgreSQL:")
        print(e)'''
