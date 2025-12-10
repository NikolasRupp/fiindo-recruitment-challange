import requests
import sys
import logging
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from src.models import Base, TickerStatistic, IndustryAggregation
import os

# --- Configuration ---
BASE_URL = "https://api.test.fiindo.com"
DB_URL = "sqlite:///fiindo_challenge.db"

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

FIRST_NAME = os.getenv("FIRST_NAME", None)
LAST_NAME = os.getenv("LAST_NAME", None)
DEFAULT_INDUSTRIES_STR = "Banks - Diversified,Software - Application,Consumer Electronics"
raw_industries = os.getenv("TARGET_INDUSTRIES", DEFAULT_INDUSTRIES_STR)

if not FIRST_NAME or not LAST_NAME:
	logger.warning("Missing required environment variables! Application requires FIRST_NAME, LAST_NAME to be set.")
	sys.exit(1)

TARGET_INDUSTRIES = [ind.strip() for ind in raw_industries.split(',') if ind.strip()]

HEADERS = {
	"Authorization": f"Bearer {FIRST_NAME}.{LAST_NAME}",
	"Content-Type": "application/json"
}


class FiindoETL:
	def __init__(self):
		"""Initialize DB connection."""
		self.engine = create_engine(DB_URL)
		self.Session = sessionmaker(bind=self.engine)

	def _get_request(self, endpoint, is_json=True):
		"""Helper for API requests."""
		url = f"{BASE_URL}{endpoint}"

		try:
			response = requests.get(url, headers=HEADERS, timeout=10)
			response.raise_for_status()
			if is_json:
				return response.json()
			return response.text
		except requests.exceptions.RequestException as e:
			logger.warning(f"Request failed for {url}: {e}")
			return None

	def check_system_health(self):
		"""Checks API health."""
		response = self._get_request("/health", is_json=False)
		if response and response.startswith('"Ok'):
			logger.info(f"System Health Check Passed: {response}")
			return True
		logger.error("System Health Check Failed.")
		return False

	def get_all_symbols(self):
		"""Fetches symbol list."""
		data = self._get_request("/api/v1/symbols")
		if data and 'symbols' in data:
			return data["symbols"]
		return []

	def get_company_profile(self, symbol):
		"""Fetches profile for industry check."""
		data = self._get_request(f"/api/v1/general/{symbol}")
		try:
			profile_data = data.get('fundamentals', {}).get('profile', {}).get('data', [])
			if profile_data:
				return profile_data[0]
		except (AttributeError, TypeError):
			pass
		return None

	def get_price_eod(self, symbol):
		"""Fetches latest EOD price."""
		data = self._get_request(f"/api/v1/eod/{symbol}")
		try:
			price_data = data.get('stockprice', {}).get('data', [])
			if not price_data: return None
			# Sort by date descending
			sorted_data = sorted(price_data, key=lambda x: x.get('date', ''), reverse=True)
			return sorted_data[0].get('close')
		except (AttributeError, TypeError, IndexError):
			return None

	def get_financials(self, symbol, statement):
		"""
		Fetches financial reports.
		Returns the raw list of data. Separation of FY/Quarter happens in calculation.
		"""
		data = self._get_request(f"/api/v1/financials/{symbol}/{statement}")
		try:
			financials_root = data.get('fundamentals', {}).get('financials', {})
			statement_node = financials_root.get(statement, {})
			return statement_node.get('data', [])
		except (AttributeError, TypeError):
			return None

	def calculate_metrics(self, symbol, industry, price, income_raw, balance_raw):
		"""
		Separates Quarterly and Yearly data to calculate accurate metrics.
		"""
		metrics = {
			'symbol': symbol,
			'industry': industry,
			'pe_ratio': None,
			'revenue_growth': None,
			'net_income_ttm': None,
			'debt_ratio': None,
			'last_revenue': 0
		}

		# --- DATA PREPARATION ---
		# 1. Filter and Sort Income Statement
		# Specific lists for Quarters (Q1-Q4) and Years (FY)
		if not income_raw: income_raw = []

		# Sort descending by date
		income_quarters = sorted(
			[x for x in income_raw if x.get('period') in ['Q1', 'Q2', 'Q3', 'Q4']],
			key=lambda x: x.get('date', ''),
			reverse=True
		)

		income_years = sorted(
			[x for x in income_raw if x.get('period') == 'FY'],
			key=lambda x: x.get('date', ''),
			reverse=True
		)

		# 2. Filter and Sort Balance Sheet
		if not balance_raw: balance_raw = []
		balance_years = sorted(
			[x for x in balance_raw if x.get('period') == 'FY'],
			key=lambda x: x.get('date', ''),
			reverse=True
		)

		# --- CALCULATIONS ---

		# 1. PE Ratio: Price / Earnings (Last Quarter)
		# Use income_quarters index 0
		try:
			if income_quarters:
				last_q_eps = income_quarters[0].get('eps', 0)
				if last_q_eps and last_q_eps != 0:
					metrics['pe_ratio'] = price / last_q_eps
		except Exception:
			pass

		# 2. Revenue Growth: QoQ (Q-1 vs. Q-2)
		# Historical quarters. Index 0 is current (Q), 1 is Q-1, 2 is Q-2.
		try:
			if len(income_quarters) >= 3:
				rev_q1 = income_quarters[1].get('revenue', 0)
				rev_q2 = income_quarters[2].get('revenue', 0)

				if rev_q2 and rev_q2 != 0:
					metrics['revenue_growth'] = (rev_q1 - rev_q2) / rev_q2
		except Exception:
			pass

		# 3. NetIncomeTTM: Sum of last 4 quarters
		# Strictly sum the last 4 available quarterly reports
		try:
			if len(income_quarters) >= 4:
				# Sum netIncome for the first 4 items in the sorted list
				ttm_income = sum(q.get('netIncome', 0) for q in income_quarters[:4])
				metrics['net_income_ttm'] = ttm_income

				# Also calculate TTM Revenue for Industry Aggregation
				metrics['last_revenue'] = sum(q.get('revenue', 0) for q in income_quarters[:4])

			elif income_years:
				# Fallback: if we don't have 4 quarters, use the latest Fiscal Year
				metrics['net_income_ttm'] = income_years[0].get('netIncome', 0)
				metrics['last_revenue'] = income_years[0].get('revenue', 0)
		except Exception:
			pass

		# 4. Debt Ratio: Debt-to-equity from LAST YEAR
		# Use balance_years index 0 (latest FY)
		try:
			if balance_years:
				last_fy = balance_years[0]
				debt = last_fy.get('totalDebt', 0)
				equity = last_fy.get('totalEquity', last_fy.get('totalStockholdersEquity', 0))

				if equity and equity != 0:
					metrics['debt_ratio'] = debt / equity
		except Exception:
			pass

		return metrics

	def run(self):
		"""Main Pipeline Execution"""
		if not self.check_system_health(): return

		session = self.Session()

		logger.info("Fetching symbols...")
		symbols = self.get_all_symbols()
		logger.info(f"Found {len(symbols)} symbols. Starting processing...")

		processed_data = []

		for i, symbol in enumerate(symbols):
			# Log some points to see how much is left
			if i%50 == 0:
				logger.info(f"Processing {i}/{len(symbols)}")
			# 1. Industry Check
			profile = self.get_company_profile(symbol)
			if not profile: continue

			industry = profile.get('industry')
			if industry not in TARGET_INDUSTRIES: continue

			# 2. Fetch Data
			income_raw = self.get_financials(symbol, "income_statement")
			balance_raw = self.get_financials(symbol, "balance_sheet_statement")
			price = self.get_price_eod(symbol) or profile.get('price')

			if price and income_raw:
				# 3. Calculate with Split Logic (FY/Quarter)
				stats = self.calculate_metrics(symbol, industry, price, income_raw, balance_raw)
				existing_stat = session.query(TickerStatistic).filter_by(symbol=stats['symbol']).first()
				# 4. Save
				if existing_stat:
					existing_stat.pe_ratio = stats['pe_ratio']
					existing_stat.revenue_growth = stats['revenue_growth']
					existing_stat.net_income_ttm = stats['net_income_ttm']
					existing_stat.debt_ratio = stats['debt_ratio']
					existing_stat.revenue = stats['last_revenue']
				else:
					db_rec = TickerStatistic(
						symbol=stats['symbol'],
						industry=stats['industry'],
						pe_ratio=stats['pe_ratio'],
						revenue_growth=stats['revenue_growth'],
						net_income_ttm=stats['net_income_ttm'],
						debt_ratio=stats['debt_ratio'],
						revenue = stats['last_revenue']
					)
					session.add(db_rec)
				processed_data.append(stats)

		session.commit()
		logger.info("Ticker stats saved.")

		# 5. Aggregation
		results = session.query(
			TickerStatistic.industry,
			func.avg(TickerStatistic.pe_ratio).label('avg_pe'),
			func.avg(TickerStatistic.revenue_growth).label('avg_growth'),
			func.sum(TickerStatistic.revenue).label('sum_rev')
		).filter(
			TickerStatistic.industry.in_(TARGET_INDUSTRIES)
		).group_by(
			TickerStatistic.industry
		).all()

		for row in results:
			ind = row.industry
			existing_agg = session.query(IndustryAggregation).filter_by(industry=ind).first()

			if existing_agg:
				existing_agg.avg_pe_ratio = row.avg_pe
				existing_agg.avg_revenue_growth = row.avg_growth
				existing_agg.sum_revenue = row.sum_rev
			else:
				agg = IndustryAggregation(
					industry=ind,
					avg_pe_ratio=row.avg_pe,
					avg_revenue_growth=row.avg_growth,
					sum_revenue=row.sum_rev
				)
				session.add(agg)

		session.commit()
		logger.info("Pipeline Done.")
		session.close()


if __name__ == "__main__":
	Base.metadata.create_all(create_engine(DB_URL))
	FiindoETL().run()