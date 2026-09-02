import { useState } from "react";
import { AlertCircle, BarChart3, BookOpen, Brain, GitBranch, ListChecks } from "lucide-react";
import { useReport } from "./hooks/useReport";
import { Header } from "./components/Header";
import { Card, Skeleton } from "./components/ui";
import { Toaster } from "./components/Toast";
import { OverviewTab } from "./components/tabs/OverviewTab";
import { FlowTab } from "./components/tabs/FlowTab";
import { AuditTab } from "./components/tabs/AuditTab";
import { GuideTab } from "./components/tabs/GuideTab";
import { LearningTab } from "./components/tabs/LearningTab";

const TABS = [
  { key: "overview", label: "Overview", icon: BarChart3 },
  { key: "learning", label: "Learning", icon: Brain },
  { key: "flow", label: "Decision flow", icon: GitBranch },
  { key: "audit", label: "Audit trail", icon: ListChecks },
  { key: "guide", label: "How it works", icon: BookOpen },
] as const;

type TabKey = (typeof TABS)[number]["key"];

export default function App() {
  const { data: report, isLoading, error } = useReport();
  const [tab, setTab] = useState<TabKey>("overview");

  return (
    <div className="min-h-full pb-16">
      <Header report={report} />

      {report && (
        <nav
          className="sticky top-[57px] z-20 border-b border-border bg-bg"
          aria-label="Sections"
        >
          <div className="mx-auto flex max-w-[1280px] gap-1 overflow-x-auto px-6">
            {TABS.map((t) => {
              const Icon = t.icon;
              const active = tab === t.key;
              return (
                <button
                  key={t.key}
                  onClick={() => setTab(t.key)}
                  aria-current={active ? "page" : undefined}
                  className={`flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 text-xs font-medium transition ${
                    active
                      ? "border-series-1 text-ink"
                      : "border-transparent text-ink-muted hover:text-ink-secondary"
                  }`}
                >
                  <Icon className="size-3.5" />
                  {t.label}
                  {t.key === "audit" && (
                    <span className="tabular rounded-full bg-surface-2 px-1.5 text-[10px] text-ink-muted">
                      {report.results.length}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </nav>
      )}

      <main className="mx-auto max-w-[1280px] px-6 py-6">
        {isLoading && <LoadingState />}
        {error && !report && <ErrorState message={(error as Error).message} />}
        {report && (
          <>
            {report.mode === "shadow" && (
              <div className="mb-4 rounded-lg border border-warn/40 bg-warn/10 px-3 py-2 text-xs text-warn">
                Shadow run — every decision was made, nothing was executed. Not saved.
              </div>
            )}
            {tab === "overview" && <OverviewTab report={report} />}
            {tab === "learning" && <LearningTab report={report} />}
            {tab === "flow" && <FlowTab report={report} />}
            {tab === "audit" && <AuditTab report={report} />}
            {tab === "guide" && <GuideTab report={report} />}

            <footer className="mt-10 border-t border-border pt-4 text-center text-[11px] leading-relaxed text-ink-muted">
              Deterministic rules move money; Claude only reasons and drafts. “Projected recovered”
              is a labelled modelling assumption — production replaces it with webhook
              confirmations.
            </footer>
          </>
        )}
      </main>

      <Toaster />
    </div>
  );
}

function LoadingState() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-5 w-2/3" />
      <div className="grid gap-3 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
      <Skeleton className="h-72" />
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <Card className="mx-auto max-w-md text-center">
      <AlertCircle className="mx-auto size-6 text-warn" />
      <h2 className="mt-2 text-sm font-semibold text-ink">No results yet</h2>
      <p className="mt-1 text-xs text-ink-muted">{message}</p>
      <p className="mt-3 text-xs leading-relaxed text-ink-muted">
        Press <strong className="text-ink-secondary">Run agent</strong> above, or start one from
        the terminal with <code className="text-ink-secondary">recover-ai run</code>.
      </p>
    </Card>
  );
}
