import { useQuery, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import { useState } from "react";
import { Switch, Text, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, City } from "@/src/api";
import { CityPicker } from "@/src/components/city-picker";
import { CompanyInput } from "@/src/components/company-input";
import { Button, ErrorBanner, Field, haptic, ScreenHeader } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";
import { useToast } from "@/src/toast";

const EMAIL_RX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function AdminCreateUser() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const qc = useQueryClient();
  const cities = useQuery({ queryKey: ["cities"], queryFn: () => api<City[]>("/cities") });
  const [f, setF] = useState({ email: "", password: "", phone: "", company: "", org_number: "", city_id: null as string | null, admin: false });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const set = (k: keyof typeof f) => (v: any) => setF((p) => ({ ...p, [k]: v }));

  const create = async () => {
    if (!EMAIL_RX.test(f.email.trim())) return setError("Ange en giltig e-postadress.");
    if (f.password.length < 6) return setError("Lösenordet måste ha minst 6 tecken.");
    if (!f.company.trim()) return setError("Företag är obligatoriskt.");
    setLoading(true);
    setError("");
    try {
      const { admin, ...rest } = f;
      await api("/admin/users", { method: "POST", body: { ...rest, email: f.email.trim(), role: admin ? "admin" : "customer" } });
      haptic("success");
      toast(`Kontot ${f.email.trim()} är skapat`, "success");
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      qc.invalidateQueries({ queryKey: ["admin-companies"] });
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
      <ScreenHeader title="Nytt konto" subtitle="Skapa ett konto åt en kund" />
      <KeyboardAwareScrollView bottomOffset={24} keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + spacing.xl }}>
        {!!error && <ErrorBanner message={error} testID="create-user-error" />}
        <Field label="E-post" testID="new-user-email-input" value={f.email} onChangeText={set("email")} autoCapitalize="none" keyboardType="email-address" placeholder="namn@foretag.se" />
        <Field label="Lösenord" testID="new-user-password-input" value={f.password} onChangeText={set("password")} secureTextEntry placeholder="Minst 6 tecken" />
        <Field label="Telefonnummer" optional testID="new-user-phone-input" value={f.phone} onChangeText={set("phone")} keyboardType="phone-pad" />
        <CompanyInput value={f.company} onChange={set("company")} testID="new-user-company-input" />
        <Field label="Organisationsnummer" optional testID="new-user-orgnr-input" value={f.org_number} onChangeText={set("org_number")} />
        <CityPicker cities={cities.data ?? []} value={f.city_id} onChange={set("city_id")} testID="new-user-city-picker" allowNone />
        <View style={styles.switchRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.switchTitle}>Administratör</Text>
            <Text style={styles.switchSub}>Får tillgång till adminpanelen</Text>
          </View>
          <Switch
            testID="new-user-admin-switch"
            value={f.admin}
            onValueChange={set("admin")}
            trackColor={{ true: colors.brandPrimary, false: colors.surfaceTertiary }}
            thumbColor={colors.onSurface}
            {...({ activeThumbColor: colors.onSurface } as object)}
          />
        </View>
        <Text style={styles.help}>Ge kunden e-postadressen och lösenordet. Kunden kan själv byta lösenord under Profil.</Text>
        <Button title="Skapa konto" testID="create-user-submit" onPress={create} loading={loading} />
      </KeyboardAwareScrollView>
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  switchRow: { flexDirection: "row", alignItems: "center", backgroundColor: c.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, padding: spacing.lg, marginBottom: spacing.md },
  switchTitle: { color: c.onSurface, fontFamily: fonts.bodyBold, fontSize: 15 },
  switchSub: { color: c.muted, fontFamily: fonts.body, fontSize: 12 },
  help: { color: c.muted, fontFamily: fonts.body, fontSize: 13, marginBottom: spacing.lg },
}));
