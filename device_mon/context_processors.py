def zbx_groups(request):
    """
    Daftar nama Grup Host Zabbix (ZabbixGroup — grouping MANUAL yang dikelola
    lewat Django Admin) untuk sidebar Device Monitor — satu link per grup.

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

    from .models import ZabbixGroup, ZabbixHost

    names = list(
        ZabbixGroup.objects.filter(aktif=True).values_list('nama', flat=True)
    )

    # Tambahkan '(Tanpa Grup)' hanya kalau memang ada host aktif yang belum
    # masuk grup mana pun — supaya host baru hasil sync tidak hilang dari UI
    # sebelum sempat dikelompokkan.
    bergrup = set(ZabbixGroup.objects.filter(aktif=True).values_list('hosts__pk', flat=True))
    ada_yatim = ZabbixHost.objects.filter(aktif=True).exclude(pk__in=bergrup).exists()
    if ada_yatim:
        names.append('(Tanpa Grup)')

    return {'zbx_groups': names}
