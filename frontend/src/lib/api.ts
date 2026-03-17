import { API_BASE } from "./utils";

const RAG_USE_CASE = process.env.NEXT_PUBLIC_RAG_USE_CASE || "default";

export type Requirements = {
  grant_name: string;
  sections: { key: string; title: string; guidance: string; word_limit?: number }[];
  eligibility?: string[];
  raw_text?: string;
  must_include?: string[];
  required_sections?: string[];
  parser_meta?: {
    mode?: string;
    confidence?: "low" | "medium" | "high" | string;
    model?: string;
    raw_text_length?: number;
    heuristic_section_count?: number;
    final_section_count?: number;
    llm_fallback_used?: boolean;
    llm_error?: string | null;
    fallback_reasons?: string[];
    diagnostics?: string[];
    used_default_template?: boolean;
    heuristic_titles_preview?: string[];
    section_titles_preview?: string[];
  };
  [k: string]: unknown;
};

export type CommunityProfile = {
  community_name: string;
  region: string;
  local_priority: string;
  timeline?: string;
  challenges?: string;
  strengths?: string;
  partners?: string;
  evidence_note?: string;
  requested_budget?: number;
  indicators_before?: Record<string, number>;
  indicators_after?: Record<string, number>;
  scenario?: Record<string, unknown>;
};

export type DraftSection = {
  key: string;
  title: string;
  body: string;
  guidance?: string;
};

export type Draft = {
  meta: {
    community_name?: string;
    local_priority?: string;
    requested_budget?: number;
    grant_name?: string;
  };
  sections: DraftSection[];
};

export type ValidationResult = {
  gaps: string[];
  warnings: string[];
};

export type ComplianceWarning = {
  type: string;
  message: string;
  details?: Record<string, unknown>;
};

export type ComplianceGap = {
  failed_check_id: string;
  category: string;
  severity: "minor" | "major" | "critical";
  confidence_score: number;
  message: string;
  recommendation: string;
  source_excerpt: string;
  source_document: string;
};

export type SectionComplianceResult = {
  section: string;
  section_label?: string;
  warnings: ComplianceWarning[];
  compliance_gaps: ComplianceGap[];
  scoring_hooks?: {
    overall_score: number;
    dimensions: Record<string, number>;
  };
};

export type AggregatedWarning = ComplianceWarning & {
  section: string;
  section_label?: string;
};

export type AggregatedComplianceGap = ComplianceGap & {
  section: string;
  section_label?: string;
};

export type ComplianceSummary = {
  sectionResults: SectionComplianceResult[];
  warnings: AggregatedWarning[];
  complianceGaps: AggregatedComplianceGap[];
};

export type RewriteReference = {
  rank: number;
  source: string;
  chunk_index?: number;
  distance?: number;
  snippet: string;
};

export type ProposalMetricIssue = {
  issue_id: string;
  title: string;
  message: string;
  severity: "success" | "info" | "warning" | "critical";
  confidence_score: number;
  section_key: string;
  anchor_type: "text" | "paragraph" | "section";
  anchor_text?: string | null;
  anchor_hint?: string | null;
  affected_sections: string[];
  excerpt?: string | null;
  recommendation: string;
};

export type ProposalMetric = {
  id: string;
  label: string;
  category_id: string;
  description: string;
  score: number;
  issues_count: number;
  status: string;
  summary: string;
  issues: ProposalMetricIssue[];
  suggestions: string[];
  linked_sections: string[];
};

export type ProposalMetricCategory = {
  id: string;
  label: string;
  score: number;
  issues: number;
  metrics: ProposalMetric[];
};

export type ProposalAnalysisSection = {
  key: string;
  title: string;
  body: string;
  order: number;
  word_limit?: number | null;
  issues_count: number;
  warnings: ComplianceWarning[];
  compliance_gaps: ComplianceGap[];
  section_score: number;
};

export type ProposalAnalysis = {
  analysis: {
    proposal_id: string;
    file_name: string;
    file_type: "pdf" | "docx";
    uploaded_at: string;
    last_analyzed_at: string;
  };
  extraction: {
    extractor: string;
    confidence: "high" | "medium" | "low";
    preview_mode: "sectioned" | "continuous";
    raw_text_length: number;
    cleaned_text_length: number;
    section_count: number;
    numbering_gaps_detected: boolean;
    warnings: string[];
    candidate_extractors: Array<{
      extractor: string;
      score: number;
      chars: number;
    }>;
  };
  overall_score: number;
  issue_count: number;
  categories: ProposalMetricCategory[];
  sections: ProposalAnalysisSection[];
  additional_submission_requirements: string[];
  assistant_starters: string[];
  raw_preview_text: string;
  report_summary: string;
};

export type ProposalRewriteResponse = {
  proposal_id: string;
  section_key: string;
  rewritten_text: string;
  rationale: string;
  references: RewriteReference[];
};

export type ProposalChatResponse = {
  proposal_id: string;
  response: string;
  suggested_actions: string[];
};

export async function parseGrant(file: File): Promise<{
  requirements: Requirements;
  raw_text: string;
}> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/parse-grant`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to parse grant");
  }
  return res.json();
}

export async function generateDraft(
  profile: CommunityProfile,
  requirements: Requirements,
  requested_budget: number
): Promise<Draft> {
  const res = await fetch(`${API_BASE}/api/generate-draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      profile,
      requirements,
      requested_budget,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to generate draft");
  }
  return res.json();
}

export async function enhanceDraft(
  draft: Draft,
  requirements: Requirements,
  profile: CommunityProfile,
  useCase: string = RAG_USE_CASE
): Promise<{ enhanced: Record<string, string> }> {
  const res = await fetch(`${API_BASE}/api/enhance`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ draft, requirements, profile, use_case: useCase }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to enhance draft");
  }
  return res.json();
}

export async function validateDraft(
  draft: Draft,
  requirements: Requirements
): Promise<ValidationResult> {
  const res = await fetch(`${API_BASE}/api/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ draft, requirements }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to validate");
  }
  return res.json();
}

export async function evaluateSectionCompliance(params: {
  section_name: string;
  section_text: string;
}): Promise<SectionComplianceResult> {
  const res = await fetch(`${API_BASE}/evaluate/compliance`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to evaluate compliance");
  }
  return res.json();
}

export async function evaluateDraftCompliance(
  sections: DraftSection[]
): Promise<ComplianceSummary> {
  const sectionResults = await Promise.all(
    sections.map(async (section) => {
      const result = await evaluateSectionCompliance({
        section_name: section.title || section.key,
        section_text: section.body || "",
      });
      return {
        ...result,
        section: section.key,
        section_label: section.title || section.key,
      };
    })
  );

  return {
    sectionResults,
    warnings: sectionResults.flatMap((result) =>
      result.warnings.map((warning) => ({
        ...warning,
        section: result.section,
        section_label: result.section_label,
      }))
    ),
    complianceGaps: sectionResults.flatMap((result) =>
      result.compliance_gaps.map((gap) => ({
        ...gap,
        section: result.section,
        section_label: result.section_label,
      }))
    ),
  };
}

export async function uploadExistingDraft(file: File): Promise<ProposalAnalysis> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/evaluate/proposal`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to analyze proposal draft");
  }
  return res.json();
}

export async function getProposalAnalysis(proposalId: string): Promise<ProposalAnalysis> {
  const res = await fetch(`${API_BASE}/evaluate/proposal/${proposalId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to load proposal analysis");
  }
  return res.json();
}

export async function reanalyzeProposal(params: {
  proposal_id: string;
  sections: ProposalAnalysisSection[];
}): Promise<ProposalAnalysis> {
  const res = await fetch(`${API_BASE}/evaluate/proposal/reanalyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to re-run proposal analysis");
  }
  return res.json();
}

export async function rewriteProposalSection(params: {
  proposal_id: string;
  section_key: string;
  instruction: string;
  metric_id?: string;
  issue_id?: string;
  issue_message?: string;
  issue_recommendation?: string;
}): Promise<ProposalRewriteResponse> {
  const res = await fetch(`${API_BASE}/evaluate/proposal/section-rewrite`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to rewrite proposal section");
  }
  return res.json();
}

export async function chatAboutProposal(params: {
  proposal_id: string;
  message: string;
  section_key?: string;
  metric_id?: string;
}): Promise<ProposalChatResponse> {
  const res = await fetch(`${API_BASE}/evaluate/proposal/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to get assistant response");
  }
  return res.json();
}

export async function rewriteSection(
  params: {
    section_key: string;
    section_title: string;
    current_text: string;
    instruction: string;
    requirements: Requirements;
    profile: CommunityProfile;
    use_case?: string;
  }
): Promise<{ text: string; references: RewriteReference[] }> {
  const res = await fetch(`${API_BASE}/api/rewrite-section`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...params,
      use_case: params.use_case || RAG_USE_CASE,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to rewrite section");
  }
  return res.json();
}

export async function exportDraftPdf(params: {
  grant_name: string;
  community_name: string;
  region: string;
  local_priority: string;
  requested_budget?: number;
  sections: Array<{ key?: string; title: string; body: string }>;
}): Promise<Blob> {
  const res = await fetch(`${API_BASE}/api/export-draft-pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to export PDF");
  }
  return res.blob();
}

export async function exportDraftDocx(params: {
  grant_name: string;
  community_name: string;
  region: string;
  local_priority: string;
  requested_budget?: number;
  sections: Array<{ key?: string; title: string; body: string }>;
}): Promise<Blob> {
  const res = await fetch(`${API_BASE}/api/export-draft-docx`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to export DOCX");
  }
  return res.blob();
}
