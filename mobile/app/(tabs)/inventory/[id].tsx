import { Stack, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, ScrollView, Text, View } from "react-native";

import { ApiError } from "@/api/client";
import { useInventoryItem, useUpdateInventoryItem } from "@/inventory/use-inventory-items";
import { colors, useBrandColors } from "@/theme/colors";
import { spacing } from "@/theme/layout";
import { type } from "@/theme/type";
import { Button } from "@/ui/button";
import { Centered } from "@/ui/empty-state";
import { Field } from "@/ui/field";

export default function InventoryItemDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const brand = useBrandColors();

  const { data: item, isLoading, error } = useInventoryItem(id);
  const updateItem = useUpdateInventoryItem(id);

  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [unitCost, setUnitCost] = useState("");
  const [unitPrice, setUnitPrice] = useState("");
  const [reorderThreshold, setReorderThreshold] = useState("");
  const [saveError, setSaveError] = useState<string | null>(null);

  function startEditing() {
    if (!item) return;
    setName(item.name);
    setCategory(item.category ?? "");
    setUnitCost(String(item.unit_cost));
    setUnitPrice(String(item.unit_price));
    setReorderThreshold(String(item.reorder_threshold));
    setSaveError(null);
    setEditing(true);
  }

  async function save() {
    const cost = Number(unitCost);
    const price = Number(unitPrice);
    const threshold = Number(reorderThreshold);
    if (
      name.trim().length === 0 ||
      Number.isNaN(cost) ||
      cost < 0 ||
      Number.isNaN(price) ||
      price < 0 ||
      Number.isNaN(threshold) ||
      threshold < 0
    ) {
      setSaveError("Check the numbers — cost, price and reorder threshold must all be 0 or more.");
      return;
    }
    setSaveError(null);
    try {
      await updateItem.mutateAsync({
        name: name.trim(),
        category: category.trim() || undefined,
        unit_cost: cost,
        unit_price: price,
        reorder_threshold: threshold,
      });
      setEditing(false);
    } catch (e) {
      setSaveError(e instanceof ApiError ? e.message : "Couldn't save. Try again.");
    }
  }

  if (isLoading) {
    return (
      <ScrollView contentInsetAdjustmentBehavior="automatic" style={{ backgroundColor: colors.background }}>
        <Centered>
          <ActivityIndicator />
        </Centered>
      </ScrollView>
    );
  }

  if (error || !item) {
    return (
      <ScrollView contentInsetAdjustmentBehavior="automatic" style={{ backgroundColor: colors.background }}>
        <Centered>
          <Text selectable style={{ ...type.body, color: brand.danger, textAlign: "center" }}>
            {error instanceof Error ? error.message : "Couldn't load this item."}
          </Text>
        </Centered>
      </ScrollView>
    );
  }

  const low = item.quantity_on_hand <= item.reorder_threshold;

  return (
    <ScrollView
      contentInsetAdjustmentBehavior="automatic"
      style={{ backgroundColor: colors.background }}
      contentContainerStyle={{ padding: spacing.lg, gap: spacing.xl }}
    >
      <Stack.Screen options={{ title: item.name }} />

      {editing ? (
        <View style={{ gap: spacing.lg }}>
          <Field label="Name" value={name} onChangeText={setName} />
          <Field label="Category" value={category} onChangeText={setCategory} />
          <Field label="Unit cost" value={unitCost} onChangeText={setUnitCost} keyboardType="numeric" />
          <Field label="Unit price" value={unitPrice} onChangeText={setUnitPrice} keyboardType="numeric" />
          <Field
            label="Reorder threshold"
            value={reorderThreshold}
            onChangeText={setReorderThreshold}
            keyboardType="numeric"
          />
          {saveError ? (
            <Text selectable style={{ color: brand.danger }}>
              {saveError}
            </Text>
          ) : null}
          <View style={{ flexDirection: "row", gap: spacing.sm }}>
            <View style={{ flex: 1 }}>
              <Button label="Save" busy={updateItem.isPending} onPress={save} />
            </View>
            <View style={{ flex: 1 }}>
              <Button label="Cancel" onPress={() => setEditing(false)} />
            </View>
          </View>
        </View>
      ) : (
        <View style={{ gap: spacing.lg }}>
          <View style={{ gap: spacing.xs }}>
            <Text style={{ ...type.overline, color: colors.secondaryLabel }}>SKU</Text>
            <Text selectable style={{ ...type.body, color: colors.label }}>
              {item.sku}
            </Text>
          </View>

          {item.category ? (
            <View style={{ gap: spacing.xs }}>
              <Text style={{ ...type.overline, color: colors.secondaryLabel }}>Category</Text>
              <Text selectable style={{ ...type.body, color: colors.label }}>
                {item.category}
              </Text>
            </View>
          ) : null}

          <View style={{ gap: spacing.xs }}>
            <Text style={{ ...type.overline, color: colors.secondaryLabel }}>On hand</Text>
            <Text style={{ ...type.numeric, fontSize: 24, color: low ? brand.accent : colors.label }}>
              {item.quantity_on_hand}
            </Text>
            <Text style={{ ...type.caption, color: colors.secondaryLabel }}>
              {low
                ? `Below the reorder threshold of ${item.reorder_threshold} — flagged on the list.`
                : `Reorder threshold: ${item.reorder_threshold}`}
            </Text>
            <Text style={{ ...type.caption, color: colors.secondaryLabel }}>
              Stock only changes through job parts used or a purchase order received — not editable
              here.
            </Text>
          </View>

          <View style={{ flexDirection: "row", gap: spacing.xl }}>
            <View style={{ gap: spacing.xs }}>
              <Text style={{ ...type.overline, color: colors.secondaryLabel }}>Cost</Text>
              <Text style={{ ...type.numeric, color: colors.label }}>
                LKR {item.unit_cost.toFixed(2)}
              </Text>
            </View>
            <View style={{ gap: spacing.xs }}>
              <Text style={{ ...type.overline, color: colors.secondaryLabel }}>Price</Text>
              <Text style={{ ...type.numeric, color: colors.label }}>
                LKR {item.unit_price.toFixed(2)}
              </Text>
            </View>
          </View>

          <Button label="Edit" onPress={startEditing} />
        </View>
      )}
    </ScrollView>
  );
}
