import { router } from "expo-router";
import { useState } from "react";
import { KeyboardAvoidingView, ScrollView, Text, View } from "react-native";

import { ApiError } from "@/api/client";
import { useCreateCustomer } from "@/customers/use-customer";
import { useBrandColors } from "@/theme/colors";
import { spacing } from "@/theme/layout";
import { Button } from "@/ui/button";
import { Field } from "@/ui/field";

export default function NewCustomer() {
  const brand = useBrandColors();
  const createCustomer = useCreateCustomer();

  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [address, setAddress] = useState("");
  const [error, setError] = useState<string | null>(null);

  const canSubmit = name.trim().length > 0 && !createCustomer.isPending;

  async function submit() {
    if (!canSubmit) return;
    setError(null);
    try {
      const customer = await createCustomer.mutateAsync({
        name: name.trim(),
        phone: phone.trim() || undefined,
        email: email.trim() || undefined,
        address: address.trim() || undefined,
      });
      router.replace(`/(tabs)/customers/${customer.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't save this customer. Try again.");
    }
  }

  return (
    <KeyboardAvoidingView
      behavior={process.env.EXPO_OS === "ios" ? "padding" : undefined}
      style={{ flex: 1 }}
    >
      <ScrollView
        contentInsetAdjustmentBehavior="automatic"
        contentContainerStyle={{ padding: spacing.lg, gap: spacing.lg }}
      >
        <Field label="Name" value={name} onChangeText={setName} placeholder="Nimal Perera" />
        <Field
          label="Phone"
          value={phone}
          onChangeText={setPhone}
          placeholder="077 123 4567"
          keyboardType="phone-pad"
        />
        <Field
          label="Email"
          value={email}
          onChangeText={setEmail}
          placeholder="nimal@example.com"
          autoCapitalize="none"
          keyboardType="email-address"
        />
        <Field label="Address" value={address} onChangeText={setAddress} multiline />

        {error ? (
          <Text selectable style={{ color: brand.danger }}>
            {error}
          </Text>
        ) : null}

        <View>
          <Button
            label="Save customer"
            busy={createCustomer.isPending}
            disabled={!canSubmit}
            onPress={submit}
          />
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
