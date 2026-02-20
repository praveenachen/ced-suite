"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { CommunityProfile } from "@/lib/api";
import { AlertCircle, Loader2 } from "lucide-react";

const schema = z.object({
  community_name: z.string().min(1, "Community name is required"),
  region: z.string().min(1, "Region / Province is required"),
  local_priority: z.string().min(1, "Local priority is required"),
  timeline: z.string().optional(),
  challenges: z.string().optional(),
  strengths: z.string().optional(),
  partners: z.string().optional(),
  requested_budget: z.coerce.number().min(10000).max(5_000_000),
});

export type CommunityFormValues = z.infer<typeof schema>;

export function CommunityForm({
  onSubmit,
  isSubmitting,
  error,
  onBack,
}: {
  onSubmit: (values: CommunityProfile & { requested_budget: number }) => void;
  isSubmitting: boolean;
  error?: string;
  onBack: () => void;
}) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<CommunityFormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      community_name: "",
      region: "",
      local_priority: "",
      timeline: "",
      challenges: "",
      strengths: "",
      partners: "",
      requested_budget: 250000,
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Community & project info</CardTitle>
        <CardDescription>
          Enter key community information so the AI can tailor the proposal to your context.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form
          onSubmit={handleSubmit((values) => {
            onSubmit({
              ...values,
              evidence_note: "",
              indicators_before: undefined,
              indicators_after: undefined,
              scenario: undefined,
            });
          })}
          className="space-y-6"
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="community_name">Community name *</Label>
              <Input
                id="community_name"
                {...register("community_name")}
                placeholder="e.g. Kinngait"
              />
              {errors.community_name && (
                <p className="text-sm text-destructive">{errors.community_name.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="region">Region / Province *</Label>
              <Input id="region" {...register("region")} placeholder="e.g. Nunavut" />
              {errors.region && (
                <p className="text-sm text-destructive">{errors.region.message}</p>
              )}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="local_priority">Local priority *</Label>
            <Input
              id="local_priority"
              {...register("local_priority")}
              placeholder="e.g. Water infrastructure"
            />
            {errors.local_priority && (
              <p className="text-sm text-destructive">{errors.local_priority.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="timeline">Timeline (optional)</Label>
            <Input id="timeline" {...register("timeline")} placeholder="e.g. Apr–Dec 2026" />
          </div>

          <div className="space-y-2">
            <Label htmlFor="requested_budget">Requested funding ($) *</Label>
            <Input
              id="requested_budget"
              type="number"
              {...register("requested_budget")}
              min={10000}
              max={5000000}
              step={5000}
            />
            {errors.requested_budget && (
              <p className="text-sm text-destructive">{errors.requested_budget.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="challenges">Key challenges (optional)</Label>
            <Textarea
              id="challenges"
              {...register("challenges")}
              rows={3}
              placeholder="Describe current challenges the grant would address."
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="strengths">Community strengths (optional)</Label>
            <Textarea
              id="strengths"
              {...register("strengths")}
              rows={2}
              placeholder="Assets, capacity, partnerships."
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="partners">Partners (optional)</Label>
            <Input
              id="partners"
              {...register("partners")}
              placeholder="Key partners and their roles"
            />
          </div>

          {error && (
            <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}

          <div className="flex gap-3">
            <Button type="button" variant="outline" onClick={onBack} disabled={isSubmitting}>
              Back
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Generating proposal…
                </>
              ) : (
                "Generate proposal"
              )}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
