# Paper Monitor

一个基于 **Crossref + SQLite + 静态 JSON + GitHub Pages** 的学术期刊最新论文监测系统。

系统按照 `config/journals.xlsx` 中维护的期刊清单逐刊访问 Crossref，获取近期新增记录，以 DOI 作为唯一标识保存历史数据，并自动生成前端所需的 JSON 文件。网页端支持 NEW 论文识别、分类/期刊/获取日期筛选、关键词检索、按日期或期刊顺序排序以及分页展示。

当前代码包的核心设计目标是：

- 使用一个统一数据源监测不同出版社期刊；
- 保留历史论文，避免每次运行只显示“本轮新论文”；
- 能够准确识别本轮新增 DOI；
- 期刊显示顺序与 Excel 中维护的顺序一致；
- 支持按系统实际获取日期回看论文；
- 可在本地运行，也可部署到 GitHub Pages；
- 对 Crossref 的临时连接失败、限流和服务器异常具有自动重试能力。

---

## 1. 当前项目结构

```text
paper-monitor/
│
├── index.html
├── README.md
├── update_and_push.bat
│
├── collectors/
│   ├── __init__.py
│   └── crossref.py
│
├── config/
│   ├── journals.xlsx
│   └── settings.yaml
│
├── core/
│   ├── __init__.py
│   └── database.py
│
├── database/
│   └── papers.db
│
├── logs/
│   └── failed_journals.json
│
├── scripts/
│   ├── __init__.py
│   ├── update.py
│   ├── generate_journal_order.py
│   └── rebuild_web_data.py
│
└── web/
    ├── app.js
    ├── style.css
    ├── papers.json
    ├── previous_papers.json
    ├── new_papers.json
    ├── update_time.json
    ├── journal_order.json
    └── README.md
```

其中：

- `index.html` 位于项目根目录，作为 GitHub Pages 的入口；
- CSS、JavaScript 和所有前端 JSON 数据统一放在 `web/` 下；
- SQLite 历史数据库保存在 `database/papers.db`；
- 每次运行的失败期刊记录在 `logs/failed_journals.json`。

---

## 2. 环境与依赖

推荐使用 Python 3.11 或更高版本。

主要 Python 依赖：

```bash
pip install requests pandas PyYAML openpyxl
```

其中：

- `requests`：访问 Crossref REST API；
- `pandas`：读取期刊 Excel；
- `PyYAML`：读取 `settings.yaml`；
- `openpyxl`：作为 pandas 读取 `.xlsx` 的引擎；
- `sqlite3`：Python 标准库，无需单独安装。

如果后续增加 `requirements.txt`，可写为：

```text
requests
pandas
PyYAML
openpyxl
```

---

## 3. 期刊配置：`config/journals.xlsx`

当前代码包中的 Excel 共有 137 个期刊记录。后续实际监测数量以 Excel 文件中的内容为准。

当前表格包含以下字段：

```text
Category
Order
Journal
pISSN
eISSN
URL
Note
Publisher
Source
API
```

程序实际使用的主要字段为：

```text
Journal
pISSN
Category
Publisher
```

### 3.1 ISSN

当前采集器主要使用：

```text
pISSN
```

向 Crossref 查询。

因此需要确保每个监测期刊的 `pISSN` 列有可用值。如果某个期刊只有 eISSN，可以将希望用于 Crossref 查询的 ISSN 填入当前程序读取的 `pISSN` 列。

如果 `pISSN` 为空，该期刊会被记录为失败：

```text
Missing pISSN
```

并写入：

```text
logs/failed_journals.json
```

### 3.2 期刊顺序

虽然 Excel 中存在 `Order` 列，但**当前代码并不读取 `Order` 字段来决定前端顺序**。

期刊顺序由：

> `journals.xlsx` 中期刊实际出现的行顺序

决定。

例如 Excel 中：

```text
Applied Soft Computing
Computers & Industrial Engineering
Computers & Operations Research
European Journal of Operational Research
...
```

则前端期刊排序也按照这一顺序。

该顺序会独立生成到：

```text
web/journal_order.json
```

示例：

```json
{
  "Applied Soft Computing": 1,
  "Computers & Industrial Engineering": 2,
  "Computers & Operations Research": 3
}
```

`journal_order` 不写入每一篇论文，因此 `papers.json` 保持简洁。

---

## 4. 基本配置：`config/settings.yaml`

当前配置为：

```yaml
days: 1
rows: 50
timezone: Asia/Shanghai
```

### `days`

控制 Crossref 查询的 metadata-created 时间窗口。

当前采集器使用：

```python
from-created-date
```

并计算：

```text
当前 UTC 日期 - days
```

例如：

```yaml
days: 1
```

表示从前一天的 UTC 日期开始查询 Crossref 中新创建/更新的记录。

需要特别注意：

> `from-created-date` 是 Crossref 元数据创建日期过滤条件，不等同于论文正式 Online Publication Date。

因此即使设置 `days: 1`，论文的 `online_date` 也可能早于查询日期。

### `rows`

表示每个期刊单次最多返回多少条 Crossref 记录。

当前：

```yaml
rows: 50
```

即每个期刊最多取 50 条。

### `timezone`

配置文件目前保留：

```yaml
timezone: Asia/Shanghai
```

但当前 `update.py` 实际采用固定的：

```text
GMT+8
```

生成系统获取日期和更新时间，并没有动态读取该 `timezone` 值。

---

## 5. Crossref 数据获取

核心采集程序：

```text
collectors/crossref.py
```

调用：

```text
https://api.crossref.org/journals/{issn}/works
```

基本参数：

```python
{
    "rows": rows,
    "sort": "created",
    "order": "desc",
    "filter": f"from-created-date:{start}"
}
```

---

## 6. Crossref 稳定访问与自动重试

为避免连续访问大量期刊时出现：

```text
ConnectionResetError(10054)
```

或临时网络异常，当前 `crossref.py` 已增加稳健访问机制。

### 6.1 请求间隔

连续 Crossref 请求之间至少间隔约：

```text
0.6 秒
```

程序使用一个共享的：

```python
requests.Session()
```

复用 TCP 连接。

### 6.2 自动重试

首次失败后最多再重试 3 次。

默认退避时间约为：

```text
2 秒
5 秒
10 秒
```

并加入少量随机等待，避免所有请求以完全相同的节奏重复发送。

### 6.3 自动重试的异常

包括：

```text
ConnectionError
Timeout
ChunkedEncodingError
```

### 6.4 自动重试的 HTTP 状态码

包括：

```text
429
500
502
503
504
```

如果 Crossref 返回：

```text
Retry-After
```

程序会优先按照服务器建议的时间等待。

因此出现临时连接重置时，命令行可能看到：

```text
Crossref connection error (ConnectionError);
retrying in 2.5s...
```

只要后续重试成功，该期刊最终仍会显示：

```text
Status: OK
```

---

## 7. 设置 Crossref 联系邮箱

建议设置 Crossref 联系邮箱。程序会自动将其加入：

```text
mailto
```

参数和：

```text
User-Agent
```

中。

环境变量名称：

```text
CROSSREF_MAILTO
```

### 7.1 PowerShell 临时设置

```powershell
$env:CROSSREF_MAILTO="your_email@example.com"
python scripts/update.py
```

只对当前 PowerShell 窗口有效。

### 7.2 Windows 永久设置

```powershell
setx CROSSREF_MAILTO "your_email@example.com"
```

执行后关闭当前 PowerShell，再重新打开。

检查：

```powershell
echo $env:CROSSREF_MAILTO
```

### 7.3 GitHub Actions

建议不要把邮箱直接写入公开代码，而是建立 Repository Secret：

```text
Settings
→ Secrets and variables
→ Actions
→ New repository secret
```

名称：

```text
CROSSREF_MAILTO
```

然后在 workflow 中使用：

```yaml
env:
  CROSSREF_MAILTO: ${{ secrets.CROSSREF_MAILTO }}
```

---

## 8. 论文日期的处理

系统区分两个日期：

```text
Online Date
Fetched Date
```

### 8.1 Online Date

Crossref 中的出版日期按以下顺序选择：

```text
published-online
→ published-print
→ issued
→ published
```

如果 Crossref 的出版日期只提供到“年”或“年月”，而 `created.date-time` 有完整日期，程序会使用 Crossref created date 作为较完整的显示日期。

最终前端通常显示：

```text
Online: YYYY-MM-DD
```

### 8.2 Fetched Date

`fetched_date` 表示：

> 系统第一次发现并保存该 DOI 的日期。

新论文的获取日期统一按照：

```text
GMT+8
```

生成。

前端显示：

```text
Fetched (GMT+8): YYYY-MM-DD
```

数据库中的对应字段名为：

```text
first_seen
```

JSON 输出时转换为：

```text
fetched_date
```

---

## 9. SQLite 历史数据库

数据库文件：

```text
database/papers.db
```

当前表结构：

```sql
CREATE TABLE papers(
    doi TEXT PRIMARY KEY,
    title TEXT,
    authors TEXT,
    journal TEXT,
    category TEXT,
    publisher TEXT,
    online_date TEXT,
    first_seen TEXT
)
```

其中 DOI 是主键。

因此同一个 DOI 不会重复写入数据库。

数据库的作用非常重要：

- 保存所有历史论文；
- 判断一个 DOI 是否已经获取过；
- 支持前端长期显示历史数据；
- 保证 GitHub Actions 每次运行时仍然知道过去已经抓取了哪些论文。

如果使用 GitHub Actions 自动更新，需要把：

```text
database/papers.db
```

一起提交回仓库，否则下一次 Action 从干净仓库启动时会失去历史状态。

---

## 10. NEW 论文识别机制

每次运行 `scripts/update.py` 时，程序首先读取当前数据库，并在抓取新数据**之前**生成：

```text
web/previous_papers.json
```

它代表：

> 本轮更新开始之前数据库中已经存在的论文。

随后访问 Crossref，将新的 DOI 写入数据库。

本轮新发现的论文还会单独写入：

```text
web/new_papers.json
```

最终前端通过：

```text
papers.json
```

与：

```text
previous_papers.json
```

比较 DOI。

如果某篇论文 DOI 不在 `previous_papers.json` 中，则前端显示：

```text
NEW
```

因此：

- NEW 表示“本轮更新新增”；
- 刷新浏览器不会改变 NEW；
- 下一次 `update.py` 运行后，上一次新增论文会进入新的 `previous_papers.json`，NEW 标签随之消失；
- 本轮新 DOI 会成为新的 NEW。

---

## 11. Web JSON 文件说明

### `web/papers.json`

所有数据库论文的前端导出文件。

字段：

```json
{
  "doi": "...",
  "title": "...",
  "authors": "...",
  "journal": "...",
  "category": "...",
  "publisher": "...",
  "online_date": "YYYY-MM-DD",
  "fetched_date": "YYYY-MM-DD"
}
```

### `web/previous_papers.json`

本轮更新开始之前的数据库快照。

主要用于前端判断 NEW。

### `web/new_papers.json`

本轮更新真正新增到数据库中的论文。

主要用于记录与调试；当前网页的 NEW 判定主要使用 `previous_papers.json`。

### `web/update_time.json`

示例：

```json
{
  "updated": "2026-08-21 09:33:52",
  "timezone": "UTC+8",
  "count": 1
}
```

保存：

- 最近一次更新时间；
- 时区；
- 本轮新增论文数量。

### `web/journal_order.json`

保存 Excel 行顺序对应的期刊排序。

---

## 12. 前端功能

入口：

```text
index.html
```

前端脚本：

```text
web/app.js
```

样式：

```text
web/style.css
```

### 12.1 页面布局

当前采用蓝色、紧凑、学术化风格。

论文卡片显示：

```text
Paper Title                         NEW

Journal Name

Full Author Names

Online: YYYY-MM-DD | Fetched (GMT+8): YYYY-MM-DD
DOI: ...
```

主要字体设置：

- 页面正文：15px；
- 页面标题：31px；
- 论文标题：18px；
- 期刊名称：14.5px；
- 作者：14.5px；
- 日期/DOI：13.5px。

### 12.2 作者显示

当前 Crossref 采集器将作者按：

```text
Given Name + Family Name
```

拼接，并尽量显示全部作者。

作者之间使用：

```text
;
```

分隔。

不主动使用：

```text
et al.
```

历史数据库中较早采集的数据可能保留旧格式。

### 12.3 DOI

DOI 可点击并跳转到：

```text
https://doi.org/{DOI}
```

---

## 13. 前端检索与筛选

顶部工具栏包括：

```text
Search
Category
Journal
All Papers / NEW Only
Fetch Date
Sort
```

### Search

可以检索：

```text
Title
Author
DOI
Journal
```

### Category

按 Excel 中的 `Category` 筛选。

### Journal

期刊下拉框会随 Category 联动。

例如选定某一 Category 后，只显示该分类下的期刊。

期刊下拉框本身按照：

```text
journal_order.json
```

排序。

### All Papers / NEW Only

```text
All Papers
NEW Only
```

其中：

- `All Papers`：显示全部符合条件的论文；
- `NEW Only`：只显示本轮新增论文。

### Fetch Date

根据：

```text
fetched_date
```

筛选。

获取日期按 GMT+8 生成，日期选项默认从新到旧排列。

---

## 14. 前端排序规则

无论选择哪种排序方式：

> NEW 论文始终优先于旧论文。

### 14.1 Sort by Date

排序规则：

```text
1. NEW 优先
2. Online Date 从新到旧
3. 日期相同时按照 Excel 期刊顺序
4. 标题
```

### 14.2 Sort by Journal

排序规则：

```text
1. NEW 优先
2. 按 journals.xlsx 实际行顺序
3. 同一期刊内部按 Online Date 从新到旧
```

---

## 15. 前端显示数量与分页

当前 `web/app.js` 配置：

```javascript
const PAGE_SIZE = 50;
const MAX_ITEMS = 1000;
```

因此：

```text
最多进入前端结果集：1000 条
每页显示：50 条
```

筛选和排序完成后，再截取最多 1000 条。

分页示例：

```text
Previous   1   2   3   …   8   Next

              Page 2 / 8
```

页数较多时会自动加入省略号。

---

## 16. 本地更新

在项目根目录运行：

```bash
python scripts/update.py
```

命令行会逐期刊显示状态，例如：

```text
========================================================================
Paper Monitor
Mode: INCREMENTAL
Journals: 137
Days: 1
Rows: 50
========================================================================

[1/137] Applied Soft Computing
  ISSN: 1568-4946
  Fetched: 5
  New: 1
  Status: OK
```

更新完成后会输出：

```text
Successful journals
Failed journals
Fetched papers
New papers
Total stored papers
Fetched date
Update time
```

失败详情保存在：

```text
logs/failed_journals.json
```

---

## 17. 本地查看网页

由于前端使用 `fetch()` 读取 JSON，不建议直接双击：

```text
index.html
```

使用 `file://` 打开可能因为浏览器安全策略无法加载 JSON。

建议在项目根目录运行：

```bash
python -m http.server 8000
```

然后浏览：

```text
http://localhost:8000/
```

---

## 18. GitHub Pages 部署

`index.html` 位于仓库根目录，因此适合直接使用 GitHub Pages：

```text
Deploy from branch
```

并将发布目录设为仓库根目录。

页面入口类似：

```text
https://<username>.github.io/<repository>/
```

因为入口文件在根目录，前端资源使用：

```html
<link rel="stylesheet" href="web/style.css">
<script src="web/app.js"></script>
```

JSON 路径为：

```javascript
fetch("web/papers.json")
fetch("web/previous_papers.json")
fetch("web/update_time.json")
fetch("web/journal_order.json")
```

---

## 19. 每天北京时间 07:30 自动更新

GitHub Actions 的 cron 使用 UTC。

北京时间：

```text
GMT+8 / UTC+8
```

因此北京时间每天：

```text
07:30
```

对应 UTC：

```text
23:30（前一天）
```

cron：

```yaml
- cron: '30 23 * * *'
```

推荐 workflow 示例：

```yaml
name: update

on:
  schedule:
    - cron: '30 23 * * *'
  workflow_dispatch:

jobs:
  update:
    runs-on: ubuntu-latest

    permissions:
      contents: write

    env:
      CROSSREF_MAILTO: ${{ secrets.CROSSREF_MAILTO }}

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install requests pandas PyYAML openpyxl

      - name: Update papers
        run: python scripts/update.py

      - name: Commit changes
        run: |
          git config --global user.name "github-actions"
          git config --global user.email "github-actions@github.com"

          git add web/
          git add database/
          git add logs/

          git commit -m "Update papers automatically" || echo "No changes"
          git push
```

GitHub Actions 的定时任务不保证精确到分钟，07:30 的任务可能在 07:30 之后几分钟实际开始，这是正常现象。

---

## 20. Windows 一键更新与 Git Push

项目包含：

```text
update_and_push.bat
```

其工作流程为：

```text
运行 update.py
→ 检查 Git 状态
→ git add 数据文件
→ git commit
→ git push
```

可直接双击运行，也可在命令行执行：

```powershell
.\update_and_push.bat
```

### 关于 journal_order.json

当前批处理文件显式 `git add` 的主要文件包括：

```text
papers.json
new_papers.json
previous_papers.json
update_time.json
papers.db
logs/
```

如果你修改了：

```text
config/journals.xlsx
```

中的期刊顺序，并重新生成了：

```text
web/journal_order.json
```

建议同时提交：

```bash
git add web/journal_order.json
```

更稳妥的做法是将批处理中的 `git add` 修改为：

```bat
git add web\papers.json web\new_papers.json web\previous_papers.json web\update_time.json web\journal_order.json database\papers.db logs\
```

如果 Excel 本身也进行了修改，还应提交：

```bat
git add config\journals.xlsx
```

---

## 21. 自动邮件推送功能

Paper Monitor 支持在完成论文更新后，自动生成 HTML 格式的论文摘要邮件，并通过 Gmail SMTP 将本轮新增论文发送至指定邮箱。

当前邮件模块不仅支持自动发送，还支持：

- 每次生成的 HTML 邮件独立归档；
- 同一天多次运行自动区分；
- 邮件标题自动加入日期、时间和运行标识；
- 自动保留最近 30 天的邮件 HTML；
- 自动删除超过 30 天的历史 HTML；
- 使用 `latest_email.json` 精确记录本轮需要发送的邮件；
- 无新增论文时自动跳过邮件生成和发送，避免重复发送历史邮件。

完整流程如下：

```text
Crossref
   |
   v
scripts/update.py
   |
   v
更新 SQLite 数据库
   |
   +---- web/new_papers.json
   |
   +---- web/update_time.json
   |
   v
scripts/generate_email.py
   |
   +---- 生成本轮 HTML 邮件
   |
   +---- 生成 latest_email.json
   |
   +---- 清理超过 30 天的旧 HTML
   |
   v
scripts/send_email.py
   |
   +---- 检查 new_papers.json
   |
   +---- 读取 latest_email.json
   |
   +---- 精确定位本轮 HTML
   |
   v
Gmail SMTP
   |
   v
接收论文提醒邮件
```

---

### 21.1 邮件功能特点

当前邮件模块支持：

- 自动生成每日论文提醒；
- 只发送本轮新增论文；
- HTML 响应式邮件布局；
- 支持 PC 和手机端显示；
- 按期刊分组展示论文；
- 论文标题支持点击 DOI 链接跳转；
- 显示完整作者列表；
- 显示 GMT+8 更新时间；
- 支持自定义发件人名称；
- 支持历史 HTML 邮件归档；
- 支持同日多次运行区分；
- 支持超过 30 天的历史邮件自动清理。

当前邮件主要展示：

```text
Paper Monitor

Daily New Papers Digest

Update time:
YYYY-MM-DD HH:MM:SS (GMT+8)

XX new papers found.


Journal Name


Paper Title
（点击标题进入论文页面）

Authors:
Author 1; Author 2; ...
```

为了提高阅读效率，当前邮件中不显示：

- DOI 文本；
- DOI 按钮；
- Online Date；
- Fetched Date。

论文 DOI 仍然保留在标题超链接中。

---

### 21.2 邮件生成程序

邮件 HTML 由：

```text
scripts/generate_email.py
```

生成。

程序主要读取：

```text
web/new_papers.json
web/journal_order.json
web/update_time.json
```

其中：

- `new_papers.json`：本轮新增论文；
- `journal_order.json`：期刊显示顺序；
- `update_time.json`：本轮更新时间。

如果：

```text
web/new_papers.json
```

为空，则程序直接退出：

```text
No new papers. Skip email generation.
```

不会生成新的 HTML 邮件。

---

### 21.3 HTML 邮件归档

早期版本每次固定生成：

```text
web/daily_papers_email.html
```

因此新邮件会覆盖旧邮件。

当前版本改为按：

```text
日期 + 时间
```

生成独立文件。

例如：

```text
web/daily_papers_email_2026-08-22_073152.html
```

其中：

```text
2026-08-22
```

表示日期，

```text
073152
```

表示：

```text
07:31:52
```

因此同一天多次运行，例如：

```text
daily_papers_email_2026-08-22_073152.html
daily_papers_email_2026-08-22_121426.html
daily_papers_email_2026-08-22_183015.html
```

会分别保存，不会互相覆盖。

---

### 21.4 同一秒重复运行的处理

极端情况下，如果同一秒内再次生成邮件，而对应 HTML 文件已经存在，则系统会自动增加序号。

例如：

```text
daily_papers_email_2026-08-22_121426.html
daily_papers_email_2026-08-22_121426_02.html
daily_papers_email_2026-08-22_121426_03.html
```

因此即使运行时间完全相同，也不会直接覆盖已有 HTML。

对应运行标识分别为：

```text
121426
121426-02
121426-03
```

---

### 21.5 `latest_email.json`

每次成功生成 HTML 后，程序还会生成：

```text
web/latest_email.json
```

该文件记录**本轮最新生成邮件**的信息。

例如：

```json
{
  "html_file": "daily_papers_email_2026-08-22_160125.html",
  "subject": "[Paper Monitor] 2026-08-22 16:01 · 18 New Papers · #160125",
  "run_id": "160125",
  "run_time": "2026-08-22 16:01:25",
  "timezone": "GMT+8",
  "paper_count": 18
}
```

字段说明：

```text
html_file
```

表示本轮需要发送的 HTML 文件；

```text
subject
```

表示本轮邮件标题；

```text
run_id
```

表示本轮运行标识；

```text
run_time
```

表示本轮运行时间；

```text
paper_count
```

表示本轮新增论文数量。

`send_email.py` 不再通过文件修改时间等方式猜测最新 HTML，而是直接读取：

```text
latest_email.json
```

因此能够精确发送本轮生成的邮件。

---

### 21.6 历史 HTML 自动清理

邮件 HTML 会暂时保留在：

```text
web/
```

目录中。

为了避免长期运行后积累过多文件，`generate_email.py` 每次运行时会自动删除：

> 超过 30 天的历史邮件 HTML。

例如当前日期为：

```text
2026-08-22
```

则：

```text
2026-07-23 ～ 2026-08-22
```

范围内的 HTML 保留。

而：

```text
2026-07-22
```

及更早的邮件 HTML 会被自动删除。

删除规则只针对符合以下命名格式的邮件文件：

```text
daily_papers_email_YYYY-MM-DD.html

daily_papers_email_YYYY-MM-DD_HHMMSS.html

daily_papers_email_YYYY-MM-DD_HHMMSS_02.html
```

其他 HTML 文件不会被该清理逻辑删除。

当前保留周期：

```python
keep_days=30
```

如以后希望保留 60 天，可修改为：

```python
keep_days=60
```

---

### 21.7 邮件发送程序

邮件发送程序：

```text
scripts/send_email.py
```

主要使用以下环境变量：

```text
MAIL_USERNAME
MAIL_PASSWORD
MAIL_TO
```

其中：

- `MAIL_USERNAME`：发送邮箱；
- `MAIL_PASSWORD`：Google App Password；
- `MAIL_TO`：接收邮箱。

当前程序发送前首先检查：

```text
web/new_papers.json
```

如果没有新增论文，则输出：

```text
No new papers. Skip sending email.
```

并停止发送。

这样可以避免：

```text
generate_email.py
```

因为没有新增论文而退出后，

```text
send_email.py
```

错误发送上一轮遗留的 HTML 邮件。

---

### 21.8 本轮邮件定位机制

`send_email.py` 读取：

```text
web/latest_email.json
```

获取：

```text
html_file
```

例如：

```json
"html_file": "daily_papers_email_2026-08-22_160125.html"
```

程序随后读取：

```text
web/daily_papers_email_2026-08-22_160125.html
```

作为本轮邮件正文。

因此完整关系为：

```text
generate_email.py
      |
      v
daily_papers_email_2026-08-22_160125.html
      |
      +---- latest_email.json
                    |
                    v
             send_email.py
                    |
                    v
               Gmail SMTP
```

这种方式可以避免同一天存在多个 HTML 时发送错误文件。

---

### 21.9 个性化邮件标题

早期版本邮件标题固定为：

```text
[Paper Monitor] Daily New Papers
```

当前版本会自动加入：

- 日期；
- 时间；
- 新增论文数量；
- 本轮运行标识。

例如：

```text
[Paper Monitor] 2026-08-22 16:01 · 18 New Papers · #160125
```

如果只有 1 篇新论文：

```text
[Paper Monitor] 2026-08-22 16:01 · 1 New Paper · #160125
```

如果同一秒第二次生成，则可能为：

```text
[Paper Monitor] 2026-08-22 16:01 · 18 New Papers · #160125-02
```

这样可以直接从邮箱标题判断：

```text
哪一天
+
几点更新
+
新增多少篇
+
属于哪一次运行
```

---

### 21.10 自定义发件人名称

当前发送程序使用：

```python
msg["From"] = formataddr(
    ("Paper Monitor", username)
)
```

因此邮件发送方显示为：

```text
Paper Monitor
```

而不是单独显示 Gmail 邮箱地址。

如果以后希望修改为：

```text
Paper Monitor | Zhen Zhang
```

可以改为：

```python
msg["From"] = formataddr(
    ("Paper Monitor | Zhen Zhang", username)
)
```

---

### 21.11 Gmail App Password

Gmail SMTP 建议使用 Google App Password，而不是账户登录密码。

配置路径：

```text
Google Account
        ↓
Security
        ↓
2-Step Verification
        ↓
App Passwords
```

生成应用密码后，将其保存为 GitHub Repository Secret：

```text
MAIL_PASSWORD
```

---

### 21.12 GitHub Secrets

GitHub 仓库进入：

```text
Settings
        ↓
Secrets and variables
        ↓
Actions
        ↓
New repository secret
```

需要配置：

```text
CROSSREF_MAILTO
MAIL_USERNAME
MAIL_PASSWORD
MAIL_TO
```

分别用于：

```text
CROSSREF_MAILTO
= Crossref API 联系邮箱

MAIL_USERNAME
= Gmail SMTP 发送账号

MAIL_PASSWORD
= Gmail App Password

MAIL_TO
= 邮件接收地址
```

这些信息不要直接写入公开代码。

---

### 21.13 GitHub Actions 邮件流程

自动任务推荐按照以下顺序执行：

```yaml
- name: Update papers
  run: python paper-monitor/scripts/update.py

- name: Generate email
  run: python paper-monitor/scripts/generate_email.py

- name: Send email
  run: python paper-monitor/scripts/send_email.py
```

完整逻辑：

```text
update.py
   |
   +---- 更新数据库
   +---- 生成 new_papers.json
   |
   v
generate_email.py
   |
   +---- 如果没有 NEW → 退出
   |
   +---- 生成唯一 HTML
   +---- 生成 latest_email.json
   +---- 删除超过30天的HTML
   |
   v
send_email.py
   |
   +---- 再次检查 new_papers.json
   |
   +---- 读取 latest_email.json
   |
   +---- 读取本轮 HTML
   |
   v
Gmail SMTP
```

---

### 21.14 邮件相关文件

当前 `web/` 目录中与邮件有关的文件包括：

```text
web/
├── new_papers.json
├── update_time.json
├── journal_order.json
├── latest_email.json
├── daily_papers_email_2026-08-22_073152.html
├── daily_papers_email_2026-08-22_121426.html
└── ...
```

其中：

```text
latest_email.json
```

会在下一次成功生成邮件时覆盖，因为它只负责指向“当前最新一轮邮件”。

而：

```text
daily_papers_email_*.html
```

作为历史邮件归档，30 天内不会覆盖或删除。

---

## 22. 辅助脚本

日常更新的核心程序为：

```text
scripts/update.py
```

邮件相关程序为：

```text
scripts/generate_email.py
scripts/send_email.py
```

此外还有两个辅助工具。

---

### 22.1 `generate_journal_order.py`

运行：

```bash
python scripts/generate_journal_order.py
```

功能：

```text
config/journals.xlsx
        ↓
web/journal_order.json
```

适用于：

- 修改 Excel 中期刊顺序；
- 不需要访问 Crossref；
- 不需要更新数据库；
- 只需要重新生成前端期刊顺序。

---

### 22.2 `rebuild_web_data.py`

运行：

```bash
python scripts/rebuild_web_data.py
```

功能：

```text
database/papers.db
        ↓
web/papers.json
```

以及：

```text
config/journals.xlsx
        ↓
web/journal_order.json
```

它不会访问 Crossref。

适用于：

- 已有完整 `papers.db`；
- JSON 文件被删除；
- 需要重新导出网页数据；
- 需要恢复 `fetched_date`；
- 不希望重新访问 Crossref。

---

## 23. 一次完整更新的工作流程

当前完整工作流程为：

```text
config/journals.xlsx
        |
        +---- 生成 journal_order.json
        |
        v
database/papers.db
        |
        +---- 更新前导出 previous_papers.json
        |
        v
逐期刊访问 Crossref
        |
        +---- 已存在 DOI → 跳过
        |
        +---- 新 DOI
        |        |
        |        +---- 写入 papers.db
        |        +---- first_seen = GMT+8
        |        +---- 加入 new_papers.json
        |
        v
导出 papers.json
        |
        +---- 更新 update_time.json
        +---- 写入 failed_journals.json
        |
        v
generate_email.py
        |
        +---- 无新增论文 → 跳过
        |
        +---- 有新增论文
                |
                +---- 生成唯一 HTML
                |
                +---- 生成 latest_email.json
                |
                +---- 清理超过 30 天的 HTML
        |
        v
send_email.py
        |
        +---- 再次检查 NEW
        +---- 读取 latest_email.json
        +---- 发送本轮 HTML
        |
        v
Gmail SMTP
        |
        v
GitHub Pages / Email
```

---

## 24. 常见问题

### 24.1 网页没有显示论文

不要直接双击：

```text
index.html
```

建议运行：

```bash
python -m http.server 8000
```

然后访问：

```text
http://localhost:8000/
```

检查：

```text
web/papers.json
web/previous_papers.json
web/update_time.json
web/journal_order.json
```

是否存在且为合法 JSON。

---

### 24.2 修改 CSS 或 JavaScript 后页面没有变化

可能是浏览器或 GitHub Pages 缓存。

可以修改：

```text
style.css?v=xxx
app.js?v=xxx
```

中的版本号。

例如：

```text
?v=15.0
```

然后强制刷新：

```text
Ctrl + F5
```

---

### 24.3 Crossref 出现 `ConnectionResetError 10054`

例如：

```text
ConnectionResetError(
    10054,
    '远程主机强迫关闭了一个现有的连接。'
)
```

当前 Crossref 采集器会自动：

```text
请求限速
   ↓
自动重试
   ↓
退避等待
   ↓
重新请求
```

最终仍然失败的期刊记录在：

```text
logs/failed_journals.json
```

下一次更新可以再次尝试。

---

### 24.4 NEW 标签为什么下一次更新后消失

NEW 表示：

> 相对于本轮更新之前数据库快照新增的 DOI。

下一次运行后，上一次新增论文已经属于历史数据库，因此不再属于本轮 NEW。

这是正常行为。

---

### 24.5 Online Date 与 Fetched Date 为什么不同

二者含义不同：

```text
Online Date
=
Crossref 提供的出版/在线日期
```

```text
Fetched Date
=
Paper Monitor 第一次发现该 DOI 的日期
```

例如：

```text
Online: 2026-08-18

Fetched: 2026-08-22
```

属于正常情况。

---

### 24.6 为什么没有收到邮件

首先检查：

```text
web/new_papers.json
```

如果内容为空：

```json
[]
```

则程序不会生成或发送邮件。

这是预期行为。

如果存在新增论文，再检查：

```text
web/latest_email.json
```

是否存在。

然后检查其中：

```text
html_file
```

对应的 HTML 是否存在于：

```text
web/
```

最后检查 GitHub Actions 是否出现：

```text
Email sent successfully.
```

---

### 24.7 为什么 `latest_email.json` 存在，但邮件没有发送

检查：

```text
MAIL_USERNAME
MAIL_PASSWORD
MAIL_TO
```

是否正确配置。

常见 SMTP 错误：

```text
SMTPAuthenticationError
```

通常与：

- Gmail App Password 错误；
- 使用了普通 Gmail 登录密码；
- Secret 未正确配置；

有关。

---

### 24.8 为什么每天有多个 HTML

这是当前版本的正常设计。

例如：

```text
daily_papers_email_2026-08-22_073152.html
daily_papers_email_2026-08-22_121426.html
```

表示 8 月 22 日分别在：

```text
07:31:52
12:14:26
```

执行过两次有效邮件生成。

系统故意不覆盖这些 HTML，以便保留短期历史记录。

---

### 24.9 为什么旧 HTML 自动消失

系统默认只保留最近：

```text
30 天
```

超过 30 天的：

```text
daily_papers_email_*.html
```

会在下一次成功生成邮件时自动删除。

这是为了避免 GitHub 仓库长期积累大量历史 HTML 文件。

---

### 24.10 如何修改历史邮件保留时间

在：

```text
scripts/generate_email.py
```

找到：

```python
cleanup_old_email_files(
    reference_dt=run_dt,
    keep_days=30
)
```

例如希望保留 60 天：

```python
cleanup_old_email_files(
    reference_dt=run_dt,
    keep_days=60
)
```

---

## 25. 建议的日常使用方式

如果主要使用 GitHub Actions：

```text
每天 07:30 GMT+8
        ↓
GitHub Actions
        ↓
update.py
        ↓
更新 DB + JSON
        ↓
generate_email.py
        ↓
生成本轮邮件 HTML
        ↓
生成 latest_email.json
        ↓
清理超过 30 天的 HTML
        ↓
send_email.py
        ↓
发送邮件
        ↓
git commit / push
        ↓
GitHub Pages 更新
```

如果本轮没有新增论文：

```text
update.py
        ↓
new_papers.json = []
        ↓
generate_email.py 跳过
        ↓
send_email.py 跳过
```

因此不会重复发送上一轮邮件。

---

### 本地手动更新

运行：

```bash
python scripts/update.py
```

然后：

```bash
python scripts/generate_email.py
```

如果需要测试实际邮件发送：

```bash
python scripts/send_email.py
```

本地发送前必须正确设置：

```text
MAIL_USERNAME
MAIL_PASSWORD
MAIL_TO
```

---

### 本地查看网页

运行：

```bash
python -m http.server 8000
```

访问：

```text
http://localhost:8000/
```

---

### 只修改期刊顺序

运行：

```bash
python scripts/generate_journal_order.py
```

---

### 只重建网页数据

运行：

```bash
python scripts/rebuild_web_data.py
```

---

## 26. Git 使用建议

建议 `.gitignore` 至少包含：

```text
.idea/
__pycache__/
*.pyc
```

不要在公开代码中保存：

```text
Gmail Password
Gmail App Password
GitHub Token
API Secret
```

应使用：

```text
环境变量
```

或：

```text
GitHub Repository Secrets
```

注入。

由于当前历史邮件 HTML 会保留最近 30 天，如果 workflow 使用：

```bash
git add paper-monitor
```

这些 HTML 文件以及：

```text
web/latest_email.json
```

会一起提交到仓库。

当超过 30 天的 HTML 被程序删除后，Git 也会检测到对应删除操作，并在下一次 commit 时同步删除远程仓库中的旧文件。

---

## 27. 当前系统的关键设计原则

当前 Paper Monitor 采用以下方案：

```text
统一数据源：
Crossref


论文唯一键：
DOI


历史存储：
SQLite


NEW 判定：
previous_papers.json
与当前 papers.json 的 DOI 差集


期刊顺序：
journals.xlsx 的实际行顺序


获取日期：
第一次发现 DOI 的 GMT+8 日期


网页入口：
index.html


网页数据：
web/*.json


前端 NEW：
本轮更新新增 DOI


邮件数据：
web/new_papers.json


邮件 HTML：
daily_papers_email_YYYY-MM-DD_HHMMSS.html


同秒重复：
自动增加 _02、_03……


当前邮件指针：
web/latest_email.json


邮件发送：
Gmail SMTP


邮件标题：
日期 + 时间 + 新增数量 + Run ID


历史邮件：
保留最近 30 天


无新增论文：
不生成邮件
不发送邮件


自动更新时间：
建议北京时间每天 07:30
```

当前整体数据流：

```text
Crossref
   ↓
SQLite
   ↓
JSON
   ├──── Web
   │
   └──── Email
           ↓
      HTML Archive
           ↓
     latest_email.json
           ↓
       Gmail SMTP
```

---

## 28. Copyright

```text
Copyright © 2026 Zhen Zhang, Dalian University of Technology
```