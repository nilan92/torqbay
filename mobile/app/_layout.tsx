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
