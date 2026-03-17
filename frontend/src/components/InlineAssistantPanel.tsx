"use client";

import { FormEvent, useEffect, useState } from "react";
import { Loader2, MessageSquareMore } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export function InlineAssistantPanel({
  starters,
  contextLabel,
  isLoading,
  response,
  onSubmit,
}: {
  starters: string[];
  contextLabel?: string | null;
  isLoading: boolean;
  response: { text: string; actions: string[] } | null;
  onSubmit: (message: string) => void;
}) {
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (contextLabel) {
      setMessage(`Improve ${contextLabel.toLowerCase()}.`);
    }
  }, [contextLabel]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!message.trim()) return;
    onSubmit(message.trim());
  };

  return (
    <Card className="border-primary/20 bg-card/80 backdrop-blur-sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <MessageSquareMore className="h-4 w-4 text-primary" />
          Inline Assistant
        </CardTitle>
        {contextLabel && <p className="text-sm text-muted-foreground">Context: {contextLabel}</p>}
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          {starters.map((starter) => (
            <Button
              key={starter}
              size="sm"
              variant="outline"
              className="h-auto max-w-full whitespace-normal break-words px-4 py-2 text-left leading-snug"
              onClick={() => onSubmit(starter)}
            >
              <span className="block w-full break-words">{starter}</span>
            </Button>
          ))}
        </div>
        <form onSubmit={submit} className="space-y-3">
          <Input
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Ask for stronger wording, alignment, or clearer outcomes..."
            className="truncate"
          />
          <Button type="submit" className="w-full" disabled={isLoading || !message.trim()}>
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Thinking...
              </>
            ) : (
              "Ask Assistant"
            )}
          </Button>
        </form>
        {response && (
          <div className="rounded-2xl border border-border/70 bg-muted/20 p-4">
            <p className="text-sm text-foreground">{response.text}</p>
            {response.actions.length > 0 && (
              <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                {response.actions.map((action) => (
                  <li key={action} className="flex gap-2">
                    <span className="text-primary">-</span>
                    <span>{action}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
