import * as fs from "fs";
import * as path from "path";

export interface Turn {
  userMessage: string;
  toolCalls: Array<{
    name: string;
    args: Record<string, any>;
    result?: string;
  }>;
  assistantOutput: string;
  timestamp: string;
}

export async function readSessionHistory(
  stateDir: string,
  agentId: string,
  sessionId: string
): Promise<any[]> {
  const sessionFile = path.join(stateDir, "agents", agentId, "sessions", `${sessionId}.jsonl`);

  if (!fs.existsSync(sessionFile)) {
    return [];
  }

  const lines = fs.readFileSync(sessionFile, "utf-8").split("\n").filter(Boolean);
  return lines.map(line => {
    try { return JSON.parse(line); } catch { return null; }
  }).filter(Boolean);
}

export function getLastTurn(history: any[]): Turn | null {
  // A turn = user message → tool calls → assistant response
  // Walk backwards to find the last complete turn
  const messages = history.filter(e => e.type === "message" && e.message);

  let userMessage = "";
  let toolCalls: Turn["toolCalls"] = [];
  let assistantOutput = "";
  let timestamp = "";

  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];

    if (msg.message.role === "assistant" && !assistantOutput) {
      assistantOutput = extractText(msg.message.content);
      timestamp = msg.timestamp || "";
      toolCalls = extractToolCalls(msg.message.content);
    }

    if (msg.message.role === "user" && assistantOutput) {
      userMessage = extractText(msg.message.content);
      break;
    }
  }

  if (!userMessage) return null;

  return { userMessage, toolCalls, assistantOutput, timestamp };
}

function extractText(content: any): string {
  let text: string;
  if (typeof content === "string") {
    text = content;
  } else if (Array.isArray(content)) {
    text = content
      .filter((c: any) => c.type === "text")
      .map((c: any) => c.text)
      .join("\n");
  } else {
    return "";
  }
  return stripOpenClawMessageHeader(text);
}

/**
 * Strip the sender metadata + timestamp header that OpenClaw injects into
 * user messages, e.g.:
 *
 *   Sender (untrusted metadata):
 *   ```json
 *   { "label": "openclaw-control-ui", ... }
 *   ```
 *   [Sun 2026-03-15 02:05 GMT+8] actual message here
 */
function stripOpenClawMessageHeader(text: string): string {
  // Remove sender metadata block: "Sender (...metadata...):\n```json\n{...}\n```\n"
  let stripped = text.replace(/^Sender \([^)]+\):\s*```(?:json)?\s*\{[\s\S]*?\}\s*```\s*/m, "");

  // Remove leading timestamp line: "[Day YYYY-MM-DD HH:MM TZ] "
  stripped = stripped.replace(/^\[[^\]]+\]\s*/, "");

  return stripped.trim();
}

function extractToolCalls(content: any): Turn["toolCalls"] {
  if (!Array.isArray(content)) return [];
  return content
    .filter((c: any) => c.type === "tool_use" || c.type === "toolCall")
    .map((c: any) => ({
      name: c.name || c.toolName || "",
      args: c.input || c.args || {},
      result: c.result,
    }));
}
