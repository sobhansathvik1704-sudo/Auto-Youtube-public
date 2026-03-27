"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { videoJobsApi, VideoJob } from "@/lib/api";

const STATUS_COLORS: Record<string, string> = {
  queued: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300",
  researching: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  script_generated: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  planning_visuals: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  generating_audio: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  generating_subtitles: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  rendering: "bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300",
  packaging: "bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300",
  completed: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  failed: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};

function StatusBadge({ status }: { status: string }) {
  const classes =
    STATUS_COLORS[status] ??
    "bg-zinc-100 text-zinc-800 dark:bg-zinc-700 dark:text-zinc-200";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${classes}`}
    >
      {status}
    </span>
  );
}

export default function VideoJobDetailPage() {
  const params = useParams<{ job_id: string }>();
  const jobId = params.job_id;

  const [job, setJob] = useState<VideoJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [uploadStatus, setUploadStatus] = useState<
    "idle" | "loading" | "success" | "error"
  >("idle");
  const [uploadMessage, setUploadMessage] = useState("");

  const fetchJob = useCallback(() => {
    if (!jobId) return;
    videoJobsApi
      .get(jobId)
      .then(setJob)
      .catch(() => setError("Could not load job details."))
      .finally(() => setLoading(false));
  }, [jobId]);

  useEffect(() => {
    fetchJob();
  }, [fetchJob]);

  async function handleUpload() {
    if (!jobId) return;
    setUploadStatus("loading");
    setUploadMessage("");
    try {
      const response = await videoJobsApi.uploadToYouTube(jobId);
      setUploadStatus("success");
      setUploadMessage(response.message);
      // Refresh job data to show updated youtube_video_id once upload completes
      setTimeout(fetchJob, 3000);
    } catch (err: unknown) {
      setUploadStatus("error");
      const message =
        err instanceof Error ? err.message : "Upload request failed.";
      setUploadMessage(message);
    }
  }

  if (loading) {
    return (
      <main className="min-h-screen bg-zinc-50 dark:bg-zinc-950 px-4 py-12">
        <p className="text-zinc-500 dark:text-zinc-400">Loading…</p>
      </main>
    );
  }

  if (error || !job) {
    return (
      <main className="min-h-screen bg-zinc-50 dark:bg-zinc-950 px-4 py-12">
        <p className="text-red-600 dark:text-red-400">
          {error || "Job not found."}
        </p>
        <Link
          href="/dashboard"
          className="mt-4 inline-block text-indigo-600 dark:text-indigo-400 hover:underline"
        >
          ← Back to dashboard
        </Link>
      </main>
    );
  }

  const isCompleted = job.status === "completed";
  const alreadyUploaded = Boolean(job.youtube_video_id);

  return (
    <main className="min-h-screen bg-zinc-50 dark:bg-zinc-950 px-4 py-12">
      <div className="mx-auto max-w-3xl">
        {/* Back link */}
        <Link
          href="/dashboard"
          className="text-sm text-indigo-600 dark:text-indigo-400 hover:underline mb-6 inline-block"
        >
          ← Back to dashboard
        </Link>

        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50 mb-1">
              {job.topic}
            </h1>
            <p className="text-xs font-mono text-zinc-400 dark:text-zinc-500">
              {job.id}
            </p>
          </div>
          <StatusBadge status={job.status} />
        </div>

        {/* Details card */}
        <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-sm p-6 mb-6">
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-zinc-500 dark:text-zinc-400 font-medium mb-1">
                Format
              </dt>
              <dd className="text-zinc-800 dark:text-zinc-200">
                {job.video_format ?? "—"}
              </dd>
            </div>
            <div>
              <dt className="text-zinc-500 dark:text-zinc-400 font-medium mb-1">
                Language
              </dt>
              <dd className="text-zinc-800 dark:text-zinc-200">
                {job.language_mode ?? "—"}
              </dd>
            </div>
            <div>
              <dt className="text-zinc-500 dark:text-zinc-400 font-medium mb-1">
                Created
              </dt>
              <dd className="text-zinc-800 dark:text-zinc-200">
                {new Date(job.created_at).toLocaleString()}
              </dd>
            </div>
            {job.completed_at && (
              <div>
                <dt className="text-zinc-500 dark:text-zinc-400 font-medium mb-1">
                  Completed
                </dt>
                <dd className="text-zinc-800 dark:text-zinc-200">
                  {new Date(job.completed_at).toLocaleString()}
                </dd>
              </div>
            )}
          </dl>
        </div>

        {/* YouTube section */}
        <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-sm p-6">
          <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50 mb-4">
            📺 YouTube Upload
          </h2>

          {alreadyUploaded ? (
            <div>
              <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-3">
                This video has been uploaded to YouTube.
              </p>
              <a
                href={`https://youtu.be/${job.youtube_video_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 rounded-lg bg-red-600 hover:bg-red-700 px-4 py-2 text-sm font-semibold text-white transition-colors"
              >
                ▶ Watch on YouTube
              </a>
            </div>
          ) : (
            <div>
              <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-4">
                {isCompleted
                  ? "Your video is ready. Upload it to YouTube as a private video so you can review it before publishing."
                  : "The video must finish generating before it can be uploaded. Current status: "}
                {!isCompleted && <StatusBadge status={job.status} />}
              </p>

              <button
                onClick={handleUpload}
                disabled={!isCompleted || uploadStatus === "loading"}
                className="rounded-lg bg-red-600 hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 text-sm font-semibold text-white transition-colors"
              >
                {uploadStatus === "loading"
                  ? "Queuing upload…"
                  : "Upload to YouTube"}
              </button>

              {uploadMessage && (
                <p
                  className={`mt-3 text-sm rounded-lg px-3 py-2 ${
                    uploadStatus === "success"
                      ? "bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                      : "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                  }`}
                >
                  {uploadMessage}
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
