"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { cartStore } from "@/lib/cart-store";

const POLL_EVERY_MS = 2000;
const MAX_POLLS = 15;

/**
 * Stripe redirects the shopper here at about the same moment it sends us the webhook, so the
 * order may still say "pending" for a second or two. We re-render the server component every
 * 2 seconds until the webhook has been processed.
 */
export function WaitForPayment() {
  const router = useRouter();
  const [gaveUp, setGaveUp] = useState(false);

  useEffect(() => {
    let polls = 0;
    const timer = setInterval(() => {
      polls += 1;
      if (polls > MAX_POLLS) {
        clearInterval(timer);
        setGaveUp(true);
        return;
      }
      router.refresh();
    }, POLL_EVERY_MS);
    return () => clearInterval(timer);
  }, [router]);

  return (
    <p className="text-sm text-muted" role="status">
      {gaveUp
        ? "This is taking longer than usual. You'll get an email as soon as your payment is confirmed. You can safely close this page."
        : "Confirming your payment with Stripe…"}
    </p>
  );
}

/** Empties the bag once the order is paid. */
export function ClearCart() {
  useEffect(() => {
    cartStore.setLines([]);
  }, []);
  return null;
}
