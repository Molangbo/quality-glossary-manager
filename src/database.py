from pathlib import Path
import shutil
import sqlite3
from datetime import datetime


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
EXPORTS_DIR = PROJECT_ROOT / "exports"
BACKUPS_DIR = PROJECT_ROOT / "backups"
DB_PATH = DATA_DIR / "glossary.db"

VALID_ENTRY_TYPES = [
    "英文单词",
    "英文词组",
    "汽车行业缩写",
    "中文专业术语",
    "中英对照术语",
    "会议句式",
]

VALID_MASTERY_LEVELS = ["不熟", "学习中", "已掌握"]
DEFAULT_MASTERY_LEVEL = "学习中"
VALID_REVIEW_STATUSES = ["待复习", "已复习", "已掌握"]
DEFAULT_REVIEW_STATUS = "待复习"


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_directories():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)


def get_connection():
    ensure_directories()
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def build_backup_path(reason="manual"):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_reason = "".join(
        char if char.isalnum() or char in ("-", "_") else "_"
        for char in reason
    ).strip("_")
    suffix = f"_{safe_reason}" if safe_reason else ""
    backup_path = BACKUPS_DIR / f"glossary_backup_{timestamp}{suffix}.db"

    counter = 1
    while backup_path.exists():
        backup_path = BACKUPS_DIR / f"glossary_backup_{timestamp}{suffix}_{counter}.db"
        counter += 1

    return backup_path


def backup_database(reason="manual"):
    ensure_directories()
    if not DB_PATH.exists():
        return None

    backup_path = build_backup_path(reason)
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def initialize_database():
    ensure_directories()
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS glossary_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chinese TEXT,
                english TEXT,
                abbreviation TEXT,
                entry_type TEXT NOT NULL,
                categories TEXT,
                explanation TEXT,
                example TEXT,
                source TEXT,
                note TEXT,
                mastery_level TEXT NOT NULL,
                review_status TEXT NOT NULL DEFAULT '待复习',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(glossary_entries)")
        }
        if "is_deleted" not in columns:
            connection.execute(
                """
                ALTER TABLE glossary_entries
                ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0
                """
            )
        if "sort_order" not in columns:
            connection.execute(
                """
                ALTER TABLE glossary_entries
                ADD COLUMN sort_order INTEGER
                """
            )
        if "review_status" not in columns:
            connection.execute(
                """
                ALTER TABLE glossary_entries
                ADD COLUMN review_status TEXT NOT NULL DEFAULT '待复习'
                """
            )
        connection.commit()
