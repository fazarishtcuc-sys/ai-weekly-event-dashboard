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
init_db(DB)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@600;700;800&display=swap');
html, body, [class*="css"] {font-family:'DM Sans',sans-serif}
.stApp{background:#f3f6fb}
.block-container{padding-top:1.35rem;max-width:1600px}
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
        if isinstance(dates, tuple) and len(dates)==2:
            start,end=dates
        else:
            start=end=dates
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
    st.markdown("**File yang Anda berikan sudah dikenali:** kolom `Event Name`, `Event Date Start`, `Event Date End`, `Provider`, `Vendor`, `Training Support`, `School`, dan `Event Status`.")
    st.stop()

df = st.session_state["events"]
if start > end:
    st.error("Tanggal mulai harus sebelum tanggal akhir.")
    st.stop()

period = filter_events(df,start,end)
if period.empty:
    st.warning("Tidak ada event yang beririsan dengan periode yang dipilih.")
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

total=len(shown)
ongoing=shown["Event Status"].astype(str).str.lower().str.contains("ongoing|in progress",regex=True).sum()
assigned=sum(1 for m in matches.values() if m.get("city") and m.get("room"))
k1,k2,k3=st.columns(3)
for col,label,value in [(k1,"TOTAL EVENT",total),(k2,"ONGOING",int(ongoing)),(k3,"KOTA & RUANGAN TERSIMPAN",f"{assigned}/{total}")]:
    col.markdown(f'<div class="kpi"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div></div>',unsafe_allow_html=True)

st.markdown('<div class="section">📋 Event Schedule</div>',unsafe_allow_html=True)
st.caption(f"Menampilkan {len(shown)} event · {start:%d %b %Y} sampai {end:%d %b %Y} · Sumber: {st.session_state['filename']}")

# Compact overview table
overview_cols=["Event Name","Event Date Start","Event Date End","Event Status","Provider","Vendor","Training Support","School"]
overview=shown[[c for c in overview_cols if c in shown.columns]].copy()
overview=overview.rename(columns={"Event Name":"Nama Event","Event Date Start":"Mulai","Event Date End":"Selesai","Event Status":"Status","Provider":"TCU Area","Training Support":"Training Support"})
st.dataframe(overview,use_container_width=True,hide_index=True,
             column_config={"Mulai":st.column_config.DateColumn("Mulai",format="DD MMM YYYY"),
                            "Selesai":st.column_config.DateColumn("Selesai",format="DD MMM YYYY")})

st.markdown('<div class="section">📍 Pengaturan Kota & Ruangan</div>',unsafe_allow_html=True)
st.caption("Pilih Kota dan Ruangan untuk setiap event, lalu tekan Simpan. Sistem akan mencoba mengenali event yang sama meskipun Event ID berubah.")
master_cities=list_cities(DB)
if not master_cities:
    master_cities=["Jakarta","Bandung","Semarang","Makassar","Yogyakarta","Surabaya"]
    st.info("Belum ada master kota tersimpan. Anda dapat menambahkannya di panel kiri → Master Kota & Ruangan.")

for idx,row in shown.iterrows():
    m=matches[idx]
    title=f"{row.get('Event Name','Event tanpa nama')} · {row.get('Event Date Start').strftime('%d %b %Y') if pd.notna(row.get('Event Date Start')) else '-'}"
    with st.expander(title,expanded=False):
        x,y,z=st.columns([1,1,2])
        x.write(f"**Event ID:** {row.get('Event ID','-')}")
        y.write(f"**School:** {row.get('School','-')}")
        z.write(f"**Provider / TCU Area:** {row.get('Provider','-')}")
        st.write(f"**Vendor:** {row.get('Vendor','-')}  ·  **Training Support:** {row.get('Training Support','-')}")
        if m["status"]=="ambiguous":
            st.warning("Ada lebih dari satu event lama yang mirip. Pilihan sebelumnya tidak diterapkan otomatis; periksa dan simpan pilihan untuk event ini.")
        elif m["status"]=="matched":
            st.success("Pilihan Kota/Ruangan sebelumnya berhasil dikenali.")
        cities=list_cities(DB)
        if not cities: cities=master_cities
        old_city=m.get("city","")
        city_options=[""]+cities
        if old_city and old_city not in city_options: city_options.insert(1,old_city)
        city=st.selectbox("Kota",city_options,index=city_options.index(old_city) if old_city in city_options else 0,key=f"city_{idx}")
        rooms=list_rooms(DB,city) if city else []
        old_room=m.get("room","")
        room_options=[""]+rooms
        if old_room and old_room not in room_options: room_options.insert(1,old_room)
        room=st.selectbox("Ruangan",room_options,index=room_options.index(old_room) if old_room in room_options else 0,key=f"room_{idx}",disabled=not city)
        # Keep selections as pending edits until the global Save button is pressed.
        if "pending_choices" not in st.session_state:
            st.session_state["pending_choices"] = {}
        st.session_state["pending_choices"][str(idx)] = {
            "row": row.to_dict(),
            "city": city,
            "room": room,
            "event_name": str(row.get("Event Name", "Event tanpa nama")),
        }

# Global save: persist all selected City/Room values together.
st.divider()
st.markdown('<div class="section">💾 Simpan Perubahan</div>', unsafe_allow_html=True)
pending = st.session_state.get("pending_choices", {})
if st.button("💾 Simpan Semua Perubahan", type="primary", use_container_width=False):
    invalid = [
        item["event_name"] for item in pending.values()
        if not item["city"] or not item["room"]
    ]
    if invalid:
        st.error(
            f"Masih ada {len(invalid)} event yang belum memiliki Kota dan Ruangan. "
            "Lengkapi keduanya sebelum menyimpan."
        )
    else:
        saved_count = 0
        for item in pending.values():
            save_choice(DB, item["row"], item["city"], item["room"])
            saved_count += 1
        st.session_state["pending_choices"] = {}
        st.success(f"Berhasil menyimpan {saved_count} pilihan Kota dan Ruangan ke database.")
        st.rerun()

# Re-fetch selections for export
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
