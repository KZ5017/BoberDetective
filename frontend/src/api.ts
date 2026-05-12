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
  document_filename: string | null;
  citation_label: string | null;
  quote_text: string;
  source_text_excerpt: string | null;
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
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
