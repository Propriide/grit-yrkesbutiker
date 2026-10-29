import { Redirect, Stack } from "expo-router";

import { useAuth } from "@/src/auth";
import { colors } from "@/src/theme";

export default function AdminLayout() {
  const { user, loading } = useAuth();
  if (!loading && user?.role !== "admin") return <Redirect href="/" />;
  return <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.surface } }} />;
}
