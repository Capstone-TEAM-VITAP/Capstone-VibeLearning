from app.chunking.code_chunker import chunk_code, get_language

def test_python_function():
    chunks = chunk_code("def greet(name):\n    return name\n", "python")
    assert any(c["symbol"] == "greet" and c["language"] == "python" for c in chunks)

def test_java_method():
    code = 'class UserService { public String findUser() { return "user"; } }'
    chunks = chunk_code(code, "java")
    assert any(c["symbol"] == "findUser" for c in chunks)

def test_javascript_function():
    chunks = chunk_code("function loginUser() { return true; }", "javascript")
    assert any(c["symbol"] == "loginUser" for c in chunks)

def test_typescript_class():
    chunks = chunk_code("class UserService { findUser(): string { return 'u'; } }", "typescript")
    assert any(c["symbol"] == "findUser" for c in chunks)

def test_cpp_function():
    chunks = chunk_code("int add(int a, int b) { return a + b; }", "cpp")
    assert any(c["symbol"] == "add" for c in chunks)

def test_extensions():
    assert get_language("main.py") == "python"
    assert get_language("Main.java") == "java"
    assert get_language("index.tsx") == "tsx"
    assert get_language("README.md") is None
