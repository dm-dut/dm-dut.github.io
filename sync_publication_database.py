import shutil
from pathlib import Path
from datetime import datetime

# 原始 Excel 文件
source_file = Path(r"publication_database.xlsx")

# 目标目录
target_dir = Path(r"E:\MY FILES\Onedrive\CV\CV-Zhen Zhang-Latest\publication")  # 可以改成你想要的目录

# 创建目录（如果不存在）
target_dir.mkdir(parents=True, exist_ok=True)

# 生成新的文件名，例如添加日期
today = datetime.today().strftime("%Y%m%d")
new_file_name = f"MyPublication.xlsx"

target_file = target_dir / new_file_name

# 复制文件
shutil.copy2(source_file, target_file)

print(f"Copied and renamed file to: {target_file}")