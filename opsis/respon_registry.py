"""
Registry Respons Pembangkit — hasil ekstraksi persis dari Excel Respons_Kit_2025
(kolom nama DE + sumber SelQuery/ExcelQuery pada Module1.UpdateKit).

RESPON_PLANTS  : pembangkit dari HIS_MEAS_KIT (B1, B3) — dipakai analisis lookback.
                 MW plant = jumlah unit yang terdaftar (seperti Excel).
RESPON_REALTIME: entri BMPP/industri yang di Excel dibaca realtime (bukan historian);
                 disimpan untuk referensi, belum dipakai di lookback.
"""

RESPON_PLANTS = [
    ('A_POSO 11', [('SLWNA6', 'UNIT1_P')]),
    ('A_POSO 12', [('SLWNA6', 'UNIT2_P')]),
    ('A_POSO 13', [('SLWNA6', 'UNIT3_P')]),
    ('A_POSO 14', [('SLWNA6', 'UNIT4_P')]),
    ('A_POSO 2A1', [('PMONA6', 'UNIT1_P')]),
    ('A_POSO 2A2', [('PMONA6', 'UNIT2_P')]),
    ('A_POSO 2A3', [('PMONA6', 'UNIT3_P')]),
    ('A_POSO 2B1', [('PMONA6', 'UNIT4_P')]),
    ('A_POSO 2B2', [('PMONA6', 'UNIT5_P')]),
    ('A_POSO 2B3', [('PMONA6', 'UNIT6_P')]),
    ('A_POSO 2B4', [('PMONA6', 'UNIT7_P')]),
    ('A_BAKARU 1', [('BKARU5', 'UNIT1_P')]),
    ('A_BAKARU 2', [('BKARU5', 'UNIT2_P')]),
    ('A_MALEA 1', [('MALEA5', 'UNIT1_P')]),
    ('A_MALEA 2', [('MALEA5', 'UNIT2_P')]),
    ('A_BILIBILI', [('PBILI', 'UNIT1_P'), ('PBILI', 'UNIT2_P')]),
    ('A_TRSBR', [('PLTMH', 'UNIT1_P')]),
    ('U_PGAYA 1', [('PNGYA5', 'UNIT1_P')]),
    ('U_PGAYA 2', [('PNGYA5', 'UNIT2_P')]),
    ('U_JNPTO 1', [('PJPNT1', 'UNIT1_P')]),
    ('U_JNPTO 2', [('PJPNT1', 'UNIT2_P')]),
    ('U_JNPTO 3A', [('PJNPT2', 'UNIT1_P')]),
    ('U_JNPTO 3B', [('PJNPT2', 'UNIT2_P')]),
    ('U_BARRU 1', [('BLUSU5', 'UNIT1_P')]),
    ('U_BARRU 2', [('BLUSU5', 'UNIT2_P')]),
    ('U_SB2', [('BLUSU5', 'UNIT3_P')]),
    ('U_NII TANASA', [('NTNSA4', 'UNIT3_P'), ('NTNSA4', 'UNIT4_P'), ('NTNSA4', 'UNIT5_P')]),
    ('U_MORAMO 1', [('KNDI35', 'UNIT1_P')]),
    ('U_MORAMO 2', [('KNDI35', 'UNIT2_P')]),
    ('U_MAMUJU', [('PMMJU', 'UNIT1_P'), ('PMMJU', 'UNIT2_P')]),
    ('U_PALU 31', [('PPLU35', 'UNIT1_P')]),
    ('U_PALU 32', [('PPLU35', 'UNIT2_P')]),
    ('G_SKG GT 11', [('SKANG5', 'UNIT1_P')]),
    ('G_SKG GT 12', [('SKANG5', 'UNIT2_P')]),
    ('G_SKG ST 18', [('SKANG5', 'UNIT3_P')]),
    ('G_SKG GT 21', [('SKANG5', 'UNIT4_P')]),
    ('G_SKG GT 22', [('SKANG5', 'UNIT5_P')]),
    ('G_SKG ST 28', [('SKANG5', 'UNIT6_P')]),
    ('D_SUPPA', [('SUPPA5', 'UNIT1_P'), ('SUPPA5', 'UNIT2_P')]),
    ('MG_KENDARI', [('NTNSA4', 'UNIT1_P'), ('NTNSA4', 'UNIT2_P')]),
    ('G_GE', [('TELLO5', 'UNIT3_P'), ('TELLO5', 'UNIT4_P')]),
    ('D_TELLO', [('TELLO5', 'UNIT5_P'), ('TELLO5', 'UNIT6_P'), ('TELLO5', 'UNIT1_P'), ('TELLO5', 'UNIT2_P')]),
    ('D_SILAE', [('PLTD_SILAE', 'UNIT1_P')]),
    ('D_TALLOLAMA', [('TLAMA_SW', 'UNIT1_P'), ('TLAMA_SW', 'UNIT2_P')]),
    ('D_PGAYA', [('PNGYA5_SW', 'UNIT1_P'), ('PNGYA5_SW', 'UNIT2_P')]),
    ('D_TELLO (SEWA)', [('TELLO_SW', 'UNIT1_P'), ('TELLO_SW', 'UNIT2_P')]),
    ('MPP_SUPPA', [('SUPPA5', 'UNIT3_P')]),
    ('MPP_TELLO', [('TELLO_SW', 'UNIT4_P')]),
    ('MPP_PGAYA', [('PNGYA5_SW', 'UNIT3_P')]),
    ('B_TOLO', [('PLTBT', 'UNIT1_P'), ('PLTBT', 'UNIT2_P')]),
    ('B_SIDRAP', [('PLTBS', 'UNIT1_P'), ('PLTBS', 'UNIT2_P')]),
]

RESPON_REALTIME = [
    ('BMPP_NUSANTARA2', [('TRANS_BMPP25_RT', 'WOLO5-1'), ('TRANS_BMPP25_RT', 'WOLO5-2')]),
    ('KTT_ANTAM', [('IND_LOAD', 'IND_ANTAM')]),
    ('KTT_CERIA', [('IND_LOAD', 'IND_CERIA')]),
    ('KTT_TONASA', [('IND_LOAD', 'IND_TNASA')]),
    ('KTT_BOSOWA', [('IND_LOAD', 'IND_BSOWA')]),
    ('KTT_HUADI 1', [('IND_LOAD', 'IND_HUADI')]),
    ('KTT_HUADI 2', [('IND_LOAD', 'IND_HUADI2')]),
    ('KTT_HUADI 3', [('IND_LOAD', 'IND_HUADI3')]),
    ('KTT_HUADI 4', [('IND_LOAD', 'IND_SMLTR4')]),
    ('KTT_HUADI 5', [('IND_LOAD', 'IND_SMLTR5')]),
]
