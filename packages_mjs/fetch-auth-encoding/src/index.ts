export interface AuthCredentials {
  username?: string;
  password?: string;
  email?: string;
  token?: string;
  headerKey?: string;
  headerValue?: string;
  value?: string;
  key?: string;
}

function b64(str: string): string {
  return Buffer.from(str).toString("base64");
}

export function encodeAuth(authType: string, creds: AuthCredentials): Record<string, string> {
  const type = authType.toLowerCase();

  // Basic Family
  if (type === "basic") {
    const user = creds.username || creds.email;
    const pass = creds.password || creds.token;
    if (!user || !pass) throw new Error("Basic auth requires username/email and password/token");
    return { Authorization: `Basic ${b64(`${user}:${pass}`)}` };
  }

  if (type === "basic_email_token") {
    if (!creds.email || !creds.token) throw new Error("basic_email_token requires email and token");
    return { Authorization: `Basic ${b64(`${creds.email}:${creds.token}`)}` };
  }

  if (type === "basic_token") {
    if (!creds.username || !creds.token) throw new Error("basic_token requires username and token");
    return { Authorization: `Basic ${b64(`${creds.username}:${creds.token}`)}` };
  }

  if (type === "basic_email") {
    if (!creds.email || !creds.password) throw new Error("basic_email requires email and password");
    return { Authorization: `Basic ${b64(`${creds.email}:${creds.password}`)}` };
  }

  // Bearer Family
  if (["bearer", "bearer_oauth", "bearer_jwt"].includes(type)) {
    const val = creds.token || creds.password;
    if (!val) throw new Error(`${type} requires token`);
    return { Authorization: `Bearer ${val}` };
  }

  if (type === "bearer_username_token") {
    if (!creds.username || !creds.token) throw new Error("bearer_username_token requires username and token");
    return { Authorization: `Bearer ${b64(`${creds.username}:${creds.token}`)}` };
  }

  if (type === "bearer_username_password") {
    if (!creds.username || !creds.password) throw new Error("bearer_username_password requires username and password");
    return { Authorization: `Bearer ${b64(`${creds.username}:${creds.password}`)}` };
  }

  if (type === "bearer_email_token") {
    if (!creds.email || !creds.token) throw new Error("bearer_email_token requires email and token");
    return { Authorization: `Bearer ${b64(`${creds.email}:${creds.token}`)}` };
  }

  if (type === "bearer_email_password") {
    if (!creds.email || !creds.password) throw new Error("bearer_email_password requires email and password");
    return { Authorization: `Bearer ${b64(`${creds.email}:${creds.password}`)}` };
  }

  // Custom
  if (type === "x-api-key") {
    const val = creds.token || creds.value || creds.key;
    if (!val) throw new Error("x-api-key requires token/value");
    return { "X-API-Key": val };
  }

  if (["custom", "custom_header"].includes(type)) {
    const key = creds.headerKey;
    const val = creds.headerValue || creds.value;
    if (!key) throw new Error(`${type} requires headerKey`);
    return { [key]: val || "" };
  }

  if (type === "none") {
    return {};
  }

  throw new Error(`Unsupported auth type: ${authType}`);
}
