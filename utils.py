import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
from haversine import haversine_vector, Unit

# Constants
CENTER_LAT, CENTER_LON = 41.15794, -8.62911                 # Porto City Hall
SAMPLING_INTERVAL_S = 15                                    # one GPS point every 15 seconds
MAX_SPEED_KMH = 200                                         # faster than this between two points = GPS jump
MAX_STEP_M = MAX_SPEED_KMH / 3.6 * SAMPLING_INTERVAL_S      # longest realistic step, about 833 m
SAMPLE_SIZE = 100_000                                       # trips used in the point-level GPS analysis
SPEED_THRESHOLD = 50                                        # average speed threshold used to narrow the search for trips with GPS faults
MAX_DURATION_S = 2 * 3600                                   # trips longer than this are checked for average speed
MIN_AVG_SPEED_KMH = 10                                      # long trips with lower average speed than this are removed
BATCH_SIZE = 5000

# Functions
def polylines_to_points(trips):
    #Turns trips into one row per GPS point, with TRIP_ID, LONGITUDE and LATITUDE
    pts = trips[["TRIP_ID", "POLYLINE"]].copy()
    pts["POLYLINE"] = pts["POLYLINE"].apply(json.loads)       # text -> list
    pts = pts.explode("POLYLINE", ignore_index=True)          # one row per point
    pts["POINT_NR"] = pts.groupby("TRIP_ID").cumcount()       # original position in the trip
    pts["LONGITUDE"] = pts["POLYLINE"].str[0].astype(float)
    pts["LATITUDE"] = pts["POLYLINE"].str[1].astype(float)
    return pts.drop(columns="POLYLINE")


def calculate_steps(pts, max_speed_kmh=MAX_SPEED_KMH):
    #Adds step length (m), speed (km/h) and a jump flag for each point.
    #The step is the distance from the previous point in the same trip.
    g = pts.groupby("TRIP_ID")
    previous = g[["LATITUDE", "LONGITUDE"]].shift()
    pts["STEP_M"] = haversine_vector(previous.to_numpy(), pts[["LATITUDE", "LONGITUDE"]].to_numpy(), Unit.METERS)
    gap = pts["POINT_NR"] - g["POINT_NR"].shift() if "POINT_NR" in pts else 1 # add gap to handle later removal of points
    pts["SPEED_KMH"] = pts["STEP_M"] / (gap * SAMPLING_INTERVAL_S) * 3.6
    pts["JUMP"] = pts["SPEED_KMH"] > max_speed_kmh
    return pts

def classify_bad_points(pts, max_step_m):
    # Add ERROR_TYPE and UNEXPLAINED_JUMP columns. Returns a new DataFrame
    pts = pts.copy()
    g = pts.groupby("TRIP_ID")
    point_nr = g.cumcount()
    n_points = g["LONGITUDE"].transform("size")

    jump_in = pts["JUMP"]
    jump_out = g["JUMP"].shift(-1, fill_value=False)
    jump_after_next = g["JUMP"].shift(-2, fill_value=False)
    jump_before = g["JUMP"].shift(1, fill_value=False)

    previous = g[["LATITUDE", "LONGITUDE"]].shift(1)
    following = g[["LATITUDE", "LONGITUDE"]].shift(-1)
    previous_to_next_m = haversine_vector(previous.to_numpy(), following.to_numpy(), Unit.METERS)

    pts["ERROR_TYPE"] = np.select(
        [
            (point_nr == 0) & jump_out & ~jump_after_next,
            (point_nr == n_points - 1) & jump_in & ~jump_before,
            jump_in & jump_out & (previous_to_next_m <= 2 * max_step_m),
        ],
        ["first point", "last point", "spike"],
        default="",
    )

    # A jump is explained if this point, or the one before it, is a bad point
    is_bad = pts["ERROR_TYPE"] != ""
    previous_is_bad = g["ERROR_TYPE"].shift(1, fill_value="") != ""
    pts["UNEXPLAINED_JUMP"] = pts["JUMP"] & ~(is_bad | previous_is_bad)
    return pts

def remove_jumps(df, iterations=10):
    after = df.copy()
    for round_nr in range(1, iterations+1):
        bad = after["ERROR_TYPE"] != ""
        print(f"Round {round_nr}: removing {bad.sum():,} bad points")
        if not bad.any():
            break
        kept = after.loc[~bad, ["TRIP_ID", "POINT_NR","LONGITUDE", "LATITUDE"]].copy()
        after = classify_bad_points(calculate_steps(kept), MAX_STEP_M)
    return after

def remove_trips_with_jump(df):

    # trips that still have at least one jump after cleaning
    jumping_ids = df.loc[df["JUMP"], "TRIP_ID"].unique()

    # keep only the other trips
    df_ok = df[~df["TRIP_ID"].isin(jumping_ids)]
    
    print(f"Removed {len(df.TRIP_ID.unique().tolist())-len(df_ok.TRIP_ID.unique().tolist())} trips with jump")
    
    return df_ok

def rebuild_polylines(df_altered, original_df):
    # rebuild the polylines
    cleaned_polylines = (
        df_altered.assign(COORD=df_altered[["LONGITUDE", "LATITUDE"]].values.tolist())
        .groupby("TRIP_ID", sort=False)["COORD"].agg(list)
        .map(lambda c: json.dumps(c, separators=(",", ":")))   # creates a json like the original
        .rename("POLYLINE")
    )
    
    # trip table with the cleaned polylines instead of the original ones
    valid_after = (
        original_df[original_df["TRIP_ID"].isin(cleaned_polylines.index)]
        .drop(columns="POLYLINE")
        .join(cleaned_polylines, on="TRIP_ID")
    )

    return valid_after

def remove_gps_faults(df):
    # identify trips with average speed above SPEED_THRESHOLD
    df_altered = df.copy(deep=True)
    df_altered["AVG_SPEED"] = df_altered["DISTANCE_KM"] / (df_altered["DURATION_S"]/3600)
    speedy_trips = df_altered[df_altered["AVG_SPEED"] > SPEED_THRESHOLD].copy()
    print(f"Nr of trips with average speed above {SPEED_THRESHOLD}: {speedy_trips.shape[0]}")

    # identify speedy trips with jump
    speedy_trips_points = polylines_to_points(speedy_trips).copy()
    speedy_trips_steps = calculate_steps(speedy_trips_points).copy()
    before = classify_bad_points(speedy_trips_steps, MAX_STEP_M)
    
    # try removing the bad points and remove the trips which still have jump
    after = remove_jumps(before)
    after_ok = remove_trips_with_jump(after)
    valid_after = rebuild_polylines(after_ok, df_altered)
    
    # update the df
    speedy_ids = set(speedy_trips["TRIP_ID"])
    df_out = pd.concat(
        [df_altered[~df_altered["TRIP_ID"].isin(speedy_ids)], valid_after],
        ignore_index=True,
    )
    
    # remove trips with fewer than 2 points in case there are any
    n_points = df_out["POLYLINE"].str.count(r"\[") - 1           
    short_ids = set(df_out.loc[n_points < 2, "TRIP_ID"])
    df_out = df_out[n_points >= 2].reset_index(drop=True)

    # keep the original trip order
    order = {tid: i for i, tid in enumerate(df["TRIP_ID"])}
    df_out = (df_out.sort_values("TRIP_ID", key=lambda s: s.map(order)).reset_index(drop=True))

    # report statistics on removal
    removed_ids = set(df["TRIP_ID"]) - set(df_out["TRIP_ID"])
    removed_trips = df[df["TRIP_ID"].isin(removed_ids)]
    removed_trips = removed_trips.assign(
        REASON=np.select(
            [removed_trips["TRIP_ID"].isin(short_ids), removed_trips["TRIP_ID"].isin(after["TRIP_ID"])],
            ["too few points", "still jumping"],
            default="all points removed",
        )
    )
    print(removed_trips["REASON"].value_counts())
    broken_ids = set(before.loc[before["JUMP"], "TRIP_ID"])         # speedy trips that actually had jumps
    kept_ids = set(valid_after["TRIP_ID"])
    repaired = broken_ids & kept_ids                                # had jumps, fixed by removing points
    print(f"Repaired: {len(repaired)}, removed: {len(removed_ids)}")

    # return new df
    return df_out


# use city hall as reference for plots
CITY_HALL = dict(lat=CENTER_LAT, lon=CENTER_LON)

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

