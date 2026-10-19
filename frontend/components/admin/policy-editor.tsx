"use client";

import { useState } from "react";

import { buttonClass, inputClass } from "@/components/admin/ui";
import { api, ApiError } from "@/lib/api";
import type { Policy } from "@/lib/types";

export function PolicyEditor({ policy }: { policy: Policy }) {
  const [status, setStatus] = useState<string | null>(null);
  return (
    <form
      onSubmit={async (event) => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        setStatus(null);
        try {
          await api.admin.updatePolicy(policy.key, {
            title: String(form.get("title")),
            summary: String(form.get("summary") ?? ""),
            body: String(form.get("body")),
          });
          setStatus("Saved. The website shows the new text now.");
        } catch (caught) {
          setStatus(caught instanceof ApiError ? caught.message : "Something went wrong.");
        }
      }}
      className="space-y-3"
    >
      <div>
        <label htmlFor={`title-${policy.key}`} className="text-sm font-medium">Title</label>
        <input id={`title-${policy.key}`} name="title" defaultValue={policy.title} required maxLength={120} className={inputClass} />
      </div>
      <div>
        <label htmlFor={`summary-${policy.key}`} className="text-sm font-medium">Summary (one line)</label>
        <input id={`summary-${policy.key}`} name="summary" defaultValue={policy.summary ?? ""} maxLength={200} className={inputClass}
          aria-describedby={`summary-hint-${policy.key}`} />
        <p id={`summary-hint-${policy.key}`} className="mt-1 text-xs text-muted">
          Shown on the homepage for shipping, returns and support hours. Leave empty to hide it there.
        </p>
      </div>
      <div>
        <label htmlFor={`body-${policy.key}`} className="text-sm font-medium">Text</label>
        <textarea id={`body-${policy.key}`} name="body" defaultValue={policy.body} required rows={4} maxLength={5000}
          className={`${inputClass} h-auto py-2 leading-relaxed`} />
      </div>
      <div className="flex items-center gap-4">
        <button type="submit" className={buttonClass}>Save</button>
        {status && <p role="status" className="text-sm text-muted">{status}</p>}
      </div>
    </form>
  );
}
