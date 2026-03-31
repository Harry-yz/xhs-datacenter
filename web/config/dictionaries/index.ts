import en from "@/config/dictionaries/en";
import zh from "@/config/dictionaries/zh";
import { type Locale } from "@/config/i18n";

const dictionaries = {
  zh,
  en
} as const;

export type Dictionary = (typeof dictionaries)[Locale];

export async function getDictionary(locale: Locale): Promise<Dictionary> {
  return dictionaries[locale];
}
