"""Юнит- и интеграционные тесты для speedtest.py."""

import json
from urllib.error import HTTPError

import speedtest

from conftest import PAYLOAD_SIZE


def test_format_size():
    assert speedtest.format_size(0) == "0 Б"
    assert speedtest.format_size(999) == "999 Б"
    assert speedtest.format_size(1000) == "1.00 КБ"
    assert speedtest.format_size(1_000_000) == "1.00 МБ"
    assert speedtest.format_size(1_000_000_000) == "1.00 ГБ"


def test_mbit_per_s():
    assert speedtest.mbit_per_s(1_000_000, 1) == 8.0


def test_mbit_per_s_zero_time_is_zero():
    assert speedtest.mbit_per_s(1_000_000, 0) == 0.0


def test_mbyte_per_s():
    assert speedtest.mbyte_per_s(1_000_000, 1) == 1.0


def test_validate_url_accepts_http_and_https():
    assert speedtest.validate_url("https://example.com/a.jpg") is None
    assert speedtest.validate_url("http://example.com/a.jpg") is None


def test_validate_url_rejects_other_schemes():
    assert speedtest.validate_url("ftp://example.com/a.jpg") is not None
    assert speedtest.validate_url("example.com/a.jpg") is not None
    assert speedtest.validate_url("file:///C:/secret.txt") is not None


def test_validate_url_rejects_malformed_authority():
    assert speedtest.validate_url("http://[") is not None
    assert speedtest.validate_url("http://:8080/file") is not None
    assert speedtest.validate_url("https://example.com:invalid/file") is not None
    assert speedtest.validate_url("http://example.com/path with spaces") is not None


def test_parse_args_defaults():
    args = speedtest.parse_args(["https://example.com/a.jpg"])
    assert args.url == "https://example.com/a.jpg"
    assert args.count == 10
    assert args.timeout == 30.0
    assert args.as_json is False


def test_parse_args_flags():
    args = speedtest.parse_args(["https://example.com/a.jpg", "-n", "3", "-t", "5", "--json"])
    assert args.count == 3
    assert args.timeout == 5.0
    assert args.as_json is True


def test_describe_http_error():
    err = HTTPError("http://x", 404, "Not Found", {}, None)
    assert speedtest._describe_error(err) == "HTTP 404 Not Found"


def test_download_reads_full_body(file_url):
    size, seconds = speedtest.download(file_url, timeout=10)
    assert size == PAYLOAD_SIZE
    assert seconds >= 0


def test_main_json_success(file_url, capsys):
    exit_code = speedtest.main([file_url, "-n", "2", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert data["successful"] == 2
    assert data["failed"] == 0
    assert data["total_bytes"] == 2 * PAYLOAD_SIZE
    assert data["speed_mbit_s"] > 0


def test_main_rejects_invalid_url(capsys):
    assert speedtest.main(["not-a-url"]) == 2
    assert "Ошибка" in capsys.readouterr().err


def test_main_rejects_bad_count(capsys):
    assert speedtest.main(["https://example.com/x", "-n", "0"]) == 2
    assert "Ошибка" in capsys.readouterr().err


def test_main_rejects_non_finite_timeout(capsys):
    assert speedtest.main(["https://example.com/x", "-t", "nan"]) == 2
    assert "Ошибка" in capsys.readouterr().err
    assert speedtest.main(["https://example.com/x", "-t", "inf"]) == 2
    assert "Ошибка" in capsys.readouterr().err
