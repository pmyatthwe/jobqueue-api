import uuid
from django.db import models


class TaskType(models.TextChoices):
    IMAGE_RESIZE = "image_resize", "Image Resize"
    REPORT_GENERATION = "report_generation", "Report Generation"
    SEND_EMAIL = "send_email", "Send Email"


class JobStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    IN_PROGRESS = "in_progress", "In Progress"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"


class Job(models.Model):
    """
    Represents one unit of background work. The API only ever creates and
    reads rows here — it never does the actual work itself. A Celery worker
    picks up the corresponding task, does the work, and updates this row's
    status/result as it goes. Storing this in Postgres (not just Redis)
    means job history survives even after Redis's result backend expires.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task_type = models.CharField(max_length=32, choices=TaskType.choices)
    status = models.CharField(max_length=16, choices=JobStatus.choices, default=JobStatus.PENDING)

    payload = models.JSONField(help_text="Input parameters for the task, e.g. image URL or report filters")
    result = models.JSONField(null=True, blank=True, help_text="Output of a successful task")
    error_message = models.TextField(null=True, blank=True)

    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=3)

    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["task_type"]),
        ]

    def __str__(self):
        return f"{self.task_type} ({self.status}) — {self.id}"