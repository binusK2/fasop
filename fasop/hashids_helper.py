from hashids import Hashids
from django.conf import settings

_hashids = Hashids(salt=settings.SECRET_KEY, min_length=6)


def encode(pk: int) -> str:
    return _hashids.encode(pk)


def decode(hid: str) -> int | None:
    nums = _hashids.decode(hid)
    return nums[0] if nums else None
