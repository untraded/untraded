// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use server";

import { revalidatePath } from "next/cache";
import { apiSend, refusedField } from "@/lib/api";

export type InviteState = {
  error: "steam_id" | "display_name" | "exists" | "failed" | null;
  /** The name of the player just invited, to confirm it. */
  invited: string | null;
  steam_id: string;
  display_name: string;
};

/** Invites a Steam account to the beta: its first sign-in creates the player. */
export async function invite(_: InviteState, formData: FormData): Promise<InviteState> {
  const body = {
    steam_id: String(formData.get("steam_id") ?? "").trim(),
    display_name: String(formData.get("display_name") ?? "").trim(),
  };
  const result = await apiSend("/admin/invitations", "POST", body);
  if (!result.ok) {
    const field = refusedField(result);
    const error =
      field === "steam_id" || field === "display_name"
        ? field
        : result.status === 409
          ? "exists"
          : "failed";
    return { error, invited: null, ...body };
  }
  revalidatePath("/admin");
  return { error: null, invited: body.display_name, steam_id: "", display_name: "" };
}

/** Withdraws an invitation nobody used yet. */
export async function revokeInvitation(formData: FormData): Promise<void> {
  const steamId = String(formData.get("steam_id"));
  if (/^\d{17}$/.test(steamId)) {
    await apiSend(`/admin/invitations/${steamId}`, "DELETE");
  }
  revalidatePath("/admin");
}

const SOURCE = /^[0-9a-f-]{36}$/;

/** Pauses, resumes or removes how the collector follows a player (`intent` in the form). */
export async function changeSource(formData: FormData): Promise<void> {
  const id = String(formData.get("source"));
  const intent = String(formData.get("intent"));
  if (!SOURCE.test(id)) return;
  if (intent === "pause" || intent === "resume") {
    await apiSend(`/admin/sources/${id}/${intent}`, "POST");
  } else if (intent === "remove") {
    await apiSend(`/admin/sources/${id}`, "DELETE");
  }
  revalidatePath("/admin");
}
