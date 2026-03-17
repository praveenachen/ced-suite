"use client";

import { useState } from "react";
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronUp, CircleDot } from "lucide-react";

import type { ProposalMetric } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const severityStyles = {
  success: "border-emerald-500/30 bg-emerald-950/15 text-emerald-200",
  info: "border-sky-500/30 bg-sky-950/15 text-sky-200",
  warning: "border-amber-500/30 bg-amber-950/15 text-amber-200",
  critical: "border-rose-500/30 bg-rose-950/15 text-rose-200",
};

function MetricScorePill({ score }: { score: number }) {
  const clamped = Math.max(0, Math.min(100, score));
  const circumference = 2 * Math.PI * 10;
  const dash = circumference - (circumference * clamped) / 100;

  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-border px-2.5 py-1 text-xs text-muted-foreground">
      <svg viewBox="0 0 24 24" className="h-4 w-4">
        <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" strokeOpacity="0.2" strokeWidth="3" />
        <circle
          cx="12"
          cy="12"
          r="10"
          fill="none"
          stroke="hsl(var(--primary))"
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dash}
          transform="rotate(-90 12 12)"
        />
      </svg>
      {clamped}%
    </span>
  );
}

function IssueCountPill({ issues }: { issues: number }) {
  if (issues === 0) {
    return (
      <span className="rounded-full border border-emerald-500/25 bg-emerald-950/15 px-3 py-1 text-xs text-emerald-300">
        0 issues
      </span>
    );
  }

  return (
    <span className="rounded-full border border-rose-500/35 bg-rose-950/20 px-3 py-1 text-xs text-rose-300">
      {issues} issues
    </span>
  );
}

export function MetricAccordionCard({
  metric,
  onSectionSelect,
  onAskAssistant,
}: {
  metric: ProposalMetric;
  onSectionSelect: (sectionKey: string) => void;
  onAskAssistant: (metricId: string) => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <Card id={`metric-${metric.id}`} className="scroll-mt-28 border-primary/20 bg-card/80 backdrop-blur-sm">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <CircleDot className="h-4 w-4 text-primary" />
              <CardTitle className="text-lg">{metric.label}</CardTitle>
              <MetricScorePill score={metric.score} />
              <IssueCountPill issues={metric.issues_count} />
            </div>
            <p className="text-sm text-muted-foreground">{metric.description}</p>
            <p className="text-sm text-foreground/90">{metric.summary}</p>
          </div>
          <Button variant="ghost" size="icon" onClick={() => setOpen((value) => !value)}>
            {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </Button>
        </div>
      </CardHeader>
      {open && (
        <CardContent className="space-y-4">
          {metric.issues.length > 0 ? (
            <div className="space-y-3">
              {metric.issues.map((issue) => (
                <div key={issue.issue_id} className={`rounded-2xl border p-4 ${severityStyles[issue.severity]}`}>
                  <div className="flex flex-wrap items-center gap-2">
                    {issue.severity === "success" ? (
                      <CheckCircle2 className="h-4 w-4" />
                    ) : (
                      <AlertTriangle className="h-4 w-4" />
                    )}
                    <p className="font-medium">{issue.message}</p>
                    <span className="text-xs uppercase tracking-[0.2em] opacity-80">
                      {issue.confidence_score}% confidence
                    </span>
                  </div>
                  <p className="mt-3 text-sm opacity-90">{issue.recommendation}</p>
                  {issue.excerpt && (
                    <details className="mt-3 rounded-xl border border-border/60 bg-background/40 p-3">
                      <summary className="cursor-pointer text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                        Issue excerpt
                      </summary>
                      <p className="mt-2 text-sm text-muted-foreground">{issue.excerpt}</p>
                    </details>
                  )}
                  {issue.affected_sections.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {issue.affected_sections.map((section) => (
                        <Button key={section} size="sm" variant="outline" onClick={() => onSectionSelect(section)}>
                          Discuss linked section
                        </Button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-2xl border border-emerald-500/30 bg-emerald-950/15 p-4 text-emerald-200">
              No issues found for this metric.
            </div>
          )}
          <div className="rounded-2xl border border-border/70 bg-muted/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">AI suggestions</p>
            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
              {metric.suggestions.map((suggestion) => (
                <li key={suggestion} className="flex gap-2">
                  <span className="text-primary">-</span>
                  <span>{suggestion}</span>
                </li>
              ))}
            </ul>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button size="sm" onClick={() => onAskAssistant(metric.id)}>
                Ask assistant about this metric
              </Button>
              <Button size="sm" variant="outline" onClick={() => onAskAssistant(metric.id)}>
                Strengthen this area
              </Button>
            </div>
          </div>
        </CardContent>
      )}
    </Card>
  );
}
