// Design tokens for the custom canvas shapes (node cards, panels).
// Dark-first, one accent per element, hairline borders — mirrors the app's token system
// (index.css) so agent-drawn shapes feel native to the product, not pasted on.

export type ShapeTheme = {
  cardBg: string
  cardBorder: string
  text: string
  textMuted: string
  iconBg: (accent: string) => string
  panelFill: (accent: string) => string
  panelBorder: (accent: string) => string
}

// Accent ramp keyed by the contract's tldraw-style color tokens. Calm, not neon.
const ACCENT_DARK: Record<string, string> = {
  blue: '#6E8BFF',
  'light-blue': '#4FB6E8',
  violet: '#A78BFA',
  orange: '#F0A35E',
  green: '#3DD68C',
  yellow: '#E8C35A',
  red: '#F1616E',
  grey: '#9AA3AB',
  black: '#9AA3AB',
}

const ACCENT_LIGHT: Record<string, string> = {
  blue: '#3B63E0',
  'light-blue': '#0E7FB8',
  violet: '#7C5CD6',
  orange: '#C97B2D',
  green: '#178C57',
  yellow: '#A8871B',
  red: '#CC4854',
  grey: '#5B646C',
  black: '#5B646C',
}

export function accent(token: string | null | undefined, dark: boolean): string {
  const map = dark ? ACCENT_DARK : ACCENT_LIGHT
  return map[token ?? ''] ?? map.grey
}

function withAlpha(hex: string, alpha: number): string {
  const n = parseInt(hex.slice(1), 16)
  const r = (n >> 16) & 255
  const g = (n >> 8) & 255
  const b = n & 255
  return `rgba(${r},${g},${b},${alpha})`
}

export function shapeTheme(dark: boolean): ShapeTheme {
  if (dark) {
    return {
      cardBg: '#14171A',
      cardBorder: '#2A3138',
      text: '#E6E9EC',
      textMuted: '#9AA3AB',
      iconBg: (a) => withAlpha(a, 0.14),
      panelFill: (a) => withAlpha(a, 0.07),
      panelBorder: (a) => withAlpha(a, 0.45),
    }
  }
  return {
    cardBg: '#FFFFFF',
    cardBorder: '#D7DCE1',
    text: '#1A2027',
    textMuted: '#5B646C',
    iconBg: (a) => withAlpha(a, 0.12),
    panelFill: (a) => withAlpha(a, 0.06),
    panelBorder: (a) => withAlpha(a, 0.5),
  }
}
