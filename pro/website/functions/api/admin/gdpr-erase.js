import { getAffiliateSession, jsonResponse, normalizeEmail } from "../../_affiliate.js";
import { eraseCustomerByEmail, exportCustomerByEmail } from "../../_gdpr.js";

// Admin-gated GDPR subject endpoint (no customer accounts exist, so erasure is
// operator-triggered after out-of-band identity verification, per SECURITY.md).
//   POST { email, mode: "export" | "erase" }
export async function onRequestPost({ request, env }) {
  try {
    const session = await getAffiliateSession(request, env, "admin");
    if (!session) return jsonResponse({ error: "unauthorized" }, 401);

    const body = await request.json().catch(() => ({}));
    const email = normalizeEmail(body.email || "");
    if (!email) return jsonResponse({ error: "email_required" }, 400);
    const mode = body.mode === "erase" ? "erase" : "export";

    if (mode === "export") {
      const data = await exportCustomerByEmail(env.DB, email);
      return jsonResponse({ mode, ...data });
    }
    const result = await eraseCustomerByEmail(env.DB, email);
    return jsonResponse({ mode, erased: true, ...result });
  } catch (err) {
    return jsonResponse({ error: "gdpr_operation_failed", detail: String(err && err.message) }, 500);
  }
}
