declare module "@openai/agents" {
  export class Agent {
    constructor(config: Record<string, unknown>);
  }
  export function run(agent: Agent, input: string): Promise<{ finalOutput?: unknown }>;
  export function tool(config: {
    name: string;
    description: string;
    parameters: unknown;
    execute: (input: any) => unknown | Promise<unknown>;
  }): unknown;
}

declare module "openai" {
  export default class OpenAI {
    constructor(config: { apiKey: string; baseURL?: string });
    chat: {
      completions: {
        create(input: Record<string, unknown>): Promise<{
          choices: Array<{ message: { content?: string | null } }>;
        }>;
      };
    };
  }
}

declare module "@supabase/supabase-js" {
  export function createClient(url: string, key: string, options?: Record<string, unknown>): any;
}

declare module "@huggingface/transformers" {
  export const env: {
    allowRemoteModels: boolean;
    localModelPath: string;
    cacheDir: string;
  };
  export function pipeline(task: string, model: string, options?: Record<string, unknown>): Promise<any>;
}
