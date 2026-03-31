"use client";

import { FormEvent, KeyboardEvent, useEffect, useState } from "react";

type SearchTab = "category" | "creator";

export function SearchBar({
  currentTab,
  searchQuery,
  onTabChange,
  onSearch,
  categoryLabel,
  creatorLabel,
  placeholder,
  searchButtonLabel,
  className = ""
}: {
  currentTab: SearchTab;
  searchQuery: string;
  onTabChange: (tab: SearchTab) => void;
  onSearch: (query: string) => void;
  categoryLabel: string;
  creatorLabel: string;
  placeholder: string;
  searchButtonLabel: string;
  className?: string;
}) {
  const [value, setValue] = useState(searchQuery);

  useEffect(() => {
    setValue(searchQuery);
  }, [searchQuery]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSearch(value);
  }

  function toggleTab() {
    onTabChange(currentTab === "category" ? "creator" : "category");
  }

  function handleInputKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Tab") {
      return;
    }

    // In input mode, Tab only toggles between the two business tabs.
    event.preventDefault();
    toggleTab();
  }

  return (
    <form className={`mx-auto w-full max-w-3xl ${className}`} onSubmit={handleSubmit}>
      <div className="flex items-center rounded-full border border-white/70 bg-white/55 p-1.5 shadow-[0_4px_16px_rgb(15,23,42,0.06)] backdrop-blur-sm">
        <div className="flex items-center pl-2 pr-2">
          <button
            className={`rounded-full px-3 py-2 text-sm font-medium transition ${
              currentTab === "category"
                ? "bg-white/80 text-peach-600"
                : "bg-transparent text-slate-600 hover:text-slate-800"
            }`}
            onClick={() => onTabChange("category")}
            tabIndex={-1}
            type="button"
          >
            {categoryLabel}
          </button>
          <button
            className={`rounded-full px-3 py-2 text-sm font-medium transition ${
              currentTab === "creator"
                ? "bg-white/80 text-peach-600"
                : "bg-transparent text-slate-600 hover:text-slate-800"
            }`}
            onClick={() => onTabChange("creator")}
            tabIndex={-1}
            type="button"
          >
            {creatorLabel}
          </button>
        </div>

        <div className="mx-2 h-5 w-px bg-slate-300/50" />

        <input
          className="h-11 w-full flex-1 bg-transparent px-3 text-sm text-slate-800 outline-none placeholder:text-slate-400"
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleInputKeyDown}
          placeholder={placeholder}
          type="text"
          value={value}
        />

        <button
          className="rounded-full bg-peach-500 px-6 py-2.5 text-sm font-medium text-white shadow-sm transition-colors duration-150 hover:bg-peach-600"
          type="submit"
        >
          {searchButtonLabel}
        </button>
      </div>
    </form>
  );
}

export type { SearchTab };
