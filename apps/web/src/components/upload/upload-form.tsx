// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { FileArchive, Upload, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { type DragEvent, useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import type { Locale } from "@/i18n/locale";
import { PUBLIC_API_PATH } from "@/lib/api-path";
import { cn } from "@/lib/cn";
import { bytes } from "@/lib/format";
import {
  ACCEPT,
  faceitMatchId,
  fromLocalInput,
  guessPlayedAt,
  isDemoName,
  type SendError,
  sendError,
  toLocalInput,
} from "@/lib/upload";

const MODES = ["faceit", "esea", "scrim"] as const;
type Mode = (typeof MODES)[number];
/** The last mode chosen, offered first next time (a per-browser convenience). */
const MODE_KEY = "untraded_upload_mode";

export interface UploadLabels {
  dropTitle: string;
  dropHint: string;
  choose: string;
  remove: string;
  file: string;
  mode: string;
  modes: Record<Mode, string>;
  date: string;
  /** The date comes from the file: when it was written, often the download. */
  dateHint: string;
  /** The date comes from FACEIT, read from the match id in the file name. */
  dateFaceit: string;
  send: string;
  cancel: string;
  /** With `{sent}` and `{total}`. */
  progress: string;
  done: string;
  aborted: string;
  errors: Record<SendError, string>;
}

type Phase =
  | { kind: "idle" }
  | { kind: "chosen"; file: File }
  | { kind: "sending"; file: File; sent: number }
  | { kind: "done" }
  | { kind: "error"; file: File | null; error: SendError }
  | { kind: "aborted"; file: File };

/**
 * Choosing a demo (button or drop), its mode and start time, then sending it as the raw body of
 * `POST /api/uploads` with a progress bar: `XMLHttpRequest`, since `fetch` reports no upload
 * progress. A refusal known before sending (`disabled`) is said by the page, above.
 */
export function UploadForm({
  maxBytes,
  disabled,
  locale,
  labels,
}: {
  maxBytes: number;
  disabled: boolean;
  locale: Locale;
  labels: UploadLabels;
}) {
  const router = useRouter();
  const ids = useId();
  const input = useRef<HTMLInputElement>(null);
  const request = useRef<XMLHttpRequest | null>(null);
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [mode, setMode] = useState<Mode>("faceit");
  const [date, setDate] = useState("");
  /** Where the suggested date comes from: FACEIT when the file name gives its match. */
  const [dateFrom, setDateFrom] = useState<"file" | "faceit">("file");
  /** The file the FACEIT date is asked for: an answer for an earlier file is dropped. */
  const asked = useRef<File | null>(null);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(MODE_KEY);
      if (saved && (MODES as readonly string[]).includes(saved)) setMode(saved as Mode);
    } catch {
      // No storage (private window): FACEIT stays first.
    }
    return () => request.current?.abort();
  }, []);

  function pick(file: File | undefined) {
    asked.current = null;
    if (!file || disabled) return;
    if (!isDemoName(file.name)) return setPhase({ kind: "error", file: null, error: "not_a_demo" });
    if (file.size > maxBytes) return setPhase({ kind: "error", file: null, error: "too_large" });
    setDate(toLocalInput(guessPlayedAt(file.lastModified, Date.now())));
    setDateFrom("file");
    setPhase({ kind: "chosen", file });
    const match = faceitMatchId(file.name);
    asked.current = match ? file : null;
    if (match) {
      setMode("faceit");
      void faceitDate(file, match);
    }
  }

  /** The start of a FACEIT match, from FACEIT: the file's own date is when it was downloaded. */
  async function faceitDate(file: File, match: string) {
    try {
      const response = await fetch(
        `${PUBLIC_API_PATH}/uploads/faceit/${encodeURIComponent(match)}`,
      );
      if (!response.ok) return;
      const { played_at } = (await response.json()) as { played_at: string | null };
      const start = played_at ? new Date(played_at) : null;
      if (asked.current !== file || !start || Number.isNaN(start.getTime())) return;
      setDate(toLocalInput(start));
      setDateFrom("faceit");
    } catch {
      // FACEIT out of reach: the file's date stays, with its warning.
    }
  }

  function send(file: File) {
    asked.current = null;
    const playedAt = fromLocalInput(date);
    if (!playedAt) return setPhase({ kind: "error", file, error: "date" });
    const query = new URLSearchParams({ name: file.name, mode, played_at: playedAt });
    const xhr = new XMLHttpRequest();
    request.current = xhr;
    xhr.open("POST", `${PUBLIC_API_PATH}/uploads?${query}`);
    xhr.setRequestHeader("content-type", "application/octet-stream");
    xhr.upload.onprogress = (event) => setPhase({ kind: "sending", file, sent: event.loaded });
    xhr.onload = () => {
      request.current = null;
      if (xhr.status === 202) {
        try {
          window.localStorage.setItem(MODE_KEY, mode);
        } catch {
          // Not remembered: fine.
        }
        setPhase({ kind: "done" });
        router.refresh();
      } else {
        setPhase({ kind: "error", file, error: sendError(xhr.status, xhr.responseText) });
      }
    };
    xhr.onerror = () => {
      request.current = null;
      setPhase({ kind: "error", file, error: "network" });
    };
    xhr.onabort = () => {
      request.current = null;
      setPhase({ kind: "aborted", file });
    };
    setPhase({ kind: "sending", file, sent: 0 });
    xhr.send(file);
  }

  const file =
    phase.kind === "chosen" || phase.kind === "sending" || phase.kind === "aborted"
      ? phase.file
      : phase.kind === "error"
        ? phase.file
        : null;
  const sending = phase.kind === "sending";
  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragging(false);
    if (!sending) pick(event.dataTransfer.files[0]);
  };
  const message =
    phase.kind === "error"
      ? labels.errors[phase.error]
      : phase.kind === "done"
        ? labels.done
        : phase.kind === "aborted"
          ? labels.aborted
          : null;

  return (
    <div className="flex flex-col gap-3">
      {!file && (
        // The drop zone is a convenience: the button inside it does the same with the keyboard.
        // biome-ignore lint/a11y/noStaticElementInteractions: drag and drop has no keyboard role
        <div
          onDragOver={(event) => {
            event.preventDefault();
            if (!disabled) setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={cn(
            "flex flex-col items-center gap-2.5 rounded-lg border-[1.5px] border-dashed border-border bg-card px-4 py-9 text-center",
            dragging && "border-foreground bg-muted",
            disabled && "opacity-60",
          )}
        >
          <Upload aria-hidden="true" className="size-6 text-muted-foreground" />
          <p className="font-semibold">{labels.dropTitle}</p>
          <p className="max-w-prose text-[0.8125rem] text-muted-foreground">{labels.dropHint}</p>
          <input
            ref={input}
            id={`${ids}-file`}
            type="file"
            accept={ACCEPT}
            disabled={disabled}
            className="sr-only"
            onChange={(event) => {
              pick(event.target.files?.[0]);
              event.target.value = "";
            }}
          />
          <Button type="button" disabled={disabled} onClick={() => input.current?.click()}>
            {labels.choose}
          </Button>
        </div>
      )}

      {file && (
        <section
          aria-label={labels.file}
          className="flex flex-col gap-4 rounded-lg border border-border bg-card p-4"
        >
          <div className="flex items-center gap-3">
            <FileArchive aria-hidden="true" className="size-5 shrink-0 text-muted-foreground" />
            <div className="min-w-0 flex-1">
              <p className="truncate font-mono text-[0.8125rem]" translate="no">
                {file.name}
              </p>
              <p className="text-xs text-muted-foreground">{bytes(file.size, locale, 1024)}</p>
            </div>
            {!sending && (
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label={labels.remove}
                title={labels.remove}
                onClick={() => {
                  asked.current = null;
                  setPhase({ kind: "idle" });
                }}
              >
                <X aria-hidden="true" />
              </Button>
            )}
          </div>

          <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
            <fieldset className="flex flex-col gap-1.5" disabled={sending}>
              <legend className="mb-1.5 text-[0.8125rem] font-medium text-muted-foreground">
                {labels.mode}
              </legend>
              <div className="inline-flex overflow-hidden rounded-md border border-border">
                {MODES.map((m) => (
                  <label
                    key={m}
                    className={cn(
                      "flex h-8 cursor-pointer items-center border-l border-border px-3 text-sm first:border-l-0 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-ring",
                      mode === m && "bg-highlight-soft font-semibold",
                    )}
                  >
                    <input
                      type="radio"
                      name={`${ids}-mode`}
                      value={m}
                      checked={mode === m}
                      onChange={() => {
                        setMode(m);
                        // Not a FACEIT match after all: its date no longer holds.
                        asked.current = null;
                        if (m !== "faceit") setDateFrom("file");
                      }}
                      className="sr-only"
                    />
                    {labels.modes[m]}
                  </label>
                ))}
              </div>
            </fieldset>
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor={`${ids}-date`}
                className="text-[0.8125rem] font-medium text-muted-foreground"
              >
                {labels.date}
              </label>
              <input
                id={`${ids}-date`}
                type="datetime-local"
                value={date}
                disabled={sending}
                aria-describedby={`${ids}-date-hint`}
                onChange={(event) => {
                  setDate(event.target.value);
                  asked.current = null;
                  setDateFrom("file");
                }}
                className="h-8 rounded-md border border-input bg-card px-2 text-sm tabular-nums"
              />
            </div>
            <p id={`${ids}-date-hint`} className="max-w-sm text-xs text-muted-foreground">
              {dateFrom === "faceit" ? labels.dateFaceit : labels.dateHint}
            </p>
          </div>

          {sending && (
            <div className="flex flex-col gap-1.5">
              <div
                role="progressbar"
                aria-label={labels.file}
                aria-valuemin={0}
                aria-valuemax={file.size}
                aria-valuenow={phase.sent}
                className="h-1.5 overflow-hidden rounded-full bg-muted"
              >
                <div
                  className="h-full bg-foreground transition-[width]"
                  style={{ width: `${Math.round((phase.sent / Math.max(file.size, 1)) * 100)}%` }}
                />
              </div>
              <p className="text-xs text-muted-foreground tabular-nums">
                {labels.progress
                  .replace("{sent}", bytes(phase.sent, locale, 1024))
                  .replace("{total}", bytes(file.size, locale, 1024))}
              </p>
            </div>
          )}

          <div className="flex justify-end gap-2">
            {sending ? (
              <Button type="button" variant="outline" onClick={() => request.current?.abort()}>
                {labels.cancel}
              </Button>
            ) : (
              <Button type="button" disabled={disabled} onClick={() => send(file)}>
                {labels.send}
              </Button>
            )}
          </div>
        </section>
      )}

      <p
        aria-live="polite"
        className={cn(
          "text-sm",
          phase.kind === "error" &&
            "rounded-md border border-border border-l-[3px] border-l-loss bg-card px-3 py-2",
          phase.kind === "done" &&
            "rounded-md border border-border border-l-[3px] border-l-win bg-card px-3 py-2",
          !message && "sr-only",
        )}
      >
        {message}
      </p>
    </div>
  );
}
