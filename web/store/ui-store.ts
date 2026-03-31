"use client";

import { create } from "zustand";

type UiState = {
  filterPanelOpen: boolean;
  cardDensity: "comfortable" | "compact";
  toggleFilterPanel: () => void;
  setCardDensity: (density: "comfortable" | "compact") => void;
};

export const useUiStore = create<UiState>((set) => ({
  filterPanelOpen: false,
  cardDensity: "comfortable",
  toggleFilterPanel: () => set((state) => ({ filterPanelOpen: !state.filterPanelOpen })),
  setCardDensity: (cardDensity) => set({ cardDensity })
}));
