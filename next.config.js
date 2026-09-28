// next.config.js
/**
 * Next.js configuration compatible with Vercel.
 * This file replaces the TypeScript version (next.config.ts) which Vercel does not support.
 */
/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable React Strict Mode for development
  reactStrictMode: true,
  // Allow image domains if needed later
  images: {
    domains: [],
  },
  // Experimental app directory support (enabled by default in Next 13+)
  experimental: {
    appDir: true,
  },
};

module.exports = nextConfig;
