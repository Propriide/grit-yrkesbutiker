import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { FlatList, RefreshControl, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Order } from "@/src/api";
import { OrderCard } from "@/src/components/order-card";
import { ReplySheet } from "@/src/components/reply-sheet";
import { EmptyState, haptic, ScreenHeader } from "@/src/components/ui";
import { makeStyles, spacing, useTheme } from "@/src/theme";
import { useToast } from "@/src/toast";

export default function AdminOrders() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const q = useQuery({ queryKey: ["admin-orders"], queryFn: () => api<Order[]>("/admin/orders") });
  const [target, setTarget] = useState<Order | null>(null);

  const markReady = async (o: Order) => {
    try {
      await api(`/admin/orders/${o.id}/ready`, { method: "POST" });
      haptic("success");
      toast(`Order ${o.order_number} klarmarkerad – kunden har fått besked`, "success");
      q.refetch();
    } catch (e: any) {
      toast(e.message, "error");
    }
  };

  return (
    <View style={styles.root}>
      <ScreenHeader title="Alla ordrar" subtitle={q.data ? `${q.data.length} st` : undefined} />
      <FlatList
        testID="admin-orders-list"
        data={q.data ?? []}
        keyExtractor={(o) => o.id}
        contentContainerStyle={{ padding: spacing.lg, gap: spacing.md, paddingBottom: insets.bottom + spacing.xl, flexGrow: 1 }}
        refreshControl={<RefreshControl refreshing={q.isRefetching} onRefresh={() => q.refetch()} tintColor={colors.brandPrimary} />}
        ListEmptyComponent={q.isLoading ? null : <EmptyState icon="package-variant" title="Inga ordrar än" />}
        renderItem={({ item }) => <OrderCard order={item} showCompany onReply={() => setTarget(item)} onReady={() => markReady(item)} />}
      />
      <ReplySheet order={target} onClose={() => setTarget(null)} onDone={() => q.refetch()} />
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
}));
