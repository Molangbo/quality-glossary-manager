# Quality Glossary Manager

中文名：项目质量英语词库管理器

这是一个本地命令行小程序，用于管理项目质量相关的中英文术语、汽车行业缩写、海外客户会议表达和日常英语词条。

它适合三个场景：

1. 项目质量英语学习
2. 海外客户会议英语
3. 日常英语背单词

当前项目同时支持命令行和本地网页界面。所有数据保存在本地 SQLite 数据库中，不需要联网。

## 项目结构

```text
quality_glossary/
├─ data/
│  └─ glossary.db
├─ backups/
│  └─ glossary_backup_YYYYMMDD_HHMMSS_before_edit.db
├─ exports/
│  └─ anki_cards.csv
├─ src/
│  ├─ main.py
│  ├─ database.py
│  ├─ glossary.py
│  ├─ review.py
│  ├─ export_anki.py
│  └─ test_data.py
├─ README.md
└─ requirements.txt
```

## 运行环境

需要 Python 3.8 或更高版本。

V0.1 只使用 Python 标准库，不需要安装第三方依赖。

## Windows 环境准备

如果你是第一次在 Windows 上运行 Python 项目，可以按下面步骤准备环境。

### 1. 检查是否已经安装 Python

打开 PowerShell 或命令提示符，输入：

```powershell
python --version
```

如果已经安装并且环境变量正常，会看到类似：

```text
Python 3.14.6
```

如果提示找不到 `python`，可以再试：

```powershell
py --version
```

如果 `python --version` 或 `py --version` 其中一个能显示版本号，说明 Python 可以使用。

如果两个命令都提示找不到，请先安装 Python。安装时建议勾选：

```text
Add python.exe to PATH
```

安装完成后，关闭当前 PowerShell，再重新打开一个新的 PowerShell 验证：

```powershell
python --version
```

### 2. 进入项目目录

如果你已经下载或克隆本项目，可以先进入项目目录。例如：

```powershell
D:\Projects\quality_glossary
```

进入项目目录：

```powershell
cd "D:\Projects\quality_glossary"
```

### 3. 创建虚拟环境

虚拟环境可以把当前项目的 Python 环境和电脑上的其他项目隔离开。虽然 V0.1 暂时不需要第三方库，但建议从一开始养成使用虚拟环境的习惯。

在项目目录中运行：

```powershell
python -m venv .venv
```

如果你的电脑只能使用 `py` 命令，则运行：

```powershell
py -m venv .venv
```

执行后，项目目录中会出现一个 `.venv` 文件夹。

### 4. 激活虚拟环境

在 PowerShell 中运行：

```powershell
.\.venv\Scripts\Activate.ps1
```

激活成功后，命令行前面通常会出现：

```text
(.venv)
```

如果 PowerShell 提示不允许执行脚本，可以在当前用户范围内执行一次：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

然后重新激活：

```powershell
.\.venv\Scripts\Activate.ps1
```

如果你使用的是传统命令提示符 CMD，则激活命令是：

```cmd
.venv\Scripts\activate.bat
```

### 5. 运行本项目

确认当前目录是项目根目录：

```powershell
cd "D:\Projects\quality_glossary"
```

然后运行：

```powershell
python src\main.py
```

如果你使用的是 `py` 命令：

```powershell
py src\main.py
```

启动后会看到命令行菜单，可以按数字选择功能。

### 6. 本项目的依赖说明

V0.1 尽量只使用 Python 标准库，不依赖复杂第三方库。

当前主要使用：

- `sqlite3`：本地数据库
- `csv`：导出 Anki CSV
- `datetime`：记录创建时间和更新时间
- `random`：复习模式随机抽题
- `pathlib`：处理文件路径

因此 V0.1 一般不需要运行 `pip install`。

## 如何运行

在命令行进入项目目录：

```bash
cd quality_glossary
```

运行：

```bash
python src/main.py
```

如果你的电脑上 Python 命令是 `python3`，则运行：

```bash
python3 src/main.py
```

如果 Windows 提示找不到 `python`，请先安装 Python，并在安装时勾选 `Add python.exe to PATH`。安装后重新打开命令行再运行。

如果命令行里的中文显示乱码，可以先在 Windows 命令行中执行：

```bash
chcp 65001
```

然后重新运行程序。

程序启动时会自动检查数据库：

- 如果 `data/glossary.db` 不存在，会自动创建。
- 如果数据库表不存在，会自动创建。
- 程序不会主动删除你的数据。

## 测试数据

V0.1 提供了一个测试数据脚本，可以一键写入几条项目质量常用词条，例如 PPAP、APQP、PSW、质量阀和客户投诉。

建议先预览：

```powershell
python src\test_data.py --dry-run
```

预览模式只显示将要新增和跳过的词条，不会修改数据库。

确认后再写入：

```powershell
python src\test_data.py
```

这个脚本只会新增缺失的测试词条。如果数据库中已经存在相同的缩写、英文名称或中文名称，会自动跳过，避免重复写入。它不会删除任何用户数据。

## 功能菜单

启动后会看到：

```text
1. 新增词条
2. 查看全部词条
3. 搜索词条
4. 按分类筛选词条
5. 按词条类型筛选词条
6. 修改词条
7. 删除词条
8. 查看回收站词条
9. 恢复回收站词条
10. 简单复习模式
11. 导出 Anki CSV
0. 退出
```

输入对应数字并按 Enter 即可使用。

## 新增词条

选择：

```text
1. 新增词条
```

按提示输入字段：

- 中文名称
- 英文名称
- 缩写
- 词条类型
- 分类
- 中文解释
- 例句
- 来源
- 备注
- 掌握程度

其中中文名称、英文名称、缩写至少填写一个。

分类可以填写多个，支持英文逗号和中文逗号，例如：

```text
APQP, PPAP, 海外会议表达
```

或：

```text
APQP，PPAP，海外会议表达
```

## 词条类型

当前固定支持以下类型：

1. 英文单词
2. 英文词组
3. 汽车行业缩写
4. 中文专业术语
5. 中英对照术语
6. 会议句式

## 掌握程度

当前固定支持：

1. 不熟
2. 学习中
3. 已掌握

新增词条时，如果直接按 Enter，默认是“不熟”。

## 搜索词条

选择：

```text
3. 搜索词条
```

可以输入：

- 中文关键词
- 英文关键词
- 缩写
- 解释中的关键词
- 分类关键词

例如：

```text
PPAP
```

或：

```text
生产件批准
```

## 按分类筛选

选择：

```text
4. 按分类筛选词条
```

输入分类关键词，例如：

```text
APQP
```

或：

```text
海外会议表达
```

## 按词条类型筛选

选择：

```text
5. 按词条类型筛选词条
```

然后按菜单选择词条类型。

## 修改词条

选择：

```text
6. 修改词条
```

使用方式：

1. 先输入要修改的词条 ID。
2. 程序会显示当前词条内容。
3. 逐项输入新内容。
4. 如果某个字段不需要修改，直接按 Enter 保留原值。
5. 如果要清空某个文本字段，输入 `清空`。
6. 修改完成后，程序会列出将要改变的字段。
7. 输入 `y` 确认保存，其他输入会取消保存。

修改保存前，程序会自动备份当前数据库。

## 数据库备份

V0.2 增加了自动备份功能。

使用“修改词条”并确认保存时，程序会先把当前数据库复制到：

```text
backups/
```

备份文件名示例：

```text
glossary_backup_20260624_183000_before_edit.db
```

这样即使修改时误操作，也可以保留修改前的数据库文件。程序不会主动删除备份文件。

## 简单复习模式

选择：

```text
10. 简单复习模式
```

程序会随机抽取词条并显示问题。

使用方式：

1. 先看问题。
2. 按 Enter 显示答案。
3. 根据记忆情况选择掌握程度：不熟 / 学习中 / 已掌握。
4. 输入 `q` 可以退出复习。

## 导出 Anki CSV

选择：

```text
11. 导出 Anki CSV
```

程序会导出：

```text
exports/anki_cards.csv
```

CSV 使用 UTF-8 with BOM 编码，方便 Windows 和 Excel 打开。

导出字段：

- `Front`
- `Back`

生成规则：

- `Front`：优先使用中文名称；如果中文名称为空，则使用缩写；如果缩写也为空，则使用英文名称。
- `Back`：包含英文、缩写、中文解释、例句、分类。

## 本地网页界面

V0.4 增加了本地网页界面，适合日常查询和维护词库。

启动方式一：双击项目根目录下的：

```text
start_web.bat
```

启动方式二：在项目根目录运行：

```powershell
python src\web_app.py
```

启动后浏览器会打开本地地址，通常是：

```text
http://127.0.0.1:8000
```

如果 8000 端口已经被占用，程序会自动尝试后续端口，例如 8001、8002。网页服务关闭后，浏览器再次访问会显示无法连接；重新运行启动命令即可。

网页界面支持：

- 查询、分类筛选、词条类型筛选
- 批量粘贴 ChatGPT 词条，解析预览后一次导入
- 分页浏览词条，每页可显示 10 / 20 / 50 条
- 新增词条
- 保存并新增，适合连续录入多个词条
- 修改词库中的词条
- 另存为新词条，适合基于相似词条快速复制新增
- 删除词条到回收站
- 查看回收站词条
- 恢复回收站词条
- 导出 Anki CSV
- 点击英文内容播放美音语音
- 同页复习模式：看中文选英文、看英文选中文、听音拼写
- 按英文、更新时间、分类、掌握程度或自定义排序号排序

网页界面和命令行共用同一个数据库：

```text
data/glossary.db
```

## 批量导入 ChatGPT 词条

网页界面支持把 ChatGPT 每日生成的多条词条一次性粘贴导入。

使用方式：

1. 点击网页顶部的“批量导入”。
2. 把 ChatGPT 输出的 1 到 10 条词条整体粘贴到文本框。
3. 点击“解析预览”。
4. 检查英文名称、缩写、中文名称、解释和例句是否正确。
5. 点击“导入全部”写入数据库。

导入前会自动识别以下标题格式：

```text
APQP (Advanced Product Quality Planning)
First Pass Yield (FPY)
Gauge R&R (Repeatability and Reproducibility)
```

识别规则：

- 缩写在前、全称在后时，自动把前半部分放入“缩写”，括号内容放入“英文名称”。
- 全称在前、缩写在后时，自动把括号内容放入“缩写”，前半部分放入“英文名称”。
- 类似 `Gauge R&R` 的行业术语会保留为英文名称和缩写，括号内容会写入备注。
- `Chinese Explanation` 或 `中文解释` 会写入中文解释。
- `Example Sentence` 会写入例句。
- `Meeting Phrases` 会写入备注。

批量导入默认掌握程度为“学习中”。如果英文、缩写或中文名称已经存在，预览中会提示重复，导入时默认跳过重复项。

## 网页复习模式

网页顶部提供“复习”入口，不会打开新的浏览器页面。点击后会在当前页面切换到复习面板，复习结束后可以返回词库。

复习模式支持：

- 看中文选英文：显示中文名称和中文解释，从英文选项中选择正确答案。
- 看英文选中文：显示英文名称或缩写，从中文选项中选择正确答案。
- 听音拼写：播放英文美音，输入听到的英文单词或词组。

每道题显示答案后，可以手动选择复习状态：

- 还要复习：复习状态设为“待复习”。
- 暂时会了：复习状态设为“已复习”。
- 已掌握：复习状态设为“已掌握”。

复习抽题默认只从“待复习”和“已复习”中抽取，不抽取“已掌握”和回收站词条。抽题权重为：

- 待复习：权重 5
- 已复习：权重 1
- 已掌握：权重 0

新增词条和批量导入词条默认：

```text
掌握程度 = 学习中
复习状态 = 待复习
```

## 词条排序

网页界面支持多种排序方式：

- 默认顺序：按创建顺序
- 英文 A-Z
- 英文 Z-A
- 最近更新
- 分类
- 掌握程度
- 自定义排序

如果想按自己的学习顺序排列，可以在右侧编辑区填写“自定义排序号”。数字越小越靠前；没有填写排序号的词条会排在已填写排序号的词条后面。

建议排序号预留间隔，例如：

```text
10, 20, 30, 40
```

这样以后想插入新词条时，可以填 `15` 或 `25`，不用重新调整全部词条。

## 英文美音播放

网页界面支持点击英文列旁边的播放按钮，生成并播放美音语音。右侧编辑区的英文名称输入框旁边也有播放按钮，方便新增或修改时试听。

语音文件会缓存到：

```text
exports/audio/
```

同一句英文、同一个声音再次播放时，会直接复用缓存的 mp3 文件，不会重复生成。

这个功能使用 `edge-tts` 生成音频。当前项目不会强制安装 `edge-tts`，如果没有安装，点击播放时网页会提示需要配置或安装。

方式一：在当前 Python 环境安装：

```powershell
pip install edge-tts
```

然后重新启动网页：

```powershell
python src\web_app.py
```

方式二：复用另一个 edge-tts 项目的虚拟环境。先把环境变量指向那个项目的 Python，例如：

```powershell
$env:QUALITY_GLOSSARY_EDGE_TTS_PYTHON="C:\path\to\edge-tts-project\.venv\Scripts\python.exe"
python src\web_app.py
```

默认语音参数为：

```text
VOICE = "en-US-AndrewNeural"
RATE = "-13%"
PITCH = "+1Hz"
VOLUME = "+0%"
```

如果想临时更换语音参数，可以设置：

```powershell
$env:QUALITY_GLOSSARY_TTS_VOICE="en-US-AriaNeural"
$env:QUALITY_GLOSSARY_TTS_RATE="-10%"
$env:QUALITY_GLOSSARY_TTS_PITCH="+0Hz"
$env:QUALITY_GLOSSARY_TTS_VOLUME="+0%"
python src\web_app.py
```

## 删除和恢复词条

V0.3 增加软删除功能。网页中的“删除”不会物理删除数据，只会把词条移入回收站，之后可以恢复。

网页回收站中还提供“彻底删除”。彻底删除会物理删除数据库记录，操作前会自动备份数据库；删除后只能通过备份文件找回。

命令行菜单：

```text
7. 删除词条
8. 查看回收站词条
9. 恢复回收站词条
```

默认情况下，以下功能只处理词库中的词条，不包含回收站词条：

- 查看全部词条
- 搜索词条
- 按分类筛选词条
- 按词条类型筛选词条
- 简单复习模式
- 导出 Anki CSV

删除、恢复、彻底删除、修改保存前都会自动备份数据库到：

```text
backups/
```

## 建议默认分类

分类可以自由输入。建议先从以下分类开始：

1. APQP
2. PPAP
3. OTS
4. PSW
5. 质量阀
6. EOL测试
7. FMEA
8. 8D / 5WHY
9. 图纸 / 尺寸 / 公差
10. 注塑 / 模具
11. 客户投诉
12. 海外会议表达
13. 日常英语
14. 其他

## 初学者建议

你可以先新增 3 到 5 条真实工作中会用到的词条，然后练习：

1. 查看全部词条
2. 用缩写搜索
3. 用中文搜索
4. 按分类筛选
5. 导出 Anki CSV

这样可以快速理解这个小程序的完整流程。
