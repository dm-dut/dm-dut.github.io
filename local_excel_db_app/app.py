import os
import re
import sqlite3
import tempfile
import subprocess
import sys
from datetime import datetime

import pandas as pd
from flask import Flask, jsonify, render_template, request, send_file

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "local_content.db")
DEFAULT_EXCEL = os.path.join(DATA_DIR, "homepage_content.xlsx")
EXPORT_EXCEL = os.path.join(DATA_DIR, "exported_content.xlsx")
AUTO_EXPORT_EXCEL = os.path.join(DATA_DIR, "auto_exported_content.xlsx")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")

AUTO_EXPORT_ENABLED = True


SYSTEM_COLUMNS = {"id", "_order_index"}
SKIP_SHEETS = {"README"}

app = Flask(__name__)
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def normalize_identifier(name: str) -> str:
    name = str(name).strip()
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^0-9a-zA-Z_\u4e00-\u9fff]", "_", name)
    if not name:
        name = "field"
    if re.match(r"^\d", name):
        name = f"c_{name}"
    return name


def table_name_from_sheet(sheet_name: str) -> str:
    return normalize_identifier(sheet_name)


def clean_value(value):
    if pd.isna(value):
        return ""
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    return str(value).strip()


def load_excel_to_sqlite(excel_path: str):
    xls = pd.ExcelFile(excel_path)
    conn = connect_db()
    cur = conn.cursor()

    cur.execute("select name from sqlite_master where type='table'")
    old_tables = [row[0] for row in cur.fetchall()]
    for table in old_tables:
        cur.execute(f'DROP TABLE IF EXISTS "{table}"')

    meta_rows = []

    for sheet_name in xls.sheet_names:
        if sheet_name in SKIP_SHEETS:
            continue

        df = pd.read_excel(excel_path, sheet_name=sheet_name, dtype=object)
        df = df.dropna(how="all")
        if df.empty and len(df.columns) == 0:
            continue

        columns = [normalize_identifier(c) for c in df.columns if str(c).strip() and not str(c).startswith("Unnamed")]
        if not columns:
            continue

        df = df.iloc[:, : len(columns)]
        df.columns = columns
        df = df.fillna("")

        table_name = table_name_from_sheet(sheet_name)
        col_defs = ", ".join([f'"{col}" TEXT' for col in columns])
        cur.execute(f'CREATE TABLE "{table_name}" (id INTEGER PRIMARY KEY AUTOINCREMENT, _order_index INTEGER, {col_defs})')

        placeholders = ", ".join(["?"] * len(columns))
        col_sql = ", ".join([f'"{col}"' for col in columns])
        insert_sql = f'INSERT INTO "{table_name}" (_order_index, {col_sql}) VALUES (?, {placeholders})'

        order_index = 1
        for _, row in df.iterrows():
            values = [clean_value(row[col]) for col in columns]
            if any(v != "" for v in values):
                cur.execute(insert_sql, [order_index] + values)
                order_index += 1

        meta_rows.append((table_name, sheet_name, "|".join(columns)))

    cur.execute('CREATE TABLE "_meta_tables" (table_name TEXT PRIMARY KEY, sheet_name TEXT, columns TEXT)')
    cur.executemany('INSERT INTO "_meta_tables" (table_name, sheet_name, columns) VALUES (?, ?, ?)', meta_rows)
    conn.commit()
    conn.close()


def database_has_meta():
    if not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) == 0:
        return False
    try:
        conn = connect_db()
        row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='_meta_tables'").fetchone()
        conn.close()
        return row is not None
    except sqlite3.DatabaseError:
        return False


def ensure_database():
    if not database_has_meta():
        if os.path.exists(DEFAULT_EXCEL):
            load_excel_to_sqlite(DEFAULT_EXCEL)
        else:
            conn = connect_db()
            conn.execute('CREATE TABLE IF NOT EXISTS "_meta_tables" (table_name TEXT PRIMARY KEY, sheet_name TEXT, columns TEXT)')
            conn.commit()
            conn.close()


def get_tables():
    ensure_database()
    conn = connect_db()
    rows = conn.execute('SELECT table_name, sheet_name, columns FROM "_meta_tables" ORDER BY rowid').fetchall()
    conn.close()
    return [
        {
            "table_name": row["table_name"],
            "sheet_name": row["sheet_name"],
            "columns": row["columns"].split("|") if row["columns"] else [],
        }
        for row in rows
    ]


def get_table_meta(table_name):
    for item in get_tables():
        if item["table_name"] == table_name:
            return item
    return None


@app.route("/")
def index():
    ensure_database()
    return render_template("index.html")


@app.route("/api/tables")
def api_tables():
    return jsonify(get_tables())


@app.route("/api/rows/<table_name>")
def api_rows(table_name):
    meta = get_table_meta(table_name)
    if not meta:
        return jsonify({"error": "Table not found"}), 404

    q = request.args.get("q", "").strip()
    conn = connect_db()

    if q:
        conditions = " OR ".join([f'"{c}" LIKE ?' for c in meta["columns"]])
        params = [f"%{q}%"] * len(meta["columns"])
        rows = conn.execute(f'SELECT * FROM "{table_name}" WHERE {conditions} ORDER BY COALESCE(_order_index, id) ASC, id ASC', params).fetchall()
    else:
        rows = conn.execute(f'SELECT * FROM "{table_name}" ORDER BY COALESCE(_order_index, id) ASC, id ASC').fetchall()

    conn.close()
    return jsonify([dict(row) for row in rows])


@app.route("/api/rows/<table_name>", methods=["POST"])
def api_add_row(table_name):
    meta = get_table_meta(table_name)
    if not meta:
        return jsonify({"error": "Table not found"}), 404

    payload = request.get_json(force=True)
    cols = meta["columns"]
    values = [str(payload.get(col, "")).strip() for col in cols]
    placeholders = ", ".join(["?"] * len(cols))
    col_sql = ", ".join([f'"{c}"' for c in cols])

    conn = connect_db()
    cur = conn.cursor()
    max_order = cur.execute(f'SELECT COALESCE(MAX(_order_index), 0) AS max_order FROM "{table_name}"').fetchone()["max_order"]
    insert_sql = f'INSERT INTO "{table_name}" (_order_index, {col_sql}) VALUES (?, {placeholders})'
    cur.execute(insert_sql, [int(max_order or 0) + 1] + values)
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    auto_export_excel()
    return jsonify({"ok": True, "id": new_id})


@app.route("/api/rows/<table_name>/<int:row_id>", methods=["PUT"])
def api_update_row(table_name, row_id):
    meta = get_table_meta(table_name)
    if not meta:
        return jsonify({"error": "Table not found"}), 404

    payload = request.get_json(force=True)
    cols = meta["columns"]
    set_sql = ", ".join([f'"{c}" = ?' for c in cols])
    values = [str(payload.get(col, "")).strip() for col in cols]

    conn = connect_db()
    conn.execute(f'UPDATE "{table_name}" SET {set_sql} WHERE id = ?', values + [row_id])
    conn.commit()
    conn.close()
    auto_export_excel()
    return jsonify({"ok": True})


@app.route("/api/rows/<table_name>/<int:row_id>", methods=["DELETE"])
def api_delete_row(table_name, row_id):
    meta = get_table_meta(table_name)
    if not meta:
        return jsonify({"error": "Table not found"}), 404

    conn = connect_db()
    conn.execute(f'DELETE FROM "{table_name}" WHERE id = ?', [row_id])
    conn.commit()
    conn.close()
    auto_export_excel()
    return jsonify({"ok": True})


@app.route("/api/import", methods=["POST"])
def api_import_excel():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files["file"]
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        return jsonify({"error": "Please upload an Excel file"}), 400

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        load_excel_to_sqlite(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    auto_export_excel()
    return jsonify({"ok": True})


def export_database_to_excel(output_path: str):
    """Export all user tables in SQLite to a multi-sheet Excel file."""
    tables = get_tables()
    conn = connect_db()
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for table in tables:
            df = pd.read_sql_query(f'SELECT * FROM "{table["table_name"]}" ORDER BY COALESCE(_order_index, id) ASC, id ASC', conn)
            for system_col in ["id", "_order_index"]:
                if system_col in df.columns:
                    df = df.drop(columns=[system_col])
            df.to_excel(writer, sheet_name=table["sheet_name"][:31], index=False)
    conn.close()
    return output_path


def auto_export_excel():
    """Automatically refresh the Excel backup after every database change."""
    if AUTO_EXPORT_ENABLED:
        export_database_to_excel(AUTO_EXPORT_EXCEL)


@app.route("/api/export")
def api_export_excel():
    export_database_to_excel(EXPORT_EXCEL)
    return send_file(EXPORT_EXCEL, as_attachment=True, download_name="exported_content.xlsx")


@app.route("/api/auto_export_status")
def api_auto_export_status():
    exists = os.path.exists(AUTO_EXPORT_EXCEL)
    modified_at = ""
    if exists:
        modified_at = datetime.fromtimestamp(os.path.getmtime(AUTO_EXPORT_EXCEL)).strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({
        "enabled": AUTO_EXPORT_ENABLED,
        "exists": exists,
        "path": AUTO_EXPORT_EXCEL,
        "modified_at": modified_at,
    })


def run_local_script(script_name: str):
    """Run a whitelisted local Python script.

    Only scripts listed in ALLOWED_TASKS can be called from the webpage, which
    avoids arbitrary command execution. Each script receives the database path
    and output folder as command-line arguments.
    """
    allowed = {
        "json": "generate_json.py",
        "tex": "generate_tex.py",
        "json_tex": "generate_all.py",
    }
    if script_name not in allowed:
        return {"ok": False, "error": "Unknown task"}, 400

    script_path = os.path.join(SCRIPTS_DIR, allowed[script_name])
    if not os.path.exists(script_path):
        return {"ok": False, "error": f"Script not found: {allowed[script_name]}"}, 404

    try:
        result = subprocess.run(
            [sys.executable, script_path, "--db", DB_PATH, "--out", OUTPUT_DIR],
            cwd=BASE_DIR,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        return {
            "ok": result.returncode == 0,
            "task": script_name,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }, 200 if result.returncode == 0 else 500
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Script timed out after 60 seconds"}, 500


@app.route("/api/run/<task>", methods=["POST"])
def api_run_task(task):
    payload, status = run_local_script(task)
    return jsonify(payload), status


@app.route("/api/files")
def api_files():
    files = []
    for name in sorted(os.listdir(OUTPUT_DIR)):
        path = os.path.join(OUTPUT_DIR, name)
        if os.path.isfile(path):
            files.append({
                "name": name,
                "size": os.path.getsize(path),
                "modified_at": datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M:%S"),
                "url": f"/api/files/{name}",
            })
    return jsonify(files)


@app.route("/api/files/<path:filename>")
def api_download_generated_file(filename):
    safe_name = os.path.basename(filename)
    path = os.path.join(OUTPUT_DIR, safe_name)
    if not os.path.exists(path):
        return jsonify({"error": "File not found"}), 404
    return send_file(path, as_attachment=True, download_name=safe_name)


if __name__ == "__main__":
    ensure_database()
    auto_export_excel()
    app.run(host="127.0.0.1", port=5000, debug=True)
