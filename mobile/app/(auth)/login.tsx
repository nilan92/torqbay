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
