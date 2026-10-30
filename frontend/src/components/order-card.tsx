import { router } from "expo-router";
import { useState } from "react";
import { Pressable, Text, View } from "react-native";

import { Order } from "@/src/api";
import { Icon } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

export function formatDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString("sv-SE") + " " + d.toLocaleTimeString("sv-SE", { hour: "2-digit", minute: "2-digit" });
}

export function OrderCard({ order, showCompany, onReply }: { order: Order; showCompany?: boolean; onReply?: () => void }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const [open, setOpen] = useState(false);
  const qty = order.items.reduce((s, i) => s + i.quantity, 0);
  const sent = order.email_status === "sent";
  const confirmed = order.status === "confirmed";
  const declined = order.status === "declined";
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
        <View style={[styles.status, sent ? styles.statusOk : styles.statusFail, confirmed && styles.statusConfirmed, declined && styles.statusFail]} testID={`order-status-${order.order_number}`}>
          <Text style={[styles.statusText, (!sent || declined) && { color: colors.onError }, confirmed && { color: colors.onBrandSecondary }]}>
            {confirmed ? "Bekräftad" : declined ? "Nekad" : "Skickad"}
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
          <Pressable testID={`order-timeline-link-${order.order_number}`} onPress={() => router.push(`/order/${order.id}`)} style={styles.timelineLink}>
            <Icon name="timeline-clock-outline" size={18} color={colors.brandPrimary} />
            <Text style={styles.timelineLinkText}>Visa tidslinje</Text>
          </Pressable>
          {onReply && (
            <Pressable testID={`order-reply-button-${order.order_number}`} onPress={onReply} style={styles.replyBtn}>
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
  statusFail: { backgroundColor: c.error },
  statusConfirmed: { backgroundColor: c.brandSecondary },
  replyBtn: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.sm, minHeight: 48, borderRadius: radius.md, backgroundColor: c.brandPrimary, marginTop: spacing.md },
  timelineLink: { flexDirection: "row", alignItems: "center", gap: spacing.sm, minHeight: 44, marginTop: spacing.sm },
  timelineLinkText: { color: c.brandPrimary, fontFamily: fonts.bodyBold, fontSize: 14 },
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
