import argparse
import json
import random
import re
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, parse_qs, urlparse

from database import (
    DB_PATH,
    DEFAULT_REVIEW_STATUS,
    VALID_ENTRY_TYPES,
    VALID_MASTERY_LEVELS,
    VALID_REVIEW_STATUSES,
    backup_database,
    get_connection,
    initialize_database,
    now_text,
)
from export_anki import ANKI_EXPORT_PATH, export_anki_cards_to_file
from glossary import normalize_categories
from tts_audio import AUDIO_DIR, TtsError, generate_tts_audio


HOST = "127.0.0.1"
DEFAULT_PORT = 8000

TEXT_FIELDS = [
    "chinese",
    "english",
    "abbreviation",
    "categories",
    "explanation",
    "example",
    "source",
    "note",
]

WEB_DEFAULT_MASTERY_LEVEL = "学习中"
DEFAULT_IMPORT_CATEGORY = "汽车质量英语"
DEFAULT_IMPORT_SOURCE = "ChatGPT 每日词条"
ENTRY_TYPE_WORD = "英文单词"
ENTRY_TYPE_PHRASE = "英文词组"
ENTRY_TYPE_ABBREVIATION = "汽车行业缩写"
REVIEW_STATUS_PENDING = "待复习"
REVIEW_STATUS_REVIEWED = "已复习"
REVIEW_STATUS_MASTERED = "已掌握"
REVIEW_STATUS_WEIGHTS = {
    REVIEW_STATUS_PENDING: 5,
    REVIEW_STATUS_REVIEWED: 1,
}

SORT_ORDER_CLAUSES = {
    "id": "id ASC",
    "english_asc": "LOWER(COALESCE(NULLIF(english, ''), NULLIF(abbreviation, ''), chinese, '')) ASC, id ASC",
    "english_desc": "LOWER(COALESCE(NULLIF(english, ''), NULLIF(abbreviation, ''), chinese, '')) DESC, id ASC",
    "updated_desc": "updated_at DESC, id DESC",
    "category": "LOWER(COALESCE(categories, '')) ASC, id ASC",
    "mastery": "CASE mastery_level WHEN '不熟' THEN 1 WHEN '学习中' THEN 2 WHEN '已掌握' THEN 3 ELSE 99 END ASC, id ASC",
    "custom": "CASE WHEN sort_order IS NULL THEN 1 ELSE 0 END ASC, sort_order ASC, id ASC",
}


def safe_print(*args, **kwargs):
    if getattr(sys, "stdout", None) is None:
        return
    print(*args, **kwargs)


HTML_PAGE = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>项目质量英语词库管理器</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f7f8;
      --panel: #ffffff;
      --line: #d9e0e4;
      --line-strong: #b9c5cb;
      --text: #1f2933;
      --muted: #65727d;
      --primary: #23636a;
      --primary-dark: #164a50;
      --danger: #b13b2e;
      --warning: #9a5b12;
      --soft: #eef4f5;
      --focus: #f2c94c;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-width: 320px;
      background: var(--bg);
      color: var(--text);
      font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
      font-size: 15px;
      line-height: 1.45;
    }

    header {
      border-bottom: 1px solid var(--line);
      background: #ffffff;
    }

    .topbar {
      max-width: 1440px;
      margin: 0 auto;
      padding: 18px 24px 14px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }

    h1 {
      margin: 0;
      font-size: 24px;
      font-weight: 700;
      letter-spacing: 0;
    }

    .db-path {
      margin-top: 3px;
      color: var(--muted);
      font-size: 13px;
      word-break: break-all;
    }

    .header-actions,
    .toolbar,
    .form-actions,
    .status-tabs {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }

    button,
    select,
    input,
    textarea {
      font: inherit;
    }

    button {
      min-height: 36px;
      border: 1px solid var(--line-strong);
      border-radius: 6px;
      background: #ffffff;
      color: var(--text);
      padding: 7px 12px;
      cursor: pointer;
    }

    button:hover {
      border-color: var(--primary);
      color: var(--primary-dark);
    }

    button.primary {
      border-color: var(--primary);
      background: var(--primary);
      color: #ffffff;
    }

    button.primary:hover {
      background: var(--primary-dark);
      color: #ffffff;
    }

    button.danger {
      border-color: var(--danger);
      color: var(--danger);
    }

    button.warning {
      border-color: var(--warning);
      color: var(--warning);
    }

    button.audio-button {
      width: 30px;
      min-width: 30px;
      min-height: 28px;
      padding: 0;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-color: var(--line-strong);
      color: var(--primary-dark);
      line-height: 1;
    }

    button.tab {
      background: #ffffff;
      color: var(--muted);
    }

    button.tab.active {
      border-color: var(--primary);
      background: var(--soft);
      color: var(--primary-dark);
      font-weight: 700;
    }

    input,
    select,
    textarea {
      width: 100%;
      min-height: 36px;
      border: 1px solid var(--line-strong);
      border-radius: 6px;
      background: #ffffff;
      color: var(--text);
      padding: 7px 10px;
    }

    textarea {
      resize: vertical;
      min-height: 76px;
    }

    input:focus,
    select:focus,
    textarea:focus,
    button:focus {
      outline: 3px solid color-mix(in srgb, var(--focus) 45%, transparent);
      outline-offset: 1px;
    }

    main {
      max-width: 1440px;
      margin: 0 auto;
      padding: 18px 24px 28px;
    }

    .toolbar {
      margin-bottom: 14px;
      align-items: end;
    }

    .filter {
      display: grid;
      gap: 5px;
      min-width: 180px;
      flex: 1 1 190px;
    }

    .filter.search {
      flex-basis: 280px;
    }

    label {
      font-size: 13px;
      color: var(--muted);
    }

    .layout {
      display: grid;
      grid-template-columns: minmax(720px, 1fr) minmax(340px, 390px);
      gap: 14px;
      align-items: stretch;
      height: calc(100vh - 170px);
      min-height: 520px;
    }

    .list-panel,
    .editor-panel {
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      overflow: hidden;
      min-height: 0;
    }

    .list-panel {
      display: flex;
      flex-direction: column;
    }

    .panel-head {
      min-height: 48px;
      padding: 11px 14px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      border-bottom: 1px solid var(--line);
      background: #fbfcfc;
    }

    .panel-title {
      margin: 0;
      font-size: 16px;
      font-weight: 700;
    }

    .count {
      color: var(--muted);
      font-size: 13px;
      white-space: nowrap;
    }

    .table-wrap {
      flex: 1 1 auto;
      overflow: auto;
      min-height: 0;
    }

    table {
      width: 100%;
      min-width: 1120px;
      border-collapse: collapse;
      table-layout: fixed;
    }

    col.col-id {
      width: 54px;
    }

    col.col-sort {
      width: 64px;
    }

    col.col-name {
      width: 15%;
    }

    col.col-english {
      width: 20%;
    }

    col.col-abbreviation {
      width: 7%;
    }

    col.col-type {
      width: 11%;
    }

    col.col-category {
      width: 12%;
    }

    col.col-mastery {
      width: 8%;
    }

    col.col-review {
      width: 8%;
    }

    th,
    td {
      border-bottom: 1px solid var(--line);
      padding: 10px 12px;
      text-align: left;
      vertical-align: top;
      overflow-wrap: break-word;
      word-break: normal;
    }

    th {
      position: sticky;
      top: 0;
      z-index: 1;
      background: #f8fafb;
      color: #4b5963;
      font-size: 13px;
      font-weight: 700;
    }

    tr {
      cursor: pointer;
    }

    tbody tr:hover,
    tbody tr.selected {
      background: var(--soft);
    }

    td.row-number {
      color: var(--muted);
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
    }

    td.sort-order {
      color: var(--muted);
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
    }

    td.name {
      font-weight: 700;
    }

    td.english {
      line-height: 1.5;
      overflow-wrap: normal;
    }

    .english-content {
      display: flex;
      gap: 8px;
      align-items: flex-start;
    }

    .english-text {
      min-width: 0;
      overflow-wrap: break-word;
    }

    td.abbreviation,
    td.mastery,
    td.review-status {
      white-space: nowrap;
    }

    td.type,
    td.mastery,
    td.review-status {
      color: #40505a;
    }

    td.category {
      line-height: 1.45;
    }

    td.note {
      color: #40505a;
      line-height: 1.55;
    }

    .empty {
      padding: 34px 16px;
      text-align: center;
      color: var(--muted);
    }

    .pagination-bar {
      min-height: 48px;
      padding: 8px 12px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      border-top: 1px solid var(--line);
      background: #fbfcfc;
      color: var(--muted);
      font-size: 13px;
    }

    .page-size,
    .page-controls {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }

    .page-size select {
      width: auto;
      min-width: 74px;
      min-height: 32px;
      padding: 4px 8px;
    }

    .page-controls button {
      min-height: 32px;
      padding: 5px 10px;
    }

    .page-controls button:disabled {
      cursor: not-allowed;
      opacity: 0.55;
    }

    .import-panel {
      margin-bottom: 14px;
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      overflow: hidden;
    }

    .import-body {
      padding: 14px;
      display: grid;
      gap: 12px;
    }

    .import-textarea {
      min-height: 180px;
      font-family: "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
    }

    .import-actions {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }

    .import-preview {
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 6px;
      max-height: 320px;
    }

    .import-preview table {
      min-width: 900px;
    }

    .import-preview td,
    .import-preview th {
      padding: 8px 10px;
      font-size: 13px;
    }

    .preview-status {
      white-space: nowrap;
      color: var(--primary-dark);
      font-weight: 700;
    }

    .preview-status.warning {
      color: var(--warning);
    }

    .review-panel {
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      overflow: hidden;
    }

    .review-body {
      padding: 16px;
      display: grid;
      gap: 14px;
    }

    .review-controls {
      display: grid;
      grid-template-columns: repeat(5, minmax(130px, 1fr));
      gap: 12px;
      align-items: end;
    }

    .review-actions,
    .review-status-actions {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
    }

    .review-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfc;
      padding: 18px;
      display: grid;
      gap: 14px;
    }

    .review-mode-label {
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
    }

    .review-prompt {
      white-space: pre-wrap;
      font-size: 24px;
      font-weight: 700;
      line-height: 1.35;
    }

    .review-detail {
      color: #40505a;
      white-space: pre-wrap;
      line-height: 1.6;
    }

    .review-options {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }

    .review-option {
      min-height: 56px;
      text-align: left;
      white-space: normal;
      line-height: 1.4;
    }

    .review-option.correct {
      border-color: var(--primary);
      background: var(--soft);
      color: var(--primary-dark);
      font-weight: 700;
    }

    .review-option.incorrect {
      border-color: var(--danger);
      color: var(--danger);
      font-weight: 700;
    }

    .spelling-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 8px;
    }

    .answer-panel {
      border-top: 1px solid var(--line);
      padding-top: 12px;
      display: grid;
      gap: 10px;
    }

    .answer-result {
      font-weight: 700;
      color: var(--primary-dark);
    }

    .answer-result.error {
      color: var(--danger);
    }

    .answer-grid {
      display: grid;
      grid-template-columns: 130px minmax(0, 1fr);
      gap: 8px 12px;
      color: #40505a;
    }

    .answer-grid strong {
      color: var(--text);
    }

    .editor-panel {
      position: sticky;
      top: 12px;
      max-height: calc(100vh - 24px);
      display: flex;
      flex-direction: column;
    }

    form {
      padding: 14px;
      display: grid;
      gap: 12px;
      flex: 1 1 auto;
      min-height: 0;
      overflow: auto;
    }

    .form-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }

    .field {
      display: grid;
      gap: 5px;
    }

    .inline-input {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 36px;
      gap: 6px;
      align-items: start;
    }

    .field.full {
      grid-column: 1 / -1;
    }

    .form-actions {
      position: sticky;
      bottom: -14px;
      z-index: 2;
      margin: 0 -14px -14px;
      padding: 12px 14px;
      border-top: 1px solid var(--line);
      background: #ffffff;
    }

    .status-line {
      min-height: 24px;
      color: var(--muted);
      font-size: 13px;
      overflow-wrap: anywhere;
    }

    .status-line.error {
      max-height: 120px;
      overflow: auto;
      color: var(--danger);
      font-weight: 700;
    }

    .status-line.ok {
      color: var(--primary-dark);
      font-weight: 700;
    }

    .hidden {
      display: none !important;
    }

    @media (max-width: 1080px) {
      .layout {
        grid-template-columns: 1fr;
        height: auto;
        min-height: 0;
      }

      .editor-panel {
        position: static;
        max-height: none;
      }

      .table-wrap {
        min-height: 360px;
      }

      .review-controls,
      .review-options {
        grid-template-columns: 1fr;
      }

      form {
        overflow: visible;
      }

      .form-actions {
        position: static;
        margin: 0;
        padding: 0;
        border-top: 0;
      }
    }

    @media (max-width: 640px) {
      .topbar,
      main {
        padding-left: 14px;
        padding-right: 14px;
      }

      .topbar {
        align-items: stretch;
        flex-direction: column;
      }

      h1 {
        font-size: 20px;
      }

      .header-actions,
      .form-actions {
        align-items: stretch;
      }

      .header-actions button,
      .form-actions button {
        flex: 1 1 auto;
      }

      .form-grid {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <header>
    <div class="topbar">
      <div>
        <h1>项目质量英语词库管理器</h1>
        <div class="db-path" id="dbPath"></div>
      </div>
      <div class="header-actions">
        <button id="newButton" type="button">新增词条</button>
        <button id="batchImportButton" type="button">批量导入</button>
        <button id="reviewButton" type="button">复习</button>
        <button id="exportButton" type="button">导出 Anki CSV</button>
        <button id="reloadButton" type="button">刷新</button>
      </div>
    </div>
  </header>

  <main>
    <div class="toolbar" id="libraryToolbar">
      <div class="status-tabs">
        <button class="tab active" type="button" data-status="active">词库</button>
        <button class="tab" type="button" data-status="deleted">回收站</button>
      </div>
      <div class="filter search">
        <label for="keyword">关键词</label>
        <input id="keyword" type="search" autocomplete="off">
      </div>
      <div class="filter">
        <label for="category">分类</label>
        <input id="category" type="search" autocomplete="off">
      </div>
      <div class="filter">
        <label for="entryTypeFilter">词条类型</label>
        <select id="entryTypeFilter"></select>
      </div>
      <div class="filter">
        <label for="sortBy">排序方式</label>
        <select id="sortBy">
          <option value="id">默认顺序</option>
          <option value="english_asc">英文 A-Z</option>
          <option value="english_desc">英文 Z-A</option>
          <option value="updated_desc">最近更新</option>
          <option value="category">分类</option>
          <option value="mastery">掌握程度</option>
          <option value="custom">自定义排序</option>
        </select>
      </div>
    </div>

    <section class="import-panel hidden" id="importPanel">
      <div class="panel-head">
        <h2 class="panel-title">批量导入 ChatGPT 词条</h2>
        <span class="count" id="importCount">未解析</span>
      </div>
      <div class="import-body">
        <div class="field full">
          <label for="importText">粘贴内容</label>
          <textarea class="import-textarea" id="importText" placeholder="可以一次粘贴 1 到 10 条，例如：&#10;1. APQP (Advanced Product Quality Planning)&#10;中文解释：...&#10;Example Sentence:&#10;The APQP activities are progressing...&#10;Meeting Phrases:&#10;- Are all APQP deliverables on schedule?"></textarea>
        </div>
        <div class="form-grid">
          <div class="field">
            <label for="importCategory">统一分类</label>
            <input id="importCategory" autocomplete="off">
          </div>
          <div class="field">
            <label for="importSource">来源</label>
            <input id="importSource" autocomplete="off">
          </div>
        </div>
        <div class="import-actions">
          <button class="primary" id="previewImportButton" type="button">解析预览</button>
          <button id="importAllButton" type="button" disabled>导入全部</button>
          <button id="closeImportButton" type="button">收起</button>
        </div>
        <div class="status-line" id="importMessage"></div>
        <div class="import-preview hidden" id="importPreview"></div>
      </div>
    </section>

    <section class="review-panel hidden" id="reviewPanel">
      <div class="panel-head">
        <h2 class="panel-title">复习</h2>
        <span class="count" id="reviewCount">未开始</span>
      </div>
      <div class="review-body">
        <div class="review-controls">
          <div class="field">
            <label for="reviewMode">复习模式</label>
            <select id="reviewMode">
              <option value="zh_to_en">看中文选英文</option>
              <option value="en_to_zh">看英文选中文</option>
              <option value="spelling">听音拼写</option>
            </select>
          </div>
          <div class="field">
            <label for="reviewScope">复习范围</label>
            <select id="reviewScope">
              <option value="pool">全部复习库</option>
              <option value="pending">待复习</option>
              <option value="reviewed">已复习</option>
            </select>
          </div>
          <div class="field">
            <label for="reviewCategory">分类</label>
            <input id="reviewCategory" type="search" autocomplete="off">
          </div>
          <div class="field">
            <label for="reviewEntryType">词条类型</label>
            <select id="reviewEntryType"></select>
          </div>
          <div class="review-actions">
            <button class="primary" id="startReviewButton" type="button">开始复习</button>
            <button id="backToLibraryButton" type="button">返回词库</button>
          </div>
        </div>

        <div class="review-card">
          <div class="review-mode-label" id="reviewModeLabel">请选择模式后开始复习</div>
          <div class="review-prompt" id="reviewPrompt">点击“开始复习”抽取第一题。</div>
          <div class="review-detail" id="reviewPromptDetail"></div>
          <div class="review-actions">
            <button class="audio-button hidden" id="playReviewAudioButton" type="button" title="播放美音" aria-label="播放美音">▶</button>
          </div>
          <div class="review-options" id="reviewOptions"></div>
          <div class="spelling-row hidden" id="spellingRow">
            <input id="spellingInput" autocomplete="off" placeholder="输入听到的英文">
            <button id="submitSpellingButton" type="button">提交</button>
          </div>
          <div class="answer-panel hidden" id="answerPanel">
            <div class="answer-result" id="answerResult"></div>
            <div class="answer-grid" id="answerDetails"></div>
            <div class="review-status-actions">
              <button id="markPendingButton" type="button">还要复习</button>
              <button id="markReviewedButton" type="button">暂时会了</button>
              <button class="primary" id="markMasteredButton" type="button">已掌握</button>
              <button id="nextReviewButton" type="button">下一题</button>
            </div>
          </div>
          <div class="status-line" id="reviewMessage"></div>
        </div>
      </div>
    </section>

    <div class="layout" id="libraryLayout">
      <section class="list-panel">
        <div class="panel-head">
          <h2 class="panel-title">词条列表</h2>
          <span class="count" id="entryCount">0 条</span>
        </div>
        <div class="table-wrap" id="tableWrap"></div>
        <div class="pagination-bar">
          <div class="page-size">
            <label for="pageSize">每页</label>
            <select id="pageSize">
              <option value="10">10 条</option>
              <option value="20">20 条</option>
              <option value="50">50 条</option>
            </select>
          </div>
          <div class="page-controls">
            <button id="prevPageButton" type="button">上一页</button>
            <span id="pageInfo">第 1 / 1 页</span>
            <button id="nextPageButton" type="button">下一页</button>
          </div>
        </div>
      </section>

      <aside class="editor-panel">
        <div class="panel-head">
          <h2 class="panel-title" id="editorTitle">新增词条</h2>
          <span class="count" id="selectedInfo">未选择</span>
        </div>
        <form id="entryForm">
          <div class="form-grid">
            <div class="field">
              <label for="chinese">中文名称</label>
              <input id="chinese" name="chinese" autocomplete="off">
            </div>
            <div class="field">
              <label for="english">英文名称</label>
              <div class="inline-input">
                <input id="english" name="english" autocomplete="off">
                <button class="audio-button" id="playEditorEnglishButton" type="button" title="播放美音" aria-label="播放英文">▶</button>
              </div>
            </div>
            <div class="field">
              <label for="abbreviation">缩写</label>
              <input id="abbreviation" name="abbreviation" autocomplete="off">
            </div>
            <div class="field">
              <label for="entry_type">词条类型</label>
              <select id="entry_type" name="entry_type"></select>
            </div>
            <div class="field full">
              <label for="categories">分类</label>
              <input id="categories" name="categories" autocomplete="off">
            </div>
            <div class="field full">
              <label for="explanation">中文解释</label>
              <textarea id="explanation" name="explanation"></textarea>
            </div>
            <div class="field full">
              <label for="example">例句</label>
              <textarea id="example" name="example"></textarea>
            </div>
            <div class="field">
              <label for="source">来源</label>
              <input id="source" name="source" autocomplete="off">
            </div>
            <div class="field">
              <label for="mastery_level">掌握程度</label>
              <select id="mastery_level" name="mastery_level"></select>
            </div>
            <div class="field">
              <label for="review_status">复习状态</label>
              <select id="review_status" name="review_status"></select>
            </div>
            <div class="field">
              <label for="sort_order">自定义排序号</label>
              <input id="sort_order" name="sort_order" type="number" min="0" step="1" autocomplete="off">
            </div>
            <div class="field full">
              <label for="note">备注</label>
              <textarea id="note" name="note"></textarea>
            </div>
          </div>
          <div class="status-line" id="message"></div>
          <div class="form-actions">
            <button class="primary" id="saveButton" type="submit">保存</button>
            <button id="saveAndNewButton" type="button">保存并新增</button>
            <button class="hidden" id="cloneButton" type="button">另存为新词条</button>
            <button class="danger hidden" id="deleteButton" type="button">删除</button>
            <button class="warning hidden" id="restoreButton" type="button">恢复</button>
            <button class="danger hidden" id="purgeButton" type="button">彻底删除</button>
          </div>
        </form>
      </aside>
    </div>
  </main>

  <script>
    const state = {
      entries: [],
      currentId: null,
      currentDeleted: false,
      filters: {
        status: "active",
        keyword: "",
        category: "",
        entryType: "",
        sortBy: "id"
      },
      pagination: {
        page: 1,
        pageSize: 10
      },
      importEntries: [],
      reviewQuestion: null,
      reviewAnswered: false,
      audio: null,
      options: {
        entryTypes: [],
        masteryLevels: [],
        reviewStatuses: [],
        defaultMasteryLevel: "学习中",
        defaultReviewStatus: "待复习"
      }
    };

    const fields = [
      "chinese",
      "english",
      "abbreviation",
      "categories",
      "explanation",
      "example",
      "source",
      "note"
    ];

    const $ = (id) => document.getElementById(id);

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function setMessage(text, type = "") {
      const element = $("message");
      element.textContent = text;
      element.className = `status-line ${type}`;
    }

    function setImportMessage(text, type = "") {
      const element = $("importMessage");
      element.textContent = text;
      element.className = `status-line ${type}`;
    }

    function setReviewMessage(text, type = "") {
      const element = $("reviewMessage");
      element.textContent = text;
      element.className = `status-line ${type}`;
    }

    async function requestJson(url, options = {}) {
      const response = await fetch(url, {
        headers: {
          "Content-Type": "application/json"
        },
        ...options
      });
      const data = await response.json();
      if (!response.ok || data.ok === false) {
        throw new Error(data.error || "操作失败");
      }
      return data;
    }

    function fillSelect(selectId, values, includeAll = false) {
      const select = $(selectId);
      select.innerHTML = "";
      if (includeAll) {
        const option = document.createElement("option");
        option.value = "";
        option.textContent = "全部";
        select.appendChild(option);
      }
      values.forEach((value) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
      });
    }

    function collectFormData() {
      const data = {};
      fields.forEach((field) => {
        data[field] = $(field).value.trim();
      });
      data.entry_type = $("entry_type").value;
      data.mastery_level = $("mastery_level").value;
      data.review_status = $("review_status").value;
      data.sort_order = $("sort_order").value.trim();
      return data;
    }

    function collectImportPayload() {
      return {
        text: $("importText").value.trim(),
        category: $("importCategory").value.trim(),
        source: $("importSource").value.trim(),
        skip_duplicates: true
      };
    }

    function getTotalPages() {
      return Math.max(1, Math.ceil(state.entries.length / state.pagination.pageSize));
    }

    function clampPage() {
      const totalPages = getTotalPages();
      state.pagination.page = Math.min(Math.max(1, state.pagination.page), totalPages);
      return totalPages;
    }

    function updatePaginationControls() {
      const totalPages = clampPage();
      $("pageSize").value = String(state.pagination.pageSize);
      $("pageInfo").textContent = `第 ${state.pagination.page} / ${totalPages} 页`;
      $("prevPageButton").disabled = state.pagination.page <= 1;
      $("nextPageButton").disabled = state.pagination.page >= totalPages;
    }

    function changePage(nextPage) {
      state.pagination.page = nextPage;
      renderEntries();
    }

    function scrollEditorToTop() {
      $("entryForm").scrollTo({top: 0, behavior: "smooth"});
    }

    function clearForm() {
      state.currentId = null;
      state.currentDeleted = false;
      fields.forEach((field) => {
        $(field).value = "";
      });
      if (state.options.entryTypes.length) {
        $("entry_type").value = state.options.entryTypes[0];
      }
      if (state.options.masteryLevels.length) {
        $("mastery_level").value = state.options.defaultMasteryLevel || state.options.masteryLevels[0];
      }
      if (state.options.reviewStatuses.length) {
        $("review_status").value = state.options.defaultReviewStatus || state.options.reviewStatuses[0];
      }
      $("sort_order").value = "";
      $("editorTitle").textContent = "新增词条";
      $("selectedInfo").textContent = "未选择";
      $("saveButton").classList.remove("hidden");
      $("saveAndNewButton").classList.remove("hidden");
      $("cloneButton").classList.add("hidden");
      $("deleteButton").classList.add("hidden");
      $("restoreButton").classList.add("hidden");
      $("purgeButton").classList.add("hidden");
      document.querySelectorAll("tbody tr").forEach((row) => row.classList.remove("selected"));
      setMessage("");
    }

    function selectEntry(entry) {
      state.currentId = entry.id;
      state.currentDeleted = Number(entry.is_deleted) === 1;
      fields.forEach((field) => {
        $(field).value = entry[field] || "";
      });
      $("entry_type").value = entry.entry_type || state.options.entryTypes[0] || "";
      $("mastery_level").value = entry.mastery_level || state.options.masteryLevels[0] || "";
      $("review_status").value = entry.review_status || state.options.defaultReviewStatus || state.options.reviewStatuses[0] || "";
      $("sort_order").value = entry.sort_order === "" ? "" : entry.sort_order;
      $("editorTitle").textContent = state.currentDeleted ? "回收站词条" : "修改词条";
      $("selectedInfo").textContent = "已选择";
      $("saveButton").classList.toggle("hidden", state.currentDeleted);
      $("saveAndNewButton").classList.add("hidden");
      $("cloneButton").classList.toggle("hidden", state.currentDeleted);
      $("deleteButton").classList.toggle("hidden", state.currentDeleted);
      $("restoreButton").classList.toggle("hidden", !state.currentDeleted);
      $("purgeButton").classList.toggle("hidden", !state.currentDeleted);
      document.querySelectorAll("tbody tr").forEach((row) => {
        row.classList.toggle("selected", Number(row.dataset.id) === Number(entry.id));
      });
      setMessage("");
    }

    function renderEntries() {
      clampPage();
      const start = (state.pagination.page - 1) * state.pagination.pageSize;
      const end = Math.min(start + state.pagination.pageSize, state.entries.length);
      const visibleEntries = state.entries.slice(start, end);
      $("entryCount").textContent = state.entries.length
        ? `${state.entries.length} 条，显示 ${start + 1}-${end}`
        : "0 条";
      if (!state.entries.length) {
        $("tableWrap").innerHTML = '<div class="empty">没有找到词条</div>';
        updatePaginationControls();
        return;
      }

      const rows = visibleEntries.map((entry, index) => `
        <tr data-id="${entry.id}">
          <td class="row-number">${start + index + 1}</td>
          <td class="sort-order">${escapeHtml(entry.sort_order)}</td>
          <td class="name">${escapeHtml(entry.chinese || entry.english || entry.abbreviation)}</td>
          <td class="english">
            <div class="english-content">
              ${entry.english ? `<button class="audio-button row-audio-button" type="button" data-speak="${escapeHtml(entry.english)}" title="播放美音" aria-label="播放美音">▶</button>` : ""}
              <span class="english-text">${escapeHtml(entry.english)}</span>
            </div>
          </td>
          <td class="abbreviation">${escapeHtml(entry.abbreviation)}</td>
          <td class="type">${escapeHtml(entry.entry_type)}</td>
          <td class="category">${escapeHtml(entry.categories)}</td>
          <td class="mastery">${escapeHtml(entry.mastery_level)}</td>
          <td class="review-status">${escapeHtml(entry.review_status)}</td>
          <td class="note">${escapeHtml(entry.explanation || entry.note)}</td>
        </tr>
      `).join("");

      $("tableWrap").innerHTML = `
        <table>
          <colgroup>
            <col class="col-id">
            <col class="col-sort">
            <col class="col-name">
            <col class="col-english">
            <col class="col-abbreviation">
            <col class="col-type">
            <col class="col-category">
            <col class="col-mastery">
            <col class="col-review">
            <col class="col-note">
          </colgroup>
          <thead>
            <tr>
              <th>序号</th>
              <th>排序</th>
              <th>名称</th>
              <th>英文</th>
              <th>缩写</th>
              <th>类型</th>
              <th>分类</th>
              <th>掌握</th>
              <th>复习</th>
              <th>解释 / 备注</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      `;

      document.querySelectorAll("tbody tr").forEach((row) => {
        row.classList.toggle("selected", Number(row.dataset.id) === Number(state.currentId));
        row.addEventListener("click", () => {
          const entry = state.entries.find((item) => Number(item.id) === Number(row.dataset.id));
          if (entry) {
            selectEntry(entry);
          }
        });
      });

      document.querySelectorAll("[data-speak]").forEach((button) => {
        button.addEventListener("click", (event) => {
          event.stopPropagation();
          playText(button.dataset.speak);
        });
      });

      updatePaginationControls();
    }

    async function loadEntries(keepSelection = false, resetPage = true) {
      state.filters.keyword = $("keyword").value.trim();
      state.filters.category = $("category").value.trim();
      state.filters.entryType = $("entryTypeFilter").value;
      state.filters.sortBy = $("sortBy").value;

      const params = new URLSearchParams({
        status: state.filters.status,
        keyword: state.filters.keyword,
        category: state.filters.category,
        entry_type: state.filters.entryType,
        sort: state.filters.sortBy
      });
      const data = await requestJson(`/api/entries?${params.toString()}`);
      state.entries = data.entries;

      if (keepSelection && state.currentId !== null) {
        const selectedIndex = state.entries.findIndex((entry) => Number(entry.id) === Number(state.currentId));
        const selected = state.entries[selectedIndex];
        if (selected) {
          state.pagination.page = Math.floor(selectedIndex / state.pagination.pageSize) + 1;
          renderEntries();
          selectEntry(selected);
          return;
        }
      }

      if (resetPage) {
        state.pagination.page = 1;
      }
      renderEntries();
      clearForm();
    }

    async function loadOptions() {
      const data = await requestJson("/api/options");
      state.options.entryTypes = data.entry_types;
      state.options.masteryLevels = data.mastery_levels;
      state.options.reviewStatuses = data.review_statuses;
      state.options.defaultMasteryLevel = data.default_mastery_level || "学习中";
      state.options.defaultReviewStatus = data.default_review_status || "待复习";
      $("dbPath").textContent = data.db_path;
      fillSelect("entryTypeFilter", state.options.entryTypes, true);
      fillSelect("reviewEntryType", state.options.entryTypes, true);
      fillSelect("entry_type", state.options.entryTypes);
      fillSelect("mastery_level", state.options.masteryLevels);
      fillSelect("review_status", state.options.reviewStatuses);
      $("importCategory").value = data.default_import_category || "";
      $("importSource").value = data.default_import_source || "";
    }

    function showLibraryPanels() {
      $("reviewPanel").classList.add("hidden");
      $("libraryToolbar").classList.remove("hidden");
      $("libraryLayout").classList.remove("hidden");
    }

    function openImportPanel() {
      showLibraryPanels();
      $("importPanel").classList.remove("hidden");
      $("importText").focus();
    }

    function closeImportPanel() {
      $("importPanel").classList.add("hidden");
    }

    function renderImportPreview(entries) {
      state.importEntries = entries;
      $("importCount").textContent = `${entries.length} 条`;
      $("importAllButton").disabled = !entries.some((entry) => !entry.duplicate && !entry.error);

      if (!entries.length) {
        $("importPreview").classList.add("hidden");
        $("importPreview").innerHTML = "";
        return;
      }

      const rows = entries.map((entry, index) => {
        const warning = entry.error || entry.duplicate || "";
        const status = warning ? warning : "可导入";
        const statusClass = warning ? "preview-status warning" : "preview-status";
        return `
          <tr>
            <td>${index + 1}</td>
            <td class="${statusClass}">${escapeHtml(status)}</td>
            <td>${escapeHtml(entry.english)}</td>
            <td>${escapeHtml(entry.abbreviation)}</td>
            <td>${escapeHtml(entry.chinese)}</td>
            <td>${escapeHtml(entry.entry_type)}</td>
            <td>${escapeHtml(entry.example)}</td>
            <td><button type="button" data-fill-import="${index}">填入表单</button></td>
          </tr>
        `;
      }).join("");

      $("importPreview").innerHTML = `
        <table>
          <thead>
            <tr>
              <th>序号</th>
              <th>状态</th>
              <th>英文名称</th>
              <th>缩写</th>
              <th>中文名称</th>
              <th>类型</th>
              <th>例句</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      `;
      $("importPreview").classList.remove("hidden");
      document.querySelectorAll("[data-fill-import]").forEach((button) => {
        button.addEventListener("click", () => {
          const entry = state.importEntries[Number(button.dataset.fillImport)];
          if (entry) {
            fillFormFromImport(entry);
          }
        });
      });
    }

    function fillFormFromImport(entry) {
      clearForm();
      fields.forEach((field) => {
        $(field).value = entry[field] || "";
      });
      $("entry_type").value = entry.entry_type || state.options.entryTypes[0] || "";
      $("mastery_level").value = entry.mastery_level || state.options.defaultMasteryLevel || "";
      $("review_status").value = entry.review_status || state.options.defaultReviewStatus || "";
      $("sort_order").value = entry.sort_order || "";
      scrollEditorToTop();
      setMessage("已填入右侧表单，确认后可以保存。", "ok");
    }

    async function previewImportEntries() {
      setImportMessage("");
      try {
        const data = await requestJson("/api/import-preview", {
          method: "POST",
          body: JSON.stringify(collectImportPayload())
        });
        renderImportPreview(data.entries);
        setImportMessage(`已解析 ${data.count} 条，请先检查预览。`, "ok");
      } catch (error) {
        renderImportPreview([]);
        setImportMessage(error.message, "error");
      }
    }

    async function importAllPreviewEntries() {
      setImportMessage("");
      if (!state.importEntries.length) {
        setImportMessage("请先解析预览。", "error");
        return;
      }
      if (!confirm("确认导入预览中的可导入词条吗？重复项会自动跳过。")) {
        return;
      }
      try {
        const data = await requestJson("/api/import-entries", {
          method: "POST",
          body: JSON.stringify(collectImportPayload())
        });
        setImportMessage(data.message, "ok");
        state.importEntries = [];
        $("importAllButton").disabled = true;
        await loadEntries(false);
      } catch (error) {
        setImportMessage(error.message, "error");
      }
    }

    function openReviewPanel() {
      $("libraryToolbar").classList.add("hidden");
      $("libraryLayout").classList.add("hidden");
      $("importPanel").classList.add("hidden");
      $("reviewPanel").classList.remove("hidden");
      setReviewMessage("");
    }

    function returnToLibrary() {
      showLibraryPanels();
      loadEntries(true);
    }

    function reviewModeLabel(mode) {
      if (mode === "zh_to_en") {
        return "看中文选英文";
      }
      if (mode === "en_to_zh") {
        return "看英文选中文";
      }
      return "听音拼写";
    }

    function collectReviewParams() {
      return new URLSearchParams({
        mode: $("reviewMode").value,
        scope: $("reviewScope").value,
        category: $("reviewCategory").value.trim(),
        entry_type: $("reviewEntryType").value
      });
    }

    function normalizeSpelling(value) {
      return String(value || "")
        .toLowerCase()
        .replaceAll("&", " and ")
        .replace(/[^a-z0-9]+/g, " ")
        .trim()
        .replace(/\s+/g, " ");
    }

    function resetReviewAnswer() {
      state.reviewAnswered = false;
      $("answerPanel").classList.add("hidden");
      $("answerResult").textContent = "";
      $("answerResult").className = "answer-result";
      $("answerDetails").innerHTML = "";
      setReviewMessage("");
    }

    async function loadReviewQuestion() {
      resetReviewAnswer();
      $("reviewOptions").innerHTML = "";
      $("spellingRow").classList.add("hidden");
      $("playReviewAudioButton").classList.add("hidden");
      $("spellingInput").value = "";
      try {
        const data = await requestJson(`/api/review/next?${collectReviewParams().toString()}`);
        state.reviewQuestion = data.question;
        renderReviewQuestion(data.question);
      } catch (error) {
        state.reviewQuestion = null;
        $("reviewCount").textContent = "0 条";
        $("reviewModeLabel").textContent = reviewModeLabel($("reviewMode").value);
        $("reviewPrompt").textContent = "没有可复习的词条";
        $("reviewPromptDetail").textContent = error.message;
        setReviewMessage(error.message, "error");
      }
    }

    function renderReviewQuestion(question) {
      $("reviewCount").textContent = `${question.total_candidates} 条可抽取`;
      $("reviewModeLabel").textContent = reviewModeLabel(question.mode);
      $("reviewPrompt").textContent = question.prompt_title || "";
      $("reviewPromptDetail").textContent = question.prompt_detail || "";
      $("playReviewAudioButton").classList.toggle("hidden", !question.speak_text);

      if (question.mode === "spelling") {
        $("reviewOptions").innerHTML = "";
        $("spellingRow").classList.remove("hidden");
        $("spellingInput").focus();
        return;
      }

      $("spellingRow").classList.add("hidden");
      const labels = ["A", "B", "C", "D"];
      $("reviewOptions").innerHTML = question.options.map((option, index) => `
        <button class="review-option" type="button" data-review-option="${index}">
          ${labels[index] || index + 1}. ${escapeHtml(option.text)}
        </button>
      `).join("");
      document.querySelectorAll("[data-review-option]").forEach((button) => {
        button.addEventListener("click", () => answerReviewOption(Number(button.dataset.reviewOption)));
      });
    }

    function renderAnswerDetails(question) {
      const entry = question.entry || {};
      const rows = [
        ["正确答案", question.answer_text || ""],
        ["英文名称", entry.english || ""],
        ["缩写", entry.abbreviation || ""],
        ["中文名称", entry.chinese || ""],
        ["中文解释", entry.explanation || ""],
        ["例句", entry.example || ""],
        ["备注", entry.note || ""],
        ["复习状态", entry.review_status || ""]
      ].filter((row) => row[1]);
      $("answerDetails").innerHTML = rows.map((row) => `
        <strong>${escapeHtml(row[0])}</strong>
        <span>${escapeHtml(row[1])}</span>
      `).join("");
    }

    function showReviewAnswer(isCorrect, userAnswer = "") {
      const question = state.reviewQuestion;
      if (!question) {
        return;
      }
      state.reviewAnswered = true;
      $("answerPanel").classList.remove("hidden");
      $("answerResult").className = `answer-result ${isCorrect ? "" : "error"}`;
      if (isCorrect) {
        $("answerResult").textContent = "正确";
      } else if (userAnswer) {
        $("answerResult").textContent = `未完全一致。你的答案：${userAnswer}`;
      } else {
        $("answerResult").textContent = "回答错误";
      }
      renderAnswerDetails(question);
    }

    function answerReviewOption(selectedIndex) {
      const question = state.reviewQuestion;
      if (!question || state.reviewAnswered) {
        return;
      }
      const correctIndex = Number(question.correct_index);
      document.querySelectorAll("[data-review-option]").forEach((button) => {
        const index = Number(button.dataset.reviewOption);
        button.disabled = true;
        button.classList.toggle("correct", index === correctIndex);
        button.classList.toggle("incorrect", index === selectedIndex && selectedIndex !== correctIndex);
      });
      showReviewAnswer(selectedIndex === correctIndex);
    }

    function submitSpellingAnswer() {
      const question = state.reviewQuestion;
      if (!question || state.reviewAnswered) {
        return;
      }
      const userAnswer = $("spellingInput").value.trim();
      const isCorrect = normalizeSpelling(userAnswer) === normalizeSpelling(question.answer_text);
      showReviewAnswer(isCorrect, userAnswer);
    }

    async function markReviewStatus(reviewStatus) {
      const question = state.reviewQuestion;
      if (!question) {
        return;
      }
      try {
        const data = await requestJson(`/api/entries/${question.entry_id}/review-status`, {
          method: "POST",
          body: JSON.stringify({review_status: reviewStatus})
        });
        state.reviewQuestion.entry = data.entry;
        renderAnswerDetails(state.reviewQuestion);
        setReviewMessage(data.message, "ok");
      } catch (error) {
        setReviewMessage(error.message, "error");
      }
    }

    async function saveCurrentEntry(options = {}) {
      const {forceCreate = false, afterSave = "stay"} = options;
      setMessage("");
      const payload = collectFormData();
      try {
        const isCreate = forceCreate || state.currentId === null;
        let data;
        if (isCreate) {
          data = await requestJson("/api/entries", {
            method: "POST",
            body: JSON.stringify(payload)
          });
        } else {
          data = await requestJson(`/api/entries/${state.currentId}/update`, {
            method: "POST",
            body: JSON.stringify(payload)
          });
        }

        if (afterSave === "new") {
          await loadEntries(false);
          clearForm();
          scrollEditorToTop();
          setMessage("已保存，可以继续新增下一条。", "ok");
          return;
        }

        state.currentId = data.entry.id;
        await loadEntries(true);
        setMessage(forceCreate ? "已另存为新词条。" : (isCreate ? "已新增词条。" : "已保存词条。"), "ok");
      } catch (error) {
        setMessage(error.message, "error");
      }
    }

    async function saveEntry(event) {
      event.preventDefault();
      await saveCurrentEntry();
    }

    async function saveAndCreateNext() {
      await saveCurrentEntry({afterSave: "new"});
    }

    async function cloneCurrentEntry() {
      if (state.currentId === null || state.currentDeleted) {
        return;
      }
      await saveCurrentEntry({forceCreate: true});
    }

    async function softDeleteCurrent() {
      if (state.currentId === null) {
        return;
      }
      if (!confirm("确认删除这个词条吗？删除后可以在回收站恢复。")) {
        return;
      }
      try {
        const data = await requestJson(`/api/entries/${state.currentId}/delete`, { method: "POST" });
        setMessage(data.message, "ok");
        await loadEntries(false);
      } catch (error) {
        setMessage(error.message, "error");
      }
    }

    async function restoreCurrent() {
      if (state.currentId === null) {
        return;
      }
      if (!confirm("确认从回收站恢复这个词条吗？")) {
        return;
      }
      try {
        const data = await requestJson(`/api/entries/${state.currentId}/restore`, { method: "POST" });
        setMessage(data.message, "ok");
        await loadEntries(false);
      } catch (error) {
        setMessage(error.message, "error");
      }
    }

    async function playText(text) {
      const spokenText = String(text || "").trim();
      if (!spokenText) {
        setMessage("没有可播放的英文内容。", "error");
        return;
      }

      try {
        setMessage("正在准备美音语音...");
        const params = new URLSearchParams({ text: spokenText });
        const data = await requestJson(`/api/tts?${params.toString()}`);

        if (state.audio) {
          state.audio.pause();
          state.audio = null;
        }

        state.audio = new Audio(data.audio_url);
        await state.audio.play();
        const ttsLabel = `${data.voice} ${data.rate} ${data.pitch}`;
        setMessage(data.cached ? `正在播放缓存语音：${ttsLabel}` : `语音已生成，正在播放：${ttsLabel}`, "ok");
      } catch (error) {
        setMessage(error.message, "error");
      }
    }

    async function permanentlyDeleteCurrent() {
      if (state.currentId === null || !state.currentDeleted) {
        return;
      }
      if (!confirm("彻底删除后不可恢复。系统会先自动备份数据库。确认继续吗？")) {
        return;
      }
      const typed = prompt("请输入“彻底删除”确认：");
      if (typed !== "彻底删除") {
        setMessage("已取消彻底删除。", "error");
        return;
      }
      try {
        const data = await requestJson(`/api/entries/${state.currentId}/purge`, {method: "POST"});
        state.currentId = null;
        state.currentDeleted = false;
        await loadEntries(false);
        setMessage(data.message, "ok");
      } catch (error) {
        setMessage(error.message, "error");
      }
    }

    async function exportAnki() {
      try {
        const data = await requestJson("/api/export-anki", { method: "POST" });
        setMessage(data.message, "ok");
        window.location.href = "/download/anki";
      } catch (error) {
        setMessage(error.message, "error");
      }
    }

    function bindEvents() {
      $("entryForm").addEventListener("submit", saveEntry);
      $("newButton").addEventListener("click", () => {
        showLibraryPanels();
        clearForm();
        scrollEditorToTop();
      });
      $("batchImportButton").addEventListener("click", openImportPanel);
      $("reviewButton").addEventListener("click", openReviewPanel);
      $("previewImportButton").addEventListener("click", previewImportEntries);
      $("importAllButton").addEventListener("click", importAllPreviewEntries);
      $("closeImportButton").addEventListener("click", closeImportPanel);
      $("startReviewButton").addEventListener("click", loadReviewQuestion);
      $("nextReviewButton").addEventListener("click", loadReviewQuestion);
      $("backToLibraryButton").addEventListener("click", returnToLibrary);
      $("playReviewAudioButton").addEventListener("click", () => {
        if (state.reviewQuestion && state.reviewQuestion.speak_text) {
          playText(state.reviewQuestion.speak_text);
        }
      });
      $("submitSpellingButton").addEventListener("click", submitSpellingAnswer);
      $("spellingInput").addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          submitSpellingAnswer();
        }
      });
      $("markPendingButton").addEventListener("click", () => markReviewStatus("待复习"));
      $("markReviewedButton").addEventListener("click", () => markReviewStatus("已复习"));
      $("markMasteredButton").addEventListener("click", () => markReviewStatus("已掌握"));
      $("reloadButton").addEventListener("click", () => loadEntries(true));
      $("exportButton").addEventListener("click", exportAnki);
      $("saveAndNewButton").addEventListener("click", saveAndCreateNext);
      $("cloneButton").addEventListener("click", cloneCurrentEntry);
      $("deleteButton").addEventListener("click", softDeleteCurrent);
      $("restoreButton").addEventListener("click", restoreCurrent);
      $("purgeButton").addEventListener("click", permanentlyDeleteCurrent);
      $("playEditorEnglishButton").addEventListener("click", () => playText($("english").value));
      $("pageSize").addEventListener("change", () => {
        state.pagination.pageSize = Number($("pageSize").value);
        state.pagination.page = 1;
        renderEntries();
      });
      $("prevPageButton").addEventListener("click", () => changePage(state.pagination.page - 1));
      $("nextPageButton").addEventListener("click", () => changePage(state.pagination.page + 1));
      ["keyword", "category"].forEach((id) => {
        $(id).addEventListener("input", () => {
          window.clearTimeout($(id)._timer);
          $(id)._timer = window.setTimeout(() => loadEntries(false), 220);
        });
      });
      $("entryTypeFilter").addEventListener("change", () => loadEntries(false));
      $("sortBy").addEventListener("change", () => loadEntries(false));
      document.querySelectorAll("[data-status]").forEach((button) => {
        button.addEventListener("click", () => {
          state.filters.status = button.dataset.status;
          document.querySelectorAll("[data-status]").forEach((item) => {
            item.classList.toggle("active", item === button);
          });
          loadEntries(false);
        });
      });
    }

    async function boot() {
      try {
        await loadOptions();
        bindEvents();
        await loadEntries(false);
      } catch (error) {
        setMessage(error.message, "error");
      }
    }

    boot();
  </script>
</body>
</html>
"""


class RequestError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def row_to_dict(row):
    return {key: row[key] if row[key] is not None else "" for key in row.keys()}


def clean_text(value):
    if value is None:
        return ""
    return str(value).strip()


def clean_import_line(line):
    text = clean_text(line)
    text = re.sub(r"^[>\|]\s*", "", text)
    text = re.sub(r"^[•·●]\s*", "- ", text)
    text = re.sub(r"^\-\s+", "- ", text)
    return text.strip()


def is_abbreviation_text(text):
    value = clean_text(text).replace(" ", "")
    if not (2 <= len(value) <= 14):
        return False
    return bool(re.fullmatch(r"[A-Z0-9&/+\-.]+", value)) and any(char.isalpha() for char in value)


def has_abbreviation_feature(text):
    value = clean_text(text)
    if "&" in value or "/" in value:
        return True
    return bool(re.search(r"\b[A-Z]{2,}\b", value))


def parse_title_fields(title):
    title = clean_text(title)
    title = re.sub(r"\s+", " ", title)
    match = re.match(r"^(?P<outer>.+?)\s*[\(（]\s*(?P<inner>.+?)\s*[\)）]\s*$", title)
    if not match:
        return title, "", ""

    outer = clean_text(match.group("outer"))
    inner = clean_text(match.group("inner"))
    if is_abbreviation_text(outer) and not is_abbreviation_text(inner):
        return inner, outer, ""
    if is_abbreviation_text(inner):
        return outer, inner, ""
    if has_abbreviation_feature(outer):
        return outer, outer, inner
    return outer, "", inner


def first_chinese_name(explanation):
    text = clean_text(explanation)
    if not text:
        return ""
    text = re.sub(r"^[：:]\s*", "", text)
    segment = re.split(r"[。；;\n]", text, maxsplit=1)[0]
    segment = clean_text(segment)
    if len(segment) > 40:
        return ""
    return segment


def parse_section_label(line):
    lowered = line.lower().strip()
    patterns = [
        ("explanation", r"^(?:chinese\s+explanation|中文解释)(?:\s*[（(].*?[）)])?\s*[：:]?\s*(.*)$"),
        ("example", r"^(?:example\s+sentence|例句)(?:\s*[（(].*?[）)])?\s*[：:]?\s*(.*)$"),
        ("meeting", r"^(?:meeting\s+phrases?|会议句式|会议表达)(?:\s*[（(].*?[）)])?\s*[：:]?\s*(.*)$"),
    ]
    for key, pattern in patterns:
        match = re.match(pattern, lowered, flags=re.IGNORECASE)
        if match:
            return key, clean_text(line[match.start(1):] if match.start(1) >= 0 else "")
    return None, ""


def normalize_section_text(lines, bullet=False):
    cleaned = []
    for line in lines:
        value = clean_import_line(line)
        if not value:
            continue
        if bullet:
            value = re.sub(r"^[\-\*]\s*", "", value).strip()
            if value:
                cleaned.append(f"- {value}")
        else:
            cleaned.append(re.sub(r"^\-\s*", "", value).strip())
    return "\n".join(cleaned).strip()


def guess_entry_type(english, abbreviation):
    if abbreviation:
        return ENTRY_TYPE_ABBREVIATION
    if re.search(r"\s|&|/", english):
        return ENTRY_TYPE_PHRASE
    return ENTRY_TYPE_WORD


def parse_import_block(number, title, block_lines, category, source):
    sections = {"explanation": [], "example": [], "meeting": []}
    current_section = None

    for raw_line in block_lines:
        line = clean_import_line(raw_line)
        if not line:
            continue
        section, inline_value = parse_section_label(line)
        if section:
            current_section = section
            if inline_value:
                sections[section].append(inline_value)
            continue
        if current_section:
            sections[current_section].append(line)

    english, abbreviation, title_note = parse_title_fields(title)
    explanation = normalize_section_text(sections["explanation"])
    example = normalize_section_text(sections["example"])
    meeting_note = normalize_section_text(sections["meeting"], bullet=True)
    note_parts = []
    if title_note:
        note_parts.append(f"英文括号说明：{title_note}")
    if meeting_note:
        note_parts.append(f"Meeting Phrases:\n{meeting_note}")

    entry = {
        "chinese": first_chinese_name(explanation),
        "english": english,
        "abbreviation": abbreviation,
        "entry_type": guess_entry_type(english, abbreviation),
        "categories": category,
        "explanation": explanation,
        "example": example,
        "source": source,
        "note": "\n\n".join(note_parts),
        "mastery_level": WEB_DEFAULT_MASTERY_LEVEL,
        "review_status": DEFAULT_REVIEW_STATUS,
        "sort_order": "",
        "raw_title": title,
        "raw_number": number,
    }
    entry["duplicate"] = find_duplicate_entry(entry)
    return entry


def parse_import_entries(raw_text, category="", source=""):
    text = str(raw_text or "").replace("\r\n", "\n").replace("\r", "\n")
    category = clean_text(category) or DEFAULT_IMPORT_CATEGORY
    source = clean_text(source) or DEFAULT_IMPORT_SOURCE
    lines = text.split("\n")
    heading_pattern = re.compile(r"^\s*(?:#+\s*)?(\d+)[\.．、)]\s+(.+?)\s*$")
    headings = []
    for index, line in enumerate(lines):
        match = heading_pattern.match(line)
        if match:
            headings.append((index, match.group(1), clean_text(match.group(2))))

    if not headings:
        first_line = next((clean_import_line(line) for line in lines if clean_import_line(line)), "")
        if not first_line:
            return []
        headings = [(0, "", first_line)]

    entries = []
    for heading_index, (line_index, number, title) in enumerate(headings):
        next_index = headings[heading_index + 1][0] if heading_index + 1 < len(headings) else len(lines)
        block_lines = lines[line_index + 1 : next_index]
        entry = parse_import_block(number, title, block_lines, category, source)
        if entry["english"] or entry["chinese"] or entry["abbreviation"]:
            entries.append(entry)
    return entries


def find_duplicate_entry(entry):
    conditions = []
    values = []
    for field in ("english", "abbreviation", "chinese"):
        value = clean_text(entry.get(field))
        if not value:
            continue
        conditions.append(f"LOWER({field}) = LOWER(?)")
        values.append(value)
    if not conditions:
        return ""

    with get_connection() as connection:
        row = connection.execute(
            f"""
            SELECT id, chinese, english, abbreviation, is_deleted
            FROM glossary_entries
            WHERE {' OR '.join(conditions)}
            ORDER BY is_deleted ASC, id ASC
            LIMIT 1
            """,
            values,
        ).fetchone()
    if row is None:
        return ""

    status = "回收站" if row["is_deleted"] else "词库"
    label = row["english"] or row["abbreviation"] or row["chinese"] or f"ID {row['id']}"
    return f"{status}中已有：{label}"


def normalize_payload(payload):
    data = {field: clean_text(payload.get(field)) for field in TEXT_FIELDS}
    data["categories"] = normalize_categories(data["categories"])

    if not data["chinese"] and not data["english"] and not data["abbreviation"]:
        raise RequestError("中文名称、英文名称、缩写至少需要填写一个。")

    entry_type = clean_text(payload.get("entry_type")) or VALID_ENTRY_TYPES[0]
    if entry_type not in VALID_ENTRY_TYPES:
        raise RequestError("词条类型无效。")

    mastery_level = clean_text(payload.get("mastery_level")) or WEB_DEFAULT_MASTERY_LEVEL
    if mastery_level not in VALID_MASTERY_LEVELS:
        raise RequestError("掌握程度无效。")

    review_status = clean_text(payload.get("review_status")) or DEFAULT_REVIEW_STATUS
    if review_status not in VALID_REVIEW_STATUSES:
        raise RequestError("复习状态无效。")

    data["entry_type"] = entry_type
    data["mastery_level"] = mastery_level
    data["review_status"] = review_status

    raw_sort_order = clean_text(payload.get("sort_order"))
    if raw_sort_order:
        try:
            sort_order = int(raw_sort_order)
        except ValueError as error:
            raise RequestError("自定义排序号必须是整数。") from error
        if sort_order < 0:
            raise RequestError("自定义排序号不能小于 0。")
        data["sort_order"] = sort_order
    else:
        data["sort_order"] = None

    return data


def fetch_entry(entry_id, only_deleted=False, only_active=False):
    conditions = ["id = ?"]
    values = [entry_id]
    if only_deleted:
        conditions.append("is_deleted = 1")
    if only_active:
        conditions.append("is_deleted = 0")

    with get_connection() as connection:
        row = connection.execute(
            f"SELECT * FROM glossary_entries WHERE {' AND '.join(conditions)}",
            values,
        ).fetchone()
    return row


def list_entries(query):
    status = query.get("status", ["active"])[0]
    keyword = clean_text(query.get("keyword", [""])[0])
    category = clean_text(query.get("category", [""])[0])
    entry_type = clean_text(query.get("entry_type", [""])[0])
    sort_by = clean_text(query.get("sort", ["id"])[0])
    order_clause = SORT_ORDER_CLAUSES.get(sort_by, SORT_ORDER_CLAUSES["id"])

    conditions = ["is_deleted = 1" if status == "deleted" else "is_deleted = 0"]
    values = []

    if keyword:
        like_keyword = f"%{keyword}%"
        conditions.append(
            """
            (
                chinese LIKE ?
                OR english LIKE ?
                OR abbreviation LIKE ?
                OR explanation LIKE ?
                OR categories LIKE ?
                OR note LIKE ?
            )
            """
        )
        values.extend([like_keyword] * 6)

    if category:
        conditions.append("categories LIKE ?")
        values.append(f"%{category}%")

    if entry_type in VALID_ENTRY_TYPES:
        conditions.append("entry_type = ?")
        values.append(entry_type)

    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT *
            FROM glossary_entries
            WHERE {' AND '.join(conditions)}
            ORDER BY {order_clause}
            """,
            values,
        ).fetchall()

    return [row_to_dict(row) for row in rows]


def create_entry(payload):
    data = normalize_payload(payload)
    current_time = now_text()

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO glossary_entries (
                chinese, english, abbreviation, entry_type, categories,
                explanation, example, source, note, mastery_level,
                review_status, sort_order, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                data["review_status"],
                data["sort_order"],
                current_time,
                current_time,
            ),
        )
        connection.commit()
        entry_id = cursor.lastrowid

    return row_to_dict(fetch_entry(entry_id))


def preview_import_entries(payload):
    raw_text = clean_text(payload.get("text"))
    if not raw_text:
        raise RequestError("请先粘贴需要解析的词条内容。")

    entries = parse_import_entries(
        raw_text,
        category=payload.get("category"),
        source=payload.get("source"),
    )
    if not entries:
        raise RequestError("没有识别到可导入的词条。请检查是否包含类似“1. APQP (...)”的标题。")

    for entry in entries:
        try:
            normalize_payload(entry)
            entry["error"] = ""
        except RequestError as error:
            entry["error"] = str(error)
    return entries


def import_previewed_entries(payload):
    entries = preview_import_entries(payload)
    skip_duplicates = payload.get("skip_duplicates", True) is not False
    importable_entries = []
    skipped_entries = []

    for entry in entries:
        if entry.get("error"):
            skipped_entries.append({"entry": entry, "reason": entry["error"]})
            continue
        if skip_duplicates and entry.get("duplicate"):
            skipped_entries.append({"entry": entry, "reason": entry["duplicate"]})
            continue
        importable_entries.append(entry)

    backup_path = backup_database("before_batch_import") if importable_entries else None
    imported_entries = [create_entry(entry) for entry in importable_entries]
    return imported_entries, skipped_entries, backup_path


def first_sentence(text):
    value = clean_text(text)
    if not value:
        return ""
    return clean_text(re.split(r"[。.!！?\n]", value, maxsplit=1)[0])


def english_answer_text(entry):
    english = clean_text(entry.get("english"))
    abbreviation = clean_text(entry.get("abbreviation"))
    if english and abbreviation and english.lower() != abbreviation.lower():
        return f"{english} ({abbreviation})"
    return english or abbreviation


def english_prompt_text(entry):
    english = clean_text(entry.get("english"))
    abbreviation = clean_text(entry.get("abbreviation"))
    if english and abbreviation and english.lower() != abbreviation.lower():
        return f"{abbreviation}\n{english}"
    return english or abbreviation


def spelling_answer_text(entry):
    return clean_text(entry.get("english")) or clean_text(entry.get("abbreviation"))


def chinese_answer_text(entry):
    return (
        clean_text(entry.get("chinese"))
        or first_sentence(entry.get("explanation"))
        or clean_text(entry.get("explanation"))[:60]
    )


def review_question_is_usable(entry, mode):
    if mode == "zh_to_en":
        return bool(chinese_answer_text(entry) and english_answer_text(entry))
    if mode == "en_to_zh":
        return bool(english_prompt_text(entry) and chinese_answer_text(entry))
    if mode == "spelling":
        return bool(spelling_answer_text(entry))
    return False


def review_scope_condition(scope):
    if scope == "pending":
        return "review_status = ?", [REVIEW_STATUS_PENDING]
    if scope == "reviewed":
        return "review_status = ?", [REVIEW_STATUS_REVIEWED]
    return "review_status IN (?, ?)", [REVIEW_STATUS_PENDING, REVIEW_STATUS_REVIEWED]


def fetch_review_entries(query):
    scope = clean_text(query.get("scope", ["pool"])[0])
    category = clean_text(query.get("category", [""])[0])
    entry_type = clean_text(query.get("entry_type", [""])[0])
    review_condition, values = review_scope_condition(scope)
    conditions = ["is_deleted = 0", review_condition]

    if category:
        conditions.append("categories LIKE ?")
        values.append(f"%{category}%")
    if entry_type in VALID_ENTRY_TYPES:
        conditions.append("entry_type = ?")
        values.append(entry_type)

    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT *
            FROM glossary_entries
            WHERE {' AND '.join(conditions)}
            """,
            values,
        ).fetchall()

    return [row_to_dict(row) for row in rows]


def fetch_distractor_entries(entry, mode):
    with get_connection() as connection:
        same_type_rows = connection.execute(
            """
            SELECT *
            FROM glossary_entries
            WHERE is_deleted = 0
              AND id != ?
              AND entry_type = ?
            """,
            (entry["id"], entry["entry_type"]),
        ).fetchall()
        all_rows = connection.execute(
            """
            SELECT *
            FROM glossary_entries
            WHERE is_deleted = 0
              AND id != ?
            """,
            (entry["id"],),
        ).fetchall()

    same_type_entries = [row_to_dict(row) for row in same_type_rows]
    all_entries = [row_to_dict(row) for row in all_rows]
    ordered = same_type_entries + [
        item for item in all_entries if item["id"] not in {entry["id"] for entry in same_type_entries}
    ]
    return [item for item in ordered if review_question_is_usable(item, mode)]


def make_review_options(entry, mode):
    correct_text = english_answer_text(entry) if mode == "zh_to_en" else chinese_answer_text(entry)
    distractors = []
    seen = {correct_text.strip().lower()}

    candidates = fetch_distractor_entries(entry, mode)
    random.shuffle(candidates)
    for candidate in candidates:
        text = english_answer_text(candidate) if mode == "zh_to_en" else chinese_answer_text(candidate)
        key = text.strip().lower()
        if not text or key in seen:
            continue
        distractors.append(text)
        seen.add(key)
        if len(distractors) >= 3:
            break

    options = [{"text": text, "correct": False} for text in distractors]
    options.append({"text": correct_text, "correct": True})
    random.shuffle(options)
    correct_index = next(index for index, option in enumerate(options) if option["correct"])
    return options, correct_index


def build_review_question(query):
    mode = clean_text(query.get("mode", ["zh_to_en"])[0]) or "zh_to_en"
    if mode not in ("zh_to_en", "en_to_zh", "spelling"):
        raise RequestError("复习模式无效。")

    candidates = [entry for entry in fetch_review_entries(query) if review_question_is_usable(entry, mode)]
    if not candidates:
        raise RequestError("当前筛选条件下没有可复习的词条。")

    weights = [REVIEW_STATUS_WEIGHTS.get(entry.get("review_status"), 0) for entry in candidates]
    if not any(weights):
        raise RequestError("当前筛选条件下没有可复习的词条。")

    entry = random.choices(candidates, weights=weights, k=1)[0]
    options, correct_index = ([], -1)
    if mode in ("zh_to_en", "en_to_zh"):
        options, correct_index = make_review_options(entry, mode)

    if mode == "zh_to_en":
        prompt_title = chinese_answer_text(entry)
        prompt_detail = clean_text(entry.get("explanation"))
        answer_text = english_answer_text(entry)
    elif mode == "en_to_zh":
        prompt_title = english_prompt_text(entry)
        prompt_detail = ""
        answer_text = chinese_answer_text(entry)
    else:
        prompt_title = "听音拼写"
        prompt_detail = "点击播放美音后输入听到的英文单词或词组。"
        answer_text = spelling_answer_text(entry)

    return {
        "mode": mode,
        "entry": entry,
        "entry_id": entry["id"],
        "prompt_title": prompt_title,
        "prompt_detail": prompt_detail,
        "answer_text": answer_text,
        "speak_text": spelling_answer_text(entry),
        "options": options,
        "correct_index": correct_index,
        "total_candidates": len(candidates),
    }


def update_review_status(entry_id, review_status):
    if review_status not in VALID_REVIEW_STATUSES:
        raise RequestError("复习状态无效。")
    if fetch_entry(entry_id, only_active=True) is None:
        raise RequestError("没有在词库中找到这个词条。", status=404)

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE glossary_entries
            SET review_status = ?,
                updated_at = ?
            WHERE id = ?
              AND is_deleted = 0
            """,
            (review_status, now_text(), entry_id),
        )
        connection.commit()

    return row_to_dict(fetch_entry(entry_id))


def update_entry(entry_id, payload):
    if fetch_entry(entry_id, only_active=True) is None:
        raise RequestError("没有在词库中找到这个词条。", status=404)

    data = normalize_payload(payload)
    backup_path = backup_database("before_web_edit")

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
                review_status = ?,
                sort_order = ?,
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
                data["review_status"],
                data["sort_order"],
                now_text(),
                entry_id,
            ),
        )
        connection.commit()

    return row_to_dict(fetch_entry(entry_id)), backup_path


def set_deleted_status(entry_id, is_deleted):
    row = fetch_entry(entry_id, only_deleted=not is_deleted, only_active=is_deleted)
    if row is None:
        target_status = "词库中" if is_deleted else "回收站中"
        raise RequestError(f"没有在{target_status}找到这个词条。", status=404)

    backup_path = backup_database("before_web_soft_delete" if is_deleted else "before_web_restore")

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

    return row_to_dict(fetch_entry(entry_id)), backup_path


def purge_deleted_entry(entry_id):
    row = fetch_entry(entry_id, only_deleted=True)
    if row is None:
        raise RequestError("没有在回收站中找到这个词条。", status=404)

    entry = row_to_dict(row)
    backup_path = backup_database("before_web_permanent_delete")

    with get_connection() as connection:
        connection.execute(
            """
            DELETE FROM glossary_entries
            WHERE id = ?
              AND is_deleted = 1
            """,
            (entry_id,),
        )
        connection.commit()

    return entry, backup_path


class GlossaryHandler(BaseHTTPRequestHandler):
    server_version = "QualityGlossaryWeb/0.1"

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self):
        body = HTML_PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_anki_file(self):
        export_anki_cards_to_file()
        body = ANKI_EXPORT_PATH.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="anki_cards.csv"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_audio_file(self, filename):
        if not filename.endswith(".mp3") or "/" in filename or "\\" in filename:
            raise RequestError("音频文件名无效。", status=404)

        audio_path = AUDIO_DIR / filename
        if not audio_path.exists():
            raise RequestError("音频文件不存在。", status=404)

        body = audio_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Cache-Control", "public, max-age=31536000")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw_body = self.rfile.read(length).decode("utf-8")
        try:
            return json.loads(raw_body)
        except json.JSONDecodeError as error:
            raise RequestError(f"JSON 格式无效：{error}")

    def handle_error(self, error):
        if isinstance(error, RequestError):
            self.send_json({"ok": False, "error": str(error)}, status=error.status)
        else:
            self.send_json({"ok": False, "error": f"服务器错误：{error}"}, status=500)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if path == "/":
                self.send_html()
            elif path == "/api/options":
                self.send_json(
                    {
                        "ok": True,
                        "db_path": str(DB_PATH),
                        "entry_types": VALID_ENTRY_TYPES,
                        "mastery_levels": VALID_MASTERY_LEVELS,
                        "review_statuses": VALID_REVIEW_STATUSES,
                        "default_mastery_level": WEB_DEFAULT_MASTERY_LEVEL,
                        "default_review_status": DEFAULT_REVIEW_STATUS,
                        "default_import_category": DEFAULT_IMPORT_CATEGORY,
                        "default_import_source": DEFAULT_IMPORT_SOURCE,
                    }
                )
            elif path == "/api/entries":
                self.send_json({"ok": True, "entries": list_entries(parse_qs(parsed.query))})
            elif path == "/api/review/next":
                self.send_json({"ok": True, "question": build_review_question(parse_qs(parsed.query))})
            elif path == "/api/tts":
                text = parse_qs(parsed.query).get("text", [""])[0]
                try:
                    audio_info = generate_tts_audio(text)
                except TtsError as error:
                    raise RequestError(str(error))
                self.send_json(
                    {
                        "ok": True,
                        "text": audio_info["text"],
                        "voice": audio_info["voice"],
                        "rate": audio_info["rate"],
                        "pitch": audio_info["pitch"],
                        "volume": audio_info["volume"],
                        "cached": audio_info["cached"],
                        "audio_url": f"/audio/{quote(audio_info['path'].name)}",
                    }
                )
            elif path.startswith("/audio/"):
                self.send_audio_file(path.removeprefix("/audio/"))
            elif path == "/download/anki":
                self.send_anki_file()
            else:
                self.send_json({"ok": False, "error": "页面不存在。"}, status=404)
        except Exception as error:
            self.handle_error(error)

    def do_POST(self):
        parsed = urlparse(self.path)
        parts = [part for part in parsed.path.split("/") if part]

        try:
            if parts == ["api", "entries"]:
                entry = create_entry(self.read_json())
                self.send_json({"ok": True, "entry": entry})
                return

            if parts == ["api", "import-preview"]:
                entries = preview_import_entries(self.read_json())
                self.send_json({"ok": True, "entries": entries, "count": len(entries)})
                return

            if parts == ["api", "import-entries"]:
                imported_entries, skipped_entries, backup_path = import_previewed_entries(self.read_json())
                self.send_json(
                    {
                        "ok": True,
                        "entries": imported_entries,
                        "skipped": skipped_entries,
                        "count": len(imported_entries),
                        "skipped_count": len(skipped_entries),
                        "backup_path": str(backup_path) if backup_path else "",
                        "message": f"已导入 {len(imported_entries)} 条词条，跳过 {len(skipped_entries)} 条。",
                    }
                )
                return

            if parts == ["api", "export-anki"]:
                export_path, entry_count = export_anki_cards_to_file()
                self.send_json(
                    {
                        "ok": True,
                        "path": str(export_path),
                        "count": entry_count,
                        "message": f"已导出 {entry_count} 张 Anki 卡片。",
                    }
                )
                return

            if len(parts) == 4 and parts[:2] == ["api", "entries"]:
                try:
                    entry_id = int(parts[2])
                except ValueError:
                    raise RequestError("词条编号无效。")

                action = parts[3]
                if action == "update":
                    entry, backup_path = update_entry(entry_id, self.read_json())
                    self.send_json(
                        {
                            "ok": True,
                            "entry": entry,
                            "backup_path": str(backup_path) if backup_path else "",
                        }
                    )
                    return
                if action == "delete":
                    entry, backup_path = set_deleted_status(entry_id, True)
                    self.send_json(
                        {
                            "ok": True,
                            "entry": entry,
                            "backup_path": str(backup_path) if backup_path else "",
                            "message": "词条已删除到回收站。",
                        }
                    )
                    return
                if action == "restore":
                    entry, backup_path = set_deleted_status(entry_id, False)
                    self.send_json(
                        {
                            "ok": True,
                            "entry": entry,
                            "backup_path": str(backup_path) if backup_path else "",
                            "message": "词条已恢复到词库。",
                        }
                    )
                    return
                if action == "purge":
                    entry, backup_path = purge_deleted_entry(entry_id)
                    self.send_json(
                        {
                            "ok": True,
                            "entry": entry,
                            "backup_path": str(backup_path) if backup_path else "",
                            "message": "词条已彻底删除。",
                        }
                    )
                    return
                if action == "review-status":
                    payload = self.read_json()
                    entry = update_review_status(entry_id, clean_text(payload.get("review_status")))
                    self.send_json(
                        {
                            "ok": True,
                            "entry": entry,
                            "message": f"复习状态已更新为：{entry['review_status']}",
                        }
                    )
                    return

            self.send_json({"ok": False, "error": "接口不存在。"}, status=404)
        except Exception as error:
            self.handle_error(error)

    def log_message(self, format, *args):
        safe_print("%s - %s" % (self.address_string(), format % args))


def build_server(host, start_port):
    last_error = None
    for port in range(start_port, start_port + 20):
        try:
            return ThreadingHTTPServer((host, port), GlossaryHandler), port
        except OSError as error:
            last_error = error
    raise RuntimeError(f"无法启动本地服务：{last_error}")


def run(host=HOST, port=DEFAULT_PORT, open_browser=True):
    initialize_database()
    server, actual_port = build_server(host, port)
    url = f"http://{host}:{actual_port}"

    safe_print("=" * 60)
    safe_print("项目质量英语词库管理器网页服务已启动")
    safe_print(f"数据库：{DB_PATH}")
    safe_print(f"访问地址：{url}")
    safe_print("按 Ctrl+C 可以停止服务。")
    safe_print("=" * 60)

    if open_browser:
        threading.Timer(0.6, webbrowser.open, args=(url,)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        safe_print()
        safe_print("网页服务已停止。")
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description="Start the local web UI for Quality Glossary Manager.")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    run(host=args.host, port=args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
