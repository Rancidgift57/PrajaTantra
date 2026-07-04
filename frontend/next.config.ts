import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // reactStrictMode: true causes React to mount→unmount→remount every component
  // in development. On remount, React tries to remove DOM nodes that browser
  // extensions (Google Translate, Grammarly, etc.) mutated during the first
  // mount — triggering: "Failed to execute 'removeChild' on 'Node'".
  //
  // Disabling strict mode stops the double-invoke in dev.
  // This does NOT affect production builds (strict mode only runs in dev).
  // Re-enable when targeting Next.js 17+ or React 19 stable with the fix.
  reactStrictMode: false,
};

export default nextConfig;