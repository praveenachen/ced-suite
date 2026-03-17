"use client";

import { BarChart3, ChevronRight } from "lucide-react";

import type { ProposalMetricCategory } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { OverallScoreCard } from "@/components/OverallScoreCard";
import { Button } from "@/components/ui/button";

export function ProposalScoreSidebar({
  overallScore,
  issueCount,
  categories,
  onMetricSelect,
}: {
  overallScore: number;
  issueCount: number;
  categories: ProposalMetricCategory[];
  onMetricSelect: (metricId: string) => void;
}) {
  const metricStatusClass = (issues: number) => {
    if (issues === 0) {
      return "border-emerald-500/30 bg-emerald-950/20 text-emerald-300";
    }
    if (issues <= 2) {
      return "border-amber-500/30 bg-amber-950/20 text-amber-300";
    }
    return "border-rose-500/30 bg-rose-950/20 text-rose-300";
  };

  return (
    <aside className="space-y-4 lg:sticky lg:top-24">
      <OverallScoreCard score={overallScore} issueCount={issueCount} />
      <Card className="border-primary/20 bg-card/80 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm uppercase tracking-[0.22em] text-muted-foreground">
            <BarChart3 className="h-4 w-4" />
            Score Breakdown
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {categories.map((category) => (
            <div key={category.id} className="space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">{category.label}</p>
                <span className="rounded-full border border-border bg-muted/30 px-2 py-0.5 text-xs font-medium text-foreground">
                  {category.score}%
                </span>
              </div>
              <div className="space-y-2">
                {category.metrics.map((metric) => (
                  <Button
                    key={metric.id}
                    variant="ghost"
                    className="h-auto w-full rounded-xl border border-border/70 bg-muted/20 px-3 py-3 text-left hover:bg-muted/40"
                    onClick={() => onMetricSelect(metric.id)}
                  >
                    <div className="grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-foreground">{metric.label}</p>
                        <p className="text-xs text-muted-foreground">
                          {metric.issues_count > 0 ? `${metric.issues_count} issues` : "No issues"}
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <span className="w-16 rounded-full border border-border px-2 py-0.5 text-center text-xs text-muted-foreground">
                          {metric.score}%
                        </span>
                        <span
                          className={`rounded-full border px-2 py-0.5 text-xs ${metricStatusClass(metric.issues_count)}`}
                        >
                          {metric.issues_count > 0 ? "Needs work" : "Healthy"}
                        </span>
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                      </div>
                    </div>
                  </Button>
                ))}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </aside>
  );
}
