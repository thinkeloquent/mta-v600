import { AuthConfig, resolveAuthHeaders } from "@internal/fetch-auth-config";

export class HeaderConfig {
    private headers: Record<string, string>;

    constructor(initialHeaders: Record<string, string> = {}) {
        this.headers = { ...initialHeaders };
    }

    set(key: string, value: string): void {
        this.headers[key] = value;
    }

    get(key: string): string | undefined {
        return this.headers[key];
    }

    merge(other: Record<string, string>): void {
        this.headers = { ...this.headers, ...other };
    }

    setAuth(authConfig: AuthConfig): void {
        const authHeaders = resolveAuthHeaders(authConfig);
        this.merge(authHeaders);
    }

    toObject(): Record<string, string> {
        return { ...this.headers };
    }

    // Helper for compatibility with Fetch API Headers constructor
    toHeaders(): Headers {
        return new Headers(this.headers);
    }
}
