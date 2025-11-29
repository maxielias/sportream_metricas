from db_connection import get_postgresdb_from_neon_keys

db = get_postgresdb_from_neon_keys('neondb_keys.json')
with db:
    df = db.to_dataframe("SELECT * FROM webhooks LIMIT 10;")
    print(df.head())