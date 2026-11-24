import sqlite3
from pathlib import Path #Python's standard library for working with file and directory paths


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "data" / "cosmic_discovery.db" #.db extension for database files.

def get_connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    return connection

def initialize_database():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS astronomical_objects (
                object_id INTEGER PRIMARY KEY,
                canonical_name TEXT NOT NULL UNIQUE,
                object_type TEXT NOT NULL,
                ra_deg REAL,
                dec_deg REAL)""")


def add_object(canonical_name, object_type, ra_deg=None, dec_deg=None):
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO astronomical_objects (
                canonical_name,
                object_type,
                ra_deg,
                dec_deg)
            VALUES (?, ?, ?, ?)
            """,
            (canonical_name, object_type, ra_deg, dec_deg) )

        return cursor.lastrowid


if __name__ == "__main__":
    initialize_database()
    print("Cosmic Discovery database initialized.")
    print(f"Database location: {DATABASE_PATH}")