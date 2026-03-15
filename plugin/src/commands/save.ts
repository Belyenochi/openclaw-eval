import { readSessionHistory, getLastTurn } from "../session.js";
import { appendCase, type GoldenCase } from "../cases.js";
import { resolveWorkspace } from "../workspace.js";

export async function saveCommand(
  api: any,
  ctx: any,
  latestSession: { sessionId?: string; sessionKey?: string; agentId?: string },
  skillName: string = "default"
): Promise<{ text: string }> {
  const workspace = resolveWorkspace(api);
  const { sessionId, agentId } = latestSession;

  if (!sessionId) {
    return {
      text:
        "❌ No active session found.\n" +
        "Make sure you have had at least one conversation turn before saving.",
    };
  }

  // Read session history from JSONL file
  const stateDir = api.runtime.state.resolveStateDir();
  const history = await readSessionHistory(stateDir, agentId || "main", sessionId);
  const lastTurn = getLastTurn(history);

  if (!lastTurn) {
    return { text: "❌ No completed turn found in current session." };
  }

  if (!lastTurn.userMessage) {
    return { text: "❌ Could not find the user message for the last turn." };
  }

  const goldenCase: GoldenCase = {
    id: generateCaseId(lastTurn),
    message: lastTurn.userMessage,
    expect_tools: lastTurn.toolCalls.map(tc => tc.name),
    expect_commands: extractCommands(lastTurn.toolCalls),
    expect_output_contains: [],
    timestamp: new Date().toISOString(),
    source: "saved",
  };

  const casesPath = appendCase(workspace, skillName, goldenCase);

  return {
    text:
      `✅ Saved golden case for skill "${skillName}"\n` +
      `   Message: "${goldenCase.message}"\n` +
      `   Expected tools: ${goldenCase.expect_tools?.join(", ") || "(none)"}\n` +
      `   Saved to: ${casesPath}`,
  };
}

function generateCaseId(turn: any): string {
  const hash = turn.userMessage.slice(0, 20).replace(/\W+/g, "_").toLowerCase();
  const ts = Date.now().toString(36);
  return `${hash}_${ts}`;
}

function extractCommands(toolCalls: any[]): string[] {
  return toolCalls
    .filter(tc => tc.name === "exec" && tc.args?.command)
    .map(tc => tc.args.command);
}

