import { Type } from "@sinclair/typebox";
import type { OpenClawConfig } from "../../config/config.js";
import { loadConfig } from "../../config/config.js";
import { stringEnum } from "../schema/typebox.js";
import { type AnyAgentTool, jsonResult, readNumberParam, readStringParam } from "./common.js";

const DEFAULT_TIMEOUT_MS = 10_000;

const HA_ACTIONS = [
  "list_entities",
  "get_state",
  "turn_on",
  "turn_off",
  "toggle",
  "set_light",
  "call_service",
] as const;

const HomeAssistantToolSchema = Type.Object({
  action: stringEnum(HA_ACTIONS, {
    description:
      "Action to perform: list_entities, get_state, turn_on, turn_off, toggle, set_light, or call_service.",
  }),
  entity_id: Type.Optional(
    Type.String({ description: 'Entity ID (e.g. "switch.office_lamp", "light.living_room").' }),
  ),
  domain: Type.Optional(
    Type.String({
      description:
        'Entity domain filter for list_entities (e.g. "light", "switch") or service domain for call_service.',
    }),
  ),
  service: Type.Optional(Type.String({ description: "Service name for call_service action." })),
  service_data: Type.Optional(
    Type.String({ description: "JSON string of additional service data for call_service." }),
  ),
  brightness: Type.Optional(
    Type.Number({ description: "Brightness level 0-255 for set_light.", minimum: 0, maximum: 255 }),
  ),
  rgb_color: Type.Optional(
    Type.String({ description: 'RGB color as "R,G,B" (e.g. "255,0,0") for set_light.' }),
  ),
  color_temp: Type.Optional(
    Type.Number({ description: "Color temperature in mireds for set_light." }),
  ),
});

function resolveHaConfig(config?: OpenClawConfig): {
  baseUrl: string;
  token: string;
  timeoutMs: number;
} | null {
  const cfg = config ?? loadConfig();
  const ha = cfg.tools?.homeAssistant;

  if (ha?.enabled === false) {
    return null;
  }

  const baseUrl = (ha?.baseUrl || process.env.HOME_ASSISTANT_URL || "").replace(/\/+$/, "");
  const token = ha?.token || process.env.HOME_ASSISTANT_TOKEN || "";

  if (!baseUrl || !token) {
    return null;
  }

  const timeoutSeconds = ha?.timeoutSeconds ?? 10;
  return { baseUrl, token, timeoutMs: timeoutSeconds * 1000 };
}

async function haFetch(
  baseUrl: string,
  token: string,
  method: string,
  path: string,
  body?: unknown,
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<unknown> {
  const url = `${baseUrl}${path}`;
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };

  const response = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(timeoutMs),
  });

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`Home Assistant API error ${response.status}: ${text || response.statusText}`);
  }

  return await response.json();
}

function extractDomain(entityId: string): string {
  const dot = entityId.indexOf(".");
  if (dot === -1) {
    throw new Error(`Invalid entity_id "${entityId}": expected format "domain.name"`);
  }
  return entityId.slice(0, dot);
}

function parseRgbColor(rgb: string): [number, number, number] {
  const parts = rgb.split(",").map((s) => Number.parseInt(s.trim(), 10));
  if (parts.length !== 3 || parts.some((n) => !Number.isFinite(n) || n < 0 || n > 255)) {
    throw new Error(`Invalid rgb_color "${rgb}": expected "R,G,B" with values 0-255`);
  }
  return parts as unknown as [number, number, number];
}

export function createHomeAssistantTool(opts?: { config?: OpenClawConfig }): AnyAgentTool | null {
  const haConfig = resolveHaConfig(opts?.config);
  if (!haConfig) {
    return null;
  }

  const { baseUrl, token, timeoutMs } = haConfig;

  return {
    label: "Home Assistant",
    name: "home_assistant",
    description:
      "Control smart home devices via Home Assistant. List entities, get states, turn on/off, toggle, set light colors/brightness, or call any service.",
    parameters: HomeAssistantToolSchema,
    execute: async (_toolCallId, args) => {
      const params = args as Record<string, unknown>;
      const action = readStringParam(params, "action", { required: true });

      if (action === "list_entities") {
        const domain = readStringParam(params, "domain");
        const states = (await haFetch(
          baseUrl,
          token,
          "GET",
          "/api/states",
          undefined,
          timeoutMs,
        )) as Array<{
          entity_id: string;
          state: string;
          attributes: Record<string, unknown>;
        }>;
        const filtered = domain
          ? states.filter((s) => s.entity_id.startsWith(`${domain}.`))
          : states;
        const summary = filtered.map((s) => ({
          entity_id: s.entity_id,
          state: s.state,
          friendly_name: s.attributes?.friendly_name ?? null,
        }));
        return jsonResult({ ok: true, count: summary.length, entities: summary });
      }

      if (action === "get_state") {
        const entityId = readStringParam(params, "entity_id", { required: true });
        const state = await haFetch(
          baseUrl,
          token,
          "GET",
          `/api/states/${encodeURIComponent(entityId)}`,
          undefined,
          timeoutMs,
        );
        return jsonResult({ ok: true, state });
      }

      if (action === "turn_on" || action === "turn_off" || action === "toggle") {
        const entityId = readStringParam(params, "entity_id", { required: true });
        const domain = extractDomain(entityId);
        const serviceName = action;
        const result = await haFetch(
          baseUrl,
          token,
          "POST",
          `/api/services/${encodeURIComponent(domain)}/${serviceName}`,
          { entity_id: entityId },
          timeoutMs,
        );
        return jsonResult({ ok: true, action, entity_id: entityId, result });
      }

      if (action === "set_light") {
        const entityId = readStringParam(params, "entity_id", { required: true });
        const brightness = readNumberParam(params, "brightness");
        const rgbColorStr = readStringParam(params, "rgb_color");
        const colorTemp = readNumberParam(params, "color_temp");

        const serviceData: Record<string, unknown> = { entity_id: entityId };
        if (brightness !== undefined) {
          serviceData.brightness = brightness;
        }
        if (rgbColorStr) {
          serviceData.rgb_color = parseRgbColor(rgbColorStr);
        }
        if (colorTemp !== undefined) {
          serviceData.color_temp = colorTemp;
        }

        const result = await haFetch(
          baseUrl,
          token,
          "POST",
          "/api/services/light/turn_on",
          serviceData,
          timeoutMs,
        );
        return jsonResult({ ok: true, action: "set_light", entity_id: entityId, result });
      }

      if (action === "call_service") {
        const domain = readStringParam(params, "domain", { required: true });
        const service = readStringParam(params, "service", { required: true });
        const entityId = readStringParam(params, "entity_id");
        const serviceDataStr = readStringParam(params, "service_data");

        let serviceData: Record<string, unknown> = {};
        if (serviceDataStr) {
          try {
            serviceData = JSON.parse(serviceDataStr) as Record<string, unknown>;
          } catch {
            throw new Error(`Invalid service_data JSON: ${serviceDataStr}`);
          }
        }
        if (entityId) {
          serviceData.entity_id = entityId;
        }

        const result = await haFetch(
          baseUrl,
          token,
          "POST",
          `/api/services/${encodeURIComponent(domain)}/${encodeURIComponent(service)}`,
          serviceData,
          timeoutMs,
        );
        return jsonResult({ ok: true, domain, service, result });
      }

      throw new Error(`Unknown action: ${action}`);
    },
  };
}
