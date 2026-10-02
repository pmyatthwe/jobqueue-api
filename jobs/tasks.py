import logging
import time
from django.utils import timezone
from celery import shared_task
from .models import Job, JobStatus

logger = logging.getLogger(__name__)


def _mark_started(job_id):
    Job.objects.filter(id=job_id).update(status=JobStatus.IN_PROGRESS, started_at=timezone.now())


def _mark_success(job_id, result):
    Job.objects.filter(id=job_id).update(
        status=JobStatus.SUCCESS, result=result, completed_at=timezone.now()
    )


def _mark_failed(job_id, error_message):
    Job.objects.filter(id=job_id).update(
        status=JobStatus.FAILED, error_message=error_message, completed_at=timezone.now()
    )


# bind=True gives access to `self`, which we need to call self.retry().
# autoretry_for + retry_backoff handles most of the retry logic declaratively,
# but we also update our own Job row so the status endpoint reflects reality —
# Celery's own retry state isn't visible through our API otherwise.
@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,      # exponential backoff: 1s, 2s, 4s, 8s...
    retry_backoff_max=60,    # cap the wait so retries don't take forever
    retry_jitter=True,       # adds randomness to avoid thundering-herd retries
    max_retries=3,
)
def process_image_resize(self, job_id):
    job = Job.objects.get(id=job_id)
    _mark_started(job_id)
    logger.info("Starting image resize for job %s", job_id)

    try:
        image_url = job.payload["image_url"]
        width = job.payload.get("width", 800)

        time.sleep(2) # for development
        if "fail" in image_url: 
            raise ValueError(f"Could not fetch image from {image_url}")

        result = {"resized_url": f"{image_url}?w={width}", "width": width}
        _mark_success(job_id, result)
        logger.info("Completed image resize for job %s", job_id)

    except Exception as exc:
        job.refresh_from_db()
  
        if self.request.retries >= self.max_retries:
            _mark_failed(job_id, str(exc))
            logger.error("Image resize job %s failed permanently: %s", job_id, exc)
        else:
            Job.objects.filter(id=job_id).update(retry_count=self.request.retries + 1)
            logger.warning(
                "Image resize job %s failed (attempt %s/%s), retrying: %s",
                job_id, self.request.retries + 1, self.max_retries, exc
            )
        raise


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)
def process_report_generation(self, job_id):
    job = Job.objects.get(id=job_id)
    _mark_started(job_id)
    logger.info("Starting report generation for job %s", job_id)

    try:
        report_type = job.payload.get("report_type", "summary")
        time.sleep(3) # for development

        result = {"report_type": report_type, "rows": 42, "generated_at": str(timezone.now())}
        _mark_success(job_id, result)
        logger.info("Completed report generation for job %s", job_id)

    except Exception as exc:
        job.refresh_from_db()
        if self.request.retries >= self.max_retries:
            _mark_failed(job_id, str(exc))
        else:
            Job.objects.filter(id=job_id).update(retry_count=self.request.retries + 1)
        raise


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)
def process_send_email(self, job_id):
    job = Job.objects.get(id=job_id)

    # Idempotency guard: if this job already succeeded (e.g. a retry fired
    # after the first attempt actually succeeded but the worker crashed
    # before updating status), don't send the email a second time.
    if job.status == JobStatus.SUCCESS:
        logger.info("Job %s already completed, skipping duplicate send", job_id)
        return

    _mark_started(job_id)
    logger.info("Starting email send for job %s", job_id)

    try:
        recipient = job.payload["recipient"]
        subject = job.payload.get("subject", "Notification")
        time.sleep(1)  # simulated SMTP call

        result = {"recipient": recipient, "subject": subject, "sent_at": str(timezone.now())}
        _mark_success(job_id, result)
        logger.info("Completed email send for job %s", job_id)

    except Exception as exc:
        job.refresh_from_db()
        if self.request.retries >= self.max_retries:
            _mark_failed(job_id, str(exc))
        else:
            Job.objects.filter(id=job_id).update(retry_count=self.request.retries + 1)
        raise


TASK_MAP = {
    "image_resize": process_image_resize,
    "report_generation": process_report_generation,
    "send_email": process_send_email,
}