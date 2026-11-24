import { NextRequest } from "next/server";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
async function proxy(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  const target =
    (process.env.API_INTERNAL_URL || "http://127.0.0.1:8800") +
    "/api/" +
    path.map(encodeURIComponent).join("/") +
    request.nextUrl.search;
  const headers = new Headers();
  for (const key of ["authorization", "content-type"]) {
    const value = request.headers.get(key);
    if (value) headers.set(key, value);
  }
  try {
    const response = await fetch(target, {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method)
        ? undefined
        : await request.arrayBuffer(),
      cache: "no-store",
      signal: AbortSignal.timeout(180000),
    });
    const outputHeaders = new Headers({ "Cache-Control": "no-store" });
    for (const key of ["content-type", "content-disposition"]) {
      const value = response.headers.get(key);
      if (value) outputHeaders.set(key, value);
    }
    return new Response(response.body, {
      status: response.status,
      headers: outputHeaders,
    });
  } catch {
    return Response.json(
      {
        detail:
          "API unavailable. Start the Docker Compose stack and check API health.",
      },
      { status: 503 },
    );
  }
}
export { proxy as GET, proxy as POST, proxy as PUT, proxy as DELETE };
