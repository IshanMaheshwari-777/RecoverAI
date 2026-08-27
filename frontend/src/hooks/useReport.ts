import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import type { PipelineReport } from "../types";

export function useReport() {
  return useQuery<PipelineReport>({
    queryKey: ["report"],
    queryFn: api.getReport,
    retry: 1,
  });
}
