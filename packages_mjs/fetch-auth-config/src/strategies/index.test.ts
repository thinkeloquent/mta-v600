import { describe, it, expect } from "vitest";
import { AuthType, AuthConfig } from "../types.js";
import { resolveAuthHeaders } from "./index.js";

describe("resolveAuthHeaders Integration", () => {
    it("should handle basic auth", () => {
        const config: AuthConfig = {
            type: AuthType.BASIC,
            username: "user",
            password: "password123",
        };
        const headers = resolveAuthHeaders(config);
        const expected = Buffer.from("user:password123").toString("base64");
        expect(headers).toEqual({ Authorization: `Basic ${expected}` });
    });

    it("should handle basic_email_token", () => {
        const config: AuthConfig = {
            type: AuthType.BASIC_EMAIL_TOKEN,
            email: "e",
            token: "t"
        };
        const headers = resolveAuthHeaders(config);
        const expected = Buffer.from("e:t").toString("base64");
        expect(headers).toEqual({ Authorization: `Basic ${expected}` });
    });

    it("should handle bearer auth", () => {
        const config: AuthConfig = {
            type: AuthType.BEARER,
            token: "sometoken",
        };
        const headers = resolveAuthHeaders(config);
        expect(headers).toEqual({ Authorization: "Bearer sometoken" });
    });

    it("should handle custom auth", () => {
        const config: AuthConfig = {
            type: AuthType.CUSTOM_HEADER,
            headerKey: "X-API-Key",
            headerValue: "key123",
        };
        const headers = resolveAuthHeaders(config);
        expect(headers).toEqual({ "X-API-Key": "key123" });
    });
});
