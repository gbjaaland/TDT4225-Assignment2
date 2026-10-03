import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import json

# bruk city hall som referansepunkt
CITY_HALL = dict(lat=41.15794, lon=-8.62911)

def plot_origin_stand(origin_stand, start_punkter):

    # plot all stands and all trips with stands for inspection
    fig = px.scatter_map(
        origin_stand,
        lat="LATITUDE",
        lon="LONGITUDE",
        custom_data="ORIGIN_STAND",
        center=CITY_HALL,
        zoom=11
    )

    fig.update_traces(
        name="Contains ORIGIN_STAND",
        marker=dict(size=18),
        hovertemplate=(
            "ORIGIN_STAND: %{customdata}<br>"
            "Lat: %{lat}<br>"
            "Lon: %{lon}"
            "<extra></extra>"
        ),
        selector=0
    )

    fig.add_trace(
        go.Scattermap(
            lat=start_punkter["LATITUDE"],
            lon=start_punkter["LONGITUDE"],
            mode="markers",
            name="Start of trip",
            marker=dict(size=8),
            customdata=start_punkter["TRIP_ID"],
            hovertemplate=(
                "TRIP_ID: %{customdata}<br>"
                "Lat: %{lat}<br>"
                "Lon: %{lon}"
                "<extra></extra>"
            )
        )
    )

    # Put legend on the right
    fig.update_layout(
        legend=dict(
            x=1.02,
            y=1,
            xanchor="left",
            yanchor="top"
        )
    )

    fig.show()
    
def plot_trip(df):
    df = df[["TRIP_ID", "POLYLINE"]].explode("POLYLINE").copy()

    df[["LONGITUDE", "LATITUDE"]] = pd.DataFrame(
        df["POLYLINE"].tolist(),
        index=df.index
    )

    df = df.drop(columns="POLYLINE").reset_index(drop=True)

    fig = go.Figure()

    for trip_id, trip in df.groupby("TRIP_ID"):

        trip = trip.reset_index(drop=True) # reset index to keep track ovof GPS data points

        fig.add_trace(
            go.Scattermap(
                lat=trip["LATITUDE"],
                lon=trip["LONGITUDE"],
                customdata=trip.index,
                mode="lines",
                name=str(trip_id),
                hovertemplate=(
                    f"Trip: {trip_id}<br>"
                    "GPS nr: %{customdata}<br>"
                    "Lat: %{lat}<br>"
                    "Lon: %{lon}"
                    "<extra></extra>"
                )
            )
        )

    fig.update_layout(
        map=dict(
            style="basic",
            zoom=12,
            center={
                "lat": CITY_HALL["lat"],
                "lon": CITY_HALL["lon"]
            }
        ),
        height=400,
        margin=dict(l=0, r=0, t=40, b=0),
        title="Trips"
    )

    fig.show()