
import sqlite3
def init(path):
    c=sqlite3.connect(path)
    c.execute('CREATE TABLE IF NOT EXISTS papers(doi TEXT PRIMARY KEY,title TEXT,authors TEXT,journal TEXT,category TEXT,publisher TEXT,online_date TEXT,first_seen TEXT)')
    c.commit()
    return c
def exists(c,doi):
    return c.execute("select 1 from papers where doi=?",(doi,)).fetchone()!=None
