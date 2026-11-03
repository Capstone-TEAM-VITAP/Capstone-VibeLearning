"""
Write data/flows_heldout.json: execution-flow questions on repositories that were not used to
design the pruner. Gold edges are file-to-file imports that carry the described behaviour; they
were annotated from knowledge of each library's module structure BEFORE any pruner variant was
run on them. Existence of every edge is checked against the independent import oracle by
run_flows.py. Each entry is (query, [(source, target), ...]).
"""

import json
from pathlib import Path

RESEARCH = Path(__file__).resolve().parents[1]

SETS = {
    ("requests", "py", "src/requests/"): [
        ("How does a top-level request function end up sending the HTTP request?", [("api.py", "sessions.py"), ("sessions.py", "adapters.py")]),
        ("How are cookies handled across requests made through a session?", [("sessions.py", "cookies.py"), ("models.py", "cookies.py")]),
        ("How are failed HTTP responses and connection problems turned into exceptions?", [("models.py", "exceptions.py"), ("adapters.py", "exceptions.py")]),
        ("How is authentication applied to an outgoing request?", [("sessions.py", "auth.py"), ("models.py", "auth.py")]),
        ("How are response hooks registered and dispatched?", [("sessions.py", "hooks.py"), ("models.py", "hooks.py")]),
    ],
    ("flask", "py", "src/flask/"): [
        ("How does the application load its configuration?", [("app.py", "sansio/app.py"), ("sansio/app.py", "config.py")]),
        ("How are user sessions stored in signed cookies?", [("app.py", "sessions.py"), ("sessions.py", "json/tag.py")]),
        ("How is JSON serialised when a view returns data?", [("sansio/app.py", "json/provider.py"), ("json/__init__.py", "json/provider.py")]),
        ("How is the request context created and pushed for each request?", [("app.py", "ctx.py"), ("ctx.py", "globals.py")]),
        ("How are blueprints registered with the application?", [("blueprints.py", "sansio/blueprints.py"), ("sansio/blueprints.py", "sansio/scaffold.py"), ("sansio/app.py", "sansio/blueprints.py")]),
        ("How are the built-in command line commands such as run and routes defined?", [("__main__.py", "cli.py"), ("app.py", "cli.py")]),
    ],
    ("httpx", "py", "httpx/"): [
        ("How does a client send a request through its transport?", [("_client.py", "_transports/default.py"), ("_transports/default.py", "_transports/base.py")]),
        ("How are authentication flows applied to requests?", [("_client.py", "_auth.py"), ("_auth.py", "_models.py")]),
        ("How is a multipart request body encoded?", [("_content.py", "_multipart.py"), ("_models.py", "_content.py")]),
        ("How are compressed response bodies decoded?", [("_models.py", "_decoders.py"), ("_client.py", "_decoders.py")]),
        ("How do the top-level helper functions use a client?", [("_api.py", "_client.py")]),
    ],
    ("click", "py", "src/click/"): [
        ("How are command-line arguments parsed into option values?", [("core.py", "parser.py"), ("core.py", "types.py")]),
        ("How is shell completion implemented?", [("core.py", "shell_completion.py"), ("shell_completion.py", "core.py")]),
        ("How are usage errors reported to the user?", [("core.py", "exceptions.py"), ("parser.py", "exceptions.py")]),
        ("How do the decorators create commands and options?", [("decorators.py", "core.py"), ("__init__.py", "decorators.py")]),
        ("How does the library print prompts and progress bars?", [("termui.py", "_termui_impl.py"), ("__init__.py", "termui.py")]),
    ],
    ("koa", "js", "lib/"): [
        ("How does Koa create the context from the request and response objects?", [("application.js", "context.js"), ("application.js", "request.js"), ("application.js", "response.js")]),
    ],
    ("express", "js", "lib/"): [
        ("How does the express factory assemble an application with request and response objects?", [("express.js", "application.js"), ("express.js", "request.js"), ("express.js", "response.js")]),
    ],
    ("hapi", "js", "lib/"): [
        ("How is a route configured with authentication, validation and a handler?", [("route.js", "auth.js"), ("route.js", "validation.js"), ("route.js", "handler.js")]),
        ("How does the server hand requests to its core and route table?", [("server.js", "core.js"), ("core.js", "route.js")]),
    ],
}

questions = []
for (repo, lang, prefix), items in SETS.items():
    for i, (query, edges) in enumerate(items, 1):
        questions.append(
            {
                "id": f"{repo}:F{i}",
                "repo": repo,
                "lang": lang,
                "query": query,
                "gold": [[prefix + a, prefix + b] for a, b in edges],
            }
        )
(RESEARCH / "data" / "flows_heldout.json").write_text(
    json.dumps({"_note": "Held-out flows; annotated before any relevance-aware pruner variant was run on them.", "questions": questions}, indent=1)
)
print(len(questions), "held-out flow questions")
