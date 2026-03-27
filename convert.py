import pandas as pd
import json
import os
import datetime


def process_author_names(author_str, corr_authors_str):
    """
    处理作者姓名逻辑：
    1. 统一分隔符。
    2. 将 "Zhang, Zhen" 转换为 "Zhen Zhang"。
    3. 匹配通讯作者并加星号 (*)。
    """
    if not author_str or str(author_str).lower() == 'nan':
        return ""

    # 统一将分号、逗号（中英文）替换为标准分号再分割，去除多余空格
    raw_authors = [a.strip() for a in str(author_str).replace('；', ';').replace('，', ',').split(';')]
    # 获取通讯作者名单
    corr_authors = [ca.strip() for ca in str(corr_authors_str).replace('；', ';').replace('，', ',').split(';')]

    processed = []
    for a in raw_authors:
        clean_name = a
        # 1. 格式转换：如果有逗号，执行 "Zhang, Zhen" -> "Zhen Zhang"
        if ',' in a:
            parts = a.split(',')
            if len(parts) == 2:
                clean_name = f"{parts[1].strip()} {parts[0].strip()}"

        # 2. 通讯作者匹配：基于原始 Excel 中的名字 'a' 进行判断，防止转置后匹配不上
        if corr_authors_str and any(ca in a or a in ca for ca in corr_authors if ca):
            # 如果是通讯作者，在转置后的名字后面加 *
            if not clean_name.endswith('*'):
                clean_name += "*"

        processed.append(clean_name)

    return ", ".join(processed)


def clean_metrics_tags(row):
    """提取检索标签（SCI, SSCI, EI 等）并清洗 ABS 小数点"""
    tags = []
    # 检查各检索证明列
    for col in ['SCI', 'SSCI', 'EI', 'CSSCI', 'ISTP', 'FMS']:
        if col in row:
            val = str(row[col]).strip()
            if val and val.lower() not in ['nan', '', '否']:
                tags.append(col if val == '是' else f"{col} {val}")

    # 处理 ABS (移除 .0)
    if 'ABS ' in row:
        abs_val = str(row['ABS ']).strip()
        if abs_val and abs_val.lower() not in ['nan', '', '否']:
            clean_abs = abs_val.replace('.0', '')
            tags.append(f"ABS {clean_abs}" if clean_abs != '是' else "ABS")

    # 处理 IF
    if 'IF' in row and str(row['IF']).strip() not in ['nan', '']:
        tags.append(f"IF={row['IF']}")
    return ", ".join(tags)


def run_conversion():
    # Excel 文件名，请确保在脚本同级目录下
    file_name = '../CV-Zhen Zhang-Latest/publication/MyPublication.xlsx'
    if not os.path.exists(file_name):
        print(f"错误: 找不到文件 {file_name}")
        return

    # 读取 Excel
    df = pd.read_excel(file_name).fillna('')

    # 初始化分类
    categories = {"Monograph": [], "Journal Articles": [], "Conference Papers": []}

    # 类型映射
    type_map = {
        "书": "Monograph", "Book": "Monograph", "著作": "Monograph", "专著": "Monograph",
        "期刊": "Journal Articles", "Journal": "Journal Articles",
        "会议": "Conference Papers", "Conference": "Conference Papers"
    }

    print("正在处理数据...")
    for _, row in df.iterrows():
        raw_type = str(row['Type']).strip()
        pub_type = type_map.get(raw_type)
        if not pub_type:
            continue

        # 核心数据构建
        item = {
            # 作者处理：统一转置并加星号
            "authors_en": process_author_names(row['Author_English'], row['Corresponding_Author']),
            "authors_cn": process_author_names(row['Author_Chinese'], row['Corresponding_Author']),

            # 标题与来源
            "title_en": str(row['Title_English']).strip(),
            "title_cn": str(row['Title_Chinese']).strip(),
            "source_en": str(row['Source_English']).strip(),
            "source_cn": str(row['Source_Chinese']).strip(),

            # 公共基础字段
            "year": str(row['Year']).replace('.0', ''),
            "vol": str(row['Volume']).replace('.0', ''),
            "no": str(row['Number']).replace('.0', ''),
            "page": str(row['Page']).strip(),
            "doi": str(row['DOI']).strip() if str(row['DOI']).lower() != 'nan' else "",

            # 专著/书特有：出版地址与 ISBN
            "Address": str(row.get('Address', '')).strip(),
            "ISBN": str(row.get('ISBN', '')).strip(),

            # 会议特有：地址与日期
            "addr": str(row.get('Conference_Address', '')).strip(),
            "date": str(row.get('Conference_Date', '')).strip(),

            # 备注与标签
            "note_en": str(row.get('Note_English', '')).strip(),
            "note_cn": str(row.get('Note_Chinese', '')).strip(),
            "esi_high": str(row.get('ESI_Highly_Cited', '')).strip() == '是',
            "metrics": clean_metrics_tags(row)
        }

        # 清理所有的 "nan" 字符串
        for k in item:
            if item[k] == "nan": item[k] = ""

        categories[pub_type].append(item)

    # 按年份降序排序
    for k in categories:
        categories[k].sort(key=lambda x: x['year'], reverse=True)

    # --- 核心新增：注入文件保存时间 ---
    now = datetime.datetime.now()
    save_time = now.strftime("%Y-%m-%d %H:%M:%S")

    output_payload = {
        "metadata": {
            "last_update": save_time
        },
        "publications": categories
    }

    # 写入 JSON
    with open('papers.json', 'w', encoding='utf-8') as f:
        json.dump(output_payload, f, ensure_ascii=False, indent=4)

    print(f"转换成功！'papers.json' 已更新。")
    print(f"记录的保存时间为: {save_time}")


if __name__ == "__main__":
    run_conversion()

