export type CaseRead = {
  id: string;
  case_reference: string | null;
  case_name: string;
  description: string | null;
  status: string;
  created_at: string;
};

export type ReviewReportSource = {
  source_reference_id: string;
  document_id: string;
  document_filename: string | null;
  document_sha256_hash: string | null;
  page_number: number | null;
  chunk_index: number | null;
  quote_char_start: number | null;
  quote_char_end: number | null;
  source_text_excerpt_char_start: number | null;
  source_text_excerpt_char_end: number | null;
  citation_label: string | null;
  quote_text: string;
  source_text_excerpt: string | null;
  support_type: string;
  relevance_rank: number | null;
};

export type ReviewReportItem = {
  object_type: string;
  object_id: string;
  title: string;
  body_text: string | null;
  subtype: string;
  review_status: string;
  source_validation_status: string;
  sources: ReviewReportSource[];
  reviews: Array<{
    id: string;
    action_type: string;
    new_review_status: string | null;
    review_comment: string | null;
    performed_at: string;
  }>;
};

export type ReviewReport = {
  counts: {
    total: number;
    needs_review: number;
    verified: number;
    rejected: number;
    corrected: number;
    new: number;
  };
  items: ReviewReportItem[];
};

export type ExportDetail = {
  export: {
    id: string;
    export_type: "json" | "html";
    sha256_hash: string | null;
    created_at: string;
  };
  items: Array<{ id: string; object_type: string; object_id: string }>;
};

export type AnalysisResponse = {
  analysis_run_id: string;
  module_key: string;
  validation_status: string;
  selected_chunk_ids: string[];
  unsupported_items: string[];
  claims: unknown[];
  events: unknown[];
  entities: unknown[];
  summary_items: unknown[];
  contradiction_candidates: unknown[];
  missing_item_candidates: unknown[];
};

const reviewPathByType: Record<string, (caseId: string, objectId: string) => string> = {
  claim: (caseId, objectId) => `/cases/${caseId}/claims/${objectId}/reviews`,
  event: (caseId, objectId) => `/cases/${caseId}/events/${objectId}/reviews`,
  entity: (caseId, objectId) => `/cases/${caseId}/entities/${objectId}/reviews`,
  summary_item: (caseId, objectId) => `/cases/${caseId}/summary-items/${objectId}/reviews`,
  contradiction_candidate: (caseId, objectId) => `/cases/${caseId}/contradiction-candidates/${objectId}/reviews`,
  missing_item_candidate: (caseId, objectId) => `/cases/${caseId}/missing-item-candidates/${objectId}/reviews`
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export function reviewObject(
  caseId: string,
  objectType: string,
  objectId: string,
  actionType: "verify" | "reject" | "mark_needs_review" | "comment",
  reviewComment?: string
): Promise<unknown> {
  const pathFactory = reviewPathByType[objectType];
  if (!pathFactory) {
    throw new Error(`Unsupported review object type: ${objectType}`);
  }
  return request(pathFactory(caseId, objectId), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action_type: actionType, review_comment: reviewComment || null })
  });
}

export function listCases(): Promise<{ data: CaseRead[] }> {
  return request("/cases");
}

export function createCase(payload: { case_name: string; case_reference?: string; description?: string }): Promise<CaseRead> {
  return request("/cases", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function importDocument(caseId: string, file: File, documentType: string): Promise<unknown> {
  const body = new FormData();
  body.append("file", file);
  body.append("document_type", documentType);
  body.append("language_code", "hu");
  return request(`/cases/${caseId}/documents`, { method: "POST", body });
}

export function runAnalysis(caseId: string, moduleKey: string, query: string, limit: number): Promise<AnalysisResponse> {
  return request(`/cases/${caseId}/analysis/modules/${moduleKey}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, limit })
  });
}

export function getReviewReport(caseId: string, objectType?: string): Promise<ReviewReport> {
  const params = objectType ? `?object_type=${encodeURIComponent(objectType)}` : "";
  return request(`/cases/${caseId}/review-report${params}`);
}

export function createExport(caseId: string, exportType: "json" | "html", objectType?: string): Promise<ExportDetail> {
  return request(`/cases/${caseId}/exports`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      export_type: exportType,
      export_scope: "review_report",
      review_filter: "needs_review",
      require_source_valid: true,
      report_filters: objectType ? { object_types: [objectType] } : null
    })
  });
}
