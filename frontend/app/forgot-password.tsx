import { router } from "expo-router";
import { useState } from "react";
import { Text, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { Button, ErrorBanner, Field, haptic, ScreenHeader } from "@/src/components/ui";
import { fonts, makeStyles, spacing } from "@/src/theme";
import { useToast } from "@/src/toast";

export default function ForgotPassword() {
  const styles = useStyles();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const [step, setStep] = useState<"email" | "code">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);

  const requestCode = async () => {
    if (!email.trim()) return setError("Ange din e-postadress.");
    setLoading(true);
    setError("");
    try {
      const r = await api<{ message: string }>("/auth/forgot-password", { method: "POST", body: { email: email.trim() } });
      setInfo(r.message);
      setStep("code");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const reset = async () => {
    if (code.trim().length !== 6) return setError("Koden har 6 siffror.");
    if (pw.length < 6) return setError("Lösenordet måste ha minst 6 tecken.");
    if (pw !== pw2) return setError("Lösenorden matchar inte.");
    setLoading(true);
    setError("");
    try {
      await api("/auth/reset-password", { method: "POST", body: { email: email.trim(), code: code.trim(), new_password: pw } });
      haptic("success");
      toast("Lösenordet är bytt – logga in med det nya", "success");
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
      <ScreenHeader title="Glömt lösenord" subtitle={step === "email" ? "Steg 1 av 2" : "Steg 2 av 2"} />
      <KeyboardAwareScrollView bottomOffset={24} keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: spacing.xl, paddingBottom: insets.bottom + spacing.xl }}>
        {!!error && <ErrorBanner message={error} testID="forgot-error" />}
        {step === "email" ? (
          <>
            <Text style={styles.help}>Ange e-postadressen för ditt konto så skickar vi en kod för att välja nytt lösenord.</Text>
            <Field label="E-post" testID="forgot-email-input" value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" placeholder="namn@foretag.se" />
            <Button title="Skicka kod" testID="forgot-send-button" onPress={requestCode} loading={loading} />
          </>
        ) : (
          <>
            <Text style={styles.help} testID="forgot-info">
              {info} Koden gäller i 15 minuter.
            </Text>
            <Field label="Kod" testID="reset-code-input" value={code} onChangeText={setCode} keyboardType="number-pad" maxLength={6} placeholder="123456" />
            <Field label="Nytt lösenord" testID="reset-password-input" value={pw} onChangeText={setPw} secureTextEntry placeholder="Minst 6 tecken" />
            <Field label="Upprepa nytt lösenord" testID="reset-password2-input" value={pw2} onChangeText={setPw2} secureTextEntry />
            <Button title="Spara nytt lösenord" testID="reset-submit-button" onPress={reset} loading={loading} />
            <Button title="Skicka ny kod" variant="ghost" testID="reset-resend-button" onPress={requestCode} style={{ marginTop: spacing.sm }} />
          </>
        )}
      </KeyboardAwareScrollView>
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  help: { color: c.onSurfaceSecondary, fontFamily: fonts.body, fontSize: 15, lineHeight: 22, marginBottom: spacing.xl },
}));
