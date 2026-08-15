/**
 * Local web search provider for DeepSeek Harness.
 * Calls a local FastAPI search backend (websearch_agent) that aggregates
 * 13+ search sources with intelligent routing.
 *
 * @module dsh-web-search-local
 */
import type { Context } from "@deepseek-ai/cordis";
import z from "@deepseek-ai/schemastery";
import type {
    WebSearchProvider,
    WebSearchRequest,
    WebSearchResult,
} from "@deepseek-ai/dsh-web";

/** Stable id this provider registers under. */
export declare const LOCAL_PROVIDER_ID = "local-search";

/** Default endpoint: local websearch_agent server. */
export declare const DEFAULT_BASE_URL = "http://127.0.0.1:4500";

/** Default maximum results per search. */
export declare const DEFAULT_MAX_RESULTS = 10;

/** Plugin config. */
export interface Config {
    /** Base URL of the local websearch_agent server. */
    baseURL?: string;
    /** Maximum results per search. */
    maxResults?: number;
}

export declare const Config: z.ZodObject<{
    baseURL: z.ZodDefault<z.ZodString>;
    maxResults: z.ZodDefault<z.ZodNumber>;
}>;

/** Resolved provider options. */
export interface LocalSearchProviderOptions {
    baseURL: string;
    maxResults: number;
}

/** The local search provider. */
export declare class LocalSearchProvider implements WebSearchProvider {
    private readonly resolveOptions;
    readonly id: string;
    constructor(resolveOptions: () => LocalSearchProviderOptions);
    available(): boolean;
    search(request: WebSearchRequest, signal?: AbortSignal): Promise<WebSearchResult>;
}

/** Cordis plugin name. */
export declare const name = "web-search-local";

/** The web seam this provider registers into. */
export declare const inject: string[];

/** Register the local search provider with `ctx.web`. */
export declare function apply(ctx: Context, config: Config): void;
