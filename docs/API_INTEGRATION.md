# API Integration Guide

This guide covers how to integrate your trading applications with the IB Docker container's API.

## API Overview

The container exposes Interactive Brokers' TWS API through standard TCP ports, making it accessible to any programming language that supports socket connections.

### Available APIs

| API Type | Protocol | Default Ports |
|----------|----------|---------------|
| TWS API | TCP Socket | 4001 (live), 4002 (paper) |
| FIX API | FIX Protocol | 4101 (live), 4102 (paper) |
| Web API | HTTP/REST | 5000 (Gateway only) |

## Connection Basics

### API Ports by Program and Mode

| Program | Mode | Port | Description |
|---------|------|------|-------------|
| Gateway | Live | 4001 | Live trading API |
| Gateway | Paper | 4002 | Paper trading API |
| TWS | Live | 7496 | Live trading API |
| TWS | Paper | 7497 | Paper trading API |

### Connection Testing

```bash
# Test API connectivity
telnet localhost 4002

# Expected response for successful connection
# (should connect without immediate disconnection)
```

## Python Integration

### Using ibapi (Official IB Python API)

#### Installation
```bash
pip install ibapi
```

#### Basic Connection Example

```python
# basic_connection.py
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
import threading
import time

class IBApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)

    def nextValidId(self, orderId):
        print(f"Connected. Next valid order ID: {orderId}")
        self.start_requests()

    def error(self, reqId, errorCode, errorString):
        print(f"Error {errorCode}: {errorString}")

    def connectionClosed(self):
        print("Connection closed")

    def start_requests(self):
        # Request market data
        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"

        self.reqMktData(1, contract, "", False, False, [])

def main():
    app = IBApp()

    # Connect to the Docker container
    app.connect("localhost", 4002, clientId=1)  # Paper trading

    # Start the message loop in a separate thread
    api_thread = threading.Thread(target=app.run)
    api_thread.start()

    # Keep the main thread alive
    try:
        time.sleep(30)
    except KeyboardInterrupt:
        pass
    finally:
        app.disconnect()

if __name__ == "__main__":
    main()
```

#### Advanced Example with Order Placement

```python
# trading_example.py
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
import threading
import time

class TradingApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.next_order_id = None

    def nextValidId(self, orderId):
        self.next_order_id = orderId
        print(f"Connected. Next order ID: {orderId}")

    def orderStatus(self, orderId, status, filled, remaining,
                   avgFillPrice, permId, parentId, lastFillPrice,
                   clientId, whyHeld, mktCapPrice):
        print(f"Order {orderId}: {status}")

    def execDetails(self, reqId, contract, execution):
        print(f"Execution: {execution.execId} - {contract.symbol}")

    def create_stock_contract(self, symbol):
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        return contract

    def create_market_order(self, action, quantity):
        order = Order()
        order.action = action
        order.totalQuantity = quantity
        order.orderType = "MKT"
        return order

    def place_order(self, symbol, action, quantity):
        if self.next_order_id is None:
            print("Not connected yet")
            return

        contract = self.create_stock_contract(symbol)
        order = self.create_market_order(action, quantity)

        self.placeOrder(self.next_order_id, contract, order)
        self.next_order_id += 1

def main():
    app = TradingApp()
    app.connect("localhost", 4002, clientId=1)

    api_thread = threading.Thread(target=app.run)
    api_thread.start()

    # Wait for connection
    time.sleep(2)

    # Place a sample order (paper trading)
    app.place_order("AAPL", "BUY", 10)

    time.sleep(10)
    app.disconnect()

if __name__ == "__main__":
    main()
```

### Using ib_insync (Simplified Async API)

#### Installation
```bash
pip install ib_insync
```

#### Example Usage

```python
# ib_insync_example.py
from ib_insync import *
import asyncio

async def main():
    # Connect to container
    ib = IB()
    await ib.connectAsync('localhost', 4002, clientId=1)

    # Create contract
    contract = Stock('AAPL', 'SMART', 'USD')
    await ib.qualifyContractsAsync(contract)

    # Get market data
    ticker = ib.reqMktData(contract)
    await asyncio.sleep(2)  # Wait for data

    print(f"AAPL Price: {ticker.marketPrice()}")

    # Place order
    order = MarketOrder('BUY', 10)
    trade = ib.placeOrder(contract, order)

    # Wait for order status
    await asyncio.sleep(5)
    print(f"Order status: {trade.orderStatus.status}")

    ib.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

## Java Integration

### Maven Dependencies

```xml
<!-- pom.xml -->
<dependencies>
    <dependency>
        <groupId>com.interactivebrokers</groupId>
        <artifactId>tws-api</artifactId>
        <version>10.19.01</version>
    </dependency>
</dependencies>
```

### Basic Java Example

```java
// IBConnection.java
import com.ib.client.*;
import java.io.IOException;

public class IBConnection implements EWrapper {
    private EClientSocket client;
    private int nextOrderId;

    public IBConnection() {
        EJavaSignal signal = new EJavaSignal();
        client = new EClientSocket(this, signal);
    }

    public void connect() {
        client.eConnect("localhost", 4002, 1);

        final EReader reader = new EReader(client, signal);
        reader.start();

        new Thread(() -> {
            while (client.isConnected()) {
                signal.waitForSignal();
                try {
                    reader.processMsgs();
                } catch (Exception e) {
                    System.out.println("Exception: " + e.getMessage());
                }
            }
        }).start();
    }

    @Override
    public void nextValidId(int orderId) {
        this.nextOrderId = orderId;
        System.out.println("Connected. Next order ID: " + orderId);
        requestMarketData();
    }

    private void requestMarketData() {
        Contract contract = new Contract();
        contract.symbol("AAPL");
        contract.secType("STK");
        contract.exchange("SMART");
        contract.currency("USD");

        client.reqMktData(1, contract, "", false, false, null);
    }

    @Override
    public void tickPrice(int tickerId, int field, double price,
                         TickAttrib attribs) {
        System.out.println("Tick Price: " + price);
    }

    // Implement other EWrapper methods...
    @Override public void error(Exception e) { System.out.println("Error: " + e.getMessage()); }
    @Override public void error(String str) { System.out.println("Error: " + str); }
    @Override public void error(int id, int errorCode, String errorMsg) {
        System.out.println("Error " + errorCode + ": " + errorMsg);
    }
    // ... other required methods
}
```

## C# Integration

### NuGet Package
```bash
Install-Package IBApi
```

### C# Example

```csharp
// IBClient.cs
using IBApi;
using System;
using System.Threading;

public class IBClient : EWrapper
{
    private EClientSocket client;
    private int nextOrderId;

    public IBClient()
    {
        EReaderSignal signal = new EReaderMonitorSignal();
        client = new EClientSocket(this, signal);
    }

    public void Connect()
    {
        client.eConnect("localhost", 4002, 1);

        var reader = new EReader(client, signal);
        reader.Start();

        new Thread(() => {
            while (client.IsConnected())
            {
                signal.waitForSignal();
                reader.processMsgs();
            }
        }) { IsBackground = true }.Start();
    }

    public void nextValidId(int orderId)
    {
        nextOrderId = orderId;
        Console.WriteLine($"Connected. Next order ID: {orderId}");
        RequestMarketData();
    }

    private void RequestMarketData()
    {
        Contract contract = new Contract();
        contract.Symbol = "AAPL";
        contract.SecType = "STK";
        contract.Exchange = "SMART";
        contract.Currency = "USD";

        client.reqMktData(1, contract, "", false, false, null);
    }

    public void tickPrice(int tickerId, int field, double price, TickAttrib attribs)
    {
        Console.WriteLine($"Price: {price}");
    }

    // Implement other required methods...
    public void error(Exception e) { Console.WriteLine($"Error: {e.Message}"); }
    public void error(string str) { Console.WriteLine($"Error: {str}"); }
    public void error(int id, int errorCode, string errorMsg)
    {
        Console.WriteLine($"Error {errorCode}: {errorMsg}");
    }
}
```

## JavaScript/Node.js Integration

### NPM Installation
```bash
npm install @stoqey/ib
```

### JavaScript Example

```javascript
// ib_client.js
const { IBApi, ErrorCode, EventName } = require('@stoqey/ib');

class IBClient {
    constructor() {
        this.ib = new IBApi({
            clientId: 1,
            host: 'localhost',
            port: 4002
        });

        this.setupEventHandlers();
    }

    setupEventHandlers() {
        this.ib.on(EventName.connected, () => {
            console.log('Connected to IB');
        });

        this.ib.on(EventName.nextValidId, (orderId) => {
            console.log(`Next order ID: ${orderId}`);
            this.requestMarketData();
        });

        this.ib.on(EventName.tickPrice, (tickerId, field, price) => {
            console.log(`Price update: ${price}`);
        });

        this.ib.on(EventName.error, (error, code, id) => {
            console.log(`Error ${code}: ${error}`);
        });
    }

    connect() {
        this.ib.connect();
    }

    requestMarketData() {
        const contract = {
            symbol: 'AAPL',
            secType: 'STK',
            exchange: 'SMART',
            currency: 'USD'
        };

        this.ib.reqMktData(1, contract, '', false, false);
    }

    disconnect() {
        this.ib.disconnect();
    }
}

// Usage
const client = new IBClient();
client.connect();

// Cleanup after 30 seconds
setTimeout(() => {
    client.disconnect();
}, 30000);
```

## Common Integration Patterns

### Connection Management

```python
# connection_manager.py
import time
import threading
from ibapi.client import EClient
from ibapi.wrapper import EWrapper

class ConnectionManager(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.connected = False
        self.connection_lock = threading.Lock()

    def connect_with_retry(self, host='localhost', port=4002,
                          client_id=1, max_retries=5):
        for attempt in range(max_retries):
            try:
                self.connect(host, port, client_id)

                # Start API thread
                api_thread = threading.Thread(target=self.run)
                api_thread.daemon = True
                api_thread.start()

                # Wait for connection confirmation
                timeout = time.time() + 10  # 10 second timeout
                while not self.connected and time.time() < timeout:
                    time.sleep(0.1)

                if self.connected:
                    print(f"Connected on attempt {attempt + 1}")
                    return True

            except Exception as e:
                print(f"Connection attempt {attempt + 1} failed: {e}")

            time.sleep(2 ** attempt)  # Exponential backoff

        return False

    def nextValidId(self, orderId):
        with self.connection_lock:
            self.connected = True

    def connectionClosed(self):
        with self.connection_lock:
            self.connected = False
```

### Error Handling

```python
# error_handler.py
class ErrorHandler:
    def __init__(self):
        self.error_callbacks = {}

    def register_error_callback(self, error_code, callback):
        if error_code not in self.error_callbacks:
            self.error_callbacks[error_code] = []
        self.error_callbacks[error_code].append(callback)

    def handle_error(self, req_id, error_code, error_string):
        print(f"Error {error_code}: {error_string}")

        # Handle specific errors
        if error_code == 502:  # Couldn't connect to TWS
            self.handle_connection_error()
        elif error_code == 200:  # No security definition found
            self.handle_contract_error(req_id)
        elif error_code in [1100, 1101, 1102]:  # Connectivity issues
            self.handle_connectivity_issue(error_code)

        # Call registered callbacks
        if error_code in self.error_callbacks:
            for callback in self.error_callbacks[error_code]:
                callback(req_id, error_string)

    def handle_connection_error(self):
        print("Attempting to reconnect...")
        # Implement reconnection logic

    def handle_contract_error(self, req_id):
        print(f"Invalid contract for request {req_id}")
        # Implement contract validation

    def handle_connectivity_issue(self, error_code):
        print(f"Connectivity issue: {error_code}")
        # Implement connectivity recovery
```

## Performance Optimization

### Connection Pooling

```python
# connection_pool.py
import queue
import threading
from contextlib import contextmanager

class ConnectionPool:
    def __init__(self, host='localhost', port=4002, max_connections=5):
        self.host = host
        self.port = port
        self.max_connections = max_connections
        self.pool = queue.Queue(maxsize=max_connections)
        self.lock = threading.Lock()

        # Pre-populate pool
        for i in range(max_connections):
            conn = self.create_connection(client_id=i+1)
            self.pool.put(conn)

    def create_connection(self, client_id):
        # Create and return a new connection
        conn = ConnectionManager()
        conn.connect_with_retry(self.host, self.port, client_id)
        return conn

    @contextmanager
    def get_connection(self):
        conn = self.pool.get()
        try:
            yield conn
        finally:
            self.pool.put(conn)
```

### Batch Operations

```python
# batch_operations.py
class BatchProcessor:
    def __init__(self, connection):
        self.connection = connection
        self.batch_size = 50
        self.request_queue = queue.Queue()

    def add_request(self, request_type, params):
        self.request_queue.put((request_type, params))

    def process_batch(self):
        batch = []
        for _ in range(self.batch_size):
            try:
                request = self.request_queue.get_nowait()
                batch.append(request)
            except queue.Empty:
                break

        for request_type, params in batch:
            if request_type == 'market_data':
                self.connection.reqMktData(**params)
            elif request_type == 'contract_details':
                self.connection.reqContractDetails(**params)
            # Add more request types as needed

        return len(batch)
```

## Testing and Debugging

### API Testing Script

```python
# test_api.py
import unittest
import time
from connection_manager import ConnectionManager

class TestAPIConnection(unittest.TestCase):
    def setUp(self):
        self.client = ConnectionManager()
        self.connected = self.client.connect_with_retry()

    def tearDown(self):
        if self.client.isConnected():
            self.client.disconnect()

    def test_connection(self):
        self.assertTrue(self.connected)
        self.assertTrue(self.client.isConnected())

    def test_market_data_request(self):
        # Test market data request
        pass

    def test_order_placement(self):
        # Test order placement (paper trading only)
        pass

if __name__ == '__main__':
    unittest.main()
```

### Debug Logging

```python
# debug_logging.py
import logging
from ibapi.client import EClient
from ibapi.wrapper import EWrapper

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ib_api.log'),
        logging.StreamHandler()
    ]
)

class DebugClient(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.logger = logging.getLogger(__name__)

    def nextValidId(self, orderId):
        self.logger.info(f"Next valid order ID: {orderId}")

    def error(self, reqId, errorCode, errorString):
        self.logger.error(f"Error {errorCode} for request {reqId}: {errorString}")

    def tickPrice(self, tickerId, field, price, attribs):
        self.logger.debug(f"Tick price - ID: {tickerId}, Field: {field}, Price: {price}")
```

## Best Practices

### 1. Connection Management
- Always implement reconnection logic
- Use appropriate client IDs for multiple connections
- Handle connection timeouts gracefully

### 2. Error Handling
- Implement comprehensive error handling
- Log all errors for debugging
- Have fallback strategies for common errors

### 3. Rate Limiting
- Respect IB's API rate limits
- Implement request queuing
- Use batch operations when possible

### 4. Data Management
- Store historical data locally when possible
- Implement data validation
- Handle market data gaps appropriately

### 5. Security
- Use paper trading for development and testing
- Implement proper authentication
- Secure API credentials

### 6. Monitoring
- Log all API interactions
- Monitor connection health
- Set up alerts for critical failures
