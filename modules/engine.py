import pandas as pd
import sqlite3
import re
import hashlib
from pathlib import Path


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def norm(v):
    """Normalisasi teks untuk pencocokan data."""
    if pd.isna(v):
        return ""
    return re.sub(r"\s+", " ", str(v).strip().lower())


def clean_value(v):
    """Mengubah nilai kosong atau 0 menjadi string kosong."""
    if pd.isna(v):
        return ""

    value = str(v).strip()

    if value.lower() in {"", "0", "0.0", "nan", "none"}:
        return ""

    return value


def dt(v):
    """Mengubah tanggal menjadi format YYYY-MM-DD."""
    if pd.isna(v) or v == "":
        return ""

    parsed = pd.to_datetime(v, errors="coerce", dayfirst=True)

    if pd.isna(parsed):
        return ""

    return parsed.strftime("%Y-%m-%d")


def normalize_columns(df):
    """
    Mendukung header Master Data.xlsx berbahasa Indonesia
    maupun header versi lama berbahasa Inggris.
    """

    aliases = {
        "Event ID": ["Event ID", "ID Event", "ID"],
        "Event Name": ["Event Name", "Nama Event", "Nama Acara"],
        "School": ["School", "Sekolah"],
        "Event Status": ["Event Status", "Status Event", "Status"],
        "Event Date Start": [
            "Event Date Start",
            "Tanggal Mulai",
            "Tanggal Pelaksanaan"
        ],
        "Event Date End": [
            "Event Date End",
            "Tanggal Akhir",
            "Tanggal Selesai"
        ],
        "Provider": ["Provider", "Penyedia"],
        "Training Support": ["Training Support", "TS"],
        "Room": ["Room", "Ruangan"],
        "City": ["City", "Lokasi", "Kota"],
    }

    # Pemetaan berdasarkan nama kolom yang dinormalisasi
    existing = {
        norm(column): column
        for column in df.columns
    }

    rename_map = {}

    for standard_name, possible_names in aliases.items():
        for possible_name in possible_names:
            source_name = existing.get(norm(possible_name))
            if source_name is not None:
                rename_map[source_name] = standard_name
                break

    df = df.rename(columns=rename_map)

    return df


# ---------------------------------------------------------
# Load Excel
# ---------------------------------------------------------

def load_event_file(upload):
    """
    Membaca Master Data.xlsx atau file Excel versi lama.
    Header Indonesia akan dinormalisasi ke nama kolom internal.
    """

    xls = pd.ExcelFile(upload)

    preferred = ["Sheet1"]
    sheet = next(
        (s for s in preferred if s in xls.sheet_names),
        xls.sheet_names[0]
    )

    df = pd.read_excel(xls, sheet_name=sheet)
    df = normalize_columns(df)

    required = [
        "Event Name",
        "Event Date Start",
        "Event Date End"
    ]

    missing = [c for c in required if c not in df.columns]

    if missing:
        raise ValueError(
            "Kolom wajib tidak ditemukan: "
            + ", ".join(missing)
            + ". Pastikan file memiliki kolom Nama Event, "
              "Tanggal Mulai, dan Tanggal Akhir."
        )

    # Kolom opsional
    optional_columns = [
        "Event ID",
        "School",
        "Event Status",
        "Provider",
        "Training Support",
        "City",
        "Room",
    ]

    for column in optional_columns:
        if column not in df.columns:
            df[column] = ""

    # Membersihkan teks
    text_columns = [
        "Event ID",
        "Event Name",
        "School",
        "Event Status",
        "Provider",
        "Training Support",
        "City",
        "Room",
    ]

    for column in text_columns:
        df[column] = df[column].apply(clean_value)

    # Nilai 0 pada Lokasi/Ruangan dianggap kosong
    df["City"] = df["City"].apply(clean_value)
    df["Room"] = df["Room"].apply(clean_value)

    # Parsing tanggal
    df["Event Date Start"] = (
        pd.to_datetime(
            df["Event Date Start"],
            errors="coerce",
            dayfirst=True
        )
        .dt.normalize()
    )

    df["Event Date End"] = (
        pd.to_datetime(
            df["Event Date End"],
            errors="coerce",
            dayfirst=True
        )
        .dt.normalize()
    )

    # Buang baris tanpa nama event atau tanggal valid
    df = df.dropna(
        subset=[
            "Event Name",
            "Event Date Start",
            "Event Date End"
        ]
    ).copy()

    df = df[df["Event Name"].astype(str).str.strip() != ""]

    return df, sheet


# ---------------------------------------------------------
# Date filtering
# ---------------------------------------------------------

def filter_events(df, start, end):
    """
    Filter berdasarkan Tanggal Mulai event saja,
    dengan tanggal awal dan akhir filter bersifat inklusif.
    """

    start_date = pd.Timestamp(start).date()
    end_date = pd.Timestamp(end).date()

    event_start = (
        pd.to_datetime(
            df["Event Date Start"],
            errors="coerce"
        )
        .dt.date
    )

    mask = (
        event_start.notna()
        & (event_start >= start_date)
        & (event_start <= end_date)
    )

    return df.loc[mask].copy()


# ---------------------------------------------------------
# SQLite database
# ---------------------------------------------------------

def init_db(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(path) as con:
        # Kolom vendor dipertahankan agar kompatibel dengan DB V1.3.
        # Secara internal kolom ini menyimpan Training Support.
        con.execute("""
            CREATE TABLE IF NOT EXISTS choices(
                fingerprint TEXT PRIMARY KEY,
                event_name TEXT,
                school TEXT,
                vendor TEXT,
                provider TEXT,
                start_date TEXT,
                end_date TEXT,
                city TEXT,
                room TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS cities(
                city TEXT PRIMARY KEY
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS rooms(
                city TEXT,
                room TEXT,
                PRIMARY KEY(city, room)
            )
        """)

        con.commit()


# ---------------------------------------------------------
# Event identity / matching
# ---------------------------------------------------------

def fingerprint(row):
    """
    Identitas event tidak menggunakan Event ID.
    Vendor juga tidak digunakan.
    """

    bits = [
        norm(row.get("Event Name")),
        norm(row.get("School")),
        norm(row.get("Provider")),
        norm(row.get("Training Support")),
        dt(row.get("Event Date Start")),
        dt(row.get("Event Date End")),
    ]

    return hashlib.sha256(
        "|".join(bits).encode()
    ).hexdigest()


def find_saved_choice(db, row):
    init_db(db)

    fp = fingerprint(row)

    event_name = norm(row.get("Event Name"))
    school = norm(row.get("School"))
    provider = norm(row.get("Provider"))
    training_support = norm(row.get("Training Support"))

    with sqlite3.connect(db) as con:
        # Pencocokan identitas lengkap
        exact = con.execute(
            """
            SELECT city, room
            FROM choices
            WHERE fingerprint = ?
            """,
            (fp,)
        ).fetchone()

        if exact:
            return {
                "status": "matched",
                "city": clean_value(exact[0]),
                "room": clean_value(exact[1]),
            }

        # Fallback jika tanggal berubah:
        # Nama Event + School + Provider + Training Support
        candidates = con.execute(
            """
            SELECT city, room
            FROM choices
            WHERE event_name = ?
              AND school = ?
              AND provider = ?
              AND vendor = ?
            """,
            (
                event_name,
                school,
                provider,
                training_support
            )
        ).fetchall()

    if len(candidates) == 1:
        return {
            "status": "matched",
            "city": clean_value(candidates[0][0]),
            "room": clean_value(candidates[0][1]),
        }

    if len(candidates) > 1:
        return {
            "status": "ambiguous",
            "city": "",
            "room": "",
        }

    return {
        "status": "new",
        "city": "",
        "room": "",
    }


def save_choice(db, row, city, room):
    init_db(db)

    event_name = norm(row.get("Event Name"))
    school = norm(row.get("School"))
    provider = norm(row.get("Provider"))
    training_support = norm(row.get("Training Support"))

    with sqlite3.connect(db) as con:
        con.execute(
            """
            INSERT INTO choices(
                fingerprint,
                event_name,
                school,
                vendor,
                provider,
                start_date,
                end_date,
                city,
                room
            )
            VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(fingerprint) DO UPDATE SET
                city = excluded.city,
                room = excluded.room,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                fingerprint(row),
                event_name,
                school,
                training_support,  # disimpan di kolom legacy vendor
                provider,
                dt(row.get("Event Date Start")),
                dt(row.get("Event Date End")),
                clean_value(city),
                clean_value(room),
            )
        )

        con.commit()


# ---------------------------------------------------------
# City and room master
# ---------------------------------------------------------

def add_city(db, city):
    city = clean_value(city)

    if not city:
        return

    init_db(db)

    with sqlite3.connect(db) as con:
        con.execute(
            "INSERT OR IGNORE INTO cities(city) VALUES(?)",
            (city,)
        )
        con.commit()


def list_cities(db):
    init_db(db)

    with sqlite3.connect(db) as con:
        return [
            row[0]
            for row in con.execute(
                "SELECT city FROM cities ORDER BY city"
            ).fetchall()
        ]


def add_room(db, city, room):
    city = clean_value(city)
    room = clean_value(room)

    if not city or not room:
        return

    add_city(db, city)

    with sqlite3.connect(db) as con:
        con.execute(
            """
            INSERT OR IGNORE INTO rooms(city, room)
            VALUES(?,?)
            """,
            (city, room)
        )
        con.commit()


def list_rooms(db, city):
    city = clean_value(city)

    if not city:
        return []

    init_db(db)

    with sqlite3.connect(db) as con:
        return [
            row[0]
            for row in con.execute(
                """
                SELECT room
                FROM rooms
                WHERE city = ?
                ORDER BY room
                """,
                (city,)
            ).fetchall()
        ]
