You are helping me build a Python auto-trading program using the Korea Investment & Securities Open API in the mock trading environment.

Goal:
Create a simple automated trading system for Samsung Electronics (005930) using REST API only.

Core constraints:

- Use Korea Investment Open API
- Mock trading only
- Do NOT use websocket
- Once authenticated, the token can be reused for the rest of the same day
- Required credentials are stored in environment variables:
    - GH_ACCOUNT
    - GH_APPKEY
    - GH_APPSECRET
- Do not hardcode credentials
- Mock trading has a low web request limit, so minimize unnecessary API calls
- The program should save all source files into a newly created project folder
- The project should be modular and easy to run in VS Code

Trading target:

- Stock: Samsung Electronics
- Symbol/code: 005930

Trading logic:

1. Check the current market price of Samsung Electronics
2. Check account balance / holdings
3. Place a buy order at 2,000 KRW below the currently checked price
4. Place a sell order at 2,000 KRW above the currently checked price
5. After placing orders, check balance/holdings again to confirm whether execution actually happened
6. Repeat this process continuously during the trading window only

Trading window:

- Start: 09:10 AM
- End: 03:30 PM
- Outside this window, do not place orders
- The program should stop trading automatically after 03:30 PM

Important behavior:

- This is polling-based only
- Since websocket is not used, rate limiting and conservative polling intervals are very important
- After each order, confirm execution by checking updated holdings / balance
- Avoid excessive repeated balance checks
- Avoid unnecessary token reissuance
- Reuse the cached token for the same day
- Use safe mock-trading design only, with no live-trading assumptions

Implementation requirements:

- Use Python
- Use requests for HTTP calls
- Use a modular folder structure
- Create the project in a new folder, for example:
    - samsung_auto_trader/
        - [main.py](http://main.py/)
        - [config.py](http://config.py/)
        - [auth.py](http://auth.py/)
        - api_client.py
        - market_data.py
        - [account.py](http://account.py/)
        - [orders.py](http://orders.py/)
        - [trader.py](http://trader.py/)
        - [logger.py](http://logger.py/)
        - token_cache.json
        - requirements.txt
        - [README.md](http://readme.md/)
- If a better structure is appropriate, propose it first

Functional requirements:

1. Load environment variables safely
2. Authenticate once and cache token for same-day reuse
3. Get current price for 005930
4. Get account holdings / available balance
5. Submit a buy order at current_price - 1000
6. Submit a sell order at current_price + 1000
7. After submitting each order, verify execution status by checking holdings/balance again
8. Run the loop only between 09:10 and 15:30
9. Add logging for every important action

Logging requirements:

- Log token reuse / token refresh
- Log current price
- Log holdings before order
- Log buy order request
- Log sell order request
- Log holdings after order
- Log whether execution seems to have occurred
- Log API errors, timeouts, and retries
- Log when the trading window starts and ends

Safety and design requirements:

- Prioritize stability and readability over speed
- Keep API usage low because mock trading limits are strict
- Use conservative polling intervals
- Use timeout handling and simple retry logic where appropriate
- Clearly separate API layer from trading logic
- If any API field names or transaction IDs are uncertain, isolate them clearly as placeholders so they can be edited easily later
- Do not overengineer
- Do not suggest websocket
- Do not assume real-time streaming
- Do not assume live trading

What I want from you:

1. First propose the folder structure
2. Then explain the responsibility of each file
3. Then generate the code step by step
4. Keep each module small and testable
5. Make the code production-style, readable, and easy to modify
6. Include comments and type hints where useful
7. Include a simple README with run instructions

Additional note:
The system should be designed to avoid excessive API calls in the mock environment.
At every step, prefer minimizing requests.