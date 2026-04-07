"use client";

import { FormEvent, KeyboardEvent, useEffect, useState } from "react";

type SearchTypeOption = "category" | "creator";

export function SearchBar({
  currentType,
  searchQuery,
  onTypeChange,
  onSearch,
  categoryLabel,
  creatorLabel,
  placeholder,
  searchButtonLabel,
  className = "",
  disabled = false,
  loading = false
}: {
  currentType: SearchTypeOption;
  searchQuery: string;
  onTypeChange: (type: SearchTypeOption) => void;
  onSearch: (query: string) => void;
  categoryLabel: string;
  creatorLabel: string;
  placeholder: string;
  searchButtonLabel: string;
  className?: string;
  disabled?: boolean;
  loading?: boolean;
}) {
  const [value, setValue] = useState(searchQuery);

  useEffect(() => {
    setValue(searchQuery);
  }, [searchQuery]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (disabled || loading) {
      return;
    }
    onSearch(value);
  }

  function handleInputKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      if (event.nativeEvent.isComposing) {
        return;
      }
      event.preventDefault();
      if (disabled || loading) {
        return;
      }
      onSearch(value);
    }
  }

  return (
    <form aria-busy={loading} className={`mx-auto w-full max-w-3xl ${className}`} onSubmit={handleSubmit}>
      <div
        className={`flex items-center rounded-full border border-white/70 bg-white/55 p-1.5 shadow-[0_4px_16px_rgb(15,23,42,0.06)] backdrop-blur-sm transition ${
          disabled || loading ? "opacity-90" : ""
        }`}
      >
        <div className="flex items-center pl-2 pr-2">
          <button
            className={`rounded-full px-3 py-2 text-sm font-medium transition ${
              currentType === "category"
                ? "bg-white/80 text-peach-600"
                : "bg-transparent text-slate-600 hover:text-slate-800"
            }`}
            disabled={disabled || loading}
            onClick={() => onTypeChange("category")}
            type="button"
          >
            {categoryLabel}
          </button>
          <button
            className={`rounded-full px-3 py-2 text-sm font-medium transition ${
              currentType === "creator"
                ? "bg-white/80 text-peach-600"
                : "bg-transparent text-slate-600 hover:text-slate-800"
            }`}
            disabled={disabled || loading}
            onClick={() => onTypeChange("creator")}
            type="button"
          >
            {creatorLabel}
          </button>
        </div>

        <div className="mx-2 h-5 w-px bg-slate-300/50" />

        <input
          className="h-11 w-full flex-1 bg-transparent px-3 text-sm text-slate-800 outline-none placeholder:text-slate-400 disabled:cursor-not-allowed disabled:text-slate-500"
          disabled={disabled || loading}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleInputKeyDown}
          placeholder={placeholder}
          type="text"
          value={value}
        />

        <button
          className={`inline-flex min-w-[104px] items-center justify-center gap-2 rounded-full px-6 py-2.5 text-sm font-medium text-white shadow-sm transition-colors duration-150 ${
            loading
              ? "bg-peach-400"
              : "bg-peach-500 hover:bg-peach-600"
          } disabled:cursor-not-allowed disabled:bg-peach-300`}
          disabled={disabled || loading}
          type="submit"
        >
          {loading ? (
            <>
              <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/35 border-t-white" />
              <span>{searchButtonLabel}</span>
            </>
          ) : (
            searchButtonLabel
          )}
        </button>
      </div>
    </form>
  );
}

export type { SearchTypeOption };
