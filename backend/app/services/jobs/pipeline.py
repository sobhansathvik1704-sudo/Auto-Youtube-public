from app.services.jobs.tasks import process_video_job


def enqueue_video_job(job_id: str) -> None:
    process_video_job.delay(job_id)