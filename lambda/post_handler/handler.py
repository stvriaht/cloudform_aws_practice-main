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


def ensure_table(conn):
    """Buat tabel jika belum ada."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sensor_data (
                id          SERIAL PRIMARY KEY,
                name        VARCHAR(100) NOT NULL,
                value       FLOAT NOT NULL,
                category    VARCHAR(50) DEFAULT 'default',
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_sensor_category ON sensor_data(category);
            CREATE INDEX IF NOT EXISTS idx_sensor_created ON sensor_data(created_at DESC);
        """)
        conn.commit()


def lambda_handler(event, context):
    """
    Lambda POST Handler
    Endpoint: POST /data
    Body: { "name": string, "value": number, "category": string }
    """
    # CORS headers untuk semua response
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization'
    }

    # Handle OPTIONS preflight
    if event.get('httpMethod') == 'OPTIONS':
        return {'statusCode': 200, 'headers': headers, 'body': ''}

    conn = None
    try:
        # Parse body
        raw_body = event.get('body') or '{}'
        if event.get('isBase64Encoded', False):
            import base64
            raw_body = base64.b64decode(raw_body).decode('utf-8')

        body = json.loads(raw_body)

        # Validasi input
        name = body.get('name', '').strip()
        value = body.get('value')
        category = body.get('category', 'default').strip()

        errors = []
        if not name:
            errors.append('name tidak boleh kosong')
        if value is None:
            errors.append('value harus diisi')
        else:
            try:
                value = float(value)
            except (TypeError, ValueError):
                errors.append('value harus berupa angka')

        if errors:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'success': False,
                    'errors': errors
                })
            }

        # Insert ke database
        conn = get_db_connection()
        ensure_table(conn)

        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO sensor_data (name, value, category)
                   VALUES (%s, %s, %s)
                   RETURNING id, name, value, category, created_at""",
                (name, value, category)
            )
            row = cur.fetchone()
            conn.commit()

        new_record = {
            'id':         row[0],
            'name':       row[1],
            'value':      float(row[2]),
            'category':   row[3],
            'created_at': row[4].isoformat()
        }

        print(f"[POST] Inserted record id={new_record['id']} name={name} value={value}")

        return {
            'statusCode': 201,
            'headers': headers,
            'body': json.dumps({
                'success': True,
                'message': 'Data berhasil disimpan',
                'data': new_record
            })
        }

    except psycopg2.Error as db_err:
        print(f"[POST] Database error: {db_err}")
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
        print(f"[POST] Unexpected error: {e}")
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
