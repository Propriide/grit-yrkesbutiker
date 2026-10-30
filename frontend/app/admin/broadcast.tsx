import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Pressable, Text, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, City, Company } from "@/src/api";
import { CityPicker } from "@/src/components/city-picker";
import { formatDate } from "@/src/components/order-card";
import { Button, ErrorBanner, Field, haptic, ScreenHeader } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";
import { useToast } from "@/src/toast";

type Broadcast = { id: string; title: string; body: string; city_id: string | null; companies?: string[]; recipients: number; created_at: string };

export default function AdminBroadcast() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const qc = useQueryClient();
  const cities = useQuery({ queryKey: ["cities"], queryFn: () => api<City[]>("/cities") });
  const history = useQuery({ queryKey: ["admin-broadcasts"], queryFn: () => api<Broadcast[]>("/admin/broadcasts") });
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [cityId, setCityId] = useState<string | null>(null);
  const companies = useQuery({ queryKey: ["admin-companies"], queryFn: () => api<Company[]>("/admin/companies") });
  const [picked, setPicked] = useState<string[]>([]);
  const togglePick = (name: string) => setPicked((p) => (p.includes(name) ? p.filter((x) => x !== name) : [...p, name]));
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const cityName = (id: string | null) => (id ? cities.data?.find((c) => c.id === id)?.name ?? "Okänd ort" : "Alla användare");

  const send = async () => {
    if (!title.trim() || !body.trim()) {
      setError("Skriv rubrik och meddelande.");
      return;
    }
    setSending(true);
    setError("");
    try {
      const r = await api<Broadcast>("/admin/broadcast", { method: "POST", body: { title, body, city_id: cityId, companies: picked } });
      haptic("success");
      toast(`Skickat till ${r.recipients} användare`, "success");
      setTitle("");
      setBody("");
      setPicked([]);
      qc.invalidateQueries({ queryKey: ["admin-broadcasts"] });
      qc.invalidateQueries({ queryKey: ["notifications"] });
    } catch (e: any) {
      haptic("error");
      setError(e.message);
    } finally {
      setSending(false);
    }
  };

  return (
    <View style={styles.root}>
      <ScreenHeader title="Skicka utskick" subtitle="Erbjudanden och nyheter till kunderna" />
      <KeyboardAwareScrollView bottomOffset={24} keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + spacing.xl }}>
        {!!error && <ErrorBanner message={error} testID="broadcast-error" />}
        <Text style={styles.help}>Meddelandet hamnar i notisklockan hos mottagarna direkt.</Text>
        <Field label="Rubrik" testID="broadcast-title-input" value={title} onChangeText={setTitle} maxLength={120} placeholder="T.ex. 20 % på vinterjackor" />
        <Field label="Meddelande" testID="broadcast-body-input" value={body} onChangeText={setBody} multiline maxLength={2000} placeholder="Skriv ditt erbjudande..." style={{ minHeight: 120, textAlignVertical: "top", paddingTop: spacing.md }} />
        <CityPicker cities={cities.data ?? []} value={cityId} onChange={setCityId} testID="broadcast-city-picker" allowNone />
        <Text style={styles.help}>Ingen ort vald = alla orter.</Text>
        <Text style={styles.label}>Företag (valfritt)</Text>
        <View style={styles.chips} testID="broadcast-companies">
          {(companies.data ?? []).filter((c) => !["admin", "yp"].includes(c.key)).map((c) => {
            const on = picked.includes(c.name);
            return (
              <Pressable key={c.key} testID={`broadcast-company-${c.key.replace(/\s+/g, "-")}`} onPress={() => togglePick(c.name)} style={[styles.chip, on && styles.chipOn]}>
                <Text style={[styles.chipText, on && { color: colors.onBrandPrimary }]}>{c.name}</Text>
              </Pressable>
            );
          })}
        </View>
        <Text style={styles.help}>{picked.length ? `Skickas bara till ${picked.length} valda företag.` : "Inget företag valt = alla kunder."}</Text>
        <Button title="Skicka utskick" icon="bullhorn" testID="broadcast-send-button" onPress={send} loading={sending} style={{ marginTop: spacing.md }} />

        {!!history.data?.length && <Text style={styles.section}>Tidigare utskick</Text>}
        {history.data?.map((b) => (
          <View key={b.id} style={styles.card} testID={`broadcast-${b.id}`}>
            <Text style={styles.cardTitle}>{b.title}</Text>
            <Text style={styles.cardBody} numberOfLines={3}>
              {b.body}
            </Text>
            <Text style={styles.meta}>
              {formatDate(b.created_at)} · {b.companies?.length ? b.companies.join(", ") : cityName(b.city_id)}
              {b.companies?.length && b.city_id ? ` (${cityName(b.city_id)})` : ""} · {b.recipients} mottagare
            </Text>
          </View>
        ))}
      </KeyboardAwareScrollView>
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  help: { color: c.muted, fontFamily: fonts.body, fontSize: 13, marginBottom: spacing.md },
  label: { color: c.onSurfaceSecondary, fontFamily: fonts.bodyBold, fontSize: 12, marginBottom: spacing.sm, textTransform: "uppercase", letterSpacing: 0.8 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginBottom: spacing.sm },
  chip: { minHeight: 44, paddingHorizontal: spacing.md, borderRadius: radius.pill, borderWidth: 1, borderColor: c.border, backgroundColor: c.surfaceSecondary, justifyContent: "center" },
  chipOn: { backgroundColor: c.brandPrimary, borderColor: c.brandPrimary },
  chipText: { color: c.onSurface, fontFamily: fonts.bodyBold, fontSize: 13 },
  section: { color: c.brandSecondary, fontFamily: fonts.display, fontSize: 16, letterSpacing: 1.5, textTransform: "uppercase", marginTop: spacing.xl, marginBottom: spacing.sm },
  card: { backgroundColor: c.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, padding: spacing.lg, marginBottom: spacing.sm },
  cardTitle: { color: c.onSurface, fontFamily: fonts.bodyBold, fontSize: 15 },
  cardBody: { color: c.onSurfaceTertiary, fontFamily: fonts.body, fontSize: 13, marginTop: 2 },
  meta: { color: c.muted, fontFamily: fonts.body, fontSize: 11, marginTop: spacing.sm },
}));
