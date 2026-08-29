
import pandas as pd

TRAIN_END = pd.Timestamp("2023-08-08T04:48:00+00:00")
VALIDATION_END = pd.Timestamp("2024-10-19T14:24:00+00:00")
RESEARCH_END = pd.Timestamp("2026-01-01T00:00:00Z")

def chronological_split(df):
    x = df.loc[df.index < RESEARCH_END].copy()
    train = x.loc[x.index < TRAIN_END]
    validation = x.loc[(x.index >= TRAIN_END) & (x.index < VALIDATION_END)]
    test = x.loc[(x.index >= VALIDATION_END) & (x.index < RESEARCH_END)]
    return train, validation, test
