What was done                                                                                                                           
                                                                                                                                          
  The problem: You had an original Marzban DB that was missing columns/tables that your fork added.                                       
                  
  Step 1 — Migrate the schema. Ran SQL against the original db.sqlite3 to add the missing pieces:                                         
                                                                                                                                          
  - Added device_limit and smart_host_address columns to users table
  - Added user_limit and traffic_limit columns to admins table
  - Created the user_devices table (for HWID tracking)
  - Updated alembic_version to c4d5e6f7a8b9 so Alembic thinks the DB is up to date with the fork

  Step 2 — Fix the DB path. Your .env had:
  SQLALCHEMY_DATABASE_URL = "sqlite:///db.sqlite3"
  This is a relative path, meaning the DB lived inside the container at /code/db.sqlite3 — not in the mounted volume. So every rebuild
  wiped it.

  Changed it to:
  SQLALCHEMY_DATABASE_URL = "sqlite:////var/lib/marzban/db.sqlite3"
  This points to /var/lib/marzban/db.sqlite3, which is mapped to the host via the volumes:bvjkdekvnfcefcf mount in docker-compose.yml. Now the DBefjvbc
  survives rebuilds.

  Step 3 — Copied the migrated DB to /var/lib/marzban/db.sqlite3 on the host, restarted the container.