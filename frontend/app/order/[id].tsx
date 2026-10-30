import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, deliveryText, Order } from "@/src/api";
import { useAuth } from "@/src/auth";
import { formatDate, useReorder } from "@/src/components/order-card";
import { ReplySheet } from "@/src/components/reply-sheet";
import { Button, EmptyState, haptic, Icon, IconName, ScreenHeader } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";
import { useToast } from "@/src/toast";

type Step = { key: string; label: string; icon: IconName; date?: string; message?: string; tone: "done" | "pending" | "declined" };

function buildSteps(o: Order): Step[] {
  const answered = !!o.replies?.length;
  const steps: Step[] = [
    { key: "sent", label: "Inväntar bekräftelse", icon: answered ? "send-check" : "timer-sand", date: o.created_at, tone: answered ? "done" : "pending" },
  ];
  for (const r of o.replies ?? []) {
    const declined = r.action === "decline";
    steps.push({ key: r.created_at, label: declined ? "Nekad" : "Bekräftad", icon: declined ? "close-octagon" : "check-decagram", date: r.created_at, message: r.message, tone: declined ? "declined" : "done" });
  }
  if (o.status === "ready") steps.push({ key: "ready", label: "Klar", icon: "package-variant-closed-check", date: o.ready_at, message: "Ordern är klar.", tone: "done" });
  return steps;
}

export default function OrderDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { user } = useAuth();
  const qc = useQueryClient();
  const reorder = useReorder();
  const toast = useToast();
  const q = useQuery({ queryKey: ["order", id], queryFn: () => api<Order>(`/orders/${id}`) });
  const o = q.data;
  const [readying, setReadying] = useState(false);
  const [replyOpen, setReplyOpen] = useState(false);

  const markReady = async () => {
    setReadying(true);
    try {
      await api(`/admin/orders/${id}/ready`, { method: "POST" });
      haptic("success");
      toast("Ordern är klarmarkerad – kunden har fått besked", "success");
      q.refetch();
      qc.invalidateQueries({ queryKey: ["admin-orders"] });
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setReadying(false);
    }
  };

  useEffect(() => {
    if (o) qc.invalidateQueries({ queryKey: ["notifications"] });
  }, [o, qc]);

  const toneColor = (t: Step["tone"]) => (t === "declined" ? colors.error : t === "pending" ? colors.borderStrong : colors.brandPrimary);

  return (
    <View style={styles.root}>
      <ScreenHeader title={o ? `Order ${o.order_number}` : "Order"} subtitle={o?.customer.company} />
      {q.isLoading ? (
        <ActivityIndicator color={colors.brandPrimary} style={{ marginTop: spacing.xxl }} />
      ) : !o ? (
        <EmptyState icon="alert-octagon" title="Ordern hittades inte" action={<Button title="Försök igen" testID="order-retry-button" onPress={() => q.refetch()} />} />
      ) : (
        <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + spacing.xl }}>
          <Text style={styles.section}>Tidslinje</Text>
          <View style={styles.card} testID="order-timeline">
            {buildSteps(o).map((s, i, arr) => (
              <View key={`${s.key}-${i}`} style={styles.step} testID={`timeline-step-${s.tone === "pending" ? "pending" : s.label.toLowerCase()}-${i}`}>
                <View style={styles.rail}>
                  <View style={[styles.dot, { backgroundColor: toneColor(s.tone) }]}>
                    <Icon name={s.icon} size={16} color={s.tone === "pending" ? colors.onSurface : s.tone === "declined" ? colors.onError : colors.onBrandPrimary} />
                  </View>
                  {i < arr.length - 1 && <View style={styles.line} />}
                </View>
                <View style={{ flex: 1, paddingBottom: spacing.lg }}>
                  <Text style={[styles.stepLabel, s.tone === "pending" && { color: colors.muted }]}>{s.label}</Text>
                  {!!s.date && <Text style={styles.stepDate}>{formatDate(s.date)}</Text>}
                  {!!s.message && <Text style={styles.stepMsg}>{s.message}</Text>}
                </View>
              </View>
            ))}
          </View>

          <Text style={styles.section}>Artiklar</Text>
          <View style={styles.card}>
            {o.items.map((i, idx) => (
              <View key={idx} style={[styles.itemRow, idx === o.items.length - 1 && { borderBottomWidth: 0 }]}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.itemName}>{i.name}</Text>
                  <Text style={styles.itemMeta}>
                    {i.part_no}
                    {i.color_code ? `-${i.color_code}` : ""} · Storlek {i.size}
                    {i.color_name ? ` · ${i.color_name}` : ""}
                  </Text>
                </View>
                <Text style={styles.itemQty}>{i.quantity} st</Text>
              </View>
            ))}
          </View>
          {!!o.delivery && (
            <>
              <Text style={styles.section}>Leverans</Text>
              <View style={[styles.card, { padding: spacing.lg }]} testID="order-delivery">
                <Text style={styles.stepMsg}>{deliveryText(o.delivery)}</Text>
              </View>
            </>
          )}
          {!!o.credits_earned && (
            <Text style={[styles.stepMsg, { marginTop: spacing.md, color: colors.brandSecondary }]} testID="order-credits-earned">
              +{o.credits_earned} credits intjänade på ordern
            </Text>
          )}
          {!!o.comment && (
            <>
              <Text style={styles.section}>Kommentar</Text>
              <View style={[styles.card, { padding: spacing.lg }]}>
                <Text style={styles.stepMsg}>{o.comment}</Text>
              </View>
            </>
          )}
          {o.user_id === user?.id && (
            <Button
              title="Beställ igen"
              icon="cart-arrow-down"
              testID="order-reorder-button"
              style={{ marginTop: spacing.xl }}
              onPress={() => reorder(o)}
            />
          )}
          {user?.role === "admin" && o.status === "confirmed" && (
            <Button title="Klarmarkera order" icon="package-variant-closed-check" testID="order-ready-button" onPress={markReady} loading={readying} style={{ marginTop: spacing.xl }} />
          )}
          {user?.role === "admin" && (o.status ?? "new") !== "ready" && (
            <Button
              title={o.status === "confirmed" || o.status === "declined" ? "Skicka nytt svar" : "Bekräfta / neka order"}
              icon="check-decagram"
              variant={o.status === "confirmed" ? "secondary" : undefined}
              testID="order-reply-open-button"
              onPress={() => setReplyOpen(true)}
              style={{ marginTop: spacing.md }}
            />
          )}
          {user?.role === "admin" && <ReplySheet order={replyOpen ? o : null} onClose={() => setReplyOpen(false)} onDone={() => { q.refetch(); qc.invalidateQueries({ queryKey: ["admin-orders"] }); }} />}
        </ScrollView>
      )}
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  section: { color: c.brandPrimary, fontFamily: fonts.display, fontSize: 16, letterSpacing: 1.5, textTransform: "uppercase", marginTop: spacing.lg, marginBottom: spacing.sm },
  card: { backgroundColor: c.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, paddingHorizontal: spacing.lg, paddingTop: spacing.lg },
  step: { flexDirection: "row", gap: spacing.md },
  rail: { alignItems: "center", width: 28 },
  dot: { width: 28, height: 28, borderRadius: 14, alignItems: "center", justifyContent: "center" },
  line: { flex: 1, width: 2, backgroundColor: c.borderStrong, marginVertical: 2 },
  stepLabel: { color: c.onSurface, fontFamily: fonts.display, fontSize: 20, textTransform: "uppercase" },
  stepDate: { color: c.muted, fontFamily: fonts.body, fontSize: 12 },
  stepMsg: { color: c.onSurfaceSecondary, fontFamily: fonts.body, fontSize: 14, marginTop: spacing.xs, lineHeight: 20 },
  itemRow: { flexDirection: "row", alignItems: "center", gap: spacing.md, paddingBottom: spacing.md, marginBottom: spacing.md, borderBottomWidth: 1, borderBottomColor: c.divider },
  itemName: { color: c.onSurface, fontFamily: fonts.bodyBold, fontSize: 14 },
  itemMeta: { color: c.muted, fontFamily: fonts.body, fontSize: 12, marginTop: 2 },
  itemQty: { color: c.brandSecondary, fontFamily: fonts.displayHeavy, fontSize: 20 },
}));
