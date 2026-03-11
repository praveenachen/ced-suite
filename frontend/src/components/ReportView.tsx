"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import Link from "next/link";
import {
  type CommunityProfile,
  type ComplianceGap,
  type ComplianceSummary,
  type ComplianceWarning,
  type Draft,
  type DraftSection,
  type Requirements,
  type RewriteReference,
  evaluateSectionCompliance,
  rewriteSection,
} from "@/lib/api";
import {
  Check,
  AlertTriangle,
  ArrowLeft,
  ChevronDown,
  ChevronUp,
  Sparkles,
  RotateCcw,
  Save,
  Loader2,
  ArrowRight,
  ExternalLink,
} from "lucide-react";

type SectionEditorState = {
  versions: string[];
  index: number;
  working: string;
  prompt: string;
  suggestion: string;
  references: RewriteReference[];
  isOpen: boolean;
};

export function ReportView({
  draft,
  enhanced,
  validation,
  requirements,
  profile,
  onContinueToExport,
}: {
  draft: Draft;
  enhanced: Record<string, string>;
  validation: ComplianceSummary | null;
  requirements: Requirements;
  profile: CommunityProfile;
  onContinueToExport: (sections: DraftSection[]) => void;
}) {
  const sections = draft.sections || [];
  const [liveValidation, setLiveValidation] = useState<ComplianceSummary | null>(validation);

  const [sectionStates, setSectionStates] = useState<Record<string, SectionEditorState>>({});
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [sectionError, setSectionError] = useState<string>("");
  const [isValidating, setIsValidating] = useState(false);
  const sectionRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const previousBodiesRef = useRef<Record<string, string>>({});

  useEffect(() => {
    const initial: Record<string, SectionEditorState> = {};
    for (const sec of sections) {
      const baseText = (enhanced[sec.key] || sec.body || "").trim();
      initial[sec.key] = {
        versions: [baseText],
        index: 0,
        working: baseText,
        prompt: "",
        suggestion: "",
        references: [],
        isOpen: false,
      };
    }
    if (sections[0]) {
      initial[sections[0].key].isOpen = true;
      setActiveKey(sections[0].key);
    }
    setSectionStates(initial);
  }, [sections, enhanced]);

  useEffect(() => {
    setLiveValidation(validation);
  }, [validation]);

  const summaryBudget = useMemo(() => draft.meta?.requested_budget?.toLocaleString(), [draft.meta]);

  const finalSections = useMemo(
    () =>
      sections.map((sec) => ({
        ...sec,
        body:
          (Object.prototype.hasOwnProperty.call(sectionStates, sec.key)
            ? sectionStates[sec.key]?.working
            : enhanced[sec.key] || sec.body || "")?.trim() || "",
      })),
    [sections, sectionStates, enhanced]
  );

  const sectionResults = useMemo(() => {
    const entries = mergeSectionResults(
      liveValidation?.sectionResults ?? [],
      buildImmediateSectionResults(finalSections)
    );
    return Object.fromEntries(entries.map((item) => [item.section, item]));
  }, [finalSections, liveValidation]);

  const warnings = useMemo(
    () =>
      Object.values(sectionResults).flatMap((result) =>
        result.warnings.map((warning) => ({
          ...warning,
          section: result.section,
          section_label: result.section_label,
        }))
      ),
    [sectionResults]
  );

  const gaps = useMemo(
    () =>
      Object.values(sectionResults).flatMap((result) =>
        result.compliance_gaps.map((gap) => ({
          ...gap,
          section: result.section,
          section_label: result.section_label,
        }))
      ),
    [sectionResults]
  );

  const groupedWarnings = useMemo(() => {
    return warnings.reduce<Record<string, typeof warnings>>((acc, warning) => {
      const label = warning.section_label || warning.section.replaceAll("_", " ");
      acc[label] = [...(acc[label] || []), warning];
      return acc;
    }, {});
  }, [warnings]);

  const groupedGaps = useMemo(() => {
    return gaps.reduce<Record<string, typeof gaps>>((acc, gap) => {
      const label = gap.section_label || gap.section.replaceAll("_", " ");
      acc[label] = [...(acc[label] || []), gap];
      return acc;
    }, {});
  }, [gaps]);

  const buildFinalSections = (): DraftSection[] => finalSections;

  const openSection = (key: string) => {
    setSectionStates((prev) => {
      const next = { ...prev };
      for (const k of Object.keys(next)) {
        next[k] = { ...next[k], isOpen: k === key };
      }
      return next;
    });
    setActiveKey(key);
  };

  const jumpToSection = (key: string) => {
    openSection(key);
    window.setTimeout(() => {
      sectionRefs.current[key]?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 120);
  };

  useEffect(() => {
    const hasInitializedStates = sections.length > 0 && Object.keys(sectionStates).length > 0;
    if (!hasInitializedStates) return;

    const currentBodies = Object.fromEntries(finalSections.map((section) => [section.key, section.body]));
    const changedSections = finalSections.filter(
      (section) => previousBodiesRef.current[section.key] !== section.body
    );
    if (changedSections.length === 0) return;

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setIsValidating(true);
      try {
        const nextResults = await Promise.all(
          changedSections.map(async (section) => {
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
        if (!cancelled) {
          setLiveValidation((prev) => {
            const merged = mergeSectionResults(prev?.sectionResults ?? [], nextResults);
            return {
              sectionResults: merged,
              warnings: merged.flatMap((result) =>
                result.warnings.map((warning) => ({
                  ...warning,
                  section: result.section,
                  section_label: result.section_label,
                }))
              ),
              complianceGaps: merged.flatMap((result) =>
                result.compliance_gaps.map((gap) => ({
                  ...gap,
                  section: result.section,
                  section_label: result.section_label,
                }))
              ),
            };
          });
          previousBodiesRef.current = currentBodies;
        }
      } catch {
        // Keep last known validation state if refresh fails.
      } finally {
        if (!cancelled) {
          setIsValidating(false);
        }
      }
    }, 250);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [finalSections, sections.length, sectionStates]);

  const setSectionState = (key: string, updater: (prev: SectionEditorState) => SectionEditorState) => {
    setSectionStates((prev) => {
      const current = prev[key];
      if (!current) return prev;
      return { ...prev, [key]: updater(current) };
    });
  };

  const toggleOpen = (key: string) => {
    setSectionStates((prev) => {
      const next = { ...prev };
      for (const k of Object.keys(next)) {
        next[k] = { ...next[k], isOpen: k === key ? !next[k].isOpen : false };
      }
      return next;
    });
    setActiveKey(key);
  };

  const saveManualEdit = (key: string) => {
    setSectionState(key, (s) => {
      const baseline = s.versions[s.index] || "";
      if (s.working.trim() === baseline.trim()) return s;
      const nextVersions = [...s.versions.slice(0, s.index + 1), s.working];
      return { ...s, versions: nextVersions, index: nextVersions.length - 1 };
    });
  };

  const undoEdit = (key: string) => {
    setSectionState(key, (s) => {
      if (s.index <= 0) return s;
      const nextIndex = s.index - 1;
      return { ...s, index: nextIndex, working: s.versions[nextIndex] || "" };
    });
  };

  const resetWorking = (key: string) => {
    setSectionState(key, (s) => ({ ...s, working: s.versions[s.index] || "" }));
  };

  const applySuggestion = (key: string) => {
    setSectionState(key, (s) => {
      if (!s.suggestion.trim()) return s;
      const nextVersions = [...s.versions.slice(0, s.index + 1), s.suggestion.trim()];
      return {
        ...s,
        versions: nextVersions,
        index: nextVersions.length - 1,
        working: s.suggestion.trim(),
      };
    });
  };

  const generateSuggestion = async (key: string, title: string) => {
    const state = sectionStates[key];
    if (!state || !state.prompt.trim()) return;
    setSectionError("");
    setBusyKey(key);
    try {
      const out = await rewriteSection({
        section_key: key,
        section_title: title,
        current_text: state.working,
        instruction: state.prompt,
        requirements,
        profile,
      });
      setSectionState(key, (s) => ({
        ...s,
        suggestion: out.text || "",
        references: out.references || [],
      }));
    } catch (e) {
      setSectionError(e instanceof Error ? e.message : "Could not generate a section suggestion.");
    } finally {
      setBusyKey(null);
    }
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-8">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Your proposal draft</h2>
        <Link href="/">
          <Button variant="outline">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Home
          </Button>
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {draft.meta?.community_name} · {draft.meta?.grant_name} · ${summaryBudget}
          </p>
        </CardContent>
      </Card>

      <Card className="border-primary/40 bg-primary/5">
        <CardHeader>
          <CardTitle className="text-base">Section editor</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Open any section below to edit text directly, ask AI for targeted changes, then apply only what you want.
        </CardContent>
      </Card>

      <div className="space-y-4">
        {sections.map((sec) => {
          const state = sectionStates[sec.key];
          if (!state) return null;
          const isBusy = busyKey === sec.key;
          const versionCount = state.versions.length;
          const sectionResult = sectionResults[sec.key];
          const sectionWarnings = sectionResult?.warnings ?? [];
          const sectionGaps = sectionResult?.compliance_gaps ?? [];

          return (
            <Card
              key={sec.key}
              ref={(node) => {
                sectionRefs.current[sec.key] = node;
              }}
            >
              <CardHeader>
                <button
                  type="button"
                  className="flex w-full items-center justify-between text-left"
                  onClick={() => toggleOpen(sec.key)}
                >
                  <div className="flex items-center gap-3">
                    <CardTitle className="text-base">{sec.title}</CardTitle>
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={
                          sectionGaps.length > 0
                            ? "rounded-full border border-rose-500/40 bg-rose-950/20 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-rose-300"
                            : "rounded-full border border-emerald-500/30 bg-emerald-950/20 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-emerald-300"
                        }
                      >
                        {sectionGaps.length > 0 ? `${sectionGaps.length} gap${sectionGaps.length === 1 ? "" : "s"}` : "no gaps"}
                      </span>
                      <span
                        className={
                          sectionWarnings.length > 0
                            ? "rounded-full border border-amber-500/40 bg-amber-950/20 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-amber-300"
                            : "rounded-full border border-sky-500/30 bg-sky-950/20 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-sky-300"
                        }
                      >
                        {sectionWarnings.length > 0
                          ? `${sectionWarnings.length} warning${sectionWarnings.length === 1 ? "" : "s"}`
                          : "no warnings"}
                      </span>
                    </div>
                  </div>
                  {state.isOpen ? (
                    <ChevronUp className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                  )}
                </button>
              </CardHeader>
              {state.isOpen && (
                <CardContent className="space-y-4">
                  <div className="grid gap-4 lg:grid-cols-5">
                    <div className="space-y-3 lg:col-span-3">
                      <p className="text-xs text-muted-foreground">
                        Version {state.index + 1} of {versionCount}
                      </p>
                      <Textarea
                        value={state.working}
                        onChange={(e) =>
                          setSectionState(sec.key, (s) => ({ ...s, working: e.target.value }))
                        }
                        rows={14}
                      />
                      <div className="flex flex-wrap gap-2">
                        <Button size="sm" variant="secondary" onClick={() => saveManualEdit(sec.key)}>
                          <Save className="mr-2 h-4 w-4" />
                          Save manual edit
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => undoEdit(sec.key)} disabled={state.index === 0}>
                          <RotateCcw className="mr-2 h-4 w-4" />
                          Undo
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => resetWorking(sec.key)}>
                          Reset unsaved
                        </Button>
                      </div>
                    </div>

                    <div className="space-y-3 rounded-lg border border-border bg-muted/20 p-3 lg:col-span-2">
                      <p className="text-sm font-medium">AI section assistant</p>
                      <Textarea
                        value={state.prompt}
                        onChange={(e) =>
                          setSectionState(sec.key, (s) => ({ ...s, prompt: e.target.value }))
                        }
                        rows={4}
                        placeholder="Describe what to change in this section, for example: clarify community involvement and include project duration."
                      />
                      <Button
                        size="sm"
                        onClick={() => generateSuggestion(sec.key, sec.title)}
                        disabled={!state.prompt.trim() || isBusy}
                      >
                        {isBusy ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Generating
                          </>
                        ) : (
                          <>
                            <Sparkles className="mr-2 h-4 w-4" />
                            Generate suggestion
                          </>
                        )}
                      </Button>

                      {state.suggestion && (
                        <div className="space-y-2 rounded-md border border-border bg-card p-3">
                          <p className="text-xs font-medium text-muted-foreground">AI suggestion preview</p>
                          <p className="max-h-48 overflow-auto whitespace-pre-wrap text-sm">{state.suggestion}</p>
                          <Button size="sm" variant="secondary" onClick={() => applySuggestion(sec.key)}>
                            Apply suggestion
                          </Button>
                        </div>
                      )}

                      {state.references.length > 0 && (
                        <div className="space-y-2 rounded-md border border-border bg-card p-3">
                          <p className="text-xs font-medium text-muted-foreground">Source references</p>
                          <div className="max-h-56 space-y-2 overflow-auto">
                            {state.references.map((ref) => (
                              <div key={`${ref.source}-${ref.rank}`} className="rounded border border-border p-2">
                                <p className="text-xs font-medium">
                                  {ref.source}
                                  {typeof ref.chunk_index !== "undefined" ? ` (chunk ${ref.chunk_index})` : ""}
                                </p>
                                <p className="mt-1 text-xs text-muted-foreground">{ref.snippet}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {sectionError && activeKey === sec.key && (
                    <p className="text-sm text-destructive">{sectionError}</p>
                  )}

                  {(sectionWarnings.length > 0 || sectionGaps.length > 0) && (
                    <div className="grid gap-4 lg:grid-cols-2">
                      <div className="rounded-lg border border-amber-500/30 bg-amber-50/60 p-3 dark:bg-amber-950/20">
                        <p className="text-sm font-medium">Section compliance gaps</p>
                        {sectionGaps.length > 0 ? (
                          <ul className="mt-2 space-y-3 text-sm text-muted-foreground">
                            {sectionGaps.map((gap) => (
                              <li key={gap.failed_check_id}>
                                <p className="font-medium text-foreground">
                                  {gap.message}
                                  <span className="ml-2 text-xs uppercase tracking-wide text-amber-700 dark:text-amber-400">
                                    {gap.severity}
                                  </span>
                                  <span className="ml-2 text-xs uppercase tracking-wide text-sky-700 dark:text-sky-400">
                                    {gap.confidence_score}% confidence
                                  </span>
                                </p>
                                <p className="mt-1">{gap.recommendation}</p>
                                <details className="mt-2 rounded-md border border-border bg-card/40 p-2">
                                  <summary className="cursor-pointer text-xs font-medium text-muted-foreground">
                                    Source: {gap.source_document}
                                  </summary>
                                  <p className="mt-2 text-xs text-muted-foreground">{gap.source_excerpt}</p>
                                </details>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="mt-2 text-sm text-muted-foreground">No compliance gaps for this section.</p>
                        )}
                      </div>

                      <div className="rounded-lg border border-amber-500/30 bg-amber-50/60 p-3 dark:bg-amber-950/20">
                        <p className="text-sm font-medium">Section warnings</p>
                        {sectionWarnings.length > 0 ? (
                          <ul className="mt-2 space-y-2 text-sm text-muted-foreground">
                            {sectionWarnings.map((warning, index) => (
                              <li key={`${warning.type}-${index}`}>
                                <span className="font-medium text-foreground">{warning.message}</span>
                                <span className="ml-2 text-xs uppercase tracking-wide text-muted-foreground/80">
                                  {warning.type.replaceAll("_", " ")}
                                </span>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="mt-2 text-sm text-muted-foreground">No warnings for this section.</p>
                        )}
                      </div>
                    </div>
                  )}
                </CardContent>
              )}
            </Card>
          );
        })}
      </div>

      <div className="grid gap-6 sm:grid-cols-2">
        <Card
          className={
            gaps.length > 0
              ? "border-rose-500/50 bg-rose-950/10"
              : "border-emerald-500/30 bg-emerald-950/10"
          }
        >
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              {gaps.length > 0 ? (
                <AlertTriangle className="h-4 w-4 text-rose-400" />
              ) : (
                <Check className="h-4 w-4 text-emerald-400" />
              )}
              Report-wide compliance gaps
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              Aggregated from all proposal sections.
            </p>
          </CardHeader>
          <CardContent>
            {isValidating && (
              <p className="mb-2 text-xs text-muted-foreground">Refreshing checks...</p>
            )}
            {gaps.length > 0 ? (
              <div className="space-y-4 text-sm text-muted-foreground">
                {Object.entries(groupedGaps).map(([sectionLabel, sectionGaps]) => (
                  <div key={sectionLabel} className="rounded-md border border-rose-500/20 bg-rose-950/10 p-3">
                    <p className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-rose-200/80">
                      {sectionLabel}
                    </p>
                    <ul className="space-y-3">
                      {sectionGaps.map((gap) => (
                        <li key={`${gap.section}-${gap.failed_check_id}`}>
                          <p className="font-medium text-foreground">
                            {gap.message}
                            <span className="ml-2 text-xs uppercase tracking-wide text-rose-300">
                              {gap.severity}
                            </span>
                            <span className="ml-2 text-xs uppercase tracking-wide text-cyan-300">
                              {gap.confidence_score}% confidence
                            </span>
                          </p>
                          <p className="mt-2">{gap.recommendation}</p>
                          <div className="mt-3">
                            <Button
                              size="sm"
                              variant="outline"
                              className="border-rose-500/30 bg-transparent text-rose-200 hover:bg-rose-950/30"
                              onClick={() => jumpToSection(gap.section)}
                            >
                              Open section
                              <ExternalLink className="ml-2 h-3.5 w-3.5" />
                            </Button>
                          </div>
                          <details
                            className="mt-2 rounded-md border border-rose-500/20 bg-rose-950/10 p-2"
                          >
                            <summary className="cursor-pointer text-xs font-medium text-muted-foreground">
                              Source: {gap.source_document}
                            </summary>
                            <p className="mt-2 text-xs text-muted-foreground">{gap.source_excerpt}</p>
                          </details>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-emerald-300">No major gaps detected.</p>
            )}
          </CardContent>
        </Card>

        <Card
          className={
            warnings.length > 0
              ? "border-amber-500/50 bg-amber-950/10"
              : "border-sky-500/30 bg-sky-950/10"
          }
        >
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              {warnings.length > 0 ? (
                <AlertTriangle className="h-4 w-4 text-amber-400" />
              ) : (
                <Check className="h-4 w-4 text-sky-400" />
              )}
              Report-wide warnings
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              Aggregated from all proposal sections.
            </p>
          </CardHeader>
          <CardContent>
            {isValidating && (
              <p className="mb-2 text-xs text-muted-foreground">Refreshing checks...</p>
            )}
            {warnings.length > 0 ? (
              <div className="space-y-4 text-sm text-muted-foreground">
                {Object.entries(groupedWarnings).map(([sectionLabel, sectionWarnings]) => (
                  <div key={sectionLabel} className="rounded-md border border-amber-500/20 bg-amber-950/10 p-3">
                    <p className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-amber-200/80">
                      {sectionLabel}
                    </p>
                    <ul className="space-y-3">
                      {sectionWarnings.map((warning, index) => (
                        <li key={`${warning.section}-${warning.type}-${index}`}>
                          <p className="font-medium text-foreground">{warning.message}</p>
                          <p className="mt-1 text-xs uppercase tracking-wide text-muted-foreground/80">
                            {warning.type.replaceAll("_", " ")}
                          </p>
                          <div className="mt-3">
                            <Button
                              size="sm"
                              variant="outline"
                              className="border-amber-500/30 bg-transparent text-amber-200 hover:bg-amber-950/30"
                              onClick={() => jumpToSection(warning.section)}
                            >
                              Open section
                              <ExternalLink className="ml-2 h-3.5 w-3.5" />
                            </Button>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-sky-300">No warnings.</p>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="flex justify-end">
        <Button onClick={() => onContinueToExport(buildFinalSections())}>
          Continue to export
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </motion.div>
  );
}

function buildImmediateSectionResults(sections: DraftSection[]) {
  return sections
    .map((section) => {
      const warnings: ComplianceWarning[] = [];
      if (section.body === "") {
        warnings.push({ type: "empty_section", message: "This section is empty." });
      } else if (section.body.trim() === "") {
        warnings.push({ type: "whitespace_only_section", message: "This section contains only whitespace." });
      }

      return {
        section: section.key,
        section_label: section.title || section.key,
        warnings,
        compliance_gaps: [] as ComplianceGap[],
        scoring_hooks: undefined,
      };
    })
    .filter((section) => section.warnings.length > 0);
}

function mergeSectionResults(base: ComplianceSummary["sectionResults"], overrides: ComplianceSummary["sectionResults"]) {
  const merged = new Map<string, ComplianceSummary["sectionResults"][number]>();

  for (const result of base) {
    merged.set(result.section, result);
  }

  for (const result of overrides) {
    const current = merged.get(result.section);
    if (!current) {
      merged.set(result.section, result);
      continue;
    }

    merged.set(result.section, {
      ...current,
      ...result,
      warnings: dedupeWarnings([...(current.warnings || []), ...(result.warnings || [])]),
      compliance_gaps: result.compliance_gaps.length > 0 ? result.compliance_gaps : current.compliance_gaps,
      scoring_hooks: result.scoring_hooks || current.scoring_hooks,
    });
  }

  return Array.from(merged.values());
}

function dedupeWarnings(warnings: ComplianceWarning[]) {
  const seen = new Set<string>();
  return warnings.filter((warning) => {
    const key = `${warning.type}:${warning.message}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
