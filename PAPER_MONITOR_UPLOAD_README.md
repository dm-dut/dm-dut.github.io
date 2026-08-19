# Paper Monitor — dm-dut.github.io 最终修正版

本压缩包用于**直接合并上传到现有 `dm-dut.github.io` 仓库根目录**。它不包含根目录 `index.html`，不会覆盖你的个人主页。

## 上传后结构

```text
<dm-dut.github.io>/
├── index.html                         # 你原有主页，本包不包含
├── ...                                # 你原有内容，不修改
├── paper-monitor/                     # 新增：网页
│   ├── index.html
│   ├── app.js
│   ├── config.js
│   ├── style.css
│   └── data/online_papers.json
├── paper_monitor_system/              # 新增：后台抓取系统
│   ├── __init__.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── export_json.py
│   │   ├── journals.py
│   │   ├── selfcheck.py
│   │   ├── sync.py
│   │   ├── utils.py
│   │   └── providers/
│   ├── data/
│   ├── journal_list.xlsx              # 79 本期刊，ISSN/eISSN 已补齐
│   ├── requirements.txt
│   └── trigger/cloudflare-worker/
└── .github/workflows/
    └── update-paper-monitor.yml
```

网页地址：

`https://dm-dut.github.io/paper-monitor/`

## 1. GitHub Secrets

进入：

`Settings → Secrets and variables → Actions → New repository secret`

添加三个 Secret，名称必须完全一致：

- `ELSEVIER_API_KEY`
- `SPRINGER_API_KEY`
- `IEEE_API_KEY`

不要把真实 API Key 写进仓库中的 `.py`、`.js`、`.yml` 或 `.env.example`。

## 2. 第一次测试

进入：

`Actions → Update paper monitor → Run workflow`

Workflow 会先运行：

```bash
python -m paper_monitor_system.app.selfcheck
```

正常日志中应出现：

```text
journal_list=.../paper_monitor_system/journal_list.xlsx (79 enabled)
providers={'sciencedirect': 39, 'springer': 25, 'ieee': 15}
SELF-CHECK OK
```

随后执行：

```bash
python -m paper_monitor_system.app.sync --provider all --initial-days 7
```

## 3. 本版重点修复

- 已彻底移除 `from app...` / `import app` 旧包路径。
- `providers/base.py`、`ieee.py`、`sciencedirect.py`、`springer.py` 全部使用正确相对导入。
- 补全 `paper_monitor_system/__init__.py`、`app/__init__.py`、`providers/__init__.py`。
- 白名单、数据库和网页 JSON 都使用基于文件位置计算的绝对路径，不依赖 GitHub Runner 当前工作目录。
- Workflow 增加独立 self-check，抓取前先验证包、白名单、数据库路径。
- provider 报错不再被静默吞掉；若 API 权限、参数或网络真正失败，Actions 会明确显示失败 provider。
- 定时更新和手动 Actions 更新共用 `paper_monitor_system/data/papers.db`，按 DOI → provider external ID → 标题回退进行 upsert 去重。
- `paper-monitor/data/online_papers.json` 只导出当前白名单仍启用的期刊，但停用期刊的历史数据库记录不会删除。

## 4. 三个平台的日期逻辑

- ScienceDirect：按 `Load-Date` 精确日增量发现，并以该日期作为 ScienceDirect 上线日期。
- Springer Nature：使用 Metadata API 的 `onlineDate` / `onlinedatefrom` / `onlinedateto`。
- IEEE：用 `start_date` / `end_date` 做增量发现，网页日期优先使用返回的 `publication_date`，`insert_date` 作为发现/回退日期。

## 5. 网页“立即更新”按钮

自动定时更新和 GitHub Actions 页面手动 `Run workflow` 不需要额外配置。

如果要启用网页里的“立即更新”按钮，需要部署：

`paper_monitor_system/trigger/cloudflare-worker/`

Worker 默认触发：

`update-paper-monitor.yml`

部署后把 Worker `/refresh` URL 填入：

`paper-monitor/config.js`

的：

```js
refreshEndpoint: "https://你的-worker.workers.dev/refresh"
```

## 6. 不影响原主页

本包没有以下根目录内容：

- `/index.html`
- `/assets/`
- `/images/`
- `/scripts/`
- `/data/`
- `/homepage_content.xlsx`
- `/publication_database.xlsx`

因此合并上传不会覆盖这些现有主页文件。
