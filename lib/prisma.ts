// lib/prisma.ts
import { PrismaClient } from "@prisma/client";

let prisma: PrismaClient;

if (process.env.NODE_ENV === "production") {
  // In production (Vercel), reuse the client across hot reloads.
  if (!(global as any).prisma) {
    (global as any).prisma = new PrismaClient();
  }
  prisma = (global as any).prisma;
} else {
  // In development, create a new client per request.
  prisma = new PrismaClient();
}

export default prisma;
