import requests

code = """
def solve(data):
    import numpy as np
    a = np.array(data, dtype=np.int64)
    a.sort()
    return a.tolist()
"""

r = requests.post('https://web-production-ed55.up.railway.app/api/submit',
    json={'challenge_id': 'sort-speed', 'code': code, 'agent_name': 'Manual_Test'})
d = r.json()
print(f"Score: {d.get('score', 'Error')}")
print(f"Global best: {d.get('global_best_score', '?')}")