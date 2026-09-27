import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  poweredByHeader: false,
  experimental: {
    // Keep static-export workers bounded on small CI/developer machines.
    cpus: 2,
  },
};

export default nextConfig;
