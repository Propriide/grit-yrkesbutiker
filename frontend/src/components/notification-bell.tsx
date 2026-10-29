import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { Pressable, Text, View } from "react-native";

import { api, AppNotification } from "@/src/api";
import { Icon } from "@/src/components/ui";
import { fonts, makeStyles, radius, useTheme } from "@/src/theme";

export function useNotifications() {
  return useQuery({
    queryKey: ["notifications"],
    queryFn: () => api<{ items: AppNotification[]; unread: number }>("/notifications"),
    refetchInterval: 30000,
  });
}

export function NotificationBell() {
  const styles = useStyles();
  const { colors } = useTheme();
  const q = useNotifications();
  const unread = q.data?.unread ?? 0;
  return (
    <Pressable testID="notification-bell" onPress={() => router.push("/notifications")} hitSlop={6} style={styles.btn}>
      <Icon name={unread ? "bell-ring" : "bell-outline"} size={24} color={unread ? colors.brandSecondary : colors.onSurface} />
      {unread > 0 && (
        <View style={styles.badge}>
          <Text style={styles.badgeText} testID="notification-unread-count">
            {unread > 99 ? "99+" : unread}
          </Text>
        </View>
      )}
    </Pressable>
  );
}

const useStyles = makeStyles((c) => ({
  btn: { width: 44, height: 44, borderRadius: radius.md, backgroundColor: c.surfaceSecondary, borderWidth: 1, borderColor: c.border, alignItems: "center", justifyContent: "center" },
  badge: { position: "absolute", top: -5, right: -5, minWidth: 20, height: 20, borderRadius: 10, backgroundColor: c.error, alignItems: "center", justifyContent: "center", paddingHorizontal: 4 },
  badgeText: { color: c.onError, fontFamily: fonts.bodyBold, fontSize: 11 },
}));
