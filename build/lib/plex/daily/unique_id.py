import random


PATTERN_UUID = "[A-Za-z0-9]|-|_|/"

# generated uuid is lowercase alpha numeric
# as large characters randomly generated are distracting.
UUID_SET = "abcdefghijklmnopqrstuvwxyz0123456789"
def make_random_uuid(length: int):
    return "".join(random.choice(UUID_SET) for _ in range(length))