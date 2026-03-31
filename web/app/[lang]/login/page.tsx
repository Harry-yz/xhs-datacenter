import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { getDictionary } from "@/config/dictionaries";
import { buildMetadata } from "@/config/metadata";
import { withLocale } from "@/utils/routes";

import type { AppPageProps } from "../layout";

export async function generateMetadata({ params }: AppPageProps): Promise<Metadata> {
  const dictionary = await getDictionary(params.lang);

  return buildMetadata(dictionary.auth.title, dictionary.auth.subtitle);
}

export default async function LoginPage({ params, searchParams }: AppPageProps) {
  const target = withLocale(params.lang, "/datacenter");
  const next =
    typeof searchParams?.next === "string" && searchParams.next.startsWith("/")
      ? searchParams.next
      : undefined;
  const query = new URLSearchParams();
  query.set("auth", "1");
  if (next) {
    query.set("next", next);
  }
  redirect(`${target}?${query.toString()}`);
}
