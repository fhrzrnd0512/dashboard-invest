import streamlit as st
import pandas as pd
import plotly.express as px
import zipfile
import os
import glob
import re

# ==========================================
# 0. KONFIGURASI HALAMAN & LOGIN
# ==========================================
st.set_page_config(page_title="Dashboard LKPM Sumut", page_icon="📈", layout="wide")

# Kredensial (Hardcoded untuk internal sederhana)
CREDENTIALS = {
    "bps_sumut": "pdrb2026",
    "neraca": "admin123",
    "timneraca": "investw"
}

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    # UI Kartu Login Minimalis
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("<h2 style='text-align: center; color: #00a65a;'>Portal Investasi Sumut</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #888;'>Silakan masuk (Tim Neraca)</p>", unsafe_allow_html=True)
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Masuk Dashboard", use_container_width=True)
            
            if submit:
                if username in CREDENTIALS and CREDENTIALS[username] == password:
                    st.session_state["logged_in"] = True
                    st.rerun()
                else:
                    st.error("Username atau Password salah!")
    st.stop() # Hentikan eksekusi kode di bawah ini jika belum login

# ==========================================
# 1. PERSIAPAN DATA (DENGAN CACHING PINTAR)
# ==========================================

# Fungsi sekarang menerima parameter 'file_list'
@st.cache_data(show_spinner=True)
def load_investasi_data(file_list):
    if not file_list:
        return pd.DataFrame()
    
    df_list = []
    for zfile in file_list:
        with zipfile.ZipFile(zfile, 'r') as z:
            # Cari file csv di dalam zip
            csv_files = [f for f in z.namelist() if f.lower().endswith('.csv')]
            if csv_files:
                with z.open(csv_files[0]) as f:
                    try:
                        df = pd.read_csv(f, sep=',', dtype=str)
                        if df.shape[1] <= 1:
                            f.seek(0)
                            df = pd.read_csv(f, sep=';', dtype=str)
                        
                        # 💡 KUNCI PERBAIKAN: Paksa semua nama kolom jadi huruf kecil dan hapus spasi berlebih
                        df.columns = df.columns.str.lower().str.strip()
                        
                        df_list.append(df)
                    except Exception as e:
                        pass
    
    if not df_list:
        return pd.DataFrame()
        
    df_raw = pd.concat(df_list, ignore_index=True)
    
    # Pembersihan Data
    df_raw['investasi_rp_juta'] = df_raw['investasi_rp_juta'].str.replace(',', '.').astype(float)
    df_raw['tki'] = pd.to_numeric(df_raw['tki'], errors='coerce').fillna(0)
    
    df_raw['periode'] = df_raw['periode'].str.strip()
    df_raw['deskripsi_kbli_2digit'] = df_raw['deskripsi_kbli_2digit'].str.strip()
    
    # Ekstrak Tahun & Triwulan
    df_raw['Tahun'] = df_raw['periode'].str.extract(r'(\d{4})').astype(float)
    df_raw['Triwulan_Num'] = df_raw['periode'].str.extract(r'(?i)(?:triwulan|tw)\s*(\d)')
    df_raw['Triwulan'] = "Q" + df_raw['Triwulan_Num']
    df_raw['Periode_Gabungan'] = df_raw['Tahun'].astype(str).str.replace('.0','') + "-" + df_raw['Triwulan']
    
    # Ekstrak KBLI & Mapping Sektor
    df_raw['Kode_KBLI'] = df_raw['deskripsi_kbli_2digit'].str.extract(r'(\d{2})')
    
    def map_sektor(kbli):
        kbli = str(kbli)
        if kbli == '00': return "00. Bidang Usaha Lainnya"
        if kbli in ['01', '02', '03']: return "A. Pertanian, Kehutanan, dan Perikanan"
        if kbli in ['05', '06', '07', '08', '09']: return "B. Pertambangan dan Penggalian"
        if kbli in [str(i) for i in range(10, 34)]: return "C. Industri Pengolahan"
        if kbli == '35': return "D. Pengadaan Listrik dan Gas"
        if kbli in ['36', '37', '38', '39']: return "E. Pengadaan Air, Pengelolaan Sampah, dsb"
        if kbli in ['41', '42', '43']: return "F. Konstruksi"
        if kbli in ['45', '46', '47']: return "G. Perdagangan Besar dan Eceran"
        if kbli in ['49', '50', '51', '52', '53']: return "H. Transportasi dan Pergudangan"
        if kbli in ['55', '56']: return "I. Penyediaan Akomodasi dan Makan Minum"
        if kbli in ['58', '59', '60', '61', '62', '63']: return "J. Informasi dan Komunikasi"
        if kbli in ['64', '65', '66']: return "K. Jasa Keuangan dan Asuransi"
        if kbli == '68': return "L. Real Estat"
        if kbli in [str(i) for i in range(69, 83)]: return "M, N. Jasa Perusahaan"
        if kbli == '84': return "O. Administrasi Pemerintahan"
        if kbli == '85': return "P. Jasa Pendidikan"
        if kbli in ['86', '87', '88']: return "Q. Jasa Kesehatan dan Kegiatan Sosial"
        if kbli in [str(i) for i in range(90, 100)]: return "R, S, T, U. Jasa Lainnya"
        return "Kategori Tidak Diketahui"
        
    df_raw['Sektor_PDRB'] = df_raw['Kode_KBLI'].apply(map_sektor)
    
    # Rename & Filter Drop NA Tahun / 2020
    df_clean = df_raw.rename(columns={
        'investasi_rp_juta': 'Nilai_Investasi',
        'provinsi': 'Provinsi',
        'kabupaten_kota': 'Wilayah',
        'deskripsi_kbli_2digit': 'Kategori',
        'status_penanaman_modal': 'Status_PM',
        'tki': 'Tenaga_Kerja'
    })
    
    df_clean = df_clean.dropna(subset=['Tahun'])
    #df_clean = df_clean[df_clean['Tahun'] != 2020]
    
    return df_clean

# DETEKSI FILE DIPINDAH KE LUAR FUNGSI CACHE
semua_file_zip = glob.glob("*.zip")
df_master = load_investasi_data(semua_file_zip)

# ==========================================
# 2. SIDEBAR (FILTER)
# ==========================================
st.sidebar.title("Filter Data")

list_tahun = ["Semua"] + sorted(df_master['Tahun'].dropna().unique().tolist(), reverse=True)
f_tahun = st.sidebar.selectbox("Tahun:", list_tahun)

f_triwulan = st.sidebar.selectbox("Triwulan:", ["Semua", "Q1", "Q2", "Q3", "Q4"])
f_status = st.sidebar.selectbox("Status PM:", ["Semua", "PMA", "PMDN"])

list_prov = sorted(df_master['Provinsi'].dropna().unique().tolist())
# Set default Sumatera Utara jika ada
default_prov = ["Sumatera Utara"] if "Sumatera Utara" in list_prov else []
f_provinsi = st.sidebar.multiselect("Provinsi:", list_prov, default=default_prov)

# Filter Dinamis Wilayah & Sektor
df_filtered = df_master.copy()
if f_provinsi:
    df_filtered = df_filtered[df_filtered['Provinsi'].isin(f_provinsi)]

list_wilayah = sorted(df_filtered['Wilayah'].dropna().unique().tolist())
f_wilayah = st.sidebar.multiselect("Kab/Kota:", list_wilayah)

list_sektor = sorted(df_filtered['Sektor_PDRB'].dropna().unique().tolist())
f_sektor = st.sidebar.multiselect("Sektor PDRB:", list_sektor)

if f_sektor:
    df_filtered = df_filtered[df_filtered['Sektor_PDRB'].isin(f_sektor)]

list_kbli = sorted(df_filtered['Kategori'].dropna().unique().tolist())
f_kbli = st.sidebar.multiselect("KBLI 2 Digit:", list_kbli)

# Terapkan semua filter BASE (Tanpa Waktu)
df_base = df_master.copy()
if f_status != "Semua": df_base = df_base[df_base['Status_PM'] == f_status]
if f_provinsi: df_base = df_base[df_base['Provinsi'].isin(f_provinsi)]
if f_wilayah: df_base = df_base[df_base['Wilayah'].isin(f_wilayah)]
if f_sektor: df_base = df_base[df_base['Sektor_PDRB'].isin(f_sektor)]
if f_kbli: df_base = df_base[df_base['Kategori'].isin(f_kbli)]

# Filter Spesifik Waktu
df_time = df_base.copy()
if f_tahun != "Semua": df_time = df_time[df_time['Tahun'] == f_tahun]
if f_triwulan != "Semua": df_time = df_time[df_time['Triwulan'] == f_triwulan]

# Logout button
if st.sidebar.button("Logout"):
    st.session_state["logged_in"] = False
    st.rerun()

# ==========================================
# 3. KONTEN UTAMA (TABS)
# ==========================================
st.title("Portal Investasi LKPM")
st.markdown("---")

tab1, tab2, tab3 = st.tabs(["Ringkasan Investasi", "Tren & Pertumbuhan", "Data Tabel Agregat"])

with tab1:
    st.subheader("Ringkasan Realisasi Investasi LKPM")
    
    # Menghitung Metrics
    total_inv = df_time['Nilai_Investasi'].sum()
    str_inv = f"{total_inv/1000000:,.2f} T" if total_inv >= 1000000 else f"{total_inv:,.0f} Jt"
    total_tk = df_time['Tenaga_Kerja'].sum()
    
    top_sek = df_time.groupby('Sektor_PDRB')['Nilai_Investasi'].sum().sort_values(ascending=False)
    str_sek = top_sek.index[0][:25] if not top_sek.empty else "-"
    
    top_wil = df_time.groupby('Wilayah')['Nilai_Investasi'].sum().sort_values(ascending=False)
    str_wil = top_wil.index[0] if not top_wil.empty else "-"
    
    # Layout Metrik
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Nilai Investasi (Rp)", str_inv)
    col2.metric("Serapan TKI", f"{total_tk:,.0f}")
    col3.metric("Sektor Dominan", str_sek)
    col4.metric("Kab/Kota Tertinggi", str_wil)
    
    # Bar Chart Sektor
    if not top_sek.empty:
        df_plot = top_sek.reset_index().rename(columns={'Nilai_Investasi': 'Total'})
        df_plot = df_plot[df_plot['Total'] > 0]
        fig = px.bar(df_plot, y='Sektor_PDRB', x='Total', orientation='h', 
                     color='Total', color_continuous_scale='viridis',
                     title="Proporsi Investasi Berdasarkan 17 Sektor PDRB")
        fig.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("Tren Pertumbuhan Investasi (QtQ & YoY)")
    
    # Trend Chart
    df_trend = df_base.groupby('Periode_Gabungan')['Nilai_Investasi'].sum().reset_index()
    fig_trend = px.line(df_trend, x='Periode_Gabungan', y='Nilai_Investasi', markers=True,
                        title="Tren Realisasi Investasi per Triwulan")
    fig_trend.update_traces(line_color='#00a65a', marker=dict(size=8))
    st.plotly_chart(fig_trend, use_container_width=True)
    
    # Growth Table (Kalkulasi Lag)
    df_q = df_base.groupby(['Tahun', 'Triwulan'])['Nilai_Investasi'].sum().reset_index()
    df_q = df_q.sort_values(by=['Tahun', 'Triwulan'])
    
    df_q['QtQ_Pct'] = df_q['Nilai_Investasi'].pct_change(periods=1) * 100
    df_q['YoY_Pct'] = df_q['Nilai_Investasi'].pct_change(periods=4) * 100
    
    df_q = df_q.sort_values(by=['Tahun', 'Triwulan'], ascending=[False, False])
    
    st.write("**Indikator Pertumbuhan (Dalam Juta Rupiah)**")
    st.dataframe(df_q.style.format({
        'Nilai_Investasi': '{:,.2f}',
        'QtQ_Pct': '{:.2f}%',
        'YoY_Pct': '{:.2f}%'
    }), use_container_width=True)

with tab3:
    st.subheader("Data Rinci LKPM")
    df_show = df_time[['Tahun', 'Triwulan', 'Kode_KBLI', 'Kategori', 'Sektor_PDRB', 
                       'Status_PM', 'Provinsi', 'Wilayah', 'Tenaga_Kerja', 'Nilai_Investasi']]
    st.dataframe(df_show, use_container_width=True)
