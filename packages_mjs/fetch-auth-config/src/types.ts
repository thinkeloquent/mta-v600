export enum AuthType {
    // Basic Family
    BASIC = "basic",
    BASIC_EMAIL_TOKEN = "basic_email_token",
    BASIC_TOKEN = "basic_token",
    BASIC_EMAIL = "basic_email",

    // Bearer Family
    BEARER = "bearer",
    BEARER_OAUTH = "bearer_oauth",
    BEARER_JWT = "bearer_jwt",
    BEARER_USERNAME_TOKEN = "bearer_username_token",
    BEARER_USERNAME_PASSWORD = "bearer_username_password",
    BEARER_EMAIL_TOKEN = "bearer_email_token",
    BEARER_EMAIL_PASSWORD = "bearer_email_password",

    // Custom
    CUSTOM = "custom",
    CUSTOM_HEADER = "custom_header",
    X_API_KEY = "x-api-key",

    // Misc
    HMAC = "hmac",
    NONE = "none",
}

export interface AuthConfig {
    type: AuthType;
    username?: string;
    password?: string;
    email?: string;
    token?: string;
    headerKey?: string;
    headerValue?: string;
}
