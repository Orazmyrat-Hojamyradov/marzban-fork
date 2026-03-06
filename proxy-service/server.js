// server.js
Deno.serve({ hostname: "0.0.0.0", port: 3000 }, async (request) => {
  const url = new URL(request.url);
  const targetUrl = url.searchParams.get("url");
  const format = url.searchParams.get("format"); // optional: json

  if (!targetUrl) {
    return new Response(JSON.stringify({ error: "Missing 'url' parameter" }), {
      status: 400,
      headers: { "content-type": "application/json" },
    });
  }

  try {
    // Headers to skip when forwarding REQUEST to upstream
    const skipRequestHeaders = new Set([
      "host", "connection", "te", "trailers", "transfer-encoding", "upgrade",
      "accept-encoding",  // Deno fetch handles its own encoding
      "content-length",   // wrong for proxied request
      "content-type",     // not relevant for GET sub requests
    ]);

    const forwardHeaders = {};
    request.headers.forEach((v, k) => {
      if (!skipRequestHeaders.has(k)) {
        forwardHeaders[k] = v;
      }
    });

    console.log(`\n[${new Date().toISOString()}] ${request.method} → ${targetUrl}`);
    console.log("ALL RAW CLIENT HEADERS:");
    request.headers.forEach((v, k) => console.log(`  [RAW] ${k}: ${v}`));
    console.log(`x-hwid specifically: "${request.headers.get("x-hwid")}"`);
    console.log("FORWARDED REQUEST HEADERS:");
    for (const [k, v] of Object.entries(forwardHeaders)) {
      console.log(`  ${k}: ${v}`);
    }

    const response = await fetch(targetUrl, { redirect: "follow", headers: forwardHeaders });
    const content = await response.text();

    console.log(`UPSTREAM STATUS: ${response.status}`);
    console.log("UPSTREAM RESPONSE HEADERS:");
    response.headers.forEach((v, k) => console.log(`  ${k}: ${v}`));

    if (format === "json") {
      const headers = {};
      response.headers.forEach((v, k) => (headers[k] = v));
      return new Response(JSON.stringify({ headers, statusCode: response.status, content }, null, 2), {
        headers: { "content-type": "application/json", "access-control-allow-origin": "*" },
      });
    }

    // Headers to skip when forwarding RESPONSE to client
    // Deno auto-decompresses, so content-encoding/content-length are stale
    const skipResponseHeaders = new Set([
      "content-encoding",
      "content-length",
      "transfer-encoding",
    ]);

    const responseHeaders = {};
    response.headers.forEach((v, k) => {
      if (!skipResponseHeaders.has(k)) {
        responseHeaders[k] = v;
      }
    });
    responseHeaders["access-control-allow-origin"] = "*";
    responseHeaders["access-control-expose-headers"] = "*";

    console.log(`RESPONSE TO CLIENT: ${response.status}, body length: ${content.length}`);

    return new Response(content, { status: response.status, headers: responseHeaders });
  } catch (err) {
    console.error("Error:", err);
    return new Response(JSON.stringify({ error: err.toString() }), {
      status: 500,
      headers: { "content-type": "application/json" },
    });
  }
});

console.log("Deno proxy running on 0.0.0.0:3000");
