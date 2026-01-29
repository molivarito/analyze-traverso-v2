import ast
import os
from pathlib import Path

def get_project_py_files(directory):
    return [f for f in os.listdir(directory) if f.endswith('.py')]

def get_local_imports(file_path, project_files):
    local_imports = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split('.')[0]
                    if f"{module_name}.py" in project_files:
                        local_imports.add(f"{module_name}.py")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.split('.')[0]
                    if f"{module_name}.py" in project_files:
                        local_imports.add(f"{module_name}.py")
                elif node.level > 0:
                    # Relative imports could be handled here if needed
                    pass
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
    
    return local_imports

def build_dependency_graph(directory):
    project_files = get_project_py_files(directory)
    graph = {}
    for py_file in project_files:
        graph[py_file] = get_local_imports(os.path.join(directory, py_file), project_files)
    return graph

def get_reachable_files(start_file, graph):
    reachable = set()
    stack = [start_file]
    while stack:
        current = stack.pop()
        if current not in reachable:
            reachable.add(current)
            if current in graph:
                for neighbor in graph[current]:
                    if neighbor not in reachable:
                        stack.append(neighbor)
    return reachable

def has_main_block(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            return 'if __name__ == "__main__":' in content or "if __name__ == '__main__':" in content
    except:
        return False

def analyze_project(directory, main_app):
    graph = build_dependency_graph(directory)
    project_files = get_project_py_files(directory)
    
    reachable_from_main = get_reachable_files(main_app, graph)
    
    independent_files = []
    other_entry_points = []
    
    for py_file in project_files:
        if py_file not in reachable_from_main:
            independent_files.append(py_file)
            if has_main_block(os.path.join(directory, py_file)):
                other_entry_points.append(py_file)
    
    print("Files REACHABLE from project main app:")
    for f in sorted(reachable_from_main):
        print(f"- {f}")
    
    print("\nIndependent files (NOT reachable from main app):")
    for f in sorted(independent_files):
        main_tag = "[ENTRY POINT]" if f in other_entry_points else ""
        print(f"- {f} {main_tag}")

if __name__ == "__main__":
    analyze_project('.', 'unified_flute_gui_qt.py')
