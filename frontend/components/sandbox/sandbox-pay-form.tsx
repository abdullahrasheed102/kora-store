"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { api, ApiError } from "@/lib/api";
import { formatPrice } from "@/lib/format";

const inputClass =
  "mt-1.5 h-12 w-full rounded-md border border-ink/15 bg-white px-4 text-base tabular-nums focus:border-ink/50 focus:outline-none focus-visible:outline-2";

const TEST_CARDS = [
  { number: "4242 4242 4242 4242", label: "Succeeds" },
  { number: "4000 0000 0000 0002", label: "Declined" },
];

/** Groups digits in fours as you type: "4242424242424242" → "4242 4242 4242 4242". */
function formatCardNumber(value: string): string {
  return value.replace(/\D/g, "").slice(0, 19).replace(/(\d{4})(?=\d)/g, "$1 ");
}

function formatExpiry(value: string): string {
  const digits = value.replace(/\D/g, "").slice(0, 4);
  return digits.length > 2 ? `${digits.slice(0, 2)}/${digits.slice(2)}` : digits;
}

export function SandboxPayForm({ sessionId, total, defaultName }: { sessionId: string; total: number; defaultName: string }) {
  const router = useRouter();
  const [card, setCard] = useState({ card_number: "", expiry: "", cvc: "", name: defaultName });
  const [error, setError] = useState<string | null>(null);
  const [paying, setPaying] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPaying(true);
    try {
      const { redirect_url } = await api.sandboxPay(sessionId, card);
      // The order is already confirmed by the time we get here (the webhook ran on the server).
      router.push(new URL(redirect_url).pathname + new URL(redirect_url).search);
    } catch (caught) {
      setPaying(false);
      if (caught instanceof ApiError && caught.code === "card_declined") {
        // Like a real decline: back to checkout, nothing charged, bag untouched.
        router.push("/checkout?payment=declined");
        return;
      }
      if (caught instanceof ApiError && caught.code === "already_paid") {
        router.refresh();
        return;
      }
      setError(caught instanceof ApiError ? caught.message : "Something went wrong. Please try again.");
    }
  }

  return (
    // autoComplete="off": a fake payment page must never invite the browser to fill in a REAL card.
    <form onSubmit={submit} autoComplete="off" className="space-y-4">
      <div>
        <label htmlFor="card_number" className="text-sm font-medium">
          Card number
        </label>
        <input
          id="card_number"
          inputMode="numeric"
          autoComplete="off"
          placeholder="4242 4242 4242 4242"
          required
          value={card.card_number}
          onChange={(e) => setCard({ ...card, card_number: formatCardNumber(e.target.value) })}
          className={inputClass}
          aria-describedby="test-cards"
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label htmlFor="expiry" className="text-sm font-medium">
            Expiry (MM/YY)
          </label>
          <input
            id="expiry"
            inputMode="numeric"
            autoComplete="off"
            placeholder="12/34"
            required
            value={card.expiry}
            onChange={(e) => setCard({ ...card, expiry: formatExpiry(e.target.value) })}
            className={inputClass}
          />
        </div>
        <div>
          <label htmlFor="cvc" className="text-sm font-medium">
            CVC
          </label>
          <input
            id="cvc"
            inputMode="numeric"
            autoComplete="off"
            placeholder="123"
            required
            maxLength={4}
            value={card.cvc}
            onChange={(e) => setCard({ ...card, cvc: e.target.value.replace(/\D/g, "").slice(0, 4) })}
            className={inputClass}
          />
        </div>
      </div>
      <div>
        <label htmlFor="cardholder" className="text-sm font-medium">
          Name on card
        </label>
        <input
          id="cardholder"
          autoComplete="off"
          required
          value={card.name}
          onChange={(e) => setCard({ ...card, name: e.target.value })}
          className={inputClass}
        />
      </div>

      <div id="test-cards" className="rounded-md bg-sage/60 p-3 text-xs">
        <p className="font-medium">Test cards (any future expiry, any 3-digit CVC)</p>
        <ul className="mt-2 space-y-1.5">
          {TEST_CARDS.map((test) => (
            <li key={test.number} className="flex items-center justify-between gap-2">
              <span className="font-mono">{test.number}</span>
              <button
                type="button"
                onClick={() => setCard({ ...card, card_number: test.number, expiry: card.expiry || "12/34", cvc: card.cvc || "123" })}
                className="rounded-full border border-ink/20 px-2.5 py-1 hover:border-ink"
              >
                Use · {test.label}
              </button>
            </li>
          ))}
        </ul>
      </div>

      {error && (
        <p role="alert" className="rounded-md bg-accent/10 px-4 py-3 text-sm text-accent-dark">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={paying}
        className="h-13 w-full rounded-md bg-ink py-4 text-sm font-semibold text-paper transition hover:bg-accent disabled:bg-ink/40"
      >
        {paying ? "Processing…" : `Pay ${formatPrice(total)}`}
      </button>
    </form>
  );
}
