import random


PATTERN_UUID = "[A-Za-z0-9]|-|_"

UUID_SET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
def make_random_uuid(length: int):
    return "".join(random.choice(UUID_SET) for _ in range(length))