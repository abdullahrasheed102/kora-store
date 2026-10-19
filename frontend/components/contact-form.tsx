"use client";

import { useState } from "react";

import { api, ApiError } from "@/lib/api";

const inputClass =
  "mt-1.5 h-12 w-full rounded-sm border border-line bg-card px-4 text-base focus:border-ink/50 focus:outline-none focus-visible:outline-2";

export function ContactForm() {
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  if (sent) {
    return (
      <div className="rounded-sm bg-sage p-6" role="status">
        <p className="font-serif text-2xl">Thanks, we&apos;ve got your message.</p>
        <p className="mt-2 text-sm">Our team replies Monday to Friday, 9am–6pm Eastern, usually within one business day.</p>
      </div>
    );
  }

  return (
    <form
      onSubmit={async (event) => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        const text = (name: string) => String(form.get(name) ?? "").trim();
        setError(null);
        setSending(true);
        try {
          await api.contact({
            name: text("name"),
            email: text("email"),
            order_number: text("order_number") || undefined,
            subject: text("subject"),
            message: text("message"),
          });
          setSent(true);
        } catch (caught) {
          setSending(false);
          setError(caught instanceof ApiError && caught.status === 429
            ? "You've sent several messages already. Please wait a while before sending another."
            : caught instanceof ApiError ? caught.message : "Something went wrong. Please try again.");
        }
      }}
      className="grid gap-4 sm:grid-cols-2"
    >
      <div>
        <label htmlFor="name" className="text-sm font-medium">Name</label>
        <input id="name" name="name" autoComplete="name" required maxLength={120} className={inputClass} />
      </div>
      <div>
        <label htmlFor="email" className="text-sm font-medium">Email</label>
        <input id="email" name="email" type="email" autoComplete="email" required className={inputClass} />
      </div>
      <div>
        <label htmlFor="order_number" className="text-sm font-medium">Order number (optional)</label>
        <input id="order_number" name="order_number" placeholder="KO-1005" maxLength={20} className={inputClass} />
      </div>
      <div>
        <label htmlFor="subject" className="text-sm font-medium">Subject</label>
        <input id="subject" name="subject" required maxLength={200} className={inputClass} />
      </div>
      <div className="sm:col-span-2">
        <label htmlFor="message" className="text-sm font-medium">Message</label>
        <textarea id="message" name="message" required minLength={10} maxLength={5000} rows={6} className={`${inputClass} h-auto py-3`} />
      </div>
      {error && <p role="alert" className="rounded-sm bg-accent/10 px-4 py-3 text-sm text-accent-dark sm:col-span-2">{error}</p>}
      <button type="submit" disabled={sending} className="h-12 w-fit rounded-full bg-ink px-8 text-sm font-medium text-paper hover:bg-accent disabled:bg-ink/40">
        {sending ? "Sending…" : "Send message"}
      </button>
    </form>
  );
}
