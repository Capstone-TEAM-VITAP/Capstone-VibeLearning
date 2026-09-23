# CodeAI

> AI-powered coding learning platform that connects GitHub repositories with personalized code analysis, learning paths, and developer insights.

---

## Overview

CodeAI is an interactive coding and learning workspace designed to accelerate developer learning. It connects directly with GitHub repositories, analyzes codebases, generates personalized learning paths, and provides intelligent developer insights to master full-stack software development.

---

## Tech Stack

- **Monorepo**: [pnpm](https://pnpm.io/) workspaces
- **Frontend**: [React 19](https://react.dev/), [Vite](https://vitejs.dev/), [@clerk/react](https://clerk.com/), Vanilla CSS
- **Backend**: [Node.js](https://nodejs.org/) (v24), [Express 5](https://expressjs.com/) (ESM), [@clerk/express](https://clerk.com/), [Zod](https://zod.dev/)
- **Database**: [Supabase PostgreSQL](https://supabase.com/)
- **ORM & Data Layer**: [Prisma 8 RC](https://www.prisma.io/) Contract Workflow (`@prisma/orm-postgres`)

---

## Quickstart

### One-click start (Windows)

```powershell
.\run.ps1
```

Checks tools, installs deps, ensures `.env` files, regenerates the Prisma
contract, runs backend tests, starts backend + frontend in their own windows,
then prints all server and endpoint links. Use `.\run.ps1 -SkipInstall` to
skip `pnpm install`. Stop with Ctrl+C in each server window.

### Manual start

### 1. Install Dependencies

```bash
pnpm install
```

### 2. Environment Configuration

Copy `.env.example` to `.env` in the appropriate app directories:

```bash
# apps/backend/.env
PORT=5000
DATABASE_URL=postgresql://...
CLERK_SECRET_KEY=sk_test_...
CLERK_PUBLISHABLE_KEY=pk_test_...
CORS_ORIGINS=http://localhost:5173

# apps/frontend/.env
VITE_API_URL=http://localhost:5000/api/v1
VITE_CLERK_PUBLISHABLE_KEY=pk_test_...
```

### 3. Run Development Servers

**Option A: Single Terminal (All services together)**
```bash
pnpm dev
```
Runs AI Service (port 8000), Backend (port 5000), and Frontend (port 5173) concurrently in a single terminal with colored logs.

**Option B: One-Click Window Launcher**
```powershell
.\run.ps1
```


---

## Documentation

- [Architecture Guide](docs/architecture.md): System layout, technology stack, and layered request flow.
- [API Contract](docs/api-contract.md): Complete HTTP API specification for all `/api/v1` endpoints.
