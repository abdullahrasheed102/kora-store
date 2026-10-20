"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { api, ApiError } from "@/lib/api";
import type { EmailVerified } from "@/lib/types";

const CONFIRMED_PAGE = "/account?email_confirmed=1";

/**
 * The page the "confirm your email" link opens. It waits for a click instead of confirming on
 * page load: mail scanners open links in emails automatically, and they never click buttons.
 */
export function VerifyEmailForm() {
  const token = useSearchParams().get("token") ?? "";
  const [result, setResult] = useState<EmailVerified | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function confirm() {
    setError(null);
    setLoading(true);
    try {
      const verified = await api.verifyEmail(token);
      if (verified.signed_in) {
        // A full page load, so the account page renders fresh with the confirmed status.
        // A full page load on purpose (as after login in auth-form.tsx): the client router may hold a copy
        // of /account from before the email was confirmed, which would show the old banner.
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.assign(CONFIRMED_PAGE);
        return;
      }
      setResult(verified); // opened on another device, or logged out: show it here, then log in
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return <p className="text-muted">This page needs the link from your email. Open the email and click the button again.</p>;
  }

  if (result) {
    return (
      <div role="status" className="space-y-4">
        <p className="text-lg">
          Thank you. <span className="break-all font-medium">{result.email}</span> is confirmed.
        </p>
        <p className="text-muted">We&apos;ll email you order confirmations and delivery updates from now on.</p>
        <Link
          href={`/login?next=${encodeURIComponent(CONFIRMED_PAGE)}`}
          className="inline-block rounded-full bg-ink px-6 py-3 text-sm font-medium text-paper hover:bg-accent"
        >
          Log in to your account
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <p className="text-muted">Click the button to confirm this is your email address.</p>
      <button
        type="button"
        onClick={confirm}
        disabled={loading}
        className="h-12 rounded-full bg-ink px-8 text-sm font-medium text-paper hover:bg-accent disabled:bg-ink/40"
      >
        {loading ? "Confirming…" : "Confirm my email"}
      </button>
      {error && (
        <p role="alert" className="rounded-sm bg-accent/10 px-4 py-3 text-sm text-accent-dark">
          {error}
        </p>
      )}
    </div>
  );
}
