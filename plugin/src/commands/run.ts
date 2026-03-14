import { loadCases, type GoldenCase } from "../cases.js";
import { runCase, type CaseResult } from "../runner.js";
import { loadReport, saveReport, diffReports, type Report } from "../report.js";
import { resolveWorkspace } from "../workspace.js";
import * as path from "path";
import * as fs from "fs";

export async function runCommand(api: any, ctx: any): Promise<{ text: string }> {
  const workspace = resolveWorkspace(api);

  // Discover all edd.yaml files
  const skillsDir = path.join(workspace, "skills");
  const allCases = discoverCases(skillsDir);

  if (allCases.length === 0) {
    return {
      text:
        "📋 No saved cases found.\n" +
        "Use `/edd save` after a good agent interaction to start building your test suite.",
    };
  }

  // Run each case
  const results: CaseResult[] = [];
  for (const { skillName, goldenCase } of allCases) {
    const result = await runCase(api, goldenCase, ctx);
    results.push({ ...result, skillName });
  }

  // Build report
  const report: Report = {
    timestamp: new Date().toISOString(),
    results,
    summary: {
      total: results.length,
      passed: results.filter(r => r.passed).length,
      failed: results.filter(r => !r.passed).length,
    },
  };

  // Load previous report and diff
  const reportsDir = path.join(workspace, "edd", "reports");
  const previousReport = loadReport(reportsDir);
  const regressions = previousReport ? diffReports(previousReport, report) : [];

  // Save current report
  saveReport(reportsDir, report);

  // Format output
  const lines: string[] = [];
  for (const r of results) {
    const status = r.passed ? "✅" : "❌";
    const regression = regressions.find(reg => reg.caseId === r.caseId);
    const regMark = regression ? " ⚠️ REGRESSION" : "";
    lines.push(`  ${status} "${r.message}" ${r.passed ? "passed" : "failed"}${regMark} (${r.durationMs}ms)`);

    if (!r.passed && r.failures.length > 0) {
      for (const f of r.failures) {
        lines.push(`     ${f}`);
      }
    }
  }

  return {
    text:
      `🧪 EDD: ${report.summary.passed}/${report.summary.total} passed` +
      (regressions.length > 0 ? ` — ${regressions.length} regression(s)` : "") +
      "\n\n" + lines.join("\n"),
  };
}

function discoverCases(skillsDir: string): Array<{ skillName: string; goldenCase: GoldenCase }> {
  const results: Array<{ skillName: string; goldenCase: GoldenCase }> = [];

  if (!fs.existsSync(skillsDir)) return results;

  for (const entry of fs.readdirSync(skillsDir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const eddPath = path.join(skillsDir, entry.name, "edd.yaml");
    if (fs.existsSync(eddPath)) {
      const cases = loadCases(eddPath);
      for (const c of cases) {
        results.push({ skillName: entry.name, goldenCase: c });
      }
    }
  }

  return results;
}
