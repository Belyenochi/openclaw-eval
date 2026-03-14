import * as path from "path";

export function resolveWorkspace(api: any): string {
  // Priority:
  // 1. Plugin config override
  // 2. Agent workspace from OpenClaw config
  // 3. Default <stateDir>/workspace

  const pluginConfig = api.pluginConfig || {};
  if (pluginConfig.casesDir) return pluginConfig.casesDir as string;

  const agentWorkspace = api.config?.agents?.defaults?.workspace;
  if (agentWorkspace) return agentWorkspace;

  const stateDir: string = api.runtime.state.resolveStateDir();
  return path.join(stateDir, "workspace");
}
