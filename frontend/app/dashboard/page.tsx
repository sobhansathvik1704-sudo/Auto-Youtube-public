"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { videoJobsApi, VideoJob } from "@/lib/api";
import { isAuthenticated, removeToken } from "@/lib/auth";

const STATUS_COLORS: Record<string, string> = {
  queued: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300",
  generating_script: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  generating_audio: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  generating_subtitles: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  rendering: "bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300",
  packaging: "bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300",
  completed: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  failed: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};

function statusGroup(status: string): "completed" | "failed" | "in-progress" | "queued" {
  if (status === "completed") return "completed";
  if (status === "failed") return "failed";
  if (status === "queued") return "queued";
  return "in-progress";
}

function StatusBadge({ status }: { status: string }) {
  const classes = STATUS_COLORS[status] ?? "bg-zinc-100 text-zinc-800 dark:bg-zinc-700 dark:text-zinc-200";
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${classes}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

function JobCard({ job }: { job: VideoJob }) {
  const group = statusGroup(job.status);
  const borderColor =
    group === "completed"
      ? "border-green-200 dark:border-green-800"
      : group === "failed"
      ? "border-red-200 dark:border-red-800"
      : group === "in-progress"
      ? "border-indigo-200 dark:border-indigo-800"
      : "border-zinc-200 dark:border-zinc-800";

  return (
    <Link
      href={`/dashboard/${job.id}`}
      className={`group block rounded-2xl border ${borderColor} bg-white dark:bg-zinc-900 shadow-sm hover:shadow-md transition-shadow p-5`}
    >
      {/* Status badge row */}
      <div className="flex items-center justify-between mb-3">
        <StatusBadge status={job.status} />
        {group === "in-progress" && (
          <span className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />
        )}
      </div>

      {/* Title */}
      <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-50 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors line-clamp-2 mb-3">
        {job.topic}
      </h3>

      {/* Meta */}
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs text-zinc-500 dark:text-zinc-400">
        {job.video_format && (
          <>
            <dt className="font-medium">Format</dt>
            <dd className="truncate capitalize">{job.video_format}</dd>
          </>
        )}
        {job.duration_seconds && (
          <>
            <dt className="font-medium">Duration</dt>
            <dd>{job.duration_seconds}s</dd>
          </>
        )}
        <dt className="font-medium">Created</dt>
        <dd className="truncate">{new Date(job.created_at).toLocaleDateString()}</dd>
      </dl>
    </Link>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<VideoJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace("/login");
      return;
    }
    videoJobsApi
      .list()
      .then((data) => {
        // Sort most recent first
        const sorted = [...data].sort(
          (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        );
        setJobs(sorted);
      })
      .catch(() => setError("Could not load jobs. Make sure the backend is running."))
      .finally(() => setLoading(false));
  }, [router]);

  function handleLogout() {
    removeToken();
    router.replace("/login");
  }

  return (
    <main className="min-h-screen bg-zinc-50 dark:bg-zinc-950 px-4 py-12">
      <div className="mx-auto max-w-6xl">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-50">
            📋 My Videos
          </h1>
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="rounded-lg bg-indigo-600 hover:bg-indigo-700 px-4 py-2 text-sm font-semibold text-white transition-colors"
            >
              + New Video
            </Link>
            <Link
              href="/schedules"
              className="rounded-lg border border-indigo-300 dark:border-indigo-700 px-4 py-2 text-sm font-semibold text-indigo-700 dark:text-indigo-300 hover:bg-indigo-50 dark:hover:bg-indigo-900/30 transition-colors"
            >
              ⏰ Schedules
            </Link>
            <button
              onClick={handleLogout}
              className="text-sm text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 transition-colors"
            >
              Sign out
            </button>
          </div>
        </div>

        {loading && (
          <div className="flex items-center gap-2 text-zinc-500 dark:text-zinc-400">
            <svg className="w-5 h-5 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            <span>Loading jobs…</span>
          </div>
        )}

        {error && (
          <p className="rounded-lg bg-red-50 dark:bg-red-900/30 px-4 py-3 text-sm text-red-700 dark:text-red-400">
            {error}
          </p>
        )}

        {!loading && !error && jobs.length === 0 && (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="text-6xl mb-4">🎬</div>
            <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50 mb-2">
              No videos yet
            </h2>
            <p className="text-zinc-500 dark:text-zinc-400 mb-6 max-w-sm">
              Create your first AI-generated YouTube video in just a few seconds.
            </p>
            <Link
              href="/"
              className="rounded-lg bg-indigo-600 hover:bg-indigo-700 px-5 py-2.5 text-sm font-semibold text-white transition-colors"
            >
              + Create Video
            </Link>
          </div>
        )}

        {!loading && jobs.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {jobs.map((job) => (
              <JobCard key={job.id} job={job} />
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
