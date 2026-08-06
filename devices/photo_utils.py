"""Utility foto lapangan: thumbnail + baca waktu EXIF.

Dipakai oleh view upload galeri foto (FotoLapangan). Semua fungsi defensif —
mengembalikan None / melewati diam-diam bila file bukan gambar valid, agar satu
foto rusak tidak menggagalkan seluruh batch upload.
"""
import io
from datetime import datetime

from django.core.files.base import ContentFile
from django.utils import timezone


def make_thumbnail(django_file, max_size=(480, 480), quality=78):
    """Kembalikan ContentFile JPEG thumbnail (orientasi EXIF diperbaiki), atau None."""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return None
    try:
        django_file.seek(0)
        img = Image.open(django_file)
        img = ImageOps.exif_transpose(img)          # betulkan foto yang miring
        img = img.convert('RGB')
        img.thumbnail(max_size, Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=quality, optimize=True)
        buf.seek(0)
        return ContentFile(buf.read())
    except Exception:
        return None
    finally:
        try:
            django_file.seek(0)
        except Exception:
            pass


def read_exif_taken_at(django_file):
    """Kembalikan datetime (aware) waktu ambil dari EXIF DateTimeOriginal, atau None."""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        django_file.seek(0)
        img = Image.open(django_file)
        exif = img._getexif() or {}
        # 36867 = DateTimeOriginal, 306 = DateTime (fallback)
        raw = exif.get(36867) or exif.get(306)
        if not raw:
            return None
        dt = datetime.strptime(str(raw).strip(), '%Y:%m:%d %H:%M:%S')
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt
    except Exception:
        return None
    finally:
        try:
            django_file.seek(0)
        except Exception:
            pass
