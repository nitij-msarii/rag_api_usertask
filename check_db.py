import os
import django
import sys

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rag_api.settings')
django.setup()

from django.db import connection

def check_tables():
    with connection.cursor() as cursor:
        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        
        print("All tables in database:")
        for table in sorted(tables):
            print(f"- {table}")
        
        # Check for our target tables
        target_tables = ['hotwash_rowcell_data', 'rag_app_cellassignee', 'rag_app_cellstatus', 'auth_user']
        print("\nTarget table status:")
        for target in target_tables:
            if target in tables:
                print(f"✓ {target} - EXISTS")
            else:
                print(f"✗ {target} - NOT FOUND")
                
        # Look for similar table names
        print("\nLooking for similar table names:")
        for table in tables:
            if 'cell' in table.lower() or 'user' in table.lower():
                print(f"- {table}")

if __name__ == "__main__":
    check_tables()
