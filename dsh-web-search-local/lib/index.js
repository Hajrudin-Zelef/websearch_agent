/**
 * Local web search provider for DeepSeek Harness.
 * Calls a local FastAPI search backend (websearch_agent) that aggregates
 * 13+ search sources with intelligent routing.
 *
 * @module dsh-web-search-local
 */

/** Stable id this provider registers under. */
const LOCAL_PROVIDER_ID = "local-search";

/** Default endpoint: local websearch_agent server. */
const DEFAULT_BASE_URL = "http://127.0.0.1:4500";

/** Default maximum results per search. */
const DEFAULT_MAX_RESULTS = 10;

/** Attribution header. */
const USER_AGENT = "dsh-web-search-local/0.1.0";

/**
 * Map a local search API response to DSH's normalized WebSearchResult.
 */
function mapLocalResponse(data) {
    const sources = (data.sources ?? []).map((item) => ({
        url: item.url ?? "",
        ...(item.title && item.title.length > 0 ? { title: item.title } : {}),
        ...(item.snippet && item.snippet.length > 0 ? { snippet: item.snippet } : {}),
    }));

    return {
        sources,
        truncated: data.truncated ?? false,
    };
}

/**
 * The local search provider. Calls GET /search on the local FastAPI backend.
 */
class LocalSearchProvider {
    resolveOptions;
    id = LOCAL_PROVIDER_ID;

    constructor(resolveOptions) {
        this.resolveOptions = resolveOptions;
    }

    available() {
        const options = this.resolveOptions();
        return URL.canParse(options.baseURL);
    }

    async search(request, signal) {
        const options = this.resolveOptions();
        const endpoint = new URL("/search", options.baseURL);
        endpoint.searchParams.set("q", request.query);
        if (request.maxResults != null) {
            endpoint.searchParams.set("max_results", String(request.maxResults));
        }

        throwIfSearchAborted(signal);

        let response;
        try {
            response = await fetch(endpoint.href, {
                method: "GET",
                redirect: "error",
                headers: {
                    "accept": "application/json",
                    "user-agent": USER_AGENT,
                },
                ...signal !== void 0 ? { signal } : {},
            });
        } catch (error) {
            if (signal?.aborted === true || isAbortError(error)) throw searchAborted(signal, error);
            throw new Error(`Local search request failed: ${String(error)}`, { cause: error });
        }

        if (!response.ok) {
            let message = `Local search API error (HTTP ${response.status})`;
            try {
                const parsed = await response.json();
                const detail = parsed.detail ?? parsed.error ?? parsed.message;
                if (detail !== void 0 && String(detail).length > 0) message = String(detail);
            } catch (error) {
                if (signal?.aborted === true || isAbortError(error)) throw searchAborted(signal, error);
            }
            throw new Error(message);
        }

        try {
            return mapLocalResponse(await response.json());
        } catch (error) {
            if (signal?.aborted === true || isAbortError(error)) throw searchAborted(signal, error);
            throw new Error(`Local search returned an unprocessable response: ${String(error)}`, { cause: error });
        }
    }
}

// ── Helpers ──────────────────────────────────────────────────────────────

function throwIfSearchAborted(signal) {
    if (signal?.aborted === true) throw searchAborted(signal);
}

function searchAborted(signal, fallback) {
    return new Error("Local search aborted", {
        cause: signal?.aborted === true ? signal.reason : fallback,
    });
}

function isAbortError(error) {
    return error instanceof DOMException && error.name === "AbortError";
}

// ── Plugin registration ──────────────────────────────────────────────────

const name = "web-search-local";

const inject = ["web"];

function apply(ctx, config) {
    const baseURL = config?.baseURL ?? DEFAULT_BASE_URL;
    const maxResults = config?.maxResults ?? DEFAULT_MAX_RESULTS;

    ctx.web.registerSearchProvider(
        new LocalSearchProvider(() => ({ baseURL, maxResults }))
    );
}

export {
    LOCAL_PROVIDER_ID,
    DEFAULT_BASE_URL,
    DEFAULT_MAX_RESULTS,
    LocalSearchProvider,
    apply,
    inject,
    name,
};
