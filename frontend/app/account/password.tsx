import { router } from "expo-router";
import { useState } from "react";
import { View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { Button, ErrorBanner, Field, haptic, ScreenHeader } from "@/src/components/ui";
import { spacing, useTheme } from "@/src/theme";
import { useToast } from "@/src/toast";

export default function ChangePassword() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const [cur, setCur] = useState("");
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const save = async () => {
    if (!cur) return setError("Ange ditt nuvarande lösenord.");
    if (pw.length < 6) return setError("Det nya lösenordet måste ha minst 6 tecken.");
    if (pw !== pw2) return setError("Lösenorden matchar inte.");
    setLoading(true);
    setError("");
    try {
      await api("/auth/change-password", { method: "POST", body: { current_password: cur, new_password: pw } });
      haptic("success");
      toast("Lösenordet är bytt", "success");
      router.back();
    } catch (e: any) {
      haptic("error");
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <ScreenHeader title="Byt lösenord" />
      <KeyboardAwareScrollView bottomOffset={24} keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: spacing.xl, paddingBottom: insets.bottom + spacing.xl }}>
        {!!error && <ErrorBanner message={error} testID="change-password-error" />}
        <Field label="Nuvarande lösenord" testID="current-password-input" value={cur} onChangeText={setCur} secureTextEntry />
        <Field label="Nytt lösenord" testID="new-password-input" value={pw} onChangeText={setPw} secureTextEntry placeholder="Minst 6 tecken" />
        <Field label="Upprepa nytt lösenord" testID="new-password2-input" value={pw2} onChangeText={setPw2} secureTextEntry />
        <Button title="Spara lösenord" testID="change-password-submit" onPress={save} loading={loading} />
      </KeyboardAwareScrollView>
    </View>
  );
}
