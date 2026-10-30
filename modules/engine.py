import pandas as pd
import sqlite3, re, hashlib
from pathlib import Path

def norm(v):
    if pd.isna(v): return ""
    return re.sub(r"\s+"," ",str(v).strip().lower())

def dt(v):
    if pd.isna(v): return ""
    return pd.to_datetime(v).strftime("%Y-%m-%d")

def load_event_file(upload):
    xls=pd.ExcelFile(upload)
    preferred=["Sheet1"]
    sheet=next((s for s in preferred if s in xls.sheet_names),xls.sheet_names[0])
    df=pd.read_excel(xls,sheet_name=sheet)
    required=["Event Name","Event Date Start","Event Date End"]
    missing=[c for c in required if c not in df.columns]
    if missing:
        raise ValueError("Kolom wajib tidak ditemukan: "+", ".join(missing))
    for c in ["Event ID","Event Category","Provider","Vendor","Training Support","Event Type","Event Group","Event Status","School"]:
        if c not in df.columns: df[c]=""
    df["Event Date Start"]=pd.to_datetime(df["Event Date Start"],errors="coerce",dayfirst=True)
    df["Event Date End"]=pd.to_datetime(df["Event Date End"],errors="coerce",dayfirst=True)
    df=df.dropna(subset=["Event Name","Event Date Start","Event Date End"]).copy()
    return df,sheet

def filter_events(df,start,end):
    a=pd.Timestamp(start)
    b=pd.Timestamp(end)+pd.Timedelta(days=1)-pd.Timedelta(seconds=1)
    # Periode dipilih berdasarkan tanggal mulai event, bukan irisan rentang event.
    return df[df["Event Date Start"].between(a, b, inclusive="both")].copy()

def init_db(path):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(path) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS choices(
          fingerprint TEXT PRIMARY KEY,event_name TEXT,school TEXT,vendor TEXT,
          provider TEXT,start_date TEXT,end_date TEXT,city TEXT,room TEXT,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        con.execute("""CREATE TABLE IF NOT EXISTS cities(city TEXT PRIMARY KEY)""")
        con.execute("""CREATE TABLE IF NOT EXISTS rooms(city TEXT,room TEXT,PRIMARY KEY(city,room))""")
        con.commit()

def fingerprint(row):
    # Stable fingerprint for unchanged event details; Event ID is deliberately excluded.
    bits=[norm(row.get("Event Name")),norm(row.get("School")),norm(row.get("Vendor")),
          dt(row.get("Event Date Start")),dt(row.get("Event Date End"))]
    return hashlib.sha256("|".join(bits).encode()).hexdigest()

def find_saved_choice(db,row):
    init_db(db)
    fp=fingerprint(row)
    with sqlite3.connect(db) as con:
        exact=con.execute("SELECT city,room FROM choices WHERE fingerprint=?",(fp,)).fetchone()
        if exact: return {"status":"matched","city":exact[0],"room":exact[1]}
        # If date changed, try a unique match using event name + school + vendor.
        candidates=con.execute("""SELECT city,room FROM choices
          WHERE event_name=? AND school=? AND vendor=?""",
          (norm(row.get("Event Name")),norm(row.get("School")),norm(row.get("Vendor")))).fetchall()
    if len(candidates)==1:
        return {"status":"matched","city":candidates[0][0],"room":candidates[0][1]}
    if len(candidates)>1:
        return {"status":"ambiguous","city":"","room":""}
    return {"status":"new","city":"","room":""}

def save_choice(db,row,city,room):
    init_db(db)
    with sqlite3.connect(db) as con:
        con.execute("""INSERT INTO choices(fingerprint,event_name,school,vendor,provider,start_date,end_date,city,room)
        VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(fingerprint) DO UPDATE SET
        city=excluded.city,room=excluded.room,updated_at=CURRENT_TIMESTAMP""",
        (fingerprint(row),norm(row.get("Event Name")),norm(row.get("School")),norm(row.get("Vendor")),
         str(row.get("Provider","")),dt(row.get("Event Date Start")),dt(row.get("Event Date End")),city,room))
        con.commit()

def add_city(db,city):
    with sqlite3.connect(db) as con:
        con.execute("INSERT OR IGNORE INTO cities(city) VALUES(?)",(city,))
        con.commit()

def list_cities(db):
    with sqlite3.connect(db) as con:
        return [r[0] for r in con.execute("SELECT city FROM cities ORDER BY city").fetchall()]

def add_room(db,city,room):
    add_city(db,city)
    with sqlite3.connect(db) as con:
        con.execute("INSERT OR IGNORE INTO rooms(city,room) VALUES(?,?)",(city,room))
        con.commit()

def list_rooms(db,city):
    if not city: return []
    with sqlite3.connect(db) as con:
        return [r[0] for r in con.execute("SELECT room FROM rooms WHERE city=? ORDER BY room",(city,)).fetchall()]
