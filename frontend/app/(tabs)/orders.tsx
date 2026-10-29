import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { FlatList, RefreshControl, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Order } from "@/src/api";
import { OrderCard } from "@/src/components/order-card";
import { Button, EmptyState } from "@/src/components/ui";
import { usesNativeTabs } from "@/src/navigation";
import { fonts, makeStyles, spacing, useTheme } from "@/src/theme";

export default function Orders() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const bottomChrome = usesNativeTabs ? insets.bottom : 0;
  const q = useQuery({ queryKey: ["orders"], queryFn: () => api<Order[]>("/orders") });

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.md }]}>
        <View style={styles.mark} />
        <Text style={styles.title}>Ordrar</Text>
      </View>
      <FlatList
        testID="orders-list"
        data={q.data ?? []}
        keyExtractor={(o) => o.id}
        contentContainerStyle={{ padding: spacing.lg, gap: spacing.md, paddingBottom: bottomChrome + spacing.xl, flexGrow: 1 }}
        refreshControl={<RefreshControl refreshing={q.isRefetching} onRefresh={() => q.refetch()} tintColor={colors.brandPrimary} />}
        ListEmptyComponent={
          q.isLoading ? null : q.isError ? (
            <EmptyState icon="alert-octagon" title="Kunde inte ladda ordrar" action={<Button title="Försök igen" testID="orders-retry-button" onPress={() => q.refetch()} />} />
          ) : (
            <EmptyState
              icon="package-variant"
              title="Inga ordrar än"
              text="Dina skickade beställningar visas här."
              action={<Button title="Till sortimentet" testID="orders-browse-button" onPress={() => router.push("/(tabs)")} />}
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
  header: { flexDirection: "row", alignItems: "center", gap: spacing.sm, paddingHorizontal: spacing.lg, paddingBottom: spacing.md, borderBottomWidth: 1, borderBottomColor: c.divider },
  mark: { width: 8, height: 26, backgroundColor: c.brandPrimary },
  title: { color: c.onSurface, fontFamily: fonts.displayHeavy, fontSize: 32, textTransform: "uppercase", flex: 1 },
}));
