from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import connection
from datetime import datetime, timedelta
import json
import re
from decimal import Decimal
from .models import QueryHistory

class OfflineRAGView(APIView):
    
    def __init__(self):
        super().__init__()
        self.schema_info = {
            'hotwash_rowcell_data': {
                'columns': ['id', 'sheet_id', 'column_id', 'row_id', 'column_index', 'column_type', 'cell_data', 'cell_date', 'created_at', 'updated_at'],
                'description': 'Main cell data with tasks and dates'
            },
            'hotwash_groups_header': {
                'columns': ['id', 'name', 'column_type', 'column_index', 'sheet_id', 'group_id'],
                'description': 'Column headers and types for sheets'
            },
            'hotwash_sheet': {
                'columns': ['id', 'name', 'privacy_type', 'user_id', 'workspace_id'],
                'description': 'Sheet information'
            },
            'hotwash_workspace': {
                'columns': ['id', 'workspace_name', 'description', 'user_id'],
                'description': 'Workspace information'
            },
            'authentication_user': {
                'columns': ['id', 'name', 'username', 'email', 'studid'],
                'description': 'User information'
            },
            'hotwash_status_dropdown': {
                'columns': ['id', 'sheet_id', 'column_id', 'status_text', 'status_color', 'status_type'],
                'description': 'Status options for cells'
            }
        }
    
    def generate_sql_query(self, user_query):
        """Generate SQL query based on user input using rule-based approach"""
        query_lower = user_query.lower()
        
        # Extract user ID or username from query
        user_id_match = re.search(r'user\s*(?:id\s*)?(\d+)', query_lower)
        username_match = re.search(r'user\s*(?:name\s*)?"?([a-zA-Z0-9_]+)"?', query_lower)
        
        # Extract date information
        date_keywords = ['today', 'yesterday', 'this week', 'last week', 'past 7 days']
        date_condition = ""
        
        if 'today' in query_lower:
            date_condition = f"DATE(gcd.cell_date) = DATE('now')"
        elif 'yesterday' in query_lower:
            date_condition = f"DATE(gcd.cell_date) = DATE('now', '-1 day')"
        elif 'past 7 days' in query_lower or 'last week' in query_lower:
            date_condition = f"DATE(gcd.cell_date) >= DATE('now', '-7 days')"
        elif 'this week' in query_lower:
            date_condition = f"DATE(gcd.cell_date) >= DATE('now', 'weekday 0', '-7 days')"
        else:
            # Default to past 7 days for context
            date_condition = f"DATE(gcd.cell_date) >= DATE('now', '-7 days')"
        
        # Base query to get name, task, date, status
        base_query = """
        SELECT 
            gcd.id,
            gcd.cell_data as task,
            gcd.cell_date as date,
            gcd.column_type,
            gcd.column_index,
            gh.name as column_name,
            gh.column_type as header_type,
            hs.name as sheet_name,
            hw.workspace_name,
            au.name as user_name,
            au.username,
            sd.status_text as status,
            sd.status_color
        FROM hotwash_rowcell_data gcd
        LEFT JOIN hotwash_groups_header gh ON gcd.column_id = gh.id
        LEFT JOIN hotwash_sheet hs ON gcd.sheet_id = hs.id
        LEFT JOIN hotwash_workspace hw ON hs.workspace_id = hw.id
        LEFT JOIN authentication_user au ON hw.user_id = au.id
        LEFT JOIN hotwash_status_dropdown sd ON (gcd.sheet_id = sd.sheet_id AND gcd.column_id = sd.column_id)
        WHERE 1=1
        """
        
        conditions = []
        
        # Add user filtering - search in cell data content for user references
        if user_id_match:
            conditions.append(f"(au.id = {user_id_match.group(1)} OR gcd.cell_data LIKE '%user {user_id_match.group(1)}%')")
        elif username_match:
            conditions.append(f"(au.username LIKE '%{username_match.group(1)}%' OR gcd.cell_data LIKE '%{username_match.group(1)}%')")
        
        # Add date condition
        if date_condition:
            conditions.append(date_condition)
        
        # Add conditions to query
        if conditions:
            base_query += " AND " + " AND ".join(conditions)
        
        base_query += " ORDER BY gcd.cell_date DESC, gcd.created_at DESC LIMIT 50"
        
        return base_query
    
    def execute_query(self, sql_query):
        """Execute SQL query and return results"""
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql_query)
                columns = [col[0] for col in cursor.description]
                results = cursor.fetchall()
                
                # Convert to list of dictionaries with JSON serializable values
                data = []
                for row in results:
                    row_dict = {}
                    for i, value in enumerate(row):
                        # Convert date objects to strings for JSON serialization
                        if hasattr(value, 'strftime'):  # date/datetime objects
                            row_dict[columns[i]] = value.strftime('%Y-%m-%d') if hasattr(value, 'date') else str(value)
                        elif isinstance(value, Decimal):
                            row_dict[columns[i]] = float(value)
                        else:
                            row_dict[columns[i]] = value
                    data.append(row_dict)
                
                return data
        except Exception as e:
            return {"error": str(e)}
    
    def generate_response(self, query, data):
        """Generate human-readable response focused on name, task, date, status"""
        if isinstance(data, dict) and "error" in data:
            return f"Error executing query: {data['error']}"
        
        if not data:
            return "No data found for the specified query."
        
        query_lower = query.lower()
        response_parts = []
        
        if 'status' in query_lower or 'what' in query_lower:
            response_parts.append("Tasks and Activities:")
            
            for i, row in enumerate(data[:10]):  # Limit to 10 records
                task = row.get('task', 'No task')
                date = row.get('date', 'No date')
                status = row.get('status', 'No status')
                user_name = row.get('user_name', row.get('username', 'Unknown user'))
                column_name = row.get('column_name', 'Unknown column')
                
                response_parts.append(f"\n{i+1}. {user_name}")
                response_parts.append(f"   Task: {task}")
                response_parts.append(f"   Date: {date}")
                response_parts.append(f"   Status: {status}")
                response_parts.append(f"   Column: {column_name}")
        
        else:
            response_parts.append(f"Found {len(data)} task records.")
            
            if data:
                # Show date range
                dates = [row.get('date', '') for row in data if row.get('date')]
                if dates:
                    latest_date = max(dates)
                    oldest_date = min(dates)
                    response_parts.append(f"Date range: {oldest_date} to {latest_date}")
                
                # Show unique users and workspaces
                users = set(row.get('user_name', row.get('username', 'Unknown')) for row in data if row.get('user_name') or row.get('username'))
                workspaces = set(row.get('workspace_name', 'Unknown') for row in data if row.get('workspace_name'))
                
                if users:
                    response_parts.append(f"Users: {', '.join(users)}")
                if workspaces:
                    response_parts.append(f"Workspaces: {', '.join(workspaces)}")
                
                # Show sample tasks
                response_parts.append("\nSample tasks:")
                for i, row in enumerate(data[:3]):
                    task = row.get('task', 'No task')
                    date = row.get('date', 'No date')
                    status = row.get('status', 'No status')
                    response_parts.append(f"  {i+1}. {date}: {task} [{status}]")
        
        return "\n".join(response_parts)
    
    def post(self, request):
        try:
            query = request.data.get('query', '')
            
            if not query:
                return Response(
                    {"error": "Query parameter is required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Generate SQL query
            sql_query = self.generate_sql_query(query)
            
            # Execute query
            data = self.execute_query(sql_query)
            
            # Generate response
            response_text = self.generate_response(query, data)
            
            # Save to history
            QueryHistory.objects.create(
                query=query,
                sql_query=sql_query,
                response=response_text,
                data_fetched=data if not isinstance(data, dict) or "error" not in data else {}
            )
            
            return Response({
                "query": query,
                "sql_query": sql_query,
                "response": response_text,
                "data_fetched": data,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            return Response(
                {"error": f"Internal server error: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class SchemaInfoView(APIView):
    """View to get database schema information"""
    
    def get(self, request):
        schema_info = {
            'hotwash_rowcell_data': {
                'columns': ['id', 'sheet_id', 'column_id', 'row_id', 'column_index', 'column_type', 'cell_data', 'cell_date', 'created_at', 'updated_at'],
                'description': 'Main cell data with tasks and dates'
            },
            'hotwash_groups_header': {
                'columns': ['id', 'name', 'column_type', 'column_index', 'sheet_id', 'group_id'],
                'description': 'Column headers and types for sheets'
            },
            'hotwash_sheet': {
                'columns': ['id', 'name', 'privacy_type', 'user_id', 'workspace_id'],
                'description': 'Sheet information'
            },
            'hotwash_workspace': {
                'columns': ['id', 'workspace_name', 'description', 'user_id'],
                'description': 'Workspace information'
            },
            'authentication_user': {
                'columns': ['id', 'name', 'username', 'email', 'studid'],
                'description': 'User information'
            },
            'hotwash_status_dropdown': {
                'columns': ['id', 'sheet_id', 'column_id', 'status_text', 'status_color', 'status_type'],
                'description': 'Status options for cells'
            }
        }
        
        return Response({
            "schema": schema_info,
            "description": "Database schema information for RAG queries"
        })

class QueryHistoryView(APIView):
    """View to get query history"""
    
    def get(self, request):
        history = QueryHistory.objects.all().order_by('-created_at')[:20]
        history_data = []
        
        for item in history:
            history_data.append({
                "id": item.id,
                "query": item.query,
                "sql_query": item.sql_query,
                "response": item.response,
                "created_at": item.created_at.isoformat()
            })
        
        return Response({
            "history": history_data,
            "count": len(history_data)
        })

# Create your views here.
