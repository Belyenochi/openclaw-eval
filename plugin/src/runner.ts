import type { GoldenCase } from "./cases.js";

export interface CaseResult {
  caseId: string;
  skillName?: string;
  message: string;
  passed: boolean;
  failures: string[];
  durationMs: number;
  toolCalls: string[];
  output: string;
}

export async function runCase(api: any, goldenCase: GoldenCase, _ctx: any): Promise<CaseResult> {
  const start = Date.now();
  const timeoutMs = (goldenCase.timeout_s || 60) * 1000;

  try {
    const response = await sendTestMessage(api, goldenCase.id, goldenCase.message, timeoutMs);
    const durationMs = Date.now() - start;

    const failures: string[] = [];
    const actualTools = response.toolCalls.map((tc: any) => tc.name);
    const actualCommands = response.toolCalls
      .filter((tc: any) => tc.name === "exec")
      .map((tc: any) => tc.args?.command || "");

    if (goldenCase.expect_tools) {
      for (const tool of goldenCase.expect_tools) {
        if (!actualTools.includes(tool)) {
          failures.push(`expected tool "${tool}" not called`);
        }
      }
    }

    if (goldenCase.expect_commands) {
      for (const cmd of goldenCase.expect_commands) {
        const found = actualCommands.some((ac: string) =>
          ac.toLowerCase().includes(cmd.toLowerCase())
        );
        if (!found) failures.push(`expected command "${cmd}" not found`);
      }
    }

    if (goldenCase.forbidden_commands) {
      for (const cmd of goldenCase.forbidden_commands) {
        const found = actualCommands.some((ac: string) =>
          ac.toLowerCase().includes(cmd.toLowerCase())
        );
        if (found) failures.push(`forbidden command "${cmd}" was executed`);
      }
    }

    if (goldenCase.expect_output_contains) {
      for (const phrase of goldenCase.expect_output_contains) {
        if (!response.output.toLowerCase().includes(phrase.toLowerCase())) {
          failures.push(`output missing "${phrase}"`);
        }
      }
    }

    if (goldenCase.forbidden_tools) {
      for (const tool of goldenCase.forbidden_tools) {
        if (actualTools.includes(tool)) {
          failures.push(`forbidden tool "${tool}" was called`);
        }
      }
    }

    return {
      caseId: goldenCase.id,
      message: goldenCase.message,
      passed: failures.length === 0,
      failures,
      durationMs,
      toolCalls: actualTools,
      output: response.output,
    };
  } catch (error: any) {
    return {
      caseId: goldenCase.id,
      message: goldenCase.message,
      passed: false,
      failures: [`Error: ${error.message}`],
      durationMs: Date.now() - start,
      toolCalls: [],
      output: "",
    };
  }
}

async function sendTestMessage(
  api: any,
  caseId: string,
  message: string,
  timeoutMs: number
): Promise<{ toolCalls: any[]; output: string }> {
  const sessionKey = `edd-test-${caseId}-${Date.now()}`;

  // 1. Send message to isolated session
  const { runId } = await api.runtime.subagent.run({
    sessionKey,
    message,
  });

  // 2. Wait for completion
  const waitResult = await api.runtime.subagent.waitForRun({
    runId,
    timeoutMs,
  });

  if (waitResult.status === "timeout") {
    await api.runtime.subagent.deleteSession({ sessionKey }).catch(() => {});
    throw new Error(`Test case timed out after ${timeoutMs}ms`);
  }

  if (waitResult.status === "error") {
    await api.runtime.subagent.deleteSession({ sessionKey }).catch(() => {});
    throw new Error(`Test case failed: ${waitResult.error}`);
  }

  // 3. Collect messages
  const { messages } = await api.runtime.subagent.getSessionMessages({ sessionKey });

  // 4. Clean up test session
  await api.runtime.subagent.deleteSession({ sessionKey, deleteTranscript: true }).catch(() => {});

  // 5. Extract tool calls and output from messages
  const toolCalls: any[] = [];
  let output = "";

  for (const msg of messages as any[]) {
    if (!msg || !msg.role) continue;

    if (msg.role === "assistant") {
      const content = msg.content;
      if (typeof content === "string") {
        output = content;
      } else if (Array.isArray(content)) {
        for (const block of content) {
          if (block.type === "text") {
            output = block.text || "";
          } else if (block.type === "tool_use") {
            toolCalls.push({
              name: block.name,
              args: block.input || {},
            });
          }
        }
      }
    }
  }

  return { toolCalls, output };
}
