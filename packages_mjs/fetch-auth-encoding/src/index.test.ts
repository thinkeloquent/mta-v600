import { describe, it, expect } from "vitest";
import { encodeAuth, AuthCredentials } from "./index.js";

const b64 = (str: string) => Buffer.from(str).toString("base64");

describe("encodeAuth", () => {
    // --- Basic Family ---
    it("should handle basic (username:password)", () => {
        const h = encodeAuth("basic", { username: "u", password: "p" });
        expect(h).toEqual({ Authorization: `Basic ${b64("u:p")}` });
    });

    it("should handle basic_email_token", () => {
        const h = encodeAuth("basic_email_token", { email: "e", token: "t" });
        expect(h).toEqual({ Authorization: `Basic ${b64("e:t")}` });
    });

    it("should handle basic_token", () => {
        const h = encodeAuth("basic_token", { username: "u", token: "t" });
        expect(h).toEqual({ Authorization: `Basic ${b64("u:t")}` });
    });

    // --- Bearer Family ---
    it("should handle bearer", () => {
        const h = encodeAuth("bearer", { token: "raw_tok" });
        expect(h).toEqual({ Authorization: "Bearer raw_tok" });
    });

    it("should handle bearer_username_token", () => {
        const h = encodeAuth("bearer_username_token", { username: "u", token: "t" });
        expect(h).toEqual({ Authorization: `Bearer ${b64("u:t")}` });
    });

    // --- Custom ---
    it("should handle x-api-key", () => {
        const h = encodeAuth("x-api-key", { value: "key123" });
        expect(h).toEqual({ "X-API-Key": "key123" });
    });

    it("should throw on missing args", () => {
        expect(() => encodeAuth("basic", { username: "u" })).toThrow("requires");
    });
});
