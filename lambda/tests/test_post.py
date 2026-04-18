import json
import sys
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

import os
import sys

# Tambahkan path ke post_handler secara dinamis
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(base_dir, 'post_handler'))


class TestPostLambdaHandler:
    """Unit tests untuk Lambda POST handler."""

    def _make_event(self, body: dict, method='POST'):
        return {
            'httpMethod': method,
            'body': json.dumps(body),
            'isBase64Encoded': False,
            'headers': {'Content-Type': 'application/json'}
        }

    def _make_mock_db(self, returned_row=None):
        """Buat mock koneksi database."""
        if returned_row is None:
            returned_row = (1, 'test', 25.5, 'sensor', datetime(2024, 1, 15, 10, 30))

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: mock_cursor
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchone.return_value = returned_row
        mock_conn.cursor.return_value = mock_cursor
        return mock_conn

    # ── Test 1: Request valid ────────────────────────────────────────────
    def test_valid_post_returns_201(self):
        from handler import lambda_handler
        event = self._make_event({'name': 'sensor-suhu', 'value': 28.5, 'category': 'sensor'})
        mock_conn = self._make_mock_db((42, 'sensor-suhu', 28.5, 'sensor', datetime.now()))

        with patch('handler.get_db_connection', return_value=mock_conn):
            with patch('handler.ensure_table'):
                result = lambda_handler(event, {})

        assert result['statusCode'] == 201
        body = json.loads(result['body'])
        assert body['success'] is True
        assert body['data']['id'] == 42
        assert body['data']['value'] == 28.5

    # ── Test 2: name kosong ─────────────────────────────────────────────
    def test_empty_name_returns_400(self):
        from handler import lambda_handler
        event = self._make_event({'name': '', 'value': 10.0})

        with patch('handler.get_db_connection'):
            result = lambda_handler(event, {})

        assert result['statusCode'] == 400
        body = json.loads(result['body'])
        assert body['success'] is False
        assert any('name' in e for e in body['errors'])

    # ── Test 3: value tidak ada ─────────────────────────────────────────
    def test_missing_value_returns_400(self):
        from handler import lambda_handler
        event = self._make_event({'name': 'sensor1'})

        with patch('handler.get_db_connection'):
            result = lambda_handler(event, {})

        assert result['statusCode'] == 400

    # ── Test 4: value bukan angka ───────────────────────────────────────
    def test_non_numeric_value_returns_400(self):
        from handler import lambda_handler
        event = self._make_event({'name': 'sensor1', 'value': 'abc'})

        with patch('handler.get_db_connection'):
            result = lambda_handler(event, {})

        assert result['statusCode'] == 400

    # ── Test 5: OPTIONS preflight ───────────────────────────────────────
    def test_options_method_returns_200(self):
        from handler import lambda_handler
        event = {'httpMethod': 'OPTIONS', 'body': None}
        result = lambda_handler(event, {})
        assert result['statusCode'] == 200
        assert 'Access-Control-Allow-Origin' in result['headers']

    # ── Test 6: CORS headers ada ────────────────────────────────────────
    def test_cors_headers_present(self):
        from handler import lambda_handler
        event = self._make_event({'name': 'test', 'value': 1.0})
        mock_conn = self._make_mock_db()

        with patch('handler.get_db_connection', return_value=mock_conn):
            with patch('handler.ensure_table'):
                result = lambda_handler(event, {})

        assert result['headers']['Access-Control-Allow-Origin'] == '*'

    # ── Test 7: Database error → 500 ───────────────────────────────────
    def test_db_error_returns_500(self):
        import psycopg2
        from handler import lambda_handler
        event = self._make_event({'name': 'test', 'value': 1.0})

        with patch('handler.get_db_connection', side_effect=psycopg2.OperationalError('Connection refused')):
            result = lambda_handler(event, {})

        assert result['statusCode'] == 500

    # ── Test 8: Default category ────────────────────────────────────────
    def test_default_category_used_when_missing(self):
        from handler import lambda_handler
        event = self._make_event({'name': 'test', 'value': 5.0})
        mock_conn = self._make_mock_db((1, 'test', 5.0, 'default', datetime.now()))

        with patch('handler.get_db_connection', return_value=mock_conn):
            with patch('handler.ensure_table'):
                result = lambda_handler(event, {})

        assert result['statusCode'] == 201
