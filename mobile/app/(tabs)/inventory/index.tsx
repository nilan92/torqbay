import { Link } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  Switch,
  Text,
  View,
} from "react-native";

import { useInventoryItems, type InventoryItem } from "@/inventory/use-inventory-items";
import { colors, useBrandColors } from "@/theme/colors";
import { continuous, radius, spacing } from "@/theme/layout";
import { type } from "@/theme/type";
import { Button } from "@/ui/button";
import { Centered, EmptyState } from "@/ui/empty-state";

function ItemCard({ item }: { item: InventoryItem }) {
  const brand = useBrandColors();
  const low = item.quantity_on_hand <= item.reorder_threshold;

  return (
    <Link href={`/(tabs)/inventory/${item.id}`} asChild>
      <Pressable
        style={({ pressed }) => ({
          backgroundColor: colors.groupedBackground,
          borderRadius: radius.md,
          padding: spacing.lg,
          gap: spacing.sm,
          borderLeftWidth: low ? 3 : 0,
          borderLeftColor: brand.accent,
          opacity: pressed ? 0.7 : 1,
          ...continuous,
        })}
      >
        <View style={{ flexDirection: "row", justifyContent: "space-between", gap: spacing.sm }}>
          <Text selectable style={{ ...type.heading, color: colors.label, flex: 1 }}>
            {item.name}
          </Text>
          <Text style={{ ...type.numeric, color: colors.label }}>
            {item.quantity_on_hand}
          </Text>
        </View>
        <Text style={{ ...type.caption, color: colors.secondaryLabel }}>{item.sku}</Text>
        {low ? (
          <Text style={{ ...type.overline, color: brand.accent }}>Low stock</Text>
        ) : null}
      </Pressable>
    </Link>
  );
}

export default function Inventory() {
  const [lowStockOnly, setLowStockOnly] = useState(false);
  const { data, isLoading, isRefetching, error, refetch } = useInventoryItems({
    lowStock: lowStockOnly,
  });
  const brand = useBrandColors();

  if (isLoading) {
    return (
      <Centered>
        <ActivityIndicator />
      </Centered>
    );
  }

  if (error) {
    return (
      <Centered>
        <Text selectable style={{ ...type.body, color: brand.danger, textAlign: "center" }}>
          {error instanceof Error ? error.message : "Couldn't load inventory."}
        </Text>
        <Text style={{ ...type.caption, color: colors.secondaryLabel }}>
          Pull down to try again.
        </Text>
      </Centered>
    );
  }

  return (
    <FlatList
      contentInsetAdjustmentBehavior="automatic"
      style={{ backgroundColor: colors.background }}
      contentContainerStyle={{ padding: spacing.lg, gap: spacing.md }}
      data={data?.items ?? []}
      keyExtractor={(item) => item.id}
      renderItem={({ item }) => <ItemCard item={item} />}
      refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
      ListHeaderComponent={
        <View style={{ gap: spacing.md, marginBottom: spacing.md }}>
          <Link href="/(tabs)/inventory/new" asChild>
            <Button label="Add item" onPress={() => {}} />
          </Link>
          <View
            style={{
              flexDirection: "row",
              alignItems: "center",
              justifyContent: "space-between",
              paddingHorizontal: spacing.xs,
            }}
          >
            <Text style={{ ...type.body, color: colors.label }}>Low stock only</Text>
            <Switch
              value={lowStockOnly}
              onValueChange={setLowStockOnly}
              trackColor={{ true: brand.brand as string }}
            />
          </View>
        </View>
      }
      ListEmptyComponent={
        <EmptyState
          title={lowStockOnly ? "Nothing is low" : "No items yet"}
          message={
            lowStockOnly
              ? "Every item is above its reorder threshold."
              : "Parts and supplies you add will show up here."
          }
        />
      }
    />
  );
}
