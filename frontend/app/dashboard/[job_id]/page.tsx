"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { videoJobsApi, VideoJob, SEOMetadata, SceneRead, SceneUpdate } from "@/lib/api";
import { isAuthenticated, removeToken, getToken } from "@/lib/auth";

const PIPELINE_STEPS = [
  { key: "queued", label: "Queued" },
  { key: "generating_script", label: "Script" },
  { key: "awaiting_approval", label: "Review" },
  { key: "generating_audio", label: "Audio" },
  { key: "generating_subtitles", label: "Subtitles" },
  { key: "rendering", label: "Rendering" },
  { key: "packaging", label: "Packaging" },
  { key: "completed", label: "Completed" },
];

// Map actual backend statuses to their pipeline-step position.
const STATUS_TO_STEP: Record<string, number> = {
  queued: 0,
  researching: 1,
  script_generated: 1,
  planning_visuals: 1,
  awaiting_approval: 2,
  generating_audio: 3,
  generating_subtitles: 4,
  rendering: 5,
  packaging: 6,
  completed: 7,
};

function getStepIndex(status: string): number {
  return STATUS_TO_STEP[status] ?? 0;
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
  awaiting_approval: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
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

function ThumbnailPreview({
  jobId,
  onError,
}: {
  jobId: string;
  onError: () => void;
}) {
  const [src, setSrc] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const objectUrlRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    async function loadThumbnail() {
      try {
        const token = getToken();
        const baseUrl =
          process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";
        const response = await fetch(
          `${baseUrl}/video-jobs/${jobId}/thumbnail`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (!response.ok) {
          if (!cancelled) onError();
          return;
        }
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        objectUrlRef.current = url;
        if (!cancelled) setSrc(url);
      } catch {
        if (!cancelled) onError();
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadThumbnail();

    return () => {
      cancelled = true;
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
    };
  }, [jobId, onError]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-32 rounded-xl bg-zinc-100 dark:bg-zinc-800">
        <div className="flex flex-col items-center gap-2 text-zinc-500 dark:text-zinc-400">
          <svg className="w-6 h-6 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          <span className="text-sm">Loading thumbnail…</span>
        </div>
      </div>
    );
  }

  if (!src) return null;

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt="Video thumbnail"
      className="w-full rounded-xl object-cover"
      style={{ maxHeight: "360px" }}
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

/** Map a scene_type to a human-readable badge label + colour class. */
function SceneTypeBadge({ sceneType }: { sceneType: string }) {
  const config: Record<string, { label: string; classes: string }> = {
    hook: {
      label: "🎯 Hook",
      classes:
        "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300",
    },
    beat: {
      label: "🔥 Beat",
      classes:
        "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
    },
    takeaway: {
      label: "💡 Takeaway",
      classes:
        "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
    },
    intro: {
      label: "▶ Intro",
      classes:
        "bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-300",
    },
    outro: {
      label: "⏹ Outro",
      classes:
        "bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300",
    },
    bullet_explainer: {
      label: "📌 Explainer",
      classes:
        "bg-cyan-100 text-cyan-800 dark:bg-cyan-900/40 dark:text-cyan-300",
    },
    icon_compare: {
      label: "⚖️ Compare",
      classes:
        "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300",
    },
    code_card: {
      label: "💻 Code",
      classes:
        "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
    },
  };
  const { label, classes } =
    config[sceneType] ?? {
      label: sceneType.replace(/_/g, " "),
      classes:
        "bg-zinc-100 text-zinc-700 dark:bg-zinc-700 dark:text-zinc-300",
    };
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${classes}`}
    >
      {label}
    </span>
  );
}

function ScriptReviewPanel({
  jobId,
  onApproved,
}: {
  jobId: string;
  onApproved: (updatedJob: VideoJob) => void;
}) {
  const [scenes, setScenes] = useState<SceneRead[]>([]);
  const [loadingScenes, setLoadingScenes] = useState(true);
  const [approving, setApproving] = useState(false);
  const [approveError, setApproveError] = useState("");

  // Per-scene edit state: map from scene.id → draft values
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<SceneUpdate>({});
  const [savingId, setSavingId] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<Record<string, string>>({});
  const [savedId, setSavedId] = useState<string | null>(null);

  useEffect(() => {
    setLoadingScenes(true);
    videoJobsApi
      .getScenes(jobId)
      .then((data) => setScenes(data))
      .catch((err) => console.error("Failed to load scenes:", err))
      .finally(() => setLoadingScenes(false));
  }, [jobId]);

  async function handleApprove() {
    setApproving(true);
    setApproveError("");
    try {
      const updated = await videoJobsApi.approveScript(jobId);
      onApproved(updated);
    } catch {
      setApproveError("Failed to approve script. Please try again.");
      setApproving(false);
    }
  }

  function startEdit(scene: SceneRead) {
    setEditingId(scene.id);
    setSavedId(null);
    setDraft({
      on_screen_text: scene.on_screen_text ?? "",
      narration_text: scene.narration_text ?? "",
      visual_prompt: scene.visual_prompt ?? "",
    });
    setSaveError((prev) => ({ ...prev, [scene.id]: "" }));
  }

  function cancelEdit() {
    setEditingId(null);
    setDraft({});
  }

  async function saveEdit(sceneId: string) {
    setSavingId(sceneId);
    setSaveError((prev) => ({ ...prev, [sceneId]: "" }));
    try {
      const updated = await videoJobsApi.updateScene(jobId, sceneId, draft);
      setScenes((prev) => prev.map((s) => (s.id === sceneId ? updated : s)));
      setEditingId(null);
      setDraft({});
      setSavedId(sceneId);
      // Clear the "Saved" indicator after 2 s
      setTimeout(() => setSavedId((cur) => (cur === sceneId ? null : cur)), 2000);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Save failed. Please try again.";
      setSaveError((prev) => ({ ...prev, [sceneId]: msg }));
    } finally {
      setSavingId(null);
    }
  }

  /** Count beat scenes for display numbering. */
  function beatNumber(scenes: SceneRead[], currentIdx: number): number {
    return scenes
      .slice(0, currentIdx + 1)
      .filter((s) => s.scene_type === "beat").length;
  }

  return (
    <div className="rounded-2xl border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30 shadow-sm p-6 mb-6">
      <div className="flex items-start justify-between mb-5">
        <div>
          <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
            📋 Script Review
          </h2>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
            Review and edit the Shorts scene plan below — hook, beats, and
            takeaway. Click <strong>✏ Edit</strong> on any scene to adjust the
            text or image prompt, then{" "}
            <strong>Approve &amp; Generate Video</strong> when ready.
          </p>
        </div>
        <span className="inline-flex items-center rounded-full bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300 px-2.5 py-0.5 text-xs font-medium whitespace-nowrap">
          Awaiting Approval
        </span>
      </div>

      {loadingScenes ? (
        <div className="flex items-center gap-2 text-zinc-500 dark:text-zinc-400 text-sm py-4">
          <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8v8H4z"
            />
          </svg>
          Loading scenes…
        </div>
      ) : scenes.length === 0 ? (
        <p className="text-sm text-zinc-500 dark:text-zinc-400 py-4">
          No scenes found. You can still proceed with rendering.
        </p>
      ) : (
        <div className="flex flex-col gap-3 mb-6">
          {scenes.map((scene, idx) => {
            const isHook = scene.scene_type === "hook";
            const isTakeaway = scene.scene_type === "takeaway";
            const isBeat = scene.scene_type === "beat";
            const borderClass = isHook
              ? "border-yellow-300 dark:border-yellow-700"
              : isTakeaway
              ? "border-green-300 dark:border-green-700"
              : "border-zinc-200 dark:border-zinc-700";
            const isEditing = editingId === scene.id;
            const isSaving = savingId === scene.id;
            const wasSaved = savedId === scene.id;

            return (
              <div
                key={scene.id}
                className={`rounded-xl border ${borderClass} bg-white dark:bg-zinc-900 p-4`}
              >
                {/* Header row: type badge + scene number + duration + edit button */}
                <div className="flex items-center gap-2 mb-3 flex-wrap">
                  <SceneTypeBadge sceneType={scene.scene_type} />
                  {isBeat && (
                    <span className="text-xs font-semibold text-zinc-500 dark:text-zinc-400">
                      #{beatNumber(scenes, idx)}
                    </span>
                  )}
                  <span className="text-xs text-zinc-400 dark:text-zinc-500">
                    {Math.round(scene.duration_ms / 1000)}s
                  </span>
                  <div className="ml-auto flex items-center gap-2">
                    {wasSaved && !isEditing && (
                      <span className="text-xs text-green-600 dark:text-green-400 font-medium">
                        ✓ Saved
                      </span>
                    )}
                    {!isEditing ? (
                      <button
                        onClick={() => startEdit(scene)}
                        className="text-xs px-2.5 py-1 rounded-md bg-zinc-100 hover:bg-zinc-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-zinc-600 dark:text-zinc-300 font-medium transition-colors"
                      >
                        ✏ Edit
                      </button>
                    ) : (
                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => saveEdit(scene.id)}
                          disabled={isSaving}
                          className="text-xs px-2.5 py-1 rounded-md bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-medium transition-colors"
                        >
                          {isSaving ? "Saving…" : "💾 Save"}
                        </button>
                        <button
                          onClick={cancelEdit}
                          disabled={isSaving}
                          className="text-xs px-2.5 py-1 rounded-md bg-zinc-100 hover:bg-zinc-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-zinc-600 dark:text-zinc-300 font-medium transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {saveError[scene.id] && (
                  <p className="mb-2 text-xs text-red-600 dark:text-red-400">
                    {saveError[scene.id]}
                  </p>
                )}

                {isEditing ? (
                  /* ── Editable form ── */
                  <div className="flex flex-col gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-zinc-500 dark:text-zinc-400 mb-1 uppercase tracking-wide">
                        On-screen text
                      </label>
                      <input
                        type="text"
                        value={draft.on_screen_text ?? ""}
                        onChange={(e) =>
                          setDraft((d) => ({
                            ...d,
                            on_screen_text: e.target.value,
                          }))
                        }
                        className="w-full rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 px-3 py-1.5 text-sm text-zinc-800 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-indigo-400"
                        placeholder="Short phrase shown on screen (3–7 words)"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-zinc-500 dark:text-zinc-400 mb-1 uppercase tracking-wide">
                        Narration / voiceover
                      </label>
                      <textarea
                        rows={2}
                        value={draft.narration_text ?? ""}
                        onChange={(e) =>
                          setDraft((d) => ({
                            ...d,
                            narration_text: e.target.value,
                          }))
                        }
                        className="w-full rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 px-3 py-1.5 text-sm text-zinc-800 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-indigo-400 resize-none"
                        placeholder="Spoken voiceover text"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-zinc-500 dark:text-zinc-400 mb-1 uppercase tracking-wide">
                        Image prompt
                      </label>
                      <textarea
                        rows={2}
                        value={draft.visual_prompt ?? ""}
                        onChange={(e) =>
                          setDraft((d) => ({
                            ...d,
                            visual_prompt: e.target.value,
                          }))
                        }
                        className="w-full rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 px-3 py-1.5 text-sm text-zinc-800 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-indigo-400 resize-none"
                        placeholder="Describe the image to generate for this scene"
                      />
                    </div>
                  </div>
                ) : (
                  /* ── Read-only view ── */
                  <>
                    {/* On-screen text — the phrase shown on the video */}
                    {scene.on_screen_text && (
                      <p
                        className={`font-semibold leading-tight mb-2 ${
                          isHook
                            ? "text-base text-yellow-700 dark:text-yellow-300"
                            : isTakeaway
                            ? "text-base text-green-700 dark:text-green-300"
                            : "text-sm text-zinc-800 dark:text-zinc-100"
                        }`}
                      >
                        {scene.on_screen_text}
                      </p>
                    )}

                    {/* Narration — what gets spoken aloud */}
                    {scene.narration_text &&
                      scene.narration_text !== scene.on_screen_text && (
                        <p className="text-xs text-zinc-500 dark:text-zinc-400 italic border-t border-zinc-100 dark:border-zinc-800 pt-2 mt-2">
                          🎙 {scene.narration_text}
                        </p>
                      )}

                    {/* Visual prompt */}
                    {scene.visual_prompt && (
                      <p className="text-xs text-zinc-400 dark:text-zinc-500 border-t border-zinc-100 dark:border-zinc-800 pt-2 mt-2 truncate">
                        🖼 {scene.visual_prompt}
                      </p>
                    )}
                  </>
                )}
              </div>
            );
          })}
        </div>
      )}

      {approveError && (
        <p className="mb-4 text-sm rounded-lg px-3 py-2 bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400">
          {approveError}
        </p>
      )}

      <button
        onClick={handleApprove}
        disabled={approving || editingId !== null}
        className="rounded-lg bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed px-5 py-2.5 text-sm font-semibold text-white transition-colors"
        title={editingId ? "Save your current edits before approving" : undefined}
      >
        {approving ? "Starting rendering…" : "✅ Approve & Generate Video"}
      </button>
      {editingId && (
        <p className="mt-2 text-xs text-amber-600 dark:text-amber-400">
          💡 Save or cancel your current edit before approving.
        </p>
      )}
    </div>
  );
}
export default function VideoJobDetailPage() {
  const router = useRouter();
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
  const [thumbnailError, setThumbnailError] = useState(false);

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

  // Auto-refresh every 3 seconds while job is still in progress.
  // Stop polling at awaiting_approval — the user must take action.
  useEffect(() => {
    if (!job) return;
    if (
      job.status === "completed" ||
      job.status === "failed" ||
      job.status === "awaiting_approval"
    )
      return;
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

        {/* Script review gate — shown when script is ready and awaiting user approval */}
        {job.status === "awaiting_approval" && (
          <ScriptReviewPanel
            jobId={jobId}
            onApproved={(updated) => setJob(updated)}
          />
        )}

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

        {/* Thumbnail preview section */}
        {isCompleted && !thumbnailError && (
          <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-sm p-6 mb-6">
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50 mb-4">
              🖼️ Thumbnail
            </h2>
            <ThumbnailPreview jobId={jobId} onError={() => setThumbnailError(true)} />
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
