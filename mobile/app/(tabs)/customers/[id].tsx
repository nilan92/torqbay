import { Stack, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, ScrollView, Text, View } from "react-native";

import { useAssets, useCreateAsset } from "@/customers/use-assets";
import { useCustomer } from "@/customers/use-customer";
import { colors, useBrandColors } from "@/theme/colors";
import { continuous, radius, spacing } from "@/theme/layout";
import { type } from "@/theme/type";
import { Button } from "@/ui/button";
import { Centered } from "@/ui/empty-state";
import { Field } from "@/ui/field";

function Row({ primary, secondary }: { primary: string; secondary?: string }) {
  return (
    <View
      style={{
        backgroundColor: colors.groupedBackground,
        borderRadius: radius.md,
        padding: spacing.lg,
        gap: spacing.xs,
        ...continuous,
      }}
    >
      <Text selectable style={{ ...type.body, color: colors.label }}>
        {primary}
      </Text>
      {secondary ? (
        <Text style={{ ...type.caption, color: colors.secondaryLabel }}>{secondary}</Text>
      ) : null}
    </View>
  );
}

export default function CustomerDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const brand = useBrandColors();

  const { data: customer, isLoading, error } = useCustomer(id);
  const { data: assets } = useAssets(id);
  const createAsset = useCreateAsset(id);

  const [showAddAsset, setShowAddAsset] = useState(false);
  const [label, setLabel] = useState("");
  const [identifier, setIdentifier] = useState("");

  if (isLoading) {
    return (
      <ScrollView contentInsetAdjustmentBehavior="automatic" style={{ backgroundColor: colors.background }}>
        <Centered>
          <ActivityIndicator />
        </Centered>
      </ScrollView>
    );
  }

  if (error || !customer) {
    return (
      <ScrollView contentInsetAdjustmentBehavior="automatic" style={{ backgroundColor: colors.background }}>
        <Centered>
          <Text selectable style={{ ...type.body, color: brand.danger, textAlign: "center" }}>
            {error instanceof Error ? error.message : "Couldn't load this customer."}
          </Text>
        </Centered>
      </ScrollView>
    );
  }

  return (
    <ScrollView
      contentInsetAdjustmentBehavior="automatic"
      style={{ backgroundColor: colors.background }}
      contentContainerStyle={{ padding: spacing.lg, gap: spacing.xl }}
    >
      <Stack.Screen options={{ title: customer.name }} />

      <View style={{ gap: spacing.xs }}>
        {customer.phone ? (
          <Text selectable style={{ ...type.body, color: colors.label }}>
            {customer.phone}
          </Text>
        ) : null}
        {customer.email ? (
          <Text selectable style={{ ...type.body, color: colors.secondaryLabel }}>
            {customer.email}
          </Text>
        ) : null}
        {customer.address ? (
          <Text selectable style={{ ...type.caption, color: colors.secondaryLabel }}>
            {customer.address}
          </Text>
        ) : null}
      </View>

      <View style={{ gap: spacing.md }}>
        <Text style={{ ...type.overline, color: colors.secondaryLabel }}>Vehicles</Text>

        {assets?.items.length ? (
          <View style={{ gap: spacing.sm }}>
            {assets.items.map((asset) => (
              <Row
                key={asset.id}
                primary={asset.label}
                secondary={asset.identifier ?? undefined}
              />
            ))}
          </View>
        ) : (
          <Text style={{ ...type.caption, color: colors.secondaryLabel }}>
            No vehicles added yet.
          </Text>
        )}

        <Button label="Add vehicle" onPress={() => setShowAddAsset((v) => !v)} />

        {showAddAsset ? (
          <View style={{ gap: spacing.md }}>
            <Field
              label="Vehicle"
              value={label}
              onChangeText={setLabel}
              placeholder="Toyota Corolla 2018"
            />
            <Field
              label="Plate / VIN (optional)"
              value={identifier}
              onChangeText={setIdentifier}
              placeholder="ABC-1234"
              autoCapitalize="characters"
            />
            <Button
              label="Save vehicle"
              busy={createAsset.isPending}
              disabled={label.trim().length === 0 || createAsset.isPending}
              onPress={() => {
                createAsset.mutate(
                  {
                    type: "vehicle",
                    label: label.trim(),
                    identifier: identifier.trim() || undefined,
                  },
                  {
                    onSuccess: () => {
                      setShowAddAsset(false);
                      setLabel("");
                      setIdentifier("");
                    },
                  }
                );
              }}
            />
          </View>
        ) : null}
      </View>
    </ScrollView>
  );
}
