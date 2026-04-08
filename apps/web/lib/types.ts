export type Repository = {
  id: string;
  name: string;
  owner?: string;
  repo_url: string;
  default_branch: string;
  local_path?: string | null;
  status: string;
  last_error?: string | null;
  primary_language?: string | null;
  framework?: string | null;
  created_at?: string;
};

export type FileRecord = {
  id: string;
  path: string;
  language?: string | null;
  file_kind: string;
  line_count?: number | null;
  parse_status?: string;
};

export type FileListResponse = {
  repository_id?: string;
  total: number;
  items: FileRecord[];
};

export type FileDetailResponse = {
  id: string;
  repository_id: string;
  path: string;
  language?: string | null;
  file_kind: string;
  line_count?: number | null;
  parse_status?: string | null;
  is_generated?: boolean;
  is_vendor?: boolean;
  content?: string | null;
};

export type SearchResultItem = {
  chunk_id: string;
  file_id?: string | null;
  file_path?: string | null;
  score: number;
  chunk_type: string;
  start_line?: number | null;
  end_line?: number | null;
  snippet: string;
};

export type SemanticSearchResponse = {
  repository_id: string;
  query: string;
  total: number;
  items: SearchResultItem[];
};

export type RenameAnalysis = {
  symbol_name: string;
  new_name: string;
  declaration_line: number | string;
  same_file_references: Array<{ line_no: number; line_text: string }>;
  declaration_only_rename_breaks: boolean;
  full_rename_safe: boolean;
  language: string;
  error_if_partial: string;
};

export type AskRepoResponse = {
  question: string;
  answer: string;
  citations: Array<{
    file_id?: string | null;
    file_path?: string | null;
    start_line?: number | null;
    end_line?: number | null;
    chunk_id: string;
  }>;
  mode: string;
  llm_model?: string | null;
  confidence?: string | null;
  query_type?: string | null;
  resolved_file?: string | null;
  resolved_line_number?: number | null;
  matched_line?: string | null;
  rename_analysis?: RenameAnalysis | null;
};

export type HotspotItem = {
  file_id: string;
  path: string;
  language?: string | null;
  file_kind: string;
  risk_score: number;
  complexity_score: number;
  dependency_score: number;
  change_proneness_score: number;
  test_proximity_score: number;
  symbol_count: number;
  inbound_dependencies: number;
  outbound_dependencies: number;
  risk_level: string;
};

export type HotspotListResponse = {
  repository_id: string;
  total: number;
  items: HotspotItem[];
};

export type OnboardingDocumentResponse = {
  id: string;
  repository_id: string;
  version: number;
  title: string;
  content_markdown: string;
  generation_mode: string;
  llm_model?: string | null;
  created_at: string;
};

export type PRImpactResponse = {
  repository_id: string;
  changed_files: string[];
  impacted_count: number;
  risk_level: string;
  total_impact_score: number;
  summary: string;
  impacted_files: Array<{
    file_id: string;
    path: string;
    language?: string | null;
    depth: number;
    inbound_dependencies: number;
    outbound_dependencies: number;
    risk_score: number;
    impact_score: number;
  }>;
  reviewer_suggestions: Array<{
    reviewer_hint: string;
    reason: string;
  }>;
};

export type RefreshJob = {
  id: string;
  repository_id: string;
  trigger_source: string;
  event_type: string;
  branch?: string | null;
  status: string;
  changed_files: string[];
  summary?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at?: string | null;
};

export type RefreshJobListResponse = {
  repository_id: string;
  total: number;
  items: RefreshJob[];
};
