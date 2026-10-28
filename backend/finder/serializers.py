from rest_framework import serializers
from .models import SearchJob

class SearchJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchJob
        fields = [
            "id", "original_filename", "query", "status", "extracted_frames",
            "results", "message", "created_at"
        ]
