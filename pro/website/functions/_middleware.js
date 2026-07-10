export async function onRequest(context) {
  const response = await context.next();
  const url = new URL(context.request.url);
  const contentType = response.headers.get("Content-Type") || "";
  if (!contentType.includes("text/html") || !["/", "/index.html"].includes(url.pathname)) {
    return response;
  }

  return new HTMLRewriter()
    .on("nav.links", {
      element(element) {
        element.append('<a href="/partner.html">Partner werden</a>', { html: true });
      },
    })
    .on("footer .foot-links", {
      element(element) {
        element.append('<a href="/partner.html">Partnerprogramm</a>', { html: true });
      },
    })
    .on("body", {
      element(element) {
        element.append('<script src="/affiliate-site.js" defer></script>', { html: true });
      },
    })
    .transform(response);
}
