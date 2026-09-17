# Repository Analysis API Contract

## Overview
The AI Service exposes Person 1's Repository Intelligence pipeline via a lightweight, deterministic HTTP endpoint built with FastAPI. It performs static analysis (scanning, AST parsing, symbol extraction, relationship extraction, cross-file resolution, architectural classification, and CodeGraph construction) on a local repository path and returns canonical Graph IR (Schema Version 1.0).

---

## Endpoint Specification

### `POST /analyze`
Runs deterministic static analysis on an accessible local repository directory.

#### Request Headers
- `Content-Type: application/json`

#### Request Body Schema
```json
{
  "repository_path": "string (required, absolute or relative local filesystem path)",
  "repo_name": "string (optional, explicit repository name identifier)"
}
```

#### Example Request
```json
{
  "repository_path": "/path/to/local/cache/sample-repo",
  "repo_name": "sample-repo"
}
```

---

## Response Specification

#### Status Codes
- `200 OK`: Analysis succeeded, Graph IR returned.
- `400 Bad Request`: Invalid request parameters (e.g. empty path, path is a file, or analysis error).
- `404 Not Found`: The specified `repository_path` does not exist on disk.
- `422 Unprocessable Entity`: Request payload failed JSON or Pydantic validation.
- `500 Internal Server Error`: An unexpected internal server error occurred (sanitized, stack trace hidden).

#### Response Body Schema (Canonical M8 Schema)
```json
{
  "repository_name": "sample-repo",
  "ir": {
    "schema_version": "1.0",
    "repository": {
      "id": "repo:sample-repo",
      "name": "sample-repo"
    },
    "nodes": [
      {
        "id": "file:src/routes/auth.js",
        "type": "file",
        "label": "auth.js",
        "metadata": {
          "extension": ".js",
          "language": "javascript",
          "path": "src/routes/auth.js",
          "size": "150"
        }
      },
      {
        "id": "symbol:src/routes/auth.js:setupAuthRoutes:3:0",
        "type": "function",
        "label": "setupAuthRoutes",
        "metadata": {
          "end_col": "1",
          "end_line": "6",
          "kind": "function",
          "name": "setupAuthRoutes",
          "path": "src/routes/auth.js",
          "start_col": "0",
          "start_line": "3"
        }
      },
      {
        "id": "architecture:src/routes/auth.js:ROUTE",
        "type": "route",
        "label": "auth.js (ROUTE)",
        "metadata": {
          "layer": "presentation",
          "path": "src/routes/auth.js",
          "role": "route"
        }
      }
    ],
    "edges": [
      {
        "id": "edge:repo:sample-repo->contains->file:src/routes/auth.js",
        "type": "contains",
        "source": "repo:sample-repo",
        "target": "file:src/routes/auth.js",
        "metadata": {}
      },
      {
        "id": "edge:file:src/routes/auth.js->classified_as->architecture:src/routes/auth.js:ROUTE",
        "type": "classified_as",
        "source": "file:src/routes/auth.js",
        "target": "architecture:src/routes/auth.js:ROUTE",
        "metadata": {
          "layer": "presentation",
          "role": "route"
        }
      }
    ]
  }
}
```

---

## Security Restrictions
1. **Local Paths Only**: The AI Service analyzes repositories pre-fetched and prepared by the backend. It does not perform network cloning or follow external symlinks.
2. **Path Boundary Enforcement**: The pipeline checks that all analyzed files reside strictly within the requested repository root. Path traversal attempts are rejected.
3. **No Execution of Repository Code**:
   - Repository code is never executed, imported, or evaluated.
   - `npm install`, `npm run`, `pip install`, build scripts, or shell commands are never invoked.
   - All extraction is performed via static Tree-sitter AST parsing.
4. **Secret Sanitization**: Neither secrets, environment variables, nor internal system paths are exposed in response bodies.

---

## Determinism Contract
Given the identical filesystem tree:
- File ordering is sorted deterministically by POSIX relative path.
- Symbols are sorted by line, column, and identifier name.
- Relationships and resolved imports are sorted by position and target.
- Nodes and edges in Graph IR are sorted deterministically by unique string ID.
