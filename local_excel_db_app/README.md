# 本地学术数据维护系统

## 运行方法

```bash
cd local_excel_db_app_source_cn_top
pip install -r requirements.txt
python app.py
```

然后打开：

```text
http://127.0.0.1:5000
```

## 数据文件

系统默认维护两个 Excel 文件：

```text
data/homepage_content.xlsx        基础数据：News、Awards、Grants、Services、Group 等
data/publication_database.xlsx    发表记录：Publications
```

`Projects` 已从默认 Excel 和数据库中移除，不再作为网页页面或导出工作表出现。

影响因子库仍作为隐藏参考库：

```text
data/impact_factors.xlsx
```

它用于根据期刊名、ISSN 或 EISSN 匹配 ISSN/IF，但不显示在左侧页面中，也不会合并导出到两个主 Excel 文件中。

## 新增记录顺序

所有表格新增记录默认插入到最上方。原始 Excel 导入顺序保持不变，只有后续新增内容会优先显示在顶部。

## 更新逻辑

新增、编辑、删除基础数据时，只更新：

```text
data/homepage_content.xlsx
```

新增、编辑、删除发表记录时，只更新：

```text
data/publication_database.xlsx
```

导入影响因子库时，只更新隐藏索引，不重写两个主 Excel。

## Publications 更新按钮

新增或编辑 `Publications` 记录后，系统会将该记录标记为待更新。进入 Publications 页面后，点击筛选栏中的 `更新` 按钮，系统只处理新增或编辑过的记录，完成：

- 根据 `Author_Chinese` 自动生成 `Author_English`；
- 根据 `Corresponding_Author_cn` 自动生成 `Corresponding_Author_en`；
- 对英文论文，如果 `Title_Chinese` 为空，自动复制 `Title_English`；
- 对英文论文，如果 `Source_Chinese` 为空，自动复制 `Source_English`；
- 根据期刊名、ISSN 或 EISSN 匹配影响因子库；
- 如果 ISSN 为空，优先提取 ISSN；如果 ISSN 为空但 eISSN 存在，则提取 eISSN；
- 如果期刊名匹配不到，可以手动填写 ISSN 或 eISSN，再点击 `更新` 匹配 IF。

影响因子库中同一期刊存在多条记录时，只使用第一条记录。

## 网页显示

- 网页字段名显示为中文，避免列名过长；
- 数据库字段名和导出的 Excel 字段名仍保留原名；
- `Publications` 默认显示期刊论文和工作论文；
- 可以切换为期刊、工作、会议、专著或全部类型；
- 不同类型动态显示不同字段，减少空白列。

## 重新初始化

如果需要重新初始化数据库，可以删除：

```text
data/local_content.db
```

然后重新运行：

```bash
python app.py
```
