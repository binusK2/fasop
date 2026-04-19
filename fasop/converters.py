from .hashids_helper import encode, decode
from django.urls.exceptions import Resolver404


class HashIdConverter:
    regex = '[a-zA-Z0-9]+'

    def to_python(self, value: str) -> int:
        pk = decode(value)
        if pk is None:
            raise Resolver404({'tried': [], 'path': value})
        return pk

    def to_url(self, value) -> str:
        return encode(int(value))
