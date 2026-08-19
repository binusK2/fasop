def zbx_groups(request):
    """
    Daftar nama Host Group Zabbix (distinct, terurut) untuk sidebar
    Device Monitor — satu link per grup (VoIP Mks, CRS, ROIP, dst).
    Dihitung dari data ZabbixHost yang sudah tersinkron, bukan dari
    ZABBIX_HOST_GROUPS di .env, supaya sidebar selalu cocok dengan apa
    yang benar-benar ada datanya.

    Hanya jalan untuk halaman di bawah /device-mon/ — context processor ini
    terdaftar global (lihat TEMPLATES di settings.py, pola yang sama dengan
    context processor lain di devices/context_processors.py), jadi query-nya
    perlu dijaga supaya tidak ikut jalan di setiap halaman FASOP.
    """
    if not request.path.startswith('/device-mon/'):
        return {}

    from .models import ZabbixHost

    csv_values = ZabbixHost.objects.filter(aktif=True).exclude(groups='').values_list('groups', flat=True)
    names = set()
    for csv in csv_values:
        for name in csv.split(','):
            name = name.strip()
            if name:
                names.add(name)

    return {'zbx_groups': sorted(names)}
