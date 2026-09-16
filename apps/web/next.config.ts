import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  output: "standalone",
  transpilePackages: ["@argus/ui"],
  poweredByHeader: false,
  outputFileTracingRoot: path.join(__dirname, "../.."),
};

export default nextConfig;
