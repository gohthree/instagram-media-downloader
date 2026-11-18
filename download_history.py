"""Durable post history independent of files users choose to keep or delete."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def open_history(base: Path, username: str):
    # A user may delete all of BASE/username without erasing the history.
    location = base / '_download_history'
    location.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(location / (username.lower() + '.sqlite3'))
    db.execute('''CREATE TABLE IF NOT EXISTS posts (
        shortcode TEXT PRIMARY KEY,
        source TEXT NOT NULL,
        recorded_at TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS story_items (
        item_key TEXT PRIMARY KEY,
        recorded_at TEXT NOT NULL
    )''')
    db.commit()
    return db


def has_post(db, shortcode: str) -> bool:
    return db.execute('SELECT 1 FROM posts WHERE shortcode=?', (shortcode,)).fetchone() is not None


def record_post(db, shortcode: str, source: str):
    db.execute('INSERT OR IGNORE INTO posts(shortcode,source,recorded_at) VALUES(?,?,?)',
               (shortcode, source, datetime.now(timezone.utc).isoformat()))
    db.commit()


def import_old_codes(db, media_folder: Path) -> int:
    """Import explicitly recorded shortcodes from earlier V3/V4 versions."""
    path = media_folder / '.downloaded_posts.json'
    if not path.is_file():
        return 0
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        values = data.get('shortcodes', [])
        if not isinstance(values, list):
            return 0
        before = db.total_changes
        for code in values:
            if isinstance(code, str) and 0 < len(code) <= 30 and code.replace('-', '').replace('_', '').isalnum():
                record_post(db, code, 'old_record')
        return db.total_changes - before
    except (OSError, ValueError, TypeError):
        return 0


def infer_existing_post(db, folder: Path, shortcode: str, date_prefix: str) -> bool:
    """Migrate old media without metadata: date-match is heuristic, not proof of completion.

    Only called while visiting a post; dates are not sufficient to infer Instagram
    shortcodes without examining the source post. Inferred posts become durable.
    """
    if any(p.is_file() and p.suffix.lower() in {'.jpg', '.jpeg', '.png', '.mp4', '.webp', '.mov'}
           for p in folder.glob(date_prefix + '*')):
        record_post(db, shortcode, 'legacy_date_inferred')
        return True
    return False


def count_posts(db):
    return db.execute('SELECT COUNT(*) FROM posts').fetchone()[0]


def has_story_item(db, key: str) -> bool:
    return db.execute('SELECT 1 FROM story_items WHERE item_key=?', (key,)).fetchone() is not None

def record_story_item(db, key: str):
    db.execute('INSERT OR IGNORE INTO story_items(item_key, recorded_at) VALUES(?,?)',
               (key, datetime.now(timezone.utc).isoformat()))
    db.commit()
