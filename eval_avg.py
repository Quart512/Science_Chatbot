import os
import json

path= './results'
log_list = os.listdir(path)
log_dict = {}

for log in log_list:
    with open (f'./results/{log}') as f:
        json_data=json.load(f)
        total_score=0
        for i in json_data:
            total_score+=i['score']
        average = total_score/len(json_data)
        log_dict[log] = average
print(log_dict)
