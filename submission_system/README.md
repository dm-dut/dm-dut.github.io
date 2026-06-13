# 期刊投稿系统链接集合

文件说明：

- `index.html`：网页入口，只负责显示页面，不内嵌 JSON 数据
- `journal_submission_systems.xlsx`：需要维护的 Excel 数据
- `journal_submission_systems.json`：网页自动读取的数据文件
- `convert_excel_to_json.py`：Excel 转 JSON 程序
- `journal/`：期刊列表目录，网页右上角“期刊列表”链接指向这里

## 更新流程

修改 Excel 后，在本目录运行：

```bash
python convert_excel_to_json.py --excel journal_submission_systems.xlsx --out journal_submission_systems.json
```

然后刷新网页即可。

## 本地预览

如果直接双击 `index.html` 无法读取 JSON，请运行：

```bash
python -m http.server 8000
```

然后访问：

```text
http://localhost:8000/
```
