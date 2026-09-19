export function serializeRuntimeEnv(values) {
  return Object.entries(values).map(([key, value]) => {
    if (!/^[A-Z_][A-Z0-9_]*$/.test(key) || typeof value !== "string" || /[\r\n\0]/.test(value)) {
      throw new Error("Unsupported env value");
    }
    return `${key}='${value.replaceAll("'", "\\'")}'`;
  }).join("\n") + "\n";
}
