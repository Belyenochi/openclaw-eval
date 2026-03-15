import { saveCommand } from "./commands/save.js";
import { runCommand } from "./commands/run.js";

export default function register(api: any) {
  // Track the latest session so /edd save can find it
  // (PluginCommandContext has no sessionId — must capture via hook)
  const latestSession: { sessionId?: string; sessionKey?: string; agentId?: string } = {};

  api.on("session_start", (event: any, ctx: any) => {
    latestSession.sessionId = event.sessionId;
    latestSession.sessionKey = event.sessionKey;
    latestSession.agentId = ctx.agentId;
  });

  api.registerCommand({
    name: "edd",
    description: "Evaluation-Driven Development — /edd save to save golden case, /edd to run eval",
    acceptsArgs: true,
    handler: async (ctx: any) => {
      const args = (ctx.args || "").trim();
      const parts = args.split(/\s+/);

      if (parts[0] === "save") {
        const skillName = parts[1] || "default";
        return saveCommand(api, ctx, latestSession, skillName);
      }

      return runCommand(api, ctx);
    },
  });

  api.logger.info("[edd] Plugin registered. Use /edd save and /edd.");
}
