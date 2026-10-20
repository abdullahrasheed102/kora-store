"use client";

import { useState } from "react";

import { api, ApiError } from "@/lib/api";

/** Shown on the account page until the email address is confirmed. */
export function VerifyBanner({ email }: { email: string }) {
  const [state, setState] = useState<"idle" | "sending" | "sent" | "verified">("idle");
  const [error, setError] = useState<string | null>(null);

  async function resend() {
    setError(null);
    setState("sending");
    try {
      const result = await api.resendVerification();
      setState(result.already_verified ? "verified" : "sent");
    } catch (caught) {
      setState("idle");
      setError(
        caught instanceof ApiError && caught.status === 429
          ? "You've asked for several emails already. Please wait an hour and try again."
          : "We couldn't send the email. Please try again.",
      );
    }
  }

  if (state === "verified") return null;

  return (
    <section aria-labelledby="verify-heading" className="rounded-sm bg-sage px-5 py-4 text-sm">
      <h2 id="verify-heading" className="font-medium">
        Please confirm your email
      </h2>
      <p className="mt-1">
        We sent a link to <span className="break-all font-medium">{email}</span>. Until you click it, we won&apos;t send
        you order confirmations or delivery updates.
      </p>
      <div className="mt-3" aria-live="polite">
        {state === "sent" ? (
          <p>Sent. Check your inbox (and your spam folder).</p>
        ) : (
          <button
            type="button"
            onClick={resend}
            disabled={state === "sending"}
            className="font-medium underline underline-offset-4 hover:text-accent disabled:opacity-60"
          >
            {state === "sending" ? "Sending…" : "Send the link again"}
          </button>
        )}
        {error && <p className="mt-2 text-accent-dark">{error}</p>}
      </div>
    </section>
  );
}
