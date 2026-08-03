# Mobile Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A running Expo app you can open on a phone, log into against the live production API, and see real data from your own workshop.

**Architecture:** Expo + Expo Router (file-based routing) in `mobile/`, alongside the existing `backend/`. Types are generated from the backend's live OpenAPI schema so requests stay in sync with the API automatically. Tokens live in `expo-secure-store`; server state is TanStack Query; styling is inline styles over a small token file.

**Tech Stack:** Expo SDK 54+, TypeScript, Expo Router, TanStack Query, expo-secure-store, openapi-typescript, jest-expo.

## Global Constraints

- **Styling is inline styles + the `Color` API from `expo-router`.** No Tailwind, no NativeWind, no `StyleSheet.create` unless a style is genuinely reused. This overrides `docs/02-architecture.md`, which specifies NativeWind — that decision was reversed because NativeWind v5 requires preview and nightly dependencies plus four config files, and the foundation needs to be boring and reliable. Update that doc when this ships.
- **File names are kebab-case.** `job-card.tsx`, never `JobCard.tsx`.
- **Use path aliases (`@/`), not relative imports** across directories.
- `process.env.EXPO_OS`, never `Platform.OS`, when branching on platform in app code. (`Platform.select` in the theme file is fine and is the documented pattern.)
- Never import from `@react-navigation/*` directly — use `expo-router` exports.
- Use `expo-image` for images, never an `img` element or `@expo/vector-icons`.
- Screens inside a Stack start with a `ScrollView`/`FlatList` carrying `contentInsetAdjustmentBehavior="automatic"`, never `SafeAreaView`.
- Use `useWindowDimensions`, never `Dimensions.get()`.
- Prefer flex `gap` over margins.
- Use `{ borderCurve: 'continuous' }` on rounded corners that aren't capsules.
- Use CSS `boxShadow`, never legacy `shadowOffset`/`elevation`.
- Add `selectable` to any `<Text>` showing data or an error.
- **The API base URL comes from `process.env.EXPO_PUBLIC_API_URL`.** It must never be hardcoded in a component.
- Run tests with `cd mobile && npm test`.
- Everything must work in **Expo Go**. Do not add a dependency requiring a custom native build.

## Visual direction

The subject is a working auto-repair shop: bright sunlight, dirty hands, a phone checked between jobs. The artifact this app replaces is the **job card** — the physical card that follows a vehicle around the shop. That's the organising metaphor: the job list is a stack of cards, and status reads like a tag clipped to one.

Chrome (backgrounds, separators, body text) uses **native semantic colors** so the app adapts to light/dark and accessibility settings for free. Identity and status use a **small fixed palette**, because job status is functional information that must be distinguishable at a glance in sunlight, not decoration:

| Token | Light | Dark | Role |
|---|---|---|---|
| `brand` | `#0F4C5C` | `#2A8FA6` | Petrol blue — workshop enamel and toolboxes. Primary actions. |
| `accent` | `#F4A208` | `#FFB627` | Hi-vis amber — attention, in-progress, low stock. |
| `statusOpen` | `#6B7280` | `#9CA3AF` | Not started |
| `statusProgress` | `#F4A208` | `#FFB627` | Being worked on |
| `statusDone` | `#2F9E44` | `#51CF66` | Work finished |
| `statusInvoiced` | `#0F4C5C` | `#2A8FA6` | Billed |
| `statusPaid` | `#1B7F3B` | `#40C057` | Settled |
| `danger` | `#C92A2A` | `#FF6B6B` | Destructive, overdue |

Type is the system face at a deliberate scale — no custom font files in the foundation (they cost load time and a config step for no benefit yet). Numbers that appear in columns use `fontVariant: ['tabular-nums']`.

**Deferred to the screens plan, not built here:** status-change animations, haptics, empty-state illustrations. The foundation establishes tokens and plumbing; personality goes on the screens that earn it.

---

### Task 1: Expo app scaffold

**Files:**
- Create: `mobile/` (via `create-expo-app`)
- Modify: `mobile/package.json`, `mobile/tsconfig.json`, `mobile/app.json`
- Modify: `.gitignore`

**Interfaces:**
- Produces: a running Expo Router app with TypeScript and the `@/` path alias

- [ ] **Step 1: Scaffold the app**

From the repository root:

```bash
npx create-expo-app@latest mobile --template blank-typescript
```

- [ ] **Step 2: Add Expo Router and its peers**

```bash
cd mobile
npx expo install expo-router react-native-safe-area-context react-native-screens expo-linking expo-constants expo-status-bar
```

- [ ] **Step 3: Switch the entry point to Expo Router**

In `mobile/package.json`, set:

```json
"main": "expo-router/entry"
```

Delete `mobile/App.tsx` — Expo Router uses the `app/` directory instead.

In `mobile/app.json`, inside the `expo` object, add the scheme Expo Router needs for deep links:

```json
"scheme": "torqbay"
```

- [ ] **Step 4: Configure the path alias**

Replace `mobile/tsconfig.json` with:

```json
{
  "extends": "expo/tsconfig.base",
  "compilerOptions": {
    "strict": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  },
  "include": ["**/*.ts", "**/*.tsx", ".expo/types/**/*.ts", "expo-env.d.ts"]
}
```

Create `mobile/src/` — all non-route code lives there; `mobile/app/` holds routes only.

- [ ] **Step 5: Create a placeholder route so the app boots**

Create `mobile/app/_layout.tsx`:

```tsx
import { Stack } from "expo-router";

export default function RootLayout() {
  return <Stack />;
}
```

Create `mobile/app/index.tsx`:

```tsx
import { ScrollView, Text } from "react-native";

export default function Index() {
  return (
    <ScrollView contentInsetAdjustmentBehavior="automatic" contentContainerStyle={{ padding: 16 }}>
      <Text>Torqbay</Text>
    </ScrollView>
  );
}
```

- [ ] **Step 6: Ignore build artifacts**

Append to the repository-root `.gitignore`:

```
# Expo / React Native
mobile/node_modules/
mobile/.expo/
mobile/dist/
mobile/ios/
mobile/android/
mobile/*.log
```

- [ ] **Step 7: Verify it type-checks and starts**

```bash
cd mobile && npx tsc --noEmit
```
Expected: no errors.

```bash
cd mobile && npx expo start
```
Expected: Metro starts and prints a QR code. Stop it with `q` once confirmed — do not leave it running.

- [ ] **Step 8: Commit**

```bash
git add mobile .gitignore
git commit -m "feat(mobile): scaffold Expo Router app with TypeScript"
```

---

### Task 2: Theme tokens

**Files:**
- Create: `mobile/src/theme/colors.ts`
- Create: `mobile/src/theme/type.ts`
- Create: `mobile/src/theme/layout.ts`

**Interfaces:**
- Produces: `colors`, `statusColor(status)`, `type`, `spacing`, `radius` — every later task imports these instead of writing raw values

Chrome uses native semantic colors so light/dark and accessibility adapt automatically. Brand and status colors are fixed values chosen for sunlight legibility, resolved against the active scheme.

- [ ] **Step 1: Write the colors**

Create `mobile/src/theme/colors.ts`:

```ts
import { Color } from "expo-router";
import { Platform, useColorScheme } from "react-native";

/** Chrome: native semantic colors, so light/dark and accessibility adapt for free. */
export const colors = {
  label: Platform.select({
    ios: Color.ios.label,
    android: Color.android.dynamic.onSurface,
    default: "#111111",
  })!,
  secondaryLabel: Platform.select({
    ios: Color.ios.secondaryLabel,
    android: Color.android.dynamic.onSurfaceVariant,
    default: "#5B5B60",
  })!,
  separator: Platform.select({
    ios: Color.ios.separator,
    android: Color.android.dynamic.outlineVariant,
    default: "#D6D6DA",
  })!,
  background: Platform.select({
    ios: Color.ios.systemBackground,
    android: Color.android.dynamic.surface,
    default: "#FFFFFF",
  })!,
  groupedBackground: Platform.select({
    ios: Color.ios.secondarySystemBackground,
    android: Color.android.dynamic.surfaceVariant,
    default: "#F2F2F7",
  })!,
};

/** Identity and status: fixed values, chosen to stay legible in direct sunlight. */
const palette = {
  light: {
    brand: "#0F4C5C",
    accent: "#F4A208",
    danger: "#C92A2A",
    open: "#6B7280",
    in_progress: "#F4A208",
    done: "#2F9E44",
    invoiced: "#0F4C5C",
    paid: "#1B7F3B",
    cancelled: "#9CA3AF",
  },
  dark: {
    brand: "#2A8FA6",
    accent: "#FFB627",
    danger: "#FF6B6B",
    open: "#9CA3AF",
    in_progress: "#FFB627",
    done: "#51CF66",
    invoiced: "#2A8FA6",
    paid: "#40C057",
    cancelled: "#6B7280",
  },
} as const;

export type JobStatus =
  | "open"
  | "in_progress"
  | "done"
  | "invoiced"
  | "paid"
  | "cancelled";

/**
 * Brand and status colors for the active scheme.
 *
 * A hook rather than a constant because Android needs a re-render when the
 * system theme flips; iOS re-resolves semantic colors on its own, but these
 * are fixed values so both platforms need the subscription.
 */
export function useBrandColors() {
  const scheme = useColorScheme();
  return palette[scheme === "dark" ? "dark" : "light"];
}

export function useStatusColor(status: JobStatus | string) {
  const brand = useBrandColors();
  return (brand as Record<string, string>)[status] ?? brand.open;
}
```

- [ ] **Step 2: Write the type scale**

Create `mobile/src/theme/type.ts`:

```ts
import type { TextStyle } from "react-native";

/**
 * One scale, used everywhere. Screen titles come from the navigation stack,
 * so there is deliberately no `screenTitle` entry here.
 */
export const type = {
  title: { fontSize: 28, fontWeight: "700", letterSpacing: -0.4 },
  heading: { fontSize: 20, fontWeight: "600", letterSpacing: -0.2 },
  body: { fontSize: 16, fontWeight: "400" },
  label: { fontSize: 15, fontWeight: "500" },
  caption: { fontSize: 13, fontWeight: "400" },
  overline: {
    fontSize: 11,
    fontWeight: "600",
    letterSpacing: 0.8,
    textTransform: "uppercase",
  },
  /** Any number that appears in a column, so digits line up. */
  numeric: { fontSize: 16, fontWeight: "500", fontVariant: ["tabular-nums"] },
} satisfies Record<string, TextStyle>;
```

- [ ] **Step 3: Write spacing and radii**

Create `mobile/src/theme/layout.ts`:

```ts
export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
} as const;

export const radius = {
  sm: 8,
  md: 12,
  lg: 16,
} as const;

/** Rounded corners that are not capsules should use this. */
export const continuous = { borderCurve: "continuous" } as const;
```

- [ ] **Step 4: Verify it type-checks**

```bash
cd mobile && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add mobile/src/theme
git commit -m "feat(mobile): add theme tokens for color, type, and layout"
```

---

### Task 3: Typed API client

**Files:**
- Create: `mobile/src/api/schema.d.ts` (generated)
- Create: `mobile/src/api/client.ts`
- Create: `mobile/src/api/client.test.ts`
- Create: `mobile/.env`
- Modify: `mobile/package.json`

**Interfaces:**
- Produces: `apiFetch<T>(path, options)`, `ApiError` — every network call in the app goes through these

Types are generated from the live backend schema rather than hand-written, so a backend change surfaces as a TypeScript error instead of a runtime bug.

- [ ] **Step 1: Add tooling**

```bash
cd mobile
npm install --save-dev openapi-typescript jest-expo jest @types/jest
```

Add to `mobile/package.json` scripts:

```json
"api:types": "openapi-typescript https://torqbay-api.flomonotio.com/openapi.json -o src/api/schema.d.ts",
"test": "jest"
```

Add a `jest` block to `mobile/package.json`:

```json
"jest": {
  "preset": "jest-expo",
  "transformIgnorePatterns": [
    "node_modules/(?!((jest-)?react-native|@react-native(-community)?)|expo(nent)?|@expo(nent)?/.*|@expo-google-fonts/.*|react-navigation|@react-navigation/.*|@unimodules/.*|unimodules|sentry-expo|native-base|react-native-svg)"
  ]
}
```

- [ ] **Step 2: Generate the API types**

```bash
cd mobile && npm run api:types
```

Expected: `src/api/schema.d.ts` is written. Confirm it contains `/api/v1/auth/login` and `/api/v1/jobs` before continuing. **Commit this generated file** — it must be in version control so the app builds without network access.

- [ ] **Step 3: Point the app at the API**

Create `mobile/.env`:

```
EXPO_PUBLIC_API_URL=https://torqbay-api.flomonotio.com
```

`EXPO_PUBLIC_`-prefixed variables are inlined at build time by Expo and are readable in app code. This URL is not a secret — it is a public API host.

- [ ] **Step 4: Write the failing test**

Create `mobile/src/api/client.test.ts`:

```ts
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

  const error = await apiFetch("/api/v1/jobs").catch((e) => e);

  expect(error).toBeInstanceOf(ApiError);
  expect(error.status).toBe(500);
  expect(typeof error.message).toBe("string");
  expect(error.message.length).toBeGreaterThan(0);
});

test("surfaces a network failure as an ApiError with status 0", async () => {
  global.fetch = jest.fn().mockRejectedValue(new TypeError("Network request failed")) as
    unknown as typeof fetch;

  const error = await apiFetch("/api/v1/jobs").catch((e) => e);

  expect(error).toBeInstanceOf(ApiError);
  expect(error.status).toBe(0);
});
```

- [ ] **Step 5: Run test to verify it fails**

```bash
cd mobile && npm test
```
Expected: FAIL — `src/api/client` does not exist.

- [ ] **Step 6: Write the client**

Create `mobile/src/api/client.ts`:

```ts
const BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }

  /** True when the caller should re-authenticate rather than retry. */
  get isUnauthorized() {
    return this.status === 401;
  }
}

export type ApiFetchOptions = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  token?: string | null;
  signal?: AbortSignal;
};

/**
 * The single place the app talks to the network.
 *
 * Always throws ApiError on failure — including transport failures — so callers
 * never have to distinguish "the request failed" from "the server said no".
 */
export async function apiFetch<T = unknown>(
  path: string,
  options: ApiFetchOptions = {}
): Promise<T> {
  const { method = "GET", body, token, signal } = options;

  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch {
    throw new ApiError(0, "Can't reach the server. Check your connection and try again.");
  }

  if (!response.ok) {
    throw new ApiError(response.status, await readErrorMessage(response));
  }

  if (response.status === 204) return undefined as T;

  try {
    return (await response.json()) as T;
  } catch {
    return undefined as T;
  }
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload?.detail === "string") return payload.detail;
    // FastAPI validation errors arrive as a list of objects.
    if (Array.isArray(payload?.detail)) {
      const first = payload.detail[0] as { msg?: string } | undefined;
      if (first?.msg) return first.msg;
    }
  } catch {
    // Body was not JSON — fall through to a status-based message.
  }
  return `Something went wrong (${response.status}).`;
}
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
cd mobile && npm test
```
Expected: PASS (8 tests).

- [ ] **Step 8: Commit**

```bash
git add mobile/src/api mobile/package.json mobile/package-lock.json mobile/.env
git commit -m "feat(mobile): add typed API client generated from the live OpenAPI schema"
```

---

### Task 4: Secure token storage

**Files:**
- Create: `mobile/src/auth/token-storage.ts`
- Create: `mobile/src/auth/token-storage.test.ts`

**Interfaces:**
- Produces: `saveTokens`, `loadTokens`, `clearTokens`, `StoredTokens`

Tokens go in `expo-secure-store` (Keychain on iOS, EncryptedSharedPreferences on Android), never AsyncStorage.

- [ ] **Step 1: Install the dependency**

```bash
cd mobile && npx expo install expo-secure-store
```

- [ ] **Step 2: Write the failing test**

Create `mobile/src/auth/token-storage.test.ts`:

```ts
import * as SecureStore from "expo-secure-store";

import { clearTokens, loadTokens, saveTokens } from "@/auth/token-storage";

jest.mock("expo-secure-store", () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
}));

const mocked = SecureStore as jest.Mocked<typeof SecureStore>;

beforeEach(() => {
  jest.clearAllMocks();
});

test("saves both tokens", async () => {
  await saveTokens({ accessToken: "access-1", refreshToken: "refresh-1" });

  expect(mocked.setItemAsync).toHaveBeenCalledWith("torqbay.access_token", "access-1");
  expect(mocked.setItemAsync).toHaveBeenCalledWith("torqbay.refresh_token", "refresh-1");
});

test("loads both tokens", async () => {
  mocked.getItemAsync.mockResolvedValueOnce("access-1").mockResolvedValueOnce("refresh-1");

  await expect(loadTokens()).resolves.toEqual({
    accessToken: "access-1",
    refreshToken: "refresh-1",
  });
});

test("returns null when nothing is stored", async () => {
  mocked.getItemAsync.mockResolvedValue(null);

  await expect(loadTokens()).resolves.toBeNull();
});

test("returns null when only one token is present", async () => {
  mocked.getItemAsync.mockResolvedValueOnce("access-1").mockResolvedValueOnce(null);

  await expect(loadTokens()).resolves.toBeNull();
});

test("clears both tokens", async () => {
  await clearTokens();

  expect(mocked.deleteItemAsync).toHaveBeenCalledWith("torqbay.access_token");
  expect(mocked.deleteItemAsync).toHaveBeenCalledWith("torqbay.refresh_token");
});

test("treats a read failure as signed out rather than crashing", async () => {
  mocked.getItemAsync.mockRejectedValue(new Error("keychain unavailable"));

  await expect(loadTokens()).resolves.toBeNull();
});
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd mobile && npm test
```
Expected: FAIL — `src/auth/token-storage` does not exist.

- [ ] **Step 4: Write the storage module**

Create `mobile/src/auth/token-storage.ts`:

```ts
import * as SecureStore from "expo-secure-store";

const ACCESS_KEY = "torqbay.access_token";
const REFRESH_KEY = "torqbay.refresh_token";

export type StoredTokens = {
  accessToken: string;
  refreshToken: string;
};

export async function saveTokens(tokens: StoredTokens): Promise<void> {
  await Promise.all([
    SecureStore.setItemAsync(ACCESS_KEY, tokens.accessToken),
    SecureStore.setItemAsync(REFRESH_KEY, tokens.refreshToken),
  ]);
}

/**
 * Returns null unless BOTH tokens are present.
 *
 * A half-written pair cannot be refreshed, so treating it as signed out is
 * safer than surfacing an access token we can never renew. A read failure
 * (locked keychain, wiped storage) is also treated as signed out rather than
 * crashing the launch.
 */
export async function loadTokens(): Promise<StoredTokens | null> {
  try {
    const accessToken = await SecureStore.getItemAsync(ACCESS_KEY);
    const refreshToken = await SecureStore.getItemAsync(REFRESH_KEY);
    if (!accessToken || !refreshToken) return null;
    return { accessToken, refreshToken };
  } catch {
    return null;
  }
}

export async function clearTokens(): Promise<void> {
  await Promise.all([
    SecureStore.deleteItemAsync(ACCESS_KEY),
    SecureStore.deleteItemAsync(REFRESH_KEY),
  ]);
}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd mobile && npm test
```
Expected: PASS (6 new tests, 14 total).

- [ ] **Step 6: Commit**

```bash
git add mobile/src/auth mobile/package.json mobile/package-lock.json
git commit -m "feat(mobile): store auth tokens in expo-secure-store"
```

---

### Task 5: Auth session

**Files:**
- Create: `mobile/src/auth/auth-context.tsx`
- Create: `mobile/src/auth/auth-context.test.tsx`

**Interfaces:**
- Consumes: `apiFetch`, `ApiError`, `saveTokens`/`loadTokens`/`clearTokens`
- Produces: `AuthProvider`, `useAuth()` returning `{ status, user, signIn, signOut }`

`status` is `"loading"` while tokens are being restored at launch, then `"authenticated"` or `"unauthenticated"`. Task 7's routing guard depends on that three-state shape — a boolean would flash the login screen on every cold start.

Login calls `POST /api/v1/auth/login`, then `GET /api/v1/users/me` to learn the user's role, which the tab bar needs.

- [ ] **Step 1: Install the test library**

```bash
cd mobile && npm install --save-dev @testing-library/react-native react-test-renderer
```

- [ ] **Step 2: Write the failing test**

Create `mobile/src/auth/auth-context.test.tsx`:

```tsx
import { act, renderHook, waitFor } from "@testing-library/react-native";
import React from "react";

import { AuthProvider, useAuth } from "@/auth/auth-context";
import { apiFetch } from "@/api/client";
import { clearTokens, loadTokens, saveTokens } from "@/auth/token-storage";

jest.mock("@/api/client", () => ({
  ...jest.requireActual("@/api/client"),
  apiFetch: jest.fn(),
}));
jest.mock("@/auth/token-storage", () => ({
  saveTokens: jest.fn(),
  loadTokens: jest.fn(),
  clearTokens: jest.fn(),
}));

const mockApi = apiFetch as jest.MockedFunction<typeof apiFetch>;
const mockLoad = loadTokens as jest.MockedFunction<typeof loadTokens>;
const mockSave = saveTokens as jest.MockedFunction<typeof saveTokens>;
const mockClear = clearTokens as jest.MockedFunction<typeof clearTokens>;

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <AuthProvider>{children}</AuthProvider>
);

const USER = { id: "u1", name: "Owner", email: "o@x.com", role: "owner", tenant_id: "t1" };

beforeEach(() => {
  jest.clearAllMocks();
});

test("starts unauthenticated when nothing is stored", async () => {
  mockLoad.mockResolvedValue(null);

  const { result } = renderHook(() => useAuth(), { wrapper });

  await waitFor(() => expect(result.current.status).toBe("unauthenticated"));
  expect(result.current.user).toBeNull();
});

test("restores a stored session on launch", async () => {
  mockLoad.mockResolvedValue({ accessToken: "a", refreshToken: "r" });
  mockApi.mockResolvedValue(USER);

  const { result } = renderHook(() => useAuth(), { wrapper });

  await waitFor(() => expect(result.current.status).toBe("authenticated"));
  expect(result.current.user?.role).toBe("owner");
});

test("signs out when the stored token is rejected", async () => {
  mockLoad.mockResolvedValue({ accessToken: "stale", refreshToken: "r" });
  const { ApiError } = jest.requireActual("@/api/client");
  mockApi.mockRejectedValue(new ApiError(401, "Invalid token"));

  const { result } = renderHook(() => useAuth(), { wrapper });

  await waitFor(() => expect(result.current.status).toBe("unauthenticated"));
  expect(mockClear).toHaveBeenCalled();
});

test("signIn stores tokens and loads the user", async () => {
  mockLoad.mockResolvedValue(null);
  mockApi
    .mockResolvedValueOnce({ access_token: "a1", refresh_token: "r1" })
    .mockResolvedValueOnce(USER);

  const { result } = renderHook(() => useAuth(), { wrapper });
  await waitFor(() => expect(result.current.status).toBe("unauthenticated"));

  await act(async () => {
    await result.current.signIn("o@x.com", "password123");
  });

  expect(mockSave).toHaveBeenCalledWith({ accessToken: "a1", refreshToken: "r1" });
  await waitFor(() => expect(result.current.status).toBe("authenticated"));
});

test("signIn surfaces bad credentials and stays signed out", async () => {
  mockLoad.mockResolvedValue(null);
  const { ApiError } = jest.requireActual("@/api/client");
  mockApi.mockRejectedValue(new ApiError(401, "Incorrect email or password"));

  const { result } = renderHook(() => useAuth(), { wrapper });
  await waitFor(() => expect(result.current.status).toBe("unauthenticated"));

  await expect(
    act(async () => {
      await result.current.signIn("o@x.com", "wrong");
    })
  ).rejects.toThrow("Incorrect email or password");

  expect(result.current.status).toBe("unauthenticated");
  expect(mockSave).not.toHaveBeenCalled();
});

test("signOut clears tokens and the user", async () => {
  mockLoad.mockResolvedValue({ accessToken: "a", refreshToken: "r" });
  mockApi.mockResolvedValue(USER);

  const { result } = renderHook(() => useAuth(), { wrapper });
  await waitFor(() => expect(result.current.status).toBe("authenticated"));

  await act(async () => {
    await result.current.signOut();
  });

  expect(mockClear).toHaveBeenCalled();
  expect(result.current.status).toBe("unauthenticated");
  expect(result.current.user).toBeNull();
});
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd mobile && npm test
```
Expected: FAIL — `src/auth/auth-context` does not exist.

- [ ] **Step 4: Write the provider**

Create `mobile/src/auth/auth-context.tsx`:

```tsx
import React, { createContext, use, useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, apiFetch } from "@/api/client";
import { clearTokens, loadTokens, saveTokens } from "@/auth/token-storage";

export type UserRole = "owner" | "manager" | "technician" | "frontdesk";

export type AuthUser = {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  tenant_id: string;
};

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

type AuthValue = {
  status: AuthStatus;
  user: AuthUser | null;
  accessToken: string | null;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);

  // Restore a stored session once, at launch.
  useEffect(() => {
    let cancelled = false;

    (async () => {
      const tokens = await loadTokens();
      if (!tokens) {
        if (!cancelled) setStatus("unauthenticated");
        return;
      }
      try {
        const me = await apiFetch<AuthUser>("/api/v1/users/me", {
          token: tokens.accessToken,
        });
        if (cancelled) return;
        setAccessToken(tokens.accessToken);
        setUser(me);
        setStatus("authenticated");
      } catch {
        // A stored token the server rejects is worse than no token: clear it
        // so the next launch doesn't repeat the failed round trip.
        await clearTokens();
        if (!cancelled) setStatus("unauthenticated");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const tokens = await apiFetch<{ access_token: string; refresh_token: string }>(
      "/api/v1/auth/login",
      { method: "POST", body: { email, password } }
    );

    await saveTokens({
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
    });

    const me = await apiFetch<AuthUser>("/api/v1/users/me", {
      token: tokens.access_token,
    });

    setAccessToken(tokens.access_token);
    setUser(me);
    setStatus("authenticated");
  }, []);

  const signOut = useCallback(async () => {
    await clearTokens();
    setAccessToken(null);
    setUser(null);
    setStatus("unauthenticated");
  }, []);

  const value = useMemo<AuthValue>(
    () => ({ status, user, accessToken, signIn, signOut }),
    [status, user, accessToken, signIn, signOut]
  );

  return <AuthContext value={value}>{children}</AuthContext>;
}

export function useAuth(): AuthValue {
  const value = use(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}

export { ApiError };
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd mobile && npm test
```
Expected: PASS (6 new tests, 20 total).

- [ ] **Step 6: Commit**

```bash
git add mobile/src/auth mobile/package.json mobile/package-lock.json
git commit -m "feat(mobile): add auth session with launch restore"
```

---

### Task 6: Login screen

**Files:**
- Create: `mobile/app/(auth)/login.tsx`
- Create: `mobile/app/(auth)/_layout.tsx`
- Create: `mobile/src/ui/button.tsx`
- Create: `mobile/src/ui/field.tsx`

**Interfaces:**
- Consumes: `useAuth`, theme tokens
- Produces: `Button`, `Field` — reused by every later form

The first screen anyone sees. Errors state what happened and what to do; they never apologise or say "Error".

- [ ] **Step 1: Write the button**

Create `mobile/src/ui/button.tsx`:

```tsx
import { ActivityIndicator, Pressable, Text } from "react-native";

import { useBrandColors } from "@/theme/colors";
import { continuous, radius, spacing } from "@/theme/layout";
import { type } from "@/theme/type";

type ButtonProps = {
  label: string;
  onPress: () => void;
  busy?: boolean;
  disabled?: boolean;
};

export function Button({ label, onPress, busy = false, disabled = false }: ButtonProps) {
  const brand = useBrandColors();
  const inactive = disabled || busy;

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: inactive, busy }}
      onPress={onPress}
      disabled={inactive}
      style={({ pressed }) => ({
        backgroundColor: brand.brand,
        opacity: inactive ? 0.5 : pressed ? 0.85 : 1,
        paddingVertical: spacing.lg,
        paddingHorizontal: spacing.xl,
        borderRadius: radius.md,
        alignItems: "center",
        justifyContent: "center",
        minHeight: 52,
        ...continuous,
      })}
    >
      {busy ? (
        <ActivityIndicator color="#FFFFFF" />
      ) : (
        <Text style={{ ...type.label, color: "#FFFFFF", fontSize: 17 }}>{label}</Text>
      )}
    </Pressable>
  );
}
```

- [ ] **Step 2: Write the field**

Create `mobile/src/ui/field.tsx`:

```tsx
import { TextInput, View, Text } from "react-native";
import type { TextInputProps } from "react-native";

import { colors, useBrandColors } from "@/theme/colors";
import { continuous, radius, spacing } from "@/theme/layout";
import { type } from "@/theme/type";

type FieldProps = TextInputProps & {
  label: string;
};

export function Field({ label, ...inputProps }: FieldProps) {
  const brand = useBrandColors();

  return (
    <View style={{ gap: spacing.sm }}>
      <Text style={{ ...type.overline, color: colors.secondaryLabel }}>{label}</Text>
      <TextInput
        {...inputProps}
        placeholderTextColor={colors.secondaryLabel}
        selectionColor={brand.brand}
        style={{
          ...type.body,
          color: colors.label,
          backgroundColor: colors.groupedBackground,
          borderRadius: radius.md,
          paddingHorizontal: spacing.lg,
          paddingVertical: spacing.lg,
          minHeight: 52,
          ...continuous,
        }}
      />
    </View>
  );
}
```

- [ ] **Step 3: Write the auth layout**

Create `mobile/app/(auth)/_layout.tsx`:

```tsx
import { Stack } from "expo-router";

export default function AuthLayout() {
  return <Stack screenOptions={{ headerShown: false }} />;
}
```

- [ ] **Step 4: Write the login screen**

Create `mobile/app/(auth)/login.tsx`:

```tsx
import { useState } from "react";
import { KeyboardAvoidingView, ScrollView, Text, View } from "react-native";

import { ApiError } from "@/api/client";
import { useAuth } from "@/auth/auth-context";
import { colors, useBrandColors } from "@/theme/colors";
import { spacing } from "@/theme/layout";
import { type } from "@/theme/type";
import { Button } from "@/ui/button";
import { Field } from "@/ui/field";

export default function Login() {
  const { signIn } = useAuth();
  const brand = useBrandColors();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const canSubmit = email.trim().length > 0 && password.length > 0 && !busy;

  async function submit() {
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      await signIn(email.trim(), password);
      // Routing is handled by the guard in app/_layout.tsx.
    } catch (e) {
      setError(
        e instanceof ApiError && e.status === 401
          ? "That email and password don't match. Check them and try again."
          : e instanceof ApiError
            ? e.message
            : "Something went wrong. Try again."
      );
      setBusy(false);
    }
  }

  return (
    <KeyboardAvoidingView
      behavior={process.env.EXPO_OS === "ios" ? "padding" : undefined}
      style={{ flex: 1, backgroundColor: colors.background }}
    >
      <ScrollView
        contentInsetAdjustmentBehavior="automatic"
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{
          flexGrow: 1,
          justifyContent: "center",
          padding: spacing.xl,
          gap: spacing.xl,
        }}
      >
        <View style={{ gap: spacing.sm }}>
          <Text style={{ ...type.title, color: brand.brand }}>Torqbay</Text>
          <Text style={{ ...type.body, color: colors.secondaryLabel }}>
            Sign in to your workshop.
          </Text>
        </View>

        <View style={{ gap: spacing.lg }}>
          <Field
            label="Email"
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="email-address"
            textContentType="emailAddress"
            placeholder="you@workshop.lk"
            editable={!busy}
          />
          <Field
            label="Password"
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            textContentType="password"
            placeholder="Your password"
            editable={!busy}
            onSubmitEditing={submit}
            returnKeyType="go"
          />

          {error ? (
            <Text selectable style={{ ...type.caption, color: brand.danger }}>
              {error}
            </Text>
          ) : null}

          <Button label="Sign in" onPress={submit} busy={busy} disabled={!canSubmit} />
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
```

- [ ] **Step 5: Verify it type-checks**

```bash
cd mobile && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add mobile/app mobile/src/ui
git commit -m "feat(mobile): add login screen with reusable button and field"
```

---

### Task 7: Root layout and auth routing guard

**Files:**
- Modify: `mobile/app/_layout.tsx`
- Delete: `mobile/app/index.tsx`

**Interfaces:**
- Consumes: `AuthProvider`, `useAuth`
- Produces: automatic redirection between `(auth)` and `(tabs)`

While `status === "loading"` the app renders nothing but the background. Rendering the login screen during restore would flash it on every cold start for an already-signed-in user.

- [ ] **Step 1: Write the root layout**

Replace `mobile/app/_layout.tsx`:

```tsx
import { Stack, useRouter, useSegments } from "expo-router";
import { useEffect } from "react";
import { View } from "react-native";

import { AuthProvider, useAuth } from "@/auth/auth-context";
import { colors } from "@/theme/colors";

function RootNavigator() {
  const { status } = useAuth();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    if (status === "loading") return;

    const inAuthGroup = segments[0] === "(auth)";

    if (status === "unauthenticated" && !inAuthGroup) {
      router.replace("/(auth)/login");
    } else if (status === "authenticated" && inAuthGroup) {
      router.replace("/(tabs)/jobs");
    }
  }, [status, segments, router]);

  // Render nothing while restoring, so an already-signed-in user never sees
  // the login screen flash on a cold start.
  if (status === "loading") {
    return <View style={{ flex: 1, backgroundColor: colors.background }} />;
  }

  return <Stack screenOptions={{ headerShown: false }} />;
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <RootNavigator />
    </AuthProvider>
  );
}
```

- [ ] **Step 2: Remove the placeholder route**

```bash
rm mobile/app/index.tsx
```

- [ ] **Step 3: Verify it type-checks**

```bash
cd mobile && npx tsc --noEmit
```
Expected: no errors. (`/(tabs)/jobs` does not exist yet — Task 8 creates it. If Expo Router's typed-routes checking rejects the unknown path, leave the string as-is; it resolves once Task 8 lands.)

- [ ] **Step 4: Commit**

```bash
git add mobile/app
git commit -m "feat(mobile): add auth routing guard to the root layout"
```

---

### Task 8: Role-aware tab shell

**Files:**
- Create: `mobile/app/(tabs)/_layout.tsx`
- Create: `mobile/app/(tabs)/jobs.tsx`
- Create: `mobile/app/(tabs)/customers.tsx`
- Create: `mobile/app/(tabs)/inventory.tsx`
- Create: `mobile/app/(tabs)/settings.tsx`
- Create: `mobile/src/auth/permissions.ts`
- Create: `mobile/src/auth/permissions.test.ts`

**Interfaces:**
- Consumes: `useAuth`, theme tokens
- Produces: `canSeeTab(role, tab)`; a bottom tab bar filtered by role

Tab visibility follows the matrix in `docs/05-mobile-app.md`. This is presentation only — the backend enforces permissions on every request regardless of what the UI shows.

- [ ] **Step 1: Write the failing permissions test**

Create `mobile/src/auth/permissions.test.ts`:

```ts
import { canSeeTab } from "@/auth/permissions";

test("owner sees every tab", () => {
  for (const tab of ["jobs", "customers", "inventory", "settings"] as const) {
    expect(canSeeTab("owner", tab)).toBe(true);
  }
});

test("manager sees every tab", () => {
  for (const tab of ["jobs", "customers", "inventory", "settings"] as const) {
    expect(canSeeTab("manager", tab)).toBe(true);
  }
});

test("technician sees jobs, inventory and settings but not customers", () => {
  expect(canSeeTab("technician", "jobs")).toBe(true);
  expect(canSeeTab("technician", "inventory")).toBe(true);
  expect(canSeeTab("technician", "settings")).toBe(true);
  expect(canSeeTab("technician", "customers")).toBe(false);
});

test("frontdesk sees every tab", () => {
  for (const tab of ["jobs", "customers", "inventory", "settings"] as const) {
    expect(canSeeTab("frontdesk", tab)).toBe(true);
  }
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd mobile && npm test
```
Expected: FAIL — `src/auth/permissions` does not exist.

- [ ] **Step 3: Write the permissions module**

Create `mobile/src/auth/permissions.ts`:

```ts
import type { UserRole } from "@/auth/auth-context";

export type TabName = "jobs" | "customers" | "inventory" | "settings";

/**
 * Which tabs each role sees, per the matrix in docs/05-mobile-app.md.
 *
 * Presentation only — the backend enforces permissions on every request, so
 * hiding a tab is a convenience, never a security boundary.
 */
const VISIBLE: Record<UserRole, TabName[]> = {
  owner: ["jobs", "customers", "inventory", "settings"],
  manager: ["jobs", "customers", "inventory", "settings"],
  technician: ["jobs", "inventory", "settings"],
  frontdesk: ["jobs", "customers", "inventory", "settings"],
};

export function canSeeTab(role: UserRole, tab: TabName): boolean {
  return VISIBLE[role]?.includes(tab) ?? false;
}
```

- [ ] **Step 4: Write the tab layout**

Create `mobile/app/(tabs)/_layout.tsx`:

```tsx
import { Tabs } from "expo-router";
import { Image } from "expo-image";

import { useAuth } from "@/auth/auth-context";
import { canSeeTab } from "@/auth/permissions";
import { colors, useBrandColors } from "@/theme/colors";

function TabIcon({ name, color }: { name: string; color: string }) {
  return (
    <Image
      source={`sf:${name}`}
      tintColor={color as string}
      style={{ width: 26, height: 26 }}
    />
  );
}

export default function TabsLayout() {
  const { user } = useAuth();
  const brand = useBrandColors();
  const role = user?.role ?? "technician";

  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: brand.brand as string,
        tabBarInactiveTintColor: colors.secondaryLabel as string,
        headerTintColor: colors.label as string,
      }}
    >
      <Tabs.Screen
        name="jobs"
        options={{
          title: "Jobs",
          tabBarIcon: ({ color }) => <TabIcon name="wrench.and.screwdriver" color={color} />,
        }}
      />
      <Tabs.Screen
        name="customers"
        options={{
          title: "Customers",
          href: canSeeTab(role, "customers") ? undefined : null,
          tabBarIcon: ({ color }) => <TabIcon name="person.2" color={color} />,
        }}
      />
      <Tabs.Screen
        name="inventory"
        options={{
          title: "Inventory",
          href: canSeeTab(role, "inventory") ? undefined : null,
          tabBarIcon: ({ color }) => <TabIcon name="shippingbox" color={color} />,
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: "Settings",
          tabBarIcon: ({ color }) => <TabIcon name="gearshape" color={color} />,
        }}
      />
    </Tabs>
  );
}
```

- [ ] **Step 5: Write placeholder screens**

Create `mobile/app/(tabs)/customers.tsx`, `mobile/app/(tabs)/inventory.tsx` using this shape, changing the title text in each:

```tsx
import { ScrollView, Text } from "react-native";

import { colors } from "@/theme/colors";
import { spacing } from "@/theme/layout";
import { type } from "@/theme/type";

export default function Customers() {
  return (
    <ScrollView
      contentInsetAdjustmentBehavior="automatic"
      style={{ backgroundColor: colors.background }}
      contentContainerStyle={{ padding: spacing.lg, gap: spacing.md }}
    >
      <Text style={{ ...type.body, color: colors.secondaryLabel }}>
        Customers arrive in the next release.
      </Text>
    </ScrollView>
  );
}
```

Create `mobile/app/(tabs)/settings.tsx` with a working sign-out, since it is the only way back to the login screen:

```tsx
import { ScrollView, Text, View } from "react-native";

import { useAuth } from "@/auth/auth-context";
import { colors } from "@/theme/colors";
import { spacing } from "@/theme/layout";
import { type } from "@/theme/type";
import { Button } from "@/ui/button";

export default function Settings() {
  const { user, signOut } = useAuth();

  return (
    <ScrollView
      contentInsetAdjustmentBehavior="automatic"
      style={{ backgroundColor: colors.background }}
      contentContainerStyle={{ padding: spacing.lg, gap: spacing.xl }}
    >
      <View style={{ gap: spacing.xs }}>
        <Text style={{ ...type.overline, color: colors.secondaryLabel }}>Signed in as</Text>
        <Text selectable style={{ ...type.heading, color: colors.label }}>
          {user?.name}
        </Text>
        <Text selectable style={{ ...type.caption, color: colors.secondaryLabel }}>
          {user?.email} · {user?.role}
        </Text>
      </View>

      <Button label="Sign out" onPress={signOut} />
    </ScrollView>
  );
}
```

Create `mobile/app/(tabs)/jobs.tsx` as a placeholder for now — Task 9 replaces its body:

```tsx
import { ScrollView, Text } from "react-native";

import { colors } from "@/theme/colors";
import { spacing } from "@/theme/layout";
import { type } from "@/theme/type";

export default function Jobs() {
  return (
    <ScrollView
      contentInsetAdjustmentBehavior="automatic"
      style={{ backgroundColor: colors.background }}
      contentContainerStyle={{ padding: spacing.lg }}
    >
      <Text style={{ ...type.body, color: colors.secondaryLabel }}>Loading jobs…</Text>
    </ScrollView>
  );
}
```

- [ ] **Step 6: Run tests and type-check**

```bash
cd mobile && npm test && npx tsc --noEmit
```
Expected: PASS (4 new tests, 24 total), no type errors.

- [ ] **Step 7: Commit**

```bash
git add mobile/app mobile/src/auth
git commit -m "feat(mobile): add role-aware tab shell"
```

---

### Task 9: Live job list

**Files:**
- Modify: `mobile/app/_layout.tsx`
- Modify: `mobile/app/(tabs)/jobs.tsx`
- Create: `mobile/src/ui/status-tag.tsx`
- Create: `mobile/src/jobs/use-jobs.ts`

**Interfaces:**
- Consumes: `apiFetch`, `useAuth`, theme tokens
- Produces: a job list rendered from the live production API

This is the payoff: real data from the real backend, on a real phone. It also proves the whole chain — token storage, restore, auth header, tenant scoping — end to end.

- [ ] **Step 1: Install TanStack Query**

```bash
cd mobile && npm install @tanstack/react-query
```

- [ ] **Step 2: Add the query provider**

In `mobile/app/_layout.tsx`, wrap the tree. Add the imports and a module-level client (created once, not per render):

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
```

```tsx
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
    },
  },
});
```

and change the default export to:

```tsx
export default function RootLayout() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <RootNavigator />
      </AuthProvider>
    </QueryClientProvider>
  );
}
```

- [ ] **Step 3: Write the status tag**

Create `mobile/src/ui/status-tag.tsx`:

```tsx
import { Text, View } from "react-native";

import { type JobStatus, useStatusColor } from "@/theme/colors";
import { continuous, radius, spacing } from "@/theme/layout";
import { type } from "@/theme/type";

const LABELS: Record<string, string> = {
  open: "Not started",
  in_progress: "In progress",
  done: "Done",
  invoiced: "Invoiced",
  paid: "Paid",
  cancelled: "Cancelled",
};

export function StatusTag({ status }: { status: JobStatus | string }) {
  const color = useStatusColor(status);

  return (
    <View
      style={{
        alignSelf: "flex-start",
        backgroundColor: `${color}1A`,
        borderLeftWidth: 3,
        borderLeftColor: color,
        paddingVertical: spacing.xs,
        paddingHorizontal: spacing.sm,
        borderRadius: radius.sm,
        ...continuous,
      }}
    >
      <Text style={{ ...type.overline, color }}>{LABELS[status] ?? status}</Text>
    </View>
  );
}
```

- [ ] **Step 4: Write the data hook**

Create `mobile/src/jobs/use-jobs.ts`:

```ts
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";
import { useAuth } from "@/auth/auth-context";

export type Job = {
  id: string;
  title: string;
  description: string | null;
  status: string;
  customer_id: string;
  asset_id: string;
  assigned_technician_id: string | null;
};

type JobListResponse = {
  items: Job[];
  total: number;
  page: number;
  page_size: number;
};

export function useJobs() {
  const { accessToken } = useAuth();

  return useQuery({
    queryKey: ["jobs"],
    enabled: Boolean(accessToken),
    queryFn: () =>
      apiFetch<JobListResponse>("/api/v1/jobs?page=1&page_size=50", {
        token: accessToken,
      }),
  });
}
```

- [ ] **Step 5: Write the job list**

Replace `mobile/app/(tabs)/jobs.tsx`:

```tsx
import { ActivityIndicator, FlatList, RefreshControl, Text, View } from "react-native";

import { useJobs, type Job } from "@/jobs/use-jobs";
import { colors, useBrandColors } from "@/theme/colors";
import { continuous, radius, spacing } from "@/theme/layout";
import { type } from "@/theme/type";
import { StatusTag } from "@/ui/status-tag";

function JobCard({ job }: { job: Job }) {
  return (
    <View
      style={{
        backgroundColor: colors.groupedBackground,
        borderRadius: radius.md,
        padding: spacing.lg,
        gap: spacing.sm,
        ...continuous,
      }}
    >
      <Text selectable style={{ ...type.heading, color: colors.label }}>
        {job.title}
      </Text>
      {job.description ? (
        <Text
          numberOfLines={2}
          style={{ ...type.caption, color: colors.secondaryLabel }}
        >
          {job.description}
        </Text>
      ) : null}
      <StatusTag status={job.status} />
    </View>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <View style={{ padding: spacing.xxl, alignItems: "center", gap: spacing.md }}>
      {children}
    </View>
  );
}

export default function Jobs() {
  const { data, isLoading, isRefetching, error, refetch } = useJobs();
  const brand = useBrandColors();

  if (isLoading) {
    return (
      <Centered>
        <ActivityIndicator />
      </Centered>
    );
  }

  if (error) {
    return (
      <Centered>
        <Text selectable style={{ ...type.body, color: brand.danger, textAlign: "center" }}>
          {error instanceof Error ? error.message : "Couldn't load jobs."}
        </Text>
        <Text style={{ ...type.caption, color: colors.secondaryLabel }}>
          Pull down to try again.
        </Text>
      </Centered>
    );
  }

  return (
    <FlatList
      contentInsetAdjustmentBehavior="automatic"
      style={{ backgroundColor: colors.background }}
      contentContainerStyle={{ padding: spacing.lg, gap: spacing.md }}
      data={data?.items ?? []}
      keyExtractor={(job) => job.id}
      renderItem={({ item }) => <JobCard job={item} />}
      refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
      ListEmptyComponent={
        <Centered>
          <Text style={{ ...type.heading, color: colors.label }}>No jobs yet</Text>
          <Text style={{ ...type.caption, color: colors.secondaryLabel, textAlign: "center" }}>
            Jobs you create will show up here.
          </Text>
        </Centered>
      }
    />
  );
}
```

- [ ] **Step 6: Verify**

```bash
cd mobile && npm test && npx tsc --noEmit
```
Expected: all tests pass, no type errors.

- [ ] **Step 7: Run it against the live API**

```bash
cd mobile && npx expo start
```

Open Expo Go on a phone and scan the QR code. Sign in with a real tenant account. Confirm: the login screen appears, signing in lands on the Jobs tab, the tab bar shows the right tabs for the role, and Settings shows the signed-in user and signs out cleanly.

**If a tenant account does not exist yet**, create one via the platform admin API — the app has no signup screen and Phase 1 deliberately does not include one:

```bash
ADMIN=$(curl -s -X POST https://torqbay-api.flomonotio.com/api/v1/admin/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"<admin email>","password":"<admin password>"}' | python3 -c 'import json,sys;print(json.load(sys.stdin)["access_token"])')

curl -s -X POST https://torqbay-api.flomonotio.com/api/v1/admin/tenants \
  -H "Authorization: Bearer $ADMIN" -H 'Content-Type: application/json' \
  -d '{"name":"Test Workshop","owner_name":"Owner","owner_email":"owner@test.lk","owner_password":"testpass123"}'
```

Report what you observed on the device, including anything that looked wrong.

- [ ] **Step 8: Commit**

```bash
git add mobile
git commit -m "feat(mobile): show the live job list from the production API"
```

---

## How to run it

```bash
cd mobile
npm install
npx expo start
```

Scan the QR code with **Expo Go** (App Store / Play Store). The app talks to the live production API at `https://torqbay-api.flomonotio.com` — no local backend needed.

Everything here runs in Expo Go. No custom native build, no Xcode, no Android Studio.

## What this deliberately does not include

Job detail, creating a job, customers, inventory screens, invoices, offline support, push notifications, and the status-change animations and haptics described in `docs/05-mobile-app.md`. Those belong to the screens plan. This plan's job is to make the app run, authenticate, and prove the data path — nothing more.
