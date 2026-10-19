"use client";

import { useRouter } from "next/navigation";
import { useId, useState } from "react";

import { buttonClass, inputClass } from "@/components/admin/ui";
import { api, ApiError } from "@/lib/api";
import { NAV_CATEGORIES } from "@/lib/site";
import type { AdminProduct, ProductInput } from "@/lib/types";

/** Create (no product) or edit (with product). Prices are typed in dollars, sent as cents. */
export function ProductForm({ product }: { product?: AdminProduct }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const categoryId = useId();

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const text = (name: string) => String(form.get(name) ?? "").trim();
    const optional = (name: string) => text(name) || null;
    const body: ProductInput = {
      name: text("name"),
      category: text("category"),
      description: text("description"),
      fit_notes: optional("fit_notes"),
      material_care: optional("material_care"),
      price_cents: Math.round(Number(text("price")) * 100), // dollars → integer cents
      is_final_sale: form.get("is_final_sale") === "on",
      restock_note: optional("restock_note"),
      image_url: optional("image_url"),
      is_active: form.get("is_active") === "on",
      // "new, autumn-edit" → ["new", "autumn-edit"]; the backend lowercases and checks them.
      tags: text("tags").split(",").map((tag) => tag.trim()).filter(Boolean),
    };
    setError(null);
    setSaved(false);
    setSaving(true);
    try {
      if (product) {
        await api.admin.updateProduct(product.id, body);
        setSaved(true);
        router.refresh();
      } else {
        const created = await api.admin.createProduct({ ...body, slug: text("slug") });
        router.push(`/admin/products/${created.id}`);
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Something went wrong.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
      <Field label="Name" name="name" defaultValue={product?.name} required />
      {product ? (
        <div>
          <p className="text-sm font-medium">Slug</p>
          <p className="mt-1.5 h-10 py-2 font-mono text-sm text-muted">{product.slug}</p>
        </div>
      ) : (
        <Field label="Slug (URL name)" name="slug" required pattern="[a-z0-9]+(-[a-z0-9]+)*" placeholder="linen-trousers"
          hint="Lowercase letters, numbers and hyphens. Can't be changed later." />
      )}
      <div>
        <label htmlFor={categoryId} className="text-sm font-medium">Category</label>
        <select id={categoryId} name="category" defaultValue={product?.category ?? "Tops"} className={inputClass}>
          {NAV_CATEGORIES.map((c) => <option key={c.slug} value={c.name}>{c.name}</option>)}
        </select>
      </div>
      <Field label="Price (USD)" name="price" type="number" step="0.01" min="0" required
        defaultValue={product ? (product.price_cents / 100).toFixed(2) : undefined} />
      <TextArea label="Description" name="description" defaultValue={product?.description} required className="sm:col-span-2" />
      <TextArea label="Fit notes" name="fit_notes" defaultValue={product?.fit_notes ?? ""} />
      <TextArea label="Material & care" name="material_care" defaultValue={product?.material_care ?? ""} />
      <Field label="Restock note" name="restock_note" defaultValue={product?.restock_note ?? ""} placeholder="Restock expected in about 3 weeks" />
      <Field label="Image URL (https)" name="image_url" type="url" defaultValue={product?.image_url ?? ""} placeholder="https://…" />
      <Field label="Tags" name="tags" defaultValue={product?.tags.join(", ") ?? ""} placeholder="new, autumn-edit"
        hint="Comma-separated. Homepage sections use: new (New for autumn), autumn-edit (The Autumn Edit), bestseller."
        className="sm:col-span-2" />
      <div className="flex flex-wrap gap-6 sm:col-span-2">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" name="is_active" defaultChecked={product?.is_active ?? true} className="size-4 accent-ink" />
          Active (visible in the shop)
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" name="is_final_sale" defaultChecked={product?.is_final_sale ?? false} className="size-4 accent-ink" />
          Final sale (can&apos;t be returned)
        </label>
      </div>
      {error && <p role="alert" className="rounded-sm bg-accent/10 px-3 py-2 text-sm text-accent-dark sm:col-span-2">{error}</p>}
      <div className="flex items-center gap-4 sm:col-span-2">
        <button type="submit" disabled={saving} className={buttonClass}>{product ? "Save changes" : "Create product"}</button>
        {saved && <p role="status" className="text-sm text-muted">Saved.</p>}
      </div>
    </form>
  );
}

// useId: unique ids per component instance. Next keeps the previous page mounted (hidden) after a
// client navigation, so two pages with a plain id="name" would both label the same input.
function Field({ label, name, hint, className, ...props }: { label: string; name: string; hint?: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  const id = useId();
  return (
    <div className={className}>
      <label htmlFor={id} className="text-sm font-medium">{label}</label>
      <input id={id} name={name} className={inputClass} {...props} />
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </div>
  );
}

function TextArea({ label, name, className = "", ...props }: { label: string; name: string; className?: string } & React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const id = useId();
  return (
    <div className={className}>
      <label htmlFor={id} className="text-sm font-medium">{label}</label>
      <textarea id={id} name={name} rows={3} className={`${inputClass} h-auto py-2`} {...props} />
    </div>
  );
}
