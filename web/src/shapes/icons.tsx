// Inline SVG renderer for the node-card icon set. Paths live in paths.ts and name
// resolution in iconset.ts, so this file exports only a component (fast refresh).

import { PATHS } from './paths'

export function Icon({ name, size = 16, color }: { name: string; size?: number; color: string }) {
  const paths = PATHS[name] ?? PATHS.box
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths.map((d, i) => (
        <path key={i} d={d} />
      ))}
    </svg>
  )
}
