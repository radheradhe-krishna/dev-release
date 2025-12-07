import pandas as pd

class SafeDict(dict):
    def __missing__(self, key):
        return "N/A"

def sanitize(value):
    if pd.isna(value) or value in ("", None):
        return "N/A"
    return value