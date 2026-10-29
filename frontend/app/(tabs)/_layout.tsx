import { Redirect, Tabs } from "expo-router";
import { NativeTabs } from "expo-router/unstable-native-tabs";
import { Platform } from "react-native";

import { useAuth } from "@/src/auth";
import { useCart } from "@/src/cart";
import { Icon } from "@/src/components/ui";
import { usesNativeTabs } from "@/src/navigation";
import { colors, fonts } from "@/src/theme";

export default function TabsLayout() {
  const { user, loading } = useAuth();
  const { count } = useCart();
  if (!loading && !user) return <Redirect href="/login" />;

  if (usesNativeTabs) {
    return (
      <NativeTabs tintColor={colors.brandPrimary}>
        <NativeTabs.Trigger name="index">
          <NativeTabs.Trigger.Icon sf="square.grid.2x2.fill" />
          <NativeTabs.Trigger.Label>Sortiment</NativeTabs.Trigger.Label>
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="cart">
          <NativeTabs.Trigger.Icon sf="cart.fill" />
          <NativeTabs.Trigger.Label>Varukorg</NativeTabs.Trigger.Label>
          {count > 0 ? <NativeTabs.Trigger.Badge>{String(count)}</NativeTabs.Trigger.Badge> : null}
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="orders">
          <NativeTabs.Trigger.Icon sf="shippingbox.fill" />
          <NativeTabs.Trigger.Label>Ordrar</NativeTabs.Trigger.Label>
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
        name="orders"
        options={{ title: "Ordrar", tabBarButtonTestID: "tab-orders", tabBarIcon: ({ color }) => <Icon name="package-variant-closed" size={24} color={color} /> }}
      />
      <Tabs.Screen
        name="profile"
        options={{ title: "Profil", tabBarButtonTestID: "tab-profile", tabBarIcon: ({ color }) => <Icon name="account-hard-hat" size={24} color={color} /> }}
      />
    </Tabs>
  );
}
