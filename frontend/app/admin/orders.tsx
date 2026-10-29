import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { FlatList, Modal, Platform, Pressable, RefreshControl, Text, TextInput, View } from "react-native";
import { KeyboardAvoidingView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Order } from "@/src/api";
import { OrderCard } from "@/src/components/order-card";
import { Button, EmptyState, ErrorBanner, haptic, Icon, ScreenHeader } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";
import { useToast } from "@/src/toast";

export default function AdminOrders() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const q = useQuery({ queryKey: ["admin-orders"], queryFn: () => api<Order[]>("/admin/orders") });
  const [target, setTarget] = useState<Order | null>(null);
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  const open = (o: Order) => {
    setTarget(o);
    setMessage("");
    setError("");
  };

  const send = async (action: "confirm" | "decline") => {
    if (!target || !message.trim()) return setError("Skriv ett meddelande till beställaren.");
    setSending(true);
    setError("");
    try {
      await api(`/admin/orders/${target.id}/reply`, { method: "POST", body: { message: message.trim(), action } });
      haptic("success");
      toast(`Order ${target.order_number} ${action === "confirm" ? "bekräftad" : "nekad"} – svar skickat`, "success");
      setTarget(null);
      q.refetch();
    } catch (e: any) {
      haptic("error");
      setError(e.message);
    } finally {
      setSending(false);
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
        renderItem={({ item }) => <OrderCard order={item} showCompany onReply={() => open(item)} />}
      />
      <Modal visible={!!target} transparent animationType="slide" onRequestClose={() => setTarget(null)}>
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} style={{ flex: 1 }}>
          <Pressable style={styles.backdrop} onPress={() => setTarget(null)} testID="reply-sheet-backdrop" />
          <View style={[styles.sheet, { paddingBottom: insets.bottom + spacing.lg }]} testID="reply-sheet">
            <View style={styles.handle} />
            <View style={styles.sheetHead}>
              <Text style={styles.sheetTitle}>Svara på {target?.order_number}</Text>
              <Pressable testID="reply-sheet-close" onPress={() => setTarget(null)} hitSlop={8}>
                <Icon name="close" size={24} color={colors.onSurface} />
              </Pressable>
            </View>
            <Text style={styles.sheetSub}>
              Svaret mejlas till {target?.customer.email} ({target?.customer.company})
            </Text>
            {!!error && <ErrorBanner message={error} testID="reply-error" />}
            <TextInput
              testID="reply-message-input"
              value={message}
              onChangeText={setMessage}
              multiline
              maxLength={2000}
              autoFocus
              placeholder="T.ex. Leverans sker om 15 min"
              placeholderTextColor={colors.muted}
              style={styles.input}
              textAlignVertical="top"
            />
            <View style={{ flexDirection: "row", gap: spacing.sm }}>
              <Button title="Neka" variant="danger" icon="close-octagon" testID="reply-decline-button" onPress={() => send("decline")} disabled={sending} style={{ flex: 1 }} />
              <Button title="Bekräfta" icon="send" testID="reply-send-button" onPress={() => send("confirm")} loading={sending} style={{ flex: 2 }} />
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.6)" },
  sheet: { backgroundColor: c.surfaceSecondary, borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg, paddingHorizontal: spacing.lg },
  handle: { width: 40, height: 4, borderRadius: 2, backgroundColor: c.borderStrong, alignSelf: "center", marginVertical: spacing.md },
  sheetHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  sheetTitle: { color: c.onSurface, fontFamily: fonts.displayHeavy, fontSize: 26, textTransform: "uppercase" },
  sheetSub: { color: c.muted, fontFamily: fonts.body, fontSize: 13, marginTop: spacing.xs, marginBottom: spacing.lg },
  input: {
    minHeight: 120,
    backgroundColor: c.surfaceTertiary,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: c.border,
    color: c.onSurface,
    padding: spacing.lg,
    fontFamily: fonts.body,
    fontSize: 15,
    marginBottom: spacing.lg,
  },
}));
