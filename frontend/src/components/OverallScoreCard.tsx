"use client";

import { Card, CardContent, CardTitle } from "@/components/ui/card";

function OverallScoreGraph({ score }: { score: number }) {
  const clamped = Math.max(0, Math.min(100, score));
  const radius = 28;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference - (circumference * clamped) / 100;

  return (
    <div className="relative flex h-20 w-20 items-center justify-center rounded-full bg-background/30 shadow-[0_0_26px_rgba(34,211,238,0.16)]">
      <svg viewBox="0 0 80 80" className="h-20 w-20 -rotate-90">
        <circle cx="40" cy="40" r={radius} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="7" />
        <circle
          cx="40"
          cy="40"
          r={radius}
          fill="none"
          stroke="#22d3ee"
          strokeWidth="7"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
        />
      </svg>
      <span className="absolute text-sm font-semibold text-foreground">{clamped}%</span>
    </div>
  );
}

export function OverallScoreCard({
  score,
  issueCount,
}: {
  score: number;
  issueCount: number;
}) {
  const clamped = Math.max(0, Math.min(100, score));

  return (
    <Card className="border-primary/30 bg-card/80 backdrop-blur-sm">
      <CardContent className="grid min-h-[220px] grid-cols-[minmax(0,1fr)_auto] items-center gap-4 p-5">
        <div className="min-w-0 space-y-3">
          <CardTitle className="text-2xl">Overall Score</CardTitle>
          <p className="text-3xl font-semibold leading-none text-foreground">
            {clamped}
            <span className="text-xl text-muted-foreground">/100</span>
          </p>
          <p className={issueCount > 0 ? "text-sm font-medium text-rose-300" : "text-sm font-medium text-emerald-300"}>
            {issueCount} issues found
          </p>
        </div>
        <OverallScoreGraph score={clamped} />
      </CardContent>
    </Card>
  );
}
