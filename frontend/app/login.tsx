import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { Redirect, router } from "expo-router";
import { useRef, useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAuth } from "@/src/auth";
import { Button, ErrorBanner, Field, haptic } from "@/src/components/ui";
import { fonts, makeStyles, spacing, useTheme } from "@/src/theme";

const HERO =
  "https://images.unsplash.com/photo-1614213951697-a45781262acf?crop=entropy&cs=srgb&fm=jpg&ixlib=rb-4.1.0&q=85&w=1200";

export default function Login() {
  const { user, login } = useAuth();
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const pwRef = useRef<TextInput>(null);

  if (user) return <Redirect href="/(tabs)" />;

  const submit = async () => {
    if (!email.trim() || !password) {
      setError("Fyll i e-post och lösenord.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      router.replace("/(tabs)");
    } catch (e: any) {
      haptic("error");
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.root}>
      <Image source={{ uri: HERO }} style={styles.hero} contentFit="cover" />
      <LinearGradient colors={["transparent", colors.scrim, colors.surface]} locations={[0, 0.55, 0.8]} style={styles.hero} />
      <KeyboardAwareScrollView
        bottomOffset={24}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={[styles.content, { paddingTop: insets.top + spacing.xxl, paddingBottom: insets.bottom + spacing.xl }]}
      >
        <View style={styles.brandRow}>
          <View style={styles.brandMark} />
          <Text style={styles.brandText}>ARBETSKLÄDER · ORDER</Text>
        </View>
        <View style={{ flex: 1, minHeight: 160 }} />
        <Text style={styles.title}>Logga in</Text>
        <Text style={styles.subtitle}>Beställ arbetskläder från Blåkläders sortiment till ditt företag.</Text>
        {!!error && <ErrorBanner message={error} testID="login-error" />}
        <Field
          label="E-post"
          testID="login-email-input"
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          autoComplete="email"
          keyboardType="email-address"
          placeholder="namn@foretag.se"
          returnKeyType="next"
          onSubmitEditing={() => pwRef.current?.focus()}
        />
        <Field
          ref={pwRef}
          label="Lösenord"
          testID="login-password-input"
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          placeholder="••••••••"
          returnKeyType="go"
          onSubmitEditing={submit}
        />
        <Button title="Logga in" testID="login-submit-button" onPress={submit} loading={loading} />
        <Pressable testID="forgot-password-link" onPress={() => router.push("/forgot-password")} style={styles.link}>
          <Text style={styles.linkStrong}>Glömt lösenord?</Text>
        </Pressable>
        <Pressable testID="go-to-register-link" onPress={() => router.push("/register")} style={styles.link}>
          <Text style={styles.linkText}>
            Inget konto? <Text style={styles.linkStrong}>registrera dig här</Text>
          </Text>
        </Pressable>
      </KeyboardAwareScrollView>
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  hero: { position: "absolute", top: 0, left: 0, right: 0, height: 560 },
  content: { flexGrow: 1, paddingHorizontal: spacing.xl },
  brandRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  brandMark: { width: 14, height: 28, backgroundColor: c.brandPrimary },
  brandText: { color: c.onSurface, fontFamily: fonts.displayHeavy, fontSize: 20, letterSpacing: 2 },
  title: { color: c.onSurface, fontFamily: fonts.displayHeavy, fontSize: 48, textTransform: "uppercase", lineHeight: 52 },
  subtitle: { color: c.onSurfaceSecondary, fontFamily: fonts.body, fontSize: 15, marginBottom: spacing.xl, marginTop: spacing.xs },
  link: { minHeight: 48, alignItems: "center", justifyContent: "center", marginTop: spacing.md },
  linkText: { color: c.onSurfaceSecondary, fontFamily: fonts.body, fontSize: 14 },
  linkStrong: { color: c.brandPrimary, fontFamily: fonts.bodyBold },
}));
