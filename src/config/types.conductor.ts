import type { ExecApprovalForwardTarget } from "./types.approvals.js";

export type ConductorAnalyzerProvider = "gemini" | "openai" | "regex" | "local";

export type ConductorAnalyzerConfig = {
  /** Which analyzer to use for detecting external-access requests. Default: "gemini". */
  provider?: ConductorAnalyzerProvider;
  /** API key for the analyzer provider. Falls back to env vars (GEMINI_API_KEY, etc.). */
  apiKey?: string;
  /** Model name (e.g., "gemini-2.0-flash", "gpt-4o-mini"). */
  model?: string;
  /** Minimum confidence threshold to trigger authorization (0-1). Default: 0.7. */
  confidenceThreshold?: number;
  /** Custom detection patterns (regex strings) for the regex provider. */
  patterns?: string[];
};

export type ConductorAuthConfig = {
  /** Where to send authorization requests. Uses the same target format as exec approvals. */
  targets?: ExecApprovalForwardTarget[];
  /** Timeout for operator response (ms). Default: 120000 (2 minutes). */
  timeoutMs?: number;
  /** Auto-approve requests matching these URL patterns (glob). */
  autoApprovePatterns?: string[];
  /** Always deny requests matching these URL patterns (glob). */
  autoDenyPatterns?: string[];
};

export type ConductorBrowserConfig = {
  /** Browser profile to use. Default: "openclaw". */
  profile?: string;
  /** Whether to use headless mode. Default: true. */
  headless?: boolean;
  /** Default timeout for browser actions (ms). Default: 30000. */
  actionTimeoutMs?: number;
  /** Whether to capture screenshots during execution. Default: true. */
  captureScreenshots?: boolean;
};

export type ConductorConfig = {
  /** Enable the conductor module. Default: false. */
  enabled?: boolean;
  /** The command to wrap (e.g., "claude", "claude-code"). Default: "claude". */
  wrappedCommand?: string;
  /** Arguments to pass to the wrapped command. */
  wrappedArgs?: string[];
  /** How often to flush terminal buffer for analysis (ms). Default: 2000. */
  bufferFlushIntervalMs?: number;
  /** Maximum terminal buffer size before forced flush (bytes). Default: 8192. */
  maxBufferSize?: number;
  /** Analyzer configuration. */
  analyzer?: ConductorAnalyzerConfig;
  /** Authorization/forwarding configuration. */
  auth?: ConductorAuthConfig;
  /** Browser automation configuration. */
  browser?: ConductorBrowserConfig;
  /** Keep audit log of all conductor actions. Default: true. */
  auditLog?: boolean;
  /** Path for audit log. Default: "~/.openclaw/conductor-audit.jsonl". */
  auditLogPath?: string;
};
