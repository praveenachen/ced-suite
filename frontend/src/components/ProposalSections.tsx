"use client";

import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { Requirements } from "@/lib/api";
import { ArrowLeft, ArrowRight, FileText, PencilLine, Plus, Trash2 } from "lucide-react";

export function ProposalSections({
  requirements,
  onNext,
  onBack,
  onSectionTitleChange,
  onSectionDelete,
  onSectionAdd,
}: {
  requirements: Requirements;
  onNext: () => void;
  onBack: () => void;
  onSectionTitleChange: (sectionKey: string, title: string) => void;
  onSectionDelete: (sectionKey: string) => void;
  onSectionAdd: () => void;
}) {
  const sections = requirements.sections || [];
  const count = sections.length;
  const parserMeta = requirements.parser_meta;
  const parseConfidence = parserMeta?.confidence;
  const showParseWarning = parseConfidence === "low" || count <= 1;
  const diagnostics = parserMeta?.diagnostics || [];
  const fallbackReasons = parserMeta?.fallback_reasons || [];
  const llmError = parserMeta?.llm_error;
  const sectionPreview = parserMeta?.section_titles_preview || [];
  const heuristicPreview = parserMeta?.heuristic_titles_preview || [];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-6"
    >
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-4">
            <div>
              <CardTitle>Proposal requirements</CardTitle>
              <CardDescription className="mt-1">
                Sections we extracted from the grant posting. You can add community info next
                and we&apos;ll generate content for each.
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <span className="rounded-md bg-muted px-2 py-1 text-xs font-medium text-muted-foreground">
                {count} sections
              </span>
              <span className="rounded-md bg-amber-100 px-2 py-1 text-xs font-medium text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
                {count} required
              </span>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {showParseWarning && (
            <div className="mb-4 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-100">
              Parse quality looks low ({count} section detected). Consider uploading a cleaner text-based PDF/DOCX, or continue and manually edit section expectations.
            </div>
          )}
          {parserMeta && (
            <details className="mb-4 rounded-lg border border-border bg-muted/30 p-3 text-sm text-muted-foreground">
              <summary className="cursor-pointer font-medium text-foreground">
                Extraction diagnostics
              </summary>
              <div className="mt-3 space-y-2">
                <p>
                  Mode: <span className="font-medium text-foreground">{parserMeta.mode || "unknown"}</span>
                  {" | "}
                  Confidence: <span className="font-medium text-foreground">{parseConfidence || "unknown"}</span>
                  {" | "}
                  Model: <span className="font-medium text-foreground">{parserMeta.model || "unknown"}</span>
                </p>
                <p>
                  Raw text: <span className="font-medium text-foreground">{parserMeta.raw_text_length || 0}</span> chars
                  {" | "}
                  Heuristic sections: <span className="font-medium text-foreground">{parserMeta.heuristic_section_count || 0}</span>
                  {" | "}
                  Final sections: <span className="font-medium text-foreground">{parserMeta.final_section_count || 0}</span>
                </p>
                {fallbackReasons.length > 0 && (
                  <p>
                    Fallback reasons: <span className="font-medium text-foreground">{fallbackReasons.join(", ")}</span>
                  </p>
                )}
                {diagnostics.length > 0 && (
                  <p>
                    Diagnostics: <span className="font-medium text-foreground">{diagnostics.join(", ")}</span>
                  </p>
                )}
                {parserMeta.used_default_template && (
                  <p className="text-amber-700 dark:text-amber-300">
                    The parser recovered with the default 5-section template because extraction confidence was too low.
                  </p>
                )}
                {llmError && (
                  <p className="text-destructive">
                    LLM fallback error: {llmError}
                  </p>
                )}
                {heuristicPreview.length > 0 && (
                  <p>
                    Heuristic preview: <span className="font-medium text-foreground">{heuristicPreview.join(" | ")}</span>
                  </p>
                )}
                {sectionPreview.length > 0 && (
                  <p>
                    Final preview: <span className="font-medium text-foreground">{sectionPreview.join(" | ")}</span>
                  </p>
                )}
              </div>
            </details>
          )}
          <div className="space-y-4">
            <div className="flex justify-end">
              <Button variant="secondary" size="sm" onClick={onSectionAdd}>
                <Plus className="mr-2 h-4 w-4" />
                Add section
              </Button>
            </div>
            {sections.map((sec, i) => (
              <div
                key={sec.key}
                className="flex gap-4 rounded-lg border border-border bg-card p-4"
              >
                <div className="h-full w-1 shrink-0 rounded-full bg-primary" />
                <div className="min-w-0 flex-1">
                  <div className="mb-2 flex items-center gap-2">
                    <PencilLine className="h-4 w-4 text-muted-foreground" />
                    <Input
                      value={sec.title}
                      onChange={(e) => onSectionTitleChange(sec.key, e.target.value)}
                      className="h-8"
                      aria-label={`Edit title for section ${i + 1}`}
                    />
                  </div>
                  {sec.guidance && (
                    <p className="mt-1 text-sm text-muted-foreground line-clamp-2">
                      {sec.guidance}
                    </p>
                  )}
                  {sec.word_limit && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      Word limit: {sec.word_limit}
                    </p>
                  )}
                </div>
                <div className="shrink-0">
                  <div className="flex items-center gap-2">
                    <FileText className="h-5 w-5 text-muted-foreground" />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => onSectionDelete(sec.key)}
                      aria-label={`Delete section ${sec.title}`}
                    >
                      <Trash2 className="h-4 w-4 text-muted-foreground" />
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {requirements.eligibility && requirements.eligibility.length > 0 && (
            <div className="mt-6 rounded-lg border border-border bg-muted/30 p-4">
              <h4 className="font-medium text-foreground">Eligibility</h4>
              <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-muted-foreground">
                {requirements.eligibility.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="mt-8 flex gap-3">
            <Button variant="outline" onClick={onBack}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Button>
            <Button onClick={onNext}>
              Continue to community info
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
