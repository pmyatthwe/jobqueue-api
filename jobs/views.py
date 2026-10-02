from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Job, JobStatus
from .serializers import JobSerializer, CreateJobSerializer
from .tasks import TASK_MAP


class JobListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/jobs   — list jobs, filterable by ?status= and ?task_type=
    POST /api/jobs   — submit a new job; returns immediately with a job ID
                        while the actual work happens asynchronously.
    """
    queryset = Job.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "task_type"]

    def get_serializer_class(self):
        return CreateJobSerializer if self.request.method == "POST" else JobSerializer

    def create(self, request, *args, **kwargs):
        input_serializer = CreateJobSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        job = Job.objects.create(
            task_type=input_serializer.validated_data["task_type"],
            payload=input_serializer.validated_data["payload"],
        )

        # Queue the task by name so the API process never imports/executes
        # task logic directly — it only ever talks to Redis via Celery.
        task_fn = TASK_MAP[job.task_type]
        task_fn.delay(str(job.id))

        return Response(JobSerializer(job).data, status=status.HTTP_201_CREATED)


class JobDetailView(generics.RetrieveAPIView):
    """GET /api/jobs/{id} — poll this to check status and get the result."""
    queryset = Job.objects.all()
    serializer_class = JobSerializer
    lookup_field = "id"


class JobRetryView(APIView):
    """POST /api/jobs/{id}/retry — manually re-queue a failed job."""

    def post(self, request, id):
        try:
            job = Job.objects.get(id=id)
        except Job.DoesNotExist:
            return Response({"detail": "Job not found."}, status=status.HTTP_404_NOT_FOUND)

        if job.status != JobStatus.FAILED:
            return Response(
                {"detail": "Only failed jobs can be retried."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        job.status = JobStatus.PENDING
        job.retry_count = 0
        job.error_message = None
        job.save(update_fields=["status", "retry_count", "error_message"])

        task_fn = TASK_MAP[job.task_type]
        task_fn.delay(str(job.id))

        return Response(JobSerializer(job).data, status=status.HTTP_200_OK)