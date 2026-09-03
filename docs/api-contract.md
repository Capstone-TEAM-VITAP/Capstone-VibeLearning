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
