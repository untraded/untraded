// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import Link from "next/link";

export default function NotFound() {
  return (
    <section className="py-16 text-center">
      <h1 className="text-2xl font-semibold">404</h1>
      <Link href="/matches" className="mt-4 inline-block text-zinc-400 hover:text-white">
        ←
      </Link>
    </section>
  );
}
