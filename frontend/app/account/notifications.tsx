import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Linking, Platform, ScrollView, Switch, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { Button, haptic, Icon, ScreenHeader } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";
import { useToast } from "@/src/toast";
import { hasWebPushSubscription, isIOSWeb, isStandalone, subscribeWebPush, unsubscribeWebPush, webPushPermission, webPushSupported } from "@/src/webpush";

type Prefs = { orders: boolean; offers: boolean };

export default function NotificationSettings() {
  const styles = useStyles();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const qc = useQueryClient();
  const prefs = useQuery({ queryKey: ["notification-prefs"], queryFn: () => api<Prefs>("/notification-prefs") });
  const [subscribed, setSubscribed] = useState(false);
  const [busy, setBusy] = useState(false);
  const isWeb = Platform.OS === "web";
  const needsInstall = isWeb && isIOSWeb() && !isStandalone();
  const blocked = isWeb && webPushPermission() === "denied";

  useEffect(() => {
    hasWebPushSubscription().then(setSubscribed);
  }, []);

  const setPref = async (k: keyof Prefs, v: boolean) => {
    const next = { ...(prefs.data ?? { orders: true, offers: true }), [k]: v };
    qc.setQueryData(["notification-prefs"], next);
    haptic("selection");
    try {
      await api("/notification-prefs", { method: "PUT", body: next });
    } catch (e: any) {
      toast(e.message, "error");
      prefs.refetch();
    }
  };

  const toggleDevice = async () => {
    setBusy(true);
    try {
      if (subscribed) {
        await unsubscribeWebPush();
        setSubscribed(false);
        toast("Notiser avstängda på den här enheten", "success");
      } else {
        const ok = await subscribeWebPush(true);
        setSubscribed(ok);
        toast(ok ? "Notiser aktiverade på den här enheten" : "Notiser tilläts inte", ok ? "success" : "error");
      }
    } catch (e: any) {
      toast("Kunde inte aktivera notiser. Försök igen eller kontrollera att notiser är tillåtna.", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={styles.root}>
      <ScreenHeader title="Notiser" subtitle="Välj vilka besked du vill få" />
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + spacing.xl, gap: spacing.md }}>
        <PrefRow icon="package-variant-closed-check" title="Orderbesked" sub="Bekräftad, nekad, klar – och nya ordrar för admin" value={prefs.data?.orders ?? true} onChange={(v) => setPref("orders", v)} testID="pref-orders-switch" />
        <PrefRow icon="bullhorn" title="Erbjudanden & kampanjer" sub="Utskick från butiken" value={prefs.data?.offers ?? true} onChange={(v) => setPref("offers", v)} testID="pref-offers-switch" />
        <Text style={styles.help}>Valen gäller pushnotiser i telefonen. Allt syns alltid i notisklockan i appen.</Text>

        <Text style={styles.section}>Den här enheten</Text>
        {!isWeb ? (
          <View style={styles.card}>
            <Text style={styles.body}>Notiser för appen styrs i telefonens inställningar.</Text>
            <Button title="Öppna inställningar" variant="secondary" icon="cog" testID="open-settings-button" onPress={() => Linking.openSettings()} style={{ marginTop: spacing.md }} />
          </View>
        ) : needsInstall ? (
          <View style={styles.card} testID="install-hint">
            <Text style={styles.cardTitle}>Installera appen först</Text>
            <Text style={styles.body}>På iPhone fungerar notiser när appen ligger på hemskärmen: tryck på Dela-knappen i Safari och välj &quot;Lägg till på hemskärmen&quot;. Öppna sedan appen därifrån och kom tillbaka hit.</Text>
          </View>
        ) : !webPushSupported() ? (
          <View style={styles.card}>
            <Text style={styles.body}>Den här webbläsaren stöder inte pushnotiser.</Text>
          </View>
        ) : blocked ? (
          <View style={styles.card} testID="blocked-hint">
            <Text style={styles.cardTitle}>Notiser är blockerade</Text>
            <Text style={styles.body}>Tillåt notiser för appen i telefonens eller webbläsarens inställningar och öppna appen igen.</Text>
          </View>
        ) : (
          <View style={styles.card}>
            <Text style={styles.body}>{subscribed ? "Notiser är aktiverade på den här enheten." : "Aktivera för att få notiser även när appen är stängd."}</Text>
            <Button title={subscribed ? "Stäng av på den här enheten" : "Aktivera notiser"} icon={subscribed ? "bell-off" : "bell-ring"} variant={subscribed ? "secondary" : undefined} testID="webpush-toggle-button" onPress={toggleDevice} loading={busy} style={{ marginTop: spacing.md }} />
          </View>
        )}
      </ScrollView>
    </View>
  );
}

function PrefRow({ icon, title, sub, value, onChange, testID }: { icon: any; title: string; sub: string; value: boolean; onChange: (v: boolean) => void; testID: string }) {
  const styles = useStyles();
  const { colors } = useTheme();
  return (
    <View style={styles.row}>
      <Icon name={icon} size={24} color={colors.brandSecondary} />
      <View style={{ flex: 1 }}>
        <Text style={styles.cardTitle}>{title}</Text>
        <Text style={styles.sub}>{sub}</Text>
      </View>
      <Switch testID={testID} value={value} onValueChange={onChange} trackColor={{ true: colors.brandPrimary, false: colors.surfaceTertiary }} thumbColor={colors.onSurface} {...({ activeThumbColor: colors.onSurface } as object)} />
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.lg, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, backgroundColor: c.surfaceSecondary },
  card: { padding: spacing.lg, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, backgroundColor: c.surfaceSecondary },
  cardTitle: { color: c.onSurface, fontFamily: fonts.bodyBold, fontSize: 15 },
  sub: { color: c.muted, fontFamily: fonts.body, fontSize: 12, marginTop: 2 },
  body: { color: c.onSurfaceSecondary, fontFamily: fonts.body, fontSize: 14, lineHeight: 20, marginTop: 2 },
  help: { color: c.muted, fontFamily: fonts.body, fontSize: 12 },
  section: { color: c.brandSecondary, fontFamily: fonts.display, fontSize: 16, letterSpacing: 1.5, textTransform: "uppercase", marginTop: spacing.lg },
}));
