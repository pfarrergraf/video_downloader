import { jsonResponse } from "../../../_lib.js";
import { playPurchaseEligibility } from "../../../_play_purchase_eligibility.js";

export async function onRequestPost({ request, env }) {
  let body;
  try {
    body = await request.json();
  } catch {
    return jsonResponse({ error: "invalid JSON" }, 400);
  }
  try {
    return jsonResponse(await playPurchaseEligibility(env, body?.device_id));
  } catch (error) {
    return jsonResponse({ error: String(error?.message || error) }, error?.status || 500);
  }
}
