import type { PipelineReport } from "../../types";
import { SectionLead } from "../ui";
import { FlowDiagram } from "../FlowDiagram";
import { ActionBreakdownCard, ExecutionMethodCard } from "../Breakdowns";

export function FlowTab({ report }: { report: PipelineReport }) {
  return (
    <div className="space-y-5">
      <SectionLead title="How every transaction moved through the agent">
        Read left to right. Each transaction was diagnosed (by a fixed rule, or by Claude for the
        ambiguous ones), the compliance layer decided which action was actually allowed, and each
        action carries a projected outcome. Hover any block to trace its paths.
      </SectionLead>

      <FlowDiagram report={report} />

      <div className="grid items-start gap-5 lg:grid-cols-2">
        <ExecutionMethodCard report={report} />
        <ActionBreakdownCard report={report} />
      </div>
    </div>
  );
}
