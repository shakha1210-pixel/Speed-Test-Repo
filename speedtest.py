#!/usr/bin/env python3
"""
speedtest.py — консольный замер скорости скачивания по заданному адресу.

Что делает:
  1. принимает URL (например, тяжёлую картинку);
  2. делает N запросов (по умолчанию 10) строго последовательно;
  3. на каждом запросе дожидается полного скачивания тела ответа;
  4. считает среднее время запроса, общий объём и скорость скачивания.

Только стандартная библиотека Python 3.8+ — ничего устанавливать не нужно.
"""

import argparse
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

CHUNK_SIZE = 64 * 1024  # читаем ответ кусками по 64 КБ
BAR_WIDTH = 24          # ширина полоски скорости в символах


# ───────────────────────── оформление ─────────────────────────

def _enable_colors() -> bool:
    """Цвета включаем только если вывод идёт в терминал и не задан NO_COLOR."""
    if os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return False
    if os.name == "nt":
        os.system("")  # трюк: включает поддержку ANSI-кодов в Windows 10+
    return True


USE_COLOR = _enable_colors()


def paint(text: str, code: str) -> str:
    """Оборачивает текст в ANSI-цвет (или возвращает как есть без цветов)."""
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text


def bold(t): return paint(t, "1")
def dim(t): return paint(t, "2")
def cyan(t): return paint(t, "36")
def green(t): return paint(t, "32")
def red(t): return paint(t, "31")
def yellow(t): return paint(t, "33")


# ───────────────────────── форматирование ─────────────────────────

def format_size(num_bytes: float) -> str:
    """Байты -> читаемая строка. Используем десятичные единицы: 1 МБ = 1 000 000 Б."""
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if num_bytes < 1000 or unit == "ГБ":
            return f"{num_bytes:.0f} {unit}" if unit == "Б" else f"{num_bytes:.2f} {unit}"
        num_bytes /= 1000
    return ""  # недостижимо, нужно только для линтеров


def mbit_per_s(num_bytes: float, seconds: float) -> float:
    """Скорость в мегабитах в секунду: байты * 8 бит / секунды / 1 000 000."""
    return num_bytes * 8 / seconds / 1_000_000 if seconds > 0 else 0.0


def mbyte_per_s(num_bytes: float, seconds: float) -> float:
    """Скорость в мегабайтах в секунду."""
    return num_bytes / seconds / 1_000_000 if seconds > 0 else 0.0


def speed_bar(value: float, maximum: float) -> str:
    """Полоска ████░░░░ пропорциональная скорости относительно максимума."""
    filled = round(BAR_WIDTH * value / maximum) if maximum > 0 else 0
    return green("█" * filled) + dim("░" * (BAR_WIDTH - filled))


# ───────────────────────── сетевая часть ─────────────────────────

def download(url: str, timeout: float, on_progress=None):
    """
    Скачивает URL целиком и возвращает (размер_в_байтах, время_в_секундах).
    Время включает установку соединения, ожидание ответа и скачивание тела.
    """
    request = urllib.request.Request(url, headers={"User-Agent": "speedtest-cli/1.0"})
    started = time.perf_counter()  # perf_counter — самые точные часы для замеров
    total = 0
    with urllib.request.urlopen(request, timeout=timeout) as response:
        while True:
            chunk = response.read(CHUNK_SIZE)
            if not chunk:  # пустой кусок = ответ закончился
                break
            total += len(chunk)
            if on_progress:
                on_progress(total, time.perf_counter() - started)
    return total, time.perf_counter() - started


# ───────────────────────── точка входа ─────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Замер скорости скачивания: N последовательных запросов к одному адресу."
    )
    parser.add_argument("url", help="адрес для запросов, например https://example.com/big.jpg")
    parser.add_argument("-n", "--count", type=int, default=10,
                        help="количество запросов (по умолчанию 10)")
    parser.add_argument("-t", "--timeout", type=float, default=30.0,
                        help="таймаут сетевых операций в секундах (по умолчанию 30)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    parsed = urlparse(args.url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        print(red("Ошибка: нужен полный адрес, начинающийся с http:// или https://"))
        return 2
    if args.count < 1:
        print(red("Ошибка: количество запросов должно быть не меньше 1"))
        return 2

    print()
    print(bold(cyan("  ⚡ SPEEDTEST")) + dim("  замер скорости скачивания"))
    print(dim("  " + "─" * 58))
    print(f"  Адрес     {args.url}")
    print(f"  Запросов  {args.count}  {dim('(последовательно)')}")
    print()

    results = []   # успешные замеры: (байты, секунды)
    failures = 0

    for i in range(1, args.count + 1):
        label = f"  [{i:>2}/{args.count}]"

        def show_progress(done, elapsed, label=label):
            # \r возвращает курсор в начало строки — так строка обновляется "на месте"
            if sys.stdout.isatty():
                speed = mbit_per_s(done, elapsed)
                sys.stdout.write(f"\r{label} {yellow('↓')} {format_size(done):>10}  {speed:7.1f} Мбит/с   ")
                sys.stdout.flush()

        try:
            size, seconds = download(args.url, args.timeout, show_progress)
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            failures += 1
            reason = getattr(error, "reason", error)
            print(f"\r{label} {red('✗ ошибка:')} {reason}" + " " * 20)
            continue

        results.append((size, seconds))
        speed = mbit_per_s(size, seconds)
        best = max(mbit_per_s(s, t) for s, t in results)
        print(f"\r{label} {green('✓')} {format_size(size):>10}  {seconds * 1000:8.0f} мс  "
              f"{speed:7.1f} Мбит/с  {speed_bar(speed, best)}")

    # ───────── итоги ─────────
    print()
    if not results:
        print(red("  Ни один запрос не завершился успешно — считать нечего."))
        print()
        return 1

    total_bytes = sum(size for size, _ in results)
    total_time = sum(sec for _, sec in results)
    avg_time = total_time / len(results)
    times = [sec for _, sec in results]
    # Общая скорость = весь объём / всё время. Это честнее, чем среднее из скоростей.
    overall_mbit = mbit_per_s(total_bytes, total_time)
    overall_mbyte = mbyte_per_s(total_bytes, total_time)

    print(dim("  " + "─" * 58))
    print(bold("  РЕЗУЛЬТАТ"))
    print()
    print(f"  Успешных запросов     {green(str(len(results)))} из {args.count}"
          + (f"  {red(f'({failures} с ошибкой)')}" if failures else ""))
    print(f"  Скачано всего         {bold(format_size(total_bytes))}")
    print(f"  Среднее время         {bold(f'{avg_time * 1000:.0f} мс')}"
          + dim(f"   (мин {min(times) * 1000:.0f} · макс {max(times) * 1000:.0f}"
                + (f" · σ {statistics.stdev(times) * 1000:.0f}" if len(times) > 1 else "") + ")"))
    print(f"  Скорость скачивания   {bold(green(f'{overall_mbit:.2f} Мбит/с'))}"
          + dim(f"   ≈ {overall_mbyte:.2f} МБ/с"))
    print()
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n  Прервано пользователем.")
        sys.exit(130)
