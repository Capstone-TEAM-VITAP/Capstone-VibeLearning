# CodeAI Architecture

This document describes the current architecture and technical design of CodeAI.

---

## Project Structure

CodeAI is structured as a **pnpm monorepo** with dedicated workspaces for frontend and backend applications, configuration, and database contracts:

```text
Capstone-VibeLearning/
├── apps/
│   ├── backend/
│   │   ├── migrations/             # Prisma 8 contract snapshot ledgers & refs
│   │   ├── prisma/
│   │   │   ├── contract.prisma     # PSL database contract definition
│   │   │   ├── contract.json       # Emitted Contract IR artifact
│   │   │   └── contract.d.ts       # Emitted contract TypeScript declarations
│   │   ├── src/
│   │   │   ├── config/
│   │   │   │   └── db.js           # Database client instance & Temporal polyfill
│   │   │   ├── controllers/
│   │   │   │   └── project.controller.js
│   │   │   ├── middleware/
│   │   │   │   ├── auth.middleware.js
│   │   │   │   ├── error.middleware.js
│   │   │   │   └── validate.middleware.js
│   │   │   ├── repositories/
│   │   │   │   ├── project.repository.js
│   │   │   │   └── user.repository.js
│   │   │   ├── routes/
│   │   │   │   ├── auth.routes.js
│   │   │   │   └── project.routes.js
│   │   │   ├── services/
│   │   │   │   └── project.service.js
│   │   │   ├── utils/
│   │   │   │   ├── errors.js       # Standard operational HTTP errors
│   │   │   │   └── response.js     # Standardized API response formatters
│   │   │   ├── validators/
│   │   │   │   └── project.validator.js
│   │   │   └── app.js              # Express application setup & middleware chain
│   │   ├── index.js                # Server entry point
│   │   ├── package.json
│   │   └── prisma.config.ts        # Prisma 8 CLI configuration
│   └── frontend/
│       ├── src/
│       │   ├── pages/
│       │   │   └── Dashboard.jsx   # Authenticated user dashboard
│       │   ├── services/
│       │   │   └── api.js          # API client with Clerk token injection
│       │   ├── App.jsx             # Shell with Clerk UserButton & auth state views
│       │   ├── App.css
│       │   ├── index.css
│       │   └── main.jsx            # React root with ClerkProvider
│       ├── index.html
│       ├── package.json
│       └── vite.config.js
├── docs/
│   ├── api-contract.md
│   └── architecture.md
├── package.json                    # Root monorepo workspace metadata
├── pnpm-workspace.yaml             # pnpm workspace definition (apps/*)
├── pnpm-lock.yaml
└── .gitignore
```

---

## Technology Stack

The project runs on the following technologies:

- **Monorepo & Package Manager**: [pnpm](https://pnpm.io/) workspace (v11) managing dependency caching and package execution across workspaces.
- **Frontend**:
  - **Framework**: React 19 (pure JavaScript / JSX, no TypeScript).
  - **Bundler**: Vite 8.
  - **Styling**: Vanilla CSS with custom properties (`--bg`, `--border`, `--accent`) implementing dark/light design tokens.
  - **Authentication SDK**: `@clerk/react` (providing `ClerkProvider`, `useAuth`, `UserButton`, `SignInButton`, `SignUpButton`, `Show`).
- **Backend**:
  - **Runtime**: Node.js (v24).
  - **Framework**: Express 5 (pure JavaScript ESM, `"type": "module"`).
  - **Authentication SDK**: `@clerk/express` (providing `clerkMiddleware` and `getAuth`).
  - **Validation**: [Zod](https://zod.dev/) (`^4.5.4`).
- **Database & Data Layer**:
  - **Database Engine**: PostgreSQL on Supabase (accessed via Supabase Session Pooler).
  - **Data Layer & Tooling**: [Prisma 8 RC](https://www.prisma.io/) Contract Workflow using `@prisma/orm-postgres` (`8.0.0-rc.8`), with `temporal-polyfill` handling losslessly decoded `DateTime` timestamps (`Temporal.Instant`).

---

## Request Flow

All incoming API requests pass through a strictly layered backend pipeline:

```text
Client (Browser / Postman)
    │
    ▼
Express Application (`src/app.js`)
    │  ├─ CORS Middleware (`cors`)
    │  ├─ Body Parser (`express.json()`)
    │  └─ Clerk Middleware (`clerkMiddleware()`)
    │
    ▼
Router (`/api/v1/projects`, `/api/v1/auth`)
    │
    ▼
Authentication Middleware (`requireAuth`)
    │  └─ Rejects unauthenticated requests with HTTP 401
    │  └─ Extracts and attaches `req.userId` (Clerk User ID)
    │
    ▼
Request Validator (`validate(schema)`)
    │  └─ Validates `body`, `params`, `query` via Zod
    │  └─ Rejects invalid data with HTTP 400
    │
    ▼
Controller (`project.controller.js`)
    │  └─ Thin layer: unpacks `req.userId`, `req.params`, `req.body`
    │  └─ Delegates directly to Service
    │
    ▼
Service (`project.service.js`)
    │  ├─ Resolves application `User` UUID from Clerk User ID
    │  ├─ Enforces resource existence and ownership verification
    │  └─ Throws operational errors (e.g. `NotFoundError` 404)
    │
    ▼
Repository (`project.repository.js`, `user.repository.js`)
    │  └─ Performs scoped database queries (`db.orm.public.*`)
    │
    ▼
Database (Supabase PostgreSQL via Prisma 8 ORM)
```

If an error is thrown at any point along the pipeline, execution forwards to the centralized **Error Handling Middleware** (`errorHandler`) at the end of the Express middleware stack.

---

## Authentication

Authentication is fully managed through **Clerk**:

1. **Client-Side Session**:
   - The user signs in via Clerk's modal or component (`SignInButton`).
   - The React frontend acquires a short-lived session token via Clerk's `useAuth().getToken()` hook.
   - All authenticated fetch requests send this token in the HTTP header:
     ```http
     Authorization: Bearer <session-token>
     ```

2. **Server-Side Token Verification**:
   - `clerkMiddleware()` from `@clerk/express` intercepts the request and cryptographically verifies the bearer token against Clerk's public keys.
   - Protected routes pass through `requireAuth` (`src/middleware/auth.middleware.js`), which reads:
     ```javascript
     const { userId } = getAuth(req);
     ```
   - If `userId` is absent, the middleware halts the request immediately with HTTP 401 `{ "success": false, "message": "Unauthorized" }`.
   - If valid, `req.userId = userId` is set for downstream handlers.

3. **Application User Resolution**:
   - Clerk generates external user IDs formatted like `user_2tN...`.
   - The backend never assumes an application user row already exists.
   - In `project.service.js`, `_resolveUser(clerkUserId)` calls `userRepository.findOrCreateByClerkId(clerkUserId)`:
     - Checks `db.orm.public.User.where({ clerkUserId }).first()`.
     - If not found (first API call by a new user), it automatically creates a corresponding record in `public.user`.
     - Returns the database record, yielding the internal UUID `user.id`.

4. **Resource Scoping**:
   - Projects in the database carry a foreign key `userId` referencing `public.user(id)`.
   - Every database query in `project.repository.js` filters explicitly by `userId: user.id`.
   - A user cannot read, update, or delete any project belonging to another user.

---

## Database

The database contract is authored in `apps/backend/prisma/contract.prisma`:

```prisma
types {
  Uuid = Uuid
}

model User {
  id          Uuid     @id @default(uuid())
  clerkUserId String   @unique
  email       String?
  name        String?
  createdAt   DateTime @default(now())
  updatedAt   DateTime @default(now())

  projects Project[]

  @@map("user")
}

model Project {
  id          Uuid     @id @default(uuid())
  name        String
  description String?
  userId      Uuid

  user User @relation(fields: [userId], references: [id])

  createdAt DateTime @default(now())
  updatedAt DateTime @default(now())

  @@index([userId])
  @@map("project")
}
```

### Key Schema Characteristics:
- **`User` Table (`user`)**:
  - `id`: Primary key (UUID v4).
  - `clerkUserId`: Unique string storing Clerk's external subject ID (`user_...`).
  - `email`, `name`: Optional metadata fields.
  - `createdAt`, `updatedAt`: Timestamps with `@default(now())`.
  - `projects`: One-to-many relation to `Project`.
- **`Project` Table (`project`)**:
  - `id`: Primary key (UUID v4).
  - `name`: String, project title.
  - `description`: Optional text.
  - `userId`: Foreign key pointing to `User.id`.
  - `@@index([userId])`: Index on the foreign key column to optimize user-scoped list queries.
  - `createdAt`, `updatedAt`: Timestamps with `@default(now())`.

---

## Error Handling

Centralized error handling is implemented in `apps/backend/src/middleware/error.middleware.js`:

1. **Zod Validation Errors (`ZodError`)**:
   - Intercepts validation failures and formats a user-friendly message:
     ```json
     {
       "success": false,
       "message": "name: Project name must not be empty"
     }
     ```
   - Responds with HTTP status **400 Bad Request**.

2. **Operational Application Errors (`AppError`)**:
   - Subclasses in `src/utils/errors.js`:
     - `BadRequestError` (400)
     - `UnauthorizedError` (401)
     - `ForbiddenError` (403)
     - `NotFoundError` (404)
     - `ConflictError` (409)
   - Returns the corresponding HTTP status code and clean error message.

3. **Unexpected Internal Errors**:
   - In production (`NODE_ENV === 'production'`), logs an error timestamp and message to standard error without leaking internal file paths, secrets, or database errors.
   - Responds with HTTP status **500** and a generic message:
     ```json
     {
       "success": false,
       "message": "Internal server error"
     }
     ```
   - In non-production environments, outputs the full error stack to the server terminal.

4. **404 Not Found Catch-All**:
   - Unmatched routes are handled by `notFoundHandler`:
     ```json
     {
       "success": false,
       "message": "Cannot GET /api/v1/unknown-path"
     }
     ```

---

## Validation

Validation is built using **Zod** (`apps/backend/src/validators/project.validator.js`) and applied via `validate(schemas)` (`src/middleware/validate.middleware.js`):

- **Route Parameter Validation (`projectIdParamSchema`)**:
  - Validates `req.params.id` as a valid UUID format before hitting the controller or database.
- **Create Payload Validation (`createProjectSchema`)**:
  - `name`: Required string, trimmed, non-empty, maximum 255 characters.
  - `description`: Optional/nullable string, trimmed, maximum 1000 characters.
- **Update Payload Validation (`updateProjectSchema`)**:
  - `name`: Optional string, trimmed, non-empty, maximum 255 characters.
  - `description`: Optional/nullable string, trimmed, maximum 1000 characters.
  - Refinement rule: Requires at least one field (`name` or `description`) to be present in the update payload.

---

## API Versioning

All API endpoints follow the `/api/v1` URL prefix:

- `/api/v1/health`
- `/api/v1/auth/*`
- `/api/v1/projects/*`

This isolates versioned API routes from frontend assets and ensures backward compatibility as the application expands.

---

## Security Principles

The backend enforces the following active security controls:

1. **Clerk Token Verification**: All protected routes require a verified Clerk session token. Unauthenticated requests are rejected immediately at the middleware layer (HTTP 401).
2. **Strict Multi-Tenant Isolation**: The backend strictly derives user identity from Clerk authentication (`getAuth(req)`). `userId` is never accepted from the request body or query parameters.
3. **Scoped Ownership Checks**: All Project queries (`findByIdAndUserId`, `update`, `delete`) verify that the project's `userId` matches the caller's internal UUID. Requesting another user's project returns HTTP 404, preventing resource enumeration.
4. **CORS Protection**: CORS origins are restricted to configured origins (`CORS_ORIGINS` environment variable) with `http://localhost:5173` as a default development fallback. Wildcard (`*`) origins are avoided while `credentials: true` is enabled.
5. **Production Error Masking**: Internal error stacks, database queries, and credentials are never exposed in API error responses.
6. **No Secret Leaks**: Secret keys (`CLERK_SECRET_KEY`, `DATABASE_URL`) are read exclusively from server environment variables and are excluded from git tracking via `.gitignore`.