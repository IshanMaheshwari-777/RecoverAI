import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import type { HealthResponse } from "../types";

/** The server's *current* credential state -- unlike `report.razorpay_live`,
 * which reflects whatever settings were active when that specific run
 * happened (a synthetic demo report can be stale here). */
export function useHealth() {
  return useQuery<HealthResponse>({
    queryKey: ["health"],
    queryFn: api.getHealth,
    retry: 1,
    staleTime: 30_000,
  });
}
