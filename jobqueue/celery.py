import os
from celery import Celery

# Tells Celery which Django settings module to use, so tasks can access
# the same database, installed apps, etc. as the web process.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobqueue.settings")

app = Celery("jobqueue")

# Reads all CELERY_* settings from Django's settings.py, with the CELERY_
# prefix removed (e.g. CELERY_BROKER_URL -> broker_url).
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discovers tasks.py inside every app listed in INSTALLED_APPS,
# so jobs/tasks.py is picked up automatically.
app.autodiscover_tasks()