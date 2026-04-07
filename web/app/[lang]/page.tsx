import { redirect } from "next/navigation";

import type { AppPageProps } from "./layout";

export default function LocaleRootPage({ params }: AppPageProps) {
  redirect(`/${params.lang}/datacenter`);
}
