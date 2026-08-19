# Paper Monitor — dm-dut.github.io 直接上传版

这个压缩包专门用于合并到现有 `dm-dut.github.io` 仓库，不会覆盖个人主页根目录的 `index.html`。

## 上传后的新增结构

```text
<dm-dut.github.io repository>/
├── index.html                         # 你原有主页，不在本压缩包中
├── ...                                # 你原有文件，不修改
├── paper-monitor/                     # 新增：论文监测网页
│   ├── index.html
│   ├── app.js
│   ├── config.js
│   ├── style.css
│   └── data/online_papers.json
├── paper_monitor_system/              # 新增：后台抓取系统
│   ├── app/
│   ├── data/
│   ├── journal_list.xlsx
│   ├── requirements.txt
│   ├── .env.example
│   └── trigger/cloudflare-worker/
└── .github/workflows/
    └── update-paper-monitor.yml        # 新增：独立更新任务
```

## 访问地址

上传并由现有 GitHub Pages 发布后：

`https://dm-dut.github.io/paper-monitor/`

## 必须配置的 GitHub Secrets

在仓库：

`Settings → Secrets and variables → Actions → New repository secret`

添加：

- `ELSEVIER_API_KEY`
- `SPRINGER_API_KEY`
- `IEEE_API_KEY`

## 第一次运行

进入：

`Actions → Update paper monitor → Run workflow`

运行成功后会生成/更新：

- `paper_monitor_system/data/papers.db`
- `paper-monitor/data/online_papers.json`

自动任务和手动 Actions 运行使用同一个 SQLite 数据库，因此会按 DOI / 外部 ID / 标题逻辑进行更新与去重。

## 网页“立即更新”按钮

按钮代码已经保留，但出于安全原因，浏览器不能直接保存 GitHub Token。若要启用网页按钮，需要部署压缩包中的 Cloudflare Worker，然后将：

`paper-monitor/config.js`

中的 `refreshEndpoint` 填成 Worker 的 `/refresh` 地址。

未配置 `refreshEndpoint` 不影响：

- GitHub Actions 页面手动运行
- 每两天自动运行
- 网页读取并显示已生成的数据

## 与原主页隔离

本压缩包没有以下根目录文件或目录，因此不会覆盖它们：

- `/index.html`
- `/assets/`
- `/images/`
- `/scripts/`
- `/data/`
- `/homepage_content.xlsx`
- `/publication_database.xlsx`

后台数据库也不再使用根目录 `/data/`，而是使用独立的：

`paper_monitor_system/data/papers.db`
