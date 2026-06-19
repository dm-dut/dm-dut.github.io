def run_conversion():
    file_name = 'E:/MY FILES/Onedrive/CV/CV-Zhen Zhang-Latest/publication/MyPublication.xlsx'
    if not os.path.exists(file_name):
        file_name = 'MyPublication.xlsx - Sheet1.csv'

    df = pd.read_csv(file_name) if file_name.endswith('.csv') else pd.read_excel(file_name)
    df = df.fillna('')

    categories = {"Monograph": [], "Journal Articles": [], "Conference Papers": []}

    # --- 修正 7：将“书”映射为 Monograph ---
    type_map = {
        "书": "Monograph", "Book": "Monograph", "著作": "Monograph", "专著": "Monograph",
        "期刊": "Journal Articles", "Journal": "Journal Articles",
        "会议": "Conference Papers", "Conference": "Conference Papers"
    }

    for _, row in df.iterrows():
        pub_type = type_map.get(str(row['Type']).strip())
        if not pub_type: continue

        # 处理检索信息 (移除 ABS 小数点)
        metrics = clean_metrics_tags(row)

        item = {
            "authors": process_author_names(row['Author_English'], row['Corresponding_Author']),
            "title": str(row['Title_English']).strip(),
            "source": str(row['Source_English']).strip(),
            "year": str(row['Year']).replace('.0', ''),
            "vol": str(row['Volume']).replace('.0', ''),
            "no": str(row['Number']).replace('.0', ''),
            "page": str(row['Page']).strip(),
            "doi": str(row['DOI']).strip(),
            "addr": str(row.get('Conference_Address', '')).strip(),
            "date": str(row.get('Conference_Date', '')).strip(),
            "esi_high": str(row.get('ESI_Highly_Cited', '')) == '是',
            "esi_hot": str(row.get('ESI_Hot', '')) == '是',
            "note_en": str(row.get('Note_English', '')).strip(),  # 英文 note 字段
            "metrics": metrics
        }
        categories[pub_type].append(item)

    # 年份降序排序
    for k in categories:
        categories[k].sort(key=lambda x: x['year'], reverse=True)

    with open('papers1.json', 'w', encoding='utf-8') as f:
        json.dump(categories, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    run_conversion()