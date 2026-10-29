import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ActivityIndicator, Text, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { Button, ErrorBanner, Field, ScreenHeader } from "@/src/components/ui";
import { formatDate } from "@/src/components/order-card";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";
import { useToast } from "@/src/toast";

type Settings = {
  order_email: string;
  product_count: number;
  catalog: { running: boolean; last_run: string | null; count: number; error: string | null };
};

export default function AdminSettings() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const q = useQuery({
    queryKey: ["admin-settings"],
    queryFn: () => api<Settings>("/admin/settings"),
    refetchInterval: (query) => (query.state.data?.catalog.running ? 4000 : false),
  });
  const [email, setEmail] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (q.data) setEmail(q.data.order_email);
  }, [q.data?.order_email]); // eslint-disable-line react-hooks/exhaustive-deps

  const save = async () => {
    setSaving(true);
    setError("");
    try {
      await api("/admin/settings", { method: "PUT", body: { order_email: email.trim() } });
      toast("Mottagaradress sparad", "success");
      q.refetch();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const sync = async () => {
    try {
      await api("/admin/catalog/sync", { method: "POST" });
      toast("Uppdatering av sortiment startad", "info");
      q.refetch();
    } catch (e: any) {
      toast(e.message, "error");
    }
  };

  const cat = q.data?.catalog;

  return (
    <View style={styles.root}>
      <ScreenHeader title="Inställningar" subtitle="Ordermottagare & sortiment" />
      {q.isLoading ? (
        <ActivityIndicator color={colors.brandPrimary} style={{ marginTop: spacing.xxl }} />
      ) : (
        <KeyboardAwareScrollView bottomOffset={24} keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + spacing.xl }}>
          <Text style={styles.section}>Ordermottagare</Text>
          <Text style={styles.help}>Alla beställningar mejlas till denna adress.</Text>
          {!q.data?.order_email && <ErrorBanner message="Ingen mottagare är inställd – kunder kan inte skicka beställningar förrän en adress sparats." testID="no-recipient-warning" />}
          {!!error && <ErrorBanner message={error} testID="settings-error" />}
          <Field
            label="E-postadress för beställningar"
            testID="settings-order-email-input"
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            keyboardType="email-address"
            placeholder="order@foretag.se"
          />
          <Button title="Spara" testID="settings-save-button" onPress={save} loading={saving} />

          <Text style={[styles.section, { marginTop: spacing.xxl }]}>Sortiment</Text>
          <View style={styles.card}>
            <Text style={styles.big} testID="settings-product-count">
              {q.data?.product_count ?? 0}
            </Text>
            <Text style={styles.help}>produkter hämtade från blaklader.se</Text>
            {cat?.last_run && <Text style={styles.meta}>Senast uppdaterad {formatDate(cat.last_run)}</Text>}
            {cat?.error && <Text style={[styles.meta, { color: colors.error }]}>Fel: {cat.error}</Text>}
          </View>
          <Button
            title={cat?.running ? "Uppdaterar..." : "Uppdatera sortiment"}
            icon="refresh"
            variant="secondary"
            testID="settings-sync-button"
            onPress={sync}
            loading={cat?.running}
            style={{ marginTop: spacing.md }}
          />
        </KeyboardAwareScrollView>
      )}
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  section: { color: c.brandPrimary, fontFamily: fonts.display, fontSize: 16, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: spacing.xs },
  help: { color: c.muted, fontFamily: fonts.body, fontSize: 13, marginBottom: spacing.lg },
  card: { backgroundColor: c.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, padding: spacing.lg, marginTop: spacing.sm },
  big: { color: c.brandSecondary, fontFamily: fonts.displayHeavy, fontSize: 44 },
  meta: { color: c.onSurfaceTertiary, fontFamily: fonts.body, fontSize: 12, marginTop: -spacing.sm },
}));
