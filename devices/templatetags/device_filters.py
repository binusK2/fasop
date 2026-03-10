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
