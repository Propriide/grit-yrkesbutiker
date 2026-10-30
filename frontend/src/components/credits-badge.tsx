import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { Pressable, Text } from "react-native";

import { api } from "@/src/api";
import { Icon } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

export type CreditTx = { id: string; amount: number; reason: "order" | "admin"; note?: string; order_number?: string; created_at: string };
export type Credits = { enabled: boolean; balance: number; history: CreditTx[] };

export const useCredits = () => useQuery({ queryKey: ["credits"], queryFn: () => api<Credits>("/credits"), staleTime: 30_000 });

export const txLabel = (t: CreditTx) => (t.reason === "order" ? `Order ${t.order_number ?? ""}`.trim() : t.note || (t.amount > 0 ? "Påfyllning" : "Avdrag"));

/** Own credit balance in the screen header; renders nothing when credits are off for the user. */
export function CreditsBadge() {
  const styles = useStyles();
  const { colors } = useTheme();
  const q = useCredits();
  if (!q.data?.enabled) return null;
  return (
    <Pressable testID="credits-badge" onPress={() => router.push("/credits")} hitSlop={6} style={styles.badge}>
      <Icon name="star-four-points" size={16} color={colors.brandSecondary} />
      <Text style={styles.text} testID="credits-balance">
        {q.data.balance}
      </Text>
      <Text style={styles.unit}>credits</Text>
    </Pressable>
  );
}

const useStyles = makeStyles((c) => ({
  badge: { flexDirection: "row", alignItems: "center", gap: 4, height: 44, paddingHorizontal: spacing.md, borderRadius: radius.md, backgroundColor: c.brandTertiary, borderWidth: 1, borderColor: c.brandPrimary },
  text: { color: c.onSurface, fontFamily: fonts.displayHeavy, fontSize: 20 },
  unit: { color: c.onSurfaceSecondary, fontFamily: fonts.body, fontSize: 11 },
}));
