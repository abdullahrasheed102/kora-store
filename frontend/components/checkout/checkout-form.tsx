"use client";

import Link from "next/link";
import { useId, useState } from "react";

import { useCart } from "@/components/cart/cart-provider";
import { CartTotals } from "@/components/cart/cart-totals";
import { LinePhoto } from "@/components/cart/line-photo";
import { TurnstileWidget } from "@/components/checkout/turnstile-widget";
import { api, ApiError } from "@/lib/api";
import { COUNTRY_NAMES, formatPrice, SHIPPING_LABELS } from "@/lib/format";
import type { Address, AddressInput, Country, PaymentMethod, ShippingMethod, User } from "@/lib/types";

const inputClass =
  "mt-1.5 h-12 w-full rounded-sm border border-line bg-card px-4 text-base focus:border-ink/50 focus:outline-none focus-visible:outline-2";

const NEW_ADDRESS = "new";

/** Shipping methods allowed for a country (shipping policy). */
function methodsFor(country: Country): ShippingMethod[] {
  return country === "US" ? ["standard", "express"] : ["international"];
}

type Props = {
  user: User | null;
  addresses: Address[];
  cancelled: boolean;
  declined: boolean;
  /** Set for guests only: they must pass Cloudflare Turnstile before ordering. */
  turnstileSiteKey?: string | null;
};

export function CheckoutForm({ user, addresses, cancelled, declined, turnstileSiteKey }: Props) {
  const { lines, quote, isUpdating, count, shippingMethod, setShippingMethod } = useCart();
  const defaultAddress = addresses.find((address) => address.is_default) ?? addresses[0];
  const [addressChoice, setAddressChoice] = useState<string>(defaultAddress ? String(defaultAddress.id) : NEW_ADDRESS);
  const [country, setCountry] = useState<Country>(defaultAddress?.country ?? "US");
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("card");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [botToken, setBotToken] = useState<string | null>(null);
  const [botReset, setBotReset] = useState(0);
  const needsBotCheck = !user && Boolean(turnstileSiteKey);
  const phoneId = useId();

  const chooseCountry = (next: Country) => {
    setCountry(next);
    // Keep the shipping and payment methods valid for the country, in the same event (no effect needed).
    if (!methodsFor(next).includes(shippingMethod)) setShippingMethod(methodsFor(next)[0]);
    if (next !== "US") setPaymentMethod("card"); // cash on delivery is for US addresses only
  };

  if (count === 0) {
    return (
      <div className="rounded-sm border border-dashed border-line px-6 py-20 text-center">
        <p className="font-serif text-2xl">Your bag is empty</p>
        <Link href="/shop" className="mt-6 inline-block rounded-full bg-ink px-6 py-3 text-sm font-medium text-paper hover:bg-accent">
          Start shopping
        </Link>
      </div>
    );
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const form = new FormData(event.currentTarget);
    const field = (name: string) => String(form.get(name) ?? "").trim();

    const saved = addresses.find((address) => String(address.id) === addressChoice);
    const address: AddressInput = saved
      ? { ...saved, is_default: false }
      : {
          name: field("name"),
          line1: field("line1"),
          line2: field("line2") || null,
          city: field("city"),
          state: field("state") || null,
          postal_code: field("postal_code"),
          country,
          is_default: false,
        };

    setSubmitting(true);
    try {
      const body = {
        email: user ? undefined : field("email"),
        address,
        shipping_method: shippingMethod,
        items: lines.map((line) => ({ variant_id: line.variantId, quantity: line.quantity })),
        save_address: !saved && form.get("save_address") === "on",
        turnstile_token: needsBotCheck ? (botToken ?? undefined) : undefined,
      };
      // Card: leave for the hosted payment page (card details never touch our servers).
      // Cash on delivery: the order is placed now, and we go straight to the thank-you page.
      const { checkout_url } =
        paymentMethod === "cod" ? await api.createCodOrder({ ...body, phone: field("phone") }) : await api.createCheckout(body);
      window.location.assign(checkout_url);
    } catch (caught) {
      setSubmitting(false);
      // A token works only once, and the API may have used it before refusing the order.
      if (needsBotCheck) setBotReset((count) => count + 1);
      const codLimit = paymentMethod === "cod" && caught instanceof ApiError && caught.status === 429;
      // COD orders are limited per hour (fake orders would hold stock), so "wait a minute" would be wrong.
      setError(codLimit ? "Too many cash on delivery orders from this connection. Please try later, or pay by card." : messageFor(caught));
    }
  }

  const usingSaved = addressChoice !== NEW_ADDRESS;
  const selectedCountry = usingSaved ? (addresses.find((a) => String(a.id) === addressChoice)?.country ?? "US") : country;
  const issues = quote?.has_issues ?? false;

  return (
    <form onSubmit={submit} className="grid gap-12 lg:grid-cols-[1fr_400px]">
      <div className="space-y-10">
        {declined && (
          <p className="rounded-sm bg-accent/10 px-4 py-3 text-sm text-accent-dark" role="alert">
            Your card was declined, so nothing was charged. Check your details or try another card.
          </p>
        )}
        {cancelled && (
          <p className="rounded-sm bg-sage px-4 py-3 text-sm" role="status">
            Payment was cancelled. Nothing was charged, and your bag is still here.
          </p>
        )}

        <section aria-labelledby="contact-heading">
          <h2 id="contact-heading" className="font-serif text-2xl">
            Contact
          </h2>
          {user ? (
            <p className="mt-3 text-sm">
              Ordering as <span className="font-medium">{user.email}</span>. We&apos;ll email your receipt here.
            </p>
          ) : (
            <div className="mt-4">
              <label htmlFor="email" className="text-sm font-medium">
                Email
              </label>
              <input id="email" name="email" type="email" autoComplete="email" required className={inputClass} />
              <p className="mt-1.5 text-xs text-muted">
                For your receipt and order updates.{" "}
                <Link href="/login?next=/checkout" className="underline underline-offset-2">
                  Log in
                </Link>{" "}
                to use saved addresses.
              </p>
            </div>
          )}
        </section>

        <section aria-labelledby="address-heading">
          <h2 id="address-heading" className="font-serif text-2xl">
            Shipping address
          </h2>
          {addresses.length > 0 && (
            <fieldset className="mt-4 space-y-2">
              <legend className="sr-only">Choose an address</legend>
              {addresses.map((address) => (
                <label key={address.id} className="flex cursor-pointer gap-3 rounded-sm border border-line bg-card p-4 has-[:checked]:border-ink">
                  <input
                    type="radio"
                    name="address_choice"
                    checked={addressChoice === String(address.id)}
                    onChange={() => {
                      setAddressChoice(String(address.id));
                      chooseCountry(address.country);
                    }}
                    className="mt-1 size-4 accent-ink"
                  />
                  <span className="text-sm leading-relaxed">
                    <span className="font-medium">{address.name}</span> · {address.line1}, {address.city}
                    {address.state && `, ${address.state}`} {address.postal_code}, {COUNTRY_NAMES[address.country]}
                  </span>
                </label>
              ))}
              <label className="flex cursor-pointer gap-3 rounded-sm border border-line bg-card p-4 has-[:checked]:border-ink">
                <input
                  type="radio"
                  name="address_choice"
                  checked={addressChoice === NEW_ADDRESS}
                  onChange={() => setAddressChoice(NEW_ADDRESS)}
                  className="mt-1 size-4 accent-ink"
                />
                <span className="text-sm font-medium">Use a new address</span>
              </label>
            </fieldset>
          )}

          {!usingSaved && (
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <Field label="Full name" name="name" autoComplete="name" className="sm:col-span-2" defaultValue={user?.name} />
              <Field label="Address" name="line1" autoComplete="address-line1" className="sm:col-span-2" />
              <Field label="Apartment, suite (optional)" name="line2" autoComplete="address-line2" required={false} className="sm:col-span-2" />
              <Field label="City" name="city" autoComplete="address-level2" />
              <Field
                label={country === "US" ? "State" : "State / province (optional)"}
                name="state"
                autoComplete="address-level1"
                required={country === "US"}
              />
              <Field label="Postal code" name="postal_code" autoComplete="postal-code" />
              <div>
                <label htmlFor="country" className="text-sm font-medium">
                  Country
                </label>
                <select
                  id="country"
                  autoComplete="country"
                  value={country}
                  onChange={(event) => chooseCountry(event.target.value as Country)}
                  className={inputClass}
                >
                  {Object.entries(COUNTRY_NAMES).map(([code, name]) => (
                    <option key={code} value={code}>
                      {name}
                    </option>
                  ))}
                </select>
              </div>
              {user && (
                <label className="flex items-center gap-2 text-sm sm:col-span-2">
                  <input type="checkbox" name="save_address" className="size-4 accent-ink" />
                  Save this address to my account
                </label>
              )}
            </div>
          )}
        </section>

        <fieldset>
          <legend className="font-serif text-2xl">Shipping method</legend>
          <div className="mt-4 space-y-2">
            {methodsFor(selectedCountry).map((method) => (
              <label key={method} className="flex cursor-pointer items-start gap-3 rounded-sm border border-line bg-card p-4 has-[:checked]:border-ink">
                <input
                  type="radio"
                  name="shipping_method"
                  checked={shippingMethod === method}
                  onChange={() => setShippingMethod(method)}
                  className="mt-1 size-4 accent-ink"
                />
                <span className="text-sm">
                  <span className="font-medium">{SHIPPING_LABELS[method].label}</span>
                  <span className="block text-muted">{SHIPPING_LABELS[method].detail}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset>
          <legend className="font-serif text-2xl">Payment</legend>
          {/* The one place the demo is spelled out: right where a shopper decides to pay. */}
          <p role="note" className="mt-4 rounded-sm border border-accent/30 bg-accent/5 px-4 py-3 text-sm leading-relaxed text-ink">
            This is a portfolio demonstration store. No real payments are taken and no orders are shipped.
          </p>
          <div className="mt-4 space-y-2">
            {PAYMENT_OPTIONS.map((option) => {
              const unavailable = option.method === "cod" && selectedCountry !== "US";
              return (
                <label
                  key={option.method}
                  className={`flex items-start gap-3 rounded-sm border border-line bg-card p-4 has-[:checked]:border-ink ${unavailable ? "cursor-not-allowed opacity-60" : "cursor-pointer"}`}
                >
                  <input
                    type="radio"
                    name="payment_method"
                    checked={paymentMethod === option.method}
                    disabled={unavailable}
                    onChange={() => setPaymentMethod(option.method)}
                    className="mt-1 size-4 accent-ink"
                  />
                  <span className="text-sm">
                    <span className="font-medium">{option.label}</span>
                    <span className="block text-muted">{unavailable ? "Available for US addresses only." : option.detail}</span>
                  </span>
                </label>
              );
            })}
          </div>
          {paymentMethod === "cod" && (
            <div className="mt-4">
              <label htmlFor={phoneId} className="text-sm font-medium">
                Phone number
              </label>
              <input
                id={phoneId}
                name="phone"
                type="tel"
                autoComplete="tel"
                required
                inputMode="tel"
                maxLength={30}
                aria-describedby={`${phoneId}-hint`}
                className={inputClass}
              />
              <p id={`${phoneId}-hint`} className="mt-1.5 text-xs text-muted">
                The courier calls this number before delivery. Have the exact amount ready in cash.
              </p>
            </div>
          )}
        </fieldset>
      </div>

      <aside aria-label="Order summary" className="h-fit space-y-6 rounded-sm bg-card p-6 ring-1 ring-line lg:sticky lg:top-32">
        <h2 className="font-serif text-2xl">Order summary</h2>
        <ul className="space-y-4">
          {quote?.items
            .filter((item) => item.product_slug)
            .map((item) => (
              <li key={item.variant_id} className="flex gap-3 text-sm">
                <div className="relative shrink-0">
                  <LinePhoto item={item} sizes="56px" className="aspect-square w-14" />
                  <span className="absolute -right-1.5 -top-1.5 flex size-5 items-center justify-center rounded-full bg-ink text-[10px] text-paper">
                    {item.quantity}
                  </span>
                </div>
                <div className="flex-1">
                  <p className="font-medium">{item.product_name}</p>
                  <p className="text-muted">
                    {item.color} · {item.size}
                  </p>
                </div>
                <p>{formatPrice(item.line_total_cents)}</p>
              </li>
            ))}
        </ul>
        <CartTotals />
        {issues && (
          <p className="text-sm text-accent" role="alert">
            Some items changed. <Link href="/cart" className="underline">Review your bag</Link> before paying.
          </p>
        )}
        {error && (
          <p className="rounded-sm bg-accent/10 px-4 py-3 text-sm text-accent-dark" role="alert">
            {error}
          </p>
        )}
        {needsBotCheck && turnstileSiteKey && (
          <TurnstileWidget siteKey={turnstileSiteKey} onToken={setBotToken} resetSignal={botReset} />
        )}
        <button
          type="submit"
          disabled={submitting || isUpdating || issues || !quote || (needsBotCheck && !botToken)}
          className="h-14 w-full rounded-full bg-ink text-sm font-medium text-paper transition hover:bg-accent disabled:cursor-not-allowed disabled:bg-ink/30"
        >
          {buttonLabel(paymentMethod, submitting, quote?.total_cents)}
        </button>
        <p className="text-center text-xs leading-relaxed text-muted">
          {paymentMethod === "cod"
            ? "You'll pay in cash when your order arrives."
            : "You'll pay on a secure hosted payment page. Use test card 4242 4242 4242 4242, any future date and any CVC."}
        </p>
      </aside>
    </form>
  );
}

const PAYMENT_OPTIONS: { method: PaymentMethod; label: string; detail: string }[] = [
  { method: "card", label: "Card", detail: "Pay securely on the next page." },
  { method: "cod", label: "Cash on delivery", detail: "Pay the courier in cash when your order arrives." },
];

function buttonLabel(method: PaymentMethod, submitting: boolean, totalCents: number | undefined): string {
  if (method === "cod") {
    if (submitting) return "Placing your order…";
    return totalCents === undefined ? "Place order" : `Place order · ${formatPrice(totalCents)}`;
  }
  if (submitting) return "Redirecting to secure payment…";
  return totalCents === undefined ? "Pay" : `Pay ${formatPrice(totalCents)}`;
}

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code.startsWith("bot_check")) return `${error.message} The check has been reset above.`;
    if (error.code === "cart_changed") return "Some items in your bag changed. Please review your bag and try again.";
    if (error.code === "payments_not_configured") return "Payments aren't set up on this server yet.";
    if (error.status === 429) return "Too many attempts. Please wait a minute and try again.";
    if (error.code === "validation_error") return `Please check the form: ${error.message.split(": ").slice(1).join(": ")}`;
    return error.message;
  }
  return "Something went wrong. Check your connection and try again.";
}

function Field({
  label,
  name,
  autoComplete,
  required = true,
  className = "",
  defaultValue,
}: {
  label: string;
  name: string;
  autoComplete: string;
  required?: boolean;
  className?: string;
  defaultValue?: string;
}) {
  const id = useId();
  return (
    <div className={className}>
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <input id={id} name={name} autoComplete={autoComplete} required={required} defaultValue={defaultValue} className={inputClass} />
    </div>
  );
}
