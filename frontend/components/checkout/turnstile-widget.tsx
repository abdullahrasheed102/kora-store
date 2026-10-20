"use client";

import Script from "next/script";
import { useEffect, useRef } from "react";

// The small part of Cloudflare's widget API we use (https://developers.cloudflare.com/turnstile/).
type TurnstileApi = {
  render: (container: HTMLElement, options: Record<string, unknown>) => string;
  reset: (widgetId: string) => void;
  remove: (widgetId: string) => void;
};

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

type Props = {
  siteKey: string;
  /** Called with a fresh token, or null when the token expires or the check fails. */
  onToken: (token: string | null) => void;
  /** Change this number to get a new token (each token works only once). */
  resetSignal: number;
};

/**
 * Cloudflare Turnstile: a bot check for guest checkout. Usually invisible; now and then it asks the
 * shopper to tick a box. It gives us a one-time token that the API checks with Cloudflare.
 */
export function TurnstileWidget({ siteKey, onToken, resetSignal }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const widgetId = useRef<string | null>(null);
  // Keep the latest callback without re-rendering the widget when the parent re-renders.
  const onTokenRef = useRef(onToken);
  useEffect(() => {
    onTokenRef.current = onToken;
  }, [onToken]);

  function renderWidget() {
    if (!window.turnstile || !container.current || widgetId.current) return;
    widgetId.current = window.turnstile.render(container.current, {
      sitekey: siteKey,
      action: "checkout", // the API refuses tokens made for any other action
      theme: "light",
      callback: (token: string) => onTokenRef.current(token),
      "expired-callback": () => onTokenRef.current(null), // tokens last 5 minutes
      "error-callback": () => onTokenRef.current(null),
    });
  }

  useEffect(() => {
    if (resetSignal > 0 && widgetId.current && window.turnstile) {
      window.turnstile.reset(widgetId.current);
      onTokenRef.current(null);
    }
  }, [resetSignal]);

  // Remove the widget when the form unmounts, so coming back renders a fresh one.
  useEffect(
    () => () => {
      if (widgetId.current && window.turnstile) window.turnstile.remove(widgetId.current);
      widgetId.current = null;
    },
    [],
  );

  return (
    <div>
      {/* render=explicit: we decide when and where the widget appears. onReady also fires when the
          script was already loaded by an earlier visit to this page. */}
      <Script
        src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit"
        strategy="afterInteractive"
        onReady={renderWidget}
      />
      <div ref={container} className="min-h-[65px]" aria-label="Security check" />
    </div>
  );
}
