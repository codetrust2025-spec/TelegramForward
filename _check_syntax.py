import ast
with open("features/candidate_store.py", encoding="utf-8") as f:
    source = f.read()
ast.parse(source)
print("SYNTAX OK")
