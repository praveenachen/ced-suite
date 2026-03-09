"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft,
  FileUp,
  FileText,
  Check,
  Loader2,
  Upload,
  AlertCircle,
  Download,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useMutation } from "@tanstack/react-query";
import {
  parseGrant,
  generateDraft,
  enhanceDraft,
  validateDraft,
  type Requirements,
  type CommunityProfile,
  type Draft,
  type DraftSection,
  type ValidationResult,
  exportDraftPdf,
} from "@/lib/api";
import { CommunityForm } from "@/components/CommunityForm";
import { ProposalSections } from "@/components/ProposalSections";
import { ReportView } from "@/components/ReportView";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "@/components/ThemeToggle";

const STEPS = [
  { id: 1, label: "Upload grant package" },
  { id: 2, label: "Review sections" },
  { id: 3, label: "Community info" },
  { id: 4, label: "Generate report" },
  { id: 5, label: "Export draft" },
];

export default function ProposalPage() {
  const [step, setStep] = useState(1);
  const [grantFile, setGrantFile] = useState<File | null>(null);
  const [requirements, setRequirements] = useState<Requirements | null>(null);
  const [profile, setProfile] = useState<CommunityProfile | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [enhanced, setEnhanced] = useState<Record<string, string> | null>(null);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [finalSections, setFinalSections] = useState<DraftSection[]>([]);
  const [exportError, setExportError] = useState<string>("");

  const exportMutation = useMutation({
    mutationFn: async () => {
      if (!profile || !requirements || finalSections.length === 0) {
        throw new Error("No finalized draft content to export.");
      }
      return exportDraftPdf({
        grant_name: requirements.grant_name || "",
        community_name: profile.community_name || "",
        region: profile.region || "",
        local_priority: profile.local_priority || "",
        requested_budget: profile.requested_budget,
        sections: finalSections.map((s) => ({
          key: s.key,
          title: s.title,
          body: s.body,
        })),
      });
    },
    onSuccess: (blob) => {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "grant_proposal.pdf";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      setExportError("");
    },
    onError: (err) => {
      setExportError(err instanceof Error ? err.message : "Export failed.");
    },
  });

  const parseMutation = useMutation({
    mutationFn: (file: File) => parseGrant(file),
    onSuccess: (data) => {
      setRequirements(data.requirements);
      setStep(2);
    },
  });

  const generateMutation = useMutation({
    mutationFn: async ({
      profile: p,
      requirements: r,
      budget,
    }: {
      profile: CommunityProfile;
      requirements: Requirements;
      budget: number;
    }) => {
      const d = await generateDraft(p, r, budget);
      const { enhanced: enh } = await enhanceDraft(d, r, p);
      const val = await validateDraft(d, r);
      return { draft: d, enhanced: enh, validation: val };
    },
    onSuccess: (data) => {
      setDraft(data.draft);
      setEnhanced(data.enhanced);
      setValidation(data.validation);
      setStep(4);
    },
  });

  const handleFileDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (file && /\.(pdf|docx|txt)$/i.test(file.name)) {
        setGrantFile(file);
        parseMutation.mutate(file);
      }
    },
    [parseMutation]
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        setGrantFile(file);
        parseMutation.mutate(file);
      }
    },
    [parseMutation]
  );

  const handleGenerate = useCallback(
    (formProfile: CommunityProfile & { requested_budget: number }) => {
      if (!requirements) return;
      setProfile(formProfile);
      generateMutation.mutate({
        profile: { ...formProfile, requested_budget: formProfile.requested_budget },
        requirements,
        budget: formProfile.requested_budget,
      });
    },
    [requirements, generateMutation]
  );

  const handleSectionTitleChange = useCallback(
    (sectionKey: string, title: string) => {
      setRequirements((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          sections: (prev.sections || []).map((s) =>
            s.key === sectionKey ? { ...s, title } : s
          ),
        };
      });
    },
    []
  );

  const handleSectionDelete = useCallback((sectionKey: string) => {
    setRequirements((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        sections: (prev.sections || []).filter((s) => s.key !== sectionKey),
      };
    });
  }, []);

  const handleSectionAdd = useCallback(() => {
    setRequirements((prev) => {
      if (!prev) return prev;
      const sections = prev.sections || [];
      let idx = sections.length + 1;
      let key = `custom_section_${idx}`;
      const existing = new Set(sections.map((s) => s.key));
      while (existing.has(key)) {
        idx += 1;
        key = `custom_section_${idx}`;
      }
      return {
        ...prev,
        sections: [
          ...sections,
          {
            key,
            title: `Custom Section ${idx}`,
            guidance: "",
          },
        ],
      };
    });
  }, []);

  const progressPct = step === 5 ? 100 : ((step - 1) / 4) * 100;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-border bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/80">
        <div className="container mx-auto flex h-14 items-center gap-4 px-4">
          <Link href="/" className="flex items-center gap-2 text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" />
            Home
          </Link>
          <div className="flex-1">
            <h1 className="font-semibold text-foreground">Grant Proposal Builder</h1>
            {grantFile && (
              <p className="text-xs text-muted-foreground">
                Improving: {grantFile.name}
              </p>
            )}
          </div>
          <ThemeToggle />
        </div>
        {/* Stepper */}
        <div className="border-t border-border bg-muted/30 px-4 py-3">
          <div className="container mx-auto flex items-center gap-2">
            {STEPS.map((s, i) => (
              <div key={s.id} className="flex items-center gap-2">
                <div
                  className={cn(
                    "flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium",
                    step > s.id
                      ? "bg-primary text-primary-foreground"
                      : step === s.id
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-muted-foreground"
                  )}
                >
                  {step > s.id ? <Check className="h-4 w-4" /> : s.id}
                </div>
                <span
                  className={cn(
                    "text-sm font-medium",
                    step >= s.id ? "text-foreground" : "text-muted-foreground"
                  )}
                >
                  {s.label}
                </span>
                {i < STEPS.length - 1 && (
                  <div
                    className={cn(
                      "mx-1 h-0.5 w-6 rounded",
                      step > s.id ? "bg-primary" : "bg-muted"
                    )}
                  />
                )}
              </div>
            ))}
            <span className="ml-auto text-sm text-muted-foreground">
              {Math.round(progressPct)}% Complete
            </span>
          </div>
        </div>
      </header>

      <main className="container mx-auto max-w-4xl px-4 py-8">
        <AnimatePresence mode="wait">
          {/* Step 1: Upload */}
          {step === 1 && (
            <motion.div
              key="step1"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="space-y-6"
            >
              <Card className="border-2">
                <CardHeader>
                  <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/10">
                    <Upload className="h-7 w-7 text-primary" />
                  </div>
                  <CardTitle>Upload grant application package</CardTitle>
                  <CardDescription>
                    Upload the grant posting (PDF, DOCX, or TXT). We&apos;ll extract key
                    sections and requirements so the AI can align your proposal.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={handleFileDrop}
                    className="flex min-h-[200px] flex-col items-center justify-center rounded-xl border-2 border-dashed border-muted-foreground/40 bg-muted/20 p-8 transition-colors hover:border-primary/50 hover:bg-muted/30"
                  >
                    {parseMutation.isPending ? (
                      <Loader2 className="h-12 w-12 animate-spin text-primary" />
                    ) : (
                      <>
                        <FileUp className="mb-4 h-12 w-12 text-muted-foreground" />
                        <p className="mb-2 font-medium text-foreground">
                          Drag & drop your grant posting here
                        </p>
                        <p className="mb-4 text-sm text-muted-foreground">
                          or click to browse (PDF, DOCX, TXT)
                        </p>
                        <input
                          type="file"
                          accept=".pdf,.docx,.txt"
                          onChange={handleFileSelect}
                          className="hidden"
                          id="grant-upload"
                        />
                        <Button
                          variant="secondary"
                          onClick={() => document.getElementById("grant-upload")?.click()}
                        >
                          <FileText className="mr-2 h-4 w-4" />
                          Choose File
                        </Button>
                      </>
                    )}
                  </div>
                  {parseMutation.isError && (
                    <div className="mt-4 flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
                      <AlertCircle className="h-4 w-4 shrink-0" />
                      {parseMutation.error.message}
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card className="border-l-4 border-l-blue-500 bg-blue-50/50 dark:bg-blue-950/20">
                <CardHeader>
                  <CardTitle className="text-base">Community context (optional)</CardTitle>
                  <CardDescription>
                    You can upload community plans and funding guidelines during the process
                    to get tailored recommendations.
                  </CardDescription>
                </CardHeader>
              </Card>
            </motion.div>
          )}

          {/* Step 2: Sections */}
          {step === 2 && requirements && (
            <motion.div
              key="step2"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
            >
              <ProposalSections
                requirements={requirements}
                onNext={() => setStep(3)}
                onBack={() => setStep(1)}
                onSectionTitleChange={handleSectionTitleChange}
                onSectionDelete={handleSectionDelete}
                onSectionAdd={handleSectionAdd}
              />
            </motion.div>
          )}

          {/* Step 3: Community form */}
          {step === 3 && requirements && (
            <motion.div
              key="step3"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
            >
              <CommunityForm
                onSubmit={handleGenerate}
                isSubmitting={generateMutation.isPending}
                error={generateMutation.error?.message}
                onBack={() => setStep(2)}
              />
            </motion.div>
          )}

          {/* Step 4: Report */}
          {step === 4 && draft && requirements && profile && (
            <motion.div
              key="step4"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
            >
              <ReportView
                draft={draft}
                enhanced={enhanced || {}}
                validation={validation}
                requirements={requirements}
                profile={profile}
                onContinueToExport={(sections) => {
                  setFinalSections(sections);
                  setStep(5);
                }}
              />
            </motion.div>
          )}

          {/* Step 5: Export */}
          {step === 5 && profile && requirements && (
            <motion.div
              key="step5"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="space-y-6"
            >
              <Card>
                <CardHeader>
                  <CardTitle>Final export</CardTitle>
                  <CardDescription>
                    Download a polished PDF version of your proposal. You can go back to the
                    editor if you want to make more section changes first.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="rounded-lg border border-border bg-muted/20 p-4 text-sm text-muted-foreground">
                    <p>
                      Document: <span className="font-medium text-foreground">{requirements.grant_name || "Grant Proposal"}</span>
                    </p>
                    <p>
                      Community: <span className="font-medium text-foreground">{profile.community_name || "N/A"}</span>
                    </p>
                    <p>
                      Sections: <span className="font-medium text-foreground">{finalSections.length}</span>
                    </p>
                  </div>

                  {exportError && (
                    <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
                      <AlertCircle className="h-4 w-4 shrink-0" />
                      {exportError}
                    </div>
                  )}

                  <div className="flex flex-wrap gap-3">
                    <Button variant="outline" onClick={() => setStep(4)} disabled={exportMutation.isPending}>
                      Back to editor
                    </Button>
                    <Button onClick={() => exportMutation.mutate()} disabled={exportMutation.isPending || finalSections.length === 0}>
                      {exportMutation.isPending ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Preparing PDF...
                        </>
                      ) : (
                        <>
                          <Download className="mr-2 h-4 w-4" />
                          Download PDF
                        </>
                      )}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  );
}
