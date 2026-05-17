export type CaseRead = {
  id: string;
  case_reference: string | null;
  case_name: string;
  description: string | null;
  status: string;
  created_at: string;
};

export type DocumentRead = {
  id: string;
  original_filename: string;
  document_group_code: string;
  document_group_label: string | null;
  document_type_code: string;
  document_type_label: string | null;
  language_code: string | null;
  file_size_bytes: number;
  sha256_hash: string;
  processing_status: string;
  page_count: number | null;
  imported_at: string;
  ocr_recommendation: {
    action: "hidden" | "recommended" | "optional";
    reason_code: string;
    message: string;
  } | null;
};

export type DocumentTaxonomyTypeRead = {
  code: string;
  label: string;
  description: string;
};

export type DocumentTaxonomyGroupRead = {
  code: string;
  label: string;
  description: string;
  types: DocumentTaxonomyTypeRead[];
};

export type DocumentPageRead = {
  id: string;
  page_number: number;
  extracted_text: string;
  text_source: string;
  ocr_used: boolean;
  ocr_confidence: number | null;
  text_char_count: number;
};

export type DocumentChunkRead = {
  id: string;
  page_start: number;
  page_end: number;
  chunk_index: number;
  chunk_text: string;
  char_start: number | null;
  char_end: number | null;
  token_count: number | null;
};

export type AnalysisRunRead = {
  id: string;
  run_type: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  provider_type: string | null;
  model_name: string | null;
  validation_status: string | null;
  error_message: string | null;
  input_parameters: Record<string, unknown> | null;
  output_schema_name: string | null;
};

export type DocumentProcessResponse = {
  document: DocumentRead;
  analysis_run: AnalysisRunRead;
};

export type AnalysisRunDetail = {
  run: AnalysisRunRead;
  inputs: Array<{
    id: string;
    input_type: string;
    document_id: string | null;
    page_id: string | null;
    chunk_id: string | null;
    related_object_type: string | null;
    related_object_id: string | null;
    sequence_no: number;
    payload_json: Record<string, unknown> | null;
    source_summary: {
      document_filename: string | null;
      page_start: number | null;
      page_end: number | null;
      chunk_index: number | null;
      char_start: number | null;
      char_end: number | null;
      text_preview: string | null;
    } | null;
  }>;
  outputs: Array<{
    id: string;
    output_type: string;
    output_object_id: string;
    output_position: number | null;
    output_summary: {
      title: string | null;
      body_text: string | null;
      review_status: string | null;
      source_validation_status: string | null;
      source_count: number | null;
    } | null;
  }>;
};

export type ReviewReportSource = {
  source_link_id: string | null;
  source_link_type: string | null;
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

export type ReviewReportFilterValues = {
  objectType?: string;
  reviewStatus?: string;
  sourceValidationStatus?: string;
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

export type ExportRead = {
  id: string;
  export_type: "json" | "html";
  export_scope: string;
  sha256_hash: string | null;
  review_filter: string | null;
  export_parameters: Record<string, unknown> | null;
  created_at: string;
};

export type EntityRead = {
  id: string;
  case_id: string;
  entity_type: string;
  canonical_name: string;
  normalized_value: string | null;
  description: string | null;
  confidence: string | number | null;
  created_by_analysis_run_id: string | null;
  created_by_user_id: string | null;
  review_status: string;
  created_at: string;
  updated_at: string;
};

export type EventRead = {
  id: string;
  case_id: string;
  event_type: string;
  event_title: string;
  event_description: string | null;
  event_time_raw: string | null;
  event_time_start: string | null;
  event_time_end: string | null;
  time_precision: string | null;
  location_text: string | null;
  confidence: string | number | null;
  created_by_analysis_run_id: string;
  source_validation_status: string;
  review_status: string;
  created_at: string;
  updated_at: string;
};

export type MissingItemCandidateRead = {
  id: string;
  case_id: string;
  missing_item_type: string;
  referenced_item_text: string;
  description: string;
  expected_document_type: string | null;
  confidence: string | number | null;
  created_by_analysis_run_id: string;
  source_validation_status: string;
  review_status: string;
  created_at: string;
  updated_at: string;
};

export type DetachedSourceItemRead = {
  id: string;
  case_id: string;
  source_reference_id: string;
  detached_from_object_type: string;
  detached_from_object_id: string;
  detached_from_source_link_id: string;
  detached_from_source_link_type: string;
  object_title_snapshot: string;
  object_body_snapshot: string | null;
  object_subtype_snapshot: string | null;
  object_review_status_snapshot: string | null;
  source_validation_status_snapshot: string | null;
  source_snapshot_json: {
    document_id?: string | null;
    page_id?: string | null;
    chunk_id?: string | null;
    page_number?: number | null;
    quote_text?: string | null;
    quote_char_start?: number | null;
    quote_char_end?: number | null;
    citation_label?: string | null;
    source_kind?: string | null;
  } | null;
  handling_status: string;
  reattached_to_object_type: string | null;
  reattached_to_object_id: string | null;
  reattached_to_object_title_snapshot: string | null;
  detach_comment: string | null;
  detached_by_user_id: string;
  detached_at: string;
  updated_at: string;
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

export type ManualObjectType = "claim" | "entity" | "event" | "missing_item_candidate";

export type ManualObjectPayload = {
  source_reference: {
    document_id: string;
    page_id?: string | null;
    chunk_id?: string | null;
    quote_text: string;
    quote_char_start?: number | null;
    quote_char_end?: number | null;
    citation_label?: string | null;
    source_kind: "chunk_quote" | "page_quote";
  };
  object_type: ManualObjectType;
  claim_type?: string;
  claim_text?: string | null;
  entity_type?: string | null;
  canonical_name?: string | null;
  normalized_value?: string | null;
  description?: string | null;
  event_type?: string | null;
  event_title?: string | null;
  event_description?: string | null;
  event_time_raw?: string | null;
  time_precision?: string | null;
  location_text?: string | null;
  missing_item_type?: string | null;
  referenced_item_text?: string | null;
  expected_document_type?: string | null;
};

export type ManualObjectFromSourcePayload = Omit<ManualObjectPayload, "source_reference">;

export type ManualObjectResponse = {
  analysis_run_id: string;
  source_reference: {
    id: string;
    citation_label: string | null;
  };
  object_type: string;
  object_id: string;
};

export type ManualContradictionCandidatePayload = {
  claim_id_a: string;
  claim_id_b: string;
  contradiction_type: "time_conflict" | "location_conflict" | "identity_conflict" | "document_mismatch" | "amount_conflict" | "other";
  severity_hint?: "low" | "medium" | "high" | null;
  description: string;
};

export type AnalysisSourceMode = "case" | "document";
export type ClaimReviewScope = "reviewable" | "verified" | "needs_review" | "all_source_valid";
export type RetrievalStrategy = "keyword" | "semantic" | "hybrid";

export type AnalysisRunPayload = {
  query?: string | null;
  source_mode?: AnalysisSourceMode;
  document_id?: string | null;
  document_ids?: string[];
  document_group_code?: string | null;
  document_type_code?: string | null;
  page_start?: number | null;
  page_end?: number | null;
  max_chunks?: number;
  batch_size?: number;
  claim_review_scope?: ClaimReviewScope;
  retrieval_strategy?: RetrievalStrategy;
  contradiction_candidate_limit?: number;
};

export type ChunkIndexResponse = {
  analysis_run_id: string;
  indexed_count: number;
  skipped_count: number;
  collection_name: string;
  embedding_model: string;
};

export type ChunkIndexJobResponse = {
  analysis_run_id: string;
  status: string;
  collection_name: string;
  embedding_model: string;
};

export type ChunkIndexStatusResponse = {
  case_id: string;
  document_id: string | null;
  document_ids: string[];
  document_group_code: string | null;
  document_type_code: string | null;
  collection_name: string;
  embedding_model: string;
  current_chunk_count: number;
  indexed_chunk_count: number;
  missing_chunk_count: number;
  is_ready: boolean;
  needs_indexing: boolean;
  latest_run_id: string | null;
  latest_run_status: string | null;
  latest_run_validation_status: string | null;
  latest_run_started_at: string | null;
  latest_run_finished_at: string | null;
  latest_run_input_count: number;
  latest_run_output_count: number;
  latest_run_progress_percent: number | null;
};

export type LlmSmokeResponse = {
  provider: string;
  base_url: string;
  reachable: boolean;
  model_ids: string[];
  configured_chat_model: string;
  configured_chat_model_available: boolean | null;
  configured_chat_model_loaded: boolean | null;
  configured_embedding_model: string;
  configured_embedding_model_available: boolean | null;
  configured_embedding_model_loaded: boolean | null;
  loaded_model_ids: string[];
  error_message: string | null;
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

export function mergeEntity(
  caseId: string,
  sourceEntityId: string,
  targetEntityId: string,
  reviewComment?: string
): Promise<unknown> {
  return request(`/cases/${caseId}/entities/${sourceEntityId}/merge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_entity_id: targetEntityId, review_comment: reviewComment || null })
  });
}

export function mergeEvent(
  caseId: string,
  sourceEventId: string,
  targetEventId: string,
  reviewComment?: string
): Promise<unknown> {
  return request(`/cases/${caseId}/events/${sourceEventId}/merge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_event_id: targetEventId, review_comment: reviewComment || null })
  });
}

export function mergeMissingItemCandidate(
  caseId: string,
  sourceCandidateId: string,
  targetCandidateId: string,
  reviewComment?: string
): Promise<unknown> {
  return request(`/cases/${caseId}/missing-item-candidates/${sourceCandidateId}/merge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_missing_item_candidate_id: targetCandidateId, review_comment: reviewComment || null })
  });
}

export function detachObjectSource(
  caseId: string,
  objectType: string,
  objectId: string,
  sourceLinkId: string,
  reviewComment?: string
): Promise<unknown> {
  const detachPathByType: Record<string, string> = {
    entity: `/cases/${caseId}/entities/${objectId}/mentions/${sourceLinkId}/detach`,
    event: `/cases/${caseId}/events/${objectId}/sources/${sourceLinkId}/detach`,
    missing_item_candidate: `/cases/${caseId}/missing-item-candidates/${objectId}/sources/${sourceLinkId}/detach`
  };
  const path = detachPathByType[objectType];
  if (!path) {
    throw new Error(`Unsupported source detach object type: ${objectType}`);
  }
  return request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ review_comment: reviewComment || null })
  });
}

export function moveObjectSource(
  caseId: string,
  objectType: string,
  objectId: string,
  sourceLinkId: string,
  targetObjectId: string,
  reviewComment?: string
): Promise<unknown> {
  const movePathByType: Record<string, { path: string; targetKey: string }> = {
    entity: {
      path: `/cases/${caseId}/entities/${objectId}/mentions/${sourceLinkId}/move`,
      targetKey: "target_entity_id"
    },
    event: {
      path: `/cases/${caseId}/events/${objectId}/sources/${sourceLinkId}/move`,
      targetKey: "target_event_id"
    },
    missing_item_candidate: {
      path: `/cases/${caseId}/missing-item-candidates/${objectId}/sources/${sourceLinkId}/move`,
      targetKey: "target_missing_item_candidate_id"
    }
  };
  const config = movePathByType[objectType];
  if (!config) {
    throw new Error(`Unsupported source move object type: ${objectType}`);
  }
  return request(config.path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ [config.targetKey]: targetObjectId, review_comment: reviewComment || null })
  });
}

export function attachDetachedSourceItem(
  caseId: string,
  itemId: string,
  targetObjectId: string,
  reviewComment?: string
): Promise<DetachedSourceItemRead> {
  return request(`/cases/${caseId}/detached-source-items/${itemId}/attach`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_object_id: targetObjectId, review_comment: reviewComment || null })
  });
}

export function discardDetachedSourceItem(
  caseId: string,
  itemId: string,
  reviewComment?: string
): Promise<DetachedSourceItemRead> {
  return request(`/cases/${caseId}/detached-source-items/${itemId}/discard`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ review_comment: reviewComment || null })
  });
}

export function createManualObject(caseId: string, payload: ManualObjectPayload): Promise<ManualObjectResponse> {
  return request(`/cases/${caseId}/manual-objects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function createManualObjectFromDetachedSource(
  caseId: string,
  itemId: string,
  payload: ManualObjectFromSourcePayload
): Promise<ManualObjectResponse> {
  return request(`/cases/${caseId}/detached-source-items/${itemId}/manual-object`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function createManualContradictionCandidate(
  caseId: string,
  payload: ManualContradictionCandidatePayload
): Promise<unknown> {
  return request(`/cases/${caseId}/contradiction-candidates/manual`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
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

export function listDocuments(caseId: string): Promise<{ data: DocumentRead[] }> {
  return request(`/cases/${caseId}/documents`);
}

export function listDocumentTaxonomy(): Promise<{ data: DocumentTaxonomyGroupRead[] }> {
  return request("/document-taxonomy");
}

export function listEntities(caseId: string): Promise<{ data: EntityRead[] }> {
  return request(`/cases/${caseId}/entities`);
}

export function listEvents(caseId: string): Promise<{ data: EventRead[] }> {
  return request(`/cases/${caseId}/events`);
}

export function listMissingItemCandidates(caseId: string): Promise<{ data: MissingItemCandidateRead[] }> {
  return request(`/cases/${caseId}/missing-item-candidates`);
}

export function listDetachedSourceItems(caseId: string): Promise<{ data: DetachedSourceItemRead[] }> {
  return request(`/cases/${caseId}/detached-source-items`);
}

export function listDocumentPages(caseId: string, documentId: string): Promise<{ data: DocumentPageRead[] }> {
  return request(`/cases/${caseId}/documents/${documentId}/pages`);
}

export function listDocumentChunks(caseId: string, documentId: string): Promise<{ data: DocumentChunkRead[] }> {
  return request(`/cases/${caseId}/documents/${documentId}/chunks`);
}

export function listAnalysisRuns(caseId: string): Promise<{ data: AnalysisRunRead[] }> {
  return request(`/cases/${caseId}/analysis-runs`);
}

export function getAnalysisRun(caseId: string, analysisRunId: string): Promise<AnalysisRunDetail> {
  return request(`/cases/${caseId}/analysis-runs/${analysisRunId}`);
}

export function listExports(caseId: string): Promise<{ data: ExportRead[] }> {
  return request(`/cases/${caseId}/exports`);
}

export function importDocument(
  caseId: string,
  file: File,
  documentGroupCode: string,
  documentTypeCode: string
): Promise<unknown> {
  const body = new FormData();
  body.append("file", file);
  body.append("document_group_code", documentGroupCode);
  body.append("document_type_code", documentTypeCode);
  body.append("language_code", "hu");
  return request(`/cases/${caseId}/documents`, { method: "POST", body });
}

export function updateDocumentTaxonomy(
  caseId: string,
  documentId: string,
  payload: { document_group_code: string; document_type_code: string; comment?: string | null }
): Promise<DocumentRead> {
  return request(`/cases/${caseId}/documents/${documentId}/taxonomy`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function runDocumentOcr(caseId: string, documentId: string, reason?: string): Promise<DocumentProcessResponse> {
  return request(`/cases/${caseId}/documents/${documentId}/ocr`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: reason || null })
  });
}

export function createDocumentChunks(caseId: string, documentId: string, reason?: string): Promise<DocumentProcessResponse> {
  return request(`/cases/${caseId}/documents/${documentId}/chunks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: reason || null })
  });
}

export function runAnalysis(caseId: string, moduleKey: string, payload: AnalysisRunPayload): Promise<AnalysisResponse> {
  return request(`/cases/${caseId}/analysis/modules/${moduleKey}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function indexChunks(
  caseId: string,
  payload: { document_id?: string | null; limit?: number; force_reindex?: boolean }
): Promise<ChunkIndexResponse> {
  return request(`/cases/${caseId}/indexes/chunks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function startChunkIndexJob(
  caseId: string,
  payload: {
    document_id?: string | null;
    document_ids?: string[];
    document_group_code?: string | null;
    document_type_code?: string | null;
    limit?: number;
    force_reindex?: boolean;
  }
): Promise<ChunkIndexJobResponse> {
  return request(`/cases/${caseId}/indexes/chunks/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function getChunkIndexStatus(
  caseId: string,
  filters?: {
    document_id?: string | null;
    document_ids?: string[];
    document_group_code?: string | null;
    document_type_code?: string | null;
  } | null
): Promise<ChunkIndexStatusResponse> {
  const params = new URLSearchParams();
  if (filters?.document_id) {
    params.set("document_id", filters.document_id);
  }
  for (const documentId of filters?.document_ids ?? []) {
    params.append("document_ids", documentId);
  }
  if (filters?.document_group_code) {
    params.set("document_group_code", filters.document_group_code);
  }
  if (filters?.document_type_code) {
    params.set("document_type_code", filters.document_type_code);
  }
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return request(`/cases/${caseId}/indexes/chunks/status${suffix}`);
}

export function getLlmSmoke(): Promise<LlmSmokeResponse> {
  return request("/system/llm/smoke");
}

export function loadEmbeddingModel(): Promise<unknown> {
  return request("/system/llm/load-embedding-model", { method: "POST" });
}

export function loadChatModel(): Promise<unknown> {
  return request("/system/llm/load-chat-model", { method: "POST" });
}

export function getReviewReport(caseId: string, filters: ReviewReportFilterValues = {}): Promise<ReviewReport> {
  const params = new URLSearchParams();
  if (filters.objectType) {
    params.set("object_type", filters.objectType);
  }
  if (filters.reviewStatus) {
    params.set("review_status", filters.reviewStatus);
  }
  if (filters.sourceValidationStatus) {
    params.set("source_validation_status", filters.sourceValidationStatus);
  }
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return request(`/cases/${caseId}/review-report${suffix}`);
}

export function createExport(
  caseId: string,
  exportType: "json" | "html",
  filters: ReviewReportFilterValues = {}
): Promise<ExportDetail> {
  return request(`/cases/${caseId}/exports`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      export_type: exportType,
      export_scope: "review_report",
      review_filter: filters.reviewStatus === "verified" ? "verified_only" : filters.reviewStatus === "rejected" ? "rejected" : filters.reviewStatus === "needs_review" ? "needs_review" : "all",
      require_source_valid: true,
      report_filters: {
        object_types: filters.objectType ? [filters.objectType] : null,
        review_statuses: filters.reviewStatus ? [filters.reviewStatus] : null,
        source_validation_statuses: filters.sourceValidationStatus ? [filters.sourceValidationStatus] : null
      }
    })
  });
}
