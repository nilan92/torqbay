import { ApiError, apiFetch } from "@/api/client";

const originalFetch = global.fetch;

afterEach(() => {
  global.fetch = originalFetch;
});

function mockFetch(status: number, body: unknown, ok = status < 400) {
  const fn = jest.fn().mockResolvedValue({
    ok,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  });
  global.fetch = fn as unknown as typeof fetch;
  return fn;
}

test("prefixes the configured base URL", async () => {
  const fetchMock = mockFetch(200, { ok: true });

  await apiFetch("/api/v1/jobs");

  expect(fetchMock.mock.calls[0][0]).toBe("https://torqbay-api.flomonotio.com/api/v1/jobs");
});

test("sends the bearer token when given one", async () => {
  const fetchMock = mockFetch(200, {});

  await apiFetch("/api/v1/jobs", { token: "abc123" });

  const headers = fetchMock.mock.calls[0][1].headers;
  expect(headers.Authorization).toBe("Bearer abc123");
});

test("omits the Authorization header when there is no token", async () => {
  const fetchMock = mockFetch(200, {});

  await apiFetch("/api/v1/auth/login", { method: "POST", body: { email: "a@b.c" } });

  expect(fetchMock.mock.calls[0][1].headers.Authorization).toBeUndefined();
});

test("serializes a JSON body and sets the content type", async () => {
  const fetchMock = mockFetch(200, {});

  await apiFetch("/api/v1/customers", { method: "POST", body: { name: "Nimal" } });

  const init = fetchMock.mock.calls[0][1];
  expect(init.body).toBe(JSON.stringify({ name: "Nimal" }));
  expect(init.headers["Content-Type"]).toBe("application/json");
});

test("returns parsed JSON on success", async () => {
  mockFetch(200, { id: "job-1", title: "Brake service" });

  const result = await apiFetch<{ id: string; title: string }>("/api/v1/jobs/job-1");

  expect(result.title).toBe("Brake service");
});

test("throws ApiError carrying the status and the server detail", async () => {
  mockFetch(404, { detail: "Job not found" }, false);

  await expect(apiFetch("/api/v1/jobs/missing")).rejects.toMatchObject({
    status: 404,
    message: "Job not found",
  });
});

test("throws ApiError with a readable message when the body is not JSON", async () => {
  global.fetch = jest.fn().mockResolvedValue({
    ok: false,
    status: 500,
    json: async () => {
      throw new Error("not json");
    },
    text: async () => "<html>Server Error</html>",
  }) as unknown as typeof fetch;

  const error = (await apiFetch("/api/v1/jobs").catch((e) => e)) as ApiError;

  expect(error).toBeInstanceOf(ApiError);
  expect(error.status).toBe(500);
  expect(typeof error.message).toBe("string");
  expect(error.message.length).toBeGreaterThan(0);
});

test("surfaces a network failure as an ApiError with status 0", async () => {
  global.fetch = jest.fn().mockRejectedValue(new TypeError("Network request failed")) as
    unknown as typeof fetch;

  const error = (await apiFetch("/api/v1/jobs").catch((e) => e)) as ApiError;

  expect(error).toBeInstanceOf(ApiError);
  expect(error.status).toBe(0);
});
