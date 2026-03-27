import axios from "axios";
import { getToken, removeToken } from "@/lib/auth";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && typeof window !== "undefined") {
      removeToken();
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

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

export interface VideoJobDownloadResponse {
  job_id: string;
  storage_key: string;
  download_url: string | null;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: { id: string; email: string };
}

export interface Project {
  id: string;
  name: string;
  description: string;
}

export interface Schedule {
  id: string;
  project_id: string;
  name: string;
  cron_expression: string;
  timezone_str: string;
  topics: string[];
  category: string;
  audience_level: string;
  language_mode: string;
  video_format: string;
  duration_seconds: number;
  auto_upload: boolean;
  is_active: boolean;
  current_topic_index: number;
  last_run_at: string | null;
  next_run_at: string | null;
  total_runs: number;
  created_at: string;
}

export interface ScheduleCreatePayload {
  project_id: string;
  name: string;
  cron_expression: string;
  timezone_str?: string;
  topics: string[];
  category?: string;
  audience_level?: string;
  language_mode?: string;
  video_format?: string;
  duration_seconds?: number;
  auto_upload?: boolean;
}

export interface ScheduleUpdatePayload {
  name?: string;
  cron_expression?: string;
  topics?: string[];
  is_active?: boolean;
  auto_upload?: boolean;
}

export const authApi = {
  login: (email: string, password: string): Promise<AuthResponse> =>
    apiClient
      .post<AuthResponse>("/auth/login", { email, password })
      .then((r) => r.data),

  register: (email: string, password: string): Promise<AuthResponse> =>
    apiClient
      .post<AuthResponse>("/auth/register", { email, password })
      .then((r) => r.data),
};

export const projectsApi = {
  list: (): Promise<Project[]> =>
    apiClient.get<Project[]>("/projects").then((r) => r.data),

  create: (name: string, description: string): Promise<Project> =>
    apiClient
      .post<Project>("/projects", { name, description })
      .then((r) => r.data),
};

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

  getDownloadUrl: (id: string): Promise<VideoJobDownloadResponse> =>
    apiClient
      .get<VideoJobDownloadResponse>(`/video-jobs/${id}/download`)
      .then((r) => r.data),
};

export const schedulesApi = {
  list: (): Promise<Schedule[]> =>
    apiClient.get<Schedule[]>("/schedules").then((r) => r.data),

  create: (payload: ScheduleCreatePayload): Promise<Schedule> =>
    apiClient.post<Schedule>("/schedules", payload).then((r) => r.data),

  get: (id: string): Promise<Schedule> =>
    apiClient.get<Schedule>(`/schedules/${id}`).then((r) => r.data),

  update: (id: string, payload: ScheduleUpdatePayload): Promise<Schedule> =>
    apiClient.put<Schedule>(`/schedules/${id}`, payload).then((r) => r.data),

  delete: (id: string): Promise<void> =>
    apiClient.delete(`/schedules/${id}`).then(() => undefined),
};
