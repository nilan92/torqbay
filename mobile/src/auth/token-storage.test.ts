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
