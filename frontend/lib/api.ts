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
  status: string;
  created_at: string;
  updated_at: string;
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

export const videoJobsApi = {
  list: (): Promise<VideoJob[]> =>
    apiClient.get<VideoJob[]>("/video-jobs").then((r) => r.data),

  create: (payload: VideoJobCreatePayload): Promise<VideoJob> =>
    apiClient.post<VideoJob>("/video-jobs", payload).then((r) => r.data),

  get: (id: string): Promise<VideoJob> =>
    apiClient.get<VideoJob>(`/video-jobs/${id}`).then((r) => r.data),
};
