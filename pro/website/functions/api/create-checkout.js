import {
  affiliateProgramEnabled,
  createDynamicCheckout,
  jsonResponse,
} from "../_affiliate.js";

export async function onRequestPost({ request, env }) {
  try {
    if (!env.DB || !env.STRIPE_SECRET_KEY) {
      return jsonResponse({ error: "not_configured" }, 500);
    }
    if (!affiliateProgramEnabled(env)) {
      return jsonResponse({ error: "affiliate_program_disabled" }, 404);
    }
    const body = await request.json().catch(() => ({}));
    const result = await createDynamicCheckout(request, env, body);
    if (result.error) return jsonResponse({ error: result.error }, result.status || 400);
    return jsonResponse(result);
  } catch (error) {
    console.error("create-checkout failed", error);
    return jsonResponse({ error: "checkout_failed", message: String(error?.message || error) }, 500);
  }
}
