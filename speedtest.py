#!/usr/bin/env python3
"""speedtest-cli — замер скорости скачивания по заданному адресу.

Скрипт делает N последовательных запросов (по умолчанию 10) к одному URL,
дожидается полного скачивания тела каждого ответа и печатает среднее время,
общий объём и скорость скачивания.

Зависимостей нет — используется только стандартная библиотека Python.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from functools import partial
from typing import Callable
from urllib.parse import urlparse

__version__ = "1.1.0"

CHUNK_SIZE = 64 * 1024  # читаем ответ кусками по 64 КБ
BAR_WIDTH = 24          # ширина полоски скорости в символах
USER_AGENT = f"speedtest-cli/{__version__}"

ProgressCallback = Callable[[int, float], None]


# ─────────────────────────────────────────────────────────────────────
# Оформление: ANSI-цвета
# ─────────────────────────────────────────────────────────────────────

def _enable_colors() -> bool:
    """Цвета включаем, только если вывод идёт в терминал и не задан NO_COLOR."""
    if "NO_COLOR" in os.environ or not sys.stdout.isatty():
        return False
    if os.name == "nt":
        os.system("")  # включает поддержку ANSI-кодов в Windows 10+
    return True


USE_COLOR = _enable_colors()


def paint(text: str, code: str) -> str:
    """Оборачивает текст в ANSI-цвет либо возвращает без изменений."""
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text


def bold(text: str) -> str:
    return paint(text, "1")


def dim(text: str) -> str:
    return paint(text, "2")


def cyan(text: str) -> str:
    return paint(text, "36")


def green(text: str) -> str:
    return paint(text, "32")


def red(text: str) -> str:
    return paint(text, "31")


def yellow(text: str) -> str:
    return paint(text, "33")


# ─────────────────────────────────────────────────────────────────────
# Форматирование чисел
# ─────────────────────────────────────────────────────────────────────

def format_size(num_bytes: float) -> str:
    """Переводит байты в читаемую строку (десятичные единицы: 1 МБ = 10^6 Б)."""
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if num_bytes < 1000 or unit == "ГБ":
            if unit == "Б":
                return f"{num_bytes:.0f} {unit}"
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1000
    return f"{num_bytes:.2f} ТБ"


def mbit_per_s(num_bytes: float, seconds: float) -> float:
    """Скорость в мегабитах в секунду: байты × 8 бит ÷ секунды ÷ 10^6."""
    return num_bytes * 8 / seconds / 1_000_000 if seconds > 0 else 0.0


def mbyte_per_s(num_bytes: float, seconds: float) -> float:
    """Скорость в мегабайтах в секунду."""
    return num_bytes / seconds / 1_000_000 if seconds > 0 else 0.0


def speed_bar(value: float, maximum: float) -> str:
    """Полоска ████░░░░, пропорциональная скорости относительно максимума."""
    filled = round(BAR_WIDTH * value / maximum) if maximum > 0 else 0
    return green("█" * filled) + dim("░" * (BAR_WIDTH - filled))


def _line_start() -> str:
    """Возвращает `\\r`, если нужно перезаписать строку прогресса в терминале."""
    return "\r" if sys.stdout.isatty() else ""


# ─────────────────────────────────────────────────────────────────────
# Сетевая часть
# ─────────────────────────────────────────────────────────────────────

def download(url: str, timeout: float,
             on_progress: ProgressCallback | None = None) -> tuple[int, float]:
    """Скачивает URL целиком и возвращает `(байты, секунды)`.

    Время включает установку соединения, ожидание ответа и скачивание тела.
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    started = time.perf_counter()  # самые точные часы для замеров
    total = 0
    with urllib.request.urlopen(request, timeout=timeout) as response:
        while True:
            chunk = response.read(CHUNK_SIZE)
            if not chunk:  # пустой кусок = ответ закончился
                break
            total += len(chunk)
            if on_progress is not None:
                on_progress(total, time.perf_counter() - started)
    return total, time.perf_counter() - started


def _describe_error(error: BaseException) -> str:
    """Превращает сетевое исключение в короткое человекочитаемое сообщение."""
    if isinstance(error, urllib.error.HTTPError):
        return f"HTTP {error.code} {error.reason}"
    reason = getattr(error, "reason", error)
    if isinstance(reason, TimeoutError):
        return "таймаут"
    text = str(reason)
    return text if text else str(error)


# ─────────────────────────────────────────────────────────────────────
# Результаты и сводка
# ─────────────────────────────────────────────────────────────────────

@dataclass
class RequestResult:
    """Итог одного запроса."""
    index: int
    bytes: int = 0
    seconds: float = 0.0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def build_summary(url: str, requested: int,
                  results: list[RequestResult]) -> dict[str, object]:
    """Собирает сводку замеров в виде словаря для JSON-вывода."""
    successful = [r for r in results if r.ok]
    total_bytes = sum(r.bytes for r in successful)
    total_time = sum(r.seconds for r in successful)
    times = [r.seconds for r in successful]
    avg_time = total_time / len(successful) if successful else 0.0

    per_request: list[dict[str, object]] = []
    for r in results:
        item: dict[str, object] = {
            "index": r.index,
            "bytes": r.bytes,
            "seconds": round(r.seconds, 6),
            "status": "ok" if r.ok else "error",
        }
        if r.error is not None:
            item["error"] = r.error
        per_request.append(item)

    return {
        "url": url,
        "requests": requested,
        "successful": len(successful),
        "failed": len(results) - len(successful),
        "total_bytes": total_bytes,
        "total_seconds": round(total_time, 6),
        "average_time_ms": round(avg_time * 1000),
        "min_time_ms": round(min(times) * 1000) if times else None,
        "max_time_ms": round(max(times) * 1000) if times else None,
        "stddev_time_ms": round(statistics.stdev(times) * 1000) if len(times) > 1 else 0,
        "speed_mbit_s": round(mbit_per_s(total_bytes, total_time), 2),
        "speed_mbyte_s": round(mbyte_per_s(total_bytes, total_time), 2),
        "results": per_request,
    }


# ─────────────────────────────────────────────────────────────────────
# Вывод в терминал
# ─────────────────────────────────────────────────────────────────────

def _fail(message: str) -> None:
    print(red(f"Ошибка: {message}"), file=sys.stderr)


def _print_header(url: str, count: int) -> None:
    print()
    print(bold(cyan("  ⚡ SPEEDTEST")) + dim("  замер скорости скачивания"))
    print(dim("  " + "─" * 58))
    print(f"  Адрес     {url}")
    print(f"  Запросов  {count}  {dim('(последовательно)')}")
    print()


def _render_progress(done: int, elapsed: float, label: str) -> None:
    """Обновляет строку прогресса «на месте» внутри одного запроса."""
    if sys.stdout.isatty():
        speed = mbit_per_s(done, elapsed)
        sys.stdout.write(f"\r  {label} {yellow('↓')} {format_size(done):>10}  "
                         f"{speed:7.1f} Мбит/с   ")
        sys.stdout.flush()


def _print_success(label: str, size: int, seconds: float,
                   results: list[RequestResult]) -> None:
    speed = mbit_per_s(size, seconds)
    best = max(mbit_per_s(r.bytes, r.seconds) for r in results if r.ok)
    print(f"{_line_start()}  {label} {green('✓')} {format_size(size):>10}  "
          f"{seconds * 1000:8.0f} мс  {speed:7.1f} Мбит/с  "
          f"{speed_bar(speed, best)}")


def _print_failure(label: str, reason: str) -> None:
    print(f"{_line_start()}  {label} {red('✗ ошибка:')} {reason}" + " " * 20)


def _print_summary(requested: int, results: list[RequestResult]) -> None:
    successful = [r for r in results if r.ok]
    failures = len(results) - len(successful)

    print()
    if not successful:
        print(red("  Ни один запрос не завершился успешно — считать нечего."))
        print()
        return

    total_bytes = sum(r.bytes for r in successful)
    total_time = sum(r.seconds for r in successful)
    avg_time = total_time / len(successful)
    times = [r.seconds for r in successful]
    overall_mbit = mbit_per_s(total_bytes, total_time)
    overall_mbyte = mbyte_per_s(total_bytes, total_time)

    # Общая скорость = весь объём ÷ всё время. Это честнее, чем среднее из скоростей.
    print(dim("  " + "─" * 58))
    print(bold("  РЕЗУЛЬТАТ"))
    print()
    print(f"  Успешных запросов     {green(str(len(successful)))} из {requested}"
          + (f"  {red(f'({failures} с ошибкой)')}" if failures else ""))
    print(f"  Скачано всего         {bold(format_size(total_bytes))}")
    print(f"  Среднее время         {bold(f'{avg_time * 1000:.0f} мс')}"
          + dim(f"   (мин {min(times) * 1000:.0f} · макс {max(times) * 1000:.0f}"
                + (f" · σ {statistics.stdev(times) * 1000:.0f}"
                   if len(times) > 1 else "")
                + ")"))
    print(f"  Скорость скачивания   {bold(green(f'{overall_mbit:.2f} Мбит/с'))}"
          + dim(f"   ≈ {overall_mbyte:.2f} МБ/с"))
    print()


# ─────────────────────────────────────────────────────────────────────
# Точка входа
# ─────────────────────────────────────────────────────────────────────

def validate_url(url: str) -> str | None:
    """Возвращает сообщение об ошибке, если адрес недопустим, иначе `None`."""
    try:
        if any(char.isspace() for char in url):
            return "адрес URL не должен содержать пробелы или управляющие символы"
        parsed = urlparse(url)
        # hostname и port дополнительно проверяют пустой хост и некорректный порт.
        if (parsed.scheme not in ("http", "https")
                or not parsed.netloc or not parsed.hostname):
            return "нужен полный адрес, начинающийся с http:// или https://"
        parsed.port
    except ValueError:
        return "некорректный адрес URL"
    return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Замер скорости скачивания: N последовательных "
                    "запросов к одному адресу.",
        epilog="Пример: python speedtest.py https://example.com/big.jpg -n 10",
    )
    parser.add_argument("url", help="адрес для запросов, например "
                                    "https://example.com/big.jpg")
    parser.add_argument("-n", "--count", type=int, default=10,
                        help="количество запросов (по умолчанию 10)")
    parser.add_argument("-t", "--timeout", type=float, default=30.0,
                        help="таймаут сети в секундах (по умолчанию 30)")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="вывести итог в формате JSON (только итог)")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {__version__}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    invalid = validate_url(args.url)
    if invalid:
        _fail(invalid)
        return 2
    if args.count < 1:
        _fail("количество запросов должно быть не меньше 1")
        return 2
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        _fail("таймаут должен быть конечным числом больше 0")
        return 2

    pretty = not args.as_json
    if pretty:
        _print_header(args.url, args.count)

    results: list[RequestResult] = []
    for i in range(1, args.count + 1):
        label = f"[{i:>2}/{args.count}]"
        on_progress = None if args.as_json else partial(_render_progress, label=label)

        try:
            size, seconds = download(args.url, args.timeout, on_progress)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            results.append(RequestResult(index=i, error=_describe_error(exc)))
            if pretty:
                _print_failure(label, _describe_error(exc))
            continue

        results.append(RequestResult(index=i, bytes=size, seconds=seconds))
        if pretty:
            _print_success(label, size, seconds, results)

    if args.as_json:
        print(json.dumps(build_summary(args.url, args.count, results),
                         ensure_ascii=False, indent=2))
    else:
        _print_summary(args.count, results)

    successful = sum(1 for r in results if r.ok)
    return 0 if successful == args.count else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n  Прервано пользователем.")
        sys.exit(130)
