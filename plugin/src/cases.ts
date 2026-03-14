import * as fs from "fs";
import * as path from "path";

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
    return parseEddYaml(content);
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
  const lines: string[] = ["cases:"];

  for (const c of cases) {
    lines.push(`  - id: ${c.id}`);
    lines.push(`    message: "${escapeYaml(c.message)}"`);

    if (c.expect_tools?.length) {
      lines.push(`    expect_tools:`);
      for (const t of c.expect_tools) lines.push(`      - ${t}`);
    }

    if (c.expect_commands?.length) {
      lines.push(`    expect_commands:`);
      for (const cmd of c.expect_commands) lines.push(`      - "${escapeYaml(cmd)}"`);
    }

    if (c.expect_output_contains?.length) {
      lines.push(`    expect_output_contains:`);
      for (const phrase of c.expect_output_contains) lines.push(`      - "${escapeYaml(phrase)}"`);
    }

    if (c.forbidden_commands?.length) {
      lines.push(`    forbidden_commands:`);
      for (const cmd of c.forbidden_commands) lines.push(`      - "${escapeYaml(cmd)}"`);
    }

    if (c.source) lines.push(`    source: ${c.source}`);
    if (c.timestamp) lines.push(`    timestamp: ${c.timestamp}`);
  }

  fs.writeFileSync(filePath, lines.join("\n") + "\n", "utf-8");
}

function escapeYaml(s: string): string {
  return s.replace(/"/g, '\\"');
}

function parseEddYaml(content: string): GoldenCase[] {
  // Minimal YAML parser for the structure we write
  // This is intentionally simple — handles only edd.yaml format
  // For robustness, consider importing a YAML lib in later versions

  const cases: GoldenCase[] = [];
  let current: Partial<GoldenCase> | null = null;
  let currentArrayKey: string | null = null;

  for (const line of content.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed === "cases:") continue;

    if (trimmed.startsWith("- id:")) {
      if (current) cases.push(current as GoldenCase);
      current = { id: trimmed.replace("- id:", "").trim() };
      currentArrayKey = null;
      continue;
    }

    if (!current) continue;

    const kvMatch = trimmed.match(/^(\w+):\s*(.+)$/);
    if (kvMatch && !trimmed.startsWith("- ")) {
      currentArrayKey = null;
      const [, key, val] = kvMatch;
      if (["expect_tools", "expect_commands", "expect_output_contains", "forbidden_commands", "expect_commands_ordered", "forbidden_tools", "tags"].includes(key)) {
        currentArrayKey = key;
        (current as any)[key] = [];
      } else {
        (current as any)[key] = val.replace(/^"|"$/g, "");
      }
      continue;
    }

    if (trimmed.startsWith("- ") && currentArrayKey && current) {
      const val = trimmed.replace(/^- /, "").replace(/^"|"$/g, "");
      ((current as any)[currentArrayKey] as string[]).push(val);
    }
  }

  if (current) cases.push(current as GoldenCase);
  return cases;
}
