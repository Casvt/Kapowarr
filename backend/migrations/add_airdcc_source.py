from alembic import op
import sqlalchemy as sa

def upgrade():
    # Add AirDCC++ configuration to settings table
    op.execute("""
        INSERT INTO settings (key, value, description) 
        VALUES ('airdcc_enabled', 'false', 'Enable AirDCC++ as search source'),
               ('airdcc_server_url', 'http://localhost:5115', 'AirDDC++ server URL'),
               ('airdcc_username', '', 'AirDCC++ username'),
               ('airdcc_password', '', 'AirDCC++ password'),
               ('airdcc_timeout', '30', 'Search timeout in seconds'),
               ('airdcc_max_results', '100', 'Maximum search results')
    """)
    
    # Add AirDCC++ to sources table
    op.execute("""
        INSERT INTO sources (name, type, enabled, config) 
        VALUES ('AirDCC++', 'airdcc', false, '{}')
    """)

def downgrade():
    op.execute("DELETE FROM settings WHERE key LIKE 'airdcc_%'")
    op.execute("DELETE FROM sources WHERE name = 'AirDCC++'")
