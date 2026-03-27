"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { schedulesApi, projectsApi, Project } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";

const CRON_PRESETS = [
  { label: "Every day at 9 AM", value: "0 9 * * *" },
  { label: "Every Monday at 9 AM", value: "0 9 * * 1" },
  { label: "Every Monday & Thursday at 9 AM", value: "0 9 * * 1,4" },
  { label: "Every weekday at 9 AM", value: "0 9 * * 1-5" },
  { label: "Custom", value: "custom" },
];

const TIMEZONES = [
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "Europe/London",
  "Europe/Paris",
  "Europe/Berlin",
  "Asia/Kolkata",
  "Asia/Tokyo",
  "Asia/Singapore",
  "Australia/Sydney",
];

export default function NewSchedulePage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  // Form state
  const [projectId, setProjectId] = useState("");
  const [name, setName] = useState("");
  const [cronPreset, setCronPreset] = useState(CRON_PRESETS[0].value);
  const [customCron, setCustomCron] = useState("");
  const [timezone, setTimezone] = useState("UTC");
  const [topics, setTopics] = useState<string[]>([""]);
  const [category, setCategory] = useState("tech");
  const [audienceLevel, setAudienceLevel] = useState("beginner");
  const [languageMode, setLanguageMode] = useState("en");
  const [videoFormat, setVideoFormat] = useState("short");
  const [durationSeconds, setDurationSeconds] = useState(60);
  const [autoUpload, setAutoUpload] = useState(true);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace("/login");
      return;
    }
    projectsApi
      .list()
      .then((data) => {
        setProjects(data);
        if (data.length > 0) setProjectId(data[0].id);
      })
      .catch(() => setError("Could not load projects."))
      .finally(() => setLoading(false));
  }, [router]);

  const cronExpression = cronPreset === "custom" ? customCron : cronPreset;

  function addTopic() {
    setTopics((prev) => [...prev, ""]);
  }

  function removeTopic(index: number) {
    setTopics((prev) => prev.filter((_, i) => i !== index));
  }

  function updateTopic(index: number, value: string) {
    setTopics((prev) => prev.map((t, i) => (i === index ? value : t)));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    const validTopics = topics.filter((t) => t.trim().length > 0);
    if (validTopics.length === 0) {
      setError("Add at least one topic.");
      return;
    }
    if (!cronExpression.trim()) {
      setError("Please enter a cron expression.");
      return;
    }

    setSubmitting(true);
    try {
      await schedulesApi.create({
        project_id: projectId,
        name,
        cron_expression: cronExpression,
        timezone_str: timezone,
        topics: validTopics,
        category,
        audience_level: audienceLevel,
        language_mode: languageMode,
        video_format: videoFormat,
        duration_seconds: durationSeconds,
        auto_upload: autoUpload,
      });
      router.push("/schedules");
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Failed to create schedule. Check cron expression and try again.";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <main className="min-h-screen bg-zinc-50 dark:bg-zinc-950 flex items-center justify-center">
        <div className="flex items-center gap-2 text-zinc-500 dark:text-zinc-400">
          <svg className="w-5 h-5 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          <span>Loading…</span>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-zinc-50 dark:bg-zinc-950 px-4 py-12">
      <div className="mx-auto max-w-2xl">
        <div className="flex items-center gap-4 mb-8">
          <Link
            href="/schedules"
            className="text-sm text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 transition-colors"
          >
            ← Schedules
          </Link>
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">
            New Schedule
          </h1>
        </div>

        {error && (
          <p className="rounded-lg bg-red-50 dark:bg-red-900/30 px-4 py-3 text-sm text-red-700 dark:text-red-400 mb-6">
            {error}
          </p>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Project */}
          <div>
            <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
              Project
            </label>
            {projects.length === 0 ? (
              <p className="text-sm text-zinc-500 dark:text-zinc-400">
                No projects found.{" "}
                <Link href="/" className="text-indigo-600 dark:text-indigo-400 underline">
                  Create one first.
                </Link>
              </p>
            ) : (
              <select
                value={projectId}
                onChange={(e) => setProjectId(e.target.value)}
                required
                className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-50 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Schedule Name */}
          <div>
            <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
              Schedule Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              minLength={2}
              maxLength={255}
              placeholder="e.g. Weekly Python Tips"
              className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-50 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* Topics */}
          <div>
            <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
              Topics <span className="text-zinc-400 font-normal">(rotated round-robin)</span>
            </label>
            <div className="space-y-2">
              {topics.map((topic, i) => (
                <div key={i} className="flex gap-2">
                  <input
                    type="text"
                    value={topic}
                    onChange={(e) => updateTopic(i, e.target.value)}
                    placeholder={`Topic ${i + 1}`}
                    className="flex-1 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-50 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                  {topics.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeTopic(i)}
                      className="px-2 text-zinc-400 hover:text-red-500 transition-colors"
                    >
                      ✕
                    </button>
                  )}
                </div>
              ))}
            </div>
            <button
              type="button"
              onClick={addTopic}
              className="mt-2 text-sm text-indigo-600 dark:text-indigo-400 hover:underline"
            >
              + Add topic
            </button>
          </div>

          {/* Cron Expression */}
          <div>
            <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
              Schedule Frequency
            </label>
            <select
              value={cronPreset}
              onChange={(e) => setCronPreset(e.target.value)}
              className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 mb-2"
            >
              {CRON_PRESETS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
            {cronPreset !== "custom" && (
              <p className="text-xs text-zinc-500 dark:text-zinc-400 font-mono">
                Cron: <span className="text-zinc-700 dark:text-zinc-300">{cronPreset}</span>
              </p>
            )}
            {cronPreset === "custom" && (
              <input
                type="text"
                value={customCron}
                onChange={(e) => setCustomCron(e.target.value)}
                placeholder="e.g. 0 9 * * 1 (min ≥ 30 min apart)"
                className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm font-mono text-zinc-900 dark:text-zinc-50 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            )}
          </div>

          {/* Timezone */}
          <div>
            <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
              Timezone
            </label>
            <select
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-50 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              {TIMEZONES.map((tz) => (
                <option key={tz} value={tz}>
                  {tz}
                </option>
              ))}
            </select>
          </div>

          {/* Video Settings */}
          <fieldset className="rounded-xl border border-zinc-200 dark:border-zinc-800 p-4 space-y-4">
            <legend className="px-1 text-sm font-semibold text-zinc-700 dark:text-zinc-300">
              Video Settings
            </legend>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                  Category
                </label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-50 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  {["tech", "science", "education", "business", "health", "finance", "other"].map((c) => (
                    <option key={c} value={c} className="capitalize">{c}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                  Audience Level
                </label>
                <select
                  value={audienceLevel}
                  onChange={(e) => setAudienceLevel(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-50 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  {["beginner", "intermediate", "advanced"].map((l) => (
                    <option key={l} value={l} className="capitalize">{l}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                  Format
                </label>
                <select
                  value={videoFormat}
                  onChange={(e) => setVideoFormat(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-50 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  {["short", "standard", "long"].map((f) => (
                    <option key={f} value={f} className="capitalize">{f}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                  Language
                </label>
                <select
                  value={languageMode}
                  onChange={(e) => setLanguageMode(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-50 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  {["en", "te-en", "hi", "ta", "fr", "de", "es"].map((l) => (
                    <option key={l} value={l}>{l}</option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                Duration: <span className="text-zinc-900 dark:text-zinc-50">{durationSeconds}s</span>
              </label>
              <input
                type="range"
                min={30}
                max={300}
                step={30}
                value={durationSeconds}
                onChange={(e) => setDurationSeconds(Number(e.target.value))}
                className="w-full accent-indigo-600"
              />
              <div className="flex justify-between text-xs text-zinc-400 mt-0.5">
                <span>30s</span>
                <span>300s</span>
              </div>
            </div>

            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={autoUpload}
                onChange={(e) => setAutoUpload(e.target.checked)}
                className="w-4 h-4 accent-indigo-600"
              />
              <span className="text-sm text-zinc-700 dark:text-zinc-300">
                Auto-upload to YouTube after generation
              </span>
            </label>
          </fieldset>

          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={submitting || projects.length === 0}
              className="flex-1 rounded-lg bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 px-4 py-2.5 text-sm font-semibold text-white transition-colors"
            >
              {submitting ? "Creating…" : "Create Schedule"}
            </button>
            <Link
              href="/schedules"
              className="rounded-lg border border-zinc-300 dark:border-zinc-700 px-4 py-2.5 text-sm font-semibold text-zinc-700 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors"
            >
              Cancel
            </Link>
          </div>
        </form>
      </div>
    </main>
  );
}
