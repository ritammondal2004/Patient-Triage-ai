
$content = Get-Content -Raw app/core/database.py
$replacement = @"
        try:
            with admin_engine.connect() as conn:
                exists = conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": db_name}
                ).scalar()
                if not exists:
                    conn.execute(text(f"CREATE DATABASE {db_name}"))
        except Exception as e:
            print(f"[warn] Could not run CREATE DATABASE (normal for Neon/managed DBs): {e}")
        finally:
            admin_engine.dispose()
"@
$content = $content -replace "(?s)        try:\s+with admin_engine\.connect\(\) as conn:\s+exists = conn\.execute\(\s+text\(`"SELECT 1 FROM pg_database WHERE datname = :name`"\), \{`"name`": db_name\}\s+\)\.scalar\(\)\s+if not exists:\s+conn\.execute\(text\(f`"CREATE DATABASE \{db_name\}`"\)\)\s+finally:\s+admin_engine\.dispose\(\)", $replacement
Set-Content -Path app/core/database.py -Value $content

