import random

from database import VALID_MASTERY_LEVELS, get_connection, now_text
from glossary import print_entry


def fetch_entries_for_review():
    with get_connection() as connection:
        return connection.execute(
            "SELECT * FROM glossary_entries WHERE is_deleted = 0 ORDER BY id ASC"
        ).fetchall()


def build_question(entry):
    if entry["chinese"]:
        return f"请说出这个中文术语的英文 / 缩写：{entry['chinese']}"
    if entry["abbreviation"]:
        return f"请说出这个缩写的全称或中文含义：{entry['abbreviation']}"
    return f"请说出这个英文词条的中文含义：{entry['english']}"


def choose_mastery_level():
    print()
    print("请选择掌握程度：")
    for index, level in enumerate(VALID_MASTERY_LEVELS, start=1):
        print(f"{index}. {level}")
    print("0. 不更新，继续下一题")

    while True:
        choice = input("请输入序号：").strip()
        if choice == "0":
            return None
        if choice.isdigit():
            number = int(choice)
            if 1 <= number <= len(VALID_MASTERY_LEVELS):
                return VALID_MASTERY_LEVELS[number - 1]
        print("输入无效，请重新输入。")


def update_mastery_level(entry_id, mastery_level):
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE glossary_entries
            SET mastery_level = ?, updated_at = ?
            WHERE id = ?
            """,
            (mastery_level, now_text(), entry_id),
        )
        connection.commit()


def review_entries():
    entries = fetch_entries_for_review()
    if not entries:
        print("当前没有词条。请先新增词条，再进入复习模式。")
        return

    shuffled_entries = list(entries)
    random.shuffle(shuffled_entries)

    print()
    print("进入复习模式。每题先显示问题，按 Enter 查看答案。")
    print("查看答案后可以更新掌握程度。输入 q 可以退出复习。")

    for index, entry in enumerate(shuffled_entries, start=1):
        print()
        print("=" * 60)
        print(f"第 {index} / {len(shuffled_entries)} 题")
        print(build_question(entry))

        command = input("按 Enter 显示答案，输入 q 退出：").strip().lower()
        if command == "q":
            print("已退出复习模式。")
            return

        print()
        print("答案：")
        print_entry(entry)

        mastery_level = choose_mastery_level()
        if mastery_level is not None:
            update_mastery_level(entry["id"], mastery_level)
            print(f"已更新为：{mastery_level}")

    print("本轮复习完成。")
