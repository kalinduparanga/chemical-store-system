/**
 * Next.js configuration compatible with Vercel.
 */
import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // Enable React Strict Mode for development
  reactStrictMode: true,
  // Use the default output directory ('.next') – Vercel will detect automatically
  // No custom server needed
  // Allow image domains if needed later
  images: {
    domains: [],
  },
  // Experimental app directory support (enabled by default in Next 13+)
  experimental: {
    appDir: true,
  },
};

export default nextConfig;
