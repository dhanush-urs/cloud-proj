import { API_BASE_URL } from "@/lib/config";
import {
  normalizeRepository,
  normalizeRepositories,
  normalizeRefreshJob,
  normalizeAskRepoResponse,
  normalizeSearchResponse,
  normalizeFileListResponse,
  normalizeHotspotResponse,
  normalizePRImpactResponse,
} from "./normalizers";
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

/**
 * Enhanced response handler with robustness and error logging.
 */
async function handleResponse<T>(
  response: Response,
  fallback: T
): Promise<T> {
  if (!response.ok) {
    let errorMessage = `API Error ${response.status}`;
    try {
      const errorData = await response.json();
      if (errorData && errorData.detail) {
        errorMessage = typeof errorData.detail === 'string' 
          ? errorData.detail 
          : JSON.stringify(errorData.detail);
      }
    } catch (e) {
      // Not JSON or no detail field
    }
    console.error(`[API] ${response.url} failed: ${errorMessage}`);
    throw new Error(errorMessage);
  }

  try {
    return await response.json();
  } catch (err) {
    console.error(`[API] Failed to parse JSON from ${response.url}:`, err);
    return fallback;
  }
}

/**
 * Centralized safe fetch wrapper to catch all network-level errors.
 */
async function safeFetch<T>(
  endpoint: string,
  options: RequestInit = {},
  fallback: T
): Promise<T> {
  try {
    const url = `${API_BASE_URL}${endpoint}`;
    const res = await fetch(url, {
      ...options,
      // Add a reasonable timeout for SSR stability
      signal: AbortSignal.timeout(10000),
    });
    return await handleResponse(res, fallback);
  } catch (err) {
    console.error(`[API] Network error on ${endpoint}:`, (err as any).message);
    return fallback;
  }
}

export async function getRepositories(): Promise<Repository[]> {
  const data = await safeFetch("/repos", { cache: "no-store" }, []);
  return normalizeRepositories(data);
}

export async function getJobs(
  repoId: string,
  limit = 1
): Promise<{ items: any[]; total: number }> {
  return safeFetch(
    `/jobs?repo_id=${repoId}&limit=${limit}`,
    { cache: "no-store" },
    { items: [], total: 0 }
  );
}

export async function getRepository(repoId: string): Promise<Repository | null> {
  const data = await safeFetch(`/repos/${repoId}`, { cache: "no-store" }, null);
  return data ? normalizeRepository(data) : null;
}

export async function createRepository(payload: {
  repo_url: string;
  branch: string;
}): Promise<Repository | null> {
  const data = await safeFetch(
    "/repos",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      body: JSON.stringify(payload),
    },
    null
  );
  return data ? normalizeRepository(data) : null;
}

export async function triggerParse(
  repoId: string
): Promise<{ message: string }> {
  return safeFetch(
    `/repos/${repoId}/parse`,
    { method: "POST", cache: "no-store" },
    { message: "Failed to trigger parse" }
  );
}

export async function triggerEmbed(repoId: string): Promise<{
  message: string;
  repository_id: string;
  job_id: string;
  task_id: string;
}> {
  return safeFetch(
    `/repos/${repoId}/embed`,
    { method: "POST", cache: "no-store" },
    {
      message: "Failed to trigger embedding",
      repository_id: repoId,
      job_id: "",
      task_id: "",
    }
  );
}

export async function getRepositoryFiles(
  repoId: string,
  limit = 100
): Promise<FileListResponse> {
  const data = await safeFetch(
    `/repos/${repoId}/files?limit=${limit}`,
    { cache: "no-store" },
    { files: [], total: 0, limit }
  );
  return normalizeFileListResponse(data);
}

export async function getRepositoryFileDetail(
  repoId: string,
  fileId: string
): Promise<FileDetailResponse | null> {
  return safeFetch(
    `/repos/${repoId}/files/${fileId}`,
    { cache: "no-store" },
    null
  );
}

export async function semanticSearch(
  repoId: string,
  payload: { query: string; top_k?: number }
): Promise<SemanticSearchResponse> {
  const data = await safeFetch(
    `/repos/${repoId}/search`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      body: JSON.stringify(payload),
    },
    { query: payload.query, results: [] }
  );
  return normalizeSearchResponse(data);
}

export async function askRepo(
  repoId: string,
  payload: { question: string; top_k?: number }
): Promise<AskRepoResponse> {
  const data = await safeFetch(
    `/repos/${repoId}/ask`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      body: JSON.stringify(payload),
    },
    {
      question: payload.question,
      answer: "The intelligence system is temporarily unavailable.",
      context_used: [],
      mode: "general",
    }
  );
  return normalizeAskRepoResponse(data);
}

export async function getHotspots(
  repoId: string
): Promise<HotspotListResponse> {
  const data = await safeFetch(
    `/repos/${repoId}/hotspots?limit=20`,
    { cache: "no-store" },
    { hotspots: [], total: 0 }
  );
  return normalizeHotspotResponse(data);
}

export async function getOnboarding(
  repoId: string
): Promise<OnboardingDocumentResponse | null> {
  return safeFetch(`/repos/${repoId}/onboarding`, { cache: "no-store" }, null);
}

export async function generateOnboarding(repoId: string): Promise<{
  message: string;
  repository_id: string;
  document_id: string;
  generation_mode: string;
  llm_model?: string | null;
}> {
  return safeFetch(
    `/repos/${repoId}/onboarding/generate`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      body: JSON.stringify({
        top_files: 10,
        include_hotspots: true,
        include_search_context: true,
      }),
    },
    {
      message: "Failed to generate onboarding",
      repository_id: repoId,
      document_id: "",
      generation_mode: "standard",
    }
  );
}

export async function analyzeImpact(
  repoId: string,
  payload: { changed_files: string[]; max_depth?: number }
): Promise<PRImpactResponse> {
  const data = await safeFetch(
    `/repos/${repoId}/impact`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      body: JSON.stringify(payload),
    },
    {
      score: 0,
      analysis: "Impact analysis unavailable.",
      affected_files: [],
      risks: [],
    }
  );
  return normalizePRImpactResponse(data);
}

export async function getRepositoryRefreshJobs(
  repoId: string
): Promise<RefreshJobListResponse> {
  const data = await safeFetch(
    `/jobs?repo_id=${repoId}&limit=50`,
    { cache: "no-store" },
    { items: [] }
  );
  return {
    repository_id: repoId,
    total: Array.isArray(data?.items) ? data.items.length : 0,
    items: Array.isArray(data?.items) ? data.items.map(normalizeRefreshJob) : [],
  };
}

export async function getRefreshJob(jobId: string): Promise<RefreshJob | null> {
  const data = await safeFetch(
    `/jobs/${jobId}`,
    { cache: "no-store" },
    null
  );
  return data ? normalizeRefreshJob(data) : null;
}

