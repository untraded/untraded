// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only

/** A few options side by side, the current one pressed. A plain form: each option posts its value
 * to a server action, so no client JavaScript is needed. */
export function Choice({
  action,
  name,
  value,
  options,
  label,
}: {
  action: (formData: FormData) => Promise<void>;
  name: string;
  value: string;
  options: { value: string; label: string }[];
  label: string;
}) {
  return (
    <form
      action={action}
      aria-label={label}
      className="inline-flex shrink-0 rounded-md border border-border bg-card p-0.5"
    >
      {options.map((option) => (
        <button
          key={option.value}
          type="submit"
          name={name}
          value={option.value}
          aria-pressed={option.value === value}
          className="h-7 rounded-sm px-2.5 text-[0.8125rem] text-muted-foreground hover:text-foreground aria-pressed:bg-muted aria-pressed:font-medium aria-pressed:text-foreground"
        >
          {option.label}
        </button>
      ))}
    </form>
  );
}
