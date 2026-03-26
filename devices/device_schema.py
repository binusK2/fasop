# devices/device_schema.py
# ============================================================
# Schema field khusus per jenis perangkat.
# Field umum (nama, merk, serial, dll) sudah ada di model Device.
# 'spesifikasi' (JSONField) akan menyimpan semua field di sini.
# ============================================================
#
# Tipe field yang didukung:
#   text, number, date, select, multiselect, textarea
# ============================================================

DEVICE_SCHEMA = {

    "Router": [
        {"key": "tegangan_input", "label": "Tegangan Input",         "type": "select",
         "options": ["12 VDC", "24 VDC", "48 VDC", "220 VAC"]},
        {"key": "jumlah_port",    "label": "Jumlah Port LAN",        "type": "number"},
        {"key": "sfp_port",       "label": "Jumlah Port SFP",        "type": "number"},   
        {"key": "sfp_speeds",     "label": "Kecepatan per Port SFP", "type": "sfp_speed",
         "options": ["100 Mbps", "1 Gbps", "10 Gbps"]},
    ],

    "Switch": [
        {"key": "tegangan_input", "label": "Tegangan Input",         "type": "select",
         "options": ["12 VDC", "24 VDC", "48 VDC", "220 VAC"]},
        {"key": "jumlah_port",    "label": "Jumlah Port LAN",        "type": "number"},
        {"key": "sfp_port",       "label": "Jumlah Port SFP",        "type": "number"},
        {"key": "sfp_speeds",     "label": "Kecepatan per Port SFP", "type": "sfp_speed",
         "options": ["100 Mbps", "1 Gbps", "10 Gbps"]},
    ],

    "Radio": [
        {"key": "frekuensi",        "label": "Frekuensi (Rx)",      "type": "text"},
        {"key": "frekuensi",        "label": "Frekuensi (TX)",      "type": "text"},
        {"key": "Tone_Rx",          "label": "Tone (Rx)",           "type": "text"},
        {"key": "Tone_Tx",          "label": "Tone (TX)",           "type": "text"},
        {"key": "tx_power",         "label": "TX Power (W)",        "type": "number"},
    ],

    "VoIP": [
        {"key": "nomor_ekstensi",   "label": "Nomor Ekstensi",       "type": "text"},
        {"key": "nama_ekstensi",    "label": "Nama Ekstensi",        "type": "text"},
    ],

    "Multiplexer": [
        {"key": "tegangan_input", "label": "Tegangan Input",         "type": "select",
         "options": ["48 VDC", "220 VAC"]},   
    ],

    "Catu Daya": [
        {"key": "tipe_catu_daya",   "label": "Tipe Catu Daya",       "type": "select",
         "options": ["Rectifier DC", "PSU AC", "Panel DC"]},
        {"key": "tegangan_input",   "label": "Tegangan Input",       "type": "text",
         "placeholder": "cth: 220V AC"},
        {"key": "tegangan_output",  "label": "Tegangan Output",      "type": "text",
         "placeholder": "cth: 48V DC / -48V DC"},
        {"key": "merk_recti",         "label": "Merk Rectifier",            "type": "text"},
        {"key": "kapasitas_daya",   "label": "Kapasitas Rectifier (A)",     "type": "number"},
        {"key": "batterai",         "label": "Merk Batterai",               "type": "text"},
        {"key": "kapasitas_baterai","label": "Kapasitas Batterai",          "type": "text"},
        {"key": "total_batterai",   "label": "Total Jumlah Batterai",       "type": "number"},
        {"key": "jumlah_modul",     "label": "Jumlah Modul",                "type": "number"},
        
    ],

    "RTU": [
        {"key": "protokol_komunikasi1", "label": "Protokol Komunikasi master makassar", "type": "select",
         "options": ["IEC 60870-5-101", "IEC 60870-5-104", "DNP3",
                     "Modbus RTU", "Modbus TCP", "IEC 61850"]},
        {"key": "protokol_komunikasi2", "label": "Protokol Komunikasi master palu", "type": "select",
         "options": ["IEC 60870-5-101", "IEC 60870-5-104", "DNP3",
                     "Modbus RTU", "Modbus TCP", "IEC 61850"]},
        {"key": "protokol_komunikasi3", "label": "Protokol Komunikasi master kendari", "type": "select",
         "options": ["IEC 60870-5-101", "IEC 60870-5-104", "DNP3",
                     "Modbus RTU", "Modbus TCP", "IEC 61850"]},
        {"key": "roda",     "label": "ip RODA",   "type": "text",
         "placeholder": "IP RODA"},
        {"key": "jumlah_di",        "label": "Digital Input (DI)",   "type": "number"},
        {"key": "jumlah_do",        "label": "Digital Output (DO)",  "type": "number"},
        {"key": "jumlah_ai",        "label": "Analog Input (AI)",    "type": "number"},
        {"key": "jumlah_ao",        "label": "Analog Output (AO)",   "type": "number"},
        {"key": "jumlah_meter",     "label": "Jumlah Digital Meter", "type": "number"},
        {"key": "tegangan_supply",  "label": "Tegangan Supply",      "type": "select",
         "options": ["24V DC", "48V DC", "110V DC", "220V AC"]},
        
    ],

    "PLC": [
        {"key": "freq_tx",          "label": "Frekuensi TX",            "type": "text"},
        {"key": "bw_tx",            "label": "Bandwidth TX",            "type": "text"},
        {"key": "freq_rx",          "label": "Frekuensi RX",            "type": "text"},
        {"key": "bw_rx",            "label": "Bandwidth RX",            "type": "text"},
        {"key": "power",            "label": "Power (w)",               "type": "text"},
        {"key": "lmu",              "label": "Merk LMU",                "type": "text"},
        
    ],

    "RoIP": [

    ],
    "TELEPROTEKSI": [
        {"key": "komunikasi",       "label": "Port Komunikasi",      "type": "select",
         "options": ["E1", "E&M", "PLC", ]},
        {"key": "jumlah_Command",        "label": "Jumlah command",    "type": "number"},
        {"key": "Command1",         "label": "command 1",   "type": "select",
         "options": ["Distance", "DEF", "DTT", "StandBy"]},
        {"key": "Command2",         "label": "command 2",   "type": "select",
         "options": ["Distance", "DEF", "DTT", "StandBy"]},
        {"key": "Command3",         "label": "command 3",   "type": "select",
         "options": ["Distance", "DEF", "DTT", "StandBy"]},
        {"key": "Command4",         "label": "command 4",   "type": "select",
         "options": ["Distance", "DEF", "DTT", "StandBy"]},
         
    ],


# BELUM UPDATE
    "SAS": [
        {"key": "standar_protokol", "label": "Standar Protokol",     "type": "select",
         "options": ["IEC 61850 Ed.1", "IEC 61850 Ed.2", "IEC 60870-5-104", "GOOSE", "SV (Sampled Values)"]},
        {"key": "bay",              "label": "Bay / Feeder",         "type": "text"},
        {"key": "level_tegangan",   "label": "Level Tegangan (kV)",  "type": "select",
         "options": ["20 kV", "70 kV", "150 kV", "500 kV"]},
        {"key": "fungsi",           "label": "Fungsi Utama",         "type": "multiselect",
         "options": ["Protection", "Control", "Monitoring", "Metering",
                     "Interlocking", "SCADA Interface"]},
        {"key": "hmi_tersedia",     "label": "HMI Tersedia",         "type": "select",
         "options": ["Ada", "Tidak Ada"]},
        {"key": "server_scada",     "label": "Server SCADA",         "type": "text"},
        {"key": "switch_jaringan",  "label": "Switch Jaringan Terhubung", "type": "text"},
    ],

    "DFR": [
        {"key": "jumlah_channel_analog",  "label": "Channel Analog",      "type": "number"},
        {"key": "jumlah_channel_digital", "label": "Channel Digital",     "type": "number"},
        {"key": "sampling_rate",    "label": "Sampling Rate",        "type": "select",
         "options": ["1 kHz", "2 kHz", "4 kHz", "8 kHz", "10 kHz", "20 kHz"]},
        {"key": "tipe_trigger",     "label": "Tipe Trigger",         "type": "select",
         "options": ["Analog Threshold", "Digital Input", "External", "Manual"]},
        {"key": "pre_trigger_time", "label": "Pre-Trigger Time (ms)", "type": "number"},
        {"key": "post_trigger_time","label": "Post-Trigger Time (ms)","type": "number"},
        {"key": "kapasitas_storage","label": "Kapasitas Storage",    "type": "text",
         "placeholder": "cth: 32 GB"},
        {"key": "format_file",      "label": "Format File",          "type": "select",
         "options": ["COMTRADE", "PQDIF", "Proprietary"]},
        {"key": "time_sync",        "label": "Sinkronisasi Waktu",   "type": "select",
         "options": ["GPS", "IRIG-B", "NTP", "PPS"]},
        {"key": "server_dfr",       "label": "Server DFR / Collector", "type": "text"},
    ],

    "RELE DEFENSE SCHEME": [
        {"key": "fungsi_proteksi",  "label": "Fungsi Proteksi",      "type": "multiselect",
         "options": ["Distance (21)", "Overcurrent (51)", "Differential (87)",
                     "Earth Fault (51N)", "Under-Frequency (81U)", "Over-Voltage (59)",
                     "Under-Voltage (27)", "Auto-Reclose (79)", "Busbar Protection"]},
        {"key": "scheme_type",      "label": "Tipe Skema",           "type": "select",
         "options": ["UFLS (Under Frequency Load Shedding)", "RAS (Remedial Action Scheme)",
                     "SPS (Special Protection Scheme)", "UVLS (Under Voltage Load Shedding)"]},
        {"key": "level_tegangan",   "label": "Level Tegangan (kV)",  "type": "select",
         "options": ["20 kV", "70 kV", "150 kV", "500 kV"]},
        {"key": "bay",              "label": "Bay / Peralatan Terhubung", "type": "text"},
        {"key": "setting_file",     "label": "File Setting",         "type": "text",
         "placeholder": "Nama file / versi setting"},
        {"key": "software_setting", "label": "Software Setting",     "type": "text",
         "placeholder": "cth: DIGSI, EnerVista, MiCOM S1"},
        {"key": "komunikasi",       "label": "Port Komunikasi",      "type": "select",
         "options": ["IEC 61850 GOOSE", "IEC 60870-5-104", "RS-485 Modbus",
                     "Hardwired", "Fiber Optic"]},
        {"key": "rating_ct",        "label": "Rating CT (A)",        "type": "text"},
        {"key": "rating_vt",        "label": "Rating VT (V)",        "type": "text"},
    ],

    "Workstation PC": [
        {"key": "os",               "label": "Sistem Operasi",       "type": "select",
         "options": ["Windows 10", "Windows 11", "Windows Server 2019",
                     "Windows Server 2022", "Linux Ubuntu", "Linux CentOS", "Linux RHEL"]},
        {"key": "processor",        "label": "Processor",            "type": "text",
         "placeholder": "cth: Intel Core i7-12700"},
        {"key": "ram",              "label": "RAM (GB)",             "type": "number"},
        {"key": "storage",          "label": "Storage",              "type": "text",
         "placeholder": "cth: 512 GB SSD + 1 TB HDD"},
        {"key": "vga",              "label": "VGA / GPU",            "type": "text"},
        {"key": "ukuran_monitor",   "label": "Ukuran Monitor (inch)", "type": "number"},
        {"key": "jumlah_monitor",   "label": "Jumlah Monitor",       "type": "number"},
        {"key": "form_factor",      "label": "Form Factor",          "type": "select",
         "options": ["Desktop Tower", "Mini PC", "All-in-One", "Rack-Mount"]},
        {"key": "fungsi_utama",     "label": "Fungsi Utama",         "type": "select",
         "options": ["HMI / SCADA", "Engineering Workstation", "Data Historian",
                     "Operator Workstation", "General Purpose"]},
        {"key": "software_terpasang", "label": "Software Utama",    "type": "text",
         "placeholder": "cth: WinCC, iFix, OSIsoft PI"},
        {"key": "antivirus",        "label": "Antivirus",            "type": "text"},
        {"key": "domain",           "label": "Domain / Workgroup",   "type": "text"},
    ],

    "SERVER": [
        {"key": "os",               "label": "Sistem Operasi",       "type": "select",
         "options": ["Windows Server 2016", "Windows Server 2019", "Windows Server 2022",
                     "Linux Ubuntu Server", "Linux CentOS", "Linux RHEL", "VMware ESXi"]},
        {"key": "processor",        "label": "Processor",            "type": "text",
         "placeholder": "cth: Intel Xeon Silver 4314"},
        {"key": "jumlah_socket",    "label": "Jumlah Socket CPU",    "type": "select",
         "options": ["1 Socket", "2 Socket", "4 Socket"]},
        {"key": "ram",              "label": "RAM (GB)",             "type": "number"},
        {"key": "storage_config",   "label": "Konfigurasi Storage",  "type": "text",
         "placeholder": "cth: 4x 1TB HDD RAID 5"},
        {"key": "raid_level",       "label": "Level RAID",           "type": "select",
         "options": ["Tidak Ada", "RAID 0", "RAID 1", "RAID 5", "RAID 6", "RAID 10"]},
        {"key": "form_factor",      "label": "Form Factor",          "type": "select",
         "options": ["1U Rack", "2U Rack", "4U Rack", "Tower", "Blade"]},
        {"key": "jumlah_nic",       "label": "Jumlah NIC",           "type": "number"},
        {"key": "psu_redundant",    "label": "PSU Redundan",         "type": "select",
         "options": ["Ya", "Tidak"]},
        {"key": "peran_server",     "label": "Peran / Fungsi Server", "type": "multiselect",
         "options": ["SCADA Server", "Data Historian", "Database Server", "File Server",
                     "Domain Controller", "Virtualization Host", "Backup Server",
                     "Application Server", "Web Server"]},
        {"key": "virtualisasi",     "label": "Platform Virtualisasi", "type": "select",
         "options": ["Tidak Ada", "VMware vSphere", "Microsoft Hyper-V", "KVM", "Proxmox"]},
        {"key": "software_utama",   "label": "Software Utama",       "type": "text"},
    ],

    "UPS": [
        {"key": "kapasitas_va",     "label": "Kapasitas (VA/KVA)",   "type": "text",
         "placeholder": "cth: 10 KVA"},
        {"key": "kapasitas_watt",   "label": "Kapasitas (Watt)",     "type": "number"},
        {"key": "tipe_ups",         "label": "Tipe UPS",             "type": "select",
         "options": ["Online Double Conversion", "Line Interactive", "Offline/Standby"]},
        {"key": "tegangan_input",   "label": "Tegangan Input",       "type": "select",
         "options": ["220V AC 1-Phase", "380V AC 3-Phase", "400V AC 3-Phase"]},
        {"key": "tegangan_output",  "label": "Tegangan Output",      "type": "select",
         "options": ["220V AC 1-Phase", "380V AC 3-Phase"]},
        {"key": "frekuensi",        "label": "Frekuensi (Hz)",       "type": "select",
         "options": ["50 Hz", "60 Hz"]},
        {"key": "runtime_fullload", "label": "Runtime Full Load (menit)", "type": "number"},
        {"key": "runtime_halfload", "label": "Runtime Half Load (menit)", "type": "number"},
        {"key": "tipe_baterai",     "label": "Tipe Baterai",         "type": "select",
         "options": ["VRLA / AGM", "Gel", "Lithium-Ion", "Wet Cell"]},
        {"key": "jumlah_baterai",   "label": "Jumlah Sel Baterai",   "type": "number"},
        {"key": "tanggal_baterai",  "label": "Tgl Pasang Baterai",   "type": "date"},
        {"key": "umur_baterai",     "label": "Umur Baterai (tahun)", "type": "number"},
    ],

    "GENSET": [
        {"key": "kapasitas_kva",    "label": "Kapasitas (KVA)",      "type": "number"},
        {"key": "kapasitas_kw",     "label": "Kapasitas (KW)",       "type": "number"},
        {"key": "tegangan_output",  "label": "Tegangan Output",      "type": "select",
         "options": ["220V / 380V 3-Phase", "220V 1-Phase"]},
        {"key": "frekuensi",        "label": "Frekuensi (Hz)",       "type": "select",
         "options": ["50 Hz", "60 Hz"]},
        {"key": "rpm",              "label": "Putaran (RPM)",        "type": "select",
         "options": ["1500 RPM", "1800 RPM", "3000 RPM"]},
        {"key": "tipe_bahan_bakar", "label": "Jenis Bahan Bakar",    "type": "select",
         "options": ["Solar (Diesel)", "Gas Alam (CNG)", "LPG", "Bensin"]},
        {"key": "kapasitas_tangki", "label": "Kapasitas Tangki (Liter)", "type": "number"},
        {"key": "konsumsi_bbm",     "label": "Konsumsi BBM (L/jam)", "type": "number"},
        {"key": "tipe_start",       "label": "Tipe Start",           "type": "select",
         "options": ["Manual", "Elektrik", "Otomatis (AMF/ATS)"]},
        {"key": "amf_ats",          "label": "Tersedia AMF/ATS",     "type": "select",
         "options": ["Ya", "Tidak"]},
        {"key": "tipe_pendingin",   "label": "Tipe Pendingin",       "type": "select",
         "options": ["Air Cooled", "Water Cooled"]},
        {"key": "jam_operasi",      "label": "Jam Operasi (HM)",     "type": "number"},
        {"key": "last_service",     "label": "Terakhir Service",     "type": "date"},
        {"key": "jadwal_service",   "label": "Interval Service (jam HM)", "type": "number",
         "placeholder": "cth: 250"},
    ],
}
