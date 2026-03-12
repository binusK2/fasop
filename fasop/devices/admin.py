from django.contrib import admin
from .models import Device, DeviceType

admin.site.register(Device)
admin.site.register(DeviceType)
# Register your models here.

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
