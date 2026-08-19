"""
Client JSON-RPC read-only ke Zabbix API — dipakai oleh management command
`sync_zabbix` untuk menarik status host/problem secara berkala (pull).

Zabbix API selalu JSON-RPC 2.0 lewat satu endpoint HTTP, contoh:
    POST {ZABBIX_API_URL}   (mis. http://zabbix.local/api_jsonrpc.php atau
                              http://zabbix.local/zabbix/api_jsonrpc.php)
    Content-Type: application/json-rpc
    {"jsonrpc":"2.0","method":"...", "params":{...}, "id":1, "auth":"<token>"}

Autentikasi — dua opsi (lihat fasop/settings.py blok "Zabbix Integration"):
  1. ZABBIX_API_TOKEN  — token API (Administration → API tokens, Zabbix >= 5.4).
     Direkomendasikan: tidak butuh login, tidak kedaluwarsa sampai dicabut manual.
  2. ZABBIX_API_USER + ZABBIX_API_PASSWORD — login user biasa (fallback untuk
     Zabbix versi lama yang belum punya API token). Sesi login (`auth` id)
     di-cache in-memory per proses, re-login otomatis kalau kedaluwarsa.

Prinsip: modul ini TIDAK PERNAH menulis ke Zabbix (read-only, method get.
Buat user Zabbix dengan role "Read-only" saja) dan tidak pernah melempar
exception yang tidak tertangani ke pemanggil biasa — pemanggil (sync_zabbix)
yang memutuskan mau retry/skip. Fungsi-fungsi publik di sini raise
ZabbixAPIError yang sudah diberi pesan human-readable.
"""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# Severity Zabbix (kolom "severity"/"priority") — index -> label.
SEVERITY_LABELS = {
    '0': 'Not classified',
    '1': 'Information',
    '2': 'Warning',
    '3': 'Average',
    '4': 'High',
    '5': 'Disaster',
}


class ZabbixAPIError(Exception):
    pass


def _url():
    return (getattr(settings, 'ZABBIX_API_URL', '') or '').strip()


def _timeout():
    return getattr(settings, 'ZABBIX_API_TIMEOUT', 10)


class ZabbixClient:
    """
    Satu instance = satu sesi pemakaian singkat (dipakai per-run sync_zabbix).
    Tidak menyimpan token login ke disk — kalau pakai user/password, login
    ulang tiap kali command dijalankan (cron tiap beberapa menit, overhead
    satu request tambahan yang dapat diabaikan).
    """

    def __init__(self, url=None, token=None, user=None, password=None, timeout=None):
        self.url = url or _url()
        self.token = token if token is not None else getattr(settings, 'ZABBIX_API_TOKEN', '')
        self.user = user if user is not None else getattr(settings, 'ZABBIX_API_USER', '')
        self.password = password if password is not None else getattr(settings, 'ZABBIX_API_PASSWORD', '')
        self.timeout = timeout or _timeout()
        self._auth = self.token or None
        self._id = 0

    def _call(self, method, params=None, use_auth=True):
        import requests

        if not self.url:
            raise ZabbixAPIError('ZABBIX_API_URL belum dikonfigurasi.')

        self._id += 1
        body = {
            'jsonrpc': '2.0',
            'method': method,
            'params': params or {},
            'id': self._id,
        }

        headers = {'Content-Type': 'application/json-rpc'}
        if use_auth and self._auth:
            # Zabbix >= 6.4: token dikirim lewat header Authorization, BUKAN
            # field "auth" di body — field itu dideprecate di 6.4 dan sudah
            # dihapus total (error "unexpected parameter auth") di 7.0+.
            headers['Authorization'] = f'Bearer {self._auth}'

        try:
            resp = requests.post(
                self.url,
                json=body,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.exceptions.RequestException as e:
            raise ZabbixAPIError(f'Gagal menghubungi Zabbix API ({self.url}): {e}')

        try:
            data = resp.json()
        except ValueError:
            raise ZabbixAPIError(
                f'Respons Zabbix API bukan JSON (HTTP {resp.status_code}): {(resp.text or "")[:200]}'
            )

        if 'error' in data:
            err = data['error']
            raise ZabbixAPIError(
                f"Zabbix API error [{method}]: {err.get('message')} — {err.get('data')}"
            )
        return data.get('result')

    def login(self):
        """Login user/password -> simpan auth token sesi. Tidak dipanggil kalau pakai API token."""
        if self.token:
            return self.token
        if not self.user or not self.password:
            raise ZabbixAPIError(
                'ZABBIX_API_TOKEN kosong dan ZABBIX_API_USER/ZABBIX_API_PASSWORD juga belum diisi.'
            )
        # Zabbix >= 6.4 memakai method "user.login" tanpa auth di body.
        result = self._call('user.login', {'username': self.user, 'password': self.password},
                            use_auth=False)
        self._auth = result
        return result

    def ensure_auth(self):
        if not self._auth:
            self.login()

    def get_hosts(self, group_names=None):
        """
        Daftar host + status trigger tertinggi (Zabbix >= 6.0: field
        `severity` di host.get lewat selectTriggers tidak langsung ada,
        jadi kita ambil host dulu, problem-nya lewat get_problems()
        terpisah dan digabung oleh sync_zabbix).

        group_names: opsional, filter ke host group tertentu (list nama).
        Return: list of dict {hostid, host, name, status, groups: [{groupid, name}, ...]}.
        `groups` selalu SEMUA host group host tsb di Zabbix, bukan cuma yang
        match `group_names` — dipakai FASOP untuk mengelompokkan tampilan
        per grup (VoIP Mks, CRS, ROIP, dst).
        """
        self.ensure_auth()
        params = {
            'output': ['hostid', 'host', 'name', 'status'],
            'selectGroups': ['name'],
            'filter': {'status': 0},   # 0 = host monitored (aktif)
        }
        if group_names:
            groups = self._call('hostgroup.get', {
                'output': ['groupid'],
                'filter': {'name': list(group_names)},
            })
            groupids = [g['groupid'] for g in (groups or [])]
            if not groupids:
                return []
            params['groupids'] = groupids

        return self._call('host.get', params) or []

    def get_problems(self, hostids=None):
        """
        Problem yang SEDANG AKTIF (belum resolved) — problem.get tanpa
        filter waktu selalu hanya mengembalikan problem yang masih terbuka.

        CATATAN: problem.get TIDAK mendukung `selectHosts` (bukan parameter
        resmi API-nya walau method Zabbix lain seperti trigger.get/event.get
        mendukungnya — Zabbix 7.4 menolak keras parameter tak dikenal).
        Pemetaan problem → host dilakukan terpisah lewat get_trigger_hosts()
        karena problem.get hanya mengembalikan `objectid` (= triggerid untuk
        problem bertipe trigger, source=0/object=0, default).

        Return: list of dict {eventid, objectid, name, severity, clock}.
        """
        self.ensure_auth()
        params = {
            'output': ['eventid', 'objectid', 'name', 'severity', 'clock', 'r_eventid'],
            'recent': False,          # hanya problem yang masih PROBLEM
            'sortfield': ['eventid'],
            'sortorder': 'DESC',
        }
        if hostids:
            params['hostids'] = list(hostids)
        return self._call('problem.get', params) or []

    def get_trigger_hosts(self, triggerids):
        """
        Peta triggerid -> daftar hostid, dipakai untuk menghubungkan hasil
        get_problems() (yang hanya punya objectid/triggerid) ke host terkait.
        Satu trigger biasanya 1 host, tapi trigger multi-host (mis. trigger
        agregat) bisa lebih dari satu — semua diikutsertakan.
        Return: dict {triggerid: [hostid, ...]}.
        """
        if not triggerids:
            return {}
        self.ensure_auth()
        triggers = self._call('trigger.get', {
            'output': ['triggerid'],
            'selectHosts': ['hostid'],
            'triggerids': list(triggerids),
        }) or []
        return {
            t['triggerid']: [h['hostid'] for h in t.get('hosts', [])]
            for t in triggers
        }

    def get_event(self, eventid):
        """Detail satu event (dipakai webhook receiver untuk validasi/lookup nama host)."""
        self.ensure_auth()
        result = self._call('event.get', {
            'output': ['eventid', 'name', 'severity', 'clock', 'r_eventid'],
            'selectHosts': ['hostid', 'host', 'name'],
            'eventids': [str(eventid)],
        })
        return (result or [None])[0]


def severity_label(sev):
    return SEVERITY_LABELS.get(str(sev), str(sev) if sev not in (None, '') else '')


def get_current_status(group_names=None):
    """
    Helper tingkat tinggi dipakai sync_zabbix: gabungkan host.get + problem.get
    menjadi satu dict {hostid: {host, name, groups, state, severity, problem_name, eventid, clock}}.
    `groups` = nama Host Group Zabbix dipisah koma (semua grup host tsb, bukan
    cuma yang match `group_names`).
    state = 'PROBLEM' kalau ada minimal satu problem aktif, selain itu 'OK'.
    Kalau ada beberapa problem aktif pada satu host, dipilih yang severity-nya
    tertinggi (SEVERITY_LABELS terurut naik -> ambil angka terbesar).
    """
    client = ZabbixClient()
    hosts = client.get_hosts(group_names=group_names)
    if not hosts:
        return {}

    hostids = [h['hostid'] for h in hosts]
    problems = client.get_problems(hostids=hostids)

    # problem.get tidak mengembalikan host langsung — petakan lewat objectid
    # (triggerid) via trigger.get. Problem non-trigger (object != 0, jarang
    # dipakai) diabaikan karena objectid-nya bukan triggerid.
    triggerids = {p['objectid'] for p in problems if p.get('objectid')}
    trigger_hosts = client.get_trigger_hosts(triggerids)

    # host -> problem tertinggi
    best = {}
    for p in problems:
        for hid in trigger_hosts.get(p.get('objectid'), []):
            sev = int(p.get('severity') or 0)
            cur = best.get(hid)
            if cur is None or sev > cur['sev']:
                best[hid] = {
                    'sev': sev,
                    'eventid': p.get('eventid'),
                    'name': p.get('name', ''),
                    'clock': p.get('clock'),
                }

    out = {}
    for h in hosts:
        hid = h['hostid']
        group_names_str = ','.join(g['name'] for g in h.get('groups', []))
        p = best.get(hid)
        if p:
            out[hid] = {
                'host': h.get('host', ''),
                'name': h.get('name', ''),
                'groups': group_names_str,
                'state': 'PROBLEM',
                'severity': severity_label(p['sev']),
                'problem_name': p['name'],
                'eventid': p['eventid'],
                'clock': p['clock'],
            }
        else:
            out[hid] = {
                'host': h.get('host', ''),
                'name': h.get('name', ''),
                'groups': group_names_str,
                'state': 'OK',
                'severity': '',
                'problem_name': '',
                'eventid': '',
                'clock': None,
            }
    return out
