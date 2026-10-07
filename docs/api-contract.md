# CodeAI API Contract

This document specifies the current API contract for the CodeAI backend.

---

## Base URL

```text
/api/v1
```

All API routes are prefixed with `/api/v1`.

---

## Authentication

Protected endpoints require a valid **Clerk session bearer token** transmitted in the `Authorization` header:

```http
Authorization: Bearer <clerk_session_jwt>
```

- If the token is missing, expired, or invalid, the request is rejected with **HTTP 401 Unauthorized**.
- The backend verifies the token and resolves the Clerk user ID (`clerkUserId`).
- The internal database user (`User.id`) is resolved automatically.
- Clients must never send a `userId` in request bodies or query parameters.

---

## Standard Response Format

All responses follow a consistent JSON envelope.

### 1. Success Response (Single Resource / Mutation)

```json
{
  "success": true,
  "data": {}
}
```

### 2. List Response (Collections)

```json
{
  "success": true,
  "data": [],
  "meta": {
    "total": 0
  }
}
```

### 3. Error Response

```json
{
  "success": false,
  "message": "Error description message"
}
```

---

## System Endpoints

### Health Check

```http
GET /api/v1/health
```

- **Authentication**: None (Public)
- **Purpose**: Verify that the backend service is running and responsive.
- **Request Body**: None
- **Parameters**: None
- **Success Status**: `200 OK`
- **Response Example**:
  ```json
  {
    "success": true,
    "data": {
      "status": "healthy"
    }
  }
  ```
- **Error Statuses**: `500` (Unexpected internal server error)

---

## Authentication Endpoints

### Get Current User Profile

```http
GET /api/v1/auth/me
```

- **Authentication**: Required (`Bearer <clerk_token>`)
- **Purpose**: Retrieve the authenticated caller's Clerk user identity.
- **Request Body**: None
- **Parameters**: None
- **Success Status**: `200 OK`
- **Response Example**:
  ```json
  {
    "success": true,
    "data": {
      "userId": "user_2tN87xXkL9..."
    }
  }
  ```
- **Error Statuses**:
  - `401 Unauthorized`:
    ```json
    {
      "success": false,
      "message": "Unauthorized"
    }
    ```

---

## Projects Endpoints

All Project endpoints are **scoped strictly to the authenticated user**. Users can only access, view, modify, and delete projects that they own.

---

### 1. List Projects

```http
GET /api/v1/projects
```

- **Authentication**: Required (`Bearer <clerk_token>`)
- **Purpose**: Retrieve all projects belonging to the authenticated user, ordered from newest to oldest.
- **Request Body**: None
- **Parameters**: None
- **Success Status**: `200 OK`
- **Response Example**:
  ```json
  {
    "success": true,
    "data": [
      {
        "id": "18f3a532-6a75-4d0f-b2b9-e16543b59301",
        "name": "Full Stack Learning App",
        "description": "Interactive learning project with Supabase and Express",
        "userId": "21620d0c-ab1c-418e-b0d8-06e857b9e633",
        "createdAt": "2026-09-02T05:38:33.613Z",
        "updatedAt": "2026-09-02T05:38:33.613Z"
      }
    ],
    "meta": {
      "total": 1
    }
  }
  ```
- **Error Statuses**:
  - `401 Unauthorized`: Missing or invalid authentication.
  - `500 Internal Server Error`: Unexpected server error.

---

### 2. Create Project

```http
POST /api/v1/projects
```

- **Authentication**: Required (`Bearer <clerk_token>`)
- **Purpose**: Create a new project owned by the authenticated user.
- **Request Body** (`application/json`):
  | Field | Type | Required | Rules |
  | :--- | :--- | :--- | :--- |
  | `name` | string | Yes | Trimmed, 1–255 characters |
  | `description` | string | No | Trimmed, maximum 1000 characters, nullable |

  ```json
  {
    "name": "My New Project",
    "description": "A description of the project"
  }
  ```
- **Parameters**: None
- **Validation**:
  - `name` missing or empty: Rejects with `400 Bad Request`.
  - `name` > 255 characters: Rejects with `400 Bad Request`.
  - `description` > 1000 characters: Rejects with `400 Bad Request`.
- **Success Status**: `201 Created`
- **Response Example**:
  ```json
  {
    "success": true,
    "data": {
      "id": "7ca647be-b695-46eb-811c-c3732808c160",
      "name": "My New Project",
      "description": "A description of the project",
      "userId": "21620d0c-ab1c-418e-b0d8-06e857b9e633",
      "createdAt": "2026-09-02T05:40:12.100Z",
      "updatedAt": "2026-09-02T05:40:12.100Z"
    }
  }
  ```
- **Error Statuses**:
  - `400 Bad Request`:
    ```json
    {
      "success": false,
      "message": "name: Project name is required"
    }
    ```
  - `401 Unauthorized`: Missing or invalid authentication.
  - `500 Internal Server Error`: Unexpected server error.

---

### 3. Get Project by ID

```http
GET /api/v1/projects/:id
```

- **Authentication**: Required (`Bearer <clerk_token>`)
- **Purpose**: Retrieve a single project by its UUID, scoped strictly to the authenticated user.
- **Request Body**: None
- **URL Parameters**:
  | Parameter | Type | Required | Description |
  | :--- | :--- | :--- | :--- |
  | `id` | string (UUID) | Yes | Unique project identifier |
- **Validation**:
  - `id` is not a valid UUID format: Rejects with `400 Bad Request`.
- **Success Status**: `200 OK`
- **Response Example**:
  ```json
  {
    "success": true,
    "data": {
      "id": "7ca647be-b695-46eb-811c-c3732808c160",
      "name": "My New Project",
      "description": "A description of the project",
      "userId": "21620d0c-ab1c-418e-b0d8-06e857b9e633",
      "createdAt": "2026-09-02T05:40:12.100Z",
      "updatedAt": "2026-09-02T05:40:12.100Z"
    }
  }
  ```
- **Error Statuses**:
  - `400 Bad Request`:
    ```json
    {
      "success": false,
      "message": "id: Invalid project ID format. Must be a valid UUID."
    }
    ```
  - `401 Unauthorized`: Missing or invalid authentication.
  - `404 Not Found`: Project does not exist or does not belong to the authenticated user:
    ```json
    {
      "success": false,
      "message": "Project not found"
    }
    ```
  - `500 Internal Server Error`: Unexpected server error.

---

### 4. Update Project

```http
PATCH /api/v1/projects/:id
```

- **Authentication**: Required (`Bearer <clerk_token>`)
- **Purpose**: Partially update an existing project owned by the authenticated user.
- **URL Parameters**:
  | Parameter | Type | Required | Description |
  | :--- | :--- | :--- | :--- |
  | `id` | string (UUID) | Yes | Unique project identifier |
- **Request Body** (`application/json`):
  | Field | Type | Required | Rules |
  | :--- | :--- | :--- | :--- |
  | `name` | string | Optional | Trimmed, 1–255 characters |
  | `description` | string | Optional | Trimmed, maximum 1000 characters, nullable |

  *At least one field (`name` or `description`) must be provided.*

  ```json
  {
    "name": "Updated Project Name",
    "description": "Updated description content"
  }
  ```
- **Validation**:
  - `id` is not a valid UUID: Rejects with `400 Bad Request`.
  - Empty body (neither `name` nor `description` provided): Rejects with `400 Bad Request`.
  - `name` is empty string: Rejects with `400 Bad Request`.
- **Success Status**: `200 OK`
- **Response Example**:
  ```json
  {
    "success": true,
    "data": {
      "id": "7ca647be-b695-46eb-811c-c3732808c160",
      "name": "Updated Project Name",
      "description": "Updated description content",
      "userId": "21620d0c-ab1c-418e-b0d8-06e857b9e633",
      "createdAt": "2026-09-02T05:40:12.100Z",
      "updatedAt": "2026-09-02T05:42:00.000Z"
    }
  }
  ```
- **Error Statuses**:
  - `400 Bad Request`:
    ```json
    {
      "success": false,
      "message": "At least one field (name or description) must be provided for update"
    }
    ```
  - `401 Unauthorized`: Missing or invalid authentication.
  - `404 Not Found`: Project does not exist or does not belong to the authenticated user.
  - `500 Internal Server Error`: Unexpected server error.

---

### 5. Delete Project

```http
DELETE /api/v1/projects/:id
```

- **Authentication**: Required (`Bearer <clerk_token>`)
- **Purpose**: Permanently delete a project owned by the authenticated user.
- **Request Body**: None
- **URL Parameters**:
  | Parameter | Type | Required | Description |
  | :--- | :--- | :--- | :--- |
  | `id` | string (UUID) | Yes | Unique project identifier |
- **Validation**:
  - `id` is not a valid UUID: Rejects with `400 Bad Request`.
- **Success Status**: `204 No Content`
- **Response Body**: Empty (no content)
- **Error Statuses**:
  - `400 Bad Request`: Invalid UUID parameter.
  - `401 Unauthorized`: Missing or invalid authentication.
  - `404 Not Found`: Project does not exist or does not belong to the authenticated user:
    ```json
    {
      "success": false,
      "message": "Project not found"
    }
    ```
  - `500 Internal Server Error`: Unexpected server error.

---

## Repositories Endpoints

Backend slice of the analysis pipeline: **GitHub Repo → Snapshot → Changed Files/Lines**.
All endpoints are scoped strictly to the authenticated user. The optional `accessToken`
(per-request, for private repos) is used for the git fetch only and is never persisted.

---

### 1. List Connected Repositories

```http
GET /api/v1/repos?projectId=<uuid>
```

- **Authentication**: Required (`Bearer <clerk_token>`)
- **Query**: `projectId` (optional UUID; must belong to the caller)
- **Success Status**: `200 OK` — list envelope `{ success, data: [], meta: { total } }`

---

### 2. Connect Repository

```http
POST /api/v1/repos/connect
```

- **Authentication**: Required (`Bearer <clerk_token>`)
- **Purpose**: Validate the GitHub URL, mirror the repo server-side, record a HEAD snapshot.
- **Request Body** (`application/json`):
  | Field | Type | Required | Rules |
  | :--- | :--- | :--- | :--- |
  | `repoUrl` | string | Yes | GitHub https or ssh URL |
  | `projectId` | string (UUID) | No | Must belong to the caller |
  | `defaultBranch` | string | No | Defaults to `main` |
  | `accessToken` | string | No | Private-repo token, never stored |

  ```json
  { "repoUrl": "https://github.com/octocat/Hello-World", "defaultBranch": "main" }
  ```
- **Success Status**: `201 Created` — the repository row (with `lastSyncSha`)
- **Error Statuses**:
  - `400 Bad Request`: Invalid URL / unreachable repo / bad token.
  - `401 Unauthorized`: Missing or invalid authentication.
  - `404 Not Found`: `projectId` does not belong to the caller.
  - `409 Conflict`: Repository already connected.

---

### 3. Get / Delete Repository

```http
GET /api/v1/repos/:id
DELETE /api/v1/repos/:id
```

- `DELETE` returns `204 No Content` and removes the server-side mirror cache (best-effort).
- Unknown / foreign IDs return `404 Not Found`.

---

### 4. Sync Repository (new Snapshot)

```http
POST /api/v1/repos/:id/sync
```

- **Request Body** (`application/json`, all optional):
  ```json
  { "ref": "origin/main", "baseSha": "6039afc5e7b4ee31ca7c6481c5e7e56acf978bfb", "accessToken": "..." }
  ```
  - `ref`: branch/tag/SHA to snapshot (defaults to `origin/<defaultBranch>`).
  - `baseSha`: full 40-char SHA the diff is measured against (defaults to `lastSyncSha`).
- **Success Status**: `201 Created`
- **Response Example**:
  ```json
  {
    "success": true,
    "data": {
      "snapshot": { "commitSha": "6a7c89be…", "message": "second", "fileCount": 2, "additions": 4, "deletions": 2 },
      "files": [{ "path": "src/app.js", "status": "M", "additions": 3, "deletions": 2 }],
      "cached": false
    }
  }
  ```

---

### 5. List Snapshots

```http
GET /api/v1/repos/:id/snapshots
```

- **Success Status**: `200 OK` — snapshots newest first, list envelope.

---

### 6. Changed Files (no hunks)

```http
GET /api/v1/repos/:id/snapshots/:sha/files?base=<sha>
```

- `:sha` and `?base=` are full 40-char commit SHAs. `base` defaults to the snapshot's recorded `baseSha`.
- **Response Example**:
  ```json
  {
    "success": true,
    "data": { "baseSha": "6039afc5…", "headSha": "6a7c89be…", "fileCount": 2, "files": [{ "path": "src/app.js", "status": "M" }] }
  }
  ```

---

### 7. Full Diff (hunks + line numbers)

```http
GET /api/v1/repos/:id/snapshots/:sha/diff?base=<sha>&path=<file>
```

- `path` (optional) restricts the diff to a single file.
- **Response Example**:
  ```json
  {
    "success": true,
    "data": {
      "baseSha": "6039afc5…", "headSha": "6a7c89be…",
      "fileCount": 2, "additions": 4, "deletions": 2,
      "files": [{ "path": "src/app.js", "status": "M", "additions": 3, "deletions": 2, "hunks": [] }]
    }
  }
  ```
- Hunk lines carry `{ type: "add"|"del"|"context", oldLine?, newLine?, text }` — the contract the AST / semantic-search / ranking stages consume.

---

### 8. Run Analysis (stub engine until ai-service lands)

```http
POST /api/v1/repos/:id/snapshots/:sha/analyze
```

- **Purpose**: Enqueue the snapshot (idempotent — one job per snapshot) and wait for completion. New snapshots from sync/connect are enqueued automatically in the background.
- **Success Status**: `200 OK` — the finished job (see below).
- **Error Statuses**: `404` unknown repo/snapshot; `500` engine failure (also recorded on the job row).

---

### 9. Get Analysis Result

```http
GET /api/v1/repos/:id/snapshots/:sha/analysis
```

- **Response Example**:
  ```json
  {
    "success": true,
    "data": {
      "status": "done",
      "attempts": 1,
      "error": null,
      "result": {
        "engine": "stub",
        "summary": "2 files changed, +4 −2",
        "files": [{ "path": "src/app.js", "status": "M", "additions": 3, "deletions": 2, "impact": "medium", "explanation": null }]
      }
    }
  }
  ```
- `status` is `pending` | `running` | `done` | `failed`. `engine: "stub"` means diff-stat output; set `AI_SERVICE_URL` for the real `POST {AI_SERVICE_URL}/analyze` engine.

---

### 10. Repository AI Assistant (Chat / QA)

```http
POST /api/v1/repos/:id/chat
```

- **Purpose**: Ask questions grounded in the connected repository's architecture, routes, database models, and source code.
- **Headers**: `Authorization: Bearer <clerk_token>`, `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "message": "Where is the authentication middleware defined and what does it do?",
    "history": [
      { "role": "user", "content": "Hello" },
      { "role": "assistant", "content": "Hi! I am your AI architect for this repo." }
    ]
  }
  ```
- **Success Status**: `200 OK`
- **Response Example**:
  ```json
  {
    "success": true,
    "data": {
      "message": "The function `requireAuth` is defined in `src/middleware/auth.middleware.js`...",
      "citations": [
        { "path": "src/middleware/auth.middleware.js", "startLine": 1, "endLine": 35 }
      ],
      "suggestedQuestions": [
        "Explain the architectural layers of this codebase",
        "Where are the API routes and controllers located?"
      ],
      "model": "grok-2-latest",
      "snapshotSha": "6a7c89be..."
    }
  }
  ```
- **Error Statuses**:
  - `400 Bad Request`: Empty or missing message.
  - `401 Unauthorized`: Missing or invalid Clerk authentication.
  - `404 Not Found`: Repository not found or not owned by user.

---

## Webhooks Endpoints

Public endpoints called by GitHub, not by users — no Clerk token. Authentication is the `X-Hub-Signature-256` HMAC header verified against `GITHUB_WEBHOOK_SECRET`.

---

### 1. GitHub Push Webhook

```http
POST /api/v1/webhooks/github
```

- **Headers**: `X-GitHub-Event` (`push`/`ping`/…), `X-Hub-Signature-256: sha256=<hmac>`
- **Purpose**: Auto-sync every connected row matching the pushed repo: fetch, resolve the pushed ref, record a snapshot (skipped if it already exists).
- **Setup**: repo Settings → Webhooks → payload URL `https://<backend>/api/v1/webhooks/github`, JSON, `push` events only, secret = `GITHUB_WEBHOOK_SECRET`.
- **Responses**:
  - `200 { success: true, data: { matched: N } }` — synced N connected rows.
  - `200 { success: true, data: { ignored: true } }` — ping, non-push, deletion, or unknown repo (not an error; stops GitHub retries).
  - `401` — bad/missing signature. `500` — webhook secret not configured.

---

## Learning Endpoints

MCQ quizzes generated from a deterministic markdown "learning pack"
(architecture roles + code excerpts from the analysis pipeline), via the
configured LLM provider (Groq first) with a deterministic offline fallback.
Questions and attempts are persisted: `LearningSet -> LearningQuestion[] -> LearningAttempt[]`.
All endpoints are scoped strictly to the authenticated user.

---

### 1. Generate Learning Set (idempotent)

```http
POST /api/v1/repos/:id/learning/generate
```

- **Authentication**: Required (`Bearer <clerk_token>`)
- **Purpose**: Build (or reuse) an MCQ set for a topic. Same user/repo/snapshot/topic/difficulty returns the saved set.
- **Request Body** (`application/json`):
  | Field | Type | Required | Rules |
  | :--- | :--- | :--- | :--- |
  | `topic` | string | Yes | Trimmed, 1–200 characters |
  | `difficulty` | string | No | `beginner` \| `intermediate` \| `advanced` (default `beginner`) |
  | `count` | number | No | 1–10 (default 5) |

  ```json
  { "topic": "authentication", "difficulty": "beginner", "count": 5 }
  ```
- **Success Status**: `201 Created` — the set with questions (answers hidden) and `engine: "llm" | "offline"`
- **Error Statuses**:
  - `400 Bad Request`: Invalid topic/difficulty/count, or not enough repository context (run analysis first).
  - `401 Unauthorized`: Missing or invalid authentication.
  - `404 Not Found`: Repository does not exist or does not belong to the caller.

---

### 2. List Learning Sets

```http
GET /api/v1/repos/:id/learning/sets
```

- **Success Status**: `200 OK` — list envelope; each set carries `progress: { answered, correct, total }`.

---

### 3. Get Learning Set

```http
GET /api/v1/repos/:id/learning/sets/:setId
```

- **Success Status**: `200 OK` — the set with questions (options only, no answers) plus the caller's latest attempt per question.
- **Error Statuses**: `404` unknown/foreign set.

---

### 4. Submit Answers

```http
POST /api/v1/repos/:id/learning/sets/:setId/submit
```

- **Request Body** (`application/json`):
  ```json
  { "answers": [{ "questionId": "<uuid>", "pickedIndex": 2 }] }
  ```
  - `answers`: 1–10 items; `pickedIndex` must be 0–3.
- **Success Status**: `200 OK`
- **Response Example**:
  ```json
  {
    "success": true,
    "data": {
      "correct": 3,
      "total": 5,
      "results": [
        {
          "questionId": "<uuid>",
          "pickedIndex": 2,
          "correct": true,
          "answerIndex": 2,
          "prompt": "In which file is \"requireAuth\" defined?",
          "options": ["src/a.js", "src/b.js", "src/c.js", "src/d.js"],
          "explanation": "\"requireAuth\" is defined in src/a.js.",
          "citationPath": "src/a.js",
          "citationStart": 10,
          "citationEnd": 25
        }
      ]
    }
  }
  ```
- **Error Statuses**: `400` empty/invalid answers or unknown question; `404` unknown/foreign set.

---

### 5. Learning Progress

```http
GET /api/v1/repos/:id/learning/progress
```

- **Success Status**: `200 OK` — `{ sets, answered, correct, total }` totals for the caller on this repo.
