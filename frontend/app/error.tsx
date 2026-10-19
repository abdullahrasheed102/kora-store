"use client"; // error boundaries must be client components

import { useEffect } from "react";

// Shown when a page fails to render, e.g. the API is down or returned an unexpected error.
export default function ErrorPage({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="mx-auto max-w-xl px-4 py-24 text-center sm:px-6">
      <h1 className="font-serif text-4xl tracking-tight">Something went wrong</h1>
      <p className="mt-4 text-muted">
        We couldn&apos;t load this page. It&apos;s probably temporary — please try again in a moment.
      </p>
      <button
        type="button"
        onClick={() => retry()}
        className="mt-8 rounded-full bg-ink px-6 py-3 text-sm font-medium text-paper hover:bg-accent"
      >
        Try again
      </button>
    </div>
  );
}
