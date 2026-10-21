import { createContext, useContext, type ComponentType, type ReactNode } from "react"
import type { PhotoInfo } from "@/api"

/**
 * Admin-only extras injected into the deck when it runs inside the unified app
 * (right-click-to-name faces, live name overrides). Absent in the standalone guest deck.
 */
export interface DeckExtras {
  names: Record<number, string>
  FaceMenu: ComponentType<{ cid: number; name?: string | null; children: ReactNode; hint?: boolean; asChild?: boolean; className?: string; hintClassName?: string }>
  fetchFaces: (src: string) => Promise<PhotoInfo | null>
}

const Ctx = createContext<DeckExtras | null>(null)
export const DeckExtrasProvider = Ctx.Provider
export const useDeckExtras = () => useContext(Ctx)
