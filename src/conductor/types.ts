/**
 * Aether Conductor — "Operation Ouroboros"
 *
 * Closed-loop system where:
 *   - Claude Code (Worker) runs inside the conductor
 *   - Gemini/AI (General) analyzes Claude's output for external-access requests
 *   - Aether (Body) executes authorized actions via browser automation
 *   - The operator (Commander) approves via messaging (Telegram/Signal/etc.)
 *
 * The conductor intercepts Claude's terminal output, detects when it needs
 * external access (visit a URL, fetch credentials, check a service), routes
 * the request through the operator for authorization, executes via Aether's
 * browser, and injects the result back into Claude's stdin.
 */

// ---------------------------------------------------------------------------
// External-access request detected by the analyzer
// ---------------------------------------------------------------------------

export type ExternalAccessKind =
  | "url-visit"        // Claude wants someone to visit a URL
  | "credential-fetch" // Claude needs credentials from an external service
  | "api-check"        // Claude wants to verify an API endpoint
  | "service-action"   // Claude needs an action performed on an external service
  | "file-download"    // Claude needs a file from the web
  | "verification"     // Claude wants visual/content verification of a page
  | "unknown";         // Catch-all for unrecognized requests

export type ExternalAccessRequest = {
  id: string;
  /** The kind of external access detected. */
  kind: ExternalAccessKind;
  /** AI-generated summary of what Claude is asking for. */
  summary: string;
  /** The raw terminal output that triggered detection. */
  rawOutput: string;
  /** Target URL if one was extracted. */
  url?: string;
  /** Target service name if identified. */
  service?: string;
  /** Specific data Claude is looking for. */
  dataNeeded?: string;
  /** Suggested browser actions to fulfill the request. */
  suggestedActions?: BrowserAction[];
  /** Timestamp when the request was created. */
  createdAtMs: number;
  /** Timestamp when the request expires. */
  expiresAtMs: number;
  /** The agent/session that generated this request. */
  sessionKey?: string;
};

// ---------------------------------------------------------------------------
// Authorization decisions
// ---------------------------------------------------------------------------

export type ConductorDecision = "approve" | "deny" | "approve-with-instructions";

export type ConductorAuthorization = {
  requestId: string;
  decision: ConductorDecision;
  /** Extra instructions from the operator (e.g., "only fetch the DB URL"). */
  instructions?: string;
  /** Who approved (display name or channel id). */
  resolvedBy?: string;
  resolvedAtMs: number;
};

// ---------------------------------------------------------------------------
// Browser actions that Aether can perform
// ---------------------------------------------------------------------------

export type BrowserAction =
  | { type: "navigate"; url: string }
  | { type: "screenshot"; selector?: string }
  | { type: "extract-text"; selector?: string }
  | { type: "click"; selector: string }
  | { type: "type"; selector: string; text: string }
  | { type: "wait"; ms: number }
  | { type: "scrape"; url: string; selectors: Record<string, string> };

export type BrowserActionResult = {
  action: BrowserAction;
  success: boolean;
  data?: string;
  screenshotPath?: string;
  error?: string;
};

// ---------------------------------------------------------------------------
// Execution result injected back into Claude
// ---------------------------------------------------------------------------

export type ConductorInjection = {
  requestId: string;
  success: boolean;
  /** The data to inject into Claude's terminal. */
  payload: string;
  /** Individual action results. */
  actionResults?: BrowserActionResult[];
  /** Timestamp. */
  injectedAtMs: number;
};

// ---------------------------------------------------------------------------
// Conductor session state
// ---------------------------------------------------------------------------

export type ConductorSessionState = {
  /** The child process ID of the wrapped Claude instance. */
  childPid?: number;
  /** Currently pending requests awaiting authorization. */
  pending: Map<string, ExternalAccessRequest>;
  /** Completed requests (for audit trail). */
  history: ConductorHistoryEntry[];
  /** Whether the conductor is actively monitoring. */
  active: boolean;
  /** Session start time. */
  startedAtMs: number;
};

export type ConductorHistoryEntry = {
  request: ExternalAccessRequest;
  authorization?: ConductorAuthorization;
  injection?: ConductorInjection;
  completedAtMs: number;
};

// ---------------------------------------------------------------------------
// Analyzer interface (pluggable — Gemini, local LLM, regex, etc.)
// ---------------------------------------------------------------------------

export type AnalyzerResult = {
  /** Whether the output contains an external access request. */
  detected: boolean;
  /** The parsed request if detected. */
  request?: Omit<ExternalAccessRequest, "id" | "createdAtMs" | "expiresAtMs">;
  /** Confidence score 0-1. */
  confidence: number;
};

export type ConductorAnalyzer = {
  analyze(terminalOutput: string): Promise<AnalyzerResult>;
};

// ---------------------------------------------------------------------------
// Forwarder interface (sends auth requests to messaging channels)
// ---------------------------------------------------------------------------

export type ConductorForwarder = {
  /** Send an authorization request to the operator via messaging. */
  requestAuthorization(request: ExternalAccessRequest): Promise<void>;
  /** Notify the operator of the result. */
  notifyResult(request: ExternalAccessRequest, injection: ConductorInjection): Promise<void>;
  /** Listen for authorization responses. Returns a cleanup function. */
  onAuthorization(
    callback: (auth: ConductorAuthorization) => void,
  ): () => void;
  stop(): void;
};

// ---------------------------------------------------------------------------
// Executor interface (performs browser actions)
// ---------------------------------------------------------------------------

export type ConductorExecutor = {
  /** Execute a series of browser actions. */
  execute(
    request: ExternalAccessRequest,
    authorization: ConductorAuthorization,
  ): Promise<BrowserActionResult[]>;
};

// ---------------------------------------------------------------------------
// Events emitted by the conductor
// ---------------------------------------------------------------------------

export type ConductorEvent =
  | { type: "started"; pid?: number; ts: number }
  | { type: "output"; text: string; ts: number }
  | { type: "request-detected"; request: ExternalAccessRequest }
  | { type: "authorization-requested"; requestId: string }
  | { type: "authorization-received"; auth: ConductorAuthorization }
  | { type: "executing"; requestId: string }
  | { type: "injection"; injection: ConductorInjection }
  | { type: "error"; message: string; requestId?: string; ts: number }
  | { type: "stopped"; ts: number };

export type ConductorEventListener = (event: ConductorEvent) => void;
