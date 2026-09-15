def zbx_groups(request):
    """
    Daftar Instansi Zabbix aktif + Grup Host Zabbix manual (ZabbixGroup,
    dikelola lewat Django Admin) milik masing-masing, untuk sidebar Device
    Monitor — satu bagian sidebar per instansi, satu link per grup di
    dalamnya.

    Sengaja dari ZabbixGroup, bukan dari ZabbixHost.groups: field `groups` di
    ZabbixHost selalu ditimpa ulang oleh sync_zabbix mengikuti Host Group di
    Zabbix, jadi tidak bisa dipakai untuk pengelompokan yang disusun sendiri.

    Hanya jalan untuk halaman di bawah /device-mon/ — context processor ini
    terdaftar global (lihat TEMPLATES di settings.py, pola yang sama dengan
    context processor lain di devices/context_processors.py), jadi query-nya
    perlu dijaga supaya tidak ikut jalan di setiap halaman FASOP.
    """
    if not request.path.startswith('/device-mon/'):
        return {}

    from .models import ZabbixInstance, ZabbixGroup, ZabbixHost

    out = []
    for instansi in ZabbixInstance.objects.filter(aktif=True):
        names = list(
            ZabbixGroup.objects.filter(aktif=True, instance=instansi).values_list('nama', flat=True)
        )

        # Tambahkan '(Tanpa Grup)' hanya kalau memang ada host aktif instansi
        # ini yang belum masuk grup mana pun — supaya host baru hasil sync
        # tidak hilang dari UI sebelum sempat dikelompokkan.
        bergrup = set(
            ZabbixGroup.objects.filter(aktif=True, instance=instansi).values_list('hosts__pk', flat=True)
        )
        ada_yatim = (ZabbixHost.objects.filter(aktif=True, instance=instansi)
                     .exclude(pk__in=bergrup).exists())
        if ada_yatim:
            names.append('(Tanpa Grup)')

        out.append({'instansi': instansi, 'groups': names})

    return {'zbx_instansi_list': out}
