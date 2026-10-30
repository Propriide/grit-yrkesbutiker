import { router } from "expo-router";
import { useState } from "react";
import { Pressable, Text, View } from "react-native";

import { Order } from "@/src/api";
import { useAuth } from "@/src/auth";
import { useCart } from "@/src/cart";
import { haptic, Icon } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";
import { useToast } from "@/src/toast";

export function formatDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString("sv-SE") + " " + d.toLocaleTimeString("sv-SE", { hour: "2-digit", minute: "2-digit" });
}

export function useReorder() {
  const cart = useCart();
  const toast = useToast();
  return (o: Order) => {
    for (const i of o.items) {
      cart.add({ part_no: i.part_no, name: i.name, image_url: i.image_url, color_code: i.color_code, color_name: i.color_name, size: i.size, quantity: i.quantity });
    }
    haptic("success");
    toast(`${o.items.reduce((s, i) => s + i.quantity, 0)} st lagda i varukorgen`, "success");
    router.dismissTo("/(tabs)/cart");
  };
}

export const STATUS_LABELS = { new: "Inväntar bekräftelse", confirmed: "Bekräftad", declined: "Nekad", ready: "Klar" } as const;

export function OrderCard({ order, showCompany, onReply, onReady }: { order: Order; showCompany?: boolean; onReply?: () => void; onReady?: () => void }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const { user } = useAuth();
  const reorder = useReorder();
  const [open, setOpen] = useState(false);
  const qty = order.items.reduce((s, i) => s + i.quantity, 0);
  const status = order.status ?? "new";
  const confirmed = status === "confirmed";
  const declined = status === "declined";
  const ready = status === "ready";
  const mine = !!user && order.user_id === user.id;
  const replies = order.replies ?? [];
  const lastReply = replies[replies.length - 1];
  return (
    <Pressable testID={`order-card-${order.order_number}`} onPress={() => setOpen(!open)} style={styles.card}>
      <View style={styles.cardTop}>
        <View style={{ flex: 1 }}>
          <Text style={styles.num}>{order.order_number}</Text>
          <Text style={styles.date}>
            {formatDate(order.created_at)}
            {showCompany ? `  ·  ${order.customer.company}` : ""}
          </Text>
        </View>
        <View style={[styles.status, styles.statusPending, confirmed && styles.statusConfirmed, ready && styles.statusOk, declined && styles.statusFail]} testID={`order-status-${order.order_number}`}>
          <Text style={[styles.statusText, status === "new" && { color: colors.onSurface }, declined && { color: colors.onError }, confirmed && { color: colors.onInfo }]}>
            {STATUS_LABELS[status]}
          </Text>
        </View>
        <Icon name={open ? "chevron-up" : "chevron-down"} size={22} color={colors.muted} />
      </View>
      <Text style={styles.summary}>
        {order.items.length} {order.items.length === 1 ? "artikel" : "artiklar"} · {qty} st{showCompany ? `  ·  ${order.customer.email}` : ""}
      </Text>
      {lastReply && (
        <View style={styles.replyBox} testID={`order-reply-${order.order_number}`}>
          <Icon name="message-reply-text" size={18} color={colors.brandSecondary} />
          <View style={{ flex: 1 }}>
            <Text style={styles.replyText}>{lastReply.message}</Text>
            <Text style={styles.replyDate}>{formatDate(lastReply.created_at)}</Text>
          </View>
        </View>
      )}
      {open && (
        <View style={styles.details}>
          {order.items.map((i, idx) => (
            <View key={idx} style={styles.itemRow}>
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
          {replies.length > 1 && (
            <View style={styles.commentBox}>
              <Text style={styles.commentLabel}>Alla svar från leverantören</Text>
              {replies.map((r, idx) => (
                <Text key={idx} style={styles.comment}>
                  {formatDate(r.created_at)}: {r.message}
                </Text>
              ))}
            </View>
          )}
          {!!order.comment && (
            <View style={styles.commentBox}>
              <Text style={styles.commentLabel}>Kommentar</Text>
              <Text style={styles.comment}>{order.comment}</Text>
            </View>
          )}
          {mine && (
            <Pressable testID={`order-card-reorder-${order.order_number}`} onPress={() => reorder(order)} style={styles.replyBtn}>
              <Icon name="cart-arrow-down" size={20} color={colors.onBrandPrimary} />
              <Text style={styles.replyBtnText}>Beställ igen</Text>
            </Pressable>
          )}
          <Pressable testID={`order-timeline-link-${order.order_number}`} onPress={() => router.push(`/order/${order.id}`)} style={styles.timelineLink}>
            <Icon name="timeline-clock-outline" size={18} color={colors.brandSecondary} />
            <Text style={styles.timelineLinkText}>Visa tidslinje</Text>
          </Pressable>
          {onReady && confirmed && (
            <Pressable testID={`order-ready-button-${order.order_number}`} onPress={onReady} style={[styles.replyBtn, { backgroundColor: colors.success }]}>
              <Icon name="package-variant-closed-check" size={20} color={colors.onSuccess} />
              <Text style={[styles.replyBtnText, { color: colors.onSuccess }]}>Klarmarkera</Text>
            </Pressable>
          )}
          {onReply && !ready && (
            <Pressable testID={`order-reply-button-${order.order_number}`} onPress={onReply} style={[styles.replyBtn, confirmed && styles.replyBtnSecondary]}>
              <Icon name="check-decagram" size={20} color={colors.onBrandPrimary} />
              <Text style={styles.replyBtnText}>{confirmed || declined ? "Skicka nytt svar" : "Bekräfta / neka order"}</Text>
            </Pressable>
          )}
        </View>
      )}
    </Pressable>
  );
}

const useStyles = makeStyles((c) => ({
  card: { backgroundColor: c.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, padding: spacing.lg },
  cardTop: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  num: { color: c.onSurface, fontFamily: fonts.displayHeavy, fontSize: 24 },
  date: { color: c.muted, fontFamily: fonts.body, fontSize: 12 },
  status: { paddingHorizontal: spacing.sm, paddingVertical: 4, borderRadius: radius.sm },
  statusOk: { backgroundColor: c.success },
  statusPending: { backgroundColor: c.surfaceTertiary },
  statusFail: { backgroundColor: c.error },
  statusConfirmed: { backgroundColor: c.info },
  replyBtnSecondary: { backgroundColor: c.surfaceTertiary },
  replyBtn: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.sm, minHeight: 48, borderRadius: radius.md, backgroundColor: c.brandPrimary, marginTop: spacing.md },
  timelineLink: { flexDirection: "row", alignItems: "center", gap: spacing.sm, minHeight: 44, marginTop: spacing.sm },
  timelineLinkText: { color: c.brandSecondary, fontFamily: fonts.bodyBold, fontSize: 14 },
  replyBtnText: { color: c.onBrandPrimary, fontFamily: fonts.display, fontSize: 17, textTransform: "uppercase", letterSpacing: 1 },
  replyBox: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.md, backgroundColor: c.brandTertiary, borderRadius: radius.sm, padding: spacing.md },
  replyText: { color: c.onSurface, fontFamily: fonts.bodyBold, fontSize: 14 },
  replyDate: { color: c.onSurfaceTertiary, fontFamily: fonts.body, fontSize: 11, marginTop: 2 },
  statusText: { color: c.onSuccess, fontFamily: fonts.bodyBold, fontSize: 11, textTransform: "uppercase" },
  summary: { color: c.onSurfaceTertiary, fontFamily: fonts.body, fontSize: 13, marginTop: spacing.sm },
  details: { marginTop: spacing.md, borderTopWidth: 1, borderTopColor: c.divider, paddingTop: spacing.sm },
  itemRow: { flexDirection: "row", alignItems: "center", paddingVertical: spacing.sm, gap: spacing.md },
  itemName: { color: c.onSurface, fontFamily: fonts.bodyBold, fontSize: 13 },
  itemMeta: { color: c.muted, fontFamily: fonts.body, fontSize: 12 },
  itemQty: { color: c.brandSecondary, fontFamily: fonts.displayHeavy, fontSize: 18 },
  commentBox: { marginTop: spacing.sm, backgroundColor: c.surfaceTertiary, borderRadius: radius.sm, padding: spacing.md },
  commentLabel: { color: c.muted, fontFamily: fonts.bodyBold, fontSize: 11, textTransform: "uppercase", marginBottom: 2 },
  comment: { color: c.onSurfaceSecondary, fontFamily: fonts.body, fontSize: 13 },
}));
