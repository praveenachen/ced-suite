"use client";

import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import Link from "next/link";
import {
  type CommunityProfile,
  type Draft,
  type DraftSection,
  type Requirements,
  type RewriteReference,
  type ValidationResult,
  rewriteSection,
  validateDraft,
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
  validation: ValidationResult | null;
  requirements: Requirements;
  profile: CommunityProfile;
  onContinueToExport: (sections: DraftSection[]) => void;
}) {
  const sections = draft.sections || [];
  const [liveValidation, setLiveValidation] = useState<ValidationResult | null>(validation);
  const gaps = liveValidation?.gaps ?? [];
  const warnings = liveValidation?.warnings ?? [];

  const [sectionStates, setSectionStates] = useState<Record<string, SectionEditorState>>({});
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [sectionError, setSectionError] = useState<string>("");
  const [isValidating, setIsValidating] = useState(false);

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
        body: (sectionStates[sec.key]?.working || enhanced[sec.key] || sec.body || "").trim(),
      })),
    [sections, sectionStates, enhanced]
  );

  const buildFinalSections = (): DraftSection[] => finalSections;

  useEffect(() => {
    const hasInitializedStates = sections.length > 0 && Object.keys(sectionStates).length > 0;
    if (!hasInitializedStates) return;

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setIsValidating(true);
      try {
        const next = await validateDraft(
          {
            ...draft,
            sections: finalSections,
          },
          requirements
        );
        if (!cancelled) {
          setLiveValidation(next);
        }
      } catch {
        // Keep last known validation state if refresh fails.
      } finally {
        if (!cancelled) {
          setIsValidating(false);
        }
      }
    }, 600);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [draft, finalSections, requirements, sections.length, sectionStates]);

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
        next[k] = { ...next[k], isOpen: k === key ? !next[k].isOpen : next[k].isOpen };
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

          return (
            <Card key={sec.key}>
              <CardHeader>
                <button
                  type="button"
                  className="flex w-full items-center justify-between text-left"
                  onClick={() => toggleOpen(sec.key)}
                >
                  <CardTitle className="text-base">{sec.title}</CardTitle>
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
                </CardContent>
              )}
            </Card>
          );
        })}
      </div>

      <div className="grid gap-6 sm:grid-cols-2">
        <Card className={gaps.length > 0 ? "border-amber-500/50" : "border-green-500/30"}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              {gaps.length > 0 ? (
                <AlertTriangle className="h-4 w-4 text-amber-600" />
              ) : (
                <Check className="h-4 w-4 text-green-600" />
              )}
              Compliance gaps
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isValidating && (
              <p className="mb-2 text-xs text-muted-foreground">Refreshing checks...</p>
            )}
            {gaps.length > 0 ? (
              <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
                {gaps.map((g, i) => (
                  <li key={i}>{g}</li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-green-700 dark:text-green-400">No major gaps detected.</p>
            )}
          </CardContent>
        </Card>

        <Card className={warnings.length > 0 ? "border-amber-500/50" : "border-green-500/30"}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              {warnings.length > 0 ? (
                <AlertTriangle className="h-4 w-4 text-amber-600" />
              ) : (
                <Check className="h-4 w-4 text-green-600" />
              )}
              Warnings
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isValidating && (
              <p className="mb-2 text-xs text-muted-foreground">Refreshing checks...</p>
            )}
            {warnings.length > 0 ? (
              <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
                {warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-green-700 dark:text-green-400">No warnings.</p>
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
