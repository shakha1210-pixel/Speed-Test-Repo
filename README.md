# Speed Test CLI

A lightweight Python command-line tool for measuring HTTP download throughput from a target URL. It performs sequential requests, reads each response body completely, and reports transfer size, request timing, and aggregate download speed.

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/runtime%20dependencies-none-16A34A)](#)
[![License: MIT](https://img.shields.io/badge/license-MIT-8B5CF6)](LICENSE)

> This tool measures download performance to a **specific HTTP(S) endpoint**. It is not a universal measurement of your internet connection.

## Features

- **Sequential measurements** — runs one request at a time; no concurrent downloads.
- **Complete response reads** — consumes each response body in 64 KiB chunks before recording the result.
- **Useful metrics** — reports successful request count, total bytes, average/minimum/maximum request time, standard deviation, and aggregate throughput.
- **Live terminal progress** — displays per-request progress and a relative speed bar in interactive terminals.
- **Machine-readable output** — `--json` emits a structured summary for scripts and automation.
- **Configurable runs** — choose the request count and network timeout.
- **No runtime dependencies** — built entirely on the Python standard library.

## Requirements

- Python **3.9 or newer**
- An internet connection
- A reachable HTTP or HTTPS URL

## Quick start

Clone the repository:

```bash
git clone https://github.com/shakha1210-pixel/Speed-Test-Repo.git
cd Speed-Test-Repo
```

Run the script:

```bash
python speedtest.py https://upload.wikimedia.org/wikipedia/commons/3/3f/Fronalpstock_big.jpg
```

On some macOS and Linux installations, use `python3` instead of `python`.

### Install as a command (optional)

The project includes packaging metadata, so it can also be installed locally:

```bash
python -m pip install .
speedtest https://example.com/large-file.bin
```

## Usage

```text
python speedtest.py URL [options]
```

| Option | Description | Default |
|---|---|---:|
| `URL` | Target HTTP(S) resource | Required |
| `-n`, `--count` | Number of sequential requests | `10` |
| `-t`, `--timeout` | Network operation timeout, in seconds | `30` |
| `--json` | Print the final summary as JSON | Off |
| `--version` | Print the application version | — |
| `-h`, `--help` | Show help | — |

Examples:

```bash
# Run the default 10 measurements
python speedtest.py https://example.com/large-file.bin

# Run 5 sequential requests with a 15-second timeout
python speedtest.py https://example.com/large-file.bin --count 5 --timeout 15

# Produce JSON output
python speedtest.py https://example.com/large-file.bin --json

# Show the installed script version
python speedtest.py --version
```

The timeout is applied to blocking network operations by Python's URL opener; it is not a strict overall deadline for the entire download.

## Example output

The following is an illustrative example. Actual values depend on the target server and network conditions.

```text
  ⚡ SPEEDTEST  download speed measurement
  ──────────────────────────────────────────────────────────
  URL       https://example.com/large-file.bin
  Requests  10  (sequential)

  [ 1/10] ✓     3.41 MB       412 ms     66.2 Mbps  ████████████████████░░░░
  [ 2/10] ✓     3.41 MB       368 ms     74.1 Mbps  ████████████████████████
  ...

  ──────────────────────────────────────────────────────────
  RESULT

  Successful requests    10 of 10
  Total downloaded      34.10 MB
  Average request time    391 ms
  Download throughput   69.80 Mbps   ≈ 8.73 MB/s
```

Colors are enabled in interactive terminals. They are automatically disabled when standard output is redirected or the `NO_COLOR` environment variable is set.

## JSON output

Use `--json` to print the final summary without the interactive terminal display. Each request is represented in the `results` array.

```bash
python speedtest.py https://example.com/large-file.bin --json
```

Example shape (values shortened for readability):

```json
{
  "url": "https://example.com/large-file.bin",
  "requests": 10,
  "successful": 10,
  "failed": 0,
  "total_bytes": 34100000,
  "total_seconds": 3.897,
  "average_time_ms": 390,
  "min_time_ms": 362,
  "max_time_ms": 455,
  "stddev_time_ms": 28,
  "speed_mbit_s": 70.0,
  "speed_mbyte_s": 8.75,
  "results": [
    {
      "index": 1,
      "bytes": 3410000,
      "seconds": 0.412,
      "status": "ok"
    }
  ]
}
```

A failed request has `"status": "error"` and includes an `error` message. Failed requests are excluded from the aggregate timing and throughput calculations.

## Measurement methodology

The script uses `time.perf_counter()`, a high-resolution monotonic timer, and `urllib.request` from the Python standard library.

1. Start the timer immediately before opening the URL.
2. Send one HTTP(S) request.
3. Read the response body in chunks of up to **64 KiB** until the stream ends.
4. Stop the timer after the complete response body has been read.
5. Finish that request before starting the next one.

The measured duration includes connection setup, waiting for the response, and downloading the response body.

### Metrics and formulas

| Metric | Calculation |
|---|---|
| Average request time | Sum of successful request durations ÷ number of successful requests |
| Total downloaded | Sum of bytes actually read from successful response bodies |
| Aggregate throughput | Total downloaded bytes × 8 ÷ total successful-request time ÷ 1,000,000 |
| MB/s | Total downloaded bytes ÷ total successful-request time ÷ 1,000,000 |

- **Mbps** means megabits per second.
- **MB/s** means megabytes per second.
- File sizes use decimal units: **1 MB = 1,000,000 bytes**.
- Request durations are displayed in milliseconds.

Aggregate throughput is calculated from the combined successful transfer volume and time. It is **not** the arithmetic mean of individual request speeds.

## Error handling and exit codes

A failed request is recorded as an error, and the script continues with the remaining requests. Only successful requests contribute to the final aggregate metrics.

| Exit code | Meaning |
|---:|---|
| `0` | Every requested measurement succeeded |
| `1` | At least one request failed |
| `2` | Invalid input, URL, request count, or timeout |
| `130` | Interrupted by the user with `Ctrl+C` |

If every request fails, the script reports that no measurement could be calculated.

## Browser version

A browser-based version is available in [`docs/index.html`](docs/index.html). It provides a visual interface with sequential download measurements and a Three.js scene that reacts to measured speed.

To publish it with GitHub Pages:

1. Open the repository's **Settings → Pages**.
2. Under **Build and deployment**, select **Deploy from a branch**.
3. Choose branch `main` and folder `/docs`.
4. Save the settings.

### Browser limitations

Browsers enforce cross-origin restrictions. The target server must allow requests from the page's origin through its CORS response headers; otherwise, the browser may block access to the response. The command-line version is not subject to browser CORS restrictions.

The browser version measures downloads only. It does not upload local files.

## Project structure

```text
.
├── docs/
│   └── index.html          # Browser-based visual speed test
├── tests/
│   ├── conftest.py         # Local test server and shared fixtures
│   └── test_speedtest.py   # Unit and integration tests
├── speedtest.py            # CLI implementation
├── pyproject.toml           # Package metadata and tool configuration
├── requirements-dev.txt     # Development-only dependencies
├── LICENSE                  # MIT license
└── README.md
```

## Development

Install the development tools:

```bash
python -m pip install -r requirements-dev.txt
```

Run the linter and test suite:

```bash
ruff check .
pytest
```

The runtime application itself does not require `pytest` or `ruff`.

## Limitations

- Results describe the route to the selected server, not an abstract or universal "internet speed".
- CDN routing, server load, caching, geographic distance, and network conditions can affect measurements.
- Requests are sequential and use a single connection per request; this does not benchmark maximum throughput achievable with parallel connections.
- The script measures bytes delivered in the HTTP response body. It does not use the `Content-Length` header as the downloaded-byte count.
- Failed or interrupted transfers do not contribute partial bytes to the final aggregate.

## License

This project is licensed under the [MIT License](LICENSE).
