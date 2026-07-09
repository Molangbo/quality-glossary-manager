import csv

from database import EXPORTS_DIR, get_connection


ANKI_EXPORT_PATH = EXPORTS_DIR / "anki_cards.csv"


def build_front(entry):
    if entry["chinese"]:
        return entry["chinese"]
    if entry["abbreviation"]:
        return entry["abbreviation"]
    return entry["english"] or ""


def build_back(entry):
    parts = [
        ("英文", entry["english"]),
        ("缩写", entry["abbreviation"]),
        ("中文解释", entry["explanation"]),
        ("例句", entry["example"]),
        ("分类", entry["categories"]),
    ]
    return "\n".join(f"{label}: {value}" for label, value in parts if value)


def export_anki_cards_to_file():
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    with get_connection() as connection:
        entries = connection.execute(
            "SELECT * FROM glossary_entries WHERE is_deleted = 0 ORDER BY id ASC"
        ).fetchall()

    with ANKI_EXPORT_PATH.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=["Front", "Back"])
        writer.writeheader()
        for entry in entries:
            writer.writerow(
                {
                    "Front": build_front(entry),
                    "Back": build_back(entry),
                }
            )

    return ANKI_EXPORT_PATH, len(entries)


def export_anki_cards():
    export_path, entry_count = export_anki_cards_to_file()
    print(f"已导出 {entry_count} 张 Anki 卡片：{export_path}")
