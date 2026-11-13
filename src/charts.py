import plotly.express as px
import pandas as pd

def bar_chart(df, x, y, title, color=None):
    if df.empty or x not in df or y not in df:
        return None
    grouped = df.groupby(x, dropna=False)[y].sum().reset_index().sort_values(y, ascending=False)
    return px.bar(grouped, x=x, y=y, color=color if color in grouped.columns else None,
                  title=title, text_auto=".2s")

def line_chart(df, x, y, title, color=None):
    if df.empty or x not in df or y not in df:
        return None
    grouped = df.groupby([x] + ([color] if color and color in df.columns else []), dropna=False)[y].sum().reset_index()
    return px.line(grouped, x=x, y=y, color=color if color in grouped.columns else None,
                   markers=True, title=title)
