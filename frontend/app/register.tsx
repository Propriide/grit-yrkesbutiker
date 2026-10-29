import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { useState } from "react";
import { Text, View } from "react-native";
import { KeyboardAwareScrollView, KeyboardStickyView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, City } from "@/src/api";
import { useAuth } from "@/src/auth";
import { CityPicker } from "@/src/components/city-picker";
import { Button, ErrorBanner, Field, haptic, ScreenHeader } from "@/src/components/ui";
import { fonts, makeStyles, spacing } from "@/src/theme";

const EMAIL_RX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function Register() {
  const { register } = useAuth();
  const styles = useStyles();
  const insets = useSafeAreaInsets();
  const cities = useQuery({ queryKey: ["cities"], queryFn: () => api<City[]>("/cities") });
  const [f, setF] = useState({ email: "", password: "", phone: "", company: "", org_number: "", city_id: null as string | null });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const set = (k: keyof typeof f) => (v: any) => {
    setF((p) => ({ ...p, [k]: v }));
    const ek = k === "city_id" ? "city" : k;
    setErrors((e) => (e[ek] ? { ...e, [ek]: "" } : e));
  };

  const submit = async () => {
    const e: Record<string, string> = {};
    if (!EMAIL_RX.test(f.email.trim())) e.email = "Ange en giltig e-postadress";
    if (f.password.length < 6) e.password = "Minst 6 tecken";
    if (f.phone.trim().length < 5) e.phone = "Ange telefonnummer";
    if (!f.company.trim()) e.company = "Företag är obligatoriskt";
    if ((cities.data?.length ?? 0) > 0 && !f.city_id) e.city = "Välj ort";
    setErrors(e);
    if (Object.keys(e).length) {
      haptic("error");
      return;
    }
    setError("");
    setLoading(true);
    try {
      await register({ ...f, email: f.email.trim(), org_number: f.org_number.trim() || undefined });
      router.replace("/(tabs)");
    } catch (err: any) {
      haptic("error");
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.root}>
      <ScreenHeader title="Registrera konto" subtitle="Konto för företagsbeställningar" />
      <KeyboardAwareScrollView bottomOffset={100} keyboardShouldPersistTaps="handled" contentContainerStyle={styles.content}>
        {!!error && <ErrorBanner message={error} testID="register-error" />}
        <Text style={styles.section}>Kontouppgifter</Text>
        <Field label="E-post" testID="register-email-input" value={f.email} onChangeText={set("email")} error={errors.email} autoCapitalize="none" keyboardType="email-address" autoComplete="email" placeholder="namn@foretag.se" />
        <Field label="Lösenord" testID="register-password-input" value={f.password} onChangeText={set("password")} error={errors.password} secureTextEntry placeholder="Minst 6 tecken" />
        <Field label="Telefonnummer" testID="register-phone-input" value={f.phone} onChangeText={set("phone")} error={errors.phone} keyboardType="phone-pad" placeholder="070-123 45 67" />
        <Text style={styles.section}>Företag</Text>
        <Field label="Företag" testID="register-company-input" value={f.company} onChangeText={set("company")} error={errors.company} placeholder="Företagets namn" />
        <Field label="Organisationsnummer" optional testID="register-orgnr-input" value={f.org_number} onChangeText={set("org_number")} keyboardType="numbers-and-punctuation" placeholder="556677-8899" />
        <CityPicker cities={cities.data ?? []} value={f.city_id} onChange={set("city_id")} testID="register-city-picker" />
        {!!errors.city && <Text style={styles.err}>{errors.city}</Text>}
      </KeyboardAwareScrollView>
      <KeyboardStickyView offset={{ opened: insets.bottom }}>
        <View style={[styles.footer, { paddingBottom: insets.bottom + spacing.md }]}>
          <Button title="Skapa konto" testID="register-submit-button" onPress={submit} loading={loading} />
        </View>
      </KeyboardStickyView>
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  content: { padding: spacing.xl, paddingBottom: spacing.xxl },
  section: { color: c.brandPrimary, fontFamily: fonts.display, fontSize: 16, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: spacing.md, marginTop: spacing.sm },
  err: { color: c.error, fontFamily: fonts.body, fontSize: 12, marginTop: -spacing.sm },
  footer: { paddingHorizontal: spacing.xl, paddingTop: spacing.md, backgroundColor: c.surface, borderTopWidth: 1, borderTopColor: c.divider },
}));
