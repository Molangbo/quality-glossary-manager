import io
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

import web_app


class SendAnkiFileTests(unittest.TestCase):
    def test_download_regenerates_existing_export(self):
        with TemporaryDirectory() as temp_dir:
            export_path = Path(temp_dir) / "anki_cards.csv"
            export_path.write_bytes(b"stale")

            def regenerate_export():
                export_path.write_bytes(b"fresh")
                return export_path, 1

            handler = object.__new__(web_app.GlossaryHandler)
            handler.wfile = io.BytesIO()
            handler.send_response = lambda status: None
            handler.send_header = lambda name, value: None
            handler.end_headers = lambda: None

            with (
                patch.object(web_app, "ANKI_EXPORT_PATH", export_path),
                patch.object(
                    web_app,
                    "export_anki_cards_to_file",
                    side_effect=regenerate_export,
                ) as export_mock,
            ):
                handler.send_anki_file()

            export_mock.assert_called_once_with()
            self.assertEqual(handler.wfile.getvalue(), b"fresh")


class ImportParserTests(unittest.TestCase):
    def parse(self, text):
        with patch.object(web_app, "find_duplicate_entry", return_value=""):
            return web_app.parse_import_entries(
                text,
                category=web_app.DEFAULT_IMPORT_CATEGORY,
                source=web_app.DEFAULT_IMPORT_SOURCE,
            )

    def test_daily_report_markdown_import(self):
        entries = self.parse(
            """
# Project Quality Daily Report English Vocabulary & Expressions | Vol. 1

## 1. Follow up on
### Type
1）Entry Form：Verb Phrase
2）Recommended Category：Progress Update
3）Common Documents / Situations：Daily Report、Open Issue List
### Chinese Explanation
跟进。用于说明对责任人、问题或行动项进行持续追踪。
### Example Sentence
I followed up on the open issues with the responsible owners.
中文：我已与相关责任人跟进未关闭问题。
### Daily Report Phrase
I followed up on three open issues today, and two of them were closed.
中文：我今天跟进了三个未关闭问题，其中两个已经关闭。

## Daily Report Practice
This paragraph must not be appended to the last entry.

## Common Follow-up Questions
What support is needed?
"""
        )

        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["english"], "Follow up on")
        self.assertEqual(entry["entry_type"], web_app.ENTRY_TYPE_PHRASE)
        self.assertEqual(entry["chinese"], "跟进")
        self.assertEqual(entry["categories"], "项目质量日报英语, Progress Update")
        self.assertEqual(
            entry["source"],
            "Project Quality Daily Report English Vocabulary & Expressions | Vol. 1",
        )
        self.assertIn("常见文档 / 场景：Daily Report、Open Issue List", entry["note"])
        self.assertIn("Daily Report Phrase:", entry["note"])
        self.assertNotIn("This paragraph must not", entry["note"])

    def test_automotive_quality_markdown_import_with_acronym(self):
        entries = self.parse(
            """
# Automotive Project Quality English Vocabulary & Expressions | Vol. 8

## 1. APQP (Advanced Product Quality Planning)
### Type
1) Entry Form: Acronym
2) Recommended Category / Process Stage: APQP/PPAP
3) Common Documents / Content Where It Appears: APQP Checklist, Project Timeline
### Chinese Explanation
产品质量先期策划。用于确保产品开发到量产全过程满足客户要求。
### Example Sentence
The APQP activities are progressing according to the project timeline.
中文：APQP活动正按项目时间表推进。
### Meeting Phrases
- Are all APQP deliverables on schedule?
- Which APQP phase are we currently in?
"""
        )

        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["english"], "Advanced Product Quality Planning")
        self.assertEqual(entry["abbreviation"], "APQP")
        self.assertEqual(entry["entry_type"], web_app.ENTRY_TYPE_ABBREVIATION)
        self.assertEqual(entry["categories"], "汽车项目质量英语, APQP/PPAP")
        self.assertIn("常见文档 / 场景：APQP Checklist, Project Timeline", entry["note"])
        self.assertIn("- Are all APQP deliverables on schedule?", entry["note"])

    def test_type_numbering_is_not_treated_as_entries(self):
        entries = self.parse(
            """
## 1. Layout
### Type
1）Entry Form：Single Word
2）Recommended Category / Process Stage：Line Layout
3）Common Documents / Content Where It Appears：Layout Drawing
### Chinese Explanation
布局。指生产线、工位或设备的空间布置。
### Example Sentence
The line layout needs to be updated.
"""
        )

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["entry_type"], web_app.ENTRY_TYPE_WORD)
        self.assertEqual(entries[0]["categories"], "汽车质量英语, Line Layout")

    def test_plain_daily_report_copy_without_markdown_headings(self):
        entries = self.parse(
            """
1. Complete
Type
- Entry Form: Single Word
- Recommended Category: Completed Tasks
- Common Documents / Situations: Daily Report / Task List / Project Timeline
Chinese Explanation
Complete 表示“完成某项工作”。
在日报中通常使用 complete + 名词。
Example Sentence
I completed the document update today.
我今天完成了文件更新。
Daily Report Phrase
Today, I completed the document update and submitted it for review.
今天我完成了文件更新，并提交评审。

Daily Report Practice
This practice text must not be imported into the entry.
"""
        )

        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["chinese"], "完成某项工作")
        self.assertEqual(entry["entry_type"], web_app.ENTRY_TYPE_WORD)
        self.assertEqual(entry["categories"], "项目质量日报英语, Completed Tasks")
        self.assertEqual(entry["source"], "ChatGPT 项目质量日报词条")
        self.assertNotIn("practice text", entry["note"])

    def test_plain_automotive_copy_ignores_horizontal_rule(self):
        entries = self.parse(
            """
1. DVP&R (Design Verification Plan & Report)
Type
- Entry Form: Acronym
- Recommended Category / Process Stage: Product Development / APQP
- Common Documents / Content Where It Appears: DVP&R, Design Review Report
Chinese Explanation
设计验证计划与报告。
用于记录产品验证项目、测试要求及结果。
Example Sentence
The DVP&R is currently under customer review.
Meeting Phrases
- Has the DVP&R been approved?
- Please update the DVP&R status.

---
2. Engineering Change
Type
- Entry Form: Professional Term
- Recommended Category / Process Stage: Change Management / APQP
- Common Documents / Content Where It Appears: ECN, Change Request
Chinese Explanation
工程变更。
涉及设计、材料、工艺、设备等方面的正式变更。
Example Sentence
The engineering change impacts several dimensions.
Meeting Phrases
- Has the engineering change been approved?
"""
        )

        self.assertEqual(len(entries), 2)
        first = entries[0]
        self.assertEqual(first["english"], "Design Verification Plan & Report")
        self.assertEqual(first["abbreviation"], "DVP&R")
        self.assertEqual(first["categories"], "汽车项目质量英语, Product Development / APQP")
        self.assertEqual(first["source"], "ChatGPT 汽车项目质量词条")
        self.assertNotIn("--", first["note"])


if __name__ == "__main__":
    unittest.main()
