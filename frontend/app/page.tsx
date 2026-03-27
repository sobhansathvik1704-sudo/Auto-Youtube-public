"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { videoJobsApi, projectsApi } from "@/lib/api";
import { isAuthenticated, removeToken } from "@/lib/auth";

const CATEGORIES = [
  { value: "tech", label: "Tech" },
  { value: "education", label: "Education" },
  { value: "entertainment", label: "Entertainment" },
  { value: "finance", label: "Finance" },
  { value: "health", label: "Health" },
  { value: "lifestyle", label: "Lifestyle" },
  { value: "science", label: "Science" },
  { value: "gaming", label: "Gaming" },
];

const AUDIENCE_LEVELS = [
  { value: "beginner", label: "Beginner" },
  { value: "intermediate", label: "Intermediate" },
  { value: "advanced", label: "Advanced" },
];

const VIDEO_FORMATS = [
  { value: "short", label: "Short (< 60s)" },
  { value: "long", label: "Long (> 60s)" },
];

const LANGUAGES = [
  { value: "en", label: "English" },
  { value: "te-en", label: "Telugu + English" },
  { value: "hi-en", label: "Hindi + English" },
];

const inputClass =
  "rounded-lg border border-zinc-300 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 w-full";

const selectClass =
  "rounded-lg border border-zinc-300 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 w-full";

export default function Home() {
  const router = useRouter();
  const [projectId, setProjectId] = useState("");
  const [topic, setTopic] = useState("");
  const [category, setCategory] = useState("tech");
  const [audienceLevel, setAudienceLevel] = useState("beginner");
  const [videoFormat, setVideoFormat] = useState("short");
  const [duration, setDuration] = useState(60);
  const [language, setLanguage] = useState("en");
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace("/login");
      return;
    }

    async function loadProject() {
      try {
        const projects = await projectsApi.list();
        if (projects.length > 0) {
          setProjectId(projects[0].id);
        } else {
          const created = await projectsApi.create(
            "Default Channel",
            "Auto-created project"
          );
          setProjectId(created.id);
        }
      } catch {
        // If fetching projects fails the 401 interceptor will redirect to login
      }
    }

    loadProject();
  }, [router]);

  function handleLogout() {
    removeToken();
    router.replace("/login");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("loading");
    setErrorMessage("");
    try {
      const job = await videoJobsApi.create({
        project_id: projectId,
        topic,
        category,
        audience_level: audienceLevel,
        video_format: videoFormat,
        duration_seconds: duration,
        language_mode: language,
      });
      // Redirect immediately to the job detail page to see progress
      router.push(`/dashboard/${job.id}`);
    } catch {
      setStatus("error");
      setErrorMessage(
        "Failed to create job. Check that the backend is running and you are authenticated."
      );
    }
  }

  return (
    <main className="min-h-screen bg-zinc-50 dark:bg-zinc-950 flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-xl bg-white dark:bg-zinc-900 rounded-2xl shadow-md p-8">
        <div className="flex items-start justify-between mb-2">
          <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-50">
            🎬 Auto-YouTube
          </h1>
          <button
            onClick={handleLogout}
            className="text-sm text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 transition-colors"
          >
            Sign out
          </button>
        </div>
        <p className="text-zinc-500 dark:text-zinc-400 mb-8">
          Submit a video topic and the AI pipeline will generate, render, and prepare it for YouTube.
        </p>

        <form onSubmit={handleSubmit} className="flex flex-col gap-6">
          {/* Topic */}
          <fieldset className="flex flex-col gap-4">
            <legend className="text-xs font-semibold uppercase tracking-widest text-zinc-400 dark:text-zinc-500 mb-1">
              Content
            </legend>
            <div className="flex flex-col gap-1">
              <label htmlFor="topic" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Video Topic <span className="text-red-500">*</span>
              </label>
              <input
                id="topic"
                type="text"
                required
                placeholder="e.g. How does async/await work in JavaScript?"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                className={inputClass}
              />
            </div>

            <div className="flex flex-col gap-1">
              <label htmlFor="category" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Category
              </label>
              <select
                id="category"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className={selectClass}
              >
                {CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-1">
              <label htmlFor="audienceLevel" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Audience Level
              </label>
              <select
                id="audienceLevel"
                value={audienceLevel}
                onChange={(e) => setAudienceLevel(e.target.value)}
                className={selectClass}
              >
                {AUDIENCE_LEVELS.map((a) => (
                  <option key={a.value} value={a.value}>{a.label}</option>
                ))}
              </select>
            </div>
          </fieldset>

          {/* Format */}
          <fieldset className="flex flex-col gap-4">
            <legend className="text-xs font-semibold uppercase tracking-widest text-zinc-400 dark:text-zinc-500 mb-1">
              Format
            </legend>
            <div className="flex flex-col gap-1">
              <label htmlFor="videoFormat" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Video Format
              </label>
              <select
                id="videoFormat"
                value={videoFormat}
                onChange={(e) => setVideoFormat(e.target.value)}
                className={selectClass}
              >
                {VIDEO_FORMATS.map((f) => (
                  <option key={f.value} value={f.value}>{f.label}</option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-1">
              <label htmlFor="duration" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Duration: <span className="font-semibold text-indigo-600 dark:text-indigo-400">{duration}s</span>
              </label>
              <input
                id="duration"
                type="range"
                min={30}
                max={300}
                step={10}
                value={duration}
                onChange={(e) => setDuration(Number(e.target.value))}
                className="accent-indigo-600"
              />
              <div className="flex justify-between text-xs text-zinc-400 dark:text-zinc-500">
                <span>30s</span>
                <span>300s</span>
              </div>
            </div>

            <div className="flex flex-col gap-1">
              <label htmlFor="language" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Language
              </label>
              <select
                id="language"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className={selectClass}
              >
                {LANGUAGES.map((l) => (
                  <option key={l.value} value={l.value}>{l.label}</option>
                ))}
              </select>
            </div>
          </fieldset>

          <button
            type="submit"
            disabled={status === "loading" || !projectId}
            className="mt-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 px-4 py-2.5 text-sm font-semibold text-white transition-colors"
          >
            {status === "loading" ? "Submitting…" : "Generate Video →"}
          </button>
        </form>

        {errorMessage && (
          <p className="mt-4 rounded-lg px-4 py-2 text-sm bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400">
            {errorMessage}
          </p>
        )}

        <div className="mt-8 border-t border-zinc-200 dark:border-zinc-800 pt-4 text-center">
          <Link
            href="/dashboard"
            className="text-sm text-indigo-600 dark:text-indigo-400 hover:underline"
          >
            View all video jobs →
          </Link>
        </div>
      </div>
    </main>
  );
}
