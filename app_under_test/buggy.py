import random

def divide(a, b):
    return a / b

# def get_user(user_id: int):
#     # Simulate an environment dependency issue (e.g., DB/network timeout)
#     raise TimeoutError("DB timeout while fetching user")

def get_user(user_id: int):
    if random.random() < 0.5:
        raise TimeoutError("DB timeout while fetching user")

def parse_user(data: dict):
    # Simulate code bug (KeyError)
    return data["name"]
