// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: LicenseRef-Untraded-Trademark
//
// A variant of the Untraded sign (see `logo.tsx`): a trademark, not covered by the licence of the
// code around it.

/**
 * The sign with no trade: the empty square (a player falls), a link cut short, and the teammate
 * who should answer drawn as a dashed outline that keeps looking. Used on the 404 page. Drawn in
 * `currentColor`; the ghost square moves only when the visitor allows motion.
 */
export function UntradedSign({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 32 32"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      <style>{`
        @media (prefers-reduced-motion: no-preference) {
          .untraded-ghost { animation: untraded-search 2.4s linear infinite; }
          .untraded-stub { animation: untraded-reach 2.4s ease-in-out infinite; }
        }
        @keyframes untraded-search {
          0% { stroke-dashoffset: 0; opacity: 0.55; }
          50% { opacity: 0.2; }
          100% { stroke-dashoffset: -8; opacity: 0.55; }
        }
        @keyframes untraded-reach {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.45; }
        }
      `}</style>
      <path fill="currentColor" fillRule="evenodd" d="M2 2H14V14H2Z M5 5V11H11V5Z" />
      <path
        className="untraded-stub"
        fill="currentColor"
        d="M12 14.1L14.1 12L16.6 14.5L14.5 16.6Z"
      />
      <rect
        className="untraded-ghost"
        x="18.75"
        y="18.75"
        width="10.5"
        height="10.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeDasharray="2 2"
        opacity="0.55"
      />
    </svg>
  );
}
