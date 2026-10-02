from rest_framework import serializers
from .models import Job, TaskType


class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = [
            "id", "task_type", "status", "payload", "result", "error_message",
            "retry_count", "max_retries", "created_at", "started_at", "completed_at",
        ]
        read_only_fields = [
            "id", "status", "result", "error_message", "retry_count",
            "created_at", "started_at", "completed_at",
        ]


class CreateJobSerializer(serializers.Serializer):
    """
    Validates the incoming request shape before we ever touch the database
    or queue anything — separate from JobSerializer since creation only
    needs task_type + payload, nothing else.
    """
    task_type = serializers.ChoiceField(choices=TaskType.choices)
    payload = serializers.JSONField()