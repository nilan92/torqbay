import { Stack, useLocalSearchParams } from "expo-router";
import { useMemo, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, TextInput, View } from "react-native";

import { useCustomer } from "@/customers/use-customer";
import { useInventoryItems } from "@/inventory/use-inventory-items";
import { formatDuration } from "@/jobs/format-duration";
import { useAddJobPart, useJobParts } from "@/jobs/use-job-parts";
import { useJob, useUpdateJob } from "@/jobs/use-jobs";
import { useLaborEntries, useStartTimer, useStopTimer } from "@/jobs/use-labor-entries";
import { useTechnicians } from "@/technicians/use-technicians";
import { colors, useBrandColors } from "@/theme/colors";
import { formatCurrency } from "@/theme/format-currency";
import { continuous, radius, spacing } from "@/theme/layout";
import { type } from "@/theme/type";
import { Button } from "@/ui/button";
import { StatusTag } from "@/ui/status-tag";

const LOCKED_STATUSES = new Set(["invoiced", "paid"]);

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={{ gap: spacing.md }}>
      <Text style={{ ...type.overline, color: colors.secondaryLabel }}>{title}</Text>
      {children}
    </View>
  );
}

function Row({
  primary,
  secondary,
  onPress,
}: {
  primary: string;
  secondary?: string;
  onPress?: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => ({
        backgroundColor: colors.groupedBackground,
        borderRadius: radius.md,
        padding: spacing.lg,
        gap: spacing.xs,
        opacity: onPress && pressed ? 0.6 : 1,
        ...continuous,
      })}
    >
      <Text selectable style={{ ...type.body, color: colors.label }}>
        {primary}
      </Text>
      {secondary ? (
        <Text selectable style={{ ...type.caption, color: colors.secondaryLabel }}>
          {secondary}
        </Text>
      ) : null}
    </Pressable>
  );
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function JobDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const brand = useBrandColors();

  const { data: job, isLoading: jobLoading, error: jobError } = useJob(id);
  const { data: customer } = useCustomer(job?.customer_id ?? "");
  const { data: parts } = useJobParts(id);
  const { data: laborEntries } = useLaborEntries(id);
  const { data: technicians } = useTechnicians();
  const { data: inventory } = useInventoryItems();

  const updateJob = useUpdateJob(id);
  const addPart = useAddJobPart(id);
  const startTimer = useStartTimer(id);
  const stopTimer = useStopTimer(id);

  const [laborCostInput, setLaborCostInput] = useState<string | null>(null);
  const [showTechPicker, setShowTechPicker] = useState(false);
  const [showAddPart, setShowAddPart] = useState(false);
  const [partSearch, setPartSearch] = useState("");
  const [partQuantities, setPartQuantities] = useState<Record<string, number>>({});

  const inventoryById = useMemo(() => {
    const map = new Map(inventory?.items.map((item) => [item.id, item]));
    return map;
  }, [inventory]);

  const filteredInventory = useMemo(() => {
    const items = inventory?.items ?? [];
    const q = partSearch.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (item) => item.name.toLowerCase().includes(q) || item.sku.toLowerCase().includes(q)
    );
  }, [inventory, partSearch]);

  const openEntry = laborEntries?.items.find((entry) => entry.end_time === null);
  const isLocked = job ? LOCKED_STATUSES.has(job.status) : false;

  if (jobLoading) {
    return (
      <ScrollView contentInsetAdjustmentBehavior="automatic" style={{ backgroundColor: colors.background }}>
        <View style={{ padding: spacing.xxl, alignItems: "center" }}>
          <ActivityIndicator />
        </View>
      </ScrollView>
    );
  }

  if (jobError || !job) {
    return (
      <ScrollView contentInsetAdjustmentBehavior="automatic" style={{ backgroundColor: colors.background }}>
        <View style={{ padding: spacing.xxl, alignItems: "center", gap: spacing.md }}>
          <Text selectable style={{ ...type.body, color: brand.danger, textAlign: "center" }}>
            {jobError instanceof Error ? jobError.message : "Couldn't load this job."}
          </Text>
        </View>
      </ScrollView>
    );
  }

  return (
    <ScrollView
      contentInsetAdjustmentBehavior="automatic"
      style={{ backgroundColor: colors.background }}
      contentContainerStyle={{ padding: spacing.lg, gap: spacing.xl }}
    >
      <Stack.Screen options={{ title: job.title }} />

      <View style={{ gap: spacing.sm }}>
        {customer ? (
          <Text selectable style={{ ...type.heading, color: colors.label }}>
            {customer.name}
          </Text>
        ) : null}
        {job.description ? (
          <Text selectable style={{ ...type.body, color: colors.secondaryLabel }}>
            {job.description}
          </Text>
        ) : null}
        <StatusTag status={job.status} />
      </View>

      {/* Status actions */}
      <View style={{ gap: spacing.sm }}>
        {job.status === "open" ? (
          <Button
            label="Start"
            busy={updateJob.isPending}
            onPress={() => updateJob.mutate({ status: "in_progress" })}
          />
        ) : null}
        {job.status === "in_progress" ? (
          <Button
            label="Mark Done"
            busy={updateJob.isPending}
            onPress={() => updateJob.mutate({ status: "done" })}
          />
        ) : null}
      </View>

      {/* Labour charge */}
      <Section title="Labour charge">
        <View style={{ flexDirection: "row", gap: spacing.sm, alignItems: "center" }}>
          <TextInput
            value={laborCostInput ?? String(job.labor_cost)}
            onChangeText={setLaborCostInput}
            keyboardType="numeric"
            editable={!isLocked}
            placeholder="0.00"
            placeholderTextColor={colors.secondaryLabel}
            style={{
              ...type.numeric,
              color: colors.label,
              backgroundColor: colors.groupedBackground,
              borderRadius: radius.md,
              paddingHorizontal: spacing.lg,
              paddingVertical: spacing.md,
              minHeight: 52,
              flex: 1,
              opacity: isLocked ? 0.5 : 1,
              ...continuous,
            }}
          />
          {!isLocked && laborCostInput !== null && Number(laborCostInput) !== job.labor_cost ? (
            <Button
              label="Save"
              busy={updateJob.isPending}
              disabled={Number.isNaN(Number(laborCostInput)) || Number(laborCostInput) < 0}
              onPress={() => {
                const value = Number(laborCostInput);
                updateJob.mutate({ labor_cost: value });
                setLaborCostInput(null);
              }}
            />
          ) : null}
        </View>
        {isLocked ? (
          <Text style={{ ...type.caption, color: colors.secondaryLabel }}>
            This job has been {job.status} — the labour charge can no longer be changed.
          </Text>
        ) : null}
      </Section>

      {/* Time tracking */}
      <Section title="Time tracked">
        {laborEntries?.items.length ? (
          <View style={{ gap: spacing.sm }}>
            {laborEntries.items.map((entry) => (
              <Row
                key={entry.id}
                primary={
                  entry.end_time
                    ? `${formatTime(entry.start_time)} – ${formatTime(entry.end_time)}`
                    : `Started ${formatTime(entry.start_time)} — running`
                }
                secondary={formatDuration(entry.start_time, entry.end_time)}
              />
            ))}
          </View>
        ) : (
          <Text style={{ ...type.caption, color: colors.secondaryLabel }}>
            No time tracked yet.
          </Text>
        )}

        {openEntry ? (
          <Button
            label="Stop timer"
            busy={stopTimer.isPending}
            onPress={() => stopTimer.mutate(openEntry.id)}
          />
        ) : (
          <Button label="Start timer" onPress={() => setShowTechPicker((v) => !v)} />
        )}

        {showTechPicker ? (
          <View style={{ gap: spacing.xs }}>
            {technicians?.items.length ? (
              technicians.items.map((tech) => (
                <Row
                  key={tech.id}
                  primary={tech.name}
                  onPress={() => {
                    startTimer.mutate(tech.id);
                    setShowTechPicker(false);
                  }}
                />
              ))
            ) : (
              <Text style={{ ...type.caption, color: colors.secondaryLabel }}>
                No technicians yet — add one in Settings.
              </Text>
            )}
          </View>
        ) : null}
      </Section>

      {/* Parts */}
      <Section title="Parts used">
        {parts?.items.length ? (
          <View style={{ gap: spacing.sm }}>
            {parts.items.map((part) => {
              const item = inventoryById.get(part.inventory_item_id);
              return (
                <Row
                  key={part.id}
                  primary={item ? `${item.name} × ${part.quantity}` : `${part.quantity} units`}
                  secondary={
                    part.overdrawn
                      ? `Short by ${part.shortfall} — flagged for reconciliation`
                      : formatCurrency(part.quantity * part.unit_price_at_time)
                  }
                />
              );
            })}
          </View>
        ) : (
          <Text style={{ ...type.caption, color: colors.secondaryLabel }}>
            No parts added yet.
          </Text>
        )}

        <Button label="Add part" onPress={() => setShowAddPart((v) => !v)} />

        {showAddPart ? (
          <View style={{ gap: spacing.sm }}>
            <TextInput
              value={partSearch}
              onChangeText={setPartSearch}
              placeholder="Search by name or SKU"
              placeholderTextColor={colors.secondaryLabel}
              style={{
                ...type.body,
                color: colors.label,
                backgroundColor: colors.groupedBackground,
                borderRadius: radius.md,
                paddingHorizontal: spacing.lg,
                paddingVertical: spacing.md,
                minHeight: 52,
                ...continuous,
              }}
            />
            {filteredInventory.slice(0, 20).map((item) => {
              const qty = partQuantities[item.id] ?? 1;
              return (
                <View
                  key={item.id}
                  style={{
                    backgroundColor: colors.groupedBackground,
                    borderRadius: radius.md,
                    padding: spacing.lg,
                    gap: spacing.sm,
                    ...continuous,
                  }}
                >
                  <Text selectable style={{ ...type.body, color: colors.label }}>
                    {item.name}
                  </Text>
                  <Text style={{ ...type.caption, color: colors.secondaryLabel }}>
                    {item.sku} · {item.quantity_on_hand} on hand
                  </Text>
                  <View style={{ flexDirection: "row", alignItems: "center", gap: spacing.md }}>
                    <TextInput
                      value={String(qty)}
                      onChangeText={(text) =>
                        setPartQuantities((prev) => ({
                          ...prev,
                          [item.id]: Math.max(1, Number(text) || 1),
                        }))
                      }
                      keyboardType="numeric"
                      style={{
                        ...type.numeric,
                        color: colors.label,
                        backgroundColor: colors.background,
                        borderRadius: radius.sm,
                        paddingHorizontal: spacing.md,
                        paddingVertical: spacing.sm,
                        width: 64,
                        textAlign: "center",
                        ...continuous,
                      }}
                    />
                    <View style={{ flex: 1 }} />
                    <Button
                      label="Add"
                      busy={addPart.isPending}
                      onPress={() => {
                        addPart.mutate({ inventory_item_id: item.id, quantity: qty });
                        setShowAddPart(false);
                        setPartSearch("");
                      }}
                    />
                  </View>
                </View>
              );
            })}
          </View>
        ) : null}
      </Section>
    </ScrollView>
  );
}
