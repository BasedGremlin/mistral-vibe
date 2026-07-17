import OpenAI from "openai";

export type ClaudeCriticResult = {
  configured: boolean;
  critique?: string;
  model: string;
  latencyMs?: number;
  error?: string;
};

export async function runClaudeCritic(
  query: string,
  candidateOutput: string,
): Promise<ClaudeCriticResult> {
  const model = process.env.CLAUDE_MODEL ?? "claude-sonnet-4-6";
  const apiKey = process.env.ANTHROPIC_API_KEY;

  if (!apiKey) {
    return {
      configured: false,
      model,
      error:
        "ANTHROPIC_API_KEY is not configured. Claude route remains installed but inactive.",
    };
  }

  const startedAt = Date.now();
  try {
    // Anthropic's official OpenAI SDK compatibility endpoint.
    // This is intentionally a secondary critic path, not the production orchestrator.
    const client = new OpenAI({
      apiKey,
      baseURL: "https://api.anthropic.com/v1/",
    });

    const response = await client.chat.completions.create({
      model,
      max_tokens: 1400,
      messages: [
        {
          role: "system",
          content:
            "You are a hostile but fair engineering reviewer. Return only actionable defects, unsupported claims, missing tests, unsafe assumptions, and a concise accept/revise verdict. Do not reveal hidden reasoning.",
        },
        {
          role: "user",
          content: [
            "ORIGINAL REQUEST:",
            query,
            "",
            "CANDIDATE SWARM OUTPUT:",
            candidateOutput,
          ].join("\n"),
        },
      ],
    });

    return {
      configured: true,
      model,
      latencyMs: Date.now() - startedAt,
      critique:
        response.choices[0]?.message?.content?.trim() ||
        "Claude critic returned no text.",
    };
  } catch (error) {
    return {
      configured: true,
      model,
      latencyMs: Date.now() - startedAt,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}
