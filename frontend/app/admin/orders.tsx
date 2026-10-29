import { useQuery } from "@tanstack/react-query";
import { FlatList, RefreshControl, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Order } from "@/src/api";
import { OrderCard } from "@/src/components/order-card";
import { EmptyState, ScreenHeader } from "@/src/components/ui";
import { spacing, useTheme } from "@/src/theme";

export default function AdminOrders() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const q = useQuery({ queryKey: ["admin-orders"], queryFn: () => api<Order[]>("/admin/orders") });
  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <ScreenHeader title="Alla ordrar" subtitle={q.data ? `${q.data.length} st` : undefined} />
      <FlatList
        testID="admin-orders-list"
        data={q.data ?? []}
        keyExtractor={(o) => o.id}
        contentContainerStyle={{ padding: spacing.lg, gap: spacing.md, paddingBottom: insets.bottom + spacing.xl, flexGrow: 1 }}
        refreshControl={<RefreshControl refreshing={q.isRefetching} onRefresh={() => q.refetch()} tintColor={colors.brandPrimary} />}
        ListEmptyComponent={q.isLoading ? null : <EmptyState icon="package-variant" title="Inga ordrar än" />}
        renderItem={({ item }) => <OrderCard order={item} showCompany />}
      />
    </View>
  );
}
