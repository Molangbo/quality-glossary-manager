from database import DB_PATH, initialize_database
from export_anki import export_anki_cards
from glossary import (
    add_entry,
    edit_entry,
    filter_by_category,
    filter_by_entry_type,
    restore_deleted_entry,
    search_entries,
    soft_delete_entry,
    view_all_entries,
    view_deleted_entries,
)
from review import review_entries


def print_menu():
    print()
    print("=" * 60)
    print("Quality Glossary Manager")
    print("项目质量英语词库管理器")
    print("=" * 60)
    print("1. 新增词条")
    print("2. 查看全部词条")
    print("3. 搜索词条")
    print("4. 按分类筛选词条")
    print("5. 按词条类型筛选词条")
    print("6. 修改词条")
    print("7. 删除词条")
    print("8. 查看回收站词条")
    print("9. 恢复回收站词条")
    print("10. 简单复习模式")
    print("11. 导出 Anki CSV")
    print("0. 退出")


def main():
    initialize_database()
    print(f"数据库已准备好：{DB_PATH}")

    actions = {
        "1": add_entry,
        "2": view_all_entries,
        "3": search_entries,
        "4": filter_by_category,
        "5": filter_by_entry_type,
        "6": edit_entry,
        "7": soft_delete_entry,
        "8": view_deleted_entries,
        "9": restore_deleted_entry,
        "10": review_entries,
        "11": export_anki_cards,
    }

    while True:
        print_menu()
        choice = input("请选择功能：").strip()

        if choice == "0":
            print("已退出。")
            break

        action = actions.get(choice)
        if action is None:
            print("输入无效，请重新选择。")
            continue

        action()


if __name__ == "__main__":
    main()
