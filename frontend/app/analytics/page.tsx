"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  analyticsApi,
  ChannelStats,
  VideoStats,
  DailyAnalyticsRow,
} from "@/lib/api";
import { isAuthenticated, removeToken } from "@/lib/auth";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatNumber(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return n.toLocaleString();
}

type SortKey = "views" | "likes" | "comments" | "published_at";

function viewColor(views: number): string {
  if (views >= 10_000) return "text-green-600 dark:text-green-400 font-semibold";
  if (views >= 1_000) return "text-yellow-600 dark:text-yellow-400 font-semibold";
  return "text-zinc-500 dark:text-zinc-400";
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatCard({
  label,
  value,
  color,
  icon,
}: {
  label: string;
  value: string;
  color: string;
  icon: string;
}) {
  return (
    <div
      className={`rounded-2xl p-6 shadow-sm border ${color} bg-white dark:bg-zinc-900`}
    >
      <div className="flex items-center gap-3 mb-2">
        <span className="text-2xl">{icon}</span>
        <span className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
          {label}
        </span>
      </div>
      <p className="text-3xl font-bold text-zinc-900 dark:text-zinc-50">
        {value}
      </p>
    </div>
  );
}

function DailyChart({ rows }: { rows: DailyAnalyticsRow[] }) {
  if (rows.length === 0) return null;
  const maxViews = Math.max(...rows.map((r) => r.views), 1);

  return (
    <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-sm p-6">
      <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50 mb-4">
        📈 Daily Views (last {rows.length} days)
      </h2>
      <div className="flex items-end gap-1 h-36">
        {rows.map((row) => {
          const pct = Math.max((row.views / maxViews) * 100, 2);
          return (
            <div
              key={row.date}
              className="flex-1 flex flex-col items-center gap-1 group"
              title={`${row.date}: ${row.views.toLocaleString()} views`}
            >
              <div
                className="w-full rounded-t bg-indigo-500 dark:bg-indigo-400 group-hover:bg-indigo-600 transition-colors"
                style={{ height: `${pct}%` }}
              />
            </div>
          );
        })}
      </div>
      <div className="flex justify-between text-xs text-zinc-400 mt-1">
        <span>{rows[0]?.date}</span>
        <span>{rows[rows.length - 1]?.date}</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function AnalyticsPage() {
  const router = useRouter();

  const [channel, setChannel] = useState<ChannelStats | null>(null);
  const [videos, setVideos] = useState<VideoStats[]>([]);
  const [daily, setDaily] = useState<DailyAnalyticsRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("views");
  const [sortAsc, setSortAsc] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace("/login");
      return;
    }

    Promise.allSettled([
      analyticsApi.getChannelStats(),
      analyticsApi.getVideoStats(),
      analyticsApi.getDailyStats(30),
    ]).then(([channelRes, videosRes, dailyRes]) => {
      if (channelRes.status === "fulfilled") setChannel(channelRes.value);
      if (videosRes.status === "fulfilled") setVideos(videosRes.value);
      if (dailyRes.status === "fulfilled") setDaily(dailyRes.value);

      // Surface the first error as a user-visible message
      const firstRejected = [channelRes, videosRes, dailyRes].find(
        (r) => r.status === "rejected"
      ) as PromiseRejectedResult | undefined;
      if (firstRejected) {
        const msg =
          firstRejected.reason?.response?.data?.detail ??
          firstRejected.reason?.message ??
          "Could not load analytics data.";
        setError(msg);
      }

      setLoading(false);
    });
  }, [router]);

  function handleLogout() {
    removeToken();
    router.replace("/login");
  }

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortAsc((a) => !a);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  }

  const sortedVideos = [...videos].sort((a, b) => {
    let diff = 0;
    if (sortKey === "published_at") {
      diff = new Date(a.published_at).getTime() - new Date(b.published_at).getTime();
    } else {
      diff = a[sortKey] - b[sortKey];
    }
    return sortAsc ? diff : -diff;
  });

  const SortIcon = ({ k }: { k: SortKey }) => {
    if (sortKey !== k) return <span className="ml-1 text-zinc-300">↕</span>;
    return (
      <span className="ml-1 text-indigo-500">{sortAsc ? "↑" : "↓"}</span>
    );
  };

  return (
    <main className="min-h-screen bg-zinc-50 dark:bg-zinc-950 px-4 py-12">
      <div className="mx-auto max-w-6xl space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-50">
            📊 Analytics
          </h1>
          <div className="flex items-center gap-3">
            <Link
              href="/dashboard"
              className="rounded-lg border border-zinc-200 dark:border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
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

        {/* Error banner */}
        {error && (
          <div className="rounded-lg bg-amber-50 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-700 px-4 py-3 text-sm text-amber-800 dark:text-amber-300">
            ⚠️ {error}
            {error.includes("credentials") && (
              <p className="mt-1 text-xs">
                Re-authorize with the{" "}
                <code className="font-mono">yt-analytics.readonly</code> scope
                to see analytics data.
              </p>
            )}
          </div>
        )}

        {/* Loading spinner */}
        {loading && (
          <div className="flex items-center gap-2 text-zinc-500 dark:text-zinc-400">
            <svg className="w-5 h-5 animate-spin" viewBox="0 0 24 24" fill="none">
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
            <span>Loading analytics…</span>
          </div>
        )}

        {/* Channel overview cards */}
        {channel && (
          <section>
            <h2 className="text-lg font-semibold text-zinc-700 dark:text-zinc-300 mb-3">
              Channel Overview — {channel.channel_name}
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard
                label="Subscribers"
                value={formatNumber(channel.subscriber_count)}
                icon="👥"
                color="border-blue-200 dark:border-blue-800"
              />
              <StatCard
                label="Total Views"
                value={formatNumber(channel.total_views)}
                icon="👁️"
                color="border-green-200 dark:border-green-800"
              />
              <StatCard
                label="Videos Uploaded"
                value={formatNumber(channel.total_videos)}
                icon="🎬"
                color="border-purple-200 dark:border-purple-800"
              />
              <StatCard
                label="Avg Views / Video"
                value={
                  channel.total_videos > 0
                    ? formatNumber(
                        Math.round(channel.total_views / channel.total_videos)
                      )
                    : "—"
                }
                icon="📈"
                color="border-orange-200 dark:border-orange-800"
              />
            </div>
          </section>
        )}

        {/* Daily chart */}
        {daily.length > 0 && <DailyChart rows={daily} />}

        {/* Video performance table */}
        {!loading && (
          <section>
            <h2 className="text-lg font-semibold text-zinc-700 dark:text-zinc-300 mb-3">
              🎥 Video Performance
            </h2>

            {sortedVideos.length === 0 ? (
              <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-sm p-10 text-center text-zinc-500 dark:text-zinc-400">
                No uploaded videos found. Upload a video to YouTube first to see
                per-video stats.
              </div>
            ) : (
              <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-sm overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-zinc-100 dark:border-zinc-800">
                      <th className="text-left px-4 py-3 font-semibold text-zinc-600 dark:text-zinc-300">
                        Title
                      </th>
                      <th
                        className="text-left px-4 py-3 font-semibold text-zinc-600 dark:text-zinc-300 cursor-pointer select-none whitespace-nowrap"
                        onClick={() => toggleSort("published_at")}
                      >
                        Published <SortIcon k="published_at" />
                      </th>
                      <th
                        className="text-right px-4 py-3 font-semibold text-zinc-600 dark:text-zinc-300 cursor-pointer select-none"
                        onClick={() => toggleSort("views")}
                      >
                        Views <SortIcon k="views" />
                      </th>
                      <th
                        className="text-right px-4 py-3 font-semibold text-zinc-600 dark:text-zinc-300 cursor-pointer select-none"
                        onClick={() => toggleSort("likes")}
                      >
                        Likes <SortIcon k="likes" />
                      </th>
                      <th
                        className="text-right px-4 py-3 font-semibold text-zinc-600 dark:text-zinc-300 cursor-pointer select-none"
                        onClick={() => toggleSort("comments")}
                      >
                        Comments <SortIcon k="comments" />
                      </th>
                      <th className="text-center px-4 py-3 font-semibold text-zinc-600 dark:text-zinc-300">
                        Link
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedVideos.map((v, idx) => (
                      <tr
                        key={v.video_id}
                        className={`border-b border-zinc-50 dark:border-zinc-800/60 hover:bg-zinc-50 dark:hover:bg-zinc-800/40 transition-colors ${
                          idx % 2 === 0
                            ? "bg-white dark:bg-zinc-900"
                            : "bg-zinc-50/50 dark:bg-zinc-900/50"
                        }`}
                      >
                        <td className="px-4 py-3 max-w-xs">
                          <span
                            className="line-clamp-2 text-zinc-800 dark:text-zinc-200 font-medium"
                            title={v.title}
                          >
                            {v.title}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-zinc-500 dark:text-zinc-400 whitespace-nowrap">
                          {new Date(v.published_at).toLocaleDateString()}
                        </td>
                        <td className={`px-4 py-3 text-right ${viewColor(v.views)}`}>
                          {formatNumber(v.views)}
                        </td>
                        <td className="px-4 py-3 text-right text-zinc-700 dark:text-zinc-300">
                          {formatNumber(v.likes)}
                        </td>
                        <td className="px-4 py-3 text-right text-zinc-700 dark:text-zinc-300">
                          {formatNumber(v.comments)}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <a
                            href={`https://www.youtube.com/watch?v=${v.video_id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-indigo-600 dark:text-indigo-400 hover:underline text-xs"
                          >
                            ▶ Watch
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}
      </div>
    </main>
  );
}
