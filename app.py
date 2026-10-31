from datetime import date, timedelta
from pathlib import Path
import pandas as pd
import streamlit as st
from modules.engine import (
    add_city,
    add_room,
    filter_events,
    find_saved_choice,
    init_db,
    list_cities,
    list_rooms,
    save_choice,
)
from modules.exporter import export_workbook

# 1. Konfigurasi Halaman (Hanya 1 kali di paling atas)
st.set_page_config(
    page_title="Weekly Event Dashboard",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB = Path("data/event_choices.db")
DB.parent.mkdir(exist_ok=True)
init_db(DB)

# ---------------------------------------------------------
# MODE FULL SCREEN DASHBOARD & CSS KUSTOM
# ---------------------------------------------------------
if "dashboard_fullscreen" not in st.session_state:
    st.session_state["dashboard_fullscreen"] = False

# CSS Kustom untuk merapatkan layout agar pas 1 layar
fullscreen_css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@600;700;800&display=swap');
html, body, [class*="css"] {font-family:'DM Sans',sans-serif}
.stApp{background:#f3f6fb}

/* Merapatkan padding container utama */
.block-container{
    padding-top: 0.6rem !important;
    padding-bottom: 1rem !important;
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
    max-width: 100%;
}

/* Merapatkan jarak vertikal antar blok elemen Streamlit */
div[data-testid="stVerticalBlock"] > div {
    gap: 0.3rem !important;
}

.hero{background:linear-gradient(115deg,#102b4e,#1d5286 68%,#2878b4);padding:14px 20px;border-radius:12px;color:#fff;margin-bottom:8px}
.hero h1{font-family:Manrope,sans-serif;color:#fff;font-size:22px;margin:0}
.hero p{color:#d9e9f7;margin:3px 0 0;font-size:12px}

.kpi{background:#fff;border:1px solid #e4eaf2;border-radius:12px;padding:12px 14px;min-height:75px;box-shadow:0 2px 8px #15395d0a}
.kpi-label{color:#738196;font-size:10px;font-weight:700;letter-spacing:.5px}
.kpi-value{font-family:Manrope,sans-serif;color:#173e67;font-size:24px;font-weight:800;margin-top:2px}

.section{font-family:Manrope,sans-serif;color:#173e67;font-size:15px;font-weight:800;margin:10px 0 4px}
.stButton>button,.stDownloadButton>button{border-radius:8px;font-weight:700;padding: 0.3rem 0.8rem;}
div[data-testid="stSidebar"]{background:#edf2f8}
</style>
"""

if st.session_state["dashboard_fullscreen"]:
    fullscreen_css += """
    <style>
        [data-testid="stSidebar"] { display: none; }
        [data-testid="stHeader"] { display: none; }
    </style>
    """

st.markdown(fullscreen_css, unsafe_allow_html=True)

# Header Hero Ringkas
st.markdown(
    """
<div class="hero">
<h1>📅 WEEKLY EVENT DASHBOARD</h1>
<p>Training Event Schedule · Monitoring jadwal, TCU Area, Kota, dan Ruangan</p>
</div>
""",
    unsafe_allow_html=True,
)

with st.sidebar:
  st.markdown("## 📂 Upload Data")
  file = st.file_uploader("Upload Excel terbaru", type=["xlsx", "xlsm"])
  st.caption("Gunakan file report post-event.")
  st.divider()
  st.markdown("## 🗓️ Periode")
  mode = st.radio("Jenis periode", ["Mingguan", "Rentang tanggal"])
  today = date.today()
  if mode == "Mingguan":
    start = st.date_input(
        "Awal minggu", today - timedelta(days=today.weekday())
    )
    end = start + timedelta(days=6)
    st.caption(f"{start:%d %b %Y} – {end:%d %b %Y}")
  else:
    dates = st.date_input(
        "Pilih rentang tanggal",
        (
            today - timedelta(days=today.weekday()),
            today + timedelta(days=6),
        ),
    )
    if isinstance(dates, (tuple, list)) and len(dates) == 2:
      start, end = dates[0], dates[1]
    elif isinstance(dates, (tuple, list)) and len(dates) == 1:
      start = end = dates[0]
    else:
      start = end = dates
  st.divider()
  with st.expander("⚙️ Master Kota & Ruangan"):
    new_city = st.text_input("Nama kota", key="new_city")
    if st.button("Tambah Kota"):
      if new_city.strip():
        add_city(DB, new_city.strip())
        st.success("Kota ditambahkan.")
        st.rerun()
    cities = list_cities(DB)
    selected_city = st.selectbox("Pilih kota", [""] + cities)
    new_room = st.text_input("Nama ruangan", key="new_room")
    if st.button("Tambah Ruangan"):
      if selected_city and new_room.strip():
        add_room(DB, selected_city, new_room.strip())
        st.success("Ruangan ditambahkan.")
        st.rerun()

if file is not None:
  try:
    df, sheet = load_event_file(file)
    st.session_state["events"] = df
    st.session_state["filename"] = file.name
    st.session_state["sheet"] = sheet
  except Exception as e:
    st.error(str(e))
    st.stop()

if "events" not in st.session_state:
  st.info("Upload file Excel melalui panel kiri untuk mulai melihat dashboard.")
  st.stop()

df = st.session_state["events"]
required_columns = [
    "Event Name",
    "Event Date Start",
    "Event Date End",
    "Provider",
    "Training Support",
    "School",
    "Event Status",
]
missing_columns = [col for col in required_columns if col not in df.columns]
if missing_columns:
  st.error("Kolom tidak ditemukan: " + ", ".join(missing_columns))
  st.stop()

if start > end:
  st.error("Tanggal mulai harus sebelum tanggal akhir.")
  st.stop()

period = filter_events(df, start, end)
if period.empty:
  st.warning("Tidak ada event dalam periode yang dipilih.")
  st.stop()

# Filters Sejajar
c1, c2, c3 = st.columns([1, 1, 1.2], gap="small")
provider_vals = sorted(
    {str(x).strip() for x in period["Provider"].dropna() if str(x).strip()}
)
school_vals = sorted(
    {str(x).strip() for x in period["School"].dropna() if str(x).strip()}
)
status_vals = sorted(
    {str(x).strip() for x in period["Event Status"].dropna() if str(x).strip()}
)

with c1:
  provider_filter = st.multiselect("TCU Area", provider_vals, default=[])
with c2:
  school_filter = st.multiselect("School", school_vals, default=[])
with c3:
  status_filter = st.multiselect("Status", status_vals, default=[])

shown = period.copy()
if provider_filter:
  shown = shown[shown["Provider"].astype(str).isin(provider_filter)]
if school_filter:
  shown = shown[shown["School"].astype(str).isin(school_filter)]
if status_filter:
  shown = shown[shown["Event Status"].astype(str).isin(status_filter)]
if shown.empty:
  st.warning("Tidak ada data sesuai filter.")
  st.stop()

matches = {}
for idx, row in shown.iterrows():
  matches[idx] = find_saved_choice(DB, row)

# Tombol Full Screen
if st.session_state["dashboard_fullscreen"]:
  if st.button("✕ Keluar Full Screen"):
    st.session_state["dashboard_fullscreen"] = False
    st.rerun()
else:
  if st.button("⛶ Mode Full Screen Dashboard"):
    st.session_state["dashboard_fullscreen"] = True
    st.rerun()

# ---------------------------------------------------------
# KPI DASHBOARD
# ---------------------------------------------------------
total = len(shown)
ongoing = (
    shown["Event Status"]
    .astype(str)
    .str.lower()
    .str.contains(r"ongoing|in progress", regex=True, na=False)
    .sum()
)
ts_values = (
    shown["Training Support"]
    .fillna("")
    .astype(str)
    .str.split(r"[,;\n]+", regex=True)
    .explode()
    .str.strip()
)
ts_values = ts_values[
    (ts_values != "") & (~ts_values.str.lower().isin(["0", "0.0", "nan", "none"]))
]
total_ts = ts_values.str.casefold().nunique()
assigned = sum(
    1 for m in matches.values() if m.get("city") and m.get("room")
)

k1, k2, k3, k4 = st.columns(4)
kpis = [
    (k1, "TOTAL EVENT", total, "#173E67"),
    (k2, "EVENT BERJALAN", int(ongoing), "#287348"),
    (k3, "TOTAL TS", total_ts, "#6745A0"),
    (k4, "KOTA & RUANGAN", f"{assigned}/{total}", "#9A641F"),
]

for col, label, value, color in kpis:
  col.markdown(
      f"""
        <div class="kpi">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value" style="color:{color}">{value}</div>
        </div>
        """,
      unsafe_allow_html=True,
  )

# ---------------------------------------------------------
# TABEL EVENT SCHEDULE (Dibatasi Tingginya)
# ---------------------------------------------------------
st.markdown('<div class="section">📋 Event Schedule</div>', unsafe_allow_html=True)
st.caption(
    f"Menampilkan {len(shown)} event · {start:%d %b %Y} - {end:%d %b %Y}"
)

overview_cols = [
    "Event ID",
    "Event Name",
    "Event Date Start",
    "Event Date End",
    "Event Status",
    "Provider",
    "Training Support",
    "School",
]
overview = shown[[c for c in overview_cols if c in shown.columns]].copy()
overview.insert(0, "No.", range(1, len(overview) + 1))
overview["Kota"] = [matches[i].get("city", "") for i in shown.index]
overview["Ruangan"] = [matches[i].get("room", "") for i in shown.index]

overview = overview.rename(
    columns={
        "Event ID": "ID Event",
        "Event Name": "Nama Event",
        "Event Date Start": "Mulai",
        "Event Date End": "Selesai",
        "Event Status": "Status",
        "Provider": "TCU Area",
    }
)

# Tinggi tabel dibatasi 220-250px agar pas dalam 1 layar penuh
st.dataframe(
    overview,
    use_container_width=True,
    height=230,
    hide_index=True,
    column_config={
        "ID Event": st.column_config.TextColumn("ID", width="small"),
        "Nama Event": st.column_config.TextColumn("Nama Event", width="large"),
        "Mulai": st.column_config.DateColumn("Mulai", format="DD MMM YYYY"),
        "Selesai": st.column_config.DateColumn("Selesai", format="DD MMM YYYY"),
    },
)

# ---------------------------------------------------------
# PENGATURAN KOTA & RUANGAN (Dimasukkan ke Expander)
# ---------------------------------------------------------
master_cities = list_cities(DB) or [
    "Jakarta",
    "Bandung",
    "Semarang",
    "Makassar",
    "Yogyakarta",
    "Surabaya",
]

st.session_state["pending_choices"] = {}

with st.expander(
    "⚙️ Atur Kota & Ruangan Per Event (Klik untuk ubah)", expanded=False
):
  st.caption("Pilih Kota dan Ruangan untuk masing-masing event di bawah ini.")
  h1, h2, h3 = st.columns([5.2, 1.7, 2.1])
  h1.markdown("**Nama Event**")
  h2.markdown("**Kota**")
  h3.markdown("**Ruangan**")
  st.divider()

  for idx, row in shown.iterrows():
    m = matches[idx]
    event_name = str(row.get("Event Name", "Event"))
    old_city = m.get("city", "")
    city_options = [""] + master_cities
    if old_city and old_city not in city_options:
      city_options.insert(1, old_city)

    r1, r2, r3 = st.columns([5.2, 1.7, 2.1], vertical_alignment="center")
    with r1:
      st.markdown(f"**{event_name}**")
    with r2:
      city = st.selectbox(
          "Kota",
          city_options,
          index=city_options.index(old_city) if old_city in city_options else 0,
          key=f"city_inline_{idx}",
          label_visibility="collapsed",
      )
    with r3:
      room_list = list_rooms(DB, city) if city else []
      old_room = m.get("room", "") if city == old_city else ""
      room_options = [""] + room_list
      room = st.selectbox(
          "Ruangan",
          room_options,
          index=room_options.index(old_room) if old_room in room_options else 0,
          key=f"room_inline_{idx}_{city or 'none'}",
          label_visibility="collapsed",
          disabled=not city or not room_list,
      )

    st.session_state["pending_choices"][str(idx)] = {
        "row": row.to_dict(),
        "city": city,
        "room": room,
        "event_name": event_name,
    }

  if st.button("💾 Simpan Perubahan Kota/Ruangan", use_container_width=True):
    saved_count = 0
    for event_key, values in st.session_state.get(
        "pending_choices", {}
    ).items():
      row = values.get("row")
      if row is not None:
        save_choice(
            DB,
            row,
            str(values.get("city", "")).strip(),
            str(values.get("room", "")).strip(),
        )
        saved_count += 1
    st.success(f"Berhasil menyimpan {saved_count} perubahan.")
    st.rerun()

# ---------------------------------------------------------
# DOWNLOAD
# ---------------------------------------------------------
export = shown.copy()
cities_out, rooms_out = [], []
for _, row in export.iterrows():
  m = find_saved_choice(DB, row)
  cities_out.append(m.get("city", ""))
  rooms_out.append(m.get("room", ""))
export["Kota Pilihan"] = cities_out
export["Ruangan Pilihan"] = rooms_out

col_dl1, col_dl2 = st.columns([3, 1])
with col_dl1:
  st.caption("Download file Excel hasil monitoring lengkap.")
with col_dl2:
  blob = export_workbook(export, start, end, st.session_state["filename"])
  st.download_button(
      "📥 Download Excel",
      blob,
      file_name=f"Weekly_Event_Dashboard_{start:%Y%m%d}_{end:%Y%m%d}.xlsx",
      mime=(
          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      ),
      type="primary",
  )
