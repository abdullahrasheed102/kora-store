import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { TextSkeleton } from "@/components/skeletons";
import { api, isNotFound } from "@/lib/api";
import { POLICY_LINKS } from "@/lib/site";

export async function generateMetadata({ params }: PageProps<"/policies/[key]">): Promise<Metadata> {
  const { key } = await params;
  const title = POLICY_LINKS.find((policy) => policy.key === key)?.title ?? "Policy";
  return { title };
}

export default function PolicyPage({ params }: PageProps<"/policies/[key]">) {
  return (
    <div className="mx-auto grid max-w-6xl gap-12 px-4 pt-12 sm:px-6 lg:grid-cols-[220px_1fr] lg:px-8">
      <nav aria-label="Policies" className="order-last lg:order-first">
        <h2 className="text-xs font-medium uppercase tracking-widest text-muted">Policies</h2>
        <ul className="mt-4 space-y-2.5 text-sm">
          {POLICY_LINKS.map((policy) => (
            <li key={policy.key}>
              <Link href={`/policies/${policy.key}`} className="hover:text-accent">
                {policy.title}
              </Link>
            </li>
          ))}
          <li>
            <Link href="/policies" className="text-muted hover:text-accent">
              All policies
            </Link>
          </li>
        </ul>
      </nav>
      <Suspense fallback={<TextSkeleton lines={6} />}>
        <PolicyContent params={params} />
      </Suspense>
    </div>
  );
}

async function PolicyContent({ params }: Pick<PageProps<"/policies/[key]">, "params">) {
  const { key } = await params;
  const policy = await api.policy(key).catch((error) => {
    if (isNotFound(error)) notFound();
    throw error;
  });
  const updated = new Date(policy.updated_at).toLocaleDateString("en-US", { dateStyle: "long" });

  return (
    <article className="max-w-2xl">
      <h1 className="font-serif text-4xl tracking-tight sm:text-5xl">{policy.title}</h1>
      <p className="mt-3 text-sm text-muted">Last updated {updated}</p>
      <p className="mt-8 text-lg leading-relaxed text-ink/85">{policy.body}</p>
      <div className="mt-12 rounded-sm bg-sage p-6">
        <h2 className="font-serif text-xl">Still have a question?</h2>
        <p className="mt-2 text-sm leading-relaxed text-ink/75">
          Our AI assistant can look up your order and answer policy questions any time. People reply Monday to
          Friday, 9am–6pm Eastern.
        </p>
      </div>
    </article>
  );
}
