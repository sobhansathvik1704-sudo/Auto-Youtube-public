"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { videoJobsApi, projectsApi } from "@/lib/api";
import { isAuthenticated, removeToken } from "@/lib/auth";

export default function Home() {
  const router = useRouter();
  const [projectId, setProjectId] = useState("");
  const [topic, setTopic] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");

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
    setMessage("");
    try {
      const job = await videoJobsApi.create({ project_id: projectId, topic });
      setStatus("success");
      setMessage(`Job created! ID: ${job.id} — Status: ${job.status}`);
      setTopic("");
    } catch {
      setStatus("error");
      setMessage("Failed to create job. Check that the backend is running and you are authenticated.");
    }
  }

  return (
    <main className="min-h-screen bg-zinc-50 dark:bg-zinc-950 flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-lg bg-white dark:bg-zinc-900 rounded-2xl shadow-md p-8">
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
          Submit a new video topic and the pipeline will take care of the rest.
        </p>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <label
              htmlFor="projectId"
              className="text-sm font-medium text-zinc-700 dark:text-zinc-300"
            >
              Project ID
            </label>
            <input
              id="projectId"
              type="text"
              required
              placeholder="e.g. 123e4567-e89b-12d3-a456-426614174000"
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              className="rounded-lg border border-zinc-300 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label
              htmlFor="topic"
              className="text-sm font-medium text-zinc-700 dark:text-zinc-300"
            >
              Video Topic
            </label>
            <input
              id="topic"
              type="text"
              required
              placeholder="e.g. How does async/await work in JavaScript?"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              className="rounded-lg border border-zinc-300 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <button
            type="submit"
            disabled={status === "loading"}
            className="mt-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 px-4 py-2 text-sm font-semibold text-white transition-colors"
          >
            {status === "loading" ? "Submitting…" : "Generate Video"}
          </button>
        </form>

        {message && (
          <p
            className={`mt-4 rounded-lg px-4 py-2 text-sm ${
              status === "success"
                ? "bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                : "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400"
            }`}
          >
            {message}
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
