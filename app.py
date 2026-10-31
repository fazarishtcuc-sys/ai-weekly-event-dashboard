import streamlit as st
import pandas as pd
from datetime import date, timedelta
from pathlib import Path
from modules.engine import (
    load_event_file, filter_events, init_db, find_saved_choice,
    save_choice, list_cities, list_rooms, add_room, add_city
)
from modules.exporter import export_workbook

st.set_page_config(page_title="Weekly Event Dashboard", page_icon="📅", layout="wide")
DB = Path("data/event_choices.db")
DB.parent.mkdir(exist_ok=True)

# ---------------------------------------------------------
# MODE FULL SCREEN DASHBOARD
# ---------------------------------------------------------

if "dashboard_fullscreen" not in st.session_state:
    st.session_state["dashboard_fullscreen"] = False

if st.session_state["dashboard_fullscreen"]:
    st.markdown("""
    <style>
        [data-testid="stSidebar"] {
            display: none;
        }
        [data-testid="stHeader"] {
            display: none;
        }
        .block-container {
            max-width: 100% !important;
            padding-top: 0.5rem !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }
    </style>
    """, unsafe_allow_html=True)

init_db(DB)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@600;700;800&display=swap');
html, body, [class*="css"] {font-family:'DM Sans',sans-serif}
.stApp{background:#f3f6fb}
.block-container{
    padding-top:1rem;
    padding-bottom:2rem;
    max-width:100%;
}
.hero{background:linear-gradient(115deg,#102b4e,#1d5286 68%,#2878b4);padding:26px 30px;border-radius:18px;color:#fff;margin-bottom:18px}
.hero h1{font-family:Manrope,sans-serif;color:#fff;font-size:27px;margin:0}
.hero p{color:#d9e9f7;margin:5px 0 0;font-size:14px}
.kpi{background:#fff;border:1px solid #e4eaf2;border-radius:15px;padding:17px 19px;min-height:96px;box-shadow:0 3px 12px #15395d0a}
.kpi-label{color:#738196;font-size:11px;font-weight:700;letter-spacing:.6px}
.kpi-value{font-family:Manrope,sans-serif;color:#173e67;font-size:29px;font-weight:800;margin-top:5px}
.section{font-family:Manrope,sans-serif;color:#173e67;font-size:19px;font-weight:800;margin:18px 0 8px}
div[data-testid="stExpander"]{background:white;border:1px solid #e5ebf3;border-radius:12px}
.stButton>button,.stDownloadButton>button{border-radius:10px;font-weight:700}
div[data-testid="stSidebar"]{background:#edf2f8}
</style>
<div class="hero">
<h1>📅 WEEKLY EVENT DASHBOARD</h1>
<p>Training Event Schedule · Monitoring jadwal, TCU Area, Kota, dan Ruangan</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## 📂 Upload Data")
    file = st.file_uploader("Upload Excel terbaru", type=["xlsx","xlsm"])
    st.caption("Gunakan file report post-event yang diunduh dari sumber Anda.")
    st.divider()
    st.markdown("## 🗓️ Periode")
    mode = st.radio("Jenis periode", ["Mingguan","Rentang tanggal"])
    today = date.today()
    if mode == "Mingguan":
        start = st.date_input("Awal minggu", today - timedelta(days=today.weekday()))
        end = start + timedelta(days=6)
        st.caption(f"{start:%d %b %Y} – {end:%d %b %Y}")
    else:
        dates = st.date_input("Pilih tanggal mulai dan akhir",
                              (today-timedelta(days=today.weekday()), today+timedelta(days=6)))
        if isinstance(dates, (tuple, list)) and len(dates) == 2:
            start, end = dates[0], dates[1]
        elif isinstance(dates, (tuple, list)) and len(dates) == 1:
            start = end = dates[0]
        else:
            start = end = dates
    st.divider()
    with st.expander("⚙️ Master Kota & Ruangan"):
        st.caption("Tambahkan pilihan yang akan tersedia untuk semua event.")
        new_city = st.text_input("Nama kota", key="new_city")
        if st.button("Tambah Kota"):
            if new_city.strip():
                add_city(DB,new_city.strip())
                st.success("Kota ditambahkan.")
                st.rerun()
        cities = list_cities(DB)
        selected_city = st.selectbox("Pilih kota untuk menambah ruangan", [""]+cities)
        new_room = st.text_input("Nama ruangan", key="new_room")
        if st.button("Tambah Ruangan"):
            if selected_city and new_room.strip():
                add_room(DB,selected_city,new_room.strip())
                st.success("Ruangan ditambahkan.")
                st.rerun()

if file is not None:
    try:
        df, sheet = load_event_file(file)
        st.session_state["events"] = df
        st.session_state["filename"] = file.name
        st.session_state["sheet"] = sheet
        st.success(f"File berhasil dibaca · {file.name} · Sheet: {sheet}")
    except Exception as e:
        st.error(str(e))
        st.stop()

if "events" not in st.session_state:
    st.info("Upload file Excel melalui panel kiri untuk mulai melihat dashboard.")
    st.markdown("**File yang Anda berikan sudah dikenali:** kolom `Event Name`, `Event Date Start`, `Event Date End`, `Provider`, `Training Support`, `School`, dan `Event Status`.")
    st.stop()

df = st.session_state["events"]
if start > end:
    st.error("Tanggal mulai harus sebelum tanggal akhir.")
    st.stop()

period = filter_events(df,start,end)
if period.empty:
    st.warning("Tidak ada event yang tanggal mulainya berada dalam periode yang dipilih.")
    st.stop()

# Filters
c1,c2,c3 = st.columns([1.2,1.2,1.5])
provider_vals = sorted({str(x).strip() for x in period["Provider"].dropna() if str(x).strip()})
school_vals = sorted({str(x).strip() for x in period["School"].dropna() if str(x).strip()})
status_vals = sorted({str(x).strip() for x in period["Event Status"].dropna() if str(x).strip()})
with c1:
    provider_filter = st.multiselect("TCU Area / Provider",provider_vals,default=[])
with c2:
    school_filter = st.multiselect("School",school_vals,default=[])
with c3:
    status_filter = st.multiselect("Status Event",status_vals,default=[])

shown = period.copy()
if provider_filter: shown=shown[shown["Provider"].astype(str).isin(provider_filter)]
if school_filter: shown=shown[shown["School"].astype(str).isin(school_filter)]
if status_filter: shown=shown[shown["Event Status"].astype(str).isin(status_filter)]
if shown.empty:
    st.warning("Tidak ada data yang sesuai dengan filter.")
    st.stop()

# Prepare match state
matches={}
for idx,row in shown.iterrows():
    matches[idx]=find_saved_choice(DB,row)

# Tombol mode layar penuh
if st.session_state["dashboard_fullscreen"]:
    if st.button("✕ Keluar Full Screen Dashboard"):
        st.session_state["dashboard_fullscreen"] = False
        st.rerun()
else:
    if st.button("⛶ Mode Full Screen Dashboard"):
        st.session_state["dashboard_fullscreen"] = True
        st.rerun()


# ---------------------------------------------------------
# KPI DASHBOARD
# ---------------------------------------------------------

# Total event dalam periode dan filter aktif
total = len(shown)

# Total event yang sedang berjalan
ongoing = shown["Event Status"].astype(str).str.lower().str.contains(
    r"ongoing|in progress",
    regex=True,
    na=False
).sum()

# Total Training Support unik yang bertugas
# Mendukung beberapa nama TS dalam satu sel,
# dipisahkan koma, titik koma, atau baris baru.
ts_values = (
    shown["Training Support"]
    .fillna("")
    .astype(str)
    .str.split(r"[,;\n]+", regex=True)
    .explode()
    .str.strip()
)

# Buang nilai kosong dan angka 0
ts_values = ts_values[
    (ts_values != "") &
    (~ts_values.str.lower().isin(["0", "0.0", "nan", "none"]))
]

# Hitung orang unik tanpa membedakan huruf besar/kecil
total_ts = ts_values.str.casefold().nunique()

# Event yang Kota dan Ruangannya sudah tersimpan
assigned = sum(
    1 for m in matches.values()
    if m.get("city") and m.get("room")
)

# Tampilkan 4 kartu KPI
k1, k2, k3, k4 = st.columns(4)

kpis = [
    (k1, "TOTAL EVENT", total, "#173E67"),
    (k2, "EVENT BERJALAN", int(ongoing), "#287348"),
    (k3, "TOTAL TS BERTUGAS", total_ts, "#6745A0"),
    (k4, "KOTA & RUANGAN TERSIMPAN", f"{assigned}/{total}", "#9A641F"),
]

for col, label, value, color in kpis:
    col.markdown(
        f"""
        <div class="kpi">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value" style="color:{color}">
                {value}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

for col,label,value in [(k1,"TOTAL EVENT",total),(k2,"ONGOING",int(ongoing)),(k3,"KOTA & RUANGAN TERSIMPAN",f"{assigned}/{total}")]:
    col.markdown(f'<div class="kpi"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div></div>',unsafe_allow_html=True)

st.markdown('<div class="section">📋 Event Schedule</div>',unsafe_allow_html=True)
st.caption(f"Menampilkan {len(shown)} event · {start:%d %b %Y} sampai {end:%d %b %Y} · Sumber: {st.session_state['filename']}")


# Compact overview table
overview_cols = [
    "Event ID",
    "Event Name",
    "Event Date Start",
    "Event Date End",
    "Event Status",
    "Provider",
    "Training Support",
    "School"
]

overview = shown[
    [c for c in overview_cols if c in shown.columns]
].copy()

# Nomor urut otomatis
overview.insert(0, "No.", range(1, len(overview) + 1))

overview["Kota"] = [
    matches[i].get("city", "") for i in shown.index
]

overview["Ruangan"] = [
    matches[i].get("room", "") for i in shown.index
]

overview = overview.rename(columns={
    "Event ID": "ID Event",
    "Event Name": "Nama Event",
    "Event Date Start": "Mulai",
    "Event Date End": "Selesai",
    "Event Status": "Status",
    "Provider": "TCU Area"
})

st.dataframe(
    overview,
    use_container_width=True,
    hide_index=True,
    column_config={
        "No.": st.column_config.NumberColumn(
            "No.",
            width="small",
            format="%d"
        ),
        "ID Event": st.column_config.TextColumn(
            "ID Event",
            width="small"
        ),
        "Nama Event": st.column_config.TextColumn(
            "Nama Event",
            width="large"
        ),
        "Mulai": st.column_config.DateColumn(
            "Mulai",
            format="DD MMM YYYY"
        ),
        "Selesai": st.column_config.DateColumn(
            "Selesai",
            format="DD MMM YYYY"
        ),
        "Kota": st.column_config.TextColumn(
            "Kota",
            width="medium"
        ),
        "Ruangan": st.column_config.TextColumn(
            "Ruangan",
            width="medium"
        )
    }
)
st.dataframe(overview,use_container_width=True,hide_index=True,
             column_config={
                 "Nama Event":st.column_config.TextColumn("Nama Event",width="large"),
                 "Mulai":st.column_config.DateColumn("Mulai",format="DD MMM YYYY"),
                 "Selesai":st.column_config.DateColumn("Selesai",format="DD MMM YYYY"),
                 "Kota":st.column_config.TextColumn("Kota",width="medium"),
                 "Ruangan":st.column_config.TextColumn("Ruangan",width="medium")
             })

st.markdown('<div class="section">📍 Pengaturan Kota & Ruangan</div>',unsafe_allow_html=True)
st.caption("Kota dan Ruangan diisi langsung di samping nama event. Pilih Kota terlebih dahulu; daftar Ruangan akan mengikuti Kota tersebut.")

master_cities=list_cities(DB)
if not master_cities:
    master_cities=["Jakarta","Bandung","Semarang","Makassar","Yogyakarta","Surabaya"]
    st.info("Master kota belum diisi. Tambahkan kota dan ruangan melalui menu Master Kota & Ruangan di panel kiri.")

# Hanya menampung perubahan untuk event yang sedang tampil pada filter aktif.
st.session_state["pending_choices"] = {}

# Header kolom agar nama event, kota, dan ruangan sejajar.
h1,h2,h3 = st.columns([5.2,1.7,2.1])
h1.markdown("**Nama Event**")
h2.markdown("**Kota**")
h3.markdown("**Ruangan**")
st.divider()

for idx,row in shown.iterrows():
    m = matches[idx]
    event_name = str(row.get("Event Name", "Event tanpa nama"))
    start_value = row.get("Event Date Start")
    start_label = start_value.strftime("%d %b %Y") if pd.notna(start_value) else "-"
    city_list = list_cities(DB) or master_cities
    old_city = m.get("city", "")
    city_options = [""] + city_list
    if old_city and old_city not in city_options:
        city_options.insert(1, old_city)

    r1,r2,r3 = st.columns([5.2,1.7,2.1], vertical_alignment="center")
    with r1:
        st.markdown(f"**{event_name}**")
        st.caption(f"{start_label} · {row.get('Provider','')} · {row.get('School','')}")
        if m.get("status") == "ambiguous":
            st.warning("Pilihan lama belum dapat dicocokkan secara unik. Silakan pilih ulang.")
    with r2:
        city = st.selectbox(
            "Kota",
            city_options,
            index=city_options.index(old_city) if old_city in city_options else 0,
            key=f"city_inline_{idx}",
            label_visibility="collapsed",
            placeholder="Pilih kota"
        )
    with r3:
        room_list = list_rooms(DB, city) if city else []
        old_room = m.get("room", "") if city == old_city else ""
        room_options = [""] + room_list
        if old_room and old_room not in room_options:
            old_room = ""
        room = st.selectbox(
            "Ruangan",
            room_options,
            index=room_options.index(old_room) if old_room in room_options else 0,
            key=f"room_inline_{idx}_{city or 'none'}",
            label_visibility="collapsed",
            disabled=not city or not room_list,
            placeholder="Pilih ruangan"
        )
        if city and not room_list:
            st.caption("Belum ada ruangan untuk kota ini.")
    st.session_state["pending_choices"][str(idx)] = {
        "row": row.to_dict(),
        "city": city,
        "room": room,
        "event_name": event_name,
    }

# ---------------------------------------------------------
# SIMPAN SEMUA PERUBAHAN
# Lokasi dan Ruangan boleh kosong
# ---------------------------------------------------------

if st.button(
    "💾 Simpan Semua Perubahan",
    type="primary",
    use_container_width=True
):
    saved_count = 0
    error_count = 0

    pending = st.session_state.get("pending_choices", {})

    for event_key, values in pending.items():
        row = values.get("row")

        if row is None:
            continue

        city = str(values.get("city", "") or "").strip()
        room = str(values.get("room", "") or "").strip()

        # Nilai 0 dianggap kosong
        if city in ["0", "0.0"]:
            city = ""

        if room in ["0", "0.0"]:
            room = ""

        try:
            save_choice(DB, row, city, room)
            saved_count += 1

        except Exception as e:
            error_count += 1
            st.error(
                f"Gagal menyimpan event "
                f"{values.get('event_name', '')}: {e}"
            )

    if error_count == 0:
        st.success(
            f"Berhasil menyimpan {saved_count} event. "
            "Lokasi dan Ruangan boleh tetap kosong."
        )
        st.session_state["pending_choices"] = {}
        st.rerun()

    else:
        st.warning(
            f"Tersimpan: {saved_count} event. "
            f"Gagal: {error_count} event."
        )


# ---------------------------------------------------------
# RE-FETCH SELECTIONS FOR EXPORT
# ---------------------------------------------------------
export=shown.copy()
cities_out=[]; rooms_out=[]
for _,row in export.iterrows():
    m=find_saved_choice(DB,row)
    cities_out.append(m.get("city",""))
    rooms_out.append(m.get("room",""))
export["Kota Pilihan"]=cities_out
export["Ruangan Pilihan"]=rooms_out

st.divider()
st.markdown('<div class="section">⬇️ Download Hasil</div>',unsafe_allow_html=True)
st.caption("File Excel berisi Dashboard, Event Detail, serta pilihan Kota dan Ruangan.")
blob=export_workbook(export,start,end,st.session_state["filename"])
st.download_button("Download Dashboard Excel",blob,
                   file_name=f"Weekly_Event_Dashboard_{start:%Y%m%d}_{end:%Y%m%d}.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",type="primary")
