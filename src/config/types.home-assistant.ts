export type HomeAssistantConfig = {
  /** Enable Home Assistant tool (default: true when baseUrl + token are present). */
  enabled?: boolean;
  /** Home Assistant base URL (e.g. "http://homeassistant.local:8123"). */
  baseUrl?: string;
  /** Long-lived access token for Home Assistant API. */
  token?: string;
  /** Timeout in seconds for API requests (default: 10). */
  timeoutSeconds?: number;
};
