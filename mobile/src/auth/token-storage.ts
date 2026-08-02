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
