import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { useState } from "react";
import { FlatList, Platform, Pressable, Text, TextInput, View } from "react-native";
import { KeyboardAvoidingView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, City } from "@/src/api";
import { Button, EmptyState, haptic, Icon, ScreenHeader } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";
import { useToast } from "@/src/toast";

export default function AdminCities() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const q = useQuery({ queryKey: ["cities"], queryFn: () => api<City[]>("/cities") });
  const [name, setName] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async (fn: () => Promise<any>, ok: string) => {
    setBusy(true);
    try {
      await fn();
      toast(ok, "success");
      q.refetch();
      return true;
    } catch (e: any) {
      haptic("error");
      toast(e.message, "error");
      return false;
    } finally {
      setBusy(false);
    }
  };

  const add = async () => {
    if (!name.trim()) return;
    if (await run(() => api("/admin/cities", { method: "POST", body: { name: name.trim() } }), "Ort tillagd")) setName("");
  };

  return (
    <KeyboardAvoidingView style={styles.root} behavior={Platform.OS === "ios" ? "padding" : "height"}>
      <ScreenHeader title="Orter & butiker" subtitle="Tryck på butiksikonen för att ändra startsidan" />
      <FlatList
        testID="cities-list"
        data={q.data ?? []}
        keyExtractor={(c) => c.id}
        contentContainerStyle={{ padding: spacing.lg, gap: spacing.sm, flexGrow: 1 }}
        keyboardShouldPersistTaps="handled"
        ListEmptyComponent={q.isLoading ? null : <EmptyState icon="map-marker-off" title="Inga orter" text="Lägg till den första orten nedan." />}
        renderItem={({ item }) => (
          <View style={styles.row} testID={`city-row-${item.id}`}>
            {editing === item.id ? (
              <>
                <TextInput testID={`city-edit-input-${item.id}`} value={editName} onChangeText={setEditName} autoFocus style={styles.editInput} placeholderTextColor={colors.muted} />
                <Pressable
                  testID={`city-save-${item.id}`}
                  style={styles.iconBtn}
                  onPress={async () => {
                    if (await run(() => api(`/admin/cities/${item.id}`, { method: "PUT", body: { name: editName.trim() } }), "Ort uppdaterad")) setEditing(null);
                  }}
                >
                  <Icon name="check-bold" size={22} color={colors.success} />
                </Pressable>
                <Pressable testID={`city-cancel-${item.id}`} style={styles.iconBtn} onPress={() => setEditing(null)}>
                  <Icon name="close" size={22} color={colors.muted} />
                </Pressable>
              </>
            ) : confirmDelete === item.id ? (
              <>
                <Text style={[styles.name, { color: colors.error }]}>Ta bort {item.name}?</Text>
                <Pressable
                  testID={`city-confirm-delete-${item.id}`}
                  style={styles.dangerBtn}
                  onPress={async () => {
                    await run(() => api(`/admin/cities/${item.id}`, { method: "DELETE" }), "Ort borttagen");
                    setConfirmDelete(null);
                  }}
                >
                  <Text style={styles.dangerText}>Ta bort</Text>
                </Pressable>
                <Pressable testID={`city-cancel-delete-${item.id}`} style={styles.iconBtn} onPress={() => setConfirmDelete(null)}>
                  <Icon name="close" size={22} color={colors.muted} />
                </Pressable>
              </>
            ) : (
              <>
                <Icon name="map-marker" size={20} color={colors.brandPrimary} />
                <Text style={styles.name}>{item.name}</Text>
                <Pressable testID={`city-store-${item.id}`} style={styles.iconBtn} onPress={() => router.push(`/admin/store/${item.id}`)}>
                  <Icon name="storefront-edit" size={20} color={colors.brandSecondary} />
                </Pressable>
                <Pressable
                  testID={`city-edit-${item.id}`}
                  style={styles.iconBtn}
                  onPress={() => {
                    setEditing(item.id);
                    setEditName(item.name);
                  }}
                >
                  <Icon name="pencil" size={20} color={colors.onSurfaceTertiary} />
                </Pressable>
                <Pressable testID={`city-delete-${item.id}`} style={styles.iconBtn} onPress={() => setConfirmDelete(item.id)}>
                  <Icon name="trash-can-outline" size={20} color={colors.error} />
                </Pressable>
              </>
            )}
          </View>
        )}
      />
      <View style={[styles.footer, { paddingBottom: insets.bottom + spacing.md }]}>
        <TextInput
          testID="city-new-input"
          value={name}
          onChangeText={setName}
          placeholder="Ny ort, t.ex. Uppsala"
          placeholderTextColor={colors.muted}
          style={styles.input}
          returnKeyType="done"
          onSubmitEditing={add}
        />
        <Button title="Lägg till" testID="city-add-button" onPress={add} loading={busy} disabled={!name.trim()} />
      </View>
    </KeyboardAvoidingView>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: c.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, paddingLeft: spacing.lg, paddingRight: spacing.xs, minHeight: 56 },
  name: { flex: 1, color: c.onSurface, fontFamily: fonts.bodyBold, fontSize: 15 },
  iconBtn: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  editInput: { flex: 1, color: c.onSurface, fontFamily: fonts.body, fontSize: 15, borderBottomWidth: 1, borderBottomColor: c.brandPrimary, paddingVertical: spacing.sm },
  dangerBtn: { backgroundColor: c.error, borderRadius: radius.sm, paddingHorizontal: spacing.md, height: 36, justifyContent: "center" },
  dangerText: { color: c.onError, fontFamily: fonts.bodyBold, fontSize: 13 },
  footer: { flexDirection: "row", gap: spacing.sm, paddingHorizontal: spacing.lg, paddingTop: spacing.md, borderTopWidth: 1, borderTopColor: c.divider, backgroundColor: c.surface },
  input: { flex: 1, minHeight: 52, backgroundColor: c.surfaceTertiary, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, color: c.onSurface, paddingHorizontal: spacing.lg, fontFamily: fonts.body, fontSize: 15 },
}));
