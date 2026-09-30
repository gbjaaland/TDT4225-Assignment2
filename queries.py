import json
from haversine import haversine, inverse_haversine, Direction, Unit
from tabulate import tabulate
from DbConnector import DbConnector


class Queries:
    def __init__(self):
        self.connection = DbConnector()
        self.db_connection = self.connection.db_connection
        self.cursor = self.connection.cursor

    def run(self, title, sql, params=None):
        self.cursor.execute(sql, params)
        rows = self.cursor.fetchall()
        headers = [d[0] for d in self.cursor.description]
        print(f"\n=== {title} ===")
        print(tabulate(rows, headers=headers))
        return rows

    # 1. Antall taxier, turer og GPS-punkter
    def q1(self):
        self.run("Oppgave 1", """
            SELECT COUNT(DISTINCT taxi_id) AS taxis,
                   COUNT(*)                AS trips,
                   SUM(n_points)           AS gps_points
            FROM Trip
        """)

    # 2. Gjennomsnittlig antall turer per taxi
    def q2(self):
        self.run("Oppgave 2", """
            SELECT ROUND(COUNT(*) / COUNT(DISTINCT taxi_id), 2) AS avg_trips_per_taxi
            FROM Trip
        """)

    # 3. Topp 20 taxier med flest turer
    def q3(self):
        self.run("Oppgave 3", """
            SELECT taxi_id, COUNT(*) AS trips
            FROM Trip
            GROUP BY taxi_id
            ORDER BY trips DESC
            LIMIT 20
        """)

    # 4a. Mest brukte call type per taxi
    def q4a(self):
        # Steg 1 (SQL): tell turer for hver taxi og hver call type
        self.cursor.execute("""
            SELECT taxi_id, call_type, COUNT(*) AS trips
            FROM Trip
            GROUP BY taxi_id, call_type
        """)
        rows = self.cursor.fetchall()

        beste = {}   # taxi_id -> (call_type, trips)
        for taxi_id, call_type, trips in rows:
            if taxi_id not in beste or trips > beste[taxi_id][1]:
                beste[taxi_id] = (call_type, trips)

        tabell = [[taxi_id, call_type, trips] for taxi_id, (call_type, trips) in sorted(beste.items())]
        print("\n=== Oppgave 4a: mest brukte call type per taxi ===")
        print(tabulate(tabell, headers=["taxi_id", "most_used_call_type", "trips"]))

    # 4b. Per call type: snittvarighet, snittdistanse og andel per tidsbånd
    def q4b(self):
        self.run("Oppgave 4b", """
            SELECT call_type,
                COUNT(*) AS trips,
                ROUND(AVG(duration_s) / 60, 2) AS avg_duration_min,
                ROUND(AVG(distance_km), 2)     AS avg_distance_km,
                ROUND(AVG(HOUR(start_time) < 6) * 100, 1)               AS pct_00_06,
                ROUND(AVG(HOUR(start_time) BETWEEN 6 AND 11) * 100, 1)  AS pct_06_12,
                ROUND(AVG(HOUR(start_time) BETWEEN 12 AND 17) * 100, 1) AS pct_12_18,
                ROUND(AVG(HOUR(start_time) >= 18) * 100, 1)             AS pct_18_24
            FROM Trip
            WHERE n_points >= 3
            GROUP BY call_type
            ORDER BY call_type
        """)
    
    # 5. Taxi med flest antall timer og deretter distanse kjørt
    def q5(self):
        self.run("Oppgave 5", """
            SELECT taxi_id, ROUND(SUM(duration_s) / 60, 2)  AS total_duration_min, ROUND(SUM(distance_km), 2) AS distance_km
            FROM Trip
            GROUP BY taxi_id
            ORDER BY total_duration_min DESC, distance_km DESC
        """)
    
    # 6. Turer som er innefor 100m readius fra city hall
    def q6(self):
        CITY_HALL = (41.15794, -8.62911) # på lat, lon format
        RADIUS_M = 100
        
        # definer lat og lon for boksen som inneholder alle punkter som er innenfor 100m fra City_hall
        max_lat, _ = inverse_haversine(CITY_HALL, RADIUS_M, Direction.NORTH, unit=Unit.METERS)
        min_lat, _ = inverse_haversine(CITY_HALL, RADIUS_M, Direction.SOUTH, unit=Unit.METERS)
        _, max_lon = inverse_haversine(CITY_HALL, RADIUS_M, Direction.EAST,  unit=Unit.METERS)
        _, min_lon = inverse_haversine(CITY_HALL, RADIUS_M, Direction.WEST,  unit=Unit.METERS)
        
        # initell filtering av turer som er innenfor boks
        self.cursor.execute("""
            SELECT trip_id, polyline
            FROM Trip
            WHERE min_lon <= %s AND max_lon >= %s
            AND min_lat <= %s AND max_lat >= %s
            """,
            (max_lon, min_lon, max_lat, min_lat),
        )

        trips = []
        
        for trip_id, polyline in self.cursor.fetchall():
            points = json.loads(polyline) if isinstance(polyline, str) else polyline
            if any(haversine((p_lat, p_lon), CITY_HALL, unit=Unit.METERS) <= RADIUS_M for p_lon, p_lat in points):
                trips.append(trip_id)
        
        print("\n=== Oppgave 6 ===")
        print(tabulate([[t] for t in trips], headers=["trip_id"]))
        print(f"\n{len(trips):,} turer passerte innenfor {RADIUS_M} m av rådhuset i Porto")
        
    # 7. Antall turer med færre enn 3 gps punkt
    def q7(self):
        self.run("Oppgave 7", """
            SELECT COUNT(trip_id) as antall_ugyldinge_turer
            FROM Trip
            WHERE n_points < 3
        """)
        
    # 8. Turer som startet en dag og sluttet den neste
    def q8(self):
        self.run("Oppgave 8", """
            SELECT trip_id, start_time, end_time
            FROM Trip
            WHERE DATE(start_time) <> DATE(end_time);
        """)
                
    # 9. Turer som startet og slutter innen 50m fra hverandre
    def q9(self):
        RADIUS_M = 50
        
        # finn alle turer
        self.cursor.execute("""
            SELECT trip_id, start_lon, end_lon, start_lat, end_lat
            FROM Trip
            WHERE start_lat IS NOT NULL AND end_lat IS NOT NULL
            """
        )

        trips = []
        
        for trip_id, start_lon, end_lon, start_lat, end_lat in self.cursor.fetchall():
            if haversine((start_lat, start_lon), (end_lat, end_lon), unit=Unit.METERS) <= RADIUS_M:
                trips.append(trip_id)
        
        print("\n=== Oppgave 9 ===")
        print(tabulate([[t] for t in trips], headers=["trip_id"]))
        print(f"\n{len(trips):,} turer som startet og sluttet innen {RADIUS_M}m fra hverandre")


    # 10. Gjennomsnittlig ventetid mellom påfølgende turer, topp 20 taxier
    def q10(self):
        self.cursor.execute("""
            SELECT taxi_id, start_time, end_time
            FROM Trip
            ORDER BY taxi_id, start_time
        """)
        ventetider = {}      # taxi_id -> liste med ventetider i sekunder
        forrige = {}         # taxi_id -> sluttid for taxiens forrige tur
        for taxi_id, start, slutt in self.cursor.fetchall():
            if taxi_id in forrige:
                vent = (start - forrige[taxi_id]).total_seconds()
                if vent >= 0:
                    ventetider.setdefault(taxi_id, []).append(vent)
            forrige[taxi_id] = slutt

        snitt = [(taxi, round(sum(v) / len(v) / 60, 1), len(v)) for taxi, v in ventetider.items()]
        snitt.sort(key=lambda rad: rad[1], reverse=True)
        print("\n=== Oppgave 10 ===")
        print(tabulate(snitt[:20], headers=["taxi_id", "avg_idle_min", "n_gaps"]))


def main():
    program = Queries()
    #for q in [program.q1, program.q2, program.q3, program.q4a, program.q4b, program.q5, program.q6, program.q7, program.q8, program.q9, program.q10]:
    for q in [program.q9]:
        q()
    program.connection.close_connection()


if __name__ == "__main__":
    main()