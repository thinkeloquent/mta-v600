import { AuthConfig, AuthType } from "../types.js";
import { encodeAuth, AuthCredentials } from "@internal/fetch-auth-encoding";

type Headers = Record<string, string>;

export interface AuthStrategy {
    getHeaders(config: AuthConfig): Headers;
}

// We can now use a generic strategy since encodeAuth handles the logic
export const genericAuthStrategy: AuthStrategy = {
    getHeaders(config: AuthConfig): Headers {
        const creds: AuthCredentials = {
            username: config.username,
            password: config.password,
            email: config.email,
            token: config.token,
            headerKey: config.headerKey,
            headerValue: config.headerValue,
            value: config.headerValue, // Aliasing for x-api-key potentially
            key: config.headerValue // Aliasing
        };
        return encodeAuth(config.type, creds);
    }
}

export function resolveAuthHeaders(config: AuthConfig): Headers {
    return genericAuthStrategy.getHeaders(config);
}
