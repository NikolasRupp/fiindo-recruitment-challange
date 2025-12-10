import unittest
from unittest.mock import patch, MagicMock
import sys
import os

os.environ['FIRST_NAME'] = "Test"
os.environ['LAST_NAME'] = "User"
os.environ['TARGET_INDUSTRIES'] = "Banks - Diversified,Software - Application,Consumer Electronics"

# Add the project root to sys.path to ensure we can import src.main
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.main import FiindoETL


class TestFiindoETL(unittest.TestCase):

	def setUp(self):
		"""
		Setup method run before every test.
		We initialize the ETL class but mock the database engine to avoid file creation.
		"""
		# We patch create_engine to use an in-memory database for testing
		with patch('src.main.create_engine') as mock_engine:
			self.etl = FiindoETL()
			# Verify engine was created
			mock_engine.assert_called()

	@patch('src.main.requests.get')
	def test_check_system_health_success(self, mock_get):
		"""Test that system health returns True when API returns 'Ok'."""
		# Setup mock response
		mock_response = MagicMock()
		mock_response.text = '"Ok 0.1.190"'
		mock_response.status_code = 200
		mock_get.return_value = mock_response

		# Execute
		result = self.etl.check_system_health()

		# Assert
		self.assertTrue(result)

	@patch('src.main.requests.get')
	def test_get_all_symbols(self, mock_get):
		"""Test parsing of the symbol list."""
		mock_response = MagicMock()
		mock_response.json.return_value = {"symbols": ["ABC.L", "XYZ.L"]}
		mock_response.status_code = 200
		mock_get.return_value = mock_response

		result = self.etl.get_all_symbols()
		self.assertEqual(result, ["ABC.L", "XYZ.L"])

	@patch('src.main.requests.get')
	def test_get_price_eod_sorting(self, mock_get):
		"""
		CRITICAL TEST: Ensure EOD price logic sorts by date descending.
		The API might return mixed order; we must pick the LATEST date.
		"""
		mock_data = {
			"stockprice": {
				"data": [
					{"date": "2023-01-01", "close": 100.0},  # Old
					{"date": "2023-01-05", "close": 150.0},  # Newest -> Should pick this
					{"date": "2023-01-03", "close": 120.0}  # Middle
				]
			}
		}
		mock_response = MagicMock()
		mock_response.json.return_value = mock_data
		mock_response.status_code = 200
		mock_get.return_value = mock_response

		price = self.etl.get_price_eod("TEST")

		# Should be 150.0 because 2023-01-05 is the latest date
		self.assertEqual(price, 150.0)

	def test_calculate_metrics_logic(self):
		"""
		COMPREHENSIVE LOGIC TEST.
		This tests the calculate_metrics method without calling the API.
		We provide raw dictionaries mimicking the mixed FY/Quarter API response.
		"""
		symbol = "TEST.L"
		industry = "Banks"
		price = 100.0

		# --- Mock Income Data ---
		# Scenario:
		# - We have Quarterly reports (Q1-Q4) and Yearly reports (FY).
		# - We must filter out FY for growth/PE/TTM calculations.
		# - Data is unsorted to test sorting logic.
		income_raw = [
			# Q1 2024 (Current)
			{"date": "2024-03-31", "period": "Q1", "eps": 2.0, "revenue": 1000, "netIncome": 100},
			# FY 2023 (Should be ignored for Q-growth, but is a distractor)
			{"date": "2023-12-31", "period": "FY", "eps": 10.0, "revenue": 5000, "netIncome": 500},
			# Q4 2023 (Previous Quarter - Index 1)
			{"date": "2023-12-31", "period": "Q4", "eps": 2.5, "revenue": 1200, "netIncome": 120},
			# Q3 2023 (Q-2 - Index 2) -> Used for growth denominator
			{"date": "2023-09-30", "period": "Q3", "eps": 1.5, "revenue": 1000, "netIncome": 100},
			# Q2 2023 (Index 3) -> Used for TTM sum
			{"date": "2023-06-30", "period": "Q2", "eps": 1.5, "revenue": 1000, "netIncome": 100},
		]

		# --- Mock Balance Sheet ---
		# Scenario: Logic requires "Last Year" data.
		balance_raw = [
			{"date": "2023-12-31", "period": "FY", "totalDebt": 500, "totalEquity": 1000},  # Latest FY
			{"date": "2022-12-31", "period": "FY", "totalDebt": 200, "totalEquity": 800},  # Old FY
		]

		# Execute Calculation
		metrics = self.etl.calculate_metrics(symbol, industry, price, income_raw, balance_raw)

		# --- ASSERTIONS ---

		# 1. PE Ratio
		# Logic: Price / Last Quarter EPS (Q1 2024)
		# 100.0 / 2.0 = 50.0
		self.assertEqual(metrics['pe_ratio'], 50.0)

		# 2. Revenue Growth
		# Logic: (Q_prev - Q_pre_prev) / Q_pre_prev
		# Uses Index 1 (Q4 2023) and Index 2 (Q3 2023)
		# (1200-1000) / 1000 = 0.2 (20% growth)
		self.assertAlmostEqual(metrics['revenue_growth'], 0.2)

		# 3. Net Income TTM
		# Logic: Sum of latest 4 quarters (Q1 2024 + Q4 2023 + Q3 2023 + Q2 2023)
		# 100 + 120 + 100 + 100 = 420
		# NOTE: It should NOT include the 500 from the FY report.
		self.assertEqual(metrics['net_income_ttm'], 420)

		# 4. Debt Ratio
		# Logic: Debt / Equity from latest Balance Sheet FY
		# 500 / 1000 = 0.5
		self.assertEqual(metrics['debt_ratio'], 0.5)

	def test_calculate_metrics_insufficient_data(self):
		"""Test that the code handles missing data gracefully without crashing."""
		income_raw = [{"date": "2024-03-31", "period": "Q1", "eps": 0}]  # Only 1 report, EPS is 0
		balance_raw = []

		metrics = self.etl.calculate_metrics("TEST", "Ind", 100.0, income_raw, balance_raw)

		# PE should be None (divide by zero or missing eps)
		self.assertIsNone(metrics['pe_ratio'])
		# Growth should be None (not enough quarters)
		self.assertIsNone(metrics['revenue_growth'])
		# Debt Ratio should be None (no balance sheet)
		self.assertIsNone(metrics['debt_ratio'])

	@patch('src.main.requests.get')
	def test_get_financials_deep_parsing(self, mock_get):
		"""Test parsing the nested JSON structure from financials."""
		# API returns structure: fundamentals -> financials -> statement_type -> data
		mock_data = {
			"fundamentals": {
				"financials": {
					"income_statement": {
						"data": [{"test_key": "success"}]
					}
				}
			}
		}

		mock_response = MagicMock()
		mock_response.json.return_value = mock_data
		mock_response.status_code = 200
		mock_get.return_value = mock_response

		# Call with a specific statement type
		result = self.etl.get_financials("SYM", "income_statement")

		# Should return the inner list
		self.assertEqual(len(result), 1)
		self.assertEqual(result[0]['test_key'], "success")


if __name__ == '__main__':
	unittest.main()