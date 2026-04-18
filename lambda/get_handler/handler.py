import json
import os
import psycopg2
from datetime import datetime


def get_db_connection():
    """Buat koneksi ke RDS PostgreSQL."""
    return psycopg2.connect(
        host=os.environ['DB_HOST'],
        port=int(os.environ.get('DB_PORT', '5432')),
        database=os.environ.get('DB_NAME', 'myappdb'),
        user=os.environ.get('DB_USER', 'myappuser'),
        password=os.environ['DB_PASSWORD'],
        connect_timeout=5
    )


def lambda_handler(event, context):
    """
    Lambda GET Handler
    Endpoint: GET /data
    Query params: category (opsional), limit (default 100), offset (default 0)
    Response: { data: [...], statistics: [...], total: number }
    """
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization'
    }

    if event.get('httpMethod') == 'OPTIONS':
        return {'statusCode': 200, 'headers': headers, 'body': ''}

    conn = None
    try:
        # Query parameters
        params = event.get('queryStringParameters') or {}
        category = params.get('category')
        try:
            limit = min(int(params.get('limit', 100)), 500)   # Max 500 per request
            offset = max(int(params.get('offset', 0)), 0)
        except (ValueError, TypeError):
            limit, offset = 100, 0

        conn = get_db_connection()

        with conn.cursor() as cur:
            # ── Query data utama ──────────────────────────
            if category:
                cur.execute("""
                    SELECT id, name, value, category, created_at
                    FROM sensor_data
                    WHERE category = %s
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                """, (category, limit, offset))
            else:
                cur.execute("""
                    SELECT id, name, value, category, created_at
                    FROM sensor_data
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                """, (limit, offset))

            rows = cur.fetchall()
            data = [
                {
                    'id':         row[0],
                    'name':       row[1],
                    'value':      float(row[2]),
                    'category':   row[3],
                    'created_at': row[4].isoformat()
                }
                for row in rows
            ]

            # ── Statistik per kategori (untuk grafik) ────
            cur.execute("""
                SELECT
                    category,
                    ROUND(AVG(value)::numeric, 2)   AS avg_value,
                    ROUND(MIN(value)::numeric, 2)   AS min_value,
                    ROUND(MAX(value)::numeric, 2)   AS max_value,
                    COUNT(*)                         AS total_count,
                    ROUND(STDDEV(value)::numeric, 2) AS std_dev
                FROM sensor_data
                GROUP BY category
                ORDER BY total_count DESC
            """)
            stats = [
                {
                    'category':    row[0],
                    'avg':         float(row[1]) if row[1] else 0,
                    'min':         float(row[2]) if row[2] else 0,
                    'max':         float(row[3]) if row[3] else 0,
                    'count':       row[4],
                    'std_dev':     float(row[5]) if row[5] else 0
                }
                for row in cur.fetchall()
            ]

            # ── Data untuk time-series chart ─────────────
            cur.execute("""
                SELECT
                    DATE_TRUNC('hour', created_at) AS hour,
                    category,
                    ROUND(AVG(value)::numeric, 2) AS avg_value,
                    COUNT(*) AS count
                FROM sensor_data
                WHERE created_at >= NOW() - INTERVAL '24 hours'
                GROUP BY DATE_TRUNC('hour', created_at), category
                ORDER BY hour ASC
            """)
            timeseries = [
                {
                    'hour':      row[0].isoformat(),
                    'category':  row[1],
                    'avg_value': float(row[2]) if row[2] else 0,
                    'count':     row[3]
                }
                for row in cur.fetchall()
            ]

            # ── Total count ───────────────────────────────
            if category:
                cur.execute("SELECT COUNT(*) FROM sensor_data WHERE category = %s", (category,))
            else:
                cur.execute("SELECT COUNT(*) FROM sensor_data")
            total = cur.fetchone()[0]

        print(f"[GET] Returned {len(data)} records, {len(stats)} categories")

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'success':    True,
                'data':       data,
                'statistics': stats,
                'timeseries': timeseries,
                'pagination': {
                    'total':  total,
                    'limit':  limit,
                    'offset': offset,
                    'has_more': (offset + limit) < total
                }
            })
        }

    except psycopg2.Error as db_err:
        print(f"[GET] Database error: {db_err}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'success': False,
                'error': 'Database error',
                'detail': str(db_err)
            })
        }
    except Exception as e:
        print(f"[GET] Unexpected error: {e}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'success': False,
                'error': 'Internal server error'
            })
        }
    finally:
        if conn:
            conn.close()
