from django import template

register = template.Library()

@register.filter
def replace_underscore(value):
    """Ganti underscore dengan spasi dan title-case untuk tampilan label."""
    return str(value).replace('_', ' ').title()

@register.filter
def is_list(value):
    """Cek apakah value adalah list."""
    return isinstance(value, list)

@register.filter
def get_item(dictionary, key):
    """Akses dict dengan key di template: {{ my_dict|get_item:key }}"""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None

@register.filter
def abs_val(value):
    """Nilai absolut untuk template."""
    try:
        return abs(value)
    except (TypeError, ValueError):
        return value

@register.filter
def hashid(value):
    """PK → hashid untuk dipakai di URL/querystring template.

    PK integer tidak pernah dipampangkan di URL FASOP (lihat
    fasop/hashids_helper.py); filter ini yang menjaga aturan itu tetap berlaku
    di parameter filter, bukan cuma di path URL.
    """
    from fasop.hashids_helper import encode
    try:
        return encode(int(value))
    except (TypeError, ValueError):
        return ''

