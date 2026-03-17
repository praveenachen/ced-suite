"use client";

import { useMemo, useState } from "react";
import { FilePenLine, Sparkles } from "lucide-react";

import type { ProposalAnalysisSection } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

type RewritePreview = {
  sectionKey: string;
  text: string;
  rationale: string;
} | null;

export function ProposalSectionEditor({
  sections,
  selectedSectionKey,
  selectedMetricLabel,
  rewritePreview,
  isRewritePending,
  onSectionSelect,
  onSectionBodyChange,
  onRewrite,
  onApplyRewrite,
}: {
  sections: ProposalAnalysisSection[];
  selectedSectionKey: string | null;
  selectedMetricLabel?: string | null;
  rewritePreview: RewritePreview;
  isRewritePending: boolean;
  onSectionSelect: (sectionKey: string) => void;
  onSectionBodyChange: (sectionKey: string, nextBody: string) => void;
  onRewrite: (sectionKey: string, instruction: string) => void;
  onApplyRewrite: (sectionKey: string) => void;
}) {
  const [instruction, setInstruction] = useState("Strengthen this section and make it more specific.");
  const selectedSection = useMemo(
    () => sections.find((section) => section.key === selectedSectionKey) || sections[0],
    [sections, selectedSectionKey]
  );

  if (!selectedSection) return null;

  const activePreview = rewritePreview?.sectionKey === selectedSection.key ? rewritePreview : null;

  return (
    <div className="grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)]">
      <Card className="border-primary/20 bg-card/80 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="text-base">Extracted sections</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {sections.map((section) => (
            <Button
              key={section.key}
              variant="ghost"
              className={`h-auto w-full justify-between rounded-xl border px-3 py-3 text-left ${
                selectedSection.key === section.key ? "border-primary/40 bg-primary/10" : "border-border/70 bg-muted/20"
              }`}
              onClick={() => onSectionSelect(section.key)}
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-foreground">{section.title}</p>
                <p className="text-xs text-muted-foreground">
                  {section.issues_count} issues - {section.section_score}% score
                </p>
              </div>
            </Button>
          ))}
        </CardContent>
      </Card>

      <Card id={`section-${selectedSection.key}`} className="scroll-mt-28 border-primary/20 bg-card/80 backdrop-blur-sm">
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <CardTitle className="flex items-center gap-2 text-lg">
                <FilePenLine className="h-4 w-4 text-primary" />
                {selectedSection.title}
              </CardTitle>
              <p className="mt-2 text-sm text-muted-foreground">
                Edit the extracted section directly, then re-run analysis to refresh the scorecard and linked issues.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <span className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground">
                {selectedSection.section_score}% score
              </span>
              {selectedMetricLabel && (
                <span className="rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs text-primary">
                  Focus: {selectedMetricLabel}
                </span>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <Textarea
            value={selectedSection.body}
            onChange={(event) => onSectionBodyChange(selectedSection.key, event.target.value)}
            rows={16}
            className="bg-background/60"
          />

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-border/70 bg-muted/20 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Rewrite this section</p>
              <Textarea
                value={instruction}
                onChange={(event) => setInstruction(event.target.value)}
                rows={3}
                className="mt-3"
              />
              <div className="mt-3 flex flex-wrap gap-2">
                <Button onClick={() => onRewrite(selectedSection.key, instruction)} disabled={isRewritePending}>
                  <Sparkles className="mr-2 h-4 w-4" />
                  {isRewritePending ? "Generating..." : "Improve this section"}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => setInstruction("Add measurable outcomes and make this section more specific.")}
                >
                  Add measurable outcomes
                </Button>
                <Button
                  variant="outline"
                  onClick={() => setInstruction("Strengthen funder alignment and clarify community benefit.")}
                >
                  Improve alignment
                </Button>
              </div>
            </div>

            <div className="rounded-2xl border border-border/70 bg-muted/20 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Section signals</p>
              <div className="mt-3 space-y-3 text-sm">
                <div className="rounded-xl border border-amber-500/20 bg-amber-950/10 p-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-300">Warnings</p>
                  {selectedSection.warnings.length > 0 ? (
                    <ul className="mt-2 space-y-2 text-amber-100/90">
                      {selectedSection.warnings.map((warning, index) => (
                        <li key={`${warning.type}-${index}`}>{warning.message}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-2 text-muted-foreground">No deterministic warnings for this section.</p>
                  )}
                </div>
                <div className="rounded-xl border border-rose-500/20 bg-rose-950/10 p-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-rose-300">Compliance gaps</p>
                  {selectedSection.compliance_gaps.length > 0 ? (
                    <ul className="mt-2 space-y-2 text-rose-100/90">
                      {selectedSection.compliance_gaps.slice(0, 3).map((gap) => (
                        <li key={gap.failed_check_id}>{gap.message}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-2 text-muted-foreground">No substantive compliance gaps for this section.</p>
                  )}
                </div>
              </div>
            </div>
          </div>

          {activePreview && (
            <div className="rounded-2xl border border-primary/30 bg-primary/10 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">Suggested rewrite</p>
                  <p className="mt-2 text-sm text-muted-foreground">{activePreview.rationale}</p>
                </div>
                <Button size="sm" onClick={() => onApplyRewrite(selectedSection.key)}>
                  Apply suggestion
                </Button>
              </div>
              <p className="mt-3 whitespace-pre-wrap text-sm text-foreground">{activePreview.text}</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
