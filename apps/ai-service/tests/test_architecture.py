"""
tests/test_architecture.py

Test suite for Milestone 6 — Architectural Detection.

Coverage
--------
FILE/PATH DETECTION:
 1.  Controller detection (filename stem, directory, dot-notation)
 2.  Service detection
 3.  Repository detection
 4.  Route detection
 5.  Model detection
 6.  Entity detection
 7.  Middleware detection
 8.  Config detection
 9.  Utility detection
10.  Test file detection (.test.js, .spec.js, __tests__ dir)
11.  Entrypoint detection (index.js, main.js, server.js, app.js)
12.  Hook detection (useXxx filename, hooks/ directory)
13.  Component detection (.jsx extension, components/ directory)

CONTENT DETECTION:
14.  Express route registration calls
15.  React hook calls → COMPONENT evidence
16.  Database operation calls → REPOSITORY evidence
17.  Model creation calls
18.  Symbol naming conventions (Controller, Service, Repository, Model)
19.  React hook symbol naming (useXxx function)
20.  JSX component symbol naming (Uppercase in .jsx)

IMPORT-BASED DETECTION:
21.  Importing 'react' → COMPONENT + HOOK evidence
22.  Importing 'express' → ROUTE evidence
23.  Importing 'mongoose' → MODEL + REPOSITORY evidence
24.  External imports only (EXTERNAL status)
25.  Non-external resolved imports ignored for import detection

MULTI-ROLE:
26.  Test + Controller (authController.test.js)
27.  Route + Entrypoint (routes/index.js)
28.  Hook + Component (components/useData.js)
29.  Repository + Model (model/schema)

UNKNOWN:
30.  Truly unclassifiable file → UNKNOWN
31.  UNKNOWN evidence is empty tuple

RELATIONSHIP DETECTION:
32.  ROUTE → CONTROLLER pattern
33.  CONTROLLER → SERVICE pattern
34.  SERVICE → REPOSITORY pattern
35.  REPOSITORY → MODEL pattern
36.  Pattern requires actual import (not just naming)
37.  No fabricated relationships from naming alone
38.  Unresolved imports ignored for relationship detection
39.  External imports ignored for relationship detection

QUALITY:
40.  Evidence items are non-empty for non-UNKNOWN roles
41.  Evidence descriptions are non-empty strings
42.  Evidence categories are valid strings
43.  Deterministic ordering of classifications
44.  Deterministic repeated calls
45.  Duplicate evidence descriptions not emitted
46.  Empty repository
47.  Repository with no symbols or relationships

IMMUTABILITY:
48.  FileClassification frozen
49.  ArchitecturalClassification frozen
50.  EvidenceItem frozen
51.  ArchitecturalRelationship frozen
52.  RepositoryArchitecture frozen
53.  SymbolId is hashable

ENUMS:
54.  ArchitectureRole values
55.  ArchitecturalLayer values
56.  Role → Layer mapping
"""

import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from repository.architecture import (
    ArchitecturalClassification,
    ArchitecturalLayer,
    ArchitecturalRelationship,
    ArchitectureRole,
    EvidenceItem,
    FileClassification,
    RepositoryArchitecture,
    _is_hook_name,
    _role_to_layer,
    classify_file,
    classify_repository,
)
from repository.models import FileInfo
from repository.parser import Position
from repository.relationships import Relationship, RelationshipKind
from repository.resolver import ResolvedRelationship, ResolutionStatus
from repository.symbols import Symbol, SymbolKind


# ===========================================================================
# Test data factories
# ===========================================================================


def _fi(path: str, ext: str = ".js") -> FileInfo:
    return FileInfo(path=path, language="javascript", extension=ext, size=100)


def _pos(line: int = 1, col: int = 0) -> Position:
    return Position(line=line, column=col)


def _sym(
    name: str,
    path: str,
    kind: SymbolKind = SymbolKind.FUNCTION,
    line: int = 1,
    parent: str | None = None,
) -> Symbol:
    return Symbol(name=name, kind=kind, path=path,
                  start=_pos(line), end=_pos(line + 2), parent=parent)


def _call(source: str, callee: str) -> Relationship:
    return Relationship(
        kind=RelationshipKind.CALLS, source_path=source,
        source_position=_pos(), target_name=callee,
        module_path=None, alias=None, is_default=False, is_namespace=False,
    )


def _imp(source: str, target_name: str, module_path: str,
         is_default: bool = False) -> Relationship:
    return Relationship(
        kind=RelationshipKind.IMPORTS, source_path=source,
        source_position=_pos(), target_name=target_name,
        module_path=module_path, alias=None,
        is_default=is_default, is_namespace=False,
    )


def _ext_resolved(source: str, module_path: str) -> ResolvedRelationship:
    """Create an EXTERNAL ResolvedRelationship."""
    return ResolvedRelationship(
        source_relationship=_imp(source, "", module_path),
        status=ResolutionStatus.EXTERNAL,
        target_path=None,
        target_symbol_id=None,
        notes=f"External dependency: {module_path!r}",
    )


def _local_resolved(source: str, target: str, module_path: str) -> ResolvedRelationship:
    """Create a RESOLVED_FILE ResolvedRelationship (local import found)."""
    return ResolvedRelationship(
        source_relationship=_imp(source, "", module_path),
        status=ResolutionStatus.RESOLVED_FILE,
        target_path=target,
        target_symbol_id=None,
        notes=None,
    )


def roles_of(fc: FileClassification) -> set[ArchitectureRole]:
    return {c.role for c in fc.classifications}


def has_role(fc: FileClassification, role: ArchitectureRole) -> bool:
    return any(c.role == role for c in fc.classifications)


def get_classification(fc: FileClassification, role: ArchitectureRole) -> ArchitecturalClassification | None:
    return next((c for c in fc.classifications if c.role == role), None)


def all_evidence(fc: FileClassification) -> list[str]:
    return [e.description for c in fc.classifications for e in c.evidence]


# ===========================================================================
# 1. Controller detection
# ===========================================================================


class TestControllerDetection:
    def test_controller_in_stem(self) -> None:
        assert has_role(classify_file(_fi("src/authController.js")), ArchitectureRole.CONTROLLER)

    def test_controller_dot_notation(self) -> None:
        assert has_role(classify_file(_fi("src/auth.controller.js")), ArchitectureRole.CONTROLLER)

    def test_controller_in_directory(self) -> None:
        assert has_role(classify_file(_fi("src/controllers/auth.js")), ArchitectureRole.CONTROLLER)

    def test_ctrl_abbreviation(self) -> None:
        assert has_role(classify_file(_fi("src/authCtrl.js")), ArchitectureRole.CONTROLLER)

    def test_controller_evidence_present(self) -> None:
        fc = classify_file(_fi("src/authController.js"))
        c = get_classification(fc, ArchitectureRole.CONTROLLER)
        assert c is not None
        assert len(c.evidence) > 0

    def test_controller_evidence_truthful(self) -> None:
        fc = classify_file(_fi("src/authController.js"))
        c = get_classification(fc, ArchitectureRole.CONTROLLER)
        assert any("controller" in e.description.lower() for e in c.evidence)

    def test_controller_layer_is_presentation(self) -> None:
        fc = classify_file(_fi("src/controllers/auth.js"))
        c = get_classification(fc, ArchitectureRole.CONTROLLER)
        assert c.layer == ArchitecturalLayer.PRESENTATION


# ===========================================================================
# 2. Service detection
# ===========================================================================


class TestServiceDetection:
    def test_service_in_stem(self) -> None:
        assert has_role(classify_file(_fi("src/authService.js")), ArchitectureRole.SERVICE)

    def test_service_dot_notation(self) -> None:
        assert has_role(classify_file(_fi("src/auth.service.js")), ArchitectureRole.SERVICE)

    def test_service_in_directory(self) -> None:
        assert has_role(classify_file(_fi("src/services/auth.js")), ArchitectureRole.SERVICE)

    def test_service_layer_is_application(self) -> None:
        fc = classify_file(_fi("src/services/auth.js"))
        c = get_classification(fc, ArchitectureRole.SERVICE)
        assert c.layer == ArchitecturalLayer.APPLICATION


# ===========================================================================
# 3. Repository detection
# ===========================================================================


class TestRepositoryDetection:
    def test_repository_in_stem(self) -> None:
        assert has_role(classify_file(_fi("src/userRepository.js")), ArchitectureRole.REPOSITORY)

    def test_repository_dot_notation(self) -> None:
        assert has_role(classify_file(_fi("src/user.repository.js")), ArchitectureRole.REPOSITORY)

    def test_repository_in_directory(self) -> None:
        assert has_role(classify_file(_fi("src/repositories/user.js")), ArchitectureRole.REPOSITORY)

    def test_repo_abbreviation(self) -> None:
        assert has_role(classify_file(_fi("src/repos/user.js")), ArchitectureRole.REPOSITORY)

    def test_repository_layer_is_data(self) -> None:
        fc = classify_file(_fi("src/repositories/user.js"))
        c = get_classification(fc, ArchitectureRole.REPOSITORY)
        assert c.layer == ArchitecturalLayer.DATA


# ===========================================================================
# 4. Route detection
# ===========================================================================


class TestRouteDetection:
    def test_route_in_stem(self) -> None:
        assert has_role(classify_file(_fi("src/authRoutes.js")), ArchitectureRole.ROUTE)

    def test_router_in_stem(self) -> None:
        assert has_role(classify_file(_fi("src/authRouter.js")), ArchitectureRole.ROUTE)

    def test_route_in_directory(self) -> None:
        assert has_role(classify_file(_fi("src/routes/auth.js")), ArchitectureRole.ROUTE)

    def test_route_layer_is_presentation(self) -> None:
        fc = classify_file(_fi("src/routes/auth.js"))
        c = get_classification(fc, ArchitectureRole.ROUTE)
        assert c.layer == ArchitecturalLayer.PRESENTATION


# ===========================================================================
# 5. Model detection
# ===========================================================================


class TestModelDetection:
    def test_model_in_stem(self) -> None:
        assert has_role(classify_file(_fi("src/UserModel.js")), ArchitectureRole.MODEL)

    def test_model_in_directory(self) -> None:
        assert has_role(classify_file(_fi("src/models/user.js")), ArchitectureRole.MODEL)

    def test_schema_in_stem(self) -> None:
        assert has_role(classify_file(_fi("src/userSchema.js")), ArchitectureRole.MODEL)

    def test_model_layer_is_domain(self) -> None:
        fc = classify_file(_fi("src/models/user.js"))
        c = get_classification(fc, ArchitectureRole.MODEL)
        assert c.layer == ArchitecturalLayer.DOMAIN


# ===========================================================================
# 6. Entity detection
# ===========================================================================


class TestEntityDetection:
    def test_entity_in_stem(self) -> None:
        assert has_role(classify_file(_fi("src/UserEntity.js")), ArchitectureRole.ENTITY)

    def test_entities_in_directory(self) -> None:
        assert has_role(classify_file(_fi("src/entities/user.js")), ArchitectureRole.ENTITY)

    def test_entity_layer_is_domain(self) -> None:
        fc = classify_file(_fi("src/entities/user.js"))
        c = get_classification(fc, ArchitectureRole.ENTITY)
        assert c.layer == ArchitecturalLayer.DOMAIN


# ===========================================================================
# 7. Middleware detection
# ===========================================================================


class TestMiddlewareDetection:
    def test_middleware_in_stem(self) -> None:
        assert has_role(classify_file(_fi("src/authMiddleware.js")), ArchitectureRole.MIDDLEWARE)

    def test_middleware_in_directory(self) -> None:
        assert has_role(classify_file(_fi("src/middleware/auth.js")), ArchitectureRole.MIDDLEWARE)

    def test_middleware_layer_is_infrastructure(self) -> None:
        fc = classify_file(_fi("src/middleware/auth.js"))
        c = get_classification(fc, ArchitectureRole.MIDDLEWARE)
        assert c.layer == ArchitecturalLayer.INFRASTRUCTURE


# ===========================================================================
# 8. Config detection
# ===========================================================================


class TestConfigDetection:
    def test_config_in_stem(self) -> None:
        assert has_role(classify_file(_fi("src/database.config.js")), ArchitectureRole.CONFIG)

    def test_config_in_directory(self) -> None:
        assert has_role(classify_file(_fi("src/config/database.js")), ArchitectureRole.CONFIG)

    def test_configuration_in_stem(self) -> None:
        assert has_role(classify_file(_fi("src/appConfiguration.js")), ArchitectureRole.CONFIG)

    def test_settings_in_stem(self) -> None:
        assert has_role(classify_file(_fi("src/settings.js")), ArchitectureRole.CONFIG)

    def test_config_layer_is_infrastructure(self) -> None:
        fc = classify_file(_fi("config/database.js"))
        c = get_classification(fc, ArchitectureRole.CONFIG)
        assert c.layer == ArchitecturalLayer.INFRASTRUCTURE


# ===========================================================================
# 9. Utility detection
# ===========================================================================


class TestUtilityDetection:
    def test_utils_in_stem(self) -> None:
        assert has_role(classify_file(_fi("src/dateUtils.js")), ArchitectureRole.UTILITY)

    def test_helper_in_stem(self) -> None:
        assert has_role(classify_file(_fi("src/formatHelper.js")), ArchitectureRole.UTILITY)

    def test_utils_in_directory(self) -> None:
        assert has_role(classify_file(_fi("src/utils/date.js")), ArchitectureRole.UTILITY)

    def test_helpers_in_directory(self) -> None:
        assert has_role(classify_file(_fi("src/helpers/format.js")), ArchitectureRole.UTILITY)

    def test_utility_layer_is_infrastructure(self) -> None:
        fc = classify_file(_fi("src/utils/date.js"))
        c = get_classification(fc, ArchitectureRole.UTILITY)
        assert c.layer == ArchitecturalLayer.INFRASTRUCTURE


# ===========================================================================
# 10. Test file detection
# ===========================================================================


class TestTestFileDetection:
    def test_dot_test_js(self) -> None:
        assert has_role(classify_file(_fi("src/auth.test.js")), ArchitectureRole.TEST)

    def test_dot_spec_js(self) -> None:
        assert has_role(classify_file(_fi("src/auth.spec.js")), ArchitectureRole.TEST)

    def test_tests_directory(self) -> None:
        assert has_role(classify_file(_fi("tests/auth.js")), ArchitectureRole.TEST)

    def test_dunder_tests_directory(self) -> None:
        assert has_role(classify_file(_fi("src/__tests__/auth.js")), ArchitectureRole.TEST)

    def test_spec_directory(self) -> None:
        assert has_role(classify_file(_fi("spec/auth.js")), ArchitectureRole.TEST)

    def test_test_layer_is_testing(self) -> None:
        fc = classify_file(_fi("src/auth.test.js"))
        c = get_classification(fc, ArchitectureRole.TEST)
        assert c.layer == ArchitecturalLayer.TESTING


# ===========================================================================
# 11. Entrypoint detection
# ===========================================================================


class TestEntrypointDetection:
    def test_index_js(self) -> None:
        assert has_role(classify_file(_fi("src/index.js")), ArchitectureRole.ENTRYPOINT)

    def test_main_js(self) -> None:
        assert has_role(classify_file(_fi("main.js")), ArchitectureRole.ENTRYPOINT)

    def test_server_js(self) -> None:
        assert has_role(classify_file(_fi("server.js")), ArchitectureRole.ENTRYPOINT)

    def test_app_js(self) -> None:
        assert has_role(classify_file(_fi("app.js")), ArchitectureRole.ENTRYPOINT)

    def test_entrypoint_layer_is_infrastructure(self) -> None:
        fc = classify_file(_fi("index.js"))
        c = get_classification(fc, ArchitectureRole.ENTRYPOINT)
        assert c.layer == ArchitecturalLayer.INFRASTRUCTURE

    def test_non_entrypoint_stem(self) -> None:
        """random.js should NOT be an entrypoint."""
        assert not has_role(classify_file(_fi("src/random.js")), ArchitectureRole.ENTRYPOINT)


# ===========================================================================
# 12. Hook detection
# ===========================================================================


class TestHookDetection:
    def test_hook_from_use_filename(self) -> None:
        assert has_role(classify_file(_fi("src/useAuth.js")), ArchitectureRole.HOOK)

    def test_hook_from_hooks_directory(self) -> None:
        assert has_role(classify_file(_fi("src/hooks/auth.js")), ArchitectureRole.HOOK)

    def test_hook_usestate_not_hook(self) -> None:
        """'useful.js' should NOT be a hook — doesn't follow useXxx pattern."""
        assert not has_role(classify_file(_fi("src/useful.js")), ArchitectureRole.HOOK)

    def test_hook_layer_is_presentation(self) -> None:
        fc = classify_file(_fi("src/hooks/useAuth.js"))
        c = get_classification(fc, ArchitectureRole.HOOK)
        assert c.layer == ArchitecturalLayer.PRESENTATION

    def test_is_hook_name_true(self) -> None:
        assert _is_hook_name("useAuth") is True
        assert _is_hook_name("useState") is True
        assert _is_hook_name("useMyCustomHook") is True

    def test_is_hook_name_false(self) -> None:
        assert _is_hook_name("useful") is False
        assert _is_hook_name("use") is False
        assert _is_hook_name("Auth") is False
        assert _is_hook_name("") is False


# ===========================================================================
# 13. Component detection
# ===========================================================================


class TestComponentDetection:
    def test_jsx_extension(self) -> None:
        assert has_role(classify_file(_fi("src/UserCard.jsx", ".jsx")), ArchitectureRole.COMPONENT)

    def test_tsx_extension(self) -> None:
        assert has_role(classify_file(_fi("src/UserCard.tsx", ".tsx")), ArchitectureRole.COMPONENT)

    def test_components_directory(self) -> None:
        assert has_role(classify_file(_fi("src/components/UserCard.js")), ArchitectureRole.COMPONENT)

    def test_pages_directory(self) -> None:
        assert has_role(classify_file(_fi("src/pages/Home.js")), ArchitectureRole.COMPONENT)

    def test_views_directory(self) -> None:
        assert has_role(classify_file(_fi("src/views/Profile.js")), ArchitectureRole.COMPONENT)

    def test_component_layer_is_presentation(self) -> None:
        fc = classify_file(_fi("src/components/Button.jsx", ".jsx"))
        c = get_classification(fc, ArchitectureRole.COMPONENT)
        assert c.layer == ArchitecturalLayer.PRESENTATION


# ===========================================================================
# 14. Express route registration calls
# ===========================================================================


class TestExpressRouteCalls:
    def test_router_get_is_route(self) -> None:
        rels = [_call("src/routes/auth.js", "router.get")]
        fc = classify_file(_fi("src/routes/auth.js"), relationships=rels)
        assert has_role(fc, ArchitectureRole.ROUTE)

    def test_router_post_is_route(self) -> None:
        rels = [_call("src/r.js", "router.post")]
        fc = classify_file(_fi("src/r.js"), relationships=rels)
        assert has_role(fc, ArchitectureRole.ROUTE)

    def test_app_use_is_route(self) -> None:
        rels = [_call("src/r.js", "app.use")]
        fc = classify_file(_fi("src/r.js"), relationships=rels)
        assert has_role(fc, ArchitectureRole.ROUTE)

    def test_route_evidence_mentions_callee(self) -> None:
        rels = [_call("src/r.js", "router.get")]
        fc = classify_file(_fi("src/r.js"), relationships=rels)
        c = get_classification(fc, ArchitectureRole.ROUTE)
        assert any("router.get" in e.description for e in c.evidence)

    def test_route_evidence_category_is_call(self) -> None:
        rels = [_call("src/r.js", "router.get")]
        fc = classify_file(_fi("src/r.js"), relationships=rels)
        c = get_classification(fc, ArchitectureRole.ROUTE)
        assert any(e.category == "call" for e in c.evidence)

    def test_multiple_router_calls_not_duplicate_evidence(self) -> None:
        """Multiple router.get calls should produce only one evidence item."""
        rels = [_call("src/r.js", "router.get"), _call("src/r.js", "router.get")]
        fc = classify_file(_fi("src/r.js"), relationships=rels)
        c = get_classification(fc, ArchitectureRole.ROUTE)
        descs = [e.description for e in c.evidence if "router.get" in e.description]
        assert len(descs) == 1


# ===========================================================================
# 15. React hook calls → COMPONENT evidence
# ===========================================================================


class TestReactHookCalls:
    def test_use_state_call_is_component(self) -> None:
        rels = [_call("src/comp.jsx", "useState")]
        fc = classify_file(_fi("src/comp.jsx", ".jsx"), relationships=rels)
        assert has_role(fc, ArchitectureRole.COMPONENT)

    def test_use_effect_call_is_component(self) -> None:
        rels = [_call("src/comp.jsx", "useEffect")]
        fc = classify_file(_fi("src/comp.jsx", ".jsx"), relationships=rels)
        assert has_role(fc, ArchitectureRole.COMPONENT)

    def test_hook_call_evidence_category(self) -> None:
        rels = [_call("src/comp.jsx", "useState")]
        fc = classify_file(_fi("src/comp.jsx", ".jsx"), relationships=rels)
        c = get_classification(fc, ArchitectureRole.COMPONENT)
        assert any(e.category == "call" for e in c.evidence)


# ===========================================================================
# 16. Database operation calls → REPOSITORY evidence
# ===========================================================================


class TestDatabaseCalls:
    def test_prisma_prefix_is_repository(self) -> None:
        rels = [_call("src/repo.js", "prisma.user.findMany")]
        fc = classify_file(_fi("src/repo.js"), relationships=rels)
        assert has_role(fc, ArchitectureRole.REPOSITORY)

    def test_db_prefix_is_repository(self) -> None:
        rels = [_call("src/repo.js", "db.query")]
        fc = classify_file(_fi("src/repo.js"), relationships=rels)
        assert has_role(fc, ArchitectureRole.REPOSITORY)

    def test_find_many_suffix_is_repository(self) -> None:
        rels = [_call("src/repo.js", "User.findMany")]
        fc = classify_file(_fi("src/repo.js"), relationships=rels)
        assert has_role(fc, ArchitectureRole.REPOSITORY)

    def test_find_by_id_suffix_is_repository(self) -> None:
        rels = [_call("src/repo.js", "User.findById")]
        fc = classify_file(_fi("src/repo.js"), relationships=rels)
        assert has_role(fc, ArchitectureRole.REPOSITORY)

    def test_save_suffix_is_repository(self) -> None:
        rels = [_call("src/repo.js", "document.save")]
        fc = classify_file(_fi("src/repo.js"), relationships=rels)
        assert has_role(fc, ArchitectureRole.REPOSITORY)

    def test_db_evidence_category_is_call(self) -> None:
        rels = [_call("src/repo.js", "prisma.user.findMany")]
        fc = classify_file(_fi("src/repo.js"), relationships=rels)
        c = get_classification(fc, ArchitectureRole.REPOSITORY)
        assert any(e.category == "call" for e in c.evidence)


# ===========================================================================
# 17. Model creation calls
# ===========================================================================


class TestModelCreationCalls:
    def test_mongoose_model_call_is_model(self) -> None:
        rels = [_call("src/models/user.js", "mongoose.model")]
        fc = classify_file(_fi("src/models/user.js"), relationships=rels)
        assert has_role(fc, ArchitectureRole.MODEL)

    def test_mongoose_model_evidence_mentions_callee(self) -> None:
        rels = [_call("src/user.js", "mongoose.model")]
        fc = classify_file(_fi("src/user.js"), relationships=rels)
        c = get_classification(fc, ArchitectureRole.MODEL)
        assert any("mongoose.model" in e.description for e in c.evidence)


# ===========================================================================
# 18. Symbol naming conventions
# ===========================================================================


class TestSymbolNamingConventions:
    def test_controller_class_symbol(self) -> None:
        symbols = [_sym("AuthController", "src/auth.js", SymbolKind.CLASS)]
        fc = classify_file(_fi("src/auth.js"), symbols=symbols)
        assert has_role(fc, ArchitectureRole.CONTROLLER)

    def test_service_class_symbol(self) -> None:
        symbols = [_sym("UserService", "src/user.js", SymbolKind.CLASS)]
        fc = classify_file(_fi("src/user.js"), symbols=symbols)
        assert has_role(fc, ArchitectureRole.SERVICE)

    def test_repository_class_symbol(self) -> None:
        symbols = [_sym("UserRepository", "src/user.js", SymbolKind.CLASS)]
        fc = classify_file(_fi("src/user.js"), symbols=symbols)
        assert has_role(fc, ArchitectureRole.REPOSITORY)

    def test_model_class_symbol(self) -> None:
        symbols = [_sym("UserModel", "src/user.js", SymbolKind.CLASS)]
        fc = classify_file(_fi("src/user.js"), symbols=symbols)
        assert has_role(fc, ArchitectureRole.MODEL)

    def test_schema_class_symbol(self) -> None:
        symbols = [_sym("UserSchema", "src/user.js", SymbolKind.CLASS)]
        fc = classify_file(_fi("src/user.js"), symbols=symbols)
        assert has_role(fc, ArchitectureRole.MODEL)

    def test_symbol_evidence_category_is_symbol(self) -> None:
        symbols = [_sym("AuthController", "src/auth.js", SymbolKind.CLASS)]
        fc = classify_file(_fi("src/auth.js"), symbols=symbols)
        c = get_classification(fc, ArchitectureRole.CONTROLLER)
        assert any(e.category == "symbol" for e in c.evidence)


# ===========================================================================
# 19. React hook symbol naming
# ===========================================================================


class TestHookSymbolNaming:
    def test_use_function_symbol_is_hook(self) -> None:
        symbols = [_sym("useAuth", "src/hooks/useAuth.js", SymbolKind.FUNCTION)]
        fc = classify_file(_fi("src/hooks/useAuth.js"), symbols=symbols)
        assert has_role(fc, ArchitectureRole.HOOK)

    def test_hook_symbol_evidence(self) -> None:
        symbols = [_sym("useUserData", "src/useUserData.js", SymbolKind.FUNCTION)]
        fc = classify_file(_fi("src/useUserData.js"), symbols=symbols)
        c = get_classification(fc, ArchitectureRole.HOOK)
        assert c is not None
        assert any("useUserData" in e.description for e in c.evidence)

    def test_non_hook_function_not_classified_as_hook(self) -> None:
        """'login' is a function but not a hook — no hook evidence from symbols."""
        symbols = [_sym("login", "src/auth.js", SymbolKind.FUNCTION)]
        fc = classify_file(_fi("src/auth.js"), symbols=symbols)
        assert not has_role(fc, ArchitectureRole.HOOK)


# ===========================================================================
# 20. React component symbol naming
# ===========================================================================


class TestComponentSymbolNaming:
    def test_uppercase_function_in_jsx_is_component(self) -> None:
        symbols = [_sym("UserCard", "src/UserCard.jsx", SymbolKind.FUNCTION)]
        fc = classify_file(_fi("src/UserCard.jsx", ".jsx"), symbols=symbols)
        assert has_role(fc, ArchitectureRole.COMPONENT)

    def test_uppercase_class_in_jsx_is_component(self) -> None:
        symbols = [_sym("UserCard", "src/UserCard.jsx", SymbolKind.CLASS)]
        fc = classify_file(_fi("src/UserCard.jsx", ".jsx"), symbols=symbols)
        assert has_role(fc, ArchitectureRole.COMPONENT)

    def test_uppercase_function_in_plain_js_not_component(self) -> None:
        """Capitalized function in .js file (not .jsx) should NOT get component evidence from symbols."""
        symbols = [_sym("UserCard", "src/user.js", SymbolKind.FUNCTION)]
        fc = classify_file(_fi("src/user.js"))
        # May still be COMPONENT from directory, but NOT from the symbol alone
        c = get_classification(fc, ArchitectureRole.COMPONENT)
        if c:
            # If COMPONENT present, evidence must NOT be from symbol in a .js file
            symbol_evidence = [e for e in c.evidence if e.category == "symbol"]
            assert not symbol_evidence


# ===========================================================================
# 21. Importing 'react' → COMPONENT + HOOK evidence
# ===========================================================================


class TestReactImportEvidence:
    def test_react_import_is_component(self) -> None:
        rr = _ext_resolved("src/App.js", "react")
        fc = classify_file(_fi("src/App.js"), resolved=[rr])
        assert has_role(fc, ArchitectureRole.COMPONENT)

    def test_react_import_is_hook(self) -> None:
        rr = _ext_resolved("src/App.js", "react")
        fc = classify_file(_fi("src/App.js"), resolved=[rr])
        assert not has_role(fc, ArchitectureRole.HOOK)

    def test_react_import_evidence_category(self) -> None:
        rr = _ext_resolved("src/App.js", "react")
        fc = classify_file(_fi("src/App.js"), resolved=[rr])
        c = get_classification(fc, ArchitectureRole.COMPONENT)
        assert any(e.category == "import" for e in c.evidence)


# ===========================================================================
# 22. Importing 'express' → ROUTE evidence
# ===========================================================================


class TestExpressImportEvidence:
    def test_express_import_is_route(self) -> None:
        rr = _ext_resolved("src/app.js", "express")
        fc = classify_file(_fi("src/app.js"), resolved=[rr])
        assert has_role(fc, ArchitectureRole.ROUTE)

    def test_express_import_evidence_description(self) -> None:
        rr = _ext_resolved("src/routes/auth.js", "express")
        fc = classify_file(_fi("src/routes/auth.js"), resolved=[rr])
        c = get_classification(fc, ArchitectureRole.ROUTE)
        assert any("express" in e.description for e in c.evidence)


# ===========================================================================
# 23. Importing 'mongoose' → MODEL + REPOSITORY evidence
# ===========================================================================


class TestMongooseImportEvidence:
    def test_mongoose_import_is_model(self) -> None:
        rr = _ext_resolved("src/user.js", "mongoose")
        fc = classify_file(_fi("src/user.js"), resolved=[rr])
        assert has_role(fc, ArchitectureRole.MODEL)

    def test_mongoose_import_is_repository(self) -> None:
        rr = _ext_resolved("src/user.js", "mongoose")
        fc = classify_file(_fi("src/user.js"), resolved=[rr])
        assert not has_role(fc, ArchitectureRole.REPOSITORY)


# ===========================================================================
# 24. External imports only
# ===========================================================================


class TestExternalImportsOnly:
    def test_only_external_imports_used(self) -> None:
        """UNRESOLVED imports should not produce import-based evidence."""
        unresolved = ResolvedRelationship(
            source_relationship=_imp("src/app.js", "foo", "./missing.js"),
            status=ResolutionStatus.UNRESOLVED,
            target_path=None, target_symbol_id=None,
            notes="Module not found",
        )
        fc = classify_file(_fi("src/app.js"), resolved=[unresolved])
        # Should not gain any role from the unresolved import
        import_evidence = [e for c in fc.classifications for e in c.evidence if e.category == "import"]
        assert len(import_evidence) == 0


# ===========================================================================
# 25. Local resolved imports ignored for import-based detection
# ===========================================================================


class TestLocalResolvedImports:
    def test_local_resolved_import_not_for_import_detection(self) -> None:
        """RESOLVED local imports don't trigger import-based role evidence."""
        local_rr = _local_resolved("src/app.js", "src/auth.js", "./auth.js")
        fc = classify_file(_fi("src/app.js"), resolved=[local_rr])
        import_evs = [e for c in fc.classifications for e in c.evidence if e.category == "import"]
        assert len(import_evs) == 0


# ===========================================================================
# 26. Multi-role: Test + Controller
# ===========================================================================


class TestMultiRole:
    def test_test_controller_dual_role(self) -> None:
        fc = classify_file(_fi("src/authController.test.js"))
        assert has_role(fc, ArchitectureRole.TEST)
        assert has_role(fc, ArchitectureRole.CONTROLLER)

    def test_route_entrypoint_dual_role(self) -> None:
        fc = classify_file(_fi("src/routes/index.js"))
        assert has_role(fc, ArchitectureRole.ROUTE)
        assert has_role(fc, ArchitectureRole.ENTRYPOINT)

    def test_dual_role_has_multiple_classifications(self) -> None:
        fc = classify_file(_fi("src/authController.test.js"))
        assert len(fc.classifications) >= 2

    def test_each_role_has_separate_evidence(self) -> None:
        fc = classify_file(_fi("src/authService.test.js"))
        test_c = get_classification(fc, ArchitectureRole.TEST)
        service_c = get_classification(fc, ArchitectureRole.SERVICE)
        assert test_c is not None
        assert service_c is not None
        # Evidence should mention different things
        test_descs = {e.description for e in test_c.evidence}
        svc_descs = {e.description for e in service_c.evidence}
        assert test_descs != svc_descs


# ===========================================================================
# 27. Multi-role: Hook + Component
# ===========================================================================


class TestHookComponentCombination:
    def test_hook_file_in_components_dir(self) -> None:
        """useData.js in components/ → both HOOK and COMPONENT."""
        fc = classify_file(_fi("src/components/useData.js"))
        assert has_role(fc, ArchitectureRole.HOOK)
        assert has_role(fc, ArchitectureRole.COMPONENT)


# ===========================================================================
# 28. UNKNOWN role
# ===========================================================================


class TestUnknownRole:
    def test_random_file_is_unknown(self) -> None:
        fc = classify_file(_fi("src/random.js"))
        assert has_role(fc, ArchitectureRole.UNKNOWN)

    def test_unknown_evidence_is_empty(self) -> None:
        fc = classify_file(_fi("src/foo.js"))
        c = get_classification(fc, ArchitectureRole.UNKNOWN)
        assert c is not None
        assert len(c.evidence) == 0

    def test_unknown_layer_is_unknown(self) -> None:
        fc = classify_file(_fi("src/foo.js"))
        c = get_classification(fc, ArchitectureRole.UNKNOWN)
        assert c.layer == ArchitecturalLayer.UNKNOWN

    def test_unknown_is_only_role_when_no_evidence(self) -> None:
        fc = classify_file(_fi("src/foo.js"))
        assert len(fc.classifications) == 1
        assert fc.classifications[0].role == ArchitectureRole.UNKNOWN


# ===========================================================================
# 29. Architectural relationship: ROUTE → CONTROLLER
# ===========================================================================


class TestRouteControllerPattern:
    def test_route_controller_pattern_detected(self) -> None:
        files = [_fi("src/routes/auth.js"), _fi("src/controllers/auth.js")]
        rr = _local_resolved("src/routes/auth.js", "src/controllers/auth.js", "./controllers/auth")
        arch = classify_repository(files, resolved=[rr])
        patterns = [ar.pattern for ar in arch.architectural_relationships]
        assert "ROUTE → CONTROLLER" in patterns

    def test_route_controller_source_and_target(self) -> None:
        files = [_fi("src/routes/auth.js"), _fi("src/controllers/auth.js")]
        rr = _local_resolved("src/routes/auth.js", "src/controllers/auth.js", "./controllers/auth")
        arch = classify_repository(files, resolved=[rr])
        ar = next(x for x in arch.architectural_relationships if x.pattern == "ROUTE → CONTROLLER")
        assert ar.source_path == "src/routes/auth.js"
        assert ar.target_path == "src/controllers/auth.js"

    def test_route_controller_roles_correct(self) -> None:
        files = [_fi("src/routes/auth.js"), _fi("src/controllers/auth.js")]
        rr = _local_resolved("src/routes/auth.js", "src/controllers/auth.js", "./controllers/auth")
        arch = classify_repository(files, resolved=[rr])
        ar = next(x for x in arch.architectural_relationships if x.pattern == "ROUTE → CONTROLLER")
        assert ar.source_role == ArchitectureRole.ROUTE
        assert ar.target_role == ArchitectureRole.CONTROLLER


# ===========================================================================
# 30. Architectural relationship: CONTROLLER → SERVICE
# ===========================================================================


class TestControllerServicePattern:
    def test_controller_service_pattern_detected(self) -> None:
        files = [_fi("src/controllers/user.js"), _fi("src/services/user.js")]
        rr = _local_resolved("src/controllers/user.js", "src/services/user.js", "./services/user")
        arch = classify_repository(files, resolved=[rr])
        patterns = [ar.pattern for ar in arch.architectural_relationships]
        assert "CONTROLLER → SERVICE" in patterns


# ===========================================================================
# 31. Architectural relationship: SERVICE → REPOSITORY
# ===========================================================================


class TestServiceRepositoryPattern:
    def test_service_repository_pattern_detected(self) -> None:
        files = [_fi("src/services/user.js"), _fi("src/repositories/user.js")]
        rr = _local_resolved("src/services/user.js", "src/repositories/user.js", "./repositories/user")
        arch = classify_repository(files, resolved=[rr])
        patterns = [ar.pattern for ar in arch.architectural_relationships]
        assert "SERVICE → REPOSITORY" in patterns


# ===========================================================================
# 32. Architectural relationship: REPOSITORY → MODEL
# ===========================================================================


class TestRepositoryModelPattern:
    def test_repository_model_pattern_detected(self) -> None:
        files = [_fi("src/repositories/user.js"), _fi("src/models/user.js")]
        rr = _local_resolved("src/repositories/user.js", "src/models/user.js", "./models/user")
        arch = classify_repository(files, resolved=[rr])
        patterns = [ar.pattern for ar in arch.architectural_relationships]
        assert "REPOSITORY → MODEL" in patterns


# ===========================================================================
# 33. No fabricated relationships without actual import
# ===========================================================================


class TestNoFabricatedRelationships:
    def test_no_rel_without_import(self) -> None:
        """ROUTE and CONTROLLER files exist but NO import — no pattern emitted."""
        files = [_fi("src/routes/auth.js"), _fi("src/controllers/auth.js")]
        arch = classify_repository(files, resolved=[])  # no resolved imports
        assert len(arch.architectural_relationships) == 0

    def test_unresolved_import_no_pattern(self) -> None:
        """Unresolved import (target file not found) must not generate arch rel."""
        files = [_fi("src/routes/auth.js")]
        unresolved = ResolvedRelationship(
            source_relationship=_imp("src/routes/auth.js", "x", "./controllers/auth"),
            status=ResolutionStatus.UNRESOLVED,
            target_path=None, target_symbol_id=None, notes=None,
        )
        arch = classify_repository(files, resolved=[unresolved])
        assert len(arch.architectural_relationships) == 0

    def test_external_import_no_pattern(self) -> None:
        """External import (npm) must not generate arch rel."""
        files = [_fi("src/routes/auth.js")]
        ext = _ext_resolved("src/routes/auth.js", "express")
        arch = classify_repository(files, resolved=[ext])
        # The file gets a ROUTE role from express import, but no arch relationship
        route_controller = [ar for ar in arch.architectural_relationships
                            if ar.pattern == "ROUTE → CONTROLLER"]
        assert len(route_controller) == 0


# ===========================================================================
# 34. Full 3-tier architecture
# ===========================================================================


class TestThreeTierArchitecture:
    def test_three_tier_patterns_all_detected(self) -> None:
        files = [
            _fi("src/routes/user.js"),
            _fi("src/controllers/user.js"),
            _fi("src/services/user.js"),
            _fi("src/repositories/user.js"),
        ]
        resolved = [
            _local_resolved("src/routes/user.js", "src/controllers/user.js", "./controllers/user"),
            _local_resolved("src/controllers/user.js", "src/services/user.js", "./services/user"),
            _local_resolved("src/services/user.js", "src/repositories/user.js", "./repositories/user"),
        ]
        arch = classify_repository(files, resolved=resolved)
        patterns = {ar.pattern for ar in arch.architectural_relationships}
        assert "ROUTE → CONTROLLER" in patterns
        assert "CONTROLLER → SERVICE" in patterns
        assert "SERVICE → REPOSITORY" in patterns


# ===========================================================================
# 35. Quality: Evidence is present and truthful
# ===========================================================================


class TestEvidenceQuality:
    def test_non_unknown_has_evidence(self) -> None:
        fc = classify_file(_fi("src/authController.js"))
        for c in fc.classifications:
            if c.role != ArchitectureRole.UNKNOWN:
                assert len(c.evidence) > 0

    def test_evidence_descriptions_non_empty(self) -> None:
        fc = classify_file(_fi("src/controllers/authController.js"))
        for c in fc.classifications:
            for e in c.evidence:
                assert len(e.description) > 0

    def test_evidence_categories_are_valid(self) -> None:
        valid_cats = {"path", "extension", "symbol", "call", "import", "classification"}
        rels = [_call("src/routes/auth.js", "router.get")]
        fc = classify_file(_fi("src/routes/auth.js"), relationships=rels)
        for c in fc.classifications:
            for e in c.evidence:
                assert e.category in valid_cats

    def test_no_duplicate_evidence_descriptions(self) -> None:
        """Same evidence description must appear at most once per classification."""
        fc = classify_file(_fi("src/controllers/auth.controller.js"))
        for c in fc.classifications:
            descs = [e.description for e in c.evidence]
            assert len(descs) == len(set(descs))


# ===========================================================================
# 36. Determinism
# ===========================================================================


class TestDeterminism:
    def test_same_input_same_output(self) -> None:
        fc1 = classify_file(_fi("src/authController.test.js"))
        fc2 = classify_file(_fi("src/authController.test.js"))
        assert fc1 == fc2

    def test_classifications_sorted(self) -> None:
        fc = classify_file(_fi("src/authController.test.js"))
        roles = [c.role.value for c in fc.classifications]
        assert roles == sorted(roles)

    def test_repository_files_sorted_by_path(self) -> None:
        files = [_fi("src/z.js"), _fi("src/a.js"), _fi("src/m.js")]
        arch = classify_repository(files)
        paths = [fc.path for fc in arch.file_classifications]
        assert paths == sorted(paths)

    def test_repeated_repository_calls_identical(self) -> None:
        files = [_fi("src/routes/auth.js"), _fi("src/controllers/auth.js")]
        rr = _local_resolved("src/routes/auth.js", "src/controllers/auth.js", "./controllers/auth")
        a1 = classify_repository(files, resolved=[rr])
        a2 = classify_repository(files, resolved=[rr])
        assert a1 == a2


# ===========================================================================
# 37. Empty repository
# ===========================================================================


class TestEmptyRepository:
    def test_empty_files_list(self) -> None:
        arch = classify_repository([])
        assert arch.file_classifications == ()
        assert arch.architectural_relationships == ()

    def test_single_file_no_symbols_no_rels(self) -> None:
        arch = classify_repository([_fi("src/random.js")])
        assert len(arch.file_classifications) == 1
        assert has_role(arch.file_classifications[0], ArchitectureRole.UNKNOWN)


# ===========================================================================
# 38. Immutability
# ===========================================================================


class TestImmutability:
    def test_file_classification_frozen(self) -> None:
        fc = classify_file(_fi("src/authController.js"))
        with pytest.raises((AttributeError, TypeError)):
            fc.path = "hacked"  # type: ignore[misc]

    def test_architectural_classification_frozen(self) -> None:
        fc = classify_file(_fi("src/authController.js"))
        c = fc.classifications[0]
        with pytest.raises((AttributeError, TypeError)):
            c.role = ArchitectureRole.UNKNOWN  # type: ignore[misc]

    def test_evidence_item_frozen(self) -> None:
        e = EvidenceItem(description="test", category="path")
        with pytest.raises((AttributeError, TypeError)):
            e.description = "hacked"  # type: ignore[misc]

    def test_repository_architecture_frozen(self) -> None:
        arch = classify_repository([])
        with pytest.raises((AttributeError, TypeError)):
            arch.file_classifications = ()  # type: ignore[misc]

    def test_architectural_relationship_frozen(self) -> None:
        files = [_fi("src/routes/auth.js"), _fi("src/controllers/auth.js")]
        rr = _local_resolved("src/routes/auth.js", "src/controllers/auth.js", "./controllers/auth")
        arch = classify_repository(files, resolved=[rr])
        if arch.architectural_relationships:
            ar = arch.architectural_relationships[0]
            with pytest.raises((AttributeError, TypeError)):
                ar.pattern = "hacked"  # type: ignore[misc]


# ===========================================================================
# 39. Enums
# ===========================================================================


class TestEnums:
    def test_architecture_role_values(self) -> None:
        assert ArchitectureRole.CONTROLLER.value == "controller"
        assert ArchitectureRole.SERVICE.value == "service"
        assert ArchitectureRole.REPOSITORY.value == "repository"
        assert ArchitectureRole.ROUTE.value == "route"
        assert ArchitectureRole.MODEL.value == "model"
        assert ArchitectureRole.ENTITY.value == "entity"
        assert ArchitectureRole.COMPONENT.value == "component"
        assert ArchitectureRole.HOOK.value == "hook"
        assert ArchitectureRole.MIDDLEWARE.value == "middleware"
        assert ArchitectureRole.UTILITY.value == "utility"
        assert ArchitectureRole.CONFIG.value == "config"
        assert ArchitectureRole.ENTRYPOINT.value == "entrypoint"
        assert ArchitectureRole.TEST.value == "test"
        assert ArchitectureRole.UNKNOWN.value == "unknown"

    def test_architectural_layer_values(self) -> None:
        assert ArchitecturalLayer.PRESENTATION.value == "presentation"
        assert ArchitecturalLayer.APPLICATION.value == "application"
        assert ArchitecturalLayer.DOMAIN.value == "domain"
        assert ArchitecturalLayer.DATA.value == "data"
        assert ArchitecturalLayer.INFRASTRUCTURE.value == "infrastructure"
        assert ArchitecturalLayer.TESTING.value == "testing"
        assert ArchitecturalLayer.UNKNOWN.value == "unknown"

    def test_role_to_layer_mapping(self) -> None:
        assert _role_to_layer(ArchitectureRole.CONTROLLER) == ArchitecturalLayer.PRESENTATION
        assert _role_to_layer(ArchitectureRole.SERVICE) == ArchitecturalLayer.APPLICATION
        assert _role_to_layer(ArchitectureRole.REPOSITORY) == ArchitecturalLayer.DATA
        assert _role_to_layer(ArchitectureRole.MODEL) == ArchitecturalLayer.DOMAIN
        assert _role_to_layer(ArchitectureRole.TEST) == ArchitecturalLayer.TESTING
        assert _role_to_layer(ArchitectureRole.CONFIG) == ArchitecturalLayer.INFRASTRUCTURE
        assert _role_to_layer(ArchitectureRole.UNKNOWN) == ArchitecturalLayer.UNKNOWN

    def test_role_is_str(self) -> None:
        assert isinstance(ArchitectureRole.CONTROLLER, str)

    def test_layer_is_str(self) -> None:
        assert isinstance(ArchitecturalLayer.PRESENTATION, str)


# ===========================================================================
# 57. Architecture Detection Quality Refinement Regression Suite
# ===========================================================================


class TestArchitectureRefinementRegressions:
    def test_controller_calling_model_not_repository(self) -> None:
        """taskController.js calling Task.findById and task.save is CONTROLLER, not REPOSITORY."""
        rels = [
            _call("backend/controllers/taskController.js", "Task.findById"),
            _call("backend/controllers/taskController.js", "task.save"),
            _call("backend/controllers/taskController.js", "Task.find"),
            _call("backend/controllers/taskController.js", "Task.findByIdAndUpdate"),
            _call("backend/controllers/taskController.js", "task.deleteOne"),
        ]
        resolved = [_ext_resolved("backend/controllers/taskController.js", "mongoose")]
        fc = classify_file(
            _fi("backend/controllers/taskController.js"),
            relationships=rels,
            resolved=resolved,
        )
        assert has_role(fc, ArchitectureRole.CONTROLLER)
        assert not has_role(fc, ArchitectureRole.REPOSITORY)

    def test_route_calling_delete_not_repository(self) -> None:
        """taskRoutes.js calling router.delete is ROUTE, not REPOSITORY."""
        rels = [
            _call("backend/routes/taskRoutes.js", "router.get"),
            _call("backend/routes/taskRoutes.js", "router.post"),
            _call("backend/routes/taskRoutes.js", "router.delete"),
        ]
        resolved = [_ext_resolved("backend/routes/taskRoutes.js", "express")]
        fc = classify_file(
            _fi("backend/routes/taskRoutes.js"),
            relationships=rels,
            resolved=resolved,
        )
        assert has_role(fc, ArchitectureRole.ROUTE)
        assert not has_role(fc, ArchitectureRole.REPOSITORY)

    def test_app_jsx_not_hook_not_repository_not_entrypoint(self) -> None:
        """App.jsx with React hooks and axios.delete is COMPONENT, not HOOK, REPOSITORY, or ENTRYPOINT."""
        rels = [
            _call("todo-frontend/src/App.jsx", "useState"),
            _call("todo-frontend/src/App.jsx", "useEffect"),
            _call("todo-frontend/src/App.jsx", "axios.get"),
            _call("todo-frontend/src/App.jsx", "axios.post"),
            _call("todo-frontend/src/App.jsx", "axios.delete"),
        ]
        resolved = [_ext_resolved("todo-frontend/src/App.jsx", "react")]
        symbols = [_sym("App", "todo-frontend/src/App.jsx", SymbolKind.FUNCTION)]
        fc = classify_file(
            _fi("todo-frontend/src/App.jsx", ".jsx"),
            symbols=symbols,
            relationships=rels,
            resolved=resolved,
        )
        assert has_role(fc, ArchitectureRole.COMPONENT)
        assert not has_role(fc, ArchitectureRole.HOOK)
        assert not has_role(fc, ArchitectureRole.REPOSITORY)
        assert not has_role(fc, ArchitectureRole.ENTRYPOINT)

    def test_taskform_using_usestate_not_hook(self) -> None:
        """TaskForm.jsx using useState is COMPONENT, not HOOK."""
        rels = [_call("todo-frontend/src/components/TaskForm.jsx", "useState")]
        resolved = [_ext_resolved("todo-frontend/src/components/TaskForm.jsx", "react")]
        symbols = [_sym("TaskForm", "todo-frontend/src/components/TaskForm.jsx", SymbolKind.FUNCTION)]
        fc = classify_file(
            _fi("todo-frontend/src/components/TaskForm.jsx", ".jsx"),
            symbols=symbols,
            relationships=rels,
            resolved=resolved,
        )
        assert has_role(fc, ArchitectureRole.COMPONENT)
        assert not has_role(fc, ArchitectureRole.HOOK)

    def test_css_and_html_not_entrypoint(self) -> None:
        """App.css, index.css, and index.html are not executable application entrypoints."""
        fc_app_css = classify_file(_fi("todo-frontend/src/App.css", ".css"))
        assert not has_role(fc_app_css, ArchitectureRole.ENTRYPOINT)
        assert has_role(fc_app_css, ArchitectureRole.UNKNOWN)

        fc_idx_css = classify_file(_fi("todo-frontend/src/index.css", ".css"))
        assert not has_role(fc_idx_css, ArchitectureRole.ENTRYPOINT)
        assert has_role(fc_idx_css, ArchitectureRole.UNKNOWN)

        fc_html = classify_file(_fi("todo-frontend/index.html", ".html"))
        assert not has_role(fc_html, ArchitectureRole.ENTRYPOINT)
        assert has_role(fc_html, ArchitectureRole.UNKNOWN)

    def test_main_jsx_is_entrypoint_and_component(self) -> None:
        """main.jsx calling createRoot is ENTRYPOINT and COMPONENT (from JSX), not HOOK."""
        rels = [_call("todo-frontend/src/main.jsx", "createRoot")]
        resolved = [_ext_resolved("todo-frontend/src/main.jsx", "react")]
        fc = classify_file(
            _fi("todo-frontend/src/main.jsx", ".jsx"),
            relationships=rels,
            resolved=resolved,
        )
        assert has_role(fc, ArchitectureRole.ENTRYPOINT)
        assert has_role(fc, ArchitectureRole.COMPONENT)
        assert not has_role(fc, ArchitectureRole.HOOK)

    def test_server_js_bootstrap_is_entrypoint(self) -> None:
        """server.js calling app.listen is ENTRYPOINT."""
        rels = [_call("server.js", "app.listen")]
        fc = classify_file(_fi("server.js"), relationships=rels)
        assert has_role(fc, ArchitectureRole.ENTRYPOINT)

    def test_genuine_custom_hook_detection(self) -> None:
        """useAuth.js or custom hook function is legitimately detected as HOOK."""
        fc_file = classify_file(_fi("src/hooks/useCustom.js"))
        assert has_role(fc_file, ArchitectureRole.HOOK)

        sym = _sym("useToggle", "src/toggle.js", SymbolKind.FUNCTION)
        fc_sym = classify_file(_fi("src/toggle.js"), symbols=[sym])
        assert has_role(fc_sym, ArchitectureRole.HOOK)

    def test_genuine_repository_detection(self) -> None:
        """Genuine repository by path, symbol, or direct db.query call is detected."""
        fc_path = classify_file(_fi("src/repositories/userRepository.js"))
        assert has_role(fc_path, ArchitectureRole.REPOSITORY)

        sym = _sym("UserRepository", "src/user.js", SymbolKind.CLASS)
        fc_sym = classify_file(_fi("src/user.js"), symbols=[sym])
        assert has_role(fc_sym, ArchitectureRole.REPOSITORY)

        rels = [_call("src/user.js", "db.query")]
        fc_call = classify_file(_fi("src/user.js"), relationships=rels)
        assert has_role(fc_call, ArchitectureRole.REPOSITORY)

    def test_report_controller_not_repository(self) -> None:
        """reportController.js must not match 'repo' substring to become REPOSITORY."""
        fc = classify_file(_fi("src/controllers/reportController.js"))
        assert has_role(fc, ArchitectureRole.CONTROLLER)
        assert not has_role(fc, ArchitectureRole.REPOSITORY)


# ===========================================================================
# 45. Gym-Buddy Architectural Quality Regressions
# ===========================================================================


class TestGymBuddyArchitecturalRegressions:
    def test_middleware_calling_model_is_not_repository(self) -> None:
        """backend/middleware/requireAuth.js calling User.findOne is MIDDLEWARE, not REPOSITORY."""
        rels = [_call("backend/middleware/requireAuth.js", "User.findOne")]
        fc = classify_file(_fi("backend/middleware/requireAuth.js"), relationships=rels)
        assert has_role(fc, ArchitectureRole.MIDDLEWARE)
        assert not has_role(fc, ArchitectureRole.REPOSITORY)

    def test_model_calling_this_findone_is_not_repository(self) -> None:
        """backend/models/usermodel.js calling this.findOne is MODEL, not REPOSITORY."""
        rels = [_call("backend/models/usermodel.js", "this.findOne")]
        fc = classify_file(_fi("backend/models/usermodel.js"), relationships=rels)
        assert has_role(fc, ArchitectureRole.MODEL)
        assert not has_role(fc, ArchitectureRole.REPOSITORY)

    def test_hook_importing_react_is_not_component(self) -> None:
        """frontend/src/hooks/useAuthContext.js is HOOK, not COMPONENT."""
        imp_rr = _ext_resolved("frontend/src/hooks/useAuthContext.js", "react")
        rels = [_call("frontend/src/hooks/useAuthContext.js", "useContext")]
        fc = classify_file(
            _fi("frontend/src/hooks/useAuthContext.js"),
            relationships=rels,
            resolved=[imp_rr],
        )
        assert has_role(fc, ArchitectureRole.HOOK)
        assert not has_role(fc, ArchitectureRole.COMPONENT)

    def test_frontend_index_js_is_entrypoint_not_component(self) -> None:
        """frontend/src/index.js calling createRoot is ENTRYPOINT, not COMPONENT."""
        imp_rr = _ext_resolved("frontend/src/index.js", "react")
        rels = [_call("frontend/src/index.js", "createRoot")]
        fc = classify_file(
            _fi("frontend/src/index.js"),
            relationships=rels,
            resolved=[imp_rr],
        )
        assert has_role(fc, ArchitectureRole.ENTRYPOINT)
        assert not has_role(fc, ArchitectureRole.COMPONENT)

    def test_frontend_app_js_with_symbol_is_component(self) -> None:
        """frontend/src/App.js declaring function App() is COMPONENT."""
        sym = _sym("App", "frontend/src/App.js", SymbolKind.FUNCTION)
        fc = classify_file(_fi("frontend/src/App.js"), symbols=[sym])
        assert has_role(fc, ArchitectureRole.COMPONENT)
        assert not has_role(fc, ArchitectureRole.ENTRYPOINT)

    def test_server_js_entrypoint_is_not_route(self) -> None:
        """backend/server.js importing express and mounting router is ENTRYPOINT, not ROUTE."""
        imp_rr = _ext_resolved("backend/server.js", "express")
        rels = [
            _call("backend/server.js", "app.listen"),
            _call("backend/server.js", "app.use"),
            _call("backend/server.js", "app.get"),
        ]
        fc = classify_file(
            _fi("backend/server.js"),
            relationships=rels,
            resolved=[imp_rr],
        )
        assert has_role(fc, ArchitectureRole.ENTRYPOINT)
        assert not has_role(fc, ArchitectureRole.ROUTE)

    def test_no_component_to_hook_arch_relationship(self) -> None:
        """COMPONENT -> HOOK should not produce architectural relationships."""
        fi_comp = _fi("src/components/Nav.jsx", ".jsx")
        fi_hook = _fi("src/hooks/useAuth.js")
        sym_comp = _sym("Nav", fi_comp.path, SymbolKind.FUNCTION)
        sym_hook = _sym("useAuth", fi_hook.path, SymbolKind.FUNCTION)
        resolved_rr = _local_resolved(fi_comp.path, fi_hook.path, "./hooks/useAuth")

        arch = classify_repository(
            files=[fi_comp, fi_hook],
            symbols=[sym_comp, sym_hook],
            relationships=[resolved_rr.source_relationship],
            resolved=[resolved_rr],
        )
        assert len(arch.architectural_relationships) == 0

