# Constants
CENTER_LAT, CENTER_LON = 41.15794, -8.62911                # Porto City Hall
SAMPLING_INTERVAL_S = 15                                    # one GPS point every 15 seconds
MAX_SPEED_KMH = 200                                         # faster than this between two points = GPS jump
MAX_STEP_M = MAX_SPEED_KMH / 3.6 * SAMPLING_INTERVAL_S      # longest realistic step, about 833 m
SAMPLE_SIZE = 100_000                                       # trips used in the point-level GPS analysis
SPEED_THRESHOLD = 50                                        # average speed threshold used to narrow the search for trips with GPS faults
MAX_DURATION_S = 2 * 3600                                   # trips longer than this are checked for average speed
MIN_AVG_SPEED_KMH = 10                                      # long trips with lower average speed than this are removed
BATCH_SIZE = 5000