// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { giveConsent } from "@/app/actions";
import { CodesForm } from "@/components/codes-form";
import { codesLabels } from "@/components/codes-labels";
import { ConsentText, knowsConsentText } from "@/components/consent-text";
import { Button } from "@/components/ui/button";
import { getMe } from "@/lib/api";
import { cn } from "@/lib/cn";
import { onboardingStep } from "@/lib/onboarding";
import { operator } from "@/lib/site";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("welcome"))("title") };
}

/**
 * Where an invited player lands until the collector can follow them: their consent to the current
 * text, then their two codes. The home page sends them here while something is missing.
 */
export default async function Welcome({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const me = await getMe();
  if (!me) redirect("/");
  const step = onboardingStep(me);
  if (step === null) redirect("/");
  const t = await getTranslations("welcome");
  const { error } = await searchParams;
  const steps = [
    { key: "consent", label: t("stepConsent") },
    { key: "codes", label: t("stepCodes") },
    { key: "done", label: t("stepDone") },
  ];
  const current = step === "consent" ? 0 : 1;
  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        <h1 className="text-2xl font-semibold sm:text-[1.75rem]">{t("title")}</h1>
        <ol aria-label={t("steps")} className="flex flex-wrap gap-x-5 gap-y-1 text-sm">
          {steps.map((s, i) => (
            <li
              key={s.key}
              aria-current={i === current ? "step" : undefined}
              className={cn(
                "flex items-center gap-2 text-muted-foreground",
                i === current && "font-semibold text-foreground",
              )}
            >
              <span
                aria-hidden="true"
                className={cn(
                  "grid size-6 place-items-center rounded-full border border-border text-xs",
                  i === current && "border-foreground",
                  i < current && "bg-muted",
                )}
              >
                {i + 1}
              </span>
              {s.label}
            </li>
          ))}
        </ol>
      </div>
      {step === "consent" ? <ConsentStep me={me} error={error} /> : null}
      {step === "codes" ? (
        <div className="flex max-w-2xl flex-col gap-4 rounded-lg border border-border bg-card p-4 sm:p-6">
          <p className="text-[0.9375rem]">{t("codesLead")}</p>
          <CodesForm labels={await codesLabels()} next="/" />
        </div>
      ) : null}
      {step === "operator" ? (
        <p className="max-w-prose rounded-lg border border-border bg-card p-4">{t("operator")}</p>
      ) : null}
    </section>
  );
}

async function ConsentStep({
  me,
  error,
}: {
  me: NonNullable<Awaited<ReturnType<typeof getMe>>>;
  error: string | undefined;
}) {
  const t = await getTranslations("welcome");
  const text = await getTranslations("consent");
  const version = me.consent_version;
  const notice = !me.consent
    ? t("consentLead")
    : !me.consent.analysis
      ? t("withdrawn")
      : t("outdated");
  if (!(await knowsConsentText(version))) {
    return (
      <p role="alert" className="max-w-prose text-destructive">
        {t("unknownText", { version, email: operator().email ?? t("emailUnset") })}
      </p>
    );
  }
  const box = (name: string, required: boolean, path: string, checked: boolean) => (
    <label className="flex max-w-[70ch] cursor-pointer gap-3 rounded-md border border-border bg-background p-3 text-[0.9375rem] has-checked:border-foreground">
      <input
        type="checkbox"
        name={name}
        required={required}
        defaultChecked={checked}
        className="mt-1 size-4 shrink-0 accent-primary"
      />
      <span>
        {text.rich(`v${version}.${path}`, {
          b: (chunks) => <strong className="font-semibold">{chunks}</strong>,
        })}
      </span>
    </label>
  );
  return (
    <div className="flex flex-col gap-5">
      <p className="max-w-prose text-muted-foreground">{notice}</p>
      <div className="rounded-lg border border-border bg-card p-4 sm:p-6">
        <ConsentText version={version} />
        <p className="mt-4 text-[0.8125rem] text-muted-foreground">
          {text(`v${version}.version`)} {t("draft")}
        </p>
      </div>
      <form action={giveConsent} className="flex flex-col gap-3">
        <input type="hidden" name="text_version" value={version} />
        <input type="hidden" name="next" value="/welcome" />
        <h2 className="font-semibold">{text(`v${version}.agree`)}</h2>
        {box("analysis", true, "box1", false)}
        {box("research_corpus", false, "box2", me.consent?.research_corpus ?? false)}
        {error && (
          <p role="alert" className="max-w-prose text-sm text-destructive">
            {t(error === "version" ? "errorVersion" : "errorFailed")}
          </p>
        )}
        <Button type="submit" className="w-fit">
          {t("agreeButton")}
        </Button>
      </form>
    </div>
  );
}
