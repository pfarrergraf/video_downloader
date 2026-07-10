import {
  affiliateProgramEnabled,
  getAffiliateSession,
  jsonResponse,
  partnerDashboardData,
  publicBaseUrl,
} from "../../_affiliate.js";

export async function onRequestGet({ request, env }) {
  if (!affiliateProgramEnabled(env) || !env.DB) return jsonResponse({ error: "not_found" }, 404);
  const session = await getAffiliateSession(request, env, "partner");
  if (!session || session.affiliate_status !== "active") {
    return jsonResponse({ error: "unauthorized" }, 401);
  }
  const data = await partnerDashboardData(env, session.affiliate_id);
  if (!data) return jsonResponse({ error: "not_found" }, 404);
  const base = publicBaseUrl(request, env);
  data.links = {
    partner: `${base}/p/${data.affiliate.slug}`,
    buy: `${base}/p/${data.affiliate.slug}?buy=1`,
    claim: `${base}/claim/${data.affiliate.slug}`,
    code: data.affiliate.code,
  };
  return jsonResponse(data);
}
