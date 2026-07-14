import json
from pathlib import Path

path = Path(__file__).parent / "results"
log_list = [p.name for p in path.iterdir()]
log_dict = {}

for log in log_list:
    with open(path / log) as f:
        json_data = json.load(f)
        total_score = 0
        for i in json_data:
            total_score += i['score']
        average = total_score / len(json_data)
        log_dict[log] = average
print(log_dict)
