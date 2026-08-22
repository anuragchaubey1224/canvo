// Chrome icons — one stroke weight, one 24-grid, one set of joins.
//
// Icons drawn by different hands at different weights are the fastest way to make a UI
// look assembled rather than designed, so every glyph here shares `s` and nothing sets
// its own stroke. (Canvas *shape* icons live in ../shapes/icons.tsx; these are for UI.)

import type { SVGProps } from 'react'

const s = {
  stroke: 'currentColor',
  strokeWidth: 1.6,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  fill: 'none',
}

type P = SVGProps<SVGSVGElement> & { size?: number }

function Svg({ size = 16, children, ...rest }: P) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {children}
    </svg>
  )
}

/* --- brand --- */
export const Logo = (p: P) => (
  <Svg {...p}>
    <path d="M4 4.5v15h15" {...s} />
    <path d="M8.5 15.5V10M13 15.5V5.5M17.5 15.5v-4" {...s} />
  </Svg>
)

/* --- openers --- */
export const Sparkle = (p: P) => (
  <Svg {...p}>
    <path d="M12 3.5l1.6 4.4 4.4 1.6-4.4 1.6L12 15.5l-1.6-4.4L6 9.5l4.4-1.6L12 3.5Z" {...s} />
    <path d="M18.4 15.6l.65 1.75 1.75.65-1.75.65-.65 1.75-.65-1.75-1.75-.65 1.75-.65.65-1.75Z" {...s} />
  </Svg>
)
export const Database = (p: P) => (
  <Svg {...p}>
    <ellipse cx="12" cy="6" rx="6.5" ry="2.75" {...s} />
    <path d="M5.5 6v6c0 1.5 2.9 2.75 6.5 2.75s6.5-1.25 6.5-2.75V6" {...s} />
    <path d="M5.5 12v6c0 1.5 2.9 2.75 6.5 2.75s6.5-1.25 6.5-2.75v-6" {...s} />
  </Svg>
)
export const Braces = (p: P) => (
  <Svg {...p}>
    <path d="M8.5 8.5L5 12l3.5 3.5M15.5 8.5L19 12l-3.5 3.5M13.5 5l-3 14" {...s} />
  </Svg>
)
export const PlusSquare = (p: P) => (
  <Svg {...p}>
    <rect x="3.75" y="3.75" width="16.5" height="16.5" rx="3.5" {...s} />
    <path d="M12 8.5v7M8.5 12h7" {...s} />
  </Svg>
)

/* --- navigation + list --- */
export const Layers = (p: P) => (
  <Svg {...p}>
    <path d="M12 3.5l8 4.25-8 4.25-8-4.25L12 3.5Z" {...s} />
    <path d="M4 12.25l8 4.25 8-4.25M4 16.5l8 4.25 8-4.25" {...s} />
  </Svg>
)
export const Clock = (p: P) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.25" {...s} />
    <path d="M12 7.25V12l3 1.75" {...s} />
  </Svg>
)
export const Draft = (p: P) => (
  <Svg {...p}>
    <path d="M13.5 3.5H7a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V9l-5.5-5.5Z" {...s} />
    <path d="M13.5 3.5V9H19" {...s} />
  </Svg>
)
export const Board = (p: P) => (
  <Svg {...p}>
    <rect x="2.75" y="4.25" width="8.5" height="6.25" rx="1.75" {...s} />
    <rect x="12.75" y="13.5" width="8.5" height="6.25" rx="1.75" {...s} />
    <path d="M7 10.5v6.125h5.75" {...s} />
  </Svg>
)

/* --- controls --- */
export const Search = (p: P) => (
  <Svg {...p}>
    <circle cx="10.75" cy="10.75" r="6.25" {...s} />
    <path d="M15.4 15.4L20 20" {...s} />
  </Svg>
)
export const X = (p: P) => (
  <Svg {...p}>
    <path d="M6.5 6.5l11 11M17.5 6.5l-11 11" {...s} />
  </Svg>
)
export const Plus = (p: P) => (
  <Svg {...p}>
    <path d="M12 5.5v13M5.5 12h13" {...s} />
  </Svg>
)
export const More = (p: P) => (
  <Svg {...p}>
    <circle cx="6" cy="12" r="1.35" fill="currentColor" stroke="none" />
    <circle cx="12" cy="12" r="1.35" fill="currentColor" stroke="none" />
    <circle cx="18" cy="12" r="1.35" fill="currentColor" stroke="none" />
  </Svg>
)
export const Trash = (p: P) => (
  <Svg {...p}>
    <path d="M4.5 6.5h15M9.5 6.5V4.75A1.25 1.25 0 0 1 10.75 3.5h2.5a1.25 1.25 0 0 1 1.25 1.25V6.5" {...s} />
    <path d="M6.75 6.5l.85 12.1a1.5 1.5 0 0 0 1.5 1.4h5.8a1.5 1.5 0 0 0 1.5-1.4l.85-12.1" {...s} />
  </Svg>
)
export const Pencil = (p: P) => (
  <Svg {...p}>
    <path d="M15.25 4.9a2.05 2.05 0 0 1 2.9 2.9L8.6 17.35l-3.85.95.95-3.85 9.55-9.55Z" {...s} />
  </Svg>
)
export const ArrowUpRight = (p: P) => (
  <Svg {...p}>
    <path d="M7.5 16.5l9-9M8.75 7.5h7.75v7.75" {...s} />
  </Svg>
)
export const PanelLeft = (p: P) => (
  <Svg {...p}>
    <rect x="3.5" y="4.5" width="17" height="15" rx="2.5" {...s} />
    <path d="M10 4.5v15" {...s} />
  </Svg>
)
export const Shield = (p: P) => (
  <Svg {...p}>
    <path d="M12 3.25l6.75 2.6v5.4c0 4.05-2.7 7.65-6.75 9.5-4.05-1.85-6.75-5.45-6.75-9.5v-5.4L12 3.25Z" {...s} />
    <path d="M9.25 11.85l2 2 3.5-3.9" {...s} />
  </Svg>
)
export const Check = (p: P) => (
  <Svg {...p}>
    <path d="M5 12.75l4.5 4.5L19 7.5" {...s} />
  </Svg>
)
export const Alert = (p: P) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.25" {...s} />
    <path d="M12 7.75v5M12 15.9v.1" {...s} />
  </Svg>
)
export const History = (p: P) => (
  <Svg {...p}>
    <path d="M3.75 12a8.25 8.25 0 1 0 2.5-5.9L3.5 8.75" {...s} />
    <path d="M3.5 4.25v4.5H8" {...s} />
    <path d="M12 7.75V12l2.75 1.6" {...s} />
  </Svg>
)

/* --- workspace chrome --- */
export const Home = (p: P) => (
  <Svg {...p}>
    <path d="M3.75 10.5L12 3.75l8.25 6.75" {...s} />
    <path d="M6 9.25V19.5a.75.75 0 0 0 .75.75h10.5a.75.75 0 0 0 .75-.75V9.25" {...s} />
  </Svg>
)
export const Undo = (p: P) => (
  <Svg {...p}>
    <path d="M4 9.5h9.5a5 5 0 0 1 0 10H8" {...s} />
    <path d="M7.5 5.5L3.5 9.5l4 4" {...s} />
  </Svg>
)
export const Redo = (p: P) => (
  <Svg {...p}>
    <path d="M20 9.5h-9.5a5 5 0 0 0 0 10H16" {...s} />
    <path d="M16.5 5.5l4 4-4 4" {...s} />
  </Svg>
)
export const SidebarRight = (p: P) => (
  <Svg {...p}>
    <rect x="3.5" y="4.5" width="17" height="15" rx="2.5" {...s} />
    <path d="M14 4.5v15" {...s} />
  </Svg>
)
export const Copy = (p: P) => (
  <Svg {...p}>
    <rect x="8.5" y="8.5" width="11" height="11" rx="2.25" {...s} />
    <path d="M15.5 8.5v-2a2 2 0 0 0-2-2h-7a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h2" {...s} />
  </Svg>
)
export const Stop = (p: P) => (
  <Svg {...p}>
    <rect x="6.5" y="6.5" width="11" height="11" rx="2" fill="currentColor" stroke="none" />
  </Svg>
)
export const Send = (p: P) => (
  <Svg {...p}>
    <path d="M12 19.5V5M12 5L5.5 11.5M12 5l6.5 6.5" {...s} />
  </Svg>
)
export const Refresh = (p: P) => (
  <Svg {...p}>
    <path d="M20 12a8 8 0 1 1-2.6-5.9" {...s} />
    <path d="M20.25 4.5v4.75H15.5" {...s} />
  </Svg>
)
export const Cursor = (p: P) => (
  <Svg {...p}>
    <path d="M5.5 3.75l13 7.1-5.9 1.6-1.6 5.9-5.5-14.6Z" {...s} />
  </Svg>
)

export const Logout = (p: P) => (
  <Svg {...p}>
    <path d="M14.5 4.5h3a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2h-3" {...s} />
    <path d="M10 15.5L13.5 12 10 8.5M13.5 12H4.5" {...s} />
  </Svg>
)
