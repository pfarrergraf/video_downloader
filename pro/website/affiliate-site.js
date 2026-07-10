(() => {
  const STRIPE_LOCALE_MAP = {
    de: "de", es: "es", fr: "fr", pt: "pt", it: "it", nl: "nl", pl: "pl",
    ro: "ro", el: "el", cs: "cs", sv: "sv", da: "da", fi: "fi", no: "nb",
    hu: "hu", sk: "sk", bg: "bg", hr: "hr", lt: "lt", lv: "lv", et: "et",
    ru: "ru", tr: "tr", ja: "ja", ko: "ko", zh: "zh", vi: "vi", th: "th",
    id: "id", ms: "ms", fil: "fil", en: "en",
  };

  function currentLocale() {
    const stored = localStorage.getItem("dt_lang") || "auto";
    const code = stored === "auto" ? (navigator.language || "en").toLowerCase().split("-")[0] : stored;
    return STRIPE_LOCALE_MAP[code] || "auto";
  }

  function addPartnerCodeField() {
    const modalCard = document.querySelector("#withdrawal-modal .modal-card");
    if (!modalCard || document.getElementById("checkout-partner-code")) return;
    const wrapper = document.createElement("div");
    wrapper.style.cssText = "margin:0 0 16px";
    const label = document.createElement("label");
    label.htmlFor = "checkout-partner-code";
    label.textContent = "Partnercode (optional)";
    label.style.cssText = "display:block;color:var(--text-dim);font-size:.85rem;margin-bottom:6px";
    const input = document.createElement("input");
    input.id = "checkout-partner-code";
    input.autocomplete = "off";
    input.maxLength = 32;
    input.placeholder = "z. B. TECHNIKMAX";
    input.style.cssText = "width:100%;padding:11px 12px;border-radius:9px;border:1px solid var(--border);background:var(--bg);color:var(--text);font:inherit;text-transform:uppercase";
    wrapper.append(label, input);
    const firstChoice = modalCard.querySelector(".choice");
    modalCard.insertBefore(wrapper, firstChoice);
  }

  function blockCheckout(event) {
    event.preventDefault();
    event.stopImmediatePropagation();
    alert("Die Bezahlung ist noch nicht freigeschaltet. Das Partnerprogramm kann bereits getestet werden; die Kauf-Freigabe folgt separat.");
  }

  async function startCheckout(event, choice) {
    const anchor = event.currentTarget;
    event.preventDefault();
    event.stopImmediatePropagation();
    anchor.setAttribute("aria-busy", "true");
    anchor.style.pointerEvents = "none";
    const originalText = anchor.querySelector("span")?.textContent || "";
    if (anchor.querySelector("span")) anchor.querySelector("span").textContent = "Checkout wird geöffnet…";
    try {
      const response = await fetch("/api/create-checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          withdrawal_choice: choice,
          locale: currentLocale(),
          partner_code: document.getElementById("checkout-partner-code")?.value || "",
        }),
      });
      const data = await response.json();
      if (!response.ok || !data.url) throw new Error(data.error || "checkout_failed");
      location.href = data.url;
    } catch (error) {
      console.error("Affiliate-aware checkout failed", error);
      alert("Der Checkout konnte nicht gestartet werden. Bitte versuche es erneut.");
      anchor.style.pointerEvents = "";
      anchor.removeAttribute("aria-busy");
      if (anchor.querySelector("span")) anchor.querySelector("span").textContent = originalText;
    }
  }

  async function init() {
    const config = await fetch("/api/partner/config", { cache: "no-store" })
      .then((response) => response.json())
      .catch(() => ({ checkout_enabled: false }));
    const waived = document.getElementById("checkout-waive-btn");
    const wait = document.getElementById("checkout-wait-btn");

    if (!config.checkout_enabled) {
      waived?.addEventListener("click", blockCheckout, true);
      wait?.addEventListener("click", blockCheckout, true);
      return;
    }

    addPartnerCodeField();
    waived?.addEventListener("click", (event) => startCheckout(event, "waived"), true);
    wait?.addEventListener("click", (event) => startCheckout(event, "wait14"), true);

    const params = new URLSearchParams(location.search);
    if (params.get("buy") === "1") {
      document.getElementById("buy-license-btn")?.click();
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
