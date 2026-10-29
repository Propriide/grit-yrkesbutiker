import { useQuery, useQueryClient } from "@tanstack/react-query";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, Switch, Text, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, City, User } from "@/src/api";
import { useAuth } from "@/src/auth";
import { CityPicker } from "@/src/components/city-picker";
import { Button, ErrorBanner, Field, haptic, ScreenHeader } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";
import { useToast } from "@/src/toast";

export default function AdminUserDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const qc = useQueryClient();
  const { user: me } = useAuth();
  const q = useQuery({ queryKey: ["admin-user", id], queryFn: () => api<User>(`/admin/users/${id}`) });
  const cities = useQuery({ queryKey: ["cities"], queryFn: () => api<City[]>("/cities") });
  const [f, setF] = useState({ company: "", phone: "", org_number: "", city_id: null as string | null, disabled: false, role: "customer" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [newPw, setNewPw] = useState("");
  const [pwSaving, setPwSaving] = useState(false);
  const isMe = me?.id === id;

  const setPassword = async () => {
    if (newPw.length < 6) {
      toast("Lösenordet måste ha minst 6 tecken", "error");
      return;
    }
    setPwSaving(true);
    try {
      await api(`/admin/users/${id}/password`, { method: "PUT", body: { new_password: newPw } });
      haptic("success");
      toast("Nytt lösenord sparat", "success");
      setNewPw("");
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setPwSaving(false);
    }
  };

  useEffect(() => {
    if (q.data) {
      const u = q.data;
      setF({ company: u.company, phone: u.phone, org_number: u.org_number, city_id: u.city_id, disabled: u.disabled, role: u.role });
    }
  }, [q.data]);

  const set = (k: keyof typeof f) => (v: any) => setF((p) => ({ ...p, [k]: v }));

  const save = async () => {
    if (!f.company.trim()) {
      setError("Företag är obligatoriskt");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await api(`/admin/users/${id}`, { method: "PUT", body: { ...f, city_id: f.city_id ?? "" } });
      toast("Kontot uppdaterat", "success");
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      q.refetch();
    } catch (e: any) {
      haptic("error");
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    try {
      await api(`/admin/users/${id}`, { method: "DELETE" });
      toast("Kontot har tagits bort", "success");
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      router.back();
    } catch (e: any) {
      toast(e.message, "error");
    }
  };

  return (
    <View style={styles.root}>
      <ScreenHeader title={q.data?.company || "Konto"} subtitle={q.data?.email} />
      {q.isLoading ? (
        <ActivityIndicator color={colors.brandPrimary} style={{ marginTop: spacing.xxl }} />
      ) : (
        <KeyboardAwareScrollView bottomOffset={24} keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + spacing.xl }}>
          {!!error && <ErrorBanner message={error} testID="user-edit-error" />}
          <View style={styles.stats}>
            <Text style={styles.statNum} testID="user-order-count">
              {q.data?.order_count ?? 0}
            </Text>
            <Text style={styles.statLabel}>ordrar</Text>
          </View>
          <Field label="Företag" testID="user-company-input" value={f.company} onChangeText={set("company")} />
          <Field label="Organisationsnummer" optional testID="user-orgnr-input" value={f.org_number} onChangeText={set("org_number")} />
          <Field label="Telefon" testID="user-phone-input" value={f.phone} onChangeText={set("phone")} keyboardType="phone-pad" />
          <CityPicker cities={cities.data ?? []} value={f.city_id} onChange={set("city_id")} testID="user-city-picker" allowNone />

          <View style={styles.switchRow}>
            <View style={{ flex: 1 }}>
              <Text style={styles.switchTitle}>Administratör</Text>
              <Text style={styles.switchSub}>Får tillgång till adminpanelen</Text>
            </View>
            <Switch
              testID="user-admin-switch"
              value={f.role === "admin"}
              disabled={isMe}
              onValueChange={(v) => set("role")(v ? "admin" : "customer")}
              trackColor={{ true: colors.brandPrimary, false: colors.surfaceTertiary }}
              thumbColor={colors.onSurface}
              {...({ activeThumbColor: colors.onSurface } as object)}
            />
          </View>
          <View style={styles.switchRow}>
            <View style={{ flex: 1 }}>
              <Text style={styles.switchTitle}>Spärrat konto</Text>
              <Text style={styles.switchSub}>Kan inte logga in eller beställa</Text>
            </View>
            <Switch
              testID="user-disabled-switch"
              value={f.disabled}
              disabled={isMe}
              onValueChange={set("disabled")}
              trackColor={{ true: colors.error, false: colors.surfaceTertiary }}
              thumbColor={colors.onSurface}
              {...({ activeThumbColor: colors.onSurface } as object)}
            />
          </View>

          <Button title="Spara ändringar" testID="user-save-button" onPress={save} loading={saving} style={{ marginTop: spacing.lg }} />

          <View style={styles.pwBox}>
            <Text style={styles.switchTitle}>Ändra lösenord</Text>
            <Text style={styles.switchSub}>Sätt ett nytt lösenord åt användaren och meddela det.</Text>
            <Field label="Nytt lösenord" testID="admin-new-password-input" value={newPw} onChangeText={setNewPw} secureTextEntry placeholder="Minst 6 tecken" />
            <Button title="Spara nytt lösenord" variant="secondary" icon="lock-reset" testID="admin-set-password-button" onPress={setPassword} loading={pwSaving} />
          </View>

          {!isMe &&
            (confirmDelete ? (
              <View style={styles.confirm} testID="user-delete-confirm">
                <Text style={styles.confirmText}>Ta bort kontot permanent? Tidigare ordrar sparas.</Text>
                <View style={{ flexDirection: "row", gap: spacing.sm }}>
                  <Button title="Avbryt" variant="secondary" testID="user-delete-cancel" onPress={() => setConfirmDelete(false)} style={{ flex: 1 }} />
                  <Button title="Ta bort" variant="danger" testID="user-delete-confirm-button" onPress={remove} style={{ flex: 1 }} />
                </View>
              </View>
            ) : (
              <Pressable testID="user-delete-button" onPress={() => setConfirmDelete(true)} style={styles.deleteLink}>
                <Text style={styles.deleteText}>Ta bort konto</Text>
              </Pressable>
            ))}
        </KeyboardAwareScrollView>
      )}
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  stats: { flexDirection: "row", alignItems: "baseline", gap: spacing.sm, marginBottom: spacing.lg },
  statNum: { color: c.brandSecondary, fontFamily: fonts.displayHeavy, fontSize: 36 },
  statLabel: { color: c.muted, fontFamily: fonts.body, fontSize: 14 },
  switchRow: { flexDirection: "row", alignItems: "center", backgroundColor: c.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, padding: spacing.lg, marginBottom: spacing.sm },
  switchTitle: { color: c.onSurface, fontFamily: fonts.bodyBold, fontSize: 15 },
  switchSub: { color: c.muted, fontFamily: fonts.body, fontSize: 12 },
  deleteLink: { minHeight: 48, alignItems: "center", justifyContent: "center", marginTop: spacing.lg },
  pwBox: { marginTop: spacing.xl, padding: spacing.lg, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, backgroundColor: c.surfaceSecondary, gap: spacing.sm },
  deleteText: { color: c.error, fontFamily: fonts.bodyBold, fontSize: 14 },
  confirm: { marginTop: spacing.lg, padding: spacing.lg, borderRadius: radius.md, borderWidth: 1, borderColor: c.error, gap: spacing.md },
  confirmText: { color: c.onSurface, fontFamily: fonts.body, fontSize: 14 },
}));
