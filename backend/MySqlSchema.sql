-- ============================================
-- 1. مشتریان (Customers)
-- ============================================
CREATE TABLE Customers (
    CustomerID      INT IDENTITY(1,1) PRIMARY KEY,
    NationalCode    CHAR(10)        NOT NULL UNIQUE,
    FullName        NVARCHAR(100)   NOT NULL,
    BirthDate       DATE            NOT NULL,
    Phone           VARCHAR(15),
    Mobile          VARCHAR(11)     NOT NULL,
    Email           VARCHAR(100),
    Address         NVARCHAR(300),
    PostalCode      CHAR(10),
    CustomerType    TINYINT         NOT NULL DEFAULT 1, -- 1=حقیقی, 2=حقوقی
    IsActive        BIT             NOT NULL DEFAULT 1,
    CreatedAt       DATETIME        NOT NULL DEFAULT GETDATE()
);

-- ============================================
-- 2. حساب‌های بانکی مشتریان
-- ============================================
CREATE TABLE BankAccounts (
    AccountID       INT IDENTITY(1,1) PRIMARY KEY,
    CustomerID      INT             NOT NULL REFERENCES Customers(CustomerID),
    BankName        NVARCHAR(50)    NOT NULL,
    BranchName      NVARCHAR(50),
    AccountNumber   VARCHAR(30)     NOT NULL UNIQUE,
    ShebaNumber     CHAR(26)        NOT NULL UNIQUE,
    IsDefault       BIT             NOT NULL DEFAULT 0,
    IsVerified      BIT             NOT NULL DEFAULT 0
);

-- ============================================
-- 3. کدهای بورسی (Trading Codes)
-- ============================================
CREATE TABLE TradingCodes (
    TradingCodeID   INT IDENTITY(1,1) PRIMARY KEY,
    CustomerID      INT             NOT NULL REFERENCES Customers(CustomerID),
    TradingCode     VARCHAR(20)     NOT NULL UNIQUE,
    MarketType      TINYINT         NOT NULL, -- 1=بورس, 2=فرابورس, 3=کالا, 4=انرژی
    IssueDate       DATE            NOT NULL,
    IsActive        BIT             NOT NULL DEFAULT 1
);

-- ============================================
-- 4. نمادها (Symbols)
-- ============================================
CREATE TABLE Symbols (
    SymbolID        INT IDENTITY(1,1) PRIMARY KEY,
    SymbolCode      VARCHAR(20)     NOT NULL UNIQUE,
    SymbolName      NVARCHAR(100)   NOT NULL,
    CompanyName     NVARCHAR(200)   NOT NULL,
    ISIN            CHAR(12)        NOT NULL UNIQUE,
    MarketType      TINYINT         NOT NULL, -- 1=بورس, 2=فرابورس
    IndustryGroup   NVARCHAR(100),
    BaseVolume      BIGINT          NOT NULL DEFAULT 1,
    TickSize        DECIMAL(18,2)   NOT NULL DEFAULT 1,
    IsActive        BIT             NOT NULL DEFAULT 1
);

-- ============================================
-- 5. قیمت‌های روزانه نمادها
-- ============================================
CREATE TABLE DailyPrices (
    PriceID         BIGINT IDENTITY(1,1) PRIMARY KEY,
    SymbolID        INT             NOT NULL REFERENCES Symbols(SymbolID),
    TradeDate       DATE            NOT NULL,
    OpenPrice       DECIMAL(18,2)   NOT NULL,
    ClosePrice      DECIMAL(18,2)   NOT NULL,
    LastPrice       DECIMAL(18,2)   NOT NULL,
    HighPrice       DECIMAL(18,2)   NOT NULL,
    LowPrice        DECIMAL(18,2)   NOT NULL,
    YesterdayPrice  DECIMAL(18,2)   NOT NULL,
    TradeVolume     BIGINT          NOT NULL DEFAULT 0,
    TradeValue      DECIMAL(28,2)   NOT NULL DEFAULT 0,
    TradeCount      INT             NOT NULL DEFAULT 0,
    UNIQUE (SymbolID, TradeDate)
);

-- ============================================
-- 6. پرتفوی مشتریان
-- ============================================
CREATE TABLE Portfolio (
    PortfolioID     BIGINT IDENTITY(1,1) PRIMARY KEY,
    TradingCodeID   INT             NOT NULL REFERENCES TradingCodes(TradingCodeID),
    SymbolID        INT             NOT NULL REFERENCES Symbols(SymbolID),
    Quantity        BIGINT          NOT NULL DEFAULT 0,
    AvgBuyPrice     DECIMAL(18,2)   NOT NULL DEFAULT 0,
    BlockedQty      BIGINT          NOT NULL DEFAULT 0,
    UpdatedAt       DATETIME        NOT NULL DEFAULT GETDATE(),
    UNIQUE (TradingCodeID, SymbolID)
);

-- ============================================
-- 7. کیف پول / موجودی نقدی
-- ============================================
CREATE TABLE Wallets (
    WalletID        INT IDENTITY(1,1) PRIMARY KEY,
    TradingCodeID   INT             NOT NULL UNIQUE REFERENCES TradingCodes(TradingCodeID),
    Balance         DECIMAL(28,2)   NOT NULL DEFAULT 0,
    BlockedBalance  DECIMAL(28,2)   NOT NULL DEFAULT 0,
    UpdatedAt       DATETIME        NOT NULL DEFAULT GETDATE()
);

-- ============================================
-- 8. سفارشات (Orders)
-- ============================================
CREATE TABLE Orders (
    OrderID         BIGINT IDENTITY(1,1) PRIMARY KEY,
    TradingCodeID   INT             NOT NULL REFERENCES TradingCodes(TradingCodeID),
    SymbolID        INT             NOT NULL REFERENCES Symbols(SymbolID),
    OrderSide       TINYINT         NOT NULL, -- 1=خرید, 2=فروش
    OrderType       TINYINT         NOT NULL DEFAULT 1, -- 1=محدود, 2=بازار
    Price           DECIMAL(18,2)   NOT NULL,
    Quantity        BIGINT          NOT NULL,
    FilledQty       BIGINT          NOT NULL DEFAULT 0,
    RemainingQty    AS (Quantity - FilledQty),
    OrderStatus     TINYINT         NOT NULL DEFAULT 1,
    -- 1=در صف, 2=ارسال شده, 3=بخشی انجام شده, 4=انجام شده, 5=لغو شده, 6=رد شده
    ExchangeOrderID VARCHAR(50),     -- شناسه سفارش در هسته معاملات
    ValidityType    TINYINT         NOT NULL DEFAULT 1, -- 1=روز, 2=GTC
    ValidityDate    DATE,
    CreatedAt       DATETIME        NOT NULL DEFAULT GETDATE(),
    UpdatedAt       DATETIME        NOT NULL DEFAULT GETDATE(),
    CancelledAt     DATETIME,
    CancelReason    NVARCHAR(200),
    Channel         TINYINT         NOT NULL DEFAULT 1 -- 1=آنلاین, 2=تلفنی, 3=حضوری
);

-- ============================================
-- 9. معاملات انجام شده (Trades)
-- ============================================
CREATE TABLE Trades (
    TradeID         BIGINT IDENTITY(1,1) PRIMARY KEY,
    OrderID         BIGINT          NOT NULL REFERENCES Orders(OrderID),
    TradingCodeID   INT             NOT NULL REFERENCES TradingCodes(TradingCodeID),
    SymbolID        INT             NOT NULL REFERENCES Symbols(SymbolID),
    TradeSide       TINYINT         NOT NULL, -- 1=خرید, 2=فروش
    Price           DECIMAL(18,2)   NOT NULL,
    Quantity        BIGINT          NOT NULL,
    TradeValue      AS (Price * Quantity),
    Commission      DECIMAL(18,2)   NOT NULL DEFAULT 0,
    Tax             DECIMAL(18,2)   NOT NULL DEFAULT 0,
    NetValue        DECIMAL(18,2)   NOT NULL,
    TradeDate       DATE            NOT NULL,
    TradeTime       TIME            NOT NULL,
    ExchangeTradeID VARCHAR(50),
    CreatedAt       DATETIME        NOT NULL DEFAULT GETDATE()
);

-- ============================================
-- 10. کارمزدها (Commission Rules)
-- ============================================
CREATE TABLE CommissionRules (
    RuleID          INT IDENTITY(1,1) PRIMARY KEY,
    MarketType      TINYINT         NOT NULL,
    TradeSide       TINYINT         NOT NULL, -- 1=خرید, 2=فروش
    MinValue        DECIMAL(28,2)   NOT NULL DEFAULT 0,
    MaxValue        DECIMAL(28,2),
    CommissionRate  DECIMAL(10,6)   NOT NULL, -- نرخ کارمزد
    BrokerShare     DECIMAL(10,6)   NOT NULL, -- سهم کارگزار
    IsActive        BIT             NOT NULL DEFAULT 1,
    EffectiveFrom   DATE            NOT NULL
);

-- ============================================
-- 11. واریز و برداشت
-- ============================================
CREATE TABLE Transactions (
    TransactionID   BIGINT IDENTITY(1,1) PRIMARY KEY,
    TradingCodeID   INT             NOT NULL REFERENCES TradingCodes(TradingCodeID),
    AccountID       INT             REFERENCES BankAccounts(AccountID),
    TxType          TINYINT         NOT NULL, -- 1=واریز, 2=برداشت, 3=کارمزد, 4=تسویه
    Amount          DECIMAL(28,2)   NOT NULL,
    BalanceBefore   DECIMAL(28,2)   NOT NULL,
    BalanceAfter    DECIMAL(28,2)   NOT NULL,
    Status          TINYINT         NOT NULL DEFAULT 1, -- 1=در انتظار, 2=تایید, 3=رد
    ReferenceNo     VARCHAR(50),
    Description     NVARCHAR(300),
    CreatedAt       DATETIME        NOT NULL DEFAULT GETDATE(),
    ConfirmedAt     DATETIME
);

-- ============================================
-- 12. کاربران سیستم (کارگزاران / ادمین)
-- ============================================
CREATE TABLE SystemUsers (
    UserID          INT IDENTITY(1,1) PRIMARY KEY,
    Username        VARCHAR(50)     NOT NULL UNIQUE,
    PasswordHash    VARCHAR(256)    NOT NULL,
    FullName        NVARCHAR(100)   NOT NULL,
    Role            TINYINT         NOT NULL, -- 1=ادمین, 2=کارگزار, 3=ناظر
    IsActive        BIT             NOT NULL DEFAULT 1,
    LastLoginAt     DATETIME,
    CreatedAt       DATETIME        NOT NULL DEFAULT GETDATE()
);

-- ============================================
-- ایندکس‌های کلیدی
-- ============================================
CREATE INDEX IX_Orders_TradingCode_Status   ON Orders(TradingCodeID, OrderStatus);
CREATE INDEX IX_Orders_Symbol_Date          ON Orders(SymbolID, CreatedAt);
CREATE INDEX IX_Trades_TradingCode_Date     ON Trades(TradingCodeID, TradeDate);
CREATE INDEX IX_Trades_Symbol_Date          ON Trades(SymbolID, TradeDate);
CREATE INDEX IX_DailyPrices_Date            ON DailyPrices(TradeDate);
CREATE INDEX IX_Transactions_TradingCode    ON Transactions(TradingCodeID, CreatedAt);
