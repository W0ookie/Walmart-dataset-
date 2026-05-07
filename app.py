from __future__ import annotations

import dash
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Input, Output, dcc, html

from data_logic import (
    build_state_summary,
    load_population,
    load_retail_sales,
    load_segment_sales,
    load_store_locations,
    load_weekly_sales,
)


stores = load_store_locations()
population = load_population()
state_summary = build_state_summary(stores, population)
retail_sales = load_retail_sales()
weekly_sales = load_weekly_sales()
segment_sales = load_segment_sales()

stores["Brand"] = stores["Type"].map({"Retail": "Walmart", "Wholesale": "Sam's Club"}).fillna(
    stores["Type"]
)

STORE_TYPES = sorted(stores["Type"].dropna().unique())
TYPE_LABELS = {"Retail": "Walmart", "Wholesale": "Sam's Club"}
STATE_OPTIONS = [{"label": "All states", "value": "ALL"}] + [
    {"label": state, "value": state} for state in sorted(stores["State"].unique())
]
BRAND_COLORS = {"Walmart": "#2563eb", "Sam's Club": "#f97316"}
SEGMENT_COLORS = {
    "Walmart U.S. / Wal-Mart Stores": "#2563eb",
    "Walmart U.S.": "#2563eb",
    "Sam's Club U.S.": "#f97316",
}
WHITE_GREEN_SCALE = [
    [0.0, "#ffffff"],
    [0.18, "#edf8e9"],
    [0.42, "#bae4b3"],
    [0.68, "#74c476"],
    [1.0, "#238b45"],
]

THEME = {
    "paper_bgcolor": "#f7f8f4",
    "plot_bgcolor": "#ffffff",
    "font": {"family": "Segoe UI, Arial, sans-serif", "color": "#18211f"},
    "margin": {"l": 40, "r": 24, "t": 56, "b": 40},
}


def apply_chart_theme(fig: go.Figure) -> go.Figure:
    fig.update_layout(**THEME)
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="#e5e7dc", zeroline=False)
    return fig


def metric_card(label: str, value: str, detail: str) -> html.Div:
    return html.Div(
        className="metric-card",
        children=[
            html.Div(label, className="metric-label"),
            html.Div(value, className="metric-value"),
            html.Div(detail, className="metric-detail"),
        ],
    )


app = dash.Dash(__name__)
app.title = "Walmart Local Dashboard"

app.layout = html.Div(
    className="app-shell",
    children=[
        html.Header(
            className="topbar",
            children=[
                html.Div(
                    [
                        html.P("Walmart and Sam's Club analytics", className="eyebrow"),
                        html.H1("Walmart/ Sams Club Retail Analysis"),
                    ]
                ),
                html.Div(
                    className="filters",
                    children=[
                        html.Label("State"),
                        dcc.Dropdown(
                            id="state-filter",
                            options=STATE_OPTIONS,
                            value="ALL",
                            clearable=False,
                            className="dropdown",
                        ),
                        html.Label("Store type"),
                        dcc.Checklist(
                            id="type-filter",
                            options=[
                                {"label": TYPE_LABELS.get(value, value), "value": value}
                                for value in STORE_TYPES
                            ],
                            value=STORE_TYPES,
                            inline=True,
                            className="checklist",
                        ),
                    ],
                ),
            ],
        ),
        html.Main(
            [
                html.Section(id="metric-row", className="metric-row"),
                html.Section(
                    className="grid two",
                    children=[
                        html.Div(dcc.Graph(id="location-map"), className="panel map-panel"),
                        html.Div(dcc.Graph(id="type-share"), className="panel"),
                    ],
                ),
                html.Section(
                    className="grid two",
                    children=[
                        html.Div(dcc.Graph(id="state-map"), className="panel"),
                        html.Div(dcc.Graph(id="top-states"), className="panel"),
                    ],
                ),
                html.Section(
                    className="grid two",
                    children=[
                        html.Div(dcc.Graph(id="segment-sales"), className="panel"),
                        html.Div(dcc.Graph(id="weekly-sales"), className="panel"),
                    ],
                ),
                html.Section(
                    className="grid one",
                    children=[html.Div(dcc.Graph(id="retail-sales"), className="panel")],
                ),
            ]
        ),
    ],
)


@app.callback(
    Output("metric-row", "children"),
    Output("location-map", "figure"),
    Output("type-share", "figure"),
    Output("state-map", "figure"),
    Output("top-states", "figure"),
    Output("segment-sales", "figure"),
    Output("weekly-sales", "figure"),
    Output("retail-sales", "figure"),
    Input("state-filter", "value"),
    Input("type-filter", "value"),
)
def update_dashboard(selected_state: str, selected_types: list[str]):
    selected_types = selected_types or STORE_TYPES
    filtered = stores[stores["Type"].isin(selected_types)].copy()
    if selected_state != "ALL":
        filtered = filtered[filtered["State"] == selected_state]

    filtered_summary = build_state_summary(filtered, population)
    total_locations = len(filtered)
    open_locations = int(filtered["is_open"].sum()) if total_locations else 0
    state_count = filtered["State"].nunique()
    top_state = (
        filtered_summary.sort_values("walmart_store_count", ascending=False).iloc[0]
        if not filtered_summary.empty
        else None
    )

    metrics = [
        metric_card("Locations", f"{total_locations:,}", "Filtered store records"),
        metric_card("Open locations", f"{open_locations:,}", "Currently marked open"),
        metric_card("States covered", f"{state_count:,}", "States and territories"),
        metric_card(
            "Top state",
            top_state["State"] if top_state is not None else "N/A",
            f"{int(top_state['walmart_store_count']):,} locations"
            if top_state is not None
            else "No filtered records",
        ),
    ]

    location_map = px.scatter_geo(
        filtered,
        lat="latitude",
        lon="longitude",
        hover_name="businessUnit_name",
        custom_data=["Type", "Description", "Address", "City", "State"],
        color="Brand",
        scope="usa",
        title="Store Locations",
        height=610,
        color_discrete_map=BRAND_COLORS,
    )
    location_map.update_traces(
        marker={"size": 4.5, "opacity": 0.68},
        hovertemplate=(
            "<b>%{hovertext}</b><br>"
            "Type: %{customdata[0]}<br>"
            "Name: %{customdata[1]}<br>"
            "Address: %{customdata[2]}<br>"
            "City: %{customdata[3]}<br>"
            "State: %{customdata[4]}"
            "<extra></extra>"
        ),
    )
    location_map.update_geos(bgcolor="#f7f8f4", lakecolor="#d7ebe7", landcolor="#f0f2eb")
    apply_chart_theme(location_map)

    type_counts = (
        filtered["Brand"].value_counts().rename_axis("brand").reset_index(name="count")
    )
    type_share = px.pie(
        type_counts,
        names="brand",
        values="count",
        hole=0.52,
        title="Location Mix",
        color="brand",
        color_discrete_map=BRAND_COLORS,
    )
    type_share.update_traces(textinfo="percent+label", hovertemplate="%{label}: %{value:,}<extra></extra>")
    apply_chart_theme(type_share)

    metric_column = "stores_per_100k" if selected_state == "ALL" else "walmart_store_count"
    state_title = (
        "Locations per 100,000 People by State"
        if metric_column == "stores_per_100k"
        else "Filtered Locations by State"
    )
    state_map = px.choropleth(
        filtered_summary,
        locations="State",
        locationmode="USA-states",
        color=metric_column,
        scope="usa",
        hover_name="state",
        hover_data={
            "State": False,
            "walmart_store_count": ":,",
            "population_2025": ":,",
            "stores_per_100k": ":.2f",
        },
        color_continuous_scale=WHITE_GREEN_SCALE,
        title=state_title,
        height=430,
        labels={
            "walmart_store_count": "Store Count",
            "population_2025": "Population 2025",
            "stores_per_100k": "Stores Per 100k",
        },
    )
    state_map.update_geos(bgcolor="#f7f8f4", lakecolor="#d7ebe7", landcolor="#f0f2eb")
    apply_chart_theme(state_map)

    top_states_data = filtered_summary.nlargest(12, "walmart_store_count").sort_values(
        "walmart_store_count"
    )
    top_states = px.bar(
        top_states_data,
        x="walmart_store_count",
        y="State",
        orientation="h",
        text="walmart_store_count",
        title="Top States by Filtered Locations",
        color="stores_per_100k",
        color_continuous_scale=WHITE_GREEN_SCALE,
        labels={
            "walmart_store_count": "Store Count",
            "stores_per_100k": "Stores Per 100k",
            "State": "State",
        },
    )
    top_states.update_traces(texttemplate="%{text:,}", textposition="outside", cliponaxis=False)
    apply_chart_theme(top_states)

    segment_fig = px.line(
        segment_sales,
        x="fiscal_year_end_year",
        y="net_sales_billions_usd",
        color="segment",
        markers=True,
        title="Walmart U.S. and Sam's Club Net Sales",
        labels={
            "fiscal_year_end_year": "Fiscal year",
            "net_sales_billions_usd": "Net sales, billions USD",
            "segment": "Segment",
        },
        color_discrete_map=SEGMENT_COLORS,
    )
    segment_fig.update_traces(hovertemplate="%{fullData.name}<br>FY %{x}: $%{y:.1f}B<extra></extra>")
    apply_chart_theme(segment_fig)

    weekly_monthly = (
        weekly_sales.set_index("Date")
        .resample("ME")
        .agg(weekly_sales=("Weekly_Sales", "sum"), fuel_price=("Fuel_Price", "mean"))
        .reset_index()
    )
    weekly_fig = px.line(
        weekly_monthly,
        x="Date",
        y="weekly_sales",
        title="Walmart Dataset Monthly Sales",
        labels={"Date": "Date", "weekly_sales": "Monthly sales"},
        color_discrete_sequence=["#166534"],
    )
    weekly_fig.update_traces(hovertemplate="%{x|%b %Y}<br>Sales: $%{y:,.0f}<extra></extra>")
    apply_chart_theme(weekly_fig)

    retail_fig = px.line(
        retail_sales,
        x="date",
        y="retail_sales",
        title="U.S. Retail Sales Over Time",
        labels={"date": "Date", "retail_sales": "Retail sales"},
        color_discrete_sequence=["#334155"],
    )
    retail_fig.update_traces(hovertemplate="%{x|%b %Y}<br>Retail sales: %{y:,.0f}<extra></extra>")
    apply_chart_theme(retail_fig)

    return (
        metrics,
        location_map,
        type_share,
        state_map,
        top_states,
        segment_fig,
        weekly_fig,
        retail_fig,
    )


if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=8050)
