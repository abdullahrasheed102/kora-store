"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState, useTransition } from "react";

import { api, ApiError } from "@/lib/api";
import { postLoginPath } from "@/lib/session-hint";

type Mode = "login" | "signup";

const inputClass =
  "mt-1.5 h-12 w-full rounded-sm border border-line bg-card px-4 text-base placeholder:text-muted/70 focus:border-ink/50 focus:outline-none focus-visible:outline-2";

export function AuthForm({ mode }: { mode: Mode }) {
  const next = useSearchParams().get("next");
  const [error, setError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [isPending, startTransition] = useTransition();

  // onSubmit (not <form action>): React resets a form after an action, which would wipe the
  // email the shopper typed whenever the password was wrong.
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError(null);
    const email = String(form.get("email") ?? "");
    const password = String(form.get("password") ?? "");
    try {
      const { user } =
        mode === "signup"
          ? await api.signup({ email, password, name: String(form.get("name") ?? "") })
          : await api.login({ email, password });
      // Admins go to /admin, customers back to where they came from (or /account).
      const destination = postLoginPath(user.role, next);
      // A full page load, not router.replace(): the client router may hold pages prefetched while
      // logged out (e.g. /account → "redirect to /login"). Reloading drops every cached page, so
      // everything renders fresh with the new session cookie.
      startTransition(() => window.location.assign(destination));
    } catch (caught) {
      setError(messageFor(caught));
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      {mode === "signup" && (
        <div>
          <label htmlFor="name" className="text-sm font-medium">
            Name
          </label>
          <input id="name" name="name" type="text" autoComplete="name" required maxLength={120} className={inputClass} />
        </div>
      )}
      <div>
        <label htmlFor="email" className="text-sm font-medium">
          Email
        </label>
        <input id="email" name="email" type="email" autoComplete="email" required maxLength={254} className={inputClass} />
      </div>
      <div>
        <div className="flex items-baseline justify-between">
          <label htmlFor="password" className="text-sm font-medium">
            Password
          </label>
          <button
            type="button"
            onClick={() => setShowPassword((shown) => !shown)}
            className="text-xs text-muted underline-offset-2 hover:text-ink hover:underline"
            aria-controls="password"
          >
            {showPassword ? "Hide" : "Show"}
          </button>
        </div>
        <input
          id="password"
          name="password"
          type={showPassword ? "text" : "password"}
          // Lets password managers fill (login) or generate (signup) the right thing.
          autoComplete={mode === "signup" ? "new-password" : "current-password"}
          required
          minLength={mode === "signup" ? 10 : undefined}
          maxLength={128}
          aria-describedby={mode === "signup" ? "password-hint" : undefined}
          className={inputClass}
        />
        {mode === "signup" && (
          <p id="password-hint" className="mt-1.5 text-xs text-muted">
            At least 10 characters. A short phrase is easier to remember than random symbols.
          </p>
        )}
      </div>

      {error && (
        <p role="alert" className="rounded-sm bg-accent/10 px-4 py-3 text-sm text-accent-dark">
          {error}
        </p>
      )}

      <SubmitButton pending={isPending} label={mode === "signup" ? "Create account" : "Log in"} />

      <p className="text-center text-sm text-muted">
        {mode === "signup" ? "Already have an account?" : "New to Kora?"}{" "}
        <Link
          href={`/${mode === "signup" ? "login" : "signup"}${next ? `?next=${encodeURIComponent(next)}` : ""}`}
          className="font-medium text-ink underline underline-offset-4 hover:text-accent"
        >
          {mode === "signup" ? "Log in" : "Create an account"}
        </Link>
      </p>
    </form>
  );
}

function SubmitButton({ pending, label }: { pending: boolean; label: string }) {
  return (
    <button
      type="submit"
      disabled={pending}
      className="h-12 w-full rounded-full bg-ink text-sm font-medium text-paper transition hover:bg-accent disabled:bg-ink/40"
    >
      {pending ? "One moment…" : label}
    </button>
  );
}

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 429) return "Too many attempts. Please wait a minute and try again.";
    if (error.code === "validation_error") {
      if (error.message.startsWith("password")) return "Your password must be 10 to 128 characters.";
      if (error.message.startsWith("email")) return "Please enter a valid email address.";
      return "Please check the form and try again.";
    }
    return error.message; // our API's messages are written for people
  }
  return "Something went wrong. Check your connection and try again.";
}
