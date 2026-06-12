# 期刊投稿系统链接集合

文件说明：

- `index.html`：网页入口，只负责显示页面，不再内嵌 JSON 数据
- `journal_submission_systems.xlsx`：需要维护的 Excel 数据
- `journal_submission_systems.json`：网页自动读取的数据文件
- `convert_excel_to_json.py`：Excel 转 JSON 程序

## 更新流程

修改 Excel 后，在本目录运行：

```bash
python convert_excel_to_json.py --excel journal_submission_systems.xlsx --out journal_submission_systems.json
```

然后刷新网页即可。

## 本地预览

如果直接双击 `index.html` 后无法读取 JSON，请在本目录运行：

```bash
python -m http.server 8000
```

然后访问：

```text
http://localhost:8000/
```

部署到 GitHub Pages 或普通网站时，只需要保证 `index.html` 和 `journal_submission_systems.json` 在同一目录。
