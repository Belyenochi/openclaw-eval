import * as fs from "fs";
import * as path from "path";
import yaml from "js-yaml";

export interface GoldenCase {
  id: string;
  message: string;
  expect_tools?: string[];
  expect_commands?: string[];
  expect_commands_ordered?: string[];
  forbidden_commands?: string[];
  expect_output_contains?: string[];
  forbidden_tools?: string[];
  timeout_s?: number;
  timestamp?: string;
  source?: string;
  tags?: string[];
}

export function loadCases(filePath: string): GoldenCase[] {
  if (!fs.existsSync(filePath)) return [];

  const content = fs.readFileSync(filePath, "utf-8");

  try {
    const doc = yaml.load(content) as { cases?: GoldenCase[] };
    return doc?.cases ?? [];
  } catch {
    return [];
  }
}

export function appendCase(workspace: string, skillName: string, newCase: GoldenCase): string {
  const casesPath = path.join(workspace, "skills", skillName, "edd.yaml");
  const dir = path.dirname(casesPath);

  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  const existing = loadCases(casesPath);

  // Dedupe by message
  const isDuplicate = existing.some(c => c.message === newCase.message);
  if (isDuplicate) {
    // Update existing case
    const updated = existing.map(c =>
      c.message === newCase.message ? { ...c, ...newCase, id: c.id } : c
    );
    writeCases(casesPath, updated);
  } else {
    existing.push(newCase);
    writeCases(casesPath, existing);
  }

  return casesPath;
}

function writeCases(filePath: string, cases: GoldenCase[]): void {
  const content = yaml.dump({ cases }, { lineWidth: -1 });
  fs.writeFileSync(filePath, content, "utf-8");
}
