import { describe, expect, it } from "vitest";
import { createAnalyzer } from "./analyzer.js";

describe("conductor analyzer (regex)", () => {
  const analyzer = createAnalyzer({ provider: "regex" });

  it("detects URL visit requests", async () => {
    const result = await analyzer.analyze(
      "I need you to go to https://railway.app/dashboard to get the database credentials.",
    );
    expect(result.detected).toBe(true);
    expect(result.request?.kind).toBe("url-visit");
    expect(result.request?.url).toBe("https://railway.app/dashboard");
    expect(result.confidence).toBeGreaterThan(0);
  });

  it("detects credential fetch requests", async () => {
    const result = await analyzer.analyze(
      "I need the API_KEY from Vercel to continue with the deployment.",
    );
    expect(result.detected).toBe(true);
    expect(result.request?.kind).toBe("credential-fetch");
    expect(result.request?.service).toBe("Vercel");
  });

  it("detects service dashboard requests", async () => {
    const result = await analyzer.analyze(
      "Please open the Railway dashboard and find the database URL.",
    );
    expect(result.detected).toBe(true);
    expect(result.request?.kind).toBe("service-action");
  });

  it("detects API check requests", async () => {
    const result = await analyzer.analyze(
      "Can you check the API endpoint at https://api.example.com/v2/health to see if it's responding?",
    );
    expect(result.detected).toBe(true);
    expect(result.request?.kind).toBe("api-check");
    expect(result.request?.url).toBe("https://api.example.com/v2/health");
  });

  it("detects verification requests", async () => {
    const result = await analyzer.analyze(
      "Please verify the deployment at https://my-app.vercel.app is working correctly.",
    );
    expect(result.detected).toBe(true);
    expect(result.request?.kind).toBe("verification");
  });

  it("returns not detected for normal terminal output", async () => {
    const result = await analyzer.analyze(
      "Compiling TypeScript...\nBuild succeeded in 2.3s\n42 modules compiled.",
    );
    expect(result.detected).toBe(false);
    expect(result.confidence).toBe(0);
  });

  it("returns not detected for code output", async () => {
    const result = await analyzer.analyze(
      'const url = "https://example.com";\nconsole.log(url);',
    );
    expect(result.detected).toBe(false);
  });

  it("strips ANSI codes before analysis", async () => {
    const result = await analyzer.analyze(
      "\x1B[32mPlease go to https://github.com/settings to check the token.\x1B[0m",
    );
    expect(result.detected).toBe(true);
    expect(result.request?.url).toBe("https://github.com/settings");
  });

  it("detects file download requests", async () => {
    const result = await analyzer.analyze(
      "I need to download the file from https://releases.example.com/v2/binary.tar.gz",
    );
    expect(result.detected).toBe(true);
    expect(result.request?.kind).toBe("file-download");
  });

  it("suggests appropriate browser actions", async () => {
    const result = await analyzer.analyze(
      "Go to https://railway.app/project/settings and grab the DATABASE_URL.",
    );
    expect(result.detected).toBe(true);
    expect(result.request?.suggestedActions).toBeDefined();
    expect(result.request?.suggestedActions?.length).toBeGreaterThan(0);
    expect(result.request?.suggestedActions?.[0]?.type).toBe("navigate");
  });
});
