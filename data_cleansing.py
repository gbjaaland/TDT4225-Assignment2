from DbConnector import DbConnector
import json
import pandas as pd
from haversine import haversine, Unit

MAX_SPEED_KMH = 200
MAX_STEP_M = MAX_SPEED_KMH / 3.6 * 15   # lengste lovlige steg på 15 sek, ca. 833 m
MAX_DURATION_S = 2 * 3600               # turer lengre enn dette sjekkes for glemt taxameter
MIN_AVG_SPEED_KMH = 10                  # lange turer under denne snittfarten fjernes
BATCH_SIZE = 5000


def trip_distance_km(polyline):
    dist_m = 0.0
    for (lon1, lat1), (lon2, lat2) in zip(polyline, polyline[1:]):
        step = haversine((lat1, lon1), (lat2, lon2), unit=Unit.METERS)
        if step <= MAX_STEP_M:          # hopp over GPS-feil
            dist_m += step
    return dist_m / 1000


def load_and_clean(path="porto.csv", nrows=None):
    df = pd.read_csv(path, nrows=nrows)
    start_count = len(df)
    before = len(df)
    df = df[~df["TRIP_ID"].duplicated(keep=False)]
    print(f"Removed {before - len(df):,} trips with duplicated TRIP_ID")
    before = len(df)
    df = df[~df["MISSING_DATA"]] 
    print(f"Removed {before - len(df):,} trips with missing data")
    df = df.drop(columns=["DAY_TYPE", "MISSING_DATA"])
    df["N_POINTS"] = df["POLYLINE"].str.count(r"\[") - 1
    before = len(df)
    df = df[df["N_POINTS"] >= 2]  
    print(f"Removed {before - len(df):,} trips with less than 2 points in polyline.")
    df["DURATION_S"] = (df["N_POINTS"] - 1).clip(lower=0) * 15

    # Turer over 2 timer med lav snittfart regnes som glemt taxameter og fjernes
    lange = df["DURATION_S"] > MAX_DURATION_S
    dist = df.loc[lange, "POLYLINE"].apply(lambda p: trip_distance_km(json.loads(p)))
    snittfart = dist / (df.loc[lange, "DURATION_S"] / 3600)
    glemt = snittfart[snittfart < MIN_AVG_SPEED_KMH].index
    df = df.drop(index=glemt)
    print(f"Removed {len(glemt):,} trips over 2 hours with average speed under {MIN_AVG_SPEED_KMH} km/h")
    
    #fjerner turer kortere enn 50 m TODO
    #before = len(df) 
    #df = df[df["DISTANCE_KM"]< 0.05]
    #print(f"Removed {before - len(df):,} trips shorter than 50m.")
    
    # Unix-tid (UTC) -> lokal Porto-tid
    start = (pd.to_datetime(df["TIMESTAMP"], unit="s", utc=True)
               .dt.tz_convert("Europe/Lisbon").dt.tz_localize(None))
    df["START_TIME"] = start
    df["END_TIME"] = start + pd.to_timedelta(df["DURATION_S"], unit="s")
    print(f"Rows before cleansing: {start_count:,} | after: {len(df):,}")

    return df


def to_int_or_none(value):
    return None if pd.isna(value) else int(value)


def build_trip_row(row):
    polyl = json.loads(row.POLYLINE)
    dist_km = trip_distance_km(polyl)
    if polyl:
        lons = [p[0] for p in polyl]
        lats = [p[1] for p in polyl]
        start_lon, start_lat = polyl[0]
        end_lon, end_lat = polyl[-1]
        bbox = (min(lons), max(lons), min(lats), max(lats))
    else:
        start_lon = start_lat = end_lon = end_lat = None
        bbox = (None, None, None, None)
    return (
        int(row.TRIP_ID), int(row.TAXI_ID), row.CALL_TYPE,
        to_int_or_none(row.ORIGIN_CALL), to_int_or_none(row.ORIGIN_STAND),
        row.START_TIME.to_pydatetime(), row.END_TIME.to_pydatetime(),
        int(row.N_POINTS), int(row.DURATION_S), round(dist_km, 4),
        start_lon, start_lat, end_lon, end_lat, *bbox,
        row.POLYLINE,
    )


class DataCleansing:

    def __init__(self):
        self.connection = DbConnector()
        self.db_connection = self.connection.db_connection
        self.cursor = self.connection.cursor

    def create_table(self):
        query1 = """
            CREATE TABLE IF NOT EXISTS Taxi (
                taxi_id INT NOT NULL,
                PRIMARY KEY (taxi_id)
            )
        """
        query2 = """
            CREATE TABLE IF NOT EXISTS Trip (
                trip_id      BIGINT   NOT NULL,
                taxi_id      INT      NOT NULL,
                call_type    CHAR(1)  NOT NULL,
                origin_call  INT      NULL,
                origin_stand INT      NULL,
                start_time   DATETIME NOT NULL,
                end_time     DATETIME NOT NULL,
                n_points     INT      NOT NULL,
                duration_s   INT      NOT NULL,
                distance_km  DOUBLE   NOT NULL,
                start_lon DOUBLE NULL, start_lat DOUBLE NULL,
                end_lon   DOUBLE NULL, end_lat   DOUBLE NULL,
                min_lon   DOUBLE NULL, max_lon   DOUBLE NULL,
                min_lat   DOUBLE NULL, max_lat   DOUBLE NULL,
                polyline  JSON     NOT NULL,
                PRIMARY KEY (trip_id),
                FOREIGN KEY (taxi_id) REFERENCES Taxi(taxi_id) ON DELETE CASCADE,
                INDEX idx_taxi_time (taxi_id, start_time),
                INDEX idx_start_time (start_time)
            )
        """
        self.cursor.execute(query1)
        self.cursor.execute(query2)
        self.db_connection.commit()
        print("Tables are created")

    def drop_tables(self):
        # Trip først, fordi den peker på Taxi
        self.cursor.execute("DROP TABLE IF EXISTS Trip")
        self.cursor.execute("DROP TABLE IF EXISTS Taxi")
        self.db_connection.commit()

    def insert_taxis(self, df):
        taxis = [(int(t),) for t in df["TAXI_ID"].unique()]
        self.cursor.executemany("INSERT IGNORE INTO Taxi (taxi_id) VALUES (%s)", taxis)
        self.db_connection.commit()
        print(f"{len(taxis)} taxis inserted")

    def insert_trips(self, df):
        sql = """
            INSERT INTO Trip (trip_id, taxi_id, call_type, origin_call, origin_stand,
                start_time, end_time, n_points, duration_s, distance_km,
                start_lon, start_lat, end_lon, end_lat,
                min_lon, max_lon, min_lat, max_lat, polyline)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        # Steg 1: gjør alle turene om til rader
        rows = [build_trip_row(row) for row in df.itertuples(index=False)]

        # Steg 2: send dem til databasen, 5000 om gangen
        for i in range(0, len(rows), BATCH_SIZE):
            self.cursor.executemany(sql, rows[i:i + BATCH_SIZE])
            self.db_connection.commit()
            print(f"{min(i + BATCH_SIZE, len(rows)):,} av {len(rows):,} trips inserted", end="\r")
        print(f"\Done: {len(rows):,} trips inserted")


def main():
    program = DataCleansing()
    program.drop_tables()
    program.create_table()
    df = load_and_clean(nrows=None)  
    program.insert_taxis(df)
    program.insert_trips(df)
    program.connection.close_connection()


if __name__ == "__main__":
    main()