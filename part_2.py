from configs.porto import PORTO_CONFIG
from configs.polyline import PORTO_POLYLINE_CONFIG
import csv
from DbConnector import DbConnector
from haversine import haversine_vector, Unit
from tabulate import tabulate

class Part_2:

    def __init__(self):
        self.connection = DbConnector()
        self.db_connection = self.connection.db_connection
        self.cursor = self.connection.cursor

    def create_table(self, config):        
        table_name = config["table"]
        print("Creates table:", table_name)

        definitions = [
            f"{name} {data_type}"
            for name, data_type in config["columns"]
        ]
        
        primary_key = config.get("primary_key")

        if primary_key:
            columns = ", ".join(primary_key)
            definitions.append(f"PRIMARY KEY ({columns})")
        
        for foreign_key in config.get("foreign_keys", []):
            columns = ", ".join(foreign_key["columns"])
            ref_columns = ", ".join(foreign_key["references_columns"])
            ref_table = foreign_key["references_table"]
            on_delete = foreign_key.get("on_delete")

            foreign_key_sql = (
                f"FOREIGN KEY ({columns}) "
                f"REFERENCES {ref_table} ({ref_columns})"
            )

            if on_delete:
                foreign_key_sql += f" ON DELETE {on_delete}"

            definitions.append(foreign_key_sql)

        column_definitions = ",\n".join(definitions)

        query = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {column_definitions}
            )
        """

        self.cursor.execute(query)
        self.db_connection.commit()

    def insert_data(self, file_name, config, batch_size=100, start_row=0):
        table_name = config["table"]
        columns = config["insert_columns"]
        row_parser = config["parser"]
        
        placeholders = ",".join(["%s"]*len(columns))
        column_names = ",".join(columns)
        
        query = f"""
            INSERT INTO {table_name}
            ({column_names})
            VALUES ({placeholders})
        """

        batch = []
        rows_read = start_row
        rows_inserted = 0

        print("Inserts data into table:", table_name)
        
        with open(file_name, "r", newline="", encoding="utf-8") as csvfile:
            readCSV = csv.reader(csvfile)

            next(readCSV)  # skip header

            for row in readCSV:
                rows_read += 1
            
                batch.append((row_parser(row)))

                if len(batch) == batch_size:
                    self.cursor.executemany(query, batch)
                    self.db_connection.commit()
                    rows_inserted += len(batch)
                    batch.clear()
                
                if rows_read % 100_000 == 0:
                    print(
                        f"Read: {rows_read:,} | "
                        f"Inserted: {rows_inserted:,}"
                    )
            if batch:
                self.cursor.executemany(query, batch)
                self.db_connection.commit()

    def task_5(self, table_name):
        query = """
            SELECT SUM(DISTANCE) AS DISTANCE_KM, SUM(DURATION_MINUTES)/60 AS TOTAL_HOURS
            FROM %s
            GROUP BY TAXI_ID
            ORDER BY DURATION_MINUTES, DISTANCE_KM 
        """
        self.cursor.execute(query % table_name)
        rows = self.cursor.fetchall()
        print("Data from table %s, tabulated:" % table_name)
        print(tabulate(rows, headers=self.cursor.column_names))
        return rows
    
    def task_6(self):
        return
    
    def task_7(self, table_name):
        query = """
            SELECT TRIP_ID, COUNT(POINT_INDEX) AS NR_OF_POINTS
            FROM %s
            GROUP BY TRIP_ID
            ORDER BY COUNT(POINT_INDEX)
        """
        self.cursor.execute(query % table_name)
        rows = self.cursor.fetchall()
        print("Data from table %s, raw format:" % table_name)
        print(rows)
        # Using tabulate to show the table in a nice way
        print("Data from table %s, tabulated:" % table_name)
        print(tabulate(rows, headers=self.cursor.column_names))
        return rows
    
    def task_8(self):
        return
    
    def task_9(self):
        return
        
    def fetch_data(self, table_name):
        query = "SELECT TRIP_ID, JSON_LENGTH(POLYLINE), POLYLINE AS NR_GPS_POINTS FROM %s WHERE JSON_LENGTH(POLYLINE) <= 35"
        self.cursor.execute(query % table_name)
        rows = self.cursor.fetchall()
        print("Data from table %s, raw format:" % table_name)
        print(rows)
        # Using tabulate to show the table in a nice way
        print("Data from table %s, tabulated:" % table_name)
        print(tabulate(rows, headers=self.cursor.column_names))
        return rows

    def drop_table(self, table_name):
        print("Dropping table %s..." % table_name)
        query = "DROP TABLE %s"
        self.cursor.execute(query % table_name)

    def show_tables(self):
        self.cursor.execute("SHOW TABLES")
        rows = self.cursor.fetchall()
        print(tabulate(rows, headers=self.cursor.column_names))


def main():
    program = None
    try:
        program = Part_2()
        program.drop_table(table_name=PORTO_CONFIG["table"])
        program.create_table(config=PORTO_CONFIG)
        #program.drop_table(table_name=PORTO_POLYLINE_CONFIG["table"])
        #program.insert_data(file_name="/app/porto/porto_cleaned.csv", config=PORTO_CONFIG) # only run once
        #program.create_table(config=PORTO_POLYLINE_CONFIG)
        #_ = program.fetch_data(table_name=PORTO_POLYLINE_CONFIG["table"])
        #program.insert_data(file_name="/app/porto/polyline_exploded.csv", config=PORTO_POLYLINE_CONFIG, start_row=1164470) # only run once
        

        # Task 5
        _ = program.task_5(table_name=PORTO_CONFIG["table"])
        # Task 6
        
        # Task 7
        #_ = program.fetch_data(table_name=PORTO_CONFIG["table"])
        #_ = program.task_7(table_name=PORTO_POLYLINE_CONFIG["table"])
        # Task 8
        
        # Task 9
        
        # Task 10
        
        
        #
        #program.drop_table(table_name="Person")
        # Check that the table is dropped
        program.show_tables()
    except Exception as e:
        print("ERROR: Failed to use database:", e)
        raise
    finally:
        if program:
            program.connection.close_connection()


if __name__ == '__main__':
    main()