// Stroke paths for the node-card icon set: one stroke width, 24px grid (Lucide-style).
// Open set — see iconset.ts for how unknown names fall back.

export const PATHS: Record<string, string[]> = {
  monitor: ['M3 5h18v11H3z', 'M9 20h6', 'M12 16v4'],
  server: ['M3 5h18v6H3z', 'M3 13h18v6H3z', 'M7 8h.01', 'M7 16h.01'],
  shield: ['M12 3l8 3v5c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6z'],
  database: ['M12 3c5 0 8 1.3 8 3s-3 3-8 3-8-1.3-8-3 3-3 8-3z', 'M4 6v12c0 1.7 3 3 8 3s8-1.3 8-3V6'],
  cloud: ['M7 18a4.5 4.5 0 1 1 .9-8.9A6 6 0 0 1 19 11a3.5 3.5 0 0 1-1 7z'],
  queue: ['M4 6h16', 'M4 12h16', 'M4 18h10', 'M18 16l3 2-3 2'],
  key: ['M15 9a4 4 0 1 0-4 4l-6 6v-3h3l3-3', 'M15 9h.01'],
  gateway: ['M12 4v5', 'M12 15v5', 'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z', 'M4 7l4 3', 'M20 7l-4 3'],
  api: ['M8 8l-4 4 4 4', 'M16 8l4 4-4 4', 'M13 6l-2 12'],
  lock: ['M6 11h12v9H6z', 'M9 11V8a3 3 0 0 1 6 0v3'],
  refresh: ['M20 8A8 8 0 0 0 5 6l-2 2', 'M3 4v4h4', 'M4 16a8 8 0 0 0 15 2l2-2', 'M21 20v-4h-4'],
  user: ['M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z', 'M4 21c0-4 3.5-6 8-6s8 2 8 6'],
  note: ['M6 3h9l4 4v14H6z', 'M15 3v4h4', 'M9 12h6', 'M9 16h6'],
  play: ['M8 5l12 7-12 7z'],
  flag: ['M5 21V4', 'M5 4h13l-2.5 4L18 12H5'],
  box: ['M4 6h16v12H4z'],
}
