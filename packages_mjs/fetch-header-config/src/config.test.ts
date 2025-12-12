import { describe, it, expect } from "vitest";
import { HeaderConfig } from "./config.js";
import { AuthType } from "@internal/fetch-auth-config";

describe("HeaderConfig", () => {
    it("should initialize with headers", () => {
        const config = new HeaderConfig({ "Content-Type": "application/json" });
        expect(config.toObject()).toEqual({ "Content-Type": "application/json" });
    });

    it("should set and get headers", () => {
        const config = new HeaderConfig();
        config.set("X-Custom", "value");
        expect(config.get("X-Custom")).toBe("value");
    });

    it("should merge headers", () => {
        const config = new HeaderConfig({ A: "1" });
        config.merge({ B: "2", C: "3" });
        expect(config.toObject()).toEqual({ A: "1", B: "2", C: "3" });
    });

    it("should set auth headers", () => {
        const config = new HeaderConfig();
        config.setAuth({
            type: AuthType.BASIC,
            username: "user",
            password: "password",
        });

        const headers = config.toObject();
        expect(headers).toHaveProperty("Authorization");
        expect(headers.Authorization).toMatch(/^Basic /);
    });
});
