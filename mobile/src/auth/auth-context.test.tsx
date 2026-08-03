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
