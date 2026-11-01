// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * A classic CS crosshair (four lines, a gap, no dot) that drifts slowly without finding a target:
 * the 404 page's illustration. Drawn in `currentColor`; it moves only when the visitor allows
 * motion.
 */
export function SearchingCrosshair({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 64 64"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      <style>{`
        @media (prefers-reduced-motion: no-preference) {
          .crosshair-drift { animation: crosshair-search 5s ease-in-out infinite; }
        }
        @keyframes crosshair-search {
          0%, 100% { transform: translate(0, 0); }
          25% { transform: translate(9px, -5px); }
          50% { transform: translate(-6px, 7px); }
          75% { transform: translate(5px, 4px); }
        }
      `}</style>
      <g
        className="crosshair-drift"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="square"
        fill="none"
      >
        <path d="M32 14V26 M32 38V50 M14 32H26 M38 32H50" />
      </g>
    </svg>
  );
}
