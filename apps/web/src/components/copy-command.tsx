// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";

/** A console command to paste in CS2, with a button that copies it. */
export function CopyCommand({ command, copy }: { command: string; copy: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <span className="inline-flex h-8 max-w-full items-center gap-1 rounded-md border border-border bg-background pr-1 pl-2.5">
      <code translate="no" className="truncate font-mono text-[0.8125rem]">
        {command}
      </code>
      <Button
        variant="ghost"
        size="icon-sm"
        aria-label={copy}
        title={copy}
        onClick={() => {
          navigator.clipboard.writeText(command).then(
            () => setCopied(true),
            () => setCopied(false),
          );
        }}
      >
        {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
      </Button>
    </span>
  );
}
