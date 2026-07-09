from database import (
    DEFAULT_MASTERY_LEVEL,
    VALID_ENTRY_TYPES,
    VALID_MASTERY_LEVELS,
    backup_database,
    get_connection,
    now_text,
)


FIELDS_FOR_DISPLAY = [
    ("id", "ID"),
    ("chinese", "中文名称"),
    ("english", "英文名称"),
    ("abbreviation", "缩写"),
    ("entry_type", "词条类型"),
    ("categories", "分类"),
    ("explanation", "中文解释"),
    ("example", "例句"),
    ("source", "来源"),
    ("note", "备注"),
    ("mastery_level", "掌握程度"),
    ("created_at", "创建时间"),
    ("updated_at", "更新时间"),
]

EDITABLE_TEXT_FIELDS = [
    ("chinese", "中文名称"),
    ("english", "英文名称"),
    ("abbreviation", "缩写"),
    ("categories", "分类"),
    ("explanation", "中文解释"),
    ("example", "例句"),
    ("source", "来源"),
    ("note", "备注"),
]


def normalize_categories(raw_categories):
    if not raw_categories:
        return ""

    separators = ["，", "、", ";", "；"]
    normalized = raw_categories
    for separator in separators:
        normalized = normalized.replace(separator, ",")

    categories = [item.strip() for item in normalized.split(",") if item.strip()]
    return ", ".join(categories)


def choose_from_list(title, options, default_value=None):
    print()
    print(title)
    for index, option in enumerate(options, start=1):
        print(f"{index}. {option}")

    while True:
        choice = input("请输入序号：").strip()
        if not choice and default_value is not None:
            return default_value
        if choice.isdigit():
            number = int(choice)
            if 1 <= number <= len(options):
                return options[number - 1]
        print("输入无效，请重新输入。")


def prompt_text(label, required=False):
    while True:
        value = input(f"{label}：").strip()
        if value or not required:
            return value
        print(f"{label}不能为空，请重新输入。")


def prompt_entry_data():
    print()
    print("请按提示输入词条信息。没有内容的字段可以直接按 Enter 跳过。")

    chinese = prompt_text("中文名称")
    english = prompt_text("英文名称")
    abbreviation = prompt_text("缩写")

    if not chinese and not english and not abbreviation:
        print("中文名称、英文名称、缩写至少需要填写一个。")
        return None

    entry_type = choose_from_list("请选择词条类型：", VALID_ENTRY_TYPES)
    categories = normalize_categories(prompt_text("分类，多个分类用英文逗号或中文逗号分隔"))
    explanation = prompt_text("中文解释")
    example = prompt_text("例句")
    source = prompt_text("来源")
    note = prompt_text("备注")

    mastery_level = choose_from_list(
        "请选择初始掌握程度，直接按 Enter 默认为“不熟”：",
        VALID_MASTERY_LEVELS,
        default_value=DEFAULT_MASTERY_LEVEL,
    )

    return {
        "chinese": chinese,
        "english": english,
        "abbreviation": abbreviation,
        "entry_type": entry_type,
        "categories": categories,
        "explanation": explanation,
        "example": example,
        "source": source,
        "note": note,
        "mastery_level": mastery_level,
    }


def add_entry():
    data = prompt_entry_data()
    if data is None:
        return

    current_time = now_text()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO glossary_entries (
                chinese, english, abbreviation, entry_type, categories,
                explanation, example, source, note, mastery_level,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["chinese"],
                data["english"],
                data["abbreviation"],
                data["entry_type"],
                data["categories"],
                data["explanation"],
                data["example"],
                data["source"],
                data["note"],
                data["mastery_level"],
                current_time,
                current_time,
            ),
        )
        connection.commit()

    print(f"新增成功，词条 ID：{cursor.lastrowid}")


def fetch_all_entries(include_deleted=False):
    where_clause = "" if include_deleted else "WHERE is_deleted = 0"
    with get_connection() as connection:
        return connection.execute(
            f"SELECT * FROM glossary_entries {where_clause} ORDER BY id ASC"
        ).fetchall()


def fetch_deleted_entries():
    with get_connection() as connection:
        return connection.execute(
            "SELECT * FROM glossary_entries WHERE is_deleted = 1 ORDER BY id ASC"
        ).fetchall()


def fetch_entry_by_id(entry_id, include_deleted=False, only_deleted=False):
    conditions = ["id = ?"]
    values = [entry_id]
    if only_deleted:
        conditions.append("is_deleted = 1")
    elif not include_deleted:
        conditions.append("is_deleted = 0")

    where_clause = " AND ".join(conditions)
    with get_connection() as connection:
        return connection.execute(
            f"SELECT * FROM glossary_entries WHERE {where_clause}",
            values,
        ).fetchone()


def print_entry(entry):
    print("-" * 60)
    for field_name, label in FIELDS_FOR_DISPLAY:
        value = entry[field_name] if entry[field_name] is not None else ""
        print(f"{label}: {value}")


def print_entry_list(entries):
    if not entries:
        print("没有找到词条。")
        return

    for entry in entries:
        print_entry(entry)
    print("-" * 60)
    print(f"共 {len(entries)} 条词条。")


def view_all_entries():
    entries = fetch_all_entries()
    print_entry_list(entries)


def search_entries():
    keyword = input("请输入搜索关键词（中文、英文或缩写）：").strip()
    if not keyword:
        print("关键词不能为空。")
        return

    like_keyword = f"%{keyword}%"
    with get_connection() as connection:
        entries = connection.execute(
            """
            SELECT *
            FROM glossary_entries
            WHERE is_deleted = 0
              AND (
                  chinese LIKE ?
                  OR english LIKE ?
                  OR abbreviation LIKE ?
                  OR explanation LIKE ?
                  OR categories LIKE ?
              )
            ORDER BY id ASC
            """,
            (like_keyword, like_keyword, like_keyword, like_keyword, like_keyword),
        ).fetchall()

    print_entry_list(entries)


def filter_by_category():
    category = input("请输入分类关键词，例如 APQP 或 海外会议表达：").strip()
    if not category:
        print("分类关键词不能为空。")
        return

    like_category = f"%{category}%"
    with get_connection() as connection:
        entries = connection.execute(
            """
            SELECT *
            FROM glossary_entries
            WHERE is_deleted = 0
              AND categories LIKE ?
            ORDER BY id ASC
            """,
            (like_category,),
        ).fetchall()

    print_entry_list(entries)


def filter_by_entry_type():
    entry_type = choose_from_list("请选择要筛选的词条类型：", VALID_ENTRY_TYPES)

    with get_connection() as connection:
        entries = connection.execute(
            """
            SELECT *
            FROM glossary_entries
            WHERE is_deleted = 0
              AND entry_type = ?
            ORDER BY id ASC
            """,
            (entry_type,),
        ).fetchall()

    print_entry_list(entries)


def prompt_entry_id_for_edit():
    while True:
        raw_value = input("请输入要修改的词条 ID，输入 q 返回主菜单：").strip()
        if raw_value.lower() == "q":
            return None
        if raw_value.isdigit() and int(raw_value) > 0:
            return int(raw_value)
        print("请输入有效的数字 ID。")


def row_to_dict(entry):
    return {key: entry[key] if entry[key] is not None else "" for key in entry.keys()}


def field_label(field_name):
    for name, label in FIELDS_FOR_DISPLAY:
        if name == field_name:
            return label
    return field_name


def prompt_update_text_field(label, current_value, normalize_func=None):
    current_display = current_value if current_value else "（空）"
    print()
    print(f"{label}当前值：{current_display}")
    new_value = input(
        f"请输入新的{label}，直接按 Enter 保留原值，输入“清空”清空该字段："
    ).strip()

    if not new_value:
        return current_value
    if new_value == "清空":
        return ""
    if normalize_func is not None:
        return normalize_func(new_value)
    return new_value


def prompt_updated_entry_data(entry):
    data = row_to_dict(entry)

    print()
    print("开始修改。直接按 Enter 会保留原值。")

    for field_name, label in EDITABLE_TEXT_FIELDS:
        normalize_func = normalize_categories if field_name == "categories" else None
        data[field_name] = prompt_update_text_field(
            label,
            data[field_name],
            normalize_func=normalize_func,
        )

    data["entry_type"] = choose_from_list(
        f"请选择词条类型，直接按 Enter 保留当前值：{data['entry_type']}",
        VALID_ENTRY_TYPES,
        default_value=data["entry_type"],
    )
    data["mastery_level"] = choose_from_list(
        f"请选择掌握程度，直接按 Enter 保留当前值：{data['mastery_level']}",
        VALID_MASTERY_LEVELS,
        default_value=data["mastery_level"],
    )

    if not data["chinese"] and not data["english"] and not data["abbreviation"]:
        print("中文名称、英文名称、缩写不能同时为空。本次修改已取消。")
        return None

    return data


def changed_fields(old_entry, new_data):
    fields = [
        "chinese",
        "english",
        "abbreviation",
        "entry_type",
        "categories",
        "explanation",
        "example",
        "source",
        "note",
        "mastery_level",
    ]
    changes = []
    for field_name in fields:
        old_value = old_entry[field_name] if old_entry[field_name] is not None else ""
        new_value = new_data[field_name]
        if old_value != new_value:
            changes.append(field_name)
    return changes


def print_changes(entry, new_data, changes):
    print()
    print("将修改以下字段：")
    for field_name in changes:
        old_value = entry[field_name] if entry[field_name] is not None else ""
        new_value = new_data[field_name]
        print(f"- {field_label(field_name)}: {old_value or '（空）'} -> {new_value or '（空）'}")


def update_entry(entry_id, data):
    backup_path = backup_database("before_edit")
    if backup_path is not None:
        print(f"已自动备份数据库：{backup_path}")

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE glossary_entries
            SET chinese = ?,
                english = ?,
                abbreviation = ?,
                entry_type = ?,
                categories = ?,
                explanation = ?,
                example = ?,
                source = ?,
                note = ?,
                mastery_level = ?,
                updated_at = ?
            WHERE id = ?
              AND is_deleted = 0
            """,
            (
                data["chinese"],
                data["english"],
                data["abbreviation"],
                data["entry_type"],
                data["categories"],
                data["explanation"],
                data["example"],
                data["source"],
                data["note"],
                data["mastery_level"],
                now_text(),
                entry_id,
            ),
        )
        connection.commit()


def edit_entry():
    entry_id = prompt_entry_id_for_edit()
    if entry_id is None:
        print("已取消修改。")
        return

    entry = fetch_entry_by_id(entry_id)
    if entry is None:
        print(f"没有找到 ID 为 {entry_id} 的词条。")
        return

    print()
    print("当前词条内容：")
    print_entry(entry)

    new_data = prompt_updated_entry_data(entry)
    if new_data is None:
        return

    changes = changed_fields(entry, new_data)
    if not changes:
        print("没有检测到修改，数据库未变化。")
        return

    print_changes(entry, new_data, changes)
    confirm = input("确认保存以上修改吗？输入 y 保存，其他输入取消：").strip().lower()
    if confirm != "y":
        print("已取消保存，数据库未变化。")
        return

    update_entry(entry_id, new_data)
    print(f"词条 ID {entry_id} 修改成功。")


def prompt_entry_id_for_status_change(action_name):
    while True:
        raw_value = input(f"请输入要{action_name}的词条 ID，输入 q 返回主菜单：").strip()
        if raw_value.lower() == "q":
            return None
        if raw_value.isdigit() and int(raw_value) > 0:
            return int(raw_value)
        print("请输入有效的数字 ID。")


def set_entry_deleted_status(entry_id, is_deleted, backup_reason):
    backup_path = backup_database(backup_reason)

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE glossary_entries
            SET is_deleted = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (1 if is_deleted else 0, now_text(), entry_id),
        )
        connection.commit()

    return backup_path


def soft_delete_entry():
    entry_id = prompt_entry_id_for_status_change("删除")
    if entry_id is None:
        print("已取消删除。")
        return

    entry = fetch_entry_by_id(entry_id)
    if entry is None:
        print(f"没有在词库中找到 ID 为 {entry_id} 的词条。")
        return

    print()
    print("将要删除以下词条到回收站：")
    print_entry(entry)
    confirm = input("确认删除这个词条吗？输入 y 删除，其他输入取消：").strip().lower()
    if confirm != "y":
        print("已取消删除，数据库未变化。")
        return

    backup_path = set_entry_deleted_status(entry_id, True, "before_soft_delete")
    if backup_path is not None:
        print(f"已自动备份数据库：{backup_path}")
    print(f"词条 ID {entry_id} 已删除到回收站。")


def view_deleted_entries():
    entries = fetch_deleted_entries()
    if not entries:
        print("当前回收站没有词条。")
        return

    print_entry_list(entries)


def restore_deleted_entry():
    entry_id = prompt_entry_id_for_status_change("恢复")
    if entry_id is None:
        print("已取消恢复。")
        return

    entry = fetch_entry_by_id(entry_id, only_deleted=True)
    if entry is None:
        print(f"没有在回收站中找到 ID 为 {entry_id} 的词条。")
        return

    print()
    print("将要恢复以下词条：")
    print_entry(entry)
    confirm = input("确认恢复这个词条吗？输入 y 恢复，其他输入取消：").strip().lower()
    if confirm != "y":
        print("已取消恢复，数据库未变化。")
        return

    backup_path = set_entry_deleted_status(entry_id, False, "before_restore")
    if backup_path is not None:
        print(f"已自动备份数据库：{backup_path}")
    print(f"词条 ID {entry_id} 已恢复到词库。")
