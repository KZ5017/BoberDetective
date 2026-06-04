export type CaseRead = {
  id: string;
  case_reference: string | null;
  case_name: string;
  description: string | null;
  status: string;
  created_at: string;
};

export type CaseDeleteResponse = {
  case_id: string;
  deleted_counts: Record<string, number>;
  qdrant_collection: string;
};

export type DocumentRead = {
  id: string;
  original_filename: string;
  language_code: string | null;
  file_size_bytes: number;
  sha256_hash: string;
  processing_status: string;
  lifecycle_status: string;
  lifecycle_status_changed_at: string | null;
  lifecycle_status_changed_by_user_id: string | null;
  lifecycle_status_reason: string | null;
  page_count: number | null;
  current_chunk_count: number;
  imported_at: string;
  ocr_recommendation: {
    action: "hidden" | "recommended" | "optional";
    reason_code: string;
    message: string;
  } | null;
};

export type DocumentCollectionRead = {
  id: string;
  case_id: string;
  name: string;
  description: string | null;
  color: string | null;
  sort_order: number;
  document_count: number;
  active_document_count: number;
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
};

export type DocumentCollectionMembershipChangeResponse = {
  collection_id: string;
  requested_count: number;
  added_count: number;
  removed_count: number;
  already_present_count: number;
  not_present_count: number;
  skipped_count: number;
  skipped_reasons: string[];
  active_document_count: number;
  total_document_count: number;
};

export type DocumentCollectionScopeResolveResponse = {
  source_mode: "case" | "documents" | "collections";
  requested_document_ids: string[];
  requested_collection_ids: string[];
  resolved_document_count: number;
  active_document_count: number;
  inactive_document_count: number;
  duplicate_membership_count: number;
  document_ids_preview: string[];
  warnings: string[];
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
  display_label: string | null;
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
      source_reference_id: string | null;
      document_id: string | null;
      document_filename: string | null;
      page_id: string | null;
      chunk_id: string | null;
      page_number: number | null;
      chunk_index: number | null;
      citation_label: string | null;
      quote_text: string | null;
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
  document_lifecycle_status: string | null;
  page_id: string | null;
  chunk_id: string | null;
  page_number: number | null;
  chunk_index: number | null;
  quote_char_start: number | null;
  quote_char_end: number | null;
  source_text_excerpt_char_start: number | null;
  source_text_excerpt_char_end: number | null;
  citation_label: string | null;
  quote_text: string;
  source_text_excerpt: string | null;
  source_kind: string;
  support_type: string;
  relevance_rank: number | null;
};

export type SourceReferenceRead = {
  id: string;
  case_id: string;
  document_id: string;
  page_id: string | null;
  chunk_id: string | null;
  page_number: number | null;
  quote_text: string;
  quote_char_start: number | null;
  quote_char_end: number | null;
  source_text_excerpt: string | null;
  source_text_excerpt_char_start: number | null;
  source_text_excerpt_char_end: number | null;
  citation_label: string | null;
  confidence: string | number | null;
  source_kind: string;
  extraction_run_id: string | null;
  created_by_user_id: string | null;
  created_at: string;
};

export type ResearchFindingRead = {
  id: string;
  case_id: string;
  analysis_run_id: string;
  source_reference_id: string;
  title: string;
  finding_text: string;
  suggested_type: "claim" | "event" | "entity" | "document_reference" | "other";
  suggested_type_reason: string | null;
  relevance_reason: string;
  source_validation_status: string;
  llm_support_status: "confirmed" | "unconfirmed";
  conversion_status: string;
  target_object_type: string | null;
  target_object_id: string | null;
  created_at: string;
  updated_at: string;
  source_reference: SourceReferenceRead | null;
};

export type ResearchFindingLatestRunSummary = {
  analysis_run_id: string;
  status: string;
  validation_status: string | null;
  started_at: string;
  finished_at: string | null;
  query: string | null;
  source_mode: AnalysisSourceMode | string | null;
  document_id: string | null;
  collection_id: string | null;
  document_ids: string[];
  max_chunks: number | null;
  batch_size: number | null;
  retrieval_strategy: RetrievalStrategy | string | null;
  selected_chunk_count: number;
  created_finding_count: number;
  corrected_finding_count: number;
  unconfirmed_finding_count: number;
  unsupported_count: number;
  unsupported_items: string[];
  error_message: string | null;
};

export type ResearchFindingLatestRunSummaryResponse = {
  latest_run: ResearchFindingLatestRunSummary | null;
};

export type ReviewReportItem = {
  object_type: string;
  object_id: string;
  title: string;
  body_text: string | null;
  subtype: string;
  event_time_start: string | null;
  time_precision: string | null;
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

export type ClaimRead = {
  id: string;
  case_id: string;
  claim_type: string;
  claim_title: string;
  claim_text: string;
  claim_time_raw: string | null;
  claim_time_normalized: string | null;
  confidence: string | number | null;
  created_by_analysis_run_id: string;
  source_validation_status: string;
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
  event_time_start: string | null;
  event_time_end: string | null;
  time_precision: string | null;
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
  source_text_excerpt: string | null;
  source_text_excerpt_char_start: number | null;
  source_text_excerpt_char_end: number | null;
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
  contradiction_candidates: unknown[];
  research_findings: Array<{
    research_finding_id: string;
    title: string;
    finding_text: string;
    suggested_type: string;
    suggested_type_reason: string | null;
    relevance_reason: string;
    llm_support_status: string;
    source_validation_status: string;
    quote_text: string;
    source_label: string;
    source_reference_id: string;
    document_id: string;
    chunk_id: string;
  }>;
  unconfirmed_research_findings: Array<{
    title: string;
    finding_text: string;
    suggested_type: string;
    suggested_type_reason: string | null;
    relevance_reason: string;
    quote_text: string;
    source_label: string;
    validation_message: string;
    document_id: string;
    chunk_id: string;
  }>;
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
  claim_title?: string | null;
  claim_text?: string | null;
  entity_type?: string | null;
  canonical_name?: string | null;
  normalized_value?: string | null;
  description?: string | null;
  event_type?: string | null;
  event_title?: string | null;
  event_description?: string | null;
  event_time_start?: string | null;
  time_precision?: string | null;
  missing_item_type?: string | null;
  referenced_item_text?: string | null;
};

export type ManualObjectFromSourcePayload = Omit<ManualObjectPayload, "source_reference">;

export type ManualSourceAttachmentPayload = {
  source_reference: ManualObjectPayload["source_reference"];
  target_object_type: ManualObjectType;
  target_object_id: string;
};

export type ManualObjectResponse = {
  analysis_run_id: string;
  source_reference: {
    id: string;
    citation_label: string | null;
  };
  object_type: string;
  object_id: string;
};

export type ManualSourceAttachmentResponse = {
  analysis_run_id: string;
  source_reference: {
    id: string;
    citation_label: string | null;
  };
  target_object_type: string;
  target_object_id: string;
  skipped_duplicate_source: boolean;
  target_reactivated: boolean;
};

export type ResearchFindingConvertResponse = ManualObjectResponse & {
  finding: ResearchFindingRead;
};

export type ManualContradictionCandidatePayload = {
  claim_id_a: string;
  claim_id_b: string;
  contradiction_type: "time_conflict" | "location_conflict" | "identity_conflict" | "document_mismatch" | "amount_conflict" | "other";
  severity_hint?: "low" | "medium" | "high" | null;
  description: string;
};

export type AnalysisSourceMode = "case" | "document" | "collection";
export type ClaimReviewScope = "reviewable" | "verified" | "needs_review" | "all_source_valid";
export type RetrievalStrategy = "keyword" | "semantic" | "hybrid";

export type AnalysisRunPayload = {
  query?: string | null;
  source_mode?: AnalysisSourceMode;
  document_id?: string | null;
  collection_id?: string | null;
  document_ids?: string[];
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
  collection_id: string | null;
  document_ids: string[];
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

export type FullDocumentProcessingProfileRead = {
  key: string;
  label: string;
  description: string;
  item_kinds: string[];
};

export type DocumentProcessingItemRead = {
  id: string;
  case_id: string;
  document_id: string;
  analysis_run_id: string;
  profile_key: string;
  item_kind: string;
  display_label: string;
  short_description: string | null;
  mentioned_forms_json: unknown[];
  source_supported_details_json: unknown[];
  relationships_json: unknown[];
  recommended_search_focus: string | null;
  alternative_search_focuses_json: unknown[];
  source_evidence_json: Array<{
    source_label?: string;
    quote_text?: string;
    page_number?: number;
    quote_char_start?: number;
    quote_char_end?: number;
    [key: string]: unknown;
  }>;
  occurrence_status: "unique" | "repeated";
  work_status: string;
  target_object_type: string | null;
  target_object_id: string | null;
  created_at: string;
  updated_at: string;
};

export type FullDocumentProcessingRunResponse = {
  analysis_run_id: string;
  document_id: string;
  profile_key: string;
  created_item_count: number;
  unsupported_count: number;
  validation_status: string;
  items: DocumentProcessingItemRead[];
  unsupported_items: string[];
};

const reviewPathByType: Record<string, (caseId: string, objectId: string) => string> = {
  claim: (caseId, objectId) => `/cases/${caseId}/claims/${objectId}/reviews`,
  event: (caseId, objectId) => `/cases/${caseId}/events/${objectId}/reviews`,
  entity: (caseId, objectId) => `/cases/${caseId}/entities/${objectId}/reviews`,
  contradiction_candidate: (caseId, objectId) => `/cases/${caseId}/contradiction-candidates/${objectId}/reviews`,
  missing_item_candidate: (caseId, objectId) => `/cases/${caseId}/missing-item-candidates/${objectId}/reviews`
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `${response.status} ${response.statusText}`);
  }
  if (response.status === 204) {
    return undefined as T;
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

export function deleteReviewReportItem(caseId: string, objectType: string, objectId: string): Promise<void> {
  return request(`/cases/${caseId}/review-report/items/${objectType}/${objectId}`, {
    method: "DELETE"
  });
}

export function updateReviewReportItemText(
  caseId: string,
  objectType: string,
  objectId: string,
  title: string,
  description: string
): Promise<void> {
  return request(`/cases/${caseId}/review-report/items/${objectType}/${objectId}/text`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, description })
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

export function mergeClaim(
  caseId: string,
  sourceClaimId: string,
  targetClaimId: string,
  reviewComment?: string
): Promise<unknown> {
  return request(`/cases/${caseId}/claims/${sourceClaimId}/merge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_claim_id: targetClaimId, review_comment: reviewComment || null })
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
    claim: `/cases/${caseId}/claims/${objectId}/sources/${sourceLinkId}/detach`,
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
    claim: {
      path: `/cases/${caseId}/claims/${objectId}/sources/${sourceLinkId}/move`,
      targetKey: "target_claim_id"
    },
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

export function deleteDetachedSourceItem(
  caseId: string,
  itemId: string
): Promise<void> {
  return request(`/cases/${caseId}/detached-source-items/${itemId}`, {
    method: "DELETE"
  });
}

export function createManualObject(caseId: string, payload: ManualObjectPayload): Promise<ManualObjectResponse> {
  return request(`/cases/${caseId}/manual-objects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function attachManualSourceToExistingObject(
  caseId: string,
  payload: ManualSourceAttachmentPayload
): Promise<ManualSourceAttachmentResponse> {
  return request(`/cases/${caseId}/manual-source-attachments`, {
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

export function deleteCase(caseId: string): Promise<CaseDeleteResponse> {
  return request(`/cases/${caseId}`, {
    method: "DELETE"
  });
}

export function listDocuments(caseId: string): Promise<{ data: DocumentRead[] }> {
  return request(`/cases/${caseId}/documents`);
}

export function listDocumentCollections(caseId: string): Promise<{ data: DocumentCollectionRead[] }> {
  return request(`/cases/${caseId}/document-collections`);
}

export function createDocumentCollection(
  caseId: string,
  payload: { name: string; description?: string | null; color?: string | null; sort_order?: number }
): Promise<DocumentCollectionRead> {
  return request(`/cases/${caseId}/document-collections`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function updateDocumentCollection(
  caseId: string,
  collectionId: string,
  payload: { name?: string; description?: string | null; color?: string | null; sort_order?: number }
): Promise<DocumentCollectionRead> {
  return request(`/cases/${caseId}/document-collections/${collectionId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function deleteDocumentCollection(caseId: string, collectionId: string): Promise<void> {
  return request(`/cases/${caseId}/document-collections/${collectionId}`, {
    method: "DELETE"
  });
}

export function listDocumentCollectionDocuments(caseId: string, collectionId: string): Promise<{ data: DocumentRead[] }> {
  return request(`/cases/${caseId}/document-collections/${collectionId}/documents`);
}

export function addDocumentsToCollection(
  caseId: string,
  collectionId: string,
  documentIds: string[]
): Promise<DocumentCollectionMembershipChangeResponse> {
  return request(`/cases/${caseId}/document-collections/${collectionId}/documents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_ids: documentIds })
  });
}

export function removeDocumentsFromCollection(
  caseId: string,
  collectionId: string,
  documentIds: string[]
): Promise<DocumentCollectionMembershipChangeResponse> {
  return request(`/cases/${caseId}/document-collections/${collectionId}/documents`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_ids: documentIds })
  });
}

export function resolveDocumentCollectionScope(
  caseId: string,
  collectionIds: string[]
): Promise<DocumentCollectionScopeResolveResponse> {
  return request(`/cases/${caseId}/document-collections/resolve-scope`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_mode: "collections", collection_ids: collectionIds })
  });
}

export function listEntities(caseId: string): Promise<{ data: EntityRead[] }> {
  return request(`/cases/${caseId}/entities`);
}

export function listClaims(caseId: string): Promise<{ data: ClaimRead[] }> {
  return request(`/cases/${caseId}/claims`);
}

export function listEvents(caseId: string): Promise<{ data: EventRead[] }> {
  return request(`/cases/${caseId}/events`);
}

export function listMissingItemCandidates(caseId: string): Promise<{ data: MissingItemCandidateRead[] }> {
  return request(`/cases/${caseId}/missing-item-candidates`);
}

export function listResearchFindings(caseId: string): Promise<{ data: ResearchFindingRead[] }> {
  return request(`/cases/${caseId}/research-findings`);
}

export function getLatestResearchFindingRunSummary(caseId: string): Promise<ResearchFindingLatestRunSummaryResponse> {
  return request(`/cases/${caseId}/research-findings/latest-run-summary`);
}

export function listFullDocumentProcessingProfiles(): Promise<{ data: FullDocumentProcessingProfileRead[] }> {
  return request("/full-document-processing/profiles");
}

export function listDocumentProcessingItems(
  caseId: string,
  documentId: string,
  filters: { profile_key?: string; work_status?: string; item_kind?: string; search?: string } = {}
): Promise<{ data: DocumentProcessingItemRead[] }> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.set(key, value);
  }
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return request(`/cases/${caseId}/documents/${documentId}/full-document-processing/items${suffix}`);
}

export function runFullDocumentProcessing(
  caseId: string,
  documentId: string,
  payload: { profile_key: string; page_start?: number | null; page_end?: number | null }
): Promise<FullDocumentProcessingRunResponse> {
  return request(`/cases/${caseId}/documents/${documentId}/full-document-processing/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function updateDocumentProcessingItemStatus(
  caseId: string,
  itemId: string,
  workStatus: "active" | "set_aside" | "deleted"
): Promise<{ item: DocumentProcessingItemRead }> {
  return request(`/cases/${caseId}/full-document-processing/items/${itemId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ work_status: workStatus })
  });
}

export function bulkDeleteDocumentProcessingItems(
  caseId: string,
  itemIds: string[]
): Promise<{ deleted_count: number }> {
  return request(`/cases/${caseId}/full-document-processing/items/bulk-delete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ item_ids: itemIds })
  });
}

export function convertResearchFinding(
  caseId: string,
  findingId: string,
  payload: ManualObjectFromSourcePayload
): Promise<ResearchFindingConvertResponse> {
  return request(`/cases/${caseId}/research-findings/${findingId}/convert`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function setAsideResearchFinding(caseId: string, findingId: string): Promise<{ finding: ResearchFindingRead }> {
  return request(`/cases/${caseId}/research-findings/${findingId}/set-aside`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({})
  });
}

export function restoreResearchFinding(caseId: string, findingId: string): Promise<{ finding: ResearchFindingRead }> {
  return request(`/cases/${caseId}/research-findings/${findingId}/restore`, {
    method: "POST"
  });
}

export function deleteResearchFinding(caseId: string, findingId: string): Promise<void> {
  return request(`/cases/${caseId}/research-findings/${findingId}`, {
    method: "DELETE"
  });
}

export function bulkDeleteResearchFindings(caseId: string, findingIds: string[]): Promise<{ deleted_count: number }> {
  return request(`/cases/${caseId}/research-findings/bulk-delete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ finding_ids: findingIds })
  });
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

export function importDocument(caseId: string, file: File): Promise<unknown> {
  const body = new FormData();
  body.append("file", file);
  body.append("language_code", "hu");
  return request(`/cases/${caseId}/documents`, { method: "POST", body });
}

export function updateDocumentLifecycle(
  caseId: string,
  documentId: string,
  action: "exclude" | "archive" | "restore",
  reason?: string
): Promise<DocumentRead> {
  return request(`/cases/${caseId}/documents/${documentId}/${action}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: reason || null })
  });
}

export function discardDocument(caseId: string, documentId: string, reason?: string): Promise<void> {
  return request(`/cases/${caseId}/documents/${documentId}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: reason || null })
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
  payload: { document_id?: string | null; collection_id?: string | null; limit?: number; force_reindex?: boolean }
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
    collection_id?: string | null;
    document_ids?: string[];
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
    collection_id?: string | null;
    document_ids?: string[];
  } | null
): Promise<ChunkIndexStatusResponse> {
  const params = new URLSearchParams();
  if (filters?.document_id) {
    params.set("document_id", filters.document_id);
  }
  if (filters?.collection_id) {
    params.set("collection_id", filters.collection_id);
  }
  for (const documentId of filters?.document_ids ?? []) {
    params.append("document_ids", documentId);
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

export function unloadEmbeddingModel(): Promise<unknown> {
  return request("/system/llm/unload-embedding-model", { method: "POST" });
}

export function unloadChatModel(): Promise<unknown> {
  return request("/system/llm/unload-chat-model", { method: "POST" });
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
