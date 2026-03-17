"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, CheckCircle2, Download, FileSpreadsheet, FileText, Loader2, RefreshCcw, Save, Sparkles } from "lucide-react";

import { OverallScoreCard } from "@/components/OverallScoreCard";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import type { ProposalAnalysis, ProposalAnalysisSection } from "@/lib/api";
import { exportDraftDocx, exportDraftPdf, getProposalAnalysis, reanalyzeProposal, rewriteProposalSection } from "@/lib/api";

const categoryStyles: Record<string, string> = {
  content: "border-cyan-500/25 bg-cyan-950/10",
  sections: "border-sky-500/25 bg-sky-950/10",
  funding_fit: "border-amber-500/25 bg-amber-950/10",
  indigenous_governance_ethics: "border-emerald-500/25 bg-emerald-950/10",
};

const graphStyles: Record<string, { stroke: string; glow: string }> = {
  content: { stroke: "#22d3ee", glow: "shadow-[0_0_26px_rgba(34,211,238,0.16)]" },
  sections: { stroke: "#60a5fa", glow: "shadow-[0_0_26px_rgba(96,165,250,0.16)]" },
  funding_fit: { stroke: "#f59e0b", glow: "shadow-[0_0_26px_rgba(245,158,11,0.16)]" },
  indigenous_governance_ethics: { stroke: "#10b981", glow: "shadow-[0_0_26px_rgba(16,185,129,0.16)]" },
};

function CategoryScoreGraph({ score, categoryId }: { score: number; categoryId: string }) {
  const clamped = Math.max(0, Math.min(100, score));
  const radius = 28;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference - (circumference * clamped) / 100;
  const style = graphStyles[categoryId] || graphStyles.content;

  return (
    <div className={`relative flex h-20 w-20 items-center justify-center rounded-full bg-background/40 ${style.glow}`}>
      <svg viewBox="0 0 80 80" className="h-20 w-20 -rotate-90">
        <circle cx="40" cy="40" r={radius} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="7" />
        <circle
          cx="40"
          cy="40"
          r={radius}
          fill="none"
          stroke={style.stroke}
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

function sanitizeSnippet(snippet?: string | null) {
  if (!snippet) return null;
  return snippet.replace(/\s+/g, " ").trim().slice(0, 160);
}

function highlightText(text: string, snippets: string[]) {
  let nodes: ReactNode[] = [text];
  let matched = false;

  for (const snippet of snippets) {
    if (!snippet || snippet.length < 18) continue;
    nodes = nodes.flatMap((node, index) => {
      if (typeof node !== "string") return [node];
      const foundAt = node.toLowerCase().indexOf(snippet.toLowerCase());
      if (foundAt === -1) return [node];
      matched = true;
      const before = node.slice(0, foundAt);
      const match = node.slice(foundAt, foundAt + snippet.length);
      const after = node.slice(foundAt + snippet.length);
      return [
        before,
        <mark
          key={`mark-${index}-${foundAt}`}
          className="rounded bg-rose-200/80 px-1 py-0.5 text-slate-900 shadow-[0_0_0_1px_rgba(244,63,94,0.12)]"
        >
          {match}
        </mark>,
        after,
      ];
    });
  }

  return { nodes, matched };
}

function paragraphMatchesAnchor(paragraph: string, anchor: string) {
  const normalizedParagraph = paragraph.replace(/\s+/g, " ").toLowerCase();
  const normalizedAnchor = anchor.replace(/\s+/g, " ").toLowerCase();
  return normalizedParagraph.includes(normalizedAnchor) || normalizedAnchor.includes(normalizedParagraph.slice(0, 120));
}

type EditorReviewState =
  | "idle"
  | "draft_updated"
  | "resolved"
  | "improved"
  | "unchanged"
  | "worsened";

type EditorReviewSnapshot = {
  metricId: string;
  sectionKey: string;
  issueId?: string | null;
  confidenceScore: number;
  issuesCount: number;
};

export default function ImproveDraftPage({ params }: { params: { proposalId: string } }) {
  const proposalId = params.proposalId;
  const queryClient = useQueryClient();
  const sectionRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const [sections, setSections] = useState<ProposalAnalysisSection[]>([]);
  const [selectedMetricId, setSelectedMetricId] = useState<string | null>(null);
  const [selectedIssueId, setSelectedIssueId] = useState<string | null>(null);
  const [selectedSectionKey, setSelectedSectionKey] = useState<string | null>(null);
  const [editorText, setEditorText] = useState("");
  const [editorPrompt, setEditorPrompt] = useState("");
  const [rewritePreview, setRewritePreview] = useState("");
  const [editorReviewState, setEditorReviewState] = useState<EditorReviewState>("idle");
  const [editorReviewSnapshot, setEditorReviewSnapshot] = useState<EditorReviewSnapshot | null>(null);

  const analysisQuery = useQuery({
    queryKey: ["proposal-analysis", proposalId],
    queryFn: () => getProposalAnalysis(proposalId),
  });

  const analysis = analysisQuery.data;

  useEffect(() => {
    if (!analysis) return;
    setSections(analysis.sections);
    const firstFlaggedMetric =
      analysis.categories.flatMap((category) => category.metrics).find((metric) => metric.issues_count > 0) ||
      analysis.categories[0]?.metrics[0];
    setSelectedMetricId((current) => current || firstFlaggedMetric?.id || null);
    const firstActionableIssue =
      firstFlaggedMetric?.issues.find((issue) => issue.anchor_type === "text" || issue.anchor_type === "paragraph") ||
      null;
    setSelectedIssueId((current) => current || firstActionableIssue?.issue_id || null);
    setSelectedSectionKey(
      (current) => current || firstActionableIssue?.section_key || analysis.sections[0]?.key || null
    );
  }, [analysis]);

  const allMetrics = useMemo(
    () => analysis?.categories.flatMap((category) => category.metrics) || [],
    [analysis]
  );

  const sortedMetrics = useMemo(
    () =>
      [...allMetrics].sort((left, right) => {
        if (right.issues_count !== left.issues_count) return right.issues_count - left.issues_count;
        if (left.score !== right.score) return left.score - right.score;
        return left.label.localeCompare(right.label);
      }),
    [allMetrics]
  );

  const actionableMetrics = useMemo(
    () =>
      sortedMetrics.filter((metric) =>
        metric.issues.some((issue) => issue.anchor_type === "text" || issue.anchor_type === "paragraph")
      ),
    [sortedMetrics]
  );

  const generalMetrics = useMemo(
    () =>
      sortedMetrics.filter(
        (metric) =>
          metric.issues_count > 0 &&
          !metric.issues.some((issue) => issue.anchor_type === "text" || issue.anchor_type === "paragraph")
      ),
    [sortedMetrics]
  );

  const selectedMetric = useMemo(
    () => allMetrics.find((metric) => metric.id === selectedMetricId) || null,
    [allMetrics, selectedMetricId]
  );

  const selectedMetricActionableIssues = useMemo(
    () =>
      selectedMetric?.issues.filter((issue) => issue.anchor_type === "text" || issue.anchor_type === "paragraph") ||
      [],
    [selectedMetric]
  );

  const selectedSection = useMemo(
    () => sections.find((section) => section.key === selectedSectionKey) || null,
    [sections, selectedSectionKey]
  );

  const workingAnalysis: ProposalAnalysis | null = useMemo(
    () => (analysis ? { ...analysis, sections } : null),
    [analysis, sections]
  );

  const reanalyzeMutation = useMutation({
    mutationFn: (nextSections: ProposalAnalysisSection[]) =>
      reanalyzeProposal({ proposal_id: proposalId, sections: nextSections }),
    onSuccess: (result) => {
      queryClient.setQueryData(["proposal-analysis", proposalId], result);
      setSections(result.sections);
      if (editorReviewSnapshot) {
        const updatedMetric = result.categories
          .flatMap((category) => category.metrics)
          .find((metric) => metric.id === editorReviewSnapshot.metricId);
        const updatedIssue =
          updatedMetric?.issues.find(
            (issue) =>
              issue.section_key === editorReviewSnapshot.sectionKey &&
              (!editorReviewSnapshot.issueId || issue.issue_id === editorReviewSnapshot.issueId)
          ) ||
          updatedMetric?.issues.find((issue) => issue.section_key === editorReviewSnapshot.sectionKey) ||
          null;
        if (!updatedIssue) {
          setEditorReviewState("resolved");
        } else {
          const confidenceDelta = updatedIssue.confidence_score - editorReviewSnapshot.confidenceScore;
          const issueCountDelta = (updatedMetric?.issues_count || 0) - editorReviewSnapshot.issuesCount;
          if (confidenceDelta <= -8 || issueCountDelta < 0) {
            setEditorReviewState("improved");
          } else if (confidenceDelta >= 8 || issueCountDelta > 0) {
            setEditorReviewState("worsened");
          } else {
            setEditorReviewState("unchanged");
          }
        }
      } else {
        setEditorReviewState("idle");
      }
    },
  });

  const rewriteMutation = useMutation({
    mutationFn: async () => {
      if (!selectedSection) throw new Error("Select a section first.");
      return rewriteProposalSection({
        proposal_id: proposalId,
        section_key: selectedSection.key,
        metric_id: selectedMetric?.id,
        issue_id: selectedActionableIssue?.issue_id,
        issue_message: selectedActionableIssue?.message,
        issue_recommendation: selectedActionableIssue?.recommendation,
        instruction: editorPrompt.trim() || `Revise this section to address ${selectedMetric?.label || "the flagged issues"}.`,
      });
    },
    onSuccess: (result) => {
      setRewritePreview(result.rewritten_text);
    },
  });

  const metricCount =
    analysis?.categories.reduce((total, category) => total + category.metrics.length, 0) || 0;
  const selectedActionableIssue = useMemo(
    () => {
      if (!selectedMetricActionableIssues.length) return null;
      return (
        selectedMetricActionableIssues.find((issue) => issue.issue_id === selectedIssueId) ||
        selectedMetricActionableIssues[0]
      );
    },
    [selectedIssueId, selectedMetricActionableIssues]
  );
  const selectedMetricIsActionable = Boolean(selectedActionableIssue);
  const selectedAnchorLabel =
    selectedActionableIssue?.anchor_type === "text"
      ? "Highlighted text"
      : selectedActionableIssue?.anchor_type === "paragraph"
        ? "Highlighted paragraph"
        : "Linked section";

  useEffect(() => {
    setEditorText(selectedSection?.body || "");
    setRewritePreview("");
    setEditorPrompt(
      selectedActionableIssue?.recommendation ||
        (selectedMetric ? `Strengthen this section for ${selectedMetric.label.toLowerCase()}.` : "")
    );
    setEditorReviewState("idle");
    setEditorReviewSnapshot(null);
  }, [selectedActionableIssue?.recommendation, selectedSection?.key, selectedMetric?.id, selectedIssueId]);

  const focusIssueContext = (metricId: string, issueId?: string | null) => {
    const metric = allMetrics.find((item) => item.id === metricId);
    const actionableIssues =
      metric?.issues.filter((issue) => issue.anchor_type === "text" || issue.anchor_type === "paragraph") || [];
    const targetIssue =
      actionableIssues.find((issue) => issue.issue_id === issueId) ||
      actionableIssues[0] ||
      null;
    setSelectedMetricId(metricId);
    setSelectedIssueId(targetIssue?.issue_id || null);
    const linkedSection = targetIssue?.section_key || null;
    if (linkedSection) {
      setSelectedSectionKey(linkedSection);
      window.setTimeout(() => {
        sectionRefs.current[linkedSection]?.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 80);
    } else {
      setSelectedSectionKey(null);
    }
  };

  const openMetricContext = (metricId: string) => {
    focusIssueContext(metricId);
  };

  const downloadReport = () => {
    if (!workingAnalysis) return;
    const blob = new Blob([JSON.stringify(workingAnalysis, null, 2)], { type: "application/json" });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${workingAnalysis.analysis.file_name.replace(/\.[^.]+$/, "")}_analysis.json`;
    link.click();
    window.URL.revokeObjectURL(url);
  };

  const updateSectionBody = (sectionKey: string, nextBody: string) => {
    setSections((current) =>
      current.map((section) =>
        section.key === sectionKey ? { ...section, body: nextBody } : section
      )
    );
    setEditorReviewState("draft_updated");
  };

  const rerunAnalysis = (nextSections: ProposalAnalysisSection[] = sections) => {
    if (selectedMetric && selectedSectionKey) {
      setEditorReviewSnapshot({
        metricId: selectedMetric.id,
        sectionKey: selectedSectionKey,
        issueId: selectedActionableIssue?.issue_id || null,
        confidenceScore: selectedActionableIssue?.confidence_score || 0,
        issuesCount: selectedMetric.issues_count,
      });
    } else {
      setEditorReviewSnapshot(null);
    }
    reanalyzeMutation.mutate(nextSections);
  };

  const exportImprovedDraft = async (format: "pdf" | "docx") => {
    if (!workingAnalysis) return;
    const payload = {
      grant_name: workingAnalysis.analysis.file_name,
      community_name: "",
      region: "",
      local_priority: "",
      sections: sections.map((section) => ({ key: section.key, title: section.title, body: section.body })),
    };
    const blob = format === "pdf" ? await exportDraftPdf(payload) : await exportDraftDocx(payload);
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${workingAnalysis.analysis.file_name.replace(/\.[^.]+$/, "")}_improved.${format}`;
    link.click();
    window.URL.revokeObjectURL(url);
  };

  const applyEditorText = () => {
    if (!selectedSection) return;
    updateSectionBody(selectedSection.key, editorText);
  };

  const applyRewritePreview = () => {
    if (!rewritePreview || !selectedSectionKey) return;
    setEditorText(rewritePreview);
    updateSectionBody(selectedSectionKey, rewritePreview);
    setRewritePreview("");
  };

  if (analysisQuery.isLoading) {
    return (
      <div className="min-h-screen">
        <header className="border-b border-border bg-card/80 backdrop-blur-sm">
          <div className="container mx-auto flex h-14 items-center justify-between px-4">
            <Link href="/" className="flex items-center gap-2 text-muted-foreground hover:text-foreground">
              <ArrowLeft className="h-4 w-4" />
              Home
            </Link>
            <ThemeToggle />
          </div>
        </header>
        <main className="container mx-auto max-w-5xl px-4 py-12">
          <Card className="border-primary/20 bg-card/80">
            <CardContent className="flex min-h-[320px] items-center justify-center">
              <div className="flex items-center gap-3 text-muted-foreground">
                <Loader2 className="h-5 w-5 animate-spin text-primary" />
                Parsing and analyzing your uploaded draft...
              </div>
            </CardContent>
          </Card>
        </main>
      </div>
    );
  }

  if (analysisQuery.isError || !analysis || !workingAnalysis) {
    return (
      <div className="min-h-screen">
        <header className="border-b border-border bg-card/80 backdrop-blur-sm">
          <div className="container mx-auto flex h-14 items-center justify-between px-4">
            <Link href="/" className="flex items-center gap-2 text-muted-foreground hover:text-foreground">
              <ArrowLeft className="h-4 w-4" />
              Home
            </Link>
            <ThemeToggle />
          </div>
        </header>
        <main className="container mx-auto max-w-4xl px-4 py-12">
          <Card className="border-destructive/30 bg-destructive/10">
            <CardHeader>
              <CardTitle>Could not load this proposal analysis</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm text-muted-foreground">
              <p>{analysisQuery.error instanceof Error ? analysisQuery.error.message : "Unknown error."}</p>
              <div className="flex gap-3">
                <Button onClick={() => analysisQuery.refetch()}>Try again</Button>
                <Link href="/">
                  <Button variant="outline">Back to home</Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-border bg-card/90 backdrop-blur-sm">
        <div className="container mx-auto flex h-14 items-center justify-between px-4">
          <Link href="/" className="flex items-center gap-2 text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" />
            Home
          </Link>
          <div className="text-sm text-muted-foreground">Improve Existing Draft</div>
          <ThemeToggle />
        </div>
      </header>
      <main className="container mx-auto max-w-[1600px] px-4 py-8">
        <div className="space-y-6">
          <Card className="border-primary/20 bg-card/80 backdrop-blur-sm">
            <CardHeader className="gap-4">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="space-y-2">
                  <CardTitle className="text-2xl">Improve Existing Draft</CardTitle>
                  <p className="max-w-3xl text-sm text-muted-foreground">{workingAnalysis.report_summary}</p>
                  <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                    <span className="rounded-full border border-border px-3 py-1">
                      {workingAnalysis.analysis.file_name}
                    </span>
                    <span className="rounded-full border border-border px-3 py-1 uppercase">
                      {workingAnalysis.analysis.file_type}
                    </span>
                    <span className="rounded-full border border-border px-3 py-1">
                      Last analyzed {new Date(workingAnalysis.analysis.last_analyzed_at).toLocaleString()}
                    </span>
                    <span className="rounded-full border border-border px-3 py-1">{sections.length} sections</span>
                    <span className="rounded-full border border-border px-3 py-1">{metricCount} metrics</span>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    onClick={() => rerunAnalysis()}
                    disabled={reanalyzeMutation.isPending}
                  >
                    {reanalyzeMutation.isPending ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Re-running
                      </>
                    ) : (
                      <>
                        <RefreshCcw className="mr-2 h-4 w-4" />
                        Re-run analysis
                      </>
                    )}
                  </Button>
                  <Button variant="outline" onClick={() => exportImprovedDraft("pdf")}>
                    <FileText className="mr-2 h-4 w-4" />
                    Export PDF
                  </Button>
                  <Button variant="outline" onClick={() => exportImprovedDraft("docx")}>
                    <FileSpreadsheet className="mr-2 h-4 w-4" />
                    Export DOCX
                  </Button>
                  <Button onClick={downloadReport}>
                    <Download className="mr-2 h-4 w-4" />
                    Download report
                  </Button>
                </div>
              </div>
            </CardHeader>
          </Card>

          <div className="grid gap-4 xl:grid-cols-[repeat(5,minmax(0,1fr))]">
            <OverallScoreCard score={workingAnalysis.overall_score} issueCount={workingAnalysis.issue_count} />
            {workingAnalysis.categories.map((category) => (
              <Card key={category.id} className={categoryStyles[category.id] || "border-primary/20 bg-card/80"}>
                <CardContent className="grid min-h-[220px] grid-cols-[minmax(0,1fr)_auto] items-center gap-4 p-5">
                  <div className="min-w-0 space-y-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                      {category.label}
                    </p>
                    <p className="text-3xl font-semibold leading-none text-foreground">{category.score}%</p>
                    <div className="space-y-1 text-sm">
                      <p
                        className={
                          category.issues > 0 ? "font-medium text-rose-300" : "font-medium text-emerald-300"
                        }
                      >
                        {category.issues} issues
                      </p>
                      <p className="text-muted-foreground">{category.metrics.length} metrics</p>
                    </div>
                  </div>
                  <CategoryScoreGraph score={category.score} categoryId={category.id} />
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_380px]">
            <section className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                    Proposal Preview
                  </p>
                  <h2 className="mt-1 text-3xl font-semibold text-foreground">Document Preview</h2>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {workingAnalysis.extraction.preview_mode === "continuous"
                      ? "Showing continuous extracted text because section parsing confidence is low."
                      : "Showing structured extracted sections from the uploaded draft."}
                  </p>
                </div>
                {selectedSection && (
                  <span className="rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs text-primary">
                    Selected section: {selectedSection.title}
                  </span>
                )}
              </div>

              <Card className="border-primary/20 bg-card/70 backdrop-blur-sm">
                <CardContent className="flex flex-wrap gap-3 p-4 text-sm text-muted-foreground">
                  <span className="rounded-full border border-border px-3 py-1 text-foreground/90">
                    Extraction confidence: {workingAnalysis.extraction.confidence}
                  </span>
                  <span className="rounded-full border border-border px-3 py-1 text-muted-foreground">
                    Extractor: {workingAnalysis.extraction.extractor}
                  </span>
                  <span className="rounded-full border border-cyan-500/25 bg-cyan-950/15 px-3 py-1 text-cyan-200">
                    Metric = the review category being scored
                  </span>
                  <span className="rounded-full border border-primary/25 bg-primary/10 px-3 py-1 text-primary">
                    Issue = a specific problem found inside that metric
                  </span>
                  <span className="rounded-full border border-amber-500/25 bg-amber-950/15 px-3 py-1 text-amber-200">
                    Section warnings = structural issues inside a section
                  </span>
                  <span className="rounded-full border border-rose-500/25 bg-rose-950/15 px-3 py-1 text-rose-200">
                    Metric findings = scoring flags tied to a review metric
                  </span>
                  {selectedMetric ? (
                    <span className="rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-primary">
                      Selected metric: {selectedMetric.label} ({selectedMetric.issues_count} findings)
                    </span>
                  ) : null}
                </CardContent>
              </Card>

              {workingAnalysis.extraction.warnings.length > 0 ? (
                <Card className="border-amber-500/30 bg-amber-950/10">
                  <CardContent className="space-y-2 p-4 text-sm text-amber-100">
                    <p className="font-medium">Extraction quality notes</p>
                    <ul className="space-y-1 text-amber-200/90">
                      {workingAnalysis.extraction.warnings.map((warning) => (
                        <li key={warning}>{warning}</li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              ) : null}

              <Card className="border-primary/20 bg-card/60 backdrop-blur-sm">
                <CardContent className="p-4">
                  <div className="max-h-[78vh] overflow-y-auto rounded-[28px] border border-border/60 bg-background/20 p-2">
                    <div className="mx-auto max-w-5xl rounded-[28px] border border-stone-200 bg-stone-50 px-16 py-16 shadow-[0_24px_60px_rgba(15,23,42,0.32)]">
                    {workingAnalysis.extraction.preview_mode === "continuous" ? (
                      <div className="scroll-mt-28">
                        <div className="rounded-2xl bg-cyan-100/55 px-5 py-4">
                          <h3 className="text-[28px] font-semibold tracking-tight text-slate-900">Continuous Extracted Draft</h3>
                        </div>
                        <div className="mt-6 space-y-5 text-[18px] leading-9 text-slate-800">
                          {(workingAnalysis.raw_preview_text || "No extracted text available.")
                            .split(/\n{2,}/)
                            .filter((paragraph) => paragraph.trim())
                            .map((paragraph, paragraphIndex) => (
                              <p key={`continuous-${paragraphIndex}`}>{paragraph}</p>
                            ))}
                        </div>
                      </div>
                    ) : sections.map((section, index) => {
                      const isActive = section.key === selectedSectionKey;
                      const sectionIssues =
                        selectedMetricIsActionable && selectedMetric && selectedMetric.linked_sections.includes(section.key)
                          ? selectedMetric.issues
                              .filter((issue) => issue.section_key === section.key)
                          : [];
                      const textAnchors = sectionIssues
                        .filter((issue) => issue.anchor_type === "text")
                        .map((issue) => sanitizeSnippet(issue.anchor_text || issue.excerpt))
                        .filter((item): item is string => Boolean(item));
                      const paragraphAnchors = sectionIssues
                        .filter((issue) => issue.anchor_type === "paragraph")
                        .map((issue) => sanitizeSnippet(issue.anchor_text || issue.anchor_hint || issue.excerpt))
                        .filter((item): item is string => Boolean(item));
                      return (
                        <div
                          key={section.key}
                          ref={(node) => {
                            sectionRefs.current[section.key] = node;
                          }}
                          className={`scroll-mt-28 ${index > 0 ? "mt-14 pt-12" : ""}`}
                        >
                          <div className={isActive ? "rounded-2xl bg-cyan-100/55 px-5 py-4" : ""}>
                            <h3 className="text-[28px] font-semibold tracking-tight text-slate-900">{section.title}</h3>
                            {section.word_limit ? (
                              <div className="mt-3 flex flex-wrap gap-2">
                                <span className="rounded-full border border-slate-300 bg-white px-3 py-1 text-xs text-slate-700">
                                  Word limit: {section.word_limit} words
                                </span>
                              </div>
                            ) : null}
                            {(section.compliance_gaps.length > 0 || section.warnings.length > 0) && (
                              <div className="mt-3 flex flex-wrap gap-2">
                                {section.compliance_gaps.length > 0 && (
                                  <span className="rounded-full border border-rose-300 bg-rose-100 px-3 py-1 text-xs text-rose-700">
                                    {section.compliance_gaps.length} compliance gaps
                                  </span>
                                )}
                                {section.warnings.length > 0 && (
                                  <>
                                    <span className="rounded-full border border-amber-300 bg-amber-100 px-3 py-1 text-xs text-amber-700">
                                      {section.warnings.length} section warnings
                                    </span>
                                    {section.warnings
                                      .filter((warning) =>
                                        warning.type === "word_limit_exceeded" || warning.type === "below_expected_word_limit"
                                      )
                                      .map((warning, warningIndex) => (
                                        <span
                                          key={`${section.key}-word-limit-${warningIndex}`}
                                          className="rounded-full border border-amber-300 bg-amber-50 px-3 py-1 text-xs text-amber-700"
                                        >
                                          {warning.message}
                                        </span>
                                      ))}
                                  </>
                                )}
                              </div>
                            )}
                          </div>

                          {selectedMetricIsActionable &&
                            selectedMetric &&
                            selectedMetric.linked_sections.includes(section.key) &&
                            selectedMetric.issues.length > 0 && (
                              <div className="mt-5 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900">
                                <p className="font-semibold">Flagged for {selectedMetric.label}</p>
                                <ul className="mt-2 space-y-1">
                                  {sectionIssues.slice(0, 2).map((issue) => (
                                    <li key={issue.issue_id}>{issue.message}</li>
                                  ))}
                                </ul>
                              </div>
                            )}

                          <div className="mt-6 space-y-5 text-[18px] leading-9 text-slate-800">
                            {(section.body || "No extracted text available for this section.")
                              .split(/\n{2,}/)
                              .filter((paragraph) => paragraph.trim())
                              .map((paragraph, paragraphIndex) => {
                                const highlighted = highlightText(paragraph, textAnchors);
                                const paragraphHighlight = paragraphAnchors.some((anchor) =>
                                  paragraphMatchesAnchor(paragraph, anchor)
                                );
                                const fallbackHighlight =
                                  sectionIssues.some((issue) => issue.anchor_type === "section") &&
                                  paragraphIndex === 0 &&
                                  !highlighted.matched &&
                                  !paragraphHighlight;
                                return (
                                  <p
                                    key={`${section.key}-${paragraphIndex}`}
                                    className={
                                      paragraphHighlight || fallbackHighlight
                                        ? "rounded-lg bg-rose-100/80 px-2 py-1 shadow-[0_0_0_1px_rgba(244,63,94,0.12)]"
                                        : undefined
                                    }
                                  >
                                    {highlighted.nodes}
                                  </p>
                                );
                              })}
                          </div>
                        </div>
                      );
                    })}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </section>

            <aside className="space-y-4 xl:sticky xl:top-24 xl:self-start">
              <Card className="border-primary/20 bg-card/80 backdrop-blur-sm">
                <CardHeader>
                  <CardTitle className="text-base">Metric Review</CardTitle>
                </CardHeader>
                <CardContent className="max-h-[68vh] space-y-4 overflow-y-auto pr-1">
                  {actionableMetrics.length > 0 ? (
                    <div className="space-y-3">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">
                        Actionable linked findings
                      </p>
                      {actionableMetrics.map((metric) => {
                        const isActive = metric.id === selectedMetricId;
                        const linkedLabel = metric.linked_sections[0]
                          ? sections.find((section) => section.key === metric.linked_sections[0])?.title
                          : null;
                        return (
                          <button
                            key={metric.id}
                            type="button"
                            onClick={() => openMetricContext(metric.id)}
                            className={`w-full rounded-2xl border p-4 text-left transition-colors ${
                              isActive
                                ? "border-primary/50 bg-primary/10"
                                : "border-rose-500/25 bg-rose-950/10 hover:bg-rose-950/20"
                            }`}
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="text-sm font-semibold text-foreground">{metric.label}</p>
                              <MetricScorePill score={metric.score} />
                            </div>
                            <div className="mt-2 flex flex-wrap items-center gap-2">
                              <span className="rounded-full border border-rose-500/30 bg-rose-950/20 px-2 py-0.5 text-[11px] text-rose-300">
                                {metric.issues_count} metric findings
                              </span>
                              {linkedLabel && (
                                <span className="rounded-full border border-border px-2 py-0.5 text-[11px] text-muted-foreground">
                                  linked: {linkedLabel}
                                </span>
                              )}
                            </div>
                            <p className="mt-3 line-clamp-3 text-xs text-muted-foreground">{metric.summary}</p>
                            {isActive ? (
                              <div className="mt-4 space-y-3 rounded-2xl border border-primary/20 bg-background/30 p-4">
                                <div className="flex flex-wrap gap-2">
                                  <MetricScorePill score={metric.score} />
                                  <span className="rounded-full border border-rose-500/30 bg-rose-950/20 px-3 py-1 text-xs text-rose-300">
                                    {metric.issues_count} metric findings
                                  </span>
                                  {selectedSection ? (
                                    <span className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground">
                                      linked section: {selectedSection.title}
                                    </span>
                                  ) : null}
                                </div>
                                <div className="rounded-2xl border border-primary/20 bg-card/40 p-4">
                                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">
                                    Why this was flagged
                                  </p>
                                  <p className="mt-3 text-sm leading-6 text-muted-foreground">{metric.description}</p>
                                  <p className="mt-3 text-sm leading-6 text-foreground/90">
                                    {metric.issues[0]
                                      ? `${metric.issues[0].message} ${metric.issues[0].recommendation}`
                                      : metric.summary}
                                  </p>
                                </div>
                                {metric.issues.length > 0 ? (
                                  <div className="space-y-3">
                                    {metric.issues.map((issue) => {
                                      const issueLinkedTitle =
                                        sections.find((section) => section.key === issue.section_key)?.title || "Linked section";
                                      const issueIsActionable =
                                        issue.anchor_type === "text" || issue.anchor_type === "paragraph";
                                      const issueIsActive = selectedIssueId === issue.issue_id;
                                      return (
                                        <button
                                          key={issue.issue_id}
                                          type="button"
                                          onClick={(event) => {
                                            event.stopPropagation();
                                            if (issueIsActionable) {
                                              focusIssueContext(metric.id, issue.issue_id);
                                            }
                                          }}
                                          className={`w-full rounded-2xl border p-4 text-left ${
                                            issueIsActive
                                              ? "border-primary/40 bg-primary/10"
                                              : "border-rose-500/25 bg-rose-950/10"
                                          } ${issueIsActionable ? "transition-colors hover:bg-rose-950/20" : "cursor-default"}`}
                                        >
                                          <div className="flex flex-wrap items-center justify-between gap-2">
                                            <span className="rounded-full border border-rose-500/30 bg-rose-950/20 px-2 py-0.5 text-[11px] text-rose-300">
                                              {issueLinkedTitle}
                                            </span>
                                            <span className="text-xs text-rose-200">{issue.confidence_score}% confidence</span>
                                          </div>
                                          <p className="mt-3 text-sm font-medium text-rose-100">{issue.message}</p>
                                          <p className="mt-2 text-[11px] uppercase tracking-[0.16em] text-rose-300/80">
                                            {issue.anchor_type === "text"
                                              ? "text-linked finding"
                                              : issue.anchor_type === "paragraph"
                                                ? "paragraph-linked finding"
                                                : "general section signal"}
                                          </p>
                                          <p className="mt-2 text-xs text-rose-200/80">{issue.recommendation}</p>
                                          {issueIsActionable ? (
                                            <p className="mt-3 text-[11px] font-semibold uppercase tracking-[0.16em] text-primary">
                                              {issueIsActive ? "Editing this flagged section" : "Click to focus and edit this section"}
                                            </p>
                                          ) : null}
                                        </button>
                                      );
                                    })}
                                  </div>
                                ) : null}
                              </div>
                            ) : null}
                          </button>
                        );
                      })}
                    </div>
                  ) : null}

                  {generalMetrics.length > 0 ? (
                    <div className="space-y-3">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                        General review signals
                      </p>
                      {generalMetrics.map((metric) => {
                        const isActive = metric.id === selectedMetricId;
                        return (
                          <button
                            key={metric.id}
                            type="button"
                            onClick={() => openMetricContext(metric.id)}
                            className={`w-full rounded-2xl border p-4 text-left transition-colors ${
                              isActive
                                ? "border-primary/40 bg-primary/10"
                                : "border-border/70 bg-background/20 hover:bg-background/35"
                            }`}
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="text-sm font-semibold text-foreground">{metric.label}</p>
                              <MetricScorePill score={metric.score} />
                            </div>
                            <div className="mt-2 flex flex-wrap items-center gap-2">
                              <span className="rounded-full border border-amber-500/30 bg-amber-950/20 px-2 py-0.5 text-[11px] text-amber-300">
                                {metric.issues_count} general signals
                              </span>
                            </div>
                            <p className="mt-3 line-clamp-3 text-xs text-muted-foreground">{metric.summary}</p>
                            {isActive ? (
                              <div className="mt-4 space-y-3 rounded-2xl border border-primary/20 bg-background/30 p-4">
                                <div className="flex flex-wrap gap-2">
                                  <MetricScorePill score={metric.score} />
                                  <span className="rounded-full border border-amber-500/30 bg-amber-950/20 px-3 py-1 text-xs text-amber-300">
                                    {metric.issues_count} general signals
                                  </span>
                                  <span className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground">
                                    general signal
                                  </span>
                                </div>
                                <div className="rounded-2xl border border-primary/20 bg-card/40 p-4">
                                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">
                                    Why this was flagged
                                  </p>
                                  <p className="mt-3 text-sm leading-6 text-muted-foreground">{metric.description}</p>
                                  <p className="mt-3 text-sm leading-6 text-foreground/90">
                                    {metric.issues[0]
                                      ? `${metric.issues[0].message} ${metric.issues[0].recommendation}`
                                      : metric.summary}
                                  </p>
                                </div>
                              </div>
                            ) : null}
                          </button>
                        );
                      })}
                    </div>
                  ) : null}
                </CardContent>
              </Card>

              {selectedMetricIsActionable && selectedSection ? (
                <Card className="border-primary/30 bg-card/90 backdrop-blur-sm">
                  <CardHeader>
                    <CardTitle className="text-base">Section Editor</CardTitle>
                    <p className="text-sm text-muted-foreground">
                      This editor updates the full section body shown in the preview. The highlighted area shows where the current finding is anchored.
                    </p>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="rounded-2xl border border-primary/20 bg-primary/10 p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-semibold text-foreground">Editing section: {selectedSection.title}</p>
                        <span className="rounded-full border border-border bg-background/40 px-3 py-1 text-xs text-muted-foreground">
                          {selectedAnchorLabel}
                        </span>
                      </div>
                      <div className="mt-3 space-y-2 text-sm">
                        <p className="text-muted-foreground">
                          Current finding: <span className="font-medium text-foreground">{selectedActionableIssue?.message}</span>
                        </p>
                        {selectedActionableIssue?.recommendation ? (
                          <p className="text-muted-foreground">
                            Suggested direction: {selectedActionableIssue.recommendation}
                          </p>
                        ) : null}
                        {selectedMetricActionableIssues.length > 1 ? (
                          <p className="text-muted-foreground">
                            This metric currently flags {selectedMetricActionableIssues.length} sections. Select a different issue card above to switch the editor focus.
                          </p>
                        ) : null}
                      </div>
                    </div>

                    {editorReviewState === "draft_updated" ? (
                      <div className="flex items-start gap-3 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm">
                        <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-300" />
                        <div className="space-y-1">
                          <p className="font-medium text-amber-100">Draft updated, analysis not refreshed yet.</p>
                          <p className="text-amber-200/80">
                            The preview now shows your latest section text. Re-run analysis to confirm whether this finding is resolved.
                          </p>
                        </div>
                      </div>
                    ) : null}

                    {editorReviewState === "resolved" ? (
                      <div className="flex items-start gap-3 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm">
                        <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-300" />
                        <div className="space-y-1">
                          <p className="font-medium text-emerald-100">Finding resolved after re-check.</p>
                          <p className="text-emerald-200/80">
                            The latest analysis no longer flags this metric issue for the selected section.
                          </p>
                        </div>
                      </div>
                    ) : null}

                    {editorReviewState === "improved" ? (
                      <div className="flex items-start gap-3 rounded-2xl border border-sky-500/30 bg-sky-500/10 p-4 text-sm">
                        <CheckCircle2 className="mt-0.5 h-4 w-4 text-sky-300" />
                        <div className="space-y-1">
                          <p className="font-medium text-sky-100">Improved, but still flagged after re-check.</p>
                          <p className="text-sky-200/80">
                            The finding still appears, but the signal weakened from about {editorReviewSnapshot?.confidenceScore ?? 0}% to {selectedActionableIssue?.confidence_score ?? 0}% confidence.
                          </p>
                        </div>
                      </div>
                    ) : null}

                    {editorReviewState === "unchanged" ? (
                      <div className="flex items-start gap-3 rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm">
                        <AlertTriangle className="mt-0.5 h-4 w-4 text-rose-300" />
                        <div className="space-y-1">
                          <p className="font-medium text-rose-100">Still needs work after re-check.</p>
                          <p className="text-rose-200/80">
                            The updated draft was re-analyzed, but this finding remains at roughly the same strength for the selected section.
                          </p>
                        </div>
                      </div>
                    ) : null}

                    {editorReviewState === "worsened" ? (
                      <div className="flex items-start gap-3 rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm">
                        <AlertTriangle className="mt-0.5 h-4 w-4 text-rose-300" />
                        <div className="space-y-1">
                          <p className="font-medium text-rose-100">The finding strengthened after re-check.</p>
                          <p className="text-rose-200/80">
                            The issue is still present and now reads stronger, moving from about {editorReviewSnapshot?.confidenceScore ?? 0}% to {selectedActionableIssue?.confidence_score ?? 0}% confidence.
                          </p>
                        </div>
                      </div>
                    ) : null}

                    <Textarea
                      value={editorText}
                      onChange={(event) => setEditorText(event.target.value)}
                      rows={12}
                      className="bg-background/60"
                    />
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" variant="secondary" onClick={applyEditorText}>
                        <Save className="mr-2 h-4 w-4" />
                        Apply changes to draft
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => rerunAnalysis()}
                        disabled={reanalyzeMutation.isPending}
                        className="bg-emerald-600 text-white hover:bg-emerald-500"
                      >
                        <RefreshCcw className="mr-2 h-4 w-4" />
                        {reanalyzeMutation.isPending ? "Re-checking" : "Re-check analysis"}
                      </Button>
                    </div>

                    <div className="rounded-2xl border border-border/70 bg-background/30 p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                        AI rewrite action
                      </p>
                      <Textarea
                        value={editorPrompt}
                        onChange={(event) => setEditorPrompt(event.target.value)}
                        rows={3}
                        className="mt-3 bg-background/60"
                        placeholder="Describe how to improve this section."
                      />
                      <Button
                        className="mt-3"
                        onClick={() => rewriteMutation.mutate()}
                        disabled={rewriteMutation.isPending}
                      >
                        {rewriteMutation.isPending ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Generating rewrite
                          </>
                        ) : (
                          <>
                            <Sparkles className="mr-2 h-4 w-4" />
                            Generate AI suggestion
                          </>
                        )}
                      </Button>
                    </div>

                    {rewritePreview ? (
                      <div className="rounded-2xl border border-primary/25 bg-primary/10 p-4">
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">
                          Suggested rewrite preview
                        </p>
                        <p className="mt-3 max-h-64 overflow-y-auto whitespace-pre-wrap text-sm text-foreground">
                          {rewritePreview}
                        </p>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <Button size="sm" onClick={applyRewritePreview}>
                            Apply suggestion to draft
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => setRewritePreview("")}>
                            Discard
                          </Button>
                        </div>
                      </div>
                    ) : null}
                  </CardContent>
                </Card>
              ) : null}
            </aside>
          </div>

          {workingAnalysis.additional_submission_requirements.length > 0 ? (
            <Card className="border-primary/20 bg-card/80 backdrop-blur-sm">
              <CardHeader>
                <CardTitle className="text-base">Additional Submission Requirements</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2 text-sm text-muted-foreground">
                  {workingAnalysis.additional_submission_requirements.map((item) => (
                    <li key={item} className="rounded-xl border border-border/70 bg-background/20 px-4 py-3">
                      {item}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ) : null}
        </div>
      </main>
    </div>
  );
}
