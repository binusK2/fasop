from django.contrib import admin
from .models import Device, DeviceType, SiteLocation

admin.site.register(Device)
admin.site.register(DeviceType)

@admin.register(SiteLocation)
class SiteLocationAdmin(admin.ModelAdmin):
    list_display  = ['nama', 'latitude', 'longitude', 'has_coords', 'keterangan']
    search_fields = ['nama']
    list_display_links = ['nama']

    def has_coords(self, obj):
        return obj.has_coords
    has_coords.boolean = True
    has_coords.short_description = 'Ada Koordinat'


from .models import UserProfile
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'has_signature']
    list_editable = ['role']
    def has_signature(self, obj): return bool(obj.signature)
    has_signature.boolean = True

@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)
