""" Database models for the Fiindo recruitment challenge. """
from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class TickerStatistic(Base):
    """
    Model to store calculated statistics per individual ticker.
    """
    __tablename__ = 'ticker_statistics'

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False, index=True)
    industry = Column(String, nullable=False)

    # Financial Metrics
    pe_ratio = Column(Float, nullable=True, comment="Price-to-Earnings ratio (Last Quarter)")
    revenue_growth = Column(Float, nullable=True, comment="QoQ Revenue Growth")
    net_income_ttm = Column(Float, nullable=True, comment="Trailing Twelve Months Net Income")
    debt_ratio = Column(Float, nullable=True, comment="Debt-to-Equity ratio (Last Year)")
    revenue = Column(Float, nullable=True, comment="Latest TTM Revenue for Aggregation")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class IndustryAggregation(Base):
    """
    Model to store aggregated data per industry.
    """
    __tablename__ = 'industry_aggregations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    industry = Column(String, unique=True, nullable=False)

    # Aggregated Metrics
    avg_pe_ratio = Column(Float, nullable=True, comment="Mean PE ratio across all tickers")
    avg_revenue_growth = Column(Float, nullable=True, comment="Mean revenue growth across all tickers")
    sum_revenue = Column(Float, nullable=True, comment="Sum revenue across all tickers")

    created_at = Column(DateTime(timezone=True), server_default=func.now())