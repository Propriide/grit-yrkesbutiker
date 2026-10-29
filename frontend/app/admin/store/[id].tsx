import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Text, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, City, StoreInfo } from "@/src/api";
import { Button, EmptyState, ErrorBanner, Field, haptic, ScreenHeader } from "@/src/components/ui";
import { fonts, makeStyles, spacing, useTheme } from "@/src/theme";
import { useToast } from "@/src/toast";

type StoreRes = StoreInfo & { id: string; custom: boolean };

export default function AdminStore() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["admin-store", id], queryFn: () => api<StoreRes>(`/admin/stores/${id}`), retry: false });
  const cities = useQuery({ queryKey: ["cities"], queryFn: () => api<City[]>("/cities") });
  const [f, setF] = useState<StoreInfo>({ title: "", text: "", address: "", phone: "", email: "", hours: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const isDefault = id === "default";
  const cityName = cities.data?.find((c) => c.id === id)?.name;

  useEffect(() => {
    if (q.data) {
      const { title, text, address, phone, email, hours } = q.data;
      setF({ title, text, address, phone, email, hours });
    }
  }, [q.data]);

  const set = (k: keyof StoreInfo) => (v: string) => setF((p) => ({ ...p, [k]: v }));

  const save = async () => {
    if (!f.title.trim() || !f.text.trim()) {
      setError("Rubrik och information får inte vara tomma.");
      toast("Rubrik och information får inte vara tomma.", "error");
      haptic("error");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await api(`/admin/stores/${id}`, { method: "PUT", body: f });
      haptic("success");
      toast("Startsidan sparad", "success");
      qc.invalidateQueries({ queryKey: ["home"] });
      q.refetch();
    } catch (e: any) {
      haptic("error");
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const reset = async () => {
    setSaving(true);
    setError("");
    try {
      await api(`/admin/stores/${id}`, { method: "DELETE" });
      toast("Butiken visar nu standardtexten", "success");
      qc.invalidateQueries({ queryKey: ["home"] });
      q.refetch();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <View style={styles.root}>
      <ScreenHeader title="Startsida" subtitle={isDefault ? "Standard – konton utan egen butikstext" : `Butik: ${cityName ?? ""}`} />
      {q.isLoading ? (
        <ActivityIndicator color={colors.brandPrimary} style={{ marginTop: spacing.xxl }} />
      ) : q.isError ? (
        <EmptyState
          icon="alert-octagon"
          title="Kunde inte ladda startsidan"
          text={(q.error as Error).message}
          action={<Button title="Försök igen" testID="store-retry-button" onPress={() => q.refetch()} />}
        />
      ) : (
        <KeyboardAwareScrollView bottomOffset={24} keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + spacing.xl }}>
          {!isDefault && q.data && !q.data.custom && (
            <Text style={styles.help} testID="store-uses-default">
              Den här butiken visar just nu standardtexten. Spara för att ge butiken en egen startsida.
            </Text>
          )}
          {!!error && <ErrorBanner message={error} testID="store-error" />}
          <Field label="Rubrik" testID="store-title-input" value={f.title} onChangeText={set("title")} placeholder="Välkommen till YP Yrkesbutiker" />
          <Field
            label="Information"
            testID="store-text-input"
            value={f.text}
            onChangeText={set("text")}
            multiline
            textAlignVertical="top"
            style={{ minHeight: 140, paddingTop: spacing.md }}
            placeholder="Text som visas på startsidan"
          />
          <Field label="Adress" optional testID="store-address-input" value={f.address} onChangeText={set("address")} placeholder="Gatan 1, 123 45 Ort" />
          <Field label="Telefon" optional testID="store-phone-input" value={f.phone} onChangeText={set("phone")} keyboardType="phone-pad" />
          <Field label="E-post" optional testID="store-email-input" value={f.email} onChangeText={set("email")} autoCapitalize="none" keyboardType="email-address" />
          <Field
            label="Öppettider"
            optional
            testID="store-hours-input"
            value={f.hours}
            onChangeText={set("hours")}
            multiline
            textAlignVertical="top"
            style={{ minHeight: 90, paddingTop: spacing.md }}
            placeholder={"Mån–Fre 07–17\nLör 10–14"}
          />
          <Button title="Spara startsida" testID="store-save-button" onPress={save} loading={saving} />
          {!isDefault && q.data?.custom && (
            <Button title="Återställ till standardtext" variant="ghost" testID="store-reset-button" onPress={reset} disabled={saving} style={{ marginTop: spacing.sm }} />
          )}
        </KeyboardAwareScrollView>
      )}
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  help: { color: c.brandSecondary, fontFamily: fonts.body, fontSize: 13, marginBottom: spacing.lg },
}));
