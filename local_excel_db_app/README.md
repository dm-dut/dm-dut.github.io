# 本地 Excel 数据库维护系统

这是一个完全本地运行的小型数据维护系统：

- 使用 SQLite 作为本地数据库；
- 使用 Flask 提供本地网页；
- 支持 Excel 导入、网页增删改查、自动导出 Excel；
- 支持从网页按钮执行本地 Python 脚本，生成 JSON、TeX 等文件；
- 网页显示顺序默认保持 Excel 原始行顺序。

## 运行方法

```bash
pip install -r requirements.txt
python app.py
```

然后打开：

```text
http://127.0.0.1:5000
```

## 文件结构

```text
local_excel_db_app/
├─ app.py                         # Flask 后台
├─ requirements.txt               # 依赖包
├─ data/
│  ├─ homepage_content.xlsx        # 默认导入的 Excel
│  ├─ local_content.db             # SQLite 本地数据库，首次运行自动生成/初始化
│  └─ auto_exported_content.xlsx   # 增删改查后自动更新的 Excel
├─ scripts/
│  ├─ generate_json.py             # 生成 JSON
│  ├─ generate_tex.py              # 生成 TeX
│  └─ generate_all.py              # 全部生成
├─ output/                         # JSON、TeX 等输出文件
├─ templates/index.html            # 网页结构
└─ static/
   ├─ style.css                    # 页面样式
   └─ app.js                       # 前端逻辑
```

## 顺序规则

导入 Excel 时，系统会给每一行记录自动写入内部字段 `_order_index`，网页查询和导出 Excel 均按：

```text
_order_index ASC, id ASC
```

排序。因此，网页显示顺序会保持 Excel 文件中的原始顺序。新增记录默认追加到当前表末尾。

## 自动导出

每次执行以下操作后，系统都会自动更新：

```text
data/auto_exported_content.xlsx
```

触发操作包括：

- 新增记录；
- 修改记录；
- 删除记录；
- 重新导入 Excel。

## 生成 JSON / TeX

网页上有三个按钮：

- 生成 JSON；
- 生成 TeX；
- 全部生成。

对应执行 `scripts/` 文件夹中的白名单脚本。生成结果会保存到 `output/` 文件夹，并在网页中显示下载链接。

如需增加新的脚本，需要：

1. 把 Python 脚本放到 `scripts/`；
2. 在 `app.py` 的 `allowed` 字典中加入对应任务；
3. 在前端页面增加按钮。

## 页面美化说明

当前版本使用柔和的绿色、橙色、米色和浅蓝色，侧边栏数据表标签使用不同背景色区分，表格采用斑马纹、悬浮高亮和固定表头，适合长期本地维护数据。
