import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import type { RunHistoryRow } from "../types";

export function useRunHistory() {
  return useQuery<RunHistoryRow[]>({
    queryKey: ["runHistory"],
    queryFn: api.getRunHistory,
    retry: 1,
  });
}
