import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

# Tambahkan path ke get_handler secara dinamis
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(base_dir, 'get_handler'))


class TestGetLambdaHandler:
    """Unit tests untuk Lambda GET handler."""

    def _make_event(self, query_params=None, method='GET'):
        return {
            'httpMethod': method,
            'queryStringParameters': query_params,
            'body': None,
            'isBase64Encoded': False
        }

    def _make_mock_db(self, data_rows=None, stat_rows=None, timeseries_rows=None, total=0):
        """Buat mock koneksi database dengan multiple query results."""
        if data_rows is None:
            data_rows = [(1, 'sensor1', 25.5, 'sensor', datetime(2024, 1, 15, 10, 0))]
        if stat_rows is None:
            stat_rows = [('sensor', 25.5, 10.0, 40.0, 1, 2.5)]
        if timeseries_rows is None:
            timeseries_rows = []

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: mock_cursor
        mock_cursor.__exit__ = MagicMock(return_value=False)

        # fetchall dipanggil 3x: data, stats, timeseries
        mock_cursor.fetchall.side_effect = [data_rows, stat_rows, timeseries_rows]
        # fetchone dipanggil 1x: total count
        mock_cursor.fetchone.return_value = (total,)

        mock_conn.cursor.return_value = mock_cursor
        return mock_conn

    # ── Test 1: GET tanpa filter ────────────────────────────────────────
    def test_get_all_data_returns_200(self):
        from handler import lambda_handler
        event = self._make_event()
        mock_conn = self._make_mock_db(total=1)

        with patch('handler.get_db_connection', return_value=mock_conn):
            result = lambda_handler(event, {})

        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['success'] is True
        assert 'data' in body
        assert 'statistics' in body
        assert 'pagination' in body

    # ── Test 2: GET dengan filter category ──────────────────────────────
    def test_get_with_category_filter(self):
        from handler import lambda_handler
        event = self._make_event({'category': 'sensor', 'limit': '10'})
        mock_conn = self._make_mock_db(total=5)

        with patch('handler.get_db_connection', return_value=mock_conn):
            result = lambda_handler(event, {})

        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['pagination']['limit'] == 10

    # ── Test 3: Limit default 100 ───────────────────────────────────────
    def test_default_limit_is_100(self):
        from handler import lambda_handler
        event = self._make_event()
        mock_conn = self._make_mock_db()

        with patch('handler.get_db_connection', return_value=mock_conn):
            result = lambda_handler(event, {})

        body = json.loads(result['body'])
        assert body['pagination']['limit'] == 100

    # ── Test 4: Limit max 500 ───────────────────────────────────────────
    def test_limit_capped_at_500(self):
        from handler import lambda_handler
        event = self._make_event({'limit': '9999'})
        mock_conn = self._make_mock_db()

        with patch('handler.get_db_connection', return_value=mock_conn):
            result = lambda_handler(event, {})

        body = json.loads(result['body'])
        assert body['pagination']['limit'] == 500

    # ── Test 5: Struktur statistik ──────────────────────────────────────
    def test_statistics_structure(self):
        from handler import lambda_handler
        event = self._make_event()
        mock_conn = self._make_mock_db(
            stat_rows=[('sensor', 25.5, 10.0, 40.0, 5, 3.2)]
        )

        with patch('handler.get_db_connection', return_value=mock_conn):
            result = lambda_handler(event, {})

        body = json.loads(result['body'])
        stat = body['statistics'][0]
        assert 'category' in stat
        assert 'avg' in stat
        assert 'min' in stat
        assert 'max' in stat
        assert 'count' in stat

    # ── Test 6: OPTIONS preflight ───────────────────────────────────────
    def test_options_returns_200(self):
        from handler import lambda_handler
        event = {'httpMethod': 'OPTIONS', 'queryStringParameters': None}
        result = lambda_handler(event, {})
        assert result['statusCode'] == 200

    # ── Test 7: Empty database ──────────────────────────────────────────
    def test_empty_database_returns_empty_list(self):
        from handler import lambda_handler
        event = self._make_event()
        mock_conn = self._make_mock_db(data_rows=[], stat_rows=[], total=0)

        with patch('handler.get_db_connection', return_value=mock_conn):
            result = lambda_handler(event, {})

        body = json.loads(result['body'])
        assert body['data'] == []
        assert body['statistics'] == []
        assert body['pagination']['total'] == 0

    # ── Test 8: has_more pagination ────────────────────────────────────
    def test_has_more_pagination(self):
        from handler import lambda_handler
        event = self._make_event({'limit': '10', 'offset': '0'})
        mock_conn = self._make_mock_db(total=50)

        with patch('handler.get_db_connection', return_value=mock_conn):
            result = lambda_handler(event, {})

        body = json.loads(result['body'])
        assert body['pagination']['has_more'] is True
