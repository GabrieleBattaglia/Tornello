import ast

filename = 'e:/git/Mine/Tornello/tornello.py'
with open(filename, 'r', encoding='utf-8') as f:
    tree = ast.parse(f.read())

print('Functions in tornello.py:')
for node in tree.body:
    if isinstance(node, ast.FunctionDef):
        print(f'- {node.name}')
