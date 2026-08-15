import { router } from "expo-router";
import { useState } from "react";
import { KeyboardAvoidingView, ScrollView, Text, View } from "react-native";

import { ApiError } from "@/api/client";
import { useCreateInventoryItem } from "@/inventory/use-inventory-items";
import { useBrandColors } from "@/theme/colors";
import { spacing } from "@/theme/layout";
import { Button } from "@/ui/button";
import { Field } from "@/ui/field";

export default function NewInventoryItem() {
  const brand = useBrandColors();
  const createItem = useCreateInventoryItem();

  const [sku, setSku] = useState("");
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [unitCost, setUnitCost] = useState("");
  const [unitPrice, setUnitPrice] = useState("");
  const [quantityOnHand, setQuantityOnHand] = useState("0");
  const [reorderThreshold, setReorderThreshold] = useState("0");
  const [error, setError] = useState<string | null>(null);

  const cost = Number(unitCost);
  const price = Number(unitPrice);
  const quantity = Number(quantityOnHand || "0");
  const threshold = Number(reorderThreshold || "0");

  const canSubmit =
    sku.trim().length > 0 &&
    name.trim().length > 0 &&
    !Number.isNaN(cost) &&
    cost >= 0 &&
    !Number.isNaN(price) &&
    price >= 0 &&
    !Number.isNaN(quantity) &&
    quantity >= 0 &&
    !Number.isNaN(threshold) &&
    threshold >= 0 &&
    !createItem.isPending;

  async function submit() {
    if (!canSubmit) return;
    setError(null);
    try {
      const item = await createItem.mutateAsync({
        sku: sku.trim(),
        name: name.trim(),
        category: category.trim() || undefined,
        unit_cost: cost,
        unit_price: price,
        quantity_on_hand: quantity,
        reorder_threshold: threshold,
      });
      router.replace(`/(tabs)/inventory/${item.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't save this item. Try again.");
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
        <Field label="SKU" value={sku} onChangeText={setSku} placeholder="OIL-5W30" autoCapitalize="characters" />
        <Field label="Name" value={name} onChangeText={setName} placeholder="5W-30 Synthetic Oil (1L)" />
        <Field label="Category (optional)" value={category} onChangeText={setCategory} />
        <Field label="Unit cost" value={unitCost} onChangeText={setUnitCost} keyboardType="numeric" placeholder="0.00" />
        <Field label="Unit price" value={unitPrice} onChangeText={setUnitPrice} keyboardType="numeric" placeholder="0.00" />
        <Field
          label="Starting stock"
          value={quantityOnHand}
          onChangeText={setQuantityOnHand}
          keyboardType="numeric"
        />
        <Field
          label="Reorder threshold"
          value={reorderThreshold}
          onChangeText={setReorderThreshold}
          keyboardType="numeric"
        />

        {error ? (
          <Text selectable style={{ color: brand.danger }}>
            {error}
          </Text>
        ) : null}

        <View>
          <Button
            label="Save item"
            busy={createItem.isPending}
            disabled={!canSubmit}
            onPress={submit}
          />
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
