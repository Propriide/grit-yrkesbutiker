import { useEffect, useState } from "react";
import { Modal, Platform, Pressable, Text, TextInput, View } from "react-native";
import { KeyboardAvoidingView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Order } from "@/src/api";
import { Button, ErrorBanner, haptic, Icon } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";
import { useToast } from "@/src/toast";

/** Admin sheet to confirm or decline an order with a message to the orderer. */
export function ReplySheet({ order, onClose, onDone }: { order: Order | null; onClose: () => void; onDone: () => void }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setMessage("");
    setError("");
  }, [order]);

  const send = async (action: "confirm" | "decline") => {
    if (!order) return;
    if (action === "decline" && !message.trim()) return setError("Skriv varför ordern nekas.");
    setSending(true);
    setError("");
    try {
      await api(`/admin/orders/${order.id}/reply`, { method: "POST", body: { message: message.trim(), action } });
      haptic("success");
      toast(`Order ${order.order_number} ${action === "confirm" ? "bekräftad" : "nekad"} – svar skickat`, "success");
      onDone();
      onClose();
    } catch (e: any) {
      haptic("error");
      setError(e.message);
    } finally {
      setSending(false);
    }
  };

  return (
    <Modal visible={!!order} transparent animationType="slide" onRequestClose={onClose}>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} style={{ flex: 1 }}>
        <Pressable style={styles.backdrop} onPress={onClose} testID="reply-sheet-backdrop" />
        <View style={[styles.sheet, { paddingBottom: insets.bottom + spacing.lg }]} testID="reply-sheet">
          <View style={styles.handle} />
          <View style={styles.sheetHead}>
            <Text style={styles.sheetTitle}>Svara på {order?.order_number}</Text>
            <Pressable testID="reply-sheet-close" onPress={onClose} hitSlop={8}>
              <Icon name="close" size={24} color={colors.onSurface} />
            </Pressable>
          </View>
          <Text style={styles.sheetSub}>
            Svaret mejlas till {order?.customer.email} ({order?.customer.company})
          </Text>
          {!!error && <ErrorBanner message={error} testID="reply-error" />}
          <TextInput
            testID="reply-message-input"
            value={message}
            onChangeText={setMessage}
            multiline
            maxLength={2000}
            autoFocus
            placeholder="Valfritt vid bekräftelse, t.ex. Leverans sker om 15 min"
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
  );
}

const useStyles = makeStyles((c) => ({
  backdrop: { flex: 1, backgroundColor: c.scrim },
  sheet: { backgroundColor: c.surfaceSecondary, borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg, paddingHorizontal: spacing.lg },
  handle: { width: 40, height: 4, borderRadius: 2, backgroundColor: c.borderStrong, alignSelf: "center", marginVertical: spacing.md },
  sheetHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  sheetTitle: { color: c.onSurface, fontFamily: fonts.displayHeavy, fontSize: 26, textTransform: "uppercase" },
  sheetSub: { color: c.muted, fontFamily: fonts.body, fontSize: 13, marginTop: spacing.xs, marginBottom: spacing.lg },
  input: { minHeight: 120, backgroundColor: c.surfaceTertiary, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, color: c.onSurface, padding: spacing.lg, fontFamily: fonts.body, fontSize: 15, marginBottom: spacing.lg },
}));
