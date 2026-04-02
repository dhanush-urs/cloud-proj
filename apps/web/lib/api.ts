import { API_BASE_URL } from "@/lib/config";
import type {
  AskRepoResponse,
  FileDetailResponse,
  FileListResponse,
  HotspotListResponse,
  OnboardingDocumentResponse,
  PRImpactResponse,
  RefreshJob,
  RefreshJobListResponse,
  Repository,
  SemanticSearchResponse,
} from "@/lib/types";

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const data = await response.json();
      if (data?.detail) {
        message = data.detail;
      }
    } catch {
      // ignore
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

function normalizeRepositoriesResponse(data: any): Repository[] {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.items)) return data.items;
  if (Array.isArray(data?.repositories)) return data.repositories;
  if (Array.isArray(data?.data)) return data.data;

  console.warn("[API] Unexpected repository list shape:", data);
  return [];
}

export async function getRepositories(): Promise<Repository[]> {
  const res = await fetch(`${API_BASE_URL}/repos`, { cache: "no-store" });
  const data = await handleResponse<any>(res);
  return normalizeRepositoriesResponse(data);
}

export async function getJobs(repoId: string, limit = 1): Promise<{ items: any[]; total: number }> {
  const res = await fetch(`${API_BASE_URL}/jobs?repo_id=${repoId}&limit=${limit}`, {
    cache: "no-store",
  });
  return handleResponse(res);
}

export async function getRepository(repoId: string): Promise<Repository> {
  const res = await fetch(`${API_BASE_URL}/repos/${repoId}`, {
    cache: "no-store",
  });
  return handleResponse<Repository>(res);
}

export async function createRepository(payload: {
  repo_url: string;
  branch: string;
}): Promise<Repository> {
  const res = await fetch(`${API_BASE_URL}/repos`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    body: JSON.stringify(payload),
  });

  return handleResponse<Repository>(res);
}

export async function triggerParse(
  repoId: string
): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE_URL}/repos/${repoId}/parse`, {
    method: "POST",
    cache: "no-store",
  });

  return handleResponse<{ message: string }>(res);
}

export async function triggerEmbed(repoId: string): Promise<{
  message: string;
  repository_id: string;
  job_id: string;
  task_id: string;
}> {
  const res = await fetch(`${API_BASE_URL}/repos/${repoId}/embed`, {
    method: "POST",
    cache: "no-store",
  });

  return handleResponse(res);
}

export async function getRepositoryFiles(
  repoId: string,
  limit = 100
): Promise<FileListResponse> {
  const res = await fetch(
    `${API_BASE_URL}/repos/${repoId}/files?limit=${limit}`,
    {
      cache: "no-store",
    }
  );

  return handleResponse<FileListResponse>(res);
}

export async function getRepositoryFileDetail(
  repoId: string,
  fileId: string
): Promise<FileDetailResponse> {
  const res = await fetch(`${API_BASE_URL}/repos/${repoId}/files/${fileId}`, {
    cache: "no-store",
  });

  return handleResponse<FileDetailResponse>(res);
}

export async function semanticSearch(
  repoId: string,
  payload: { query: string; top_k?: number }
): Promise<SemanticSearchResponse> {
  const res = await fetch(`${API_BASE_URL}/repos/${repoId}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    body: JSON.stringify(payload),
  });

  return handleResponse<SemanticSearchResponse>(res);
}

export async function askRepo(
  repoId: string,
  payload: { question: string; top_k?: number }
): Promise<AskRepoResponse> {
  const res = await fetch(`${API_BASE_URL}/repos/${repoId}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    body: JSON.stringify(payload),
  });

  return handleResponse<AskRepoResponse>(res);
}

export async function getHotspots(
  repoId: string
): Promise<HotspotListResponse> {
  const res = await fetch(`${API_BASE_URL}/repos/${repoId}/hotspots?limit=20`, {
    cache: "no-store",
  });

  return handleResponse<HotspotListResponse>(res);
}

export async function getOnboarding(
  repoId: string
): Promise<OnboardingDocumentResponse> {
  const res = await fetch(`${API_BASE_URL}/repos/${repoId}/onboarding`, {
    cache: "no-store",
  });

  return handleResponse<OnboardingDocumentResponse>(res);
}

export async function generateOnboarding(repoId: string): Promise<{
  message: string;
  repository_id: string;
  document_id: string;
  generation_mode: string;
  llm_model?: string | null;
}> {
  const res = await fetch(
    `${API_BASE_URL}/repos/${repoId}/onboarding/generate`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      body: JSON.stringify({
        top_files: 10,
        include_hotspots: true,
        include_search_context: true,
      }),
    }
  );

  return handleResponse(res);
}

export async function analyzeImpact(
  repoId: string,
  payload: { changed_files: string[]; max_depth?: number }
): Promise<PRImpactResponse> {
  const res = await fetch(`${API_BASE_URL}/repos/${repoId}/impact`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    body: JSON.stringify(payload),
  });

  return handleResponse<PRImpactResponse>(res);
}

export async function getRepositoryRefreshJobs(
  repoId: string
): Promise<RefreshJobListResponse> {
  const res = await fetch(`${API_BASE_URL}/repos/${repoId}/refresh-jobs`, {
    cache: "no-store",
  });

  return handleResponse<RefreshJobListResponse>(res);
}

export async function getRefreshJob(jobId: string): Promise<RefreshJob> {
  const res = await fetch(`${API_BASE_URL}/api/v1/refresh-jobs/${jobId}`, {
    cache: "no-store",
  });

  return handleResponse<RefreshJob>(res);
}
