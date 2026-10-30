# AI Weekly Event Dashboard V1.1

## Jalankan lokal
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Kolom sumber yang digunakan
`Event ID`, `Event Name`, `Event Category`, `Provider`, `Vendor`, `Training Support`, `Event Status`, `School`, `Event Date Start`, `Event Date End`.

- `Provider` ditampilkan sebagai TCU Area/Provider sesuai data sumber.
- `Vendor` adalah vendor pelatihan.
- Event yang tanggalnya beririsan dengan periode akan ditampilkan.
- Event ID tidak digunakan sebagai identitas permanen.
- Pilihan Kota/Ruangan disimpan terpisah dalam SQLite.
- Pencocokan otomatis memakai Nama Event + School + Vendor, dan tanggal sebagai fingerprint utama. Jika kandidat lebih dari satu, sistem meminta pemeriksaan manual.

## Deploy
Upload seluruh isi folder ke GitHub, lalu deploy `app.py` melalui Streamlit Community Cloud.

**Penting:** SQLite lokal pada hosting tidak selalu persisten saat instance di-restart. Untuk penggunaan tim dan penyimpanan permanen, pindahkan database ke Supabase/PostgreSQL pada tahap berikutnya.


## Simpan Semua Perubahan
V1.2 menyediakan tombol **Simpan Semua Perubahan**. Pilihan Kota dan Ruangan yang sedang tampil dikumpulkan sebagai perubahan sementara, lalu disimpan sekaligus ke SQLite saat tombol ditekan. Setelah tersimpan, pilihan akan dicocokkan kembali saat file Excel baru diunggah.

Catatan: pada hosting Streamlit yang filesystem-nya sementara, SQLite lokal dapat hilang saat instance dibuat ulang. Untuk penyimpanan permanen lintas deploy/restart dan penggunaan banyak pegawai, gunakan database terkelola seperti Supabase/PostgreSQL.
