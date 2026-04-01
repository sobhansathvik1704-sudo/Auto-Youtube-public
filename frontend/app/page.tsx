"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { videoJobsApi, projectsApi } from "@/lib/api";
import { isAuthenticated, removeToken } from "@/lib/auth";

const CATEGORIES = [
  { value: "tech", label: "Tech" },
  { value: "finance", label: "Finance" },
  { value: "education", label: "Education" },
  { value: "science", label: "Science" },
  { value: "history", label: "History" },
  { value: "health", label: "Health" },
  { value: "motivation", label: "Motivation" },
  { value: "business", label: "Business" },
  { value: "entertainment", label: "Entertainment" },
  { value: "gaming", label: "Gaming" },
  { value: "lifestyle", label: "Lifestyle" },
];

const SUBCATEGORIES: Record<string, string[]> = {
  tech: [
    "Programming",
    "Web Development",
    "Operating Systems",
    "AI / ML",
    "DevOps / Cloud",
    "Databases",
    "Cybersecurity",
    "Networking",
    "System Design",
    "Mobile Development",
  ],
  finance: [
    "Investing",
    "Budgeting",
    "Trading",
    "Economics",
    "Personal Finance",
    "Crypto",
    "Real Estate",
  ],
  education: [
    "Physics",
    "Chemistry",
    "Biology",
    "Mathematics",
    "General Science",
    "History",
    "Geography",
    "Literature",
  ],
  science: [
    "Physics",
    "Chemistry",
    "Biology",
    "Astronomy",
    "Earth Science",
    "Environmental Science",
  ],
  history: [
    "Ancient History",
    "Medieval History",
    "Modern History",
    "Wars & Conflicts",
    "Biographies",
    "Civilizations",
  ],
  health: [
    "Fitness",
    "Nutrition",
    "Mental Health",
    "Medical Basics",
    "Wellness",
    "Sleep & Recovery",
  ],
  motivation: [
    "Productivity",
    "Mindset",
    "Habits",
    "Discipline",
    "Communication",
    "Personal Growth",
  ],
  business: [
    "Startups",
    "Marketing",
    "Leadership",
    "Career",
    "Freelancing",
    "Interview Prep",
  ],
  entertainment: [
    "Movies",
    "Anime",
    "Gaming",
    "Pop Culture",
    "Music",
    "Storytelling",
  ],
  gaming: [
    "Game Reviews",
    "Esports",
    "Game Development",
    "Game Guides",
    "Gaming History",
  ],
  lifestyle: [
    "Travel",
    "Food",
    "Fashion",
    "Home & Decor",
    "Relationships",
  ],
};

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

const AVATAR_MODES = [
  { value: "static", label: "Static Slides (default)" },
  { value: "did", label: "AI Avatar — D-ID (requires API key)" },
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
  const [subcategory, setSubcategory] = useState<string>("");
  const [audienceLevel, setAudienceLevel] = useState("beginner");
  const [videoFormat, setVideoFormat] = useState("short");
  const [duration, setDuration] = useState(60);
  const [language, setLanguage] = useState("en");
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [avatarMode, setAvatarMode] = useState("static");

  // Reset subcategory when category changes
  useEffect(() => {
    setSubcategory("");
  }, [category]);

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
        subcategory: subcategory || null,
        audience_level: audienceLevel,
        video_format: videoFormat,
        duration_seconds: duration,
        language_mode: language,
        avatar_mode: avatarMode,
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

  const availableSubcategories = SUBCATEGORIES[category] ?? [];

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

            {availableSubcategories.length > 0 && (
              <div className="flex flex-col gap-1">
                <label htmlFor="subcategory" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                  Subcategory <span className="text-zinc-400 dark:text-zinc-500 font-normal">(optional — improves visuals)</span>
                </label>
                <select
                  id="subcategory"
                  value={subcategory}
                  onChange={(e) => setSubcategory(e.target.value)}
                  className={selectClass}
                >
                  <option value="">— Select subcategory —</option>
                  {availableSubcategories.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                {subcategory && (
                  <p className="text-xs text-indigo-600 dark:text-indigo-400 mt-0.5">
                    ✓ Scripts and visuals will be tailored for <strong>{subcategory}</strong>
                  </p>
                )}
              </div>
            )}

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

            <div className="flex flex-col gap-1">
              <label htmlFor="avatarMode" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                🎭 Avatar Mode
              </label>
              <select
                id="avatarMode"
                value={avatarMode}
                onChange={(e) => setAvatarMode(e.target.value)}
                className={selectClass}
              >
                {AVATAR_MODES.map((m) => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </select>
              {avatarMode === "did" && (
                <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">
                  ⚠️ D-ID mode requires <code>DID_API_KEY</code> set on the server. Each scene makes one API call.
                </p>
              )}
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

