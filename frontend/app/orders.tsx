import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { FlatList, RefreshControl, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Order } from "@/src/api";
import { OrderCard } from "@/src/components/order-card";
import { Button, EmptyState, ScreenHeader } from "@/src/components/ui";
import { makeStyles, spacing, useTheme } from "@/src/theme";

export default function Orders() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const q = useQuery({ queryKey: ["orders"], queryFn: () => api<Order[]>("/orders") });

  return (
    <View style={styles.root}>
      <ScreenHeader title="Mina ordrar" />
      <FlatList
        testID="orders-list"
        data={q.data ?? []}
        keyExtractor={(o) => o.id}
        contentContainerStyle={{ padding: spacing.lg, gap: spacing.md, paddingBottom: insets.bottom + spacing.xl, flexGrow: 1 }}
        refreshControl={<RefreshControl refreshing={q.isRefetching} onRefresh={() => q.refetch()} tintColor={colors.brandPrimary} />}
        ListEmptyComponent={
          q.isLoading ? null : q.isError ? (
            <EmptyState icon="alert-octagon" title="Kunde inte ladda ordrar" action={<Button title="Försök igen" testID="orders-retry-button" onPress={() => q.refetch()} />} />
          ) : (
            <EmptyState
              icon="package-variant"
              title="Inga ordrar än"
              text="Dina skickade beställningar visas här."
              action={<Button title="Till sortimentet" testID="orders-browse-button" onPress={() => router.dismissTo("/(tabs)/shop")} />}
            />
          )
        }
        renderItem={({ item }) => <OrderCard order={item} />}
      />
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
}));
