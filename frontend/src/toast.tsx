import { createContext, ReactNode, useCallback, useContext, useRef, useState } from "react";
import { Text, View } from "react-native";
import Animated, { FadeInDown as FadeInUp, FadeOutDown as FadeOutUp } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { fonts, makeStyles, radius, spacing } from "@/src/theme";

type ToastType = "success" | "error" | "info";
type Toast = { id: number; message: string; type: ToastType };

const Ctx = createContext<(message: string, type?: ToastType) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<Toast | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const insets = useSafeAreaInsets();
  const styles = useStyles();

  const show = useCallback((message: string, type: ToastType = "info") => {
    if (timer.current) clearTimeout(timer.current);
    setToast({ id: Date.now(), message, type });
    timer.current = setTimeout(() => setToast(null), 3200);
  }, []);

  return (
    <Ctx.Provider value={show}>
      <View style={{ flex: 1 }}>
        {children}
        {toast && (
          <Animated.View
            key={toast.id}
            entering={FadeInUp}
            exiting={FadeOutUp}
            pointerEvents="none"
            style={[styles.wrap, { bottom: insets.bottom + 96 }]}
          >
            <View
              testID="toast-message"
              style={[styles.toast, toast.type === "error" ? styles.error : toast.type === "success" ? styles.success : styles.info]}
            >
              <Text style={[styles.text, toast.type === "info" ? styles.textInfo : null]}>{toast.message}</Text>
            </View>
          </Animated.View>
        )}
      </View>
    </Ctx.Provider>
  );
}

export const useToast = () => useContext(Ctx);

const useStyles = makeStyles((c) => ({
  wrap: { position: "absolute", left: spacing.lg, right: spacing.lg },
  toast: { borderRadius: radius.md, paddingVertical: spacing.md, paddingHorizontal: spacing.lg, borderLeftWidth: 4 },
  success: { backgroundColor: c.surfaceTertiary, borderLeftColor: c.success },
  error: { backgroundColor: c.surfaceTertiary, borderLeftColor: c.error },
  info: { backgroundColor: c.surfaceTertiary, borderLeftColor: c.brandPrimary },
  text: { color: c.onSurface, fontFamily: fonts.bodyBold, fontSize: 14 },
  textInfo: {},
}));
