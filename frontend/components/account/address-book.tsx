"use client";

import { useRouter } from "next/navigation";
import { useId, useState, useTransition } from "react";

import { api, ApiError } from "@/lib/api";
import { COUNTRY_NAMES } from "@/lib/format";
import type { Address, AddressInput, Country } from "@/lib/types";

const inputClass =
  "mt-1.5 h-11 w-full rounded-sm border border-line bg-card px-3 text-base focus:border-ink/50 focus:outline-none focus-visible:outline-2";

/**
 * The list comes from the server as props. After each change we call router.refresh(), which
 * re-runs the server component and passes in the new list. No copy of the data lives here.
 */
export function AddressBook({ addresses }: { addresses: Address[] }) {
  const router = useRouter();
  const [editing, setEditing] = useState<number | "new" | null>(addresses.length === 0 ? "new" : null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  async function run(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
      setEditing(null);
      startTransition(() => router.refresh());
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Something went wrong. Please try again.");
    }
  }

  return (
    <div className={`space-y-6 ${isPending ? "opacity-60" : ""}`} aria-busy={isPending}>
      {error && (
        <p role="alert" className="rounded-sm bg-accent/10 px-4 py-3 text-sm text-accent-dark">
          {error}
        </p>
      )}

      <ul className="grid gap-4 sm:grid-cols-2">
        {addresses.map((address) =>
          editing === address.id ? (
            <li key={address.id} className="sm:col-span-2">
              <AddressForm
                initial={address}
                onCancel={() => setEditing(null)}
                onSubmit={(input) => run(() => api.updateAddress(address.id, input))}
              />
            </li>
          ) : (
            <li key={address.id} className="flex flex-col rounded-sm bg-card p-5 ring-1 ring-line">
              {address.is_default && (
                <span className="mb-2 w-fit rounded-full bg-sage px-2.5 py-1 text-xs font-medium">Default</span>
              )}
              <address className="flex-1 text-sm not-italic leading-relaxed">
                <span className="font-medium">{address.name}</span>
                <br />
                {address.line1}
                {address.line2 && <>, {address.line2}</>}
                <br />
                {address.city}
                {address.state && `, ${address.state}`} {address.postal_code}
                <br />
                {COUNTRY_NAMES[address.country]}
              </address>
              <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-sm">
                <button type="button" onClick={() => setEditing(address.id)} className="font-medium underline-offset-4 hover:underline">
                  Edit
                </button>
                {!address.is_default && (
                  <button
                    type="button"
                    onClick={() => run(() => api.updateAddress(address.id, { ...address, is_default: true }))}
                    className="underline-offset-4 hover:underline"
                  >
                    Make default
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => {
                    if (window.confirm("Delete this address?")) run(() => api.deleteAddress(address.id));
                  }}
                  className="text-muted underline-offset-4 hover:text-accent hover:underline"
                >
                  Delete
                </button>
              </div>
            </li>
          ),
        )}
      </ul>

      {editing === "new" ? (
        <AddressForm
          onCancel={addresses.length > 0 ? () => setEditing(null) : undefined}
          onSubmit={(input) => run(() => api.createAddress(input))}
        />
      ) : (
        <button
          type="button"
          onClick={() => setEditing("new")}
          className="rounded-full border border-ink/20 px-5 py-2.5 text-sm font-medium hover:border-ink"
        >
          Add an address
        </button>
      )}
    </div>
  );
}

function AddressForm({
  initial,
  onSubmit,
  onCancel,
}: {
  initial?: Address;
  onSubmit: (input: AddressInput) => Promise<void>;
  onCancel?: () => void;
}) {
  const [country, setCountry] = useState<Country>(initial?.country ?? "US");
  const [saving, setSaving] = useState(false);
  const field = (form: FormData, name: string) => String(form.get(name) ?? "").trim();

  return (
    <form
      // onSubmit, not <form action>: an action resets the fields, losing input when saving fails.
      onSubmit={async (event) => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        setSaving(true);
        await onSubmit({
          name: field(form, "name"),
          line1: field(form, "line1"),
          line2: field(form, "line2") || null,
          city: field(form, "city"),
          state: field(form, "state") || null,
          postal_code: field(form, "postal_code"),
          country,
          is_default: form.get("is_default") === "on",
        });
        setSaving(false);
      }}
      className="grid gap-4 rounded-sm bg-card p-5 ring-1 ring-line sm:grid-cols-2"
    >
      <h2 className="font-serif text-xl sm:col-span-2">{initial ? "Edit address" : "New address"}</h2>
      <Field label="Full name" name="name" autoComplete="name" defaultValue={initial?.name} className="sm:col-span-2" />
      <Field label="Address" name="line1" autoComplete="address-line1" defaultValue={initial?.line1} className="sm:col-span-2" />
      <Field
        label="Apartment, suite (optional)"
        name="line2"
        autoComplete="address-line2"
        defaultValue={initial?.line2 ?? ""}
        required={false}
        className="sm:col-span-2"
      />
      <Field label="City" name="city" autoComplete="address-level2" defaultValue={initial?.city} />
      <Field
        label={country === "US" ? "State" : "State / province (optional)"}
        name="state"
        autoComplete="address-level1"
        defaultValue={initial?.state ?? ""}
        required={country === "US"}
      />
      <Field label="Postal code" name="postal_code" autoComplete="postal-code" defaultValue={initial?.postal_code} />
      <div>
        <label htmlFor="country" className="text-sm font-medium">
          Country
        </label>
        <select
          id="country"
          name="country"
          autoComplete="country"
          value={country}
          onChange={(event) => setCountry(event.target.value as Country)}
          className={inputClass}
        >
          {Object.entries(COUNTRY_NAMES).map(([code, name]) => (
            <option key={code} value={code}>
              {name}
            </option>
          ))}
        </select>
      </div>
      {!initial?.is_default && (
        <label className="flex items-center gap-2 text-sm sm:col-span-2">
          <input type="checkbox" name="is_default" defaultChecked={false} className="size-4 accent-ink" />
          Make this my default address
        </label>
      )}
      <div className="flex gap-3 sm:col-span-2">
        <button
          type="submit"
          disabled={saving}
          className="rounded-full bg-ink px-6 py-2.5 text-sm font-medium text-paper hover:bg-accent disabled:bg-ink/40"
        >
          {saving ? "Saving…" : "Save address"}
        </button>
        {onCancel && (
          <button type="button" onClick={onCancel} className="px-4 py-2.5 text-sm underline-offset-4 hover:underline">
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}

function Field({
  label,
  name,
  defaultValue,
  autoComplete,
  required = true,
  className = "",
}: {
  label: string;
  name: string;
  defaultValue?: string;
  autoComplete: string;
  required?: boolean;
  className?: string;
}) {
  const id = useId();
  return (
    <div className={className}>
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <input id={id} name={name} defaultValue={defaultValue} autoComplete={autoComplete} required={required} className={inputClass} />
    </div>
  );
}
