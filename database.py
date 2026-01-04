import sqlite3
from datetime import datetime
import os

class TranscriptDatabase:
    def __init__(self, db_path="transcripts.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Create the database tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                title TEXT,
                duration_seconds REAL,
                transcript TEXT NOT NULL,
                model_used TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_size_mb REAL
            )
        ''')

        conn.commit()
        conn.close()

    def save_transcript(self, url, title, transcript, duration_seconds=None,
                       model_used="whisper", file_size_mb=None):
        """Save a transcript to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO transcripts (url, title, transcript, duration_seconds, model_used, file_size_mb)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (url, title, transcript, duration_seconds, model_used, file_size_mb))

        transcript_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return transcript_id

    def get_transcript_by_url(self, url):
        """Check if a URL has already been transcribed"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM transcripts WHERE url = ?', (url,))
        result = cursor.fetchone()

        conn.close()
        return result

    def get_all_transcripts(self):
        """Get all transcripts from the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT id, url, title, created_at FROM transcripts ORDER BY created_at DESC')
        results = cursor.fetchall()

        conn.close()
        return results

    def search_transcripts(self, search_term):
        """Search for transcripts containing a specific term"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, url, title, created_at
            FROM transcripts
            WHERE transcript LIKE ? OR title LIKE ?
            ORDER BY created_at DESC
        ''', (f'%{search_term}%', f'%{search_term}%'))

        results = cursor.fetchall()
        conn.close()
        return results
