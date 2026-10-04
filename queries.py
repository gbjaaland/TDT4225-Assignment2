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

    # 1. Number of taxis, trips and GPS-points
    def q1(self):
        self.run("Task 1", """
            SELECT COUNT(DISTINCT taxi_id) AS taxis,
                   COUNT(*)                AS trips,
                   SUM(n_points)           AS gps_points
            FROM Trip
        """)

    # 2. Average number of trips per taxi
    def q2(self):
        self.run("Task 2", """
            SELECT ROUND(COUNT(*) / COUNT(DISTINCT taxi_id), 2) AS avg_trips_per_taxi
            FROM Trip
        """)

    # 3. Top 20 taxis with most trips
    def q3(self):
        self.run("Task 3", """
            SELECT taxi_id, COUNT(*) AS trips
            FROM Trip
            GROUP BY taxi_id
            ORDER BY trips DESC
            LIMIT 20
        """)

    # 4a. Most used call type per taxi
    def q4a(self):
        self.cursor.execute("""
            SELECT taxi_id, call_type, COUNT(*) AS trips
            FROM Trip
            GROUP BY taxi_id, call_type
        """)
        rows = self.cursor.fetchall()

        best = {}   # taxi_id -> (call_type, trips)
        for taxi_id, call_type, trips in rows:
            if taxi_id not in best or trips > best[taxi_id][1]:
                best[taxi_id] = (call_type, trips)

        table = [[taxi_id, call_type, trips] for taxi_id, (call_type, trips) in sorted(best.items())]
        table = table[:10]
        print("\n=== Task 4a: most used call type per taxi ===")
        print(tabulate(table, headers=["taxi_id", "most_used_call_type", "trips"]))

    # 4b. Per call type: average duragtion, average distance and share per timeslot
    def q4b(self):
        self.run("Task 4b", """
            SELECT call_type,
                COUNT(*) AS trips,
                ROUND(AVG(duration_s) / 60, 2) AS avg_duration_min,
                ROUND(AVG(distance_km), 2)     AS avg_distance_km,
                ROUND(AVG(HOUR(start_time) < 6) * 100, 1)               AS pct_00_06,
                ROUND(AVG(HOUR(start_time) BETWEEN 6 AND 11) * 100, 1)  AS pct_06_12,
                ROUND(AVG(HOUR(start_time) BETWEEN 12 AND 17) * 100, 1) AS pct_12_18,
                ROUND(AVG(HOUR(start_time) >= 18) * 100, 1)             AS pct_18_24
            FROM Trip
            GROUP BY call_type
            ORDER BY call_type
        """)
    
    # 5. Taxi with most number hours and then distance driven 
    def q5(self):
        self.run("Task 5", """
            SELECT taxi_id, ROUND(SUM(duration_s) / 60, 2)  AS total_duration_min, ROUND(SUM(distance_km), 2) AS distance_km
            FROM Trip
            GROUP BY taxi_id
            ORDER BY total_duration_min DESC, distance_km DESC
        """)
    
    # 6. Trips within 100m radius from city hall
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
        
        print("\n=== Task 6 ===")
        print(tabulate([[t] for t in trips], headers=["trip_id"]))
        print(f"\n{len(trips):,} trips passed within {RADIUS_M} m of city hall in Porto")
        
    # 7. Number of trips with less than 3 gps points
    def q7(self):
        self.run("Task 7", """
            SELECT COUNT(trip_id) as antall_ugyldinge_turer
            FROM Trip
            WHERE n_points < 3
        """)
        
    # 8. Trips which started one day and ended the next
    def q8(self):
        self.run("Task 8", """
            SELECT trip_id, start_time, end_time
            FROM Trip
            WHERE DATE(start_time) <> DATE(end_time);
        """)
                
    # 9. Trips which started and ended within 50m of eachother
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
        
        print("\n=== Task 9 ===")
        print(tabulate([[t] for t in trips], headers=["trip_id"]))
        print(f"\n{len(trips):,} trips which started and ended within {RADIUS_M}m from each other")


    # 10. Average waiting time following trips, top 20 taxis
    def q10(self):
        self.cursor.execute("""
            SELECT taxi_id, start_time, end_time
            FROM Trip
            ORDER BY taxi_id, start_time
        """)
        waitingtimes = {}      # taxi_id -> list with waiting times in seconds
        previous = {}         # taxi_id -> end time for taxis previous trips
        for taxi_id, start, slutt in self.cursor.fetchall():
            if taxi_id in previous:
                vent = (start - previous[taxi_id]).total_seconds()
                if vent >= 0:
                    waitingtimes.setdefault(taxi_id, []).append(vent)
            previous[taxi_id] = slutt

        snitt = [(taxi, round(sum(v) / len(v) / 60, 1), len(v)) for taxi, v in waitingtimes.items()]
        snitt.sort(key=lambda rad: rad[1], reverse=True)
        print("\n=== Task 10 ===")
        print(tabulate(snitt[:20], headers=["taxi_id", "avg_idle_min", "n_gaps"]))


def main():
    program = Queries()
    for q in [program.q1, program.q2, program.q3, program.q4a, program.q4b, program.q5, program.q6, program.q7, program.q8, program.q9, program.q10]:
        q()
    program.connection.close_connection()


if __name__ == "__main__":
    main()