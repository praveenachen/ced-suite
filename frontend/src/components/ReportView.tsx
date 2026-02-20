"use client";

import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import type { Draft, Requirements, ValidationResult } from "@/lib/api";
import { Check, AlertTriangle, ArrowLeft } from "lucide-react";

export function ReportView({
  draft,
  enhanced,
  validation,
  requirements,
}: {
  draft: Draft;
  enhanced: Record<string, string>;
  validation: ValidationResult | null;
  requirements: Requirements;
}) {
  const sections = draft.sections || [];
  const gaps = validation?.gaps ?? [];
  const warnings = validation?.warnings ?? [];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-8"
    >
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
            {draft.meta?.community_name} · {draft.meta?.grant_name} · $
            {draft.meta?.requested_budget?.toLocaleString()}
          </p>
        </CardContent>
      </Card>

      <div className="space-y-6">
        {sections.map((sec) => {
          const body = enhanced[sec.key] || sec.body;
          return (
            <Card key={sec.key}>
              <CardHeader>
                <CardTitle className="text-base">{sec.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="whitespace-pre-wrap text-sm text-foreground">{body}</div>
              </CardContent>
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
    </motion.div>
  );
}
