import { jsonResponse } from "../../_lib.js";
import { decidePlayRefund, isRefundAdmin, listPlayRefunds } from "../../_play_refunds.js";

function unauthorized() {
  return jsonResponse({ error: "unauthorized" }, 401, { "WWW-Authenticate": "Bearer" });
}

export async function onRequestGet({ request, env }) {
  if (!(await isRefundAdmin(request, env))) return unauthorized();
  return jsonResponse({ refunds: await listPlayRefunds(env) });
}

export async function onRequestPost({ request, env }) {
  if (!(await isRefundAdmin(request, env))) return unauthorized();
  let body;
  try {
    body = await request.json();
  } catch {
    return jsonResponse({ error: "invalid JSON" }, 400);
  }
  if (typeof body?.id !== "string" || !["approve", "reject"].includes(body?.action)) {
    return jsonResponse({ error: "id and action (approve/reject) are required" }, 400);
  }
  try {
    return jsonResponse(await decidePlayRefund(env, { id: body.id, approve: body.action === "approve" }));
  } catch (error) {
    return jsonResponse({ error: String(error?.message || error) }, error?.status || 500);
  }
}
