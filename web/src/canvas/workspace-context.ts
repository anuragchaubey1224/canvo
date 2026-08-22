// What the canvas chrome needs from the workspace around it.
//
// tldraw renders its component slots itself, with no props — so anything mounted into
// `TopPanel` or `Toolbar` gets its data from here rather than from an argument. A context
// is also what lets the header live *inside* the editor (where `useEditor` works) while
// its state lives outside it.

import { createContext, useContext } from 'react'

/** Whether the canvas on screen matches the canvas on the server. */
export type SaveState = 'idle' | 'unsaved' | 'saving' | 'saved' | 'error'

export interface Workspace {
  title: string
  /** Commits a rename. The caller persists it and updates the shown title. */
  onRename: (title: string) => void
  saveState: SaveState
  onHome: () => void
  railOpen: boolean
  onToggleRail: () => void
  /** True while the agent is streaming — the header shows it, and title editing waits. */
  busy: boolean
}

export const WorkspaceContext = createContext<Workspace | null>(null)

export function useWorkspace(): Workspace {
  const value = useContext(WorkspaceContext)
  if (!value) throw new Error('useWorkspace must be used inside <WorkspaceContext.Provider>')
  return value
}
