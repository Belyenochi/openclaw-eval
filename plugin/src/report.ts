import * as fs from "fs";
import * as path from "path";
import type { CaseResult } from "./runner.js";

export interface Report {
  timestamp: string;
  results: CaseResult[];
  summary: {
    total: number;
    passed: number;
    failed: number;
  };
}

export interface Regression {
  caseId: string;
  message: string;
  previousStatus: "passed" | "failed";
  currentStatus: "passed" | "failed";
}

export function loadReport(reportsDir: string): Report | null {
  const latestPath = path.join(reportsDir, "latest.json");
  if (!fs.existsSync(latestPath)) return null;

  try {
    return JSON.parse(fs.readFileSync(latestPath, "utf-8"));
  } catch {
    return null;
  }
}

export function saveReport(reportsDir: string, report: Report): void {
  if (!fs.existsSync(reportsDir)) {
    fs.mkdirSync(reportsDir, { recursive: true });
  }

  // Save as latest
  fs.writeFileSync(
    path.join(reportsDir, "latest.json"),
    JSON.stringify(report, null, 2),
    "utf-8"
  );

  // Also save timestamped copy
  const ts = report.timestamp.replace(/[:.]/g, "-");
  fs.writeFileSync(
    path.join(reportsDir, `report-${ts}.json`),
    JSON.stringify(report, null, 2),
    "utf-8"
  );
}

export function diffReports(previous: Report, current: Report): Regression[] {
  const regressions: Regression[] = [];

  for (const curr of current.results) {
    const prev = previous.results.find(r => r.caseId === curr.caseId);
    if (prev && prev.passed && !curr.passed) {
      regressions.push({
        caseId: curr.caseId,
        message: curr.message,
        previousStatus: "passed",
        currentStatus: "failed",
      });
    }
  }

  return regressions;
}
