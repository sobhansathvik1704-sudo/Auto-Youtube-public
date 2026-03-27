"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { videoJobsApi, VideoJob } from "@/lib/api";

const STATUS_COLORS: Record<string, string> = {
  queued: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300",
  running: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  complete: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  failed: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};

function StatusBadge({ status }: { status: string }) {
  const classes = STATUS_COLORS[status] ?? "bg-zinc-100 text-zinc-800 dark:bg-zinc-700 dark:text-zinc-200";
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${classes}`}>
      {status}
    </span>
  );
}

export default function DashboardPage() {
  const [jobs, setJobs] = useState<VideoJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    videoJobsApi
      .list()
      .then(setJobs)
      .catch(() => setError("Could not load jobs. Make sure the backend is running."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="min-h-screen bg-zinc-50 dark:bg-zinc-950 px-4 py-12">
      <div className="mx-auto max-w-4xl">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-50">
            📋 Video Jobs
          </h1>
          <Link
            href="/"
            className="rounded-lg bg-indigo-600 hover:bg-indigo-700 px-4 py-2 text-sm font-semibold text-white transition-colors"
          >
            + New Job
          </Link>
        </div>

        {loading && (
          <p className="text-zinc-500 dark:text-zinc-400">Loading jobs…</p>
        )}

        {error && (
          <p className="rounded-lg bg-red-50 dark:bg-red-900/30 px-4 py-3 text-sm text-red-700 dark:text-red-400">
            {error}
          </p>
        )}

        {!loading && !error && jobs.length === 0 && (
          <p className="text-zinc-500 dark:text-zinc-400">
            No jobs yet.{" "}
            <Link href="/" className="text-indigo-600 dark:text-indigo-400 hover:underline">
              Create one now
            </Link>
            .
          </p>
        )}

        {!loading && jobs.length > 0 && (
          <div className="overflow-hidden rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-sm">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-800/50">
                  <th className="px-6 py-3 text-left font-semibold text-zinc-700 dark:text-zinc-300">
                    ID
                  </th>
                  <th className="px-6 py-3 text-left font-semibold text-zinc-700 dark:text-zinc-300">
                    Topic
                  </th>
                  <th className="px-6 py-3 text-left font-semibold text-zinc-700 dark:text-zinc-300">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left font-semibold text-zinc-700 dark:text-zinc-300">
                    Created
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                {jobs.map((job) => (
                  <tr
                    key={job.id}
                    className="hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors"
                  >
                    <td className="px-6 py-4 font-mono text-xs text-zinc-500 dark:text-zinc-400 max-w-[10rem] truncate">
                      {job.id}
                    </td>
                    <td className="px-6 py-4 text-zinc-800 dark:text-zinc-200">
                      {job.topic}
                    </td>
                    <td className="px-6 py-4">
                      <StatusBadge status={job.status} />
                    </td>
                    <td className="px-6 py-4 text-zinc-500 dark:text-zinc-400">
                      {new Date(job.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}
