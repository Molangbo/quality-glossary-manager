import argparse

from database import DEFAULT_MASTERY_LEVEL, get_connection, initialize_database, now_text


SAMPLE_ENTRIES = [
    {
        "chinese": "生产件批准程序",
        "english": "Production Part Approval Process",
        "abbreviation": "PPAP",
        "entry_type": "汽车行业缩写",
        "categories": "PPAP",
        "explanation": "用于确认供应商是否理解客户工程设计和规范要求，并具备稳定生产能力。",
        "example": "We need to submit the PPAP package before mass production.",
        "source": "V0.1 测试数据",
        "note": "项目质量常用术语。",
        "mastery_level": DEFAULT_MASTERY_LEVEL,
    },
    {
        "chinese": "先期产品质量策划",
        "english": "Advanced Product Quality Planning",
        "abbreviation": "APQP",
        "entry_type": "汽车行业缩写",
        "categories": "APQP",
        "explanation": "一种结构化的产品质量策划方法，用于确保产品满足客户要求。",
        "example": "APQP helps the team identify quality risks early.",
        "source": "V0.1 测试数据",
        "note": "和项目开发流程相关。",
        "mastery_level": "学习中",
    },
    {
        "chinese": "零件提交保证书",
        "english": "Part Submission Warrant",
        "abbreviation": "PSW",
        "entry_type": "汽车行业缩写",
        "categories": "PSW, PPAP",
        "explanation": "PPAP 提交资料中的关键文件，用于声明零件满足客户要求。",
        "example": "The supplier signed the PSW after PPAP approval.",
        "source": "V0.1 测试数据",
        "note": "通常和 PPAP 一起出现。",
        "mastery_level": DEFAULT_MASTERY_LEVEL,
    },
    {
        "chinese": "质量阀",
        "english": "Quality Gate",
        "abbreviation": "",
        "entry_type": "中英对照术语",
        "categories": "质量阀",
        "explanation": "项目阶段之间的质量检查节点，用于判断是否允许进入下一阶段。",
        "example": "The project cannot pass the quality gate until all open issues are closed.",
        "source": "V0.1 测试数据",
        "note": "适合用于项目节点评审。",
        "mastery_level": DEFAULT_MASTERY_LEVEL,
    },
    {
        "chinese": "客户投诉",
        "english": "customer complaint",
        "abbreviation": "",
        "entry_type": "中英对照术语",
        "categories": "客户投诉, 海外会议表达",
        "explanation": "客户对产品质量、交付、服务或沟通问题提出的不满意反馈。",
        "example": "We received a customer complaint about a dimensional issue.",
        "source": "V0.1 测试数据",
        "note": "会议和 8D 场景常用。",
        "mastery_level": DEFAULT_MASTERY_LEVEL,
    },
    {
        "chinese": "我们需要在量产前提交 PPAP 包。",
        "english": "We need to submit the PPAP package before mass production.",
        "abbreviation": "",
        "entry_type": "会议句式",
        "categories": "海外会议表达, PPAP",
        "explanation": "用于会议中说明 PPAP 提交时间要求。",
        "example": "We need to submit the PPAP package before mass production.",
        "source": "V0.1 测试数据",
        "note": "适合海外客户会议。",
        "mastery_level": DEFAULT_MASTERY_LEVEL,
    },
]


def find_existing_entry(connection, entry):
    conditions = []
    values = []

    for field_name in ("abbreviation", "english", "chinese"):
        value = entry.get(field_name, "").strip()
        if value:
            conditions.append(f"{field_name} = ?")
            values.append(value)

    if not conditions:
        return None

    sql = "SELECT id FROM glossary_entries WHERE " + " OR ".join(conditions) + " LIMIT 1"
    return connection.execute(sql, values).fetchone()


def insert_entry(connection, entry):
    current_time = now_text()
    connection.execute(
        """
        INSERT INTO glossary_entries (
            chinese, english, abbreviation, entry_type, categories,
            explanation, example, source, note, mastery_level,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entry["chinese"],
            entry["english"],
            entry["abbreviation"],
            entry["entry_type"],
            entry["categories"],
            entry["explanation"],
            entry["example"],
            entry["source"],
            entry["note"],
            entry["mastery_level"],
            current_time,
            current_time,
        ),
    )


def add_sample_entries(dry_run=False):
    initialize_database()

    added = []
    skipped = []

    with get_connection() as connection:
        for entry in SAMPLE_ENTRIES:
            existing_entry = find_existing_entry(connection, entry)
            if existing_entry:
                skipped.append((entry, existing_entry["id"]))
                continue

            added.append(entry)
            if not dry_run:
                insert_entry(connection, entry)

        if not dry_run:
            connection.commit()

    return added, skipped


def print_summary(added, skipped, dry_run=False):
    action_text = "将新增" if dry_run else "已新增"
    print(f"{action_text} {len(added)} 条测试词条。")

    if added:
        print()
        print(f"{action_text}的词条：")
        for entry in added:
            name = entry["abbreviation"] or entry["english"] or entry["chinese"]
            print(f"- {name}：{entry['chinese']}")

    if skipped:
        print()
        print(f"跳过 {len(skipped)} 条已存在词条：")
        for entry, existing_id in skipped:
            name = entry["abbreviation"] or entry["english"] or entry["chinese"]
            print(f"- {name}：已存在，ID {existing_id}")

    if dry_run:
        print()
        print("当前是预览模式，数据库没有被修改。去掉 --dry-run 后才会写入。")


def main():
    parser = argparse.ArgumentParser(description="Add sample glossary entries for V0.1 testing.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be inserted without changing the database.",
    )
    args = parser.parse_args()

    added, skipped = add_sample_entries(dry_run=args.dry_run)
    print_summary(added, skipped, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
