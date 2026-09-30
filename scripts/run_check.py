"""Script for Render Cron Job — runs check_alerts task."""
from app.workers.quotes import check_alerts

if __name__ == "__main__":
    check_alerts()