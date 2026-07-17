import path from "node:path";
import { ROLE_DESCRIPTIONS } from "./project-context";
import { defaultHfRoot } from "./provider-status";

type RankedRole = {
  slug: string;
  score: number;
};

let extractorPromise: Promise<any> | undefined;

async function getExtractor(): Promise<any> {
  if (!extractorPromise) {
    extractorPromise = (async () => {
      const { env, pipeline } = await import("@huggingface/transformers");
      env.allowRemoteModels = process.env.HF_ALLOW_REMOTE_MODELS === "true";
      env.localModelPath = defaultHfRoot();
      env.cacheDir =
        process.env.HF_CACHE_DIR ?? path.join(defaultHfRoot(), ".cache");

      const model =
        process.env.HF_EMBEDDING_MODEL ??
        "mixedbread-ai/mxbai-embed-xsmall-v1";

      return pipeline("feature-extraction", model);
    })();
  }
  return extractorPromise;
}

function dot(a: number[], b: number[]): number {
  let value = 0;
  const size = Math.min(a.length, b.length);
  for (let i = 0; i < size; i += 1) value += a[i] * b[i];
  return value;
}

export async function rankRolesLocally(
  query: string,
  limit = 3,
): Promise<RankedRole[] | null> {
  if (process.env.HF_LOCAL_ROUTER_ENABLED === "false") return null;

  try {
    const extractor = await getExtractor();
    const texts = [
      query,
      ...ROLE_DESCRIPTIONS.map(
        (role) => `${role.slug}: ${role.description}`,
      ),
    ];
    const tensor = await extractor(texts, {
      pooling: "mean",
      normalize: true,
    });
    const vectors = tensor.tolist() as number[][];
    const queryVector = vectors[0];

    return ROLE_DESCRIPTIONS.map((role, index) => ({
      slug: role.slug,
      score: dot(queryVector, vectors[index + 1]),
    }))
      .sort((a, b) => b.score - a.score)
      .slice(0, limit);
  } catch (error) {
    console.warn(
      "Hugging Face local semantic router unavailable; using deterministic fallback.",
      error instanceof Error ? error.message : error,
    );
    return null;
  }
}

export function rankRolesByKeywords(query: string, limit = 3): RankedRole[] {
  const q = query.toLowerCase();
  const score: Record<string, number> = {
    planner: 4,
    validator: 4,
    synthesizer: 3,
    researcher: 0,
    analyst: 0,
    coder: 0,
    creative: 0,
    memory: 0,
  };

  if (/(code|api|typescript|react|debug|build|integrat|database)/.test(q)) {
    score.coder += 10;
  }
  if (/(research|search|source|paper|guide|documentation)/.test(q)) {
    score.researcher += 10;
  }
  if (/(analy|compare|risk|metric|cost|score|architecture)/.test(q)) {
    score.analyst += 9;
  }
  if (/(design|visual|canva|creative|brand)/.test(q)) {
    score.creative += 7;
  }
  if (/(history|memory|previous|context|canonical)/.test(q)) {
    score.memory += 7;
  }

  return Object.entries(score)
    .map(([slug, value]) => ({ slug, score: value }))
    .sort((a, b) => b.score - a.score)
    .slice(0, limit);
}
