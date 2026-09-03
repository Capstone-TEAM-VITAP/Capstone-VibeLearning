import "temporal-polyfill/global";
import postgres from "@prisma/orm-postgres/runtime";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Read emitted contract JSON artifact
const contractJsonPath = path.resolve(__dirname, "../../prisma/contract.json");
const contractJson = JSON.parse(fs.readFileSync(contractJsonPath, "utf-8"));

export const db = postgres({
  contractJson,
  url: process.env.DATABASE_URL,
});

export default db;
