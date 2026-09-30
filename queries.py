import json
from haversine import haversine, Unit
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
    for q in [program.q1, program.q2, program.q3, program.q4a, program.q4b, program.q10]:
        q()
    program.connection.close_connection()


if __name__ == "__main__":
    main()