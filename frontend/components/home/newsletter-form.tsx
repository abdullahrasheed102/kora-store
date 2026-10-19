"use client";

import { useId, useState } from "react";

import { api, ApiError } from "@/lib/api";

type State =
  | { status: "idle" | "sending" }
  | { status: "done" | "error"; message: string };

export function NewsletterForm() {
  const [state, setState] = useState<State>({ status: "idle" });
  const id = useId();

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const email = String(
      new FormData(event.currentTarget).get("email") ?? "",
    ).trim();
    setState({ status: "sending" });
    try {
      const { message } = await api.newsletter(email);
      setState({ status: "done", message });
    } catch (caught) {
      let message = "Something went wrong. Please try again.";
      if (caught instanceof ApiError && caught.status === 429)
        message = "Too many attempts. Please try again in a minute.";
      else if (caught instanceof ApiError && caught.status === 400)
        message = "Please enter a valid email address.";
      setState({ status: "error", message });
    }
  }

  if (state.status === "done") {
    return (
      // Same height as the form (field + error line), so the page below doesn't jump when it's replaced.
      <p
        role="status"
        className="flex min-h-20 items-start justify-center pt-3 font-serif text-xl sm:justify-start"
      >
        {state.message}
      </p>
    );
  }

  return (
    <form onSubmit={submit} className="w-full">
      <div className="flex flex-col gap-3 sm:flex-row">
        <label htmlFor={id} className="sr-only">
          Email address
        </label>
        <input
          id={id}
          name="email"
          type="email"
          required
          maxLength={254}
          autoComplete="email"
          placeholder="you@example.com"
          aria-describedby={
            state.status === "error" ? `${id}-error` : undefined
          }
          aria-invalid={state.status === "error" || undefined}
          className="h-13 w-full min-w-0 rounded-full sm:flex-1 border border-line bg-card px-5 text-sm placeholder:text-muted/70 focus:border-ink"
        />
        <button
          type="submit"
          disabled={state.status === "sending"}
          className="h-13 shrink-0 rounded-full bg-ink px-7 text-sm font-medium text-paper transition-colors duration-300 hover:bg-accent disabled:bg-ink/50"
        >
          {state.status === "sending" ? "Subscribing…" : "Subscribe"}
        </button>
      </div>
      {/* Reserved space for the error, so showing it doesn't push the page down. */}
      <p
        id={`${id}-error`}
        role="alert"
        className="mt-2 min-h-5 text-sm text-accent-dark"
      >
        {state.status === "error" ? state.message : ""}
      </p>
    </form>
  );
}
