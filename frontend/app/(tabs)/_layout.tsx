import { Redirect, Tabs, usePathname } from "expo-router";
import { NativeTabs } from "expo-router/unstable-native-tabs";
import { useEffect } from "react";
import { Platform } from "react-native";

import { useAuth } from "@/src/auth";
import { useCart } from "@/src/cart";
import { Icon } from "@/src/components/ui";
import { rememberTab, usesNativeTabs } from "@/src/navigation";
import { colors, fonts } from "@/src/theme";

export default function TabsLayout() {
  const { user, loading } = useAuth();
  const { count } = useCart();
  const pathname = usePathname();
  useEffect(() => rememberTab(pathname), [pathname]);
  if (!loading && !user) return <Redirect href="/login" />;

  if (usesNativeTabs) {
    return (
      <NativeTabs tintColor={colors.brandPrimary}>
        <NativeTabs.Trigger name="index">
          <NativeTabs.Trigger.Icon sf="house.fill" />
          <NativeTabs.Trigger.Label>Hem</NativeTabs.Trigger.Label>
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="shop">
          <NativeTabs.Trigger.Icon sf="square.grid.2x2.fill" />
          <NativeTabs.Trigger.Label>Sortiment</NativeTabs.Trigger.Label>
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="cart">
          <NativeTabs.Trigger.Icon sf="cart.fill" />
          <NativeTabs.Trigger.Label>Varukorg</NativeTabs.Trigger.Label>
          {count > 0 ? <NativeTabs.Trigger.Badge>{String(count)}</NativeTabs.Trigger.Badge> : null}
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="profile">
          <NativeTabs.Trigger.Icon sf="person.crop.circle.fill" />
          <NativeTabs.Trigger.Label>Profil</NativeTabs.Trigger.Label>
        </NativeTabs.Trigger>
      </NativeTabs>
    );
  }

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.brandPrimary,
        tabBarInactiveTintColor: colors.muted,
        tabBarStyle: {
          backgroundColor: colors.surfaceSecondary,
          borderTopColor: colors.border,
          ...(Platform.OS === "web" ? { height: 64 } : {}),
        },
        tabBarItemStyle: { alignSelf: "center" },
        tabBarLabelStyle: { fontFamily: fonts.bodyBold, fontSize: 11 },
        sceneStyle: { backgroundColor: colors.surface },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{ title: "Hem", tabBarButtonTestID: "tab-home", tabBarIcon: ({ color }) => <Icon name="home-variant" size={24} color={color} /> }}
      />
      <Tabs.Screen
        name="shop"
        options={{ title: "Sortiment", tabBarButtonTestID: "tab-shop", tabBarIcon: ({ color }) => <Icon name="view-grid" size={24} color={color} /> }}
      />
      <Tabs.Screen
        name="cart"
        options={{
          title: "Varukorg",
          tabBarButtonTestID: "tab-cart",
          tabBarBadge: count > 0 ? count : undefined,
          tabBarBadgeStyle: { backgroundColor: colors.brandSecondary, color: colors.onBrandSecondary, fontFamily: fonts.bodyBold },
          tabBarIcon: ({ color }) => <Icon name="cart" size={24} color={color} />,
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{ title: "Profil", tabBarButtonTestID: "tab-profile", tabBarIcon: ({ color }) => <Icon name="account-hard-hat" size={24} color={color} /> }}
      />
    </Tabs>
  );
}
