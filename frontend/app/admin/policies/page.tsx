import type { Metadata } from "next";

import { PolicyEditor } from "@/components/admin/policy-editor";
import { AdminPageHeader, Card } from "@/components/admin/ui";
import { api } from "@/lib/api";

export const metadata: Metadata = { title: "Policies" };

export default async function AdminPoliciesPage() {
  const policies = await api.policies();
  return (
    <div>
      <AdminPageHeader
        title="Policies"
        description="This text is shown on the website and read by the AI assistant. The rules the system enforces (e.g. the 30-day return window) are code: change both together."
      />
      <div className="space-y-6">
        {policies.map((policy) => (
          <Card key={policy.key} title={policy.key}>
            <PolicyEditor policy={policy} />
          </Card>
        ))}
      </div>
    </div>
  );
}
