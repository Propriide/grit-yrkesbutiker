import MaterialDesignIcons from "@react-native-vector-icons/material-design-icons";
import * as Haptics from "expo-haptics";
import { router } from "expo-router";
import { forwardRef, ReactNode, useState } from "react";
import {
  ActivityIndicator,
  Platform,
  Pressable,
  StyleProp,
  Text,
  TextInput,
  TextInputProps,
  View,
  ViewStyle,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

export const Icon = MaterialDesignIcons;
export type IconName = React.ComponentProps<typeof MaterialDesignIcons>["name"];

export function haptic(kind: "impact" | "success" | "selection" | "error" = "impact") {
  if (Platform.OS === "web") return;
  if (kind === "impact") Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
  else if (kind === "selection") Haptics.selectionAsync();
  else Haptics.notificationAsync(kind === "success" ? Haptics.NotificationFeedbackType.Success : Haptics.NotificationFeedbackType.Error);
}

type BtnProps = {
  title: string;
  onPress: () => void;
  variant?: "primary" | "secondary" | "ghost" | "danger";
  loading?: boolean;
  disabled?: boolean;
  icon?: IconName;
  testID: string;
  style?: StyleProp<ViewStyle>;
};

export function Button({ title, onPress, variant = "primary", loading, disabled, icon, testID, style }: BtnProps) {
  const styles = useStyles();
  const { colors } = useTheme();
  const fg =
    variant === "primary" ? colors.onBrandPrimary : variant === "danger" ? colors.error : variant === "ghost" ? colors.brandPrimary : colors.onSurface;
  return (
    <Pressable
      testID={testID}
      disabled={disabled || loading}
      onPress={() => {
        haptic("impact");
        onPress();
      }}
      style={({ pressed }) => [
        styles.btn,
        variant === "primary" && styles.btnPrimary,
        variant === "secondary" && styles.btnSecondary,
        variant === "danger" && styles.btnDanger,
        variant === "ghost" && styles.btnGhost,
        (disabled || loading) && { opacity: 0.5 },
        pressed && { opacity: 0.8, transform: [{ scale: 0.98 }] },
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={fg} />
      ) : (
        <View style={styles.btnRow}>
          {icon && <Icon name={icon} size={20} color={fg} />}
          <Text style={[styles.btnText, { color: fg }]}>{title}</Text>
        </View>
      )}
    </Pressable>
  );
}

type FieldProps = TextInputProps & { label: string; testID: string; error?: string; optional?: boolean };

export const Field = forwardRef<TextInput, FieldProps>(function Field({ label, error, optional, style, ...rest }, ref) {
  const styles = useStyles();
  const { colors } = useTheme();
  const [focused, setFocused] = useState(false);
  return (
    <View style={styles.field}>
      <Text style={styles.label}>
        {label}
        {optional ? <Text style={styles.optional}>  (frivilligt)</Text> : null}
      </Text>
      <TextInput
        ref={ref}
        placeholderTextColor={colors.muted}
        onFocus={(e) => {
          setFocused(true);
          rest.onFocus?.(e);
        }}
        onBlur={(e) => {
          setFocused(false);
          rest.onBlur?.(e);
        }}
        style={[styles.input, focused && styles.inputFocused, !!error && styles.inputError, style]}
        {...rest}
      />
      {!!error && <Text style={styles.fieldError}>{error}</Text>}
    </View>
  );
});

export function ScreenHeader({ title, subtitle, back = true, right }: { title: string; subtitle?: string; back?: boolean; right?: ReactNode }) {
  const styles = useStyles();
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  return (
    <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
      {back && (
        <Pressable testID="header-back-button" hitSlop={8} onPress={() => (router.canGoBack() ? router.back() : router.replace("/"))} style={styles.backBtn}>
          <Icon name="arrow-left" size={24} color={colors.onSurface} />
        </Pressable>
      )}
      <View style={{ flex: 1 }}>
        <Text style={styles.headerTitle} numberOfLines={1}>
          {title}
        </Text>
        {subtitle ? <Text style={styles.headerSub}>{subtitle}</Text> : null}
      </View>
      {right}
    </View>
  );
}

export function EmptyState({ icon, title, text, action }: { icon: IconName; title: string; text?: string; action?: ReactNode }) {
  const styles = useStyles();
  const { colors } = useTheme();
  return (
    <View style={styles.empty} testID="empty-state">
      <View style={styles.emptyIcon}>
        <Icon name={icon} size={40} color={colors.brandPrimary} />
      </View>
      <Text style={styles.emptyTitle}>{title}</Text>
      {text ? <Text style={styles.emptyText}>{text}</Text> : null}
      {action}
    </View>
  );
}

export function Stepper({ value, onChange, testIDPrefix, compact }: { value: number; onChange: (v: number) => void; testIDPrefix: string; compact?: boolean }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const size = compact ? 36 : 48;
  return (
    <View style={styles.stepper}>
      <Pressable
        testID={`${testIDPrefix}-decrease`}
        onPress={() => {
          haptic("selection");
          onChange(Math.max(1, value - 1));
        }}
        style={[styles.stepBtn, { width: size, height: size }]}
      >
        <Icon name="minus" size={20} color={colors.onSurface} />
      </Pressable>
      <Text testID={`${testIDPrefix}-value`} style={[styles.stepValue, compact && { fontSize: 18, minWidth: 32 }]}>
        {value}
      </Text>
      <Pressable
        testID={`${testIDPrefix}-increase`}
        onPress={() => {
          haptic("selection");
          onChange(Math.min(9999, value + 1));
        }}
        style={[styles.stepBtn, { width: size, height: size }]}
      >
        <Icon name="plus" size={20} color={colors.onSurface} />
      </Pressable>
    </View>
  );
}

export function ErrorBanner({ message, testID = "error-banner" }: { message: string; testID?: string }) {
  const styles = useStyles();
  const { colors } = useTheme();
  return (
    <View style={styles.banner} testID={testID}>
      <Icon name="alert-circle" size={18} color={colors.error} />
      <Text style={styles.bannerText}>{message}</Text>
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  btn: { minHeight: 52, borderRadius: radius.md, alignItems: "center", justifyContent: "center", paddingHorizontal: spacing.lg },
  btnPrimary: { backgroundColor: c.brandPrimary },
  btnSecondary: { backgroundColor: c.surfaceTertiary, borderWidth: 1, borderColor: c.border },
  btnDanger: { backgroundColor: "transparent", borderWidth: 1, borderColor: c.error },
  btnGhost: { backgroundColor: "transparent" },
  btnRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  btnText: { fontFamily: fonts.display, fontSize: 18, letterSpacing: 1, textTransform: "uppercase" },
  field: { marginBottom: spacing.lg },
  label: { color: c.onSurfaceSecondary, fontFamily: fonts.bodyBold, fontSize: 12, marginBottom: spacing.sm, textTransform: "uppercase", letterSpacing: 0.8 },
  optional: { color: c.muted, fontFamily: fonts.body, textTransform: "none", letterSpacing: 0 },
  input: {
    minHeight: 50,
    backgroundColor: c.surfaceTertiary,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: c.border,
    color: c.onSurface,
    paddingHorizontal: spacing.lg,
    fontFamily: fonts.body,
    fontSize: 16,
  },
  inputFocused: { borderColor: c.brandPrimary },
  inputError: { borderColor: c.error },
  fieldError: { color: c.error, fontFamily: fonts.body, fontSize: 12, marginTop: spacing.xs },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
    backgroundColor: c.surface,
    borderBottomWidth: 1,
    borderBottomColor: c.divider,
  },
  backBtn: { width: 44, height: 44, alignItems: "center", justifyContent: "center", marginLeft: -spacing.sm },
  headerTitle: { color: c.onSurface, fontFamily: fonts.display, fontSize: 26, textTransform: "uppercase", letterSpacing: 0.5 },
  headerSub: { color: c.muted, fontFamily: fonts.body, fontSize: 12 },
  empty: { alignItems: "center", justifyContent: "center", padding: spacing.xxl, gap: spacing.md },
  emptyIcon: { width: 80, height: 80, borderRadius: radius.lg, backgroundColor: c.brandTertiary, alignItems: "center", justifyContent: "center" },
  emptyTitle: { color: c.onSurface, fontFamily: fonts.display, fontSize: 24, textTransform: "uppercase", textAlign: "center" },
  emptyText: { color: c.muted, fontFamily: fonts.body, fontSize: 14, textAlign: "center", marginBottom: spacing.sm },
  stepper: { flexDirection: "row", alignItems: "center", backgroundColor: c.surfaceTertiary, borderRadius: radius.md, borderWidth: 1, borderColor: c.border },
  stepBtn: { alignItems: "center", justifyContent: "center" },
  stepValue: { color: c.onSurface, fontFamily: fonts.displayHeavy, fontSize: 24, minWidth: 48, textAlign: "center" },
  banner: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: c.surfaceSecondary,
    borderLeftWidth: 4,
    borderLeftColor: c.error,
    borderRadius: radius.sm,
    padding: spacing.md,
    marginBottom: spacing.lg,
  },
  bannerText: { color: c.onSurface, fontFamily: fonts.body, fontSize: 14, flex: 1 },
}));
