"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { schedulesApi, Schedule } from "@/lib/api";
import { isAuthenticated, removeToken } from "@/lib/auth";

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

function ScheduleCard({
  schedule,
  onToggle,
  onDelete,
}: {
  schedule: Schedule;
  onToggle: (id: string, active: boolean) => void;
  onDelete: (id: string) => void;
}) {
  return (
    <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-sm p-5">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-50">
            {schedule.name}
          </h3>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5 font-mono">
            {schedule.cron_expression}
          </p>
        </div>
        <span
          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${
            schedule.is_active
              ? "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300"
              : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
          }`}
        >
          {schedule.is_active ? "Active" : "Paused"}
        </span>
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs text-zinc-500 dark:text-zinc-400 mb-4">
        <dt className="font-medium">Topics</dt>
        <dd className="truncate">{schedule.topics.join(", ")}</dd>
        <dt className="font-medium">Next run</dt>
        <dd className="truncate">{formatDate(schedule.next_run_at)}</dd>
        <dt className="font-medium">Last run</dt>
        <dd className="truncate">{formatDate(schedule.last_run_at)}</dd>
        <dt className="font-medium">Total runs</dt>
        <dd>{schedule.total_runs}</dd>
        <dt className="font-medium">Format</dt>
        <dd className="capitalize">{schedule.video_format}</dd>
        <dt className="font-medium">Auto-upload</dt>
        <dd>{schedule.auto_upload ? "Yes" : "No"}</dd>
      </dl>

      <div className="flex items-center gap-2">
        <button
          onClick={() => onToggle(schedule.id, !schedule.is_active)}
          className="flex-1 rounded-lg border border-zinc-300 dark:border-zinc-700 px-3 py-1.5 text-xs font-semibold text-zinc-700 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors"
        >
          {schedule.is_active ? "Pause" : "Resume"}
        </button>
        <button
          onClick={() => onDelete(schedule.id)}
          className="rounded-lg border border-red-200 dark:border-red-900 px-3 py-1.5 text-xs font-semibold text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 transition-colors"
        >
          Delete
        </button>
      </div>
    </div>
  );
}

export default function SchedulesPage() {
  const router = useRouter();
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace("/login");
      return;
    }
    schedulesApi
      .list()
      .then((data) => setSchedules(data))
      .catch(() => setError("Could not load schedules. Make sure the backend is running."))
      .finally(() => setLoading(false));
  }, [router]);

  function handleLogout() {
    removeToken();
    router.replace("/login");
  }

  async function handleToggle(id: string, active: boolean) {
    try {
      const updated = await schedulesApi.update(id, { is_active: active });
      setSchedules((prev) => prev.map((s) => (s.id === id ? updated : s)));
    } catch {
      setError("Failed to update schedule.");
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this schedule? This cannot be undone.")) return;
    try {
      await schedulesApi.delete(id);
      setSchedules((prev) => prev.filter((s) => s.id !== id));
    } catch {
      setError("Failed to delete schedule.");
    }
  }

  return (
    <main className="min-h-screen bg-zinc-50 dark:bg-zinc-950 px-4 py-12">
      <div className="mx-auto max-w-6xl">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-50">
              ⏰ Schedules
            </h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
              Auto-generate and publish videos on a recurring schedule.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/schedules/new"
              className="rounded-lg bg-indigo-600 hover:bg-indigo-700 px-4 py-2 text-sm font-semibold text-white transition-colors"
            >
              + New Schedule
            </Link>
            <Link
              href="/dashboard"
              className="text-sm text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 transition-colors"
            >
              ← Dashboard
            </Link>
            <button
              onClick={handleLogout}
              className="text-sm text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 transition-colors"
            >
              Sign out
            </button>
          </div>
        </div>

        {error && (
          <p className="rounded-lg bg-red-50 dark:bg-red-900/30 px-4 py-3 text-sm text-red-700 dark:text-red-400 mb-6">
            {error}
          </p>
        )}

        {loading && (
          <div className="flex items-center gap-2 text-zinc-500 dark:text-zinc-400">
            <svg className="w-5 h-5 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            <span>Loading schedules…</span>
          </div>
        )}

        {!loading && !error && schedules.length === 0 && (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="text-6xl mb-4">⏰</div>
            <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50 mb-2">
              No schedules yet
            </h2>
            <p className="text-zinc-500 dark:text-zinc-400 mb-6 max-w-sm">
              Set up a recurring schedule to auto-generate and publish videos hands-free.
            </p>
            <Link
              href="/schedules/new"
              className="rounded-lg bg-indigo-600 hover:bg-indigo-700 px-5 py-2.5 text-sm font-semibold text-white transition-colors"
            >
              + Create Schedule
            </Link>
          </div>
        )}

        {!loading && schedules.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {schedules.map((schedule) => (
              <ScheduleCard
                key={schedule.id}
                schedule={schedule}
                onToggle={handleToggle}
                onDelete={handleDelete}
              />
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
