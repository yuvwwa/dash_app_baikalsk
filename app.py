import dash
from dash import dcc, html
from layout import HEADER_H
from callbacks import register_callbacks

app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "Байкальск. Дашборд"

app.index_string = '''
<!DOCTYPE html>
<html>
<head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    {%css%}
    <style>
        html, body {
            background-color: #FFFFFF !important;
            color: #000000 !important;
            font-family: "IBM Plex Sans", "Inter", sans-serif;
            margin: 0; padding: 0;
        }
        #react-entry-point, #_dash-app-content, .dash-renderer {
            background-color: #FFFFFF !important;
            min-height: 100vh;
        }
        /* Plotly SVG фон */
        .main-svg .bg { fill: #FFFFFF !important; }
        /* Все тексты на графиках */
        .xtick text, .ytick text, .gtitle,
        .legendtext, .annotation-text { fill: #000000 !important; }
        /* Загрузка */
        ._dash-loading { background-color: #FFFFFF !important; }
    </style>
</head>
<body>
    {%app_entry%}
    <footer>
        {%config%}
        {%scripts%}
        {%renderer%}
    </footer>
</body>
</html>
'''

app.layout = html.Div([
    html.Link(
        href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600&display=swap",
        rel="stylesheet",
    ),
    html.Div(id="app-header"),
    html.Div(id="page-content", style={"paddingTop": HEADER_H}),
    dcc.Store(id="active-tab",    data="transport"),
    dcc.Store(id="selected-stop", data=[]),
], style={
    "backgroundColor": "#FFFFFF",
    "color":           "#000000",
    "fontFamily":      "'IBM Plex Sans', sans-serif",
    "minHeight":       "100vh",
})

register_callbacks(app)

if __name__ == "__main__":
    app.run(debug=False, port=8050)