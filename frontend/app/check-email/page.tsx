import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Suspense } from "react";

import { CheckEmailPanel } from "@/components/account/check-email-panel";
import { TextSkeleton } from "@/components/skeletons";
import { getCurrentUser } from "@/lib/api-server";
import { safeNextPath } from "@/lib/session-hint";

export const metadata: Metadata = { title: "Check your email", robots: { index: false } };

/** Where a new account lands after sign-up (it's already logged in). */
export default function CheckEmailPage({ searchParams }: PageProps<"/check-email">) {
  return (
    <div className="mx-auto max-w-xl px-4 pt-16 text-center sm:px-6">
      <Suspense fallback={<TextSkeleton lines={5} />}>
        <CheckEmail searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

// Reads the session cookie and the URL, so it streams in at request time.
async function CheckEmail({ searchParams }: Pick<PageProps<"/check-email">, "searchParams">) {
  const [user, { sent, next }] = await Promise.all([getCurrentUser(), searchParams]);
  if (!user) redirect("/login?next=/check-email"); // proxy.ts normally catches this first
  const continueTo = safeNextPath(typeof next === "string" ? next : null, "/shop");

  if (user.email_verified) {
    return (
      <div className="space-y-5">
        <h1 className="font-serif text-4xl tracking-tight sm:text-5xl">Your email is confirmed</h1>
        <p className="text-muted">You&apos;ll get order confirmations and delivery updates at {user.email}.</p>
        <Link href="/account" className="inline-block rounded-full bg-ink px-6 py-3 text-sm font-medium text-paper hover:bg-accent">
          Go to your account
        </Link>
      </div>
    );
  }
  return <CheckEmailPanel email={user.email} justSent={sent === "1"} continueTo={continueTo} />;
}
