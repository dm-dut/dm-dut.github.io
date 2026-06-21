import xlwings as xw
from pypinyin import pinyin, Style
import re
import os


def chinese_name_to_english(name_str):
    """
    将中文姓名转换为学术规范拼音格式，并确保英文作者间使用逗号分隔
    """
    if not name_str or not str(name_str).strip():
        return ""

    origin_str = str(name_str).strip()

    # 1. 统一分隔符（支持中文分号、逗号）
    normalized_str = re.sub(r'[；，,]', ';', origin_str)
    chinese_authors = [auth.strip() for auth in normalized_str.split(';') if auth.strip()]
    english_authors = []

    for author in chinese_authors:
        pinyin_raw = pinyin(author, style=Style.NORMAL)
        pinyin_list = [item[0].lower() for item in pinyin_raw if item[0].isalpha()]

        if not pinyin_list:
            continue

        # 2. 姓名内部逻辑保持不变 (Last, First)
        if len(pinyin_list) == 1:
            formatted_name = pinyin_list[0].capitalize()
        elif len(pinyin_list) == 2:
            formatted_name = f"{pinyin_list[0].capitalize()}, {pinyin_list[1].capitalize()}"
        elif len(pinyin_list) == 3:
            last_name = pinyin_list[0].capitalize()
            first_name = ("".join(pinyin_list[1:])).capitalize()
            formatted_name = f"{last_name}, {first_name}"
        else:
            if author.startswith(('欧阳', '司马', '诸葛', '东方', '独孤', '皇甫', '公孙')):
                last_name = ("".join(pinyin_list[:2])).capitalize()
                first_name = ("".join(pinyin_list[2:])).capitalize()
            else:
                last_name = pinyin_list[0].capitalize()
                first_name = ("".join(pinyin_list[1:])).capitalize()
            formatted_name = f"{last_name}, {first_name}"

        english_authors.append(formatted_name)

    # 3. 关键修改：将原来的 "; " 改为 ", "，这样作者间就是逗号分隔了
    return ", ".join(english_authors)


def fill_english_authors_with_xlwings(file_path, output_path):
    print("正在通过 Excel 进程打开文件（保持后台隐藏）...")
    app = xw.App(visible=False, add_book=False)

    try:
        wb = app.books.open(file_path)
        sheet = wb.sheets[0]  # 操作第一个 sheet

        # 1. 获取第一行表头并映射列号
        header_row = sheet.range('A1').expand('right').value
        header_map = {val: idx + 1 for idx, val in enumerate(header_row) if val}

        # 检查必要的列
        required_cols = ['Corresponding_Author_cn', 'Corresponding_Author_en', 'Author_Chinese', 'Author_English',
                         'Language']
        for r_col in required_cols:
            if r_col not in header_map:
                raise ValueError(f"Excel 表头中未找到必要的列: {r_col}")

        col_ca_cn = header_map['Corresponding_Author_cn']
        col_ca_en = header_map['Corresponding_Author_en']
        col_ac_cn = header_map['Author_Chinese']
        col_ae_en = header_map['Author_English']
        col_lang = header_map['Language']  # 语言列号

        # 2. 动态获取最后一行的行号
        max_row = sheet.range('A' + str(sheet.cells.last_cell.row)).end('up').row

        print(f"开始处理数据，共计 {max_row - 1} 行...")

        # 3. 循环处理数据行
        for row in range(2, max_row + 1):
            # 获取当前行的语言类型
            lang_val = str(sheet.cells(row, col_lang).value).strip() if sheet.cells(row, col_lang).value else ""

            # 判断是否为中文论文
            is_chinese_paper = lang_val in ['中文', 'Chinese', 'ZH', 'zh']

            # --- A. 处理通讯作者 ---
            ca_cn_val = sheet.cells(row, col_ca_cn).value
            ca_en_val = sheet.cells(row, col_ca_en).value

            if ca_cn_val and (ca_en_val is None or str(ca_en_val).strip() == ""):
                if is_chinese_paper:
                    # 中文论文：走拼音转换逻辑
                    sheet.cells(row, col_ca_en).value = chinese_name_to_english(str(ca_cn_val))
                else:
                    # 英文论文：直接 100% 原样填充，不做任何处理
                    sheet.cells(row, col_ca_en).value = ca_cn_val

            # --- B. 处理全体作者 ---
            ac_cn_val = sheet.cells(row, col_ac_cn).value
            ae_en_val = sheet.cells(row, col_ae_en).value

            if ac_cn_val and (ae_en_val is None or str(ae_en_val).strip() == ""):
                if is_chinese_paper:
                    # 中文论文：走拼音转换逻辑
                    sheet.cells(row, col_ae_en).value = chinese_name_to_english(str(ac_cn_val))
                else:
                    # 英文论文：直接 100% 原样填充，不做任何处理
                    sheet.cells(row, col_ae_en).value = ac_cn_val

        # 4. 保存文件并关闭
        wb.save(output_path)
        wb.close()
        print(f"🎉 成功！英文论文已完全原样填充。新文件：{output_path}")

    finally:
        # 确保强制关闭后台 Excel 进程
        app.quit()


if __name__ == "__main__":
    current_dir = os.getcwd()
    input_file = os.path.join(current_dir, "publication_database.xlsx")
    output_file = os.path.join(current_dir, "publication_database.xlsx")

    fill_english_authors_with_xlwings(input_file, output_file)

