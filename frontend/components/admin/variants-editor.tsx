"use client";

import { useRouter } from "next/navigation";
import { useId, useState, useTransition } from "react";

import { buttonClass, inputClass, secondaryButtonClass } from "@/components/admin/ui";
import { api, ApiError } from "@/lib/api";
import { formatPrice } from "@/lib/format";
import type { AdminProduct, AdminVariant } from "@/lib/types";

export function VariantsEditor({ product }: { product: AdminProduct }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  async function run(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
      startTransition(() => router.refresh());
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Something went wrong.");
    }
  }

  return (
    <div className={isPending ? "opacity-60" : ""}>
      {error && <p role="alert" className="mb-3 rounded-sm bg-accent/10 px-3 py-2 text-sm text-accent-dark">{error}</p>}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Variants of {product.name}</caption>
          <thead className="border-b border-line text-xs uppercase tracking-widest text-muted">
            <tr>
              <th scope="col" className="py-2 pr-3 font-medium">SKU</th>
              <th scope="col" className="py-2 pr-3 font-medium">Colour / size</th>
              <th scope="col" className="py-2 pr-3 font-medium">Price</th>
              <th scope="col" className="py-2 pr-3 text-right font-medium">Stock</th>
              <th scope="col" className="py-2 font-medium">Adjust stock</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {product.variants.map((variant) => (
              <VariantRow key={variant.id} variant={variant} onRun={run} />
            ))}
          </tbody>
        </table>
      </div>
      <AddVariantForm productId={product.id} onRun={run} />
    </div>
  );
}

function VariantRow({ variant, onRun }: { variant: AdminVariant; onRun: (action: () => Promise<unknown>) => Promise<void> }) {
  const [change, setChange] = useState("");
  const amount = Number(change);
  return (
    <tr>
      <td className="py-2 pr-3 font-mono text-xs">{variant.sku}</td>
      <td className="py-2 pr-3">{variant.color} · {variant.size}</td>
      <td className="py-2 pr-3 tabular-nums">
        {formatPrice(variant.effective_price_cents)}
        {variant.price_cents !== null && <span className="ml-1 text-xs text-muted">(override)</span>}
      </td>
      <td className={`py-2 pr-3 text-right tabular-nums ${variant.stock === 0 ? "font-semibold text-accent-dark" : ""}`}>{variant.stock}</td>
      <td className="py-2">
        {/* A change, not a new total: a sale between loading this page and saving is never lost. */}
        <form
          className="flex items-center gap-2"
          onSubmit={async (event) => {
            event.preventDefault();
            if (!Number.isInteger(amount) || amount === 0) return;
            await onRun(() => api.admin.updateVariant(variant.id, { stock_change: amount }));
            setChange("");
          }}
        >
          <label htmlFor={`change-${variant.id}`} className="sr-only">Stock change for {variant.sku}</label>
          <input
            id={`change-${variant.id}`}
            type="number"
            step="1"
            value={change}
            onChange={(e) => setChange(e.target.value)}
            placeholder="+10 / -1"
            className="h-9 w-24 rounded-sm border border-line bg-paper px-2 text-sm"
          />
          <button type="submit" disabled={!amount} className={secondaryButtonClass}>Apply</button>
        </form>
      </td>
    </tr>
  );
}

function AddVariantForm({ productId, onRun }: { productId: number; onRun: (action: () => Promise<unknown>) => Promise<void> }) {
  const uid = useId();
  return (
    <form
      className="mt-6 grid gap-3 border-t border-line pt-4 sm:grid-cols-5 sm:items-end"
      onSubmit={async (event) => {
        event.preventDefault();
        const element = event.currentTarget;
        const form = new FormData(element);
        const price = String(form.get("price") ?? "").trim();
        await onRun(() =>
          api.admin.addVariant(productId, {
            sku: String(form.get("sku")).trim().toUpperCase(),
            size: String(form.get("size")).trim(),
            color: String(form.get("color")).trim(),
            stock: Number(form.get("stock") || 0),
            price_cents: price ? Math.round(Number(price) * 100) : null,
          }),
        );
        element.reset();
      }}
    >
      <p className="text-sm font-medium sm:col-span-5">Add a variant</p>
      {[
        { name: "sku", label: "SKU", placeholder: "KO-001-NAVY-M", required: true },
        { name: "color", label: "Colour", placeholder: "Navy", required: true },
        { name: "size", label: "Size", placeholder: "M", required: true },
        { name: "stock", label: "Stock", placeholder: "0", type: "number" },
        { name: "price", label: "Price override (USD)", placeholder: "optional", type: "number" },
      ].map((field) => (
        <div key={field.name}>
          <label htmlFor={`${uid}-${field.name}`} className="text-xs text-muted">{field.label}</label>
          <input id={`${uid}-${field.name}`} name={field.name} type={field.type ?? "text"} min={field.type ? 0 : undefined}
            step={field.name === "price" ? "0.01" : undefined} required={field.required} placeholder={field.placeholder} className={inputClass} />
        </div>
      ))}
      <button type="submit" className={`${buttonClass} sm:col-span-5 sm:w-fit`}>Add variant</button>
    </form>
  );
}
