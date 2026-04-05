{
  "workflows": [
    {
      "name": "Stock Alert Pipeline",
      "description": "Monitors portfolio stocks, triggers alerts on price/volume breakouts",
      "trigger": "Schedule (every 15 min)",
      "nodes": ["Schedule Trigger", "HTTP Request (Yahoo Finance)", "IF Node (Price > Target)", "Telegram/Email Alert"],
      "webhook": "/api/n8n/stock-alert"
    },
    {
      "name": "Earnings Calendar Tracker",
      "description": "Fetches upcoming earnings dates, pre-populates analysis queue",
      "trigger": "Daily 6AM",
      "nodes": ["Cron Trigger", "HTTP Request (Earnings API)", "Filter (Next 7 Days)", "Webhook to Celesys"],
      "webhook": "/api/n8n/earnings-calendar"
    },
    {
      "name": "Sector Rotation Scanner",
      "description": "Scans sector ETFs daily, identifies rotation patterns",
      "trigger": "Daily 9:30 AM",
      "nodes": ["Schedule", "HTTP Batch (11 Sector ETFs)", "Calculate Returns", "Rank & Score", "Store Results"],
      "webhook": "/api/n8n/sector-rotation"
    },
    {
      "name": "Portfolio Rebalance Signal",
      "description": "Compares current allocation vs target, signals rebalance needs",
      "trigger": "Weekly Monday 8AM",
      "nodes": ["Schedule", "Fetch Holdings", "Calculate Drift", "IF Drift > 5%", "Rebalance Alert"],
      "webhook": "/api/n8n/rebalance"
    },
    {
      "name": "News Sentiment Pipeline",
      "description": "Aggregates financial news, scores sentiment, flags material events",
      "trigger": "Every 30 min",
      "nodes": ["Schedule", "RSS Feed (Multiple Sources)", "AI Sentiment Analysis", "Score & Categorize", "Dashboard Update"],
      "webhook": "/api/n8n/news-sentiment"
    },
    {
      "name": "DCF Model Auto-Update",
      "description": "Refreshes DCF models when new quarterly data arrives",
      "trigger": "On Earnings Release",
      "nodes": ["Webhook Trigger", "Fetch Financials", "Run DCF Calculator", "Compare vs Previous", "Store & Alert"],
      "webhook": "/api/n8n/dcf-update"
    }
  ]
}
