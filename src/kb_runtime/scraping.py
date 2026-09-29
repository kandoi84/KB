"""Live Data Scraper for Indian Equities.

Uses bfinance.Ticker to fetch high-fidelity audited financials and qualitative data.
"""

import os
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from bfinance import Ticker

class LiveScraper:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.data_dir = root_dir / "raw_data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def get_company_details(self, symbol: str) -> Dict[str, Any]:
        """Fetch basic company details using bfinance.Ticker."""
        try:
            ticker = Ticker(symbol)
            info = ticker.info
            # ISIN is often not in .info for all tickers; use symbol as fallback
            isin = info.get("isin") or f"ISIN_{symbol}"
            return {
                "symbol": symbol,
                "name": info.get("longName"),
                "sector": ticker.sector,
                "industry": ticker.industry,
                "isin": isin
            }
        except Exception as e:
            print(f"Error fetching company details for {symbol}: {e}")
            return {"symbol": symbol, "isin": f"ISIN_{symbol}"}

    def fetch_financials(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Fetch historical audited financials.
        Uses bfinance's deep history (10-12 years).
        """
        try:
            ticker = Ticker(symbol)
            df_income = ticker.financials
            
            metrics = []
            if df_income is not None and not df_income.empty:
                for metric_name, row in df_income.iterrows():
                    for period, value in row.items():
                        if pd.isna(value): continue
                        filing_date = self._parse_period_to_date(period)
                        metrics.append({
                            "metric_name": metric_name,
                            "value": float(value),
                            "period_end": str(period),
                            "filing_date": filing_date,
                            "version_id": f"m_{metric_name}_{filing_date}"
                        })
            return metrics
        except Exception as e:
            print(f"Error fetching financials for {symbol}: {e}")
            return []

    def fetch_concalls(self, symbol: str) -> List[Dict[str, Any]]:
        """Fetch concall transcripts and audio links using bfinance.Ticker."""
        try:
            ticker = Ticker(symbol)
            concalls = ticker.concalls 
            
            results = []
            for call in concalls:
                # Handle both object and dict forms
                pdf_url = getattr(call, 'pdf_url', None) if not isinstance(call, dict) else call.get('pdf_url')
                date = getattr(call, 'date', None) if not isinstance(call, dict) else call.get('date')
                quarter = getattr(call, 'quarter', None) if not isinstance(call, dict) else call.get('quarter')
                
                pdf_path = self._download_file(pdf_url, f"{symbol}_concalls")
                
                results.append({
                    "date": date,
                    "quarter": quarter,
                    "pdf_path": str(pdf_path) if pdf_path else None,
                    "audio_url": getattr(call, 'audio_url', None) if not isinstance(call, dict) else call.get('audio_url'),
                    "transcript_text": getattr(call, 'transcript_text', None) if not isinstance(call, dict) else call.get('transcript_text')
                })
            return results
        except Exception as e:
            print(f"Error fetching concalls for {symbol}: {e}")
            return []

    def _parse_period_to_date(self, period: Any) -> str:
        """Converts period (Datetime or string) to YYYY-MM-DD."""
        try:
            return pd.to_datetime(period).strftime("%Y-%m-%d")
        except:
            return datetime.now().strftime("%Y-%m-%d")

    def _download_file(self, url: str, folder: str) -> Optional[Path]:
        """Helper to download a file to the raw_data directory."""
        if not url: return None
        try:
            import requests
            dest_folder = self.data_dir / folder
            dest_folder.mkdir(parents=True, exist_ok=True)
            filename = url.split("/")[-1]
            path = dest_folder / filename
            response = requests.get(url, timeout=10)
            with open(path, "wb") as f:
                f.write(response.content)
            return path
        except Exception as e:
            print(f"Download failed for {url}: {e}")
            return None
