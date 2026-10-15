from pathlib import Path
from tree_sitter_language_pack import get_parser

EXTENSION_TO_LANGUAGE = {
    ".py": "python", ".java": "java",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "tsx",
    ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".hh": "cpp", ".hxx": "cpp",
}
DEFINITION_TYPES = {
    "python": {"function_definition": "function", "class_definition": "class"},
    "java": {"method_declaration": "method", "constructor_declaration": "constructor",
             "class_declaration": "class", "interface_declaration": "interface",
             "enum_declaration": "enum", "record_declaration": "record"},
    "javascript": {"function_declaration": "function", "generator_function_declaration": "function",
                   "method_definition": "method", "class_declaration": "class"},
    "typescript": {"function_declaration": "function", "generator_function_declaration": "function",
                   "method_definition": "method", "class_declaration": "class",
                   "interface_declaration": "interface", "enum_declaration": "enum",
                   "abstract_class_declaration": "class"},
    "tsx": {"function_declaration": "function", "generator_function_declaration": "function",
            "method_definition": "method", "class_declaration": "class",
            "interface_declaration": "interface", "enum_declaration": "enum"},
    "c": {"function_definition": "function", "struct_specifier": "struct",
          "enum_specifier": "enum", "type_definition": "type"},
    "cpp": {
    "function_definition": "function",
    "class_specifier": "class",
    "struct_specifier": "struct",
    "enum_specifier": "enum",
    "namespace_definition": "namespace",
    "alias_declaration": "type",
    "type_definition": "type",
},
}

def get_language(file_path):
    return EXTENSION_TO_LANGUAGE.get(Path(file_path).suffix.lower())

def _node_name(node, source_bytes):
    name_node = node.child_by_field_name("name")
    if name_node is not None:
        return source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace")
    for child in node.children:
        if child.type in {"identifier", "type_identifier", "field_identifier", "namespace_identifier", "operator_name"}:
            return source_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
    return f"anonymous_{node.start_point.row + 1}"

def chunk_code(source_code: str, language: str):
    if not isinstance(source_code, str):
        raise TypeError("source_code must be a string.")
    if language not in DEFINITION_TYPES or not source_code.strip():
        return []
    parser = get_parser(language)
    source_bytes = source_code.encode("utf-8")
    tree = parser.parse(source_bytes)
    chunks = []
    definitions = DEFINITION_TYPES[language]

    def visit(node):
        if node.type in definitions:
            code = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace").strip()
            if code:
                chunks.append({
                    "symbol": _node_name(node, source_bytes),
                    "type": definitions[node.type],
                    "code": code,
                    "language": language,
                    "start_line": node.start_point.row + 1,
                    "end_line": node.end_point.row + 1,
                })
        for child in node.children:
            visit(child)
    visit(tree.root_node)
    return chunks

def chunk_python_code(source_code):
    return chunk_code(source_code, "python")

def chunk_file(file_path, source_code=None):
    file_path = Path(file_path)
    language = get_language(file_path)
    if language is None:
        return []
    if source_code is None:
        source_code = file_path.read_text(encoding="utf-8", errors="replace")
    return chunk_code(source_code, language)
