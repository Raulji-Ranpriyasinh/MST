import pymysql

# Replace these with your actual database credentials
DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = "8888"
DB_NAME = "exam"

conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
cursor = conn.cursor()

columns_to_add = [
    ("logo_url", "VARCHAR(500) NULL"),
    ("primary_color", "VARCHAR(7) NULL"),
    ("secondary_color", "VARCHAR(7) NULL"),
]

for col_name, col_type in columns_to_add:
    try:
        cursor.execute(f"ALTER TABLE consultancy_firms ADD COLUMN {col_name} {col_type}")
        print(f"Added column: {col_name}")
    except pymysql.err.OperationalError as e:
        if e.args[0] == 1060:  # Duplicate column
            print(f"Column {col_name} already exists, skipping.")
        else:
            raise

conn.commit()
cursor.close()
conn.close()
print("Done!")