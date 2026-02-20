"use client";

import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { Requirements } from "@/lib/api";
import { ArrowLeft, ArrowRight, FileText } from "lucide-react";

export function ProposalSections({
  requirements,
  onNext,
  onBack,
}: {
  requirements: Requirements;
  onNext: () => void;
  onBack: () => void;
}) {
  const sections = requirements.sections || [];
  const count = sections.length;

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
          <div className="space-y-4">
            {sections.map((sec, i) => (
              <div
                key={sec.key}
                className="flex gap-4 rounded-lg border border-border bg-card p-4"
              >
                <div className="h-full w-1 shrink-0 rounded-full bg-primary" />
                <div className="min-w-0 flex-1">
                  <h3 className="font-semibold text-foreground">{sec.title}</h3>
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
                  <FileText className="h-5 w-5 text-muted-foreground" />
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
