"use client";

import { motion } from "framer-motion";
import {
  ArrowUpFromLine,
  MessageCircle,
  Check,
  FileUp,
  Sparkles,
  ArrowRight,
  Database,
  Cpu,
} from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ThemeToggle } from "@/components/ThemeToggle";

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08 },
  },
};

const item = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0 },
};

export default function HomePage() {
  return (
    <div className="relative min-h-screen overflow-hidden">
      {/* Header */}
      <header className="relative z-10 border-b border-border bg-card/80 backdrop-blur-sm">
        <div className="container mx-auto flex h-14 items-center justify-between px-4">
          <span className="font-semibold text-foreground">Community Grant Assistant</span>
          <ThemeToggle showLabel />
        </div>
      </header>

      <main className="relative z-10 container mx-auto max-w-5xl px-4 py-12">
        <motion.div
          variants={container}
          initial={false}
          animate="show"
          className="flex flex-col items-center text-center"
        >
          {/* Logo / branding */}
          <motion.div
            variants={item}
            className="mb-6 flex h-16 w-16 items-center justify-center rounded-xl border-2 border-primary bg-primary/10"
          >
            <Sparkles className="h-8 w-8 text-primary" />
          </motion.div>
          <motion.h1 variants={item} className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            Community Grant Assistant
          </motion.h1>
          <motion.h2
            variants={item}
            className="mt-3 max-w-4xl bg-gradient-to-r from-fuchsia-500 via-cyan-400 to-blue-500 bg-clip-text text-4xl font-semibold tracking-tight text-transparent sm:text-6xl"
          >
            Funding-Ready Proposals, Faster
          </motion.h2>
          <motion.p variants={item} className="mt-2 max-w-xl text-muted-foreground">
            AI-powered grant proposal builder for communities. Get expert guidance through
            interactive workflows and intelligent document analysis.
          </motion.p>
          <motion.div
            variants={item}
            className="mt-4 inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary"
          >
            <Sparkles className="h-4 w-4" />
            Powered by RAG and GPT-5 mini
          </motion.div>
        </motion.div>
        <div className="mx-auto mt-10 h-px w-full max-w-4xl bg-gradient-to-r from-fuchsia-500/0 via-cyan-400/80 to-blue-500/0" />

        {/* Two main cards */}
        <motion.div
          variants={container}
          initial={false}
          animate="show"
          className="mt-12 grid gap-8 sm:grid-cols-2"
        >
          {/* Improve Existing Draft */}
          <motion.div variants={item}>
            <Card className="h-full border-2 transition-shadow hover:shadow-md">
              <CardHeader>
                <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-xl bg-primary/15">
                  <ArrowUpFromLine className="h-6 w-6 text-primary" />
                </div>
                <CardTitle className="text-xl">Improve Existing Draft</CardTitle>
                <CardDescription>
                  Upload your current proposal for AI analysis. Get a competitiveness score
                  and personalized suggestions to strengthen your application.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex min-h-[140px] flex-col items-center justify-center rounded-lg border-2 border-dashed border-muted-foreground/30 bg-muted/30 p-6 text-center text-sm text-muted-foreground">
                  <FileUp className="mb-2 h-10 w-10 opacity-50" />
                  Drag & drop your proposal here or click to browse
                </div>
                <Button variant="secondary" className="w-full" size="lg">
                  <FileUp className="mr-2 h-4 w-4" />
                  Choose File
                </Button>
                <ul className="space-y-2 text-sm text-muted-foreground">
                  {["Instant competitiveness score", "Section-by-section feedback", "AI-powered improvements"].map(
                    (t) => (
                      <li key={t} className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-primary" />
                        {t}
                      </li>
                    )
                  )}
                </ul>
              </CardContent>
            </Card>
          </motion.div>

          {/* Start New Proposal */}
          <motion.div variants={item}>
            <Card className="h-full border-2 transition-shadow hover:shadow-md">
              <CardHeader>
                <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-xl bg-primary/15">
                  <MessageCircle className="h-6 w-6 text-primary" />
                </div>
                <CardTitle className="text-xl">Start New Proposal</CardTitle>
                <CardDescription>
                  Create a professional grant proposal from scratch. Our AI assistant will
                  guide you through each section with guided prompts and smart suggestions.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <Link href="/proposal">
                  <Button className="w-full" size="lg">
                    Start with AI Assistant
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
                <ul className="space-y-2 text-sm text-muted-foreground">
                  {[
                    "Guided assistant workflow",
                    "11-section structured workflow",
                    "RAG-based smart suggestions",
                  ].map((t) => (
                    <li key={t} className="flex items-center gap-2">
                      <Check className="h-4 w-4 text-primary" />
                      {t}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </motion.div>
        </motion.div>

        {/* Bottom feature cards */}
        <motion.div
          variants={container}
          initial={false}
          animate="show"
          className="mt-16 grid gap-6 sm:grid-cols-3"
        >
          {[
            {
              title: "RAG Technology",
              desc: "Upload your community documents for context-aware proposal generation",
              icon: Database,
              color: "bg-cyan-500/15 text-cyan-400",
            },
            {
              title: "GPT-5 mini Powered",
              desc: "Advanced AI understands Indigenous and Northern community context",
              icon: Cpu,
              color: "bg-blue-500/15 text-blue-400",
            },
          ].map((f) => (
            <motion.div key={f.title} variants={item}>
              <Card>
                <CardHeader>
                  <div className={`mb-2 flex h-10 w-10 items-center justify-center rounded-lg ${f.color}`}>
                    <f.icon className="h-5 w-5" />
                  </div>
                  <CardTitle className="text-base">{f.title}</CardTitle>
                  <CardDescription>{f.desc}</CardDescription>
                </CardHeader>
              </Card>
            </motion.div>
          ))}
        </motion.div>

        <p className="mt-12 text-center text-sm text-muted-foreground">
          Designed specifically for small Northern and Indigenous communities.
          <br />
          Works offline/low-bandwidth with saved progress.
        </p>
      </main>
    </div>
  );
}

