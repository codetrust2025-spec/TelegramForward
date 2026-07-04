import ast
with open("features/candidate_store.py", encoding="utf-8") as f:
    ast.parse(f.read())
print("OK")
