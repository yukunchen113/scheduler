import os
import pickle


def load_from_cache(datestr: str, cache_base_file: str):
    cache_file = cache_base_file + datestr
    if not os.path.exists(cache_file):
        return {}
    with open(cache_file, "rb") as file:
        return pickle.load(file)


def save_to_cache(data: object, datestr: str, cache_base_file: str):
    cache_file = cache_base_file + datestr
    cache_basepath = os.path.dirname(cache_file)
    if not os.path.exists(cache_file):
        os.makedirs(cache_basepath, exist_ok=True)
    with open(cache_file, "wb") as file:
        pickle.dump(data, file)
    current_files = [
        os.path.join(cache_basepath, file) for file in os.listdir(cache_basepath)
    ]
    current_files = sorted(current_files, key=lambda file: os.path.getmtime(file))
    while len(current_files) > 10:
        os.remove(current_files.pop(0))
