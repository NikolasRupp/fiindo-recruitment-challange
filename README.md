# Fiindo Recruitment Challenge

## Fiindo ETL Pipeline

A data processing application that extracts financial data from the Fiindo API calculates key metrics (PE Ratio, Revenue Growth, etc.), and stores the results in an SQLite database.

### Features
- **ETL Pipeline**: Extracts financial data, transforms it (calculating PE Ratio, Revenue Growth, Net Income TTM, Debt Ratio), and loads it into SQLite.
- **Robustness**: Includes health checks and smart filtering for mixed fiscal periods (Quarters vs. Fiscal Years).
- **Dockerized**: Easy to run with Docker Compose.
- **Testing**: Comprehensive unit tests covering logic and edge cases.

### Prerequisites
- Docker & Docker Compose
- *Or* Python 3.10+ (for local manual runs)

### Quick Start (Docker)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/NikolasRupp/fiindo-recruitment-challange
   cd fiindo-recruitment-challange
   ```

2. Run the application: This builds the image and starts the container.
   ```bash
   # Default run (uses default names)
   docker-compose up --build

   # Custom run (override names and industries)
   # Windows PowerShell:
   $env:FIRST_NAME="Jane"; $env:LAST_NAME="Doe"; docker-compose up --build

   # Linux/Mac:
   FIRST_NAME="Jane" LAST_NAME="Doe" docker-compose up --build
   ```

3. Check the Output

   The application will log its progress. Once finished, you will see "Pipeline Done." and the container will exit. The database fiindo_challenge.db will be updated in your local folder.

### Running Tests
To run the unit tests (which do not require API access), execute:

```bash
# Using Python directly
python -m unittest discover tests

# Or inside Docker (if container is running)
docker exec -it fiindo_etl_container python -m unittest discover tests
```

### Configuration
| Variable          | Description                                   | Default                                                           |
|-------------------|-----------------------------------------------|-------------------------------------------------------------------|
| FIRST_NAME        | Your first name for API Auth                  | None (Required)                                                   |
| LAST_NAME         | Your last name for API Auth                   | None (Required)                                                   |
| TARGET_INDUSTRIES | Comma-separated list of industries to process | Banks - Diversified, Software - Application, Consumer Electronics |

---

This repository contains a coding challenge for fiindo candidates. Candidates should fork this repository and implement their solution based on the requirements below.

## Challenge Overview

Create a data processing application that:
- Fetches financial data from an API
- Performs calculations on stock ticker data
- Saves results to an SQLite database

## Technical Requirements

### Input
- **API Endpoint**: `https://api.test.fiindo.com` (docs: `https://api.test.fiindo.com/api/v1/docs/`)
- **Authentication**: Use header `Auhtorization: Bearer {first_name}.{last_name}` with every request. Anything else WILL BE IGNORED. No other format or value will be accepted.
- **Template**: This forked repository as starting point

### Output
- **Database**: SQLite database with processed financial data
- **Tables**: Individual ticker statistics and industry aggregations

## Process Steps

### 1. Data Collection
- Connect to the Fiindo API
- Authenticate using your identifier `Auhtorization: Bearer {first_name}.{last_name}`
- Fetch financial data

### 2. Data Calculations

Calculate data for symbols only from those 3 industries:
  - `Banks - Diversified`
  - `Software - Application`
  - `Consumer Electronics`

#### Per Ticker Statistics
- **PE Ratio**: Price-to-Earnings ratio calculation from last quarter
- **Revenue Growth**: Quarter-over-quarter revenue growth (Q-1 vs. Q-2)
- **NetIncomeTTM**: Trailing twelve months net income
- **DebtRatio**: Debt-to-equity ratio from last year

#### Industry Aggregation
- **Average PE Ratio**: Mean PE ratio across all tickers in each industry
- **Average Revenue Growth**: Mean revenue growth across all tickers in each industry
- **Sum of Revenue**: Sum revenue across all tickers in each industry

### 3. Data Storage
- Design appropriate database schema
- Save individual ticker statistics
- Save aggregated industry data

## Database Setup

### Database Files
- `fiindo_challenge.db`: SQLite database file
- `models.py`: SQLAlchemy model definitions (can be divided into separate files if needed)
- `alembic/`: Database migration management

## Getting Started

1. **Fork this repository** to your GitHub account
2. **Implement the solution** following the process steps outlined above 

## Deliverables

Your completed solution should include:
- Working application that fetches data from the API
- SQLite database with calculated results
- Clean, documented code
- README with setup and run instructions

## Bonus Points

### Dockerization
- Containerize your solution using Docker
- Create a `Dockerfile` and `docker-compose.yml`

### Unit Testing
- Write comprehensive unit tests for ETL part of your solution


Good luck with your implementation!
