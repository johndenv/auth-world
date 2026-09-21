from django.contrib import admin

from .models import Record


@admin.register(Record)
class RecordAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "owner", "created_by", "created_at")
    list_filter = ("status",)
    search_fields = ("name",)