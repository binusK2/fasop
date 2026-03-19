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

