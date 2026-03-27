"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { videoJobsApi, VideoJob, SEOMetadata } from "@/lib/api";
import { isAuthenticated, removeToken, getToken } from "@/lib/auth";

const PIPELINE_STEPS = [
  { key: "queued", label: "Queued" },
  { key: "generating_script", label: "Script" },
  { key: "generating_audio", label: "Audio" },
  { key: "generating_subtitles", label: "Subtitles" },
  { key: "rendering", label: "Rendering" },
  { key: "packaging", label: "Packaging" },
  { key: "completed", label: "Completed" },
];

function getStepIndex(status: string): number {
  const idx = PIPELINE_STEPS.findIndex((s) => s.key === status);
  return idx === -1 ? 0 : idx;
}

function ProgressStepper({ status }: { status: string }) {
  const isFailed = status === "failed";
  const currentIdx = isFailed ? -1 : getStepIndex(status);
  const isCompleted = status === "completed";

  return (
    <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-sm p-6 mb-6">
      <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50 mb-5">
        Pipeline Progress
      </h2>
      {isFailed ? (
        <div className="flex items-center gap-3 text-red-600 dark:text-red-400">
          <span className="flex items-center justify-center w-8 h-8 rounded-full bg-red-100 dark:bg-red-900/40 text-lg font-bold">✕</span>
          <span className="font-medium">Job failed — check logs for details.</span>
        </div>
      ) : (
        <div className="flex items-center gap-1 overflow-x-auto pb-1">
          {PIPELINE_STEPS.map((step, idx) => {
            const isDone = idx < currentIdx || isCompleted;
            const isCurrent = !isCompleted && idx === currentIdx;
            return (
              <div key={step.key} className="flex items-center min-w-0">
                {/* Step circle */}
                <div className="flex flex-col items-center gap-1.5">
                  <div
                    className={`flex items-center justify-center w-8 h-8 rounded-full text-sm font-semibold transition-all ${
                      isDone
                        ? "bg-green-500 text-white"
                        : isCurrent
                        ? "bg-indigo-600 text-white ring-2 ring-indigo-300 dark:ring-indigo-700 animate-pulse"
                        : "bg-zinc-200 dark:bg-zinc-700 text-zinc-500 dark:text-zinc-400"
                    }`}
                  >
                    {isDone ? "✓" : idx + 1}
                  </div>
                  <span
                    className={`text-xs whitespace-nowrap ${
                      isDone
                        ? "text-green-600 dark:text-green-400 font-medium"
                        : isCurrent
                        ? "text-indigo-600 dark:text-indigo-400 font-semibold"
                        : "text-zinc-400 dark:text-zinc-500"
                    }`}
                  >
                    {step.label}
                  </span>
                </div>
                {/* Connector line */}
                {idx < PIPELINE_STEPS.length - 1 && (
                  <div
                    className={`h-0.5 w-6 sm:w-10 flex-shrink-0 mx-1 rounded ${
                      idx < currentIdx || isCompleted
                        ? "bg-green-500"
                        : "bg-zinc-200 dark:bg-zinc-700"
                    }`}
                  />
                )}
              </div>
            );
          })}
        </div>
      )}
      {isCompleted && (
        <p className="mt-4 text-sm text-green-600 dark:text-green-400 font-medium flex items-center gap-2">
          <span className="text-lg">🎉</span> Your video is ready!
        </p>
      )}
    </div>
  );
}

const STATUS_COLORS: Record<string, string> = {
  queued: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300",
  researching: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  generating_script: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
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

function VideoPlayer({ jobId }: { jobId: string }) {
  const [videoSrc, setVideoSrc] = useState<string | null>(null);
  const [videoLoading, setVideoLoading] = useState(true);
  const [videoError, setVideoError] = useState("");
  const objectUrlRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setVideoLoading(true);
    setVideoError("");

    async function loadVideo() {
      try {
        const token = getToken();
        const baseUrl =
          process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

        // First try the S3 presigned URL, fall back to local file serving
        let url: string | null = null;
        try {
          const info = await videoJobsApi.getDownloadUrl(jobId);
          if (info.download_url) {
            url = info.download_url;
          }
        } catch {
          // fall through to local endpoint
        }

        if (!url) {
          const response = await fetch(
            `${baseUrl}/video-jobs/${jobId}/download/file`,
            { headers: { Authorization: `Bearer ${token}` } }
          );
          if (!response.ok) throw new Error("Could not load video");
          const blob = await response.blob();
          // Create a blob object URL and track it for cleanup on unmount.
          // S3 presigned URLs are plain https:// links and don't need revocation.
          url = URL.createObjectURL(blob);
          objectUrlRef.current = url;
        }

        if (!cancelled) setVideoSrc(url);
      } catch {
        if (!cancelled) setVideoError("Could not load video preview.");
      } finally {
        if (!cancelled) setVideoLoading(false);
      }
    }

    loadVideo();

    return () => {
      cancelled = true;
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
    };
  }, [jobId]);

  if (videoLoading) {
    return (
      <div className="flex items-center justify-center h-48 rounded-xl bg-zinc-100 dark:bg-zinc-800">
        <div className="flex flex-col items-center gap-2 text-zinc-500 dark:text-zinc-400">
          <svg className="w-8 h-8 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          <span className="text-sm">Loading video…</span>
        </div>
      </div>
    );
  }

  if (videoError || !videoSrc) {
    return (
      <p className="text-sm text-red-600 dark:text-red-400">{videoError || "Video unavailable."}</p>
    );
  }

  return (
    <video
      src={videoSrc}
      controls
      className="w-full rounded-xl bg-black"
      style={{ maxHeight: "480px" }}
    />
  );
}

function SEOPreview({ seo }: { seo: SEOMetadata }) {
  const [showFullDesc, setShowFullDesc] = useState(false);
  const TITLE_MAX = 100;
  const DESC_PREVIEW_CHARS = 300;
  const titleLen = seo.title.length;
  const titleColor =
    titleLen <= 60
      ? "text-green-600 dark:text-green-400"
      : titleLen <= 100
      ? "text-yellow-600 dark:text-yellow-400"
      : "text-red-600 dark:text-red-400";

  const descLen = seo.description.length;
  const descColor =
    descLen >= 300 && descLen <= 5000
      ? "text-green-600 dark:text-green-400"
      : "text-yellow-600 dark:text-yellow-400";

  const tagCount = seo.tags.length;
  const tagColor =
    tagCount >= 15
      ? "text-green-600 dark:text-green-400"
      : tagCount >= 8
      ? "text-yellow-600 dark:text-yellow-400"
      : "text-red-600 dark:text-red-400";

  const YOUTUBE_CATEGORIES: Record<number, string> = {
    28: "Science & Technology",
    27: "Education",
    24: "Entertainment",
    22: "People & Blogs",
    20: "Gaming",
    10: "Music",
    17: "Sports",
  };

  return (
    <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-sm p-6 mb-6">
      <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50 mb-5">
        🔍 SEO Preview
      </h2>

      {/* Quality indicators */}
      <div className="flex flex-wrap gap-3 mb-5 text-xs font-medium">
        <span className={`flex items-center gap-1 ${titleColor}`}>
          📝 Title: {titleLen}/{TITLE_MAX} chars
        </span>
        <span className={`flex items-center gap-1 ${descColor}`}>
          📄 Description: {descLen} chars
        </span>
        <span className={`flex items-center gap-1 ${tagColor}`}>
          🏷️ Tags: {tagCount}
        </span>
      </div>

      {/* Title */}
      <div className="mb-4">
        <p className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide mb-1">
          Title
        </p>
        <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200 bg-zinc-50 dark:bg-zinc-800 rounded-lg px-3 py-2">
          {seo.title}
        </p>
      </div>

      {/* Description */}
      <div className="mb-4">
        <p className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide mb-1">
          Description
        </p>
        <div className="text-sm text-zinc-700 dark:text-zinc-300 bg-zinc-50 dark:bg-zinc-800 rounded-lg px-3 py-2 whitespace-pre-wrap">
          {showFullDesc
            ? seo.description
            : seo.description.slice(0, DESC_PREVIEW_CHARS) +
              (seo.description.length > DESC_PREVIEW_CHARS ? "…" : "")}
        </div>
        {seo.description.length > DESC_PREVIEW_CHARS && (
          <button
            onClick={() => setShowFullDesc((v) => !v)}
            className="mt-1 text-xs text-indigo-600 dark:text-indigo-400 hover:underline"
          >
            {showFullDesc ? "Show less" : "Show more"}
          </button>
        )}
      </div>

      {/* Tags */}
      <div className="mb-4">
        <p className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide mb-2">
          Tags
        </p>
        <div className="flex flex-wrap gap-1.5">
          {seo.tags.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center rounded-full bg-indigo-50 dark:bg-indigo-900/30 px-2.5 py-0.5 text-xs font-medium text-indigo-700 dark:text-indigo-300"
            >
              {tag}
            </span>
          ))}
        </div>
      </div>

      {/* Hashtags */}
      {seo.hashtags.length > 0 && (
        <div className="mb-4">
          <p className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide mb-2">
            Hashtags
          </p>
          <div className="flex flex-wrap gap-1.5">
            {seo.hashtags.map((ht) => (
              <span
                key={ht}
                className="inline-flex items-center rounded-full bg-blue-50 dark:bg-blue-900/30 px-2.5 py-0.5 text-xs font-medium text-blue-700 dark:text-blue-300"
              >
                {ht}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Category */}
      <div>
        <p className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide mb-1">
          YouTube Category
        </p>
        <p className="text-sm text-zinc-700 dark:text-zinc-300">
          {YOUTUBE_CATEGORIES[seo.category_id] ?? `Category ${seo.category_id}`}{" "}
          <span className="text-zinc-400 dark:text-zinc-500">(ID: {seo.category_id})</span>
        </p>
      </div>
    </div>
  );
}

export default function VideoJobDetailPage() {
  const params = useParams<{ job_id: string }>();
  const jobId = params.job_id;

  const [job, setJob] = useState<VideoJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [seoData, setSeoData] = useState<SEOMetadata | null>(null);
  const [uploadStatus, setUploadStatus] = useState<
    "idle" | "loading" | "success" | "error"
  >("idle");
  const [uploadMessage, setUploadMessage] = useState("");
  const [downloadLoading, setDownloadLoading] = useState(false);
  const [downloadError, setDownloadError] = useState("");

  const fetchJob = useCallback(() => {
    if (!jobId) return;
    videoJobsApi
      .get(jobId)
      .then((data) => {
        setJob(data);
        setLoading(false);
      })
      .catch(() => {
        setError("Could not load job details.");
        setLoading(false);
      });
  }, [jobId]);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace("/login");
      return;
    }
    fetchJob();
  }, [fetchJob, router]);

  // Auto-refresh every 3 seconds while job is still in progress
  useEffect(() => {
    if (!job) return;
    if (job.status === "completed" || job.status === "failed") return;
    const timer = setInterval(fetchJob, 3000);
    return () => clearInterval(timer);
  }, [job, fetchJob]);

  function handleLogout() {
    removeToken();
    router.replace("/login");
  }

  async function handleDownload() {
    if (!jobId) return;
    setDownloadLoading(true);
    setDownloadError("");
    try {
      const info = await videoJobsApi.getDownloadUrl(jobId);
      if (info.download_url) {
        // S3 presigned URL
        window.open(info.download_url, "_blank", "noopener,noreferrer");
      } else {
        // Local storage — use the file serving endpoint
        const token = getToken();
        const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";
        const response = await fetch(`${baseUrl}/video-jobs/${jobId}/download/file`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) throw new Error("Download failed");
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        const disposition = response.headers.get("Content-Disposition");
        const match = disposition?.match(/filename="?([^"]+)"?/);
        a.download = match?.[1] ?? `video_${jobId}.mp4`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
      }
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Could not fetch download link.";
      setDownloadError(message);
    } finally {
      setDownloadLoading(false);
    }
  }

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
        <div className="flex items-center justify-between mb-6">
          <Link
            href="/dashboard"
            className="text-sm text-indigo-600 dark:text-indigo-400 hover:underline"
          >
            ← Back to dashboard
          </Link>
          <button
            onClick={handleLogout}
            className="text-sm text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 transition-colors"
          >
            Sign out
          </button>
        </div>

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

        {/* Progress stepper */}
        <ProgressStepper status={job.status} />

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

        {/* Video preview + download section */}
        {isCompleted && (
          <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-sm p-6 mb-6">
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50 mb-4">
              🎬 Video Preview
            </h2>
            <VideoPlayer jobId={jobId} />
            <div className="mt-4 flex items-center gap-3">
              <button
                onClick={handleDownload}
                disabled={downloadLoading}
                className="rounded-lg bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 text-sm font-semibold text-white transition-colors"
              >
                {downloadLoading ? "Fetching link…" : "⬇ Download Video"}
              </button>
            </div>
            {downloadError && (
              <p className="mt-3 text-sm rounded-lg px-3 py-2 bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400">
                {downloadError}
              </p>
            )}
          </div>
        )}

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
