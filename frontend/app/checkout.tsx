import { useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import { useState } from "react";
import { Text, TextInput, View } from "react-native";
import { KeyboardAwareScrollView, KeyboardStickyView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Order } from "@/src/api";
import { useAuth } from "@/src/auth";
import { useCart } from "@/src/cart";
import { Button, EmptyState, ErrorBanner, haptic, Icon, ScreenHeader } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

export default function Checkout() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const cart = useCart();
  const { user } = useAuth();
  const qc = useQueryClient();
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState<Order | null>(null);

  const submit = async () => {
    setLoading(true);
    setError("");
    try {
      const order = await api<Order>("/orders", {
        method: "POST",
        body: {
          comment,
          items: cart.items.map((i) => ({ part_no: i.part_no, color_code: i.color_code, size: i.size, quantity: i.quantity })),
        },
      });
      haptic("success");
      cart.clear();
      qc.invalidateQueries({ queryKey: ["orders"] });
      setDone(order);
    } catch (e: any) {
      haptic("error");
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  if (done) {
    return (
      <View style={[styles.root, { paddingTop: insets.top, paddingBottom: insets.bottom + spacing.lg }]}>
        <View style={{ flex: 1, justifyContent: "center" }} testID="order-success">
          <View style={styles.successIcon}>
            <Icon name="check-bold" size={48} color={colors.onSuccess} />
          </View>
          <Text style={styles.successTitle}>{done.email_status === "sent" ? "Beställning skickad" : "Beställning sparad"}</Text>
          <Text style={styles.successNum} testID="order-success-number">
            Order {done.order_number}
          </Text>
          {done.email_status === "sent" ? (
            <Text style={styles.successText}>Din beställning för {done.customer.company} har skickats. Du hittar den under Ordrar.</Text>
          ) : (
            <Text style={[styles.successText, { color: colors.warning }]} testID="order-email-warning">
              Ordern är sparad, men mejlet till leverantören kunde inte skickas just nu. Administratören ser ordern i appen – lägg inte ordern igen.
            </Text>
          )}
        </View>
        <View style={{ paddingHorizontal: spacing.xl, gap: spacing.md }}>
          <Button title="Visa ordrar" testID="order-success-orders-button" onPress={() => router.replace("/orders")} />
          <Button title="Fortsätt handla" variant="secondary" testID="order-success-shop-button" onPress={() => router.dismissTo("/(tabs)/shop")} />
        </View>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <ScreenHeader title="Kassa" subtitle={user?.company} />
      {cart.items.length === 0 ? (
        <EmptyState icon="cart-outline" title="Varukorgen är tom" action={<Button title="Till sortimentet" testID="checkout-browse-button" onPress={() => router.dismissTo("/(tabs)/shop")} />} />
      ) : (
        <>
          <KeyboardAwareScrollView bottomOffset={100} keyboardShouldPersistTaps="handled" contentContainerStyle={styles.content}>
            {!!error && <ErrorBanner message={error} testID="checkout-error" />}
            <Text style={styles.section}>Beställare</Text>
            <View style={styles.card}>
              <Row label="Företag" value={user?.company} />
              {!!user?.org_number && <Row label="Org.nr" value={user.org_number} />}
              {!!user?.city_name && <Row label="Ort" value={user.city_name} />}
              <Row label="E-post" value={user?.email} />
              <Row label="Telefon" value={user?.phone} last />
            </View>

            <Text style={styles.section}>Artiklar ({cart.count} st)</Text>
            <View style={styles.card}>
              {cart.items.map((i, idx) => (
                <View key={i.key} style={[styles.itemRow, idx === cart.items.length - 1 && { borderBottomWidth: 0 }]}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.itemName} numberOfLines={1}>
                      {i.name}
                    </Text>
                    <Text style={styles.itemMeta}>
                      {i.part_no}
                      {i.color_code ? `-${i.color_code}` : ""} · Storlek {i.size}
                    </Text>
                  </View>
                  <Text style={styles.itemQty}>{i.quantity} st</Text>
                </View>
              ))}
            </View>

            <Text style={styles.section}>Kommentar / önskat leveransdatum</Text>
            <TextInput
              testID="checkout-comment-input"
              value={comment}
              onChangeText={setComment}
              multiline
              maxLength={2000}
              placeholder="T.ex. leverans senast fredag v.24, märkning med logga..."
              placeholderTextColor={colors.muted}
              style={styles.comment}
              textAlignVertical="top"
            />
          </KeyboardAwareScrollView>
          <KeyboardStickyView offset={{ opened: insets.bottom }}>
            <View style={[styles.footer, { paddingBottom: insets.bottom + spacing.md }]}>
              <Button title="Skicka beställning" icon="send" testID="checkout-submit-button" onPress={submit} loading={loading} />
            </View>
          </KeyboardStickyView>
        </>
      )}
    </View>
  );
}

function Row({ label, value, last }: { label: string; value?: string | null; last?: boolean }) {
  const styles = useStyles();
  return (
    <View style={[styles.infoRow, last && { borderBottomWidth: 0 }]}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={styles.infoValue} numberOfLines={1}>
        {value || "-"}
      </Text>
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  content: { padding: spacing.lg, paddingBottom: spacing.xxl },
  section: { color: c.brandPrimary, fontFamily: fonts.display, fontSize: 16, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: spacing.sm, marginTop: spacing.lg },
  card: { backgroundColor: c.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, paddingHorizontal: spacing.md },
  infoRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: spacing.md, borderBottomWidth: 1, borderBottomColor: c.divider, gap: spacing.md },
  infoLabel: { color: c.muted, fontFamily: fonts.body, fontSize: 13 },
  infoValue: { color: c.onSurface, fontFamily: fonts.bodyBold, fontSize: 13, flexShrink: 1 },
  itemRow: { flexDirection: "row", alignItems: "center", paddingVertical: spacing.md, borderBottomWidth: 1, borderBottomColor: c.divider, gap: spacing.md },
  itemName: { color: c.onSurface, fontFamily: fonts.bodyBold, fontSize: 14 },
  itemMeta: { color: c.muted, fontFamily: fonts.body, fontSize: 12, marginTop: 2 },
  itemQty: { color: c.brandSecondary, fontFamily: fonts.displayHeavy, fontSize: 20 },
  comment: {
    minHeight: 120,
    backgroundColor: c.surfaceTertiary,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: c.border,
    color: c.onSurface,
    padding: spacing.lg,
    fontFamily: fonts.body,
    fontSize: 15,
  },
  footer: { paddingHorizontal: spacing.lg, paddingTop: spacing.md, backgroundColor: c.surface, borderTopWidth: 1, borderTopColor: c.divider },
  successIcon: { width: 96, height: 96, borderRadius: radius.lg, backgroundColor: c.success, alignItems: "center", justifyContent: "center", alignSelf: "center", marginBottom: spacing.xl },
  successTitle: { color: c.onSurface, fontFamily: fonts.displayHeavy, fontSize: 36, textTransform: "uppercase", textAlign: "center" },
  successNum: { color: c.brandPrimary, fontFamily: fonts.display, fontSize: 22, textAlign: "center", marginTop: spacing.xs },
  successText: { color: c.onSurfaceSecondary, fontFamily: fonts.body, fontSize: 15, textAlign: "center", marginTop: spacing.md, paddingHorizontal: spacing.xl },
}));
