
import os, sys, json, datetime
import pandas as pd

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from collectors.crossref import fetch
from core.database import init, exists

os.makedirs(ROOT+"/web", exist_ok=True)
os.makedirs(ROOT+"/database", exist_ok=True)

conn=init(ROOT+"/database/papers.db")
journals=pd.read_excel(ROOT+"/config/journals.xlsx")

# backup previous database snapshot for NEW comparison
old=[]
for r in conn.execute(
    "select doi,title,authors,journal,category,publisher,online_date from papers"
):
    old.append(dict(zip(
        ["doi","title","authors","journal","category","publisher","online_date"], r
    )))

with open(ROOT+"/web/previous_papers.json","w",encoding="utf-8") as f:
    json.dump(old,f,ensure_ascii=False,indent=2)

first=len(old)==0

print("="*70)
print("Paper Monitor v13.7")
print("Mode:", "INITIAL" if first else "INCREMENTAL")
print("Journals:", len(journals))
print("="*70)

new=[]

for i,(_,row) in enumerate(journals.iterrows(),1):
    name=row.get("Journal","")
    issn=row.get("pISSN","")

    print(f"[{i}/{len(journals)}] {name} ({issn})")

    try:
        papers=fetch(issn)

        add=0
        for p in papers:
            p["category"]=str(row.get("Category",""))
            p["publisher"]=str(row.get("Publisher",""))

            if first or not exists(conn,p["doi"]):
                new.append(p)
                add+=1

            if not exists(conn,p["doi"]):
                conn.execute(
                "insert into papers values(?,?,?,?,?,?,?,date('now'))",
                (
                    p["doi"],p["title"],p["authors"],
                    p["journal"],p["category"],
                    p["publisher"],p["online_date"]
                ))

        conn.commit()
        print("  Fetched:",len(papers)," New:",add)

    except Exception as e:
        print("  FAILED:",e)

allpapers=[]
for r in conn.execute(
"select doi,title,authors,journal,category,publisher,online_date from papers"
):
    allpapers.append(dict(zip(
    ["doi","title","authors","journal","category","publisher","online_date"],r)))

with open(ROOT+"/web/papers.json","w",encoding="utf-8") as f:
    json.dump(allpapers,f,ensure_ascii=False,indent=2)

with open(ROOT+"/web/new_papers.json","w",encoding="utf-8") as f:
    json.dump(new,f,ensure_ascii=False,indent=2)

with open(ROOT+"/web/update_time.json","w",encoding="utf-8") as f:
    json.dump({
        "updated":datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "count":len(new)
    },f,ensure_ascii=False,indent=2)

print("="*70)
print("Finished")
print("Total papers:",len(allpapers))
print("New papers:",len(new))
print("="*70)
