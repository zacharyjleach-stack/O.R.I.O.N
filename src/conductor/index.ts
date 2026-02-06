/**
 * Aether Conductor — Module Index
 *
 * The conductor provides a closed-loop system for AI agent external access:
 *   Worker (Claude) → Analyzer (Gemini) → Forwarder (Messaging) → Executor (Browser) → Injector
 */

export { Conductor, type ConductorOptions } from "./conductor.js";
export { TerminalInterceptor, generateRequestId } from "./interceptor.js";
export { createAnalyzer } from "./analyzer.js";
export { createConductorForwarder, createGatewayForwarder } from "./forwarder.js";
export { createBrowserExecutor } from "./browser-executor.js";
export {
  formatInjectionPayload,
  injectResults,
  injectDenial,
  injectTimeout,
} from "./injector.js";
export type {
  ExternalAccessKind,
  ExternalAccessRequest,
  ConductorDecision,
  ConductorAuthorization,
  BrowserAction,
  BrowserActionResult,
  ConductorInjection,
  ConductorSessionState,
  ConductorHistoryEntry,
  AnalyzerResult,
  ConductorAnalyzer,
  ConductorForwarder,
  ConductorExecutor,
  ConductorEvent,
  ConductorEventListener,
} from "./types.js";
