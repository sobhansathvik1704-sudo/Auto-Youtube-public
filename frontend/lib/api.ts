import axios from "axios";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
});

export interface VideoJob {
  id: string;
  project_id: string;
  topic: string;
  category: string;
  audience_level: string;
  language_mode: string;
  video_format: string;
  duration_seconds: number;
  status: string;
  render_storage_key: string | null;
  metadata_json: string | null;
  youtube_video_id: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface VideoJobCreatePayload {
  project_id: string;
  topic: string;
  category?: string;
  audience_level?: string;
  language_mode?: string;
  video_format?: string;
  duration_seconds?: number;
}

export interface YouTubeUploadResponse {
  job_id: string;
  task_id: string;
  message: string;
}

export const videoJobsApi = {
  list: (): Promise<VideoJob[]> =>
    apiClient.get<VideoJob[]>("/video-jobs").then((r) => r.data),

  create: (payload: VideoJobCreatePayload): Promise<VideoJob> =>
    apiClient.post<VideoJob>("/video-jobs", payload).then((r) => r.data),

  get: (id: string): Promise<VideoJob> =>
    apiClient.get<VideoJob>(`/video-jobs/${id}`).then((r) => r.data),

  uploadToYouTube: (id: string): Promise<YouTubeUploadResponse> =>
    apiClient
      .post<YouTubeUploadResponse>(`/video-jobs/${id}/upload`)
      .then((r) => r.data),
};
