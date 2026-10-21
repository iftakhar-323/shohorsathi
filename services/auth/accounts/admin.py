from django.contrib import admin

from .models import Address, Area, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["phone", "full_name", "role", "is_phone_verified", "is_active", "date_joined"]
    list_filter = ["role", "is_active"]
    search_fields = ["phone", "full_name", "email"]
    exclude = ["password"]


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ["name_en", "name_bn", "city", "ward", "is_active"]
    list_filter = ["city", "is_active"]


admin.site.register(Address)
