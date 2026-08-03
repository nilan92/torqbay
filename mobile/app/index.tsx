import { Redirect } from "expo-router";
import { View } from "react-native";

import { useAuth } from "@/auth/auth-context";
import { colors } from "@/theme/colors";

/**
 * The app's entry route.
 *
 * Expo Router needs a real route at "/" — without one, launching the app shows
 * "Unmatched Route" before the guard in _layout.tsx ever gets to redirect.
 * This renders nothing while the stored session is being restored, then sends
 * the user to the right place.
 */
export default function Index() {
  const { status } = useAuth();

  if (status === "loading") {
    return <View style={{ flex: 1, backgroundColor: colors.background }} />;
  }

  return (
    <Redirect href={status === "authenticated" ? "/(tabs)/jobs" : "/(auth)/login"} />
  );
}
