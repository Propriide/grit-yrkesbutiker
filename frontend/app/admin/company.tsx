import { useQuery } from "@tanstack/react-query";
import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, FlatList, Pressable, RefreshControl, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Order, User } from "@/src/api";
import { OrderCard } from "@/src/components/order-card";
import { EmptyState, ScreenHeader } from "@/src/components/ui";
import { UserRow } from "@/src/components/user-row";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

export default function AdminCompany() {
  const { name = "" } = useLocalSearchParams<{ name: string }>();
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const [view, setView] = useState<"people" | "orders">("people");
  const users = useQuery({ queryKey: ["admin-company-users", name], queryFn: () => api<User[]>(`/admin/company-users?name=${encodeURIComponent(name)}`) });
  const orders = useQuery({ queryKey: ["admin-company-orders", name], queryFn: () => api<Order[]>(`/admin/company-orders?name=${encodeURIComponent(name)}`) });
  const active = view === "people" ? users : orders;
  const nUsers = users.data?.length;
  const nOrders = orders.data?.length;

  return (
    <View style={styles.root}>
      <ScreenHeader title={name} subtitle={nUsers !== undefined ? `${nUsers} ${nUsers === 1 ? "person" : "personer"} på företaget` : undefined} />
      <View style={styles.segment}>
        {(
          [
            ["people", `Personer${nUsers !== undefined ? ` (${nUsers})` : ""}`],
            ["orders", `Ordrar${nOrders !== undefined ? ` (${nOrders})` : ""}`],
          ] as const
        ).map(([v, label]) => (
          <Pressable key={v} testID={`company-view-${v}`} onPress={() => setView(v)} style={[styles.segBtn, view === v && styles.segBtnActive]}>
            <Text style={[styles.segText, view === v && styles.segTextActive]}>{label}</Text>
          </Pressable>
        ))}
      </View>
      <FlatList<User | Order>
        testID={view === "people" ? "company-users-list" : "company-orders-list"}
        data={(view === "people" ? users.data : orders.data) ?? []}
        keyExtractor={(x) => x.id}
        contentContainerStyle={{ padding: spacing.lg, gap: spacing.sm, paddingBottom: insets.bottom + spacing.xl, flexGrow: 1 }}
        refreshControl={<RefreshControl refreshing={active.isRefetching} onRefresh={() => active.refetch()} tintColor={colors.brandPrimary} />}
        ListEmptyComponent={
          active.isLoading ? (
            <ActivityIndicator color={colors.brandPrimary} style={{ marginTop: spacing.xxl }} />
          ) : view === "people" ? (
            <EmptyState icon="domain-off" title="Inga konton" />
          ) : (
            <EmptyState icon="package-variant" title="Inga ordrar än" text="Företaget har inte beställt något ännu." />
          )
        }
        renderItem={({ item }) =>
          view === "people" ? <UserRow user={item as User} onPress={() => router.push(`/admin/user/${item.id}`)} /> : <OrderCard order={item as Order} showCompany />
        }
      />
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  segment: { flexDirection: "row", backgroundColor: c.surfaceTertiary, borderRadius: radius.md, padding: 4, gap: 4, marginHorizontal: spacing.lg, marginTop: spacing.md },
  segBtn: { flex: 1, height: 44, borderRadius: radius.sm, alignItems: "center", justifyContent: "center" },
  segBtnActive: { backgroundColor: c.brandPrimary },
  segText: { color: c.onSurfaceSecondary, fontFamily: fonts.display, fontSize: 17, textTransform: "uppercase", letterSpacing: 1 },
  segTextActive: { color: c.onBrandPrimary },
}));
