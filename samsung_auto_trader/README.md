# Samsung Auto Trader

Polling-based mock auto trader for Samsung Electronics (`005930`) using the Korea Investment & Securities Open API REST endpoints only.

## Folder structure

- `main.py`: entry point for VS Code or terminal runs
- `config.py`: environment loading, account parsing, and API/TR ID settings
- `auth.py`: same-day token caching and refresh
- `api_client.py`: shared HTTP client, retries, and `hashkey` issuance
- `market_data.py`: current price lookup
- `account.py`: holdings and available cash lookup
- `orders.py`: buy/sell order submission and execution inquiry
- `trader.py`: trading-window loop and order verification flow
- `logger.py`: logging setup
- `token_cache.json`: persisted same-day access token cache
- `requirements.txt`: minimal runtime dependency

## Assumptions

- Mock trading only. Default base URL is `https://openapivts.koreainvestment.com:29443`.
- `GH_ACCOUNT` is expected as `12345678`, `12345678-01`, or `1234567801`.
- The trading logic defaults to placing a buy order `2000 KRW` below and a sell order `2000 KRW` above the last polled price because that is the primary rule in `CODEX.md`.
- KIS field names and some TR IDs can vary by account/product. The code isolates those values in `config.py` and uses alias-based parsing in `account.py` and `orders.py` so they can be adjusted quickly if your mock account responds differently.

## Required environment variables

You can either set environment variables or fill in `credentials.local.json`.

For class demos, the easiest path is to open `credentials.local.json` and fill in:

```json
{
  "VTS": "https://openapivts.koreainvestment.com:29443",
  "PROD": "https://openapi.koreainvestment.com:9443",
  "CANO": "12345678-01",
  "ACNT_PRDT_CD": "01",
  "VTS_APPKEY": "your_mock_app_key",
  "VTS_APPSECRET": "your_mock_app_secret",
  "VTS_TOKEN": ""
}
```

`VTS_TOKEN` is optional. Leave it empty to let the program issue and cache a token automatically.

If you prefer PowerShell environment variables:

```powershell
$env:GH_ACCOUNT="12345678-01"
$env:GH_APPKEY="your_app_key"
$env:GH_APPSECRET="your_app_secret"
```

## Optional environment variables

```powershell
$env:GH_BUY_OFFSET_KRW="2000"
$env:GH_SELL_OFFSET_KRW="2000"
$env:GH_ORDER_QUANTITY="1"
$env:GH_POLL_INTERVAL_SECONDS="60"
$env:GH_POST_ORDER_WAIT_SECONDS="15"
$env:GH_TRADING_START="09:10"
$env:GH_TRADING_END="15:30"
```

## Run

```powershell
cd samsung_auto_trader
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## Logging behavior

The program logs:

- token reuse and token refresh
- current price
- holdings before orders
- buy and sell order requests
- holdings after each post-order verification
- detected execution changes
- API errors, timeouts, and retries
- trading-window start and end

## Notes

- This implementation intentionally avoids websocket usage.
- It also avoids repeated token issuance by persisting the same-day access token to `token_cache.json`.
- To keep mock-trading API usage low, the bot does not open additional quote streams and only performs the minimum REST calls required for each cycle.
