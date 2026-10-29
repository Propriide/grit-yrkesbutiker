import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api, Favorite } from "@/src/api";

export function useFavorites() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["favorites"], queryFn: () => api<Favorite[]>("/favorites") });
  const list = q.data ?? [];
  const find = (part_no: string, color_code?: string | null) => list.find((f) => f.part_no === part_no && (f.color_code ?? null) === (color_code ?? null));
  const add = async (part_no: string, color_code?: string | null) => {
    await api("/favorites", { method: "POST", body: { part_no, color_code: color_code ?? null } });
    await qc.invalidateQueries({ queryKey: ["favorites"] });
  };
  const remove = async (id: string) => {
    qc.setQueryData<Favorite[]>(["favorites"], (prev) => prev?.filter((f) => f.id !== id));
    await api(`/favorites/${id}`, { method: "DELETE" });
    await qc.invalidateQueries({ queryKey: ["favorites"] });
  };
  return { query: q, list, find, add, remove };
}
