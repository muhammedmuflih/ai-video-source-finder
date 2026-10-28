from django.contrib import admin
from .models import SearchJob

@admin.register(SearchJob)
class SearchJobAdmin(admin.ModelAdmin):
    list_display = ("id", "original_filename", "status", "extracted_frames", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("original_filename", "query")
