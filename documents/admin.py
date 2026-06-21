from django.contrib import admin
from .models import Document

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'uploaded_by', 'created_at', 'is_published']
    list_filter = ['is_published']
    search_fields = ['title']