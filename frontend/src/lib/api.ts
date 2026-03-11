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
