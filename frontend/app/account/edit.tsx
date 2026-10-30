import { useQuery, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Text, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, City } from "@/src/api";
import { useAuth } from "@/src/auth";
import { CityPicker } from "@/src/components/city-picker";
import { Button, ErrorBanner, Field, haptic, ScreenHeader } from "@/src/components/ui";
import { fonts, makeStyles, spacing } from "@/src/theme";
import { useToast } from "@/src/toast";

export default function EditProfile() {
  const styles = useStyles();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const qc = useQueryClient();
  const { user, refresh } = useAuth();
  const cities = useQuery({ queryKey: ["cities"], queryFn: () => api<City[]>("/cities") });
  const [f, setF] = useState({
    name: user?.name ?? "",
    company: user?.company ?? "",
    phone: user?.phone ?? "",
    org_number: user?.org_number ?? "",
    city_id: user?.city_id ?? null,
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const set = (k: keyof typeof f) => (v: any) => setF((p) => ({ ...p, [k]: v }));
  useEffect(() => {
    if (user) setF({ name: user.name ?? "", company: user.company ?? "", phone: user.phone ?? "", org_number: user.org_number ?? "", city_id: user.city_id ?? null });
  }, [user]);

  const save = async () => {
    if (!f.name.trim()) return setError("Ange ditt namn.");
    if (!f.company.trim()) return setError("Företag är obligatoriskt.");
    if (f.phone.trim().length < 5) return setError("Ange telefonnummer.");
    setLoading(true);
    setError("");
    try {
      await api("/auth/me", { method: "PUT", body: f });
      await refresh();
      qc.invalidateQueries({ queryKey: ["home"] });
      haptic("success");
      toast("Uppgifterna är sparade", "success");
      router.back();
    } catch (e: any) {
      haptic("error");
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.root}>
      <ScreenHeader title="Mina uppgifter" subtitle={user?.email} />
      <KeyboardAwareScrollView bottomOffset={24} keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: spacing.xl, paddingBottom: insets.bottom + spacing.xl }}>
        {!!error && <ErrorBanner message={error} testID="edit-profile-error" />}
        <Text style={styles.help}>E-postadressen används för inloggning och kan ändras av administratören.</Text>
        <Field label="Ditt namn" testID="edit-name-input" value={f.name} onChangeText={set("name")} />
        <Field label="Företag" testID="edit-company-input" value={f.company} onChangeText={set("company")} />
        <Field label="Telefonnummer" testID="edit-phone-input" value={f.phone} onChangeText={set("phone")} keyboardType="phone-pad" />
        <Field label="Organisationsnummer" optional testID="edit-orgnr-input" value={f.org_number} onChangeText={set("org_number")} />
        <CityPicker cities={cities.data ?? []} value={f.city_id} onChange={set("city_id")} testID="edit-city-picker" />
        <Button title="Spara" testID="edit-profile-save" onPress={save} loading={loading} />
      </KeyboardAwareScrollView>
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  help: { color: c.muted, fontFamily: fonts.body, fontSize: 13, marginBottom: spacing.lg },
}));
