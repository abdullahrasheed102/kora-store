"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";

const COOLDOWN_SECONDS = 60; // matches the API's limit: one resend a minute

const inputClass =
  "mt-1.5 h-12 w-full rounded-sm border border-line bg-card px-4 text-base focus:border-ink/50 focus:outline-none focus-visible:outline-2";

type Props = {
  email: string;
  /** True right after sign-up: a link was sent seconds ago, so start with the countdown running. */
  justSent: boolean;
  continueTo: string;
};

export function CheckEmailPanel({ email: initialEmail, justSent, continueTo }: Props) {
  const [email, setEmail] = useState(initialEmail);
  const [secondsLeft, setSecondsLeft] = useState(justSent ? COOLDOWN_SECONDS : 0);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [changing, setChanging] = useState(false);

  // One tick per second while the countdown runs. (Effects are for syncing with something outside
  // React, and a timer is exactly that.)
  useEffect(() => {
    if (secondsLeft <= 0) return;
    const timer = setTimeout(() => setSecondsLeft((seconds) => seconds - 1), 1000);
    return () => clearTimeout(timer);
  }, [secondsLeft]);

  async function resend() {
    setError(null);
    setStatus(null);
    setSending(true);
    try {
      const result = await api.resendVerification();
      if (result.already_verified) {
        // A full page load on purpose (as after login in auth-form.tsx): the client router may hold a copy
        // of /account from before the email was confirmed, which would show the old banner.
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.assign("/account?email_confirmed=1");
        return;
      }
      setStatus(`We sent a new link to ${email}.`);
      setSecondsLeft(COOLDOWN_SECONDS);
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 429) {
        // The server knows best how long to wait (Retry-After).
        setSecondsLeft(caught.retryAfter ?? COOLDOWN_SECONDS);
        setError("You've asked for a few links already. You can ask again when the countdown ends.");
      } else {
        setError("We couldn't send the email. Please try again.");
      }
    } finally {
      setSending(false);
    }
  }

  async function changeEmail(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError(null);
    setStatus(null);
    setSending(true);
    try {
      const { user } = await api.changeEmail(String(form.get("email") ?? ""), String(form.get("password") ?? ""));
      setEmail(user.email);
      setChanging(false);
      setStatus(`Updated. We sent a new link to ${user.email}.`);
      setSecondsLeft(COOLDOWN_SECONDS);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.status === 429
            ? "Too many changes. Please try again later."
            : caught.code === "validation_error"
              ? "Please enter a valid email address."
              : caught.message
          : "Something went wrong. Please try again.",
      );
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="font-serif text-4xl tracking-tight sm:text-5xl">Check your email</h1>
      <p className="text-muted">
        We sent a link to <span className="break-all font-medium text-ink">{email}</span>. Click it to confirm your
        address. Until then you can shop as normal, but we won&apos;t send you order confirmations or delivery updates.
      </p>

      <div aria-live="polite" className="space-y-3">
        {status && <p className="rounded-sm bg-sage px-4 py-3 text-sm">{status}</p>}
        {error && (
          <p role="alert" className="rounded-sm bg-accent/10 px-4 py-3 text-sm text-accent-dark">
            {error}
          </p>
        )}
      </div>

      <div className="flex flex-col items-center gap-3">
        <button
          type="button"
          onClick={resend}
          disabled={sending || secondsLeft > 0}
          className="h-12 rounded-full bg-ink px-8 text-sm font-medium text-paper hover:bg-accent disabled:bg-ink/40"
        >
          {secondsLeft > 0 ? `Resend link in ${secondsLeft}s` : sending ? "Sending…" : "Resend link"}
        </button>
        <p className="text-sm text-muted">Can&apos;t find it? Check your spam folder.</p>
      </div>

      {changing ? (
        <form onSubmit={changeEmail} className="space-y-4 rounded-sm bg-card p-6 text-left ring-1 ring-line">
          <div>
            <label htmlFor="new-email" className="text-sm font-medium">
              The right email address
            </label>
            <input id="new-email" name="email" type="email" autoComplete="email" required maxLength={254} className={inputClass} />
          </div>
          <div>
            <label htmlFor="current-password" className="text-sm font-medium">
              Your password
            </label>
            <input
              id="current-password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              maxLength={128}
              className={inputClass}
            />
            <p className="mt-1.5 text-xs text-muted">So nobody else using this browser can move your account.</p>
          </div>
          <div className="flex gap-3">
            <button
              type="submit"
              disabled={sending}
              className="h-11 rounded-full bg-ink px-6 text-sm font-medium text-paper hover:bg-accent disabled:bg-ink/40"
            >
              {sending ? "Saving…" : "Save and send a new link"}
            </button>
            <button type="button" onClick={() => setChanging(false)} className="text-sm font-medium hover:text-accent">
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <p className="text-sm">
          Wrong email?{" "}
          <button type="button" onClick={() => setChanging(true)} className="font-medium underline underline-offset-4 hover:text-accent">
            Change it
          </button>
        </p>
      )}

      <Link href={continueTo} className="inline-block text-sm font-medium text-muted hover:text-ink">
        Continue shopping →
      </Link>
    </div>
  );
}
