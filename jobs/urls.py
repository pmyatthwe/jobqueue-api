from django.urls import path
from .views import JobListCreateView, JobDetailView, JobRetryView

urlpatterns = [
    path("jobs", JobListCreateView.as_view(), name="job-list-create"),
    path("jobs/<uuid:id>", JobDetailView.as_view(), name="job-detail"),
    path("jobs/<uuid:id>/retry", JobRetryView.as_view(), name="job-retry"),
]