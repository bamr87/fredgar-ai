# Comprehensive API Documentation for SEC EDGAR Database

> The SEC `data.sec.gov` endpoints and response shapes, with the SEC developer FAQ rules (User-Agent, 10 req/s fair access, lag, ticker files).

## Introduction

The U.S. Securities and Exchange Commission (SEC) provides public access to the Electronic Data Gathering, Analysis, and Retrieval (EDGAR) system through a set of RESTful APIs hosted at `data.sec.gov`. These APIs allow developers to retrieve company submission histories and eXtensible Business Reporting Language (XBRL) financial data in JSON format. The APIs are designed for programmatic access to EDGAR filings, enabling applications such as financial analysis tools, research platforms, and data aggregators.

Key features:
- **Timeliness**: JSON on `data.sec.gov` is updated with dissemination; the SEC does not guarantee how quickly filing content appears on `www.sec.gov` after EDGAR acceptance (see [Availability and lag](#availability-and-lag) below).
- **No Authentication Required**: APIs are openly accessible without API keys.
- **JSON Responses**: These endpoints return JSON.
- **Bulk Downloads**: ZIP files for large-scale data access, updated nightly.

This documentation expands on the official SEC resources, providing detailed endpoint descriptions, parameters, response structures, examples, and best practices. It addresses gaps in the official explanations by including code samples, error handling details, and structured schemas derived from actual API responses.

**Base URL**: `https://data.sec.gov`

**Official references** (SEC):

- [Webmaster Frequently Asked Questions — Developers](https://www.sec.gov/about/webmaster-frequently-asked-questions#developers) (section reviewed/updated by the SEC as of August 2024 on that page).
- [EDGAR application programming interfaces](https://www.sec.gov/page/edgar-application-programming-interfaces-old) (SEC’s overview of `data.sec.gov` JSON services).

## SEC Webmaster FAQ: guidance for developers

The following summarizes the **Developers** portion of the SEC’s [Webmaster FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions#developers) so this repo stays aligned with how the agency describes scripted access, limits, and support. If anything disagrees with the live SEC page, treat the SEC site as authoritative.

### User-Agent and “Undeclared Automated Tool”

The SEC expects automated clients to **declare a User-Agent** that identifies who is accessing the site. Requests without a proper declaration can produce an **“Undeclared Automated Tool”** error; the FAQ directs developers to the same programmatic-access guidance below.

Use a descriptive value (for example, organization or product name plus a contact email). The FAQ illustrates request headers including:

- `User-Agent`: e.g. `Sample Company Name AdminContact@example.com` (adapt to your real identity and working address).
- `Accept-Encoding`: `gzip, deflate` (as in the SEC’s sample).

Send requests to the appropriate host (`data.sec.gov` for JSON APIs, `www.sec.gov` for Archives and HTML as applicable).

### Rate limiting and fair access

The SEC states that its **current maximum access rate is 10 requests per second**, monitored to preserve equitable access. Details sit in the **[Internet Security Policy](https://www.sec.gov/privacy.htm#security)** (linked from the FAQ). Treat this limit as applying across your automation footprint (multiple machines or processes under the same project or organization should aggregate under the cap).

### JSON API services (`data.sec.gov`)

Per the FAQ, company submissions and extracted XBRL data are available via **RESTful APIs on `data.sec.gov`** returning **JSON**. The SEC points to its [EDGAR APIs overview](https://www.sec.gov/page/edgar-application-programming-interfaces-old) for that material.

### “Access Denied”

If you receive **Access Denied**, the FAQ asks you to email **[webmaster@sec.gov](mailto:webmaster@sec.gov)** with a screenshot or the error text and **your IP address** so staff can assist.

### Programmatic downloads: support boundaries

The SEC **does not provide technical support** for writing code to download EDGAR filings. **Scripted access is allowed.** The FAQ highlights:

- [Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)
- [Developer Resources](https://www.sec.gov/developer)

### Availability and lag

For documents on **`www.sec.gov`**, the FAQ states that filings are **often** available within **about one to three minutes** of the EDGAR system timestamp, but lag **can increase** under load. The SEC **does not guarantee** timing and **cannot predict** it. There is **no** separate timestamp for “first visible on sec.gov.”

### Near–real-time discovery

To get as close as possible to when new filings appear on `www.sec.gov`, the FAQ recommends **[Latest Filings](https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent)** and the associated **RSS** feeds, while reminding readers to respect the [Internet Security Policy](https://www.sec.gov/privacy.htm#security). For a subscription-style feed, see the SEC’s **[EDGAR Public Dissemination Service](https://www.sec.gov/oit/announcement/public-dissemination-service-system-contact.html)** contact page.

### Email alerts and RSS

The SEC **does not** offer email notifications specifically for EDGAR filings; **dynamic RSS** is available for some searches ([SEC RSS](https://www.sec.gov/about/secrss.shtml)). Non-EDGAR **email updates** are offered separately from the sec.gov home page.

### Ticker, CIK, and company name

The FAQ lists two mapping files (periodically updated; **accuracy and scope are not guaranteed**):

| File | URL | Contents |
|------|-----|----------|
| Tab-delimited ticker ↔ CIK | [ticker.txt](https://www.sec.gov/include/ticker.txt) | Used for Company Search “fast search.” |
| JSON ticker ↔ CIK ↔ name | [company_tickers.json](https://www.sec.gov/files/company_tickers.json) | EDGAR conformed names; used for home-page typeahead. |

## Rate Limits and Best Practices

Operational summary (see [SEC Webmaster FAQ: guidance for developers](#sec-webmaster-faq-guidance-for-developers) above for official wording and links):

- **Cap**: Stay at or below **10 requests per second** total for your use case, per SEC guidance and [Internet Security Policy](https://www.sec.gov/privacy.htm#security).
- **Consequences of exceeding limits**: Access may be restricted or blocked; APIs may return HTTP **429 Too Many Requests**.

**Best practices** (in addition to SEC expectations):

- Set a clear **User-Agent** (and keep contact information current) to avoid “Undeclared Automated Tool” errors and so the SEC can reach you if needed.
- Use **`Accept-Encoding: gzip, deflate`** where your HTTP client supports it (matches SEC’s sample and reduces bandwidth).
- Implement exponential backoff for retries on errors like 429.
- Cache responses locally to minimize repeated requests.
- For large datasets, prefer bulk ZIP downloads over individual API calls.
- Prefer documented JSON and bulk endpoints over scraping HTML when they meet your needs.
- Download only what you need (specific filings or slices rather than unnecessary full histories).

## Authentication

No authentication is required. APIs are public and do not use API keys, tokens, or credentials.

## Error Handling

Responses use standard HTTP status codes. Common errors include:
- **200 OK**: Successful response.
- **400 Bad Request**: Invalid parameters (e.g., malformed CIK).
- **404 Not Found**: Resource not available (e.g., invalid CIK or tag).
- **429 Too Many Requests**: Rate limit exceeded; retry after a delay.
- **500 Internal Server Error**: Rare server-side issues; retry later.

Error responses may include a JSON body with details, e.g., `{"error": "Invalid CIK"}`. Always check the status code and parse the body for messages.

## Endpoints

### 1. Submissions API

**Description**: Retrieves the filing history for a specific entity, including metadata (e.g., company name, tickers, addresses) and a list of recent filings (up to 1,000 or one year, whichever is larger). Additional historical filings are referenced in separate JSON files.

**Endpoint**: `/submissions/CIK{10-digit-cik}.json`

**Method**: GET

**Parameters**:
- `CIK{10-digit-cik}` (required, string): 10-digit Central Index Key, padded with leading zeros (e.g., `0000320193` for Apple Inc.).

**Response Format**: JSON object with company metadata and filings.
- **Root Keys**:
  - `cik` (string): CIK identifier.
  - `entityType` (string): e.g., "operating".
  - `sic` (string): Standard Industrial Classification code.
  - `sicDescription` (string): Description of SIC.
  - `name` (string): Company name.
  - `tickers` (array of strings): Stock tickers.
  - `exchanges` (array of strings): Exchanges.
  - `ein` (string): Employer ID Number.
  - `addresses` (object): Mailing and business addresses (each with `street1`, `city`, `stateOrCountry`, etc.).
  - `phone` (string): Contact phone.
  - `formerNames` (array of objects): Previous names with `name`, `from`, `to`.
  - `filings` (object):
    - `recent` (object): Parallel arrays for recent filings (e.g., `accessionNumber`, `filingDate`, `form`, `size`, `isXBRL`, `primaryDocument`).
    - `files` (array of objects): References to additional JSON files (e.g., `{ "name": "CIK...-submissions-001.json", "filingCount": 1154, "filingFrom": "1994-01-26", "filingTo": "..." }`).
- Derived from example response for CIK0000320193.

**Example Request**:
```
GET https://data.sec.gov/submissions/CIK0000320193.json
User-Agent: YourCompany your@email.com
```

**Example Response Snippet**:
```json
{
  "cik": "0000320193",
  "entityType": "operating",
  "sic": "3571",
  "sicDescription": "Electronic Computers",
  "name": "Apple Inc.",
  "tickers": ["AAPL"],
  "exchanges": ["Nasdaq"],
  "ein": "942404110",
  "addresses": {
    "mailing": {
      "street1": "ONE APPLE PARK WAY",
      "city": "CUPERTINO",
      "stateOrCountry": "CA",
      "zipCode": "95014"
    },
    "business": { ... }
  },
  "phone": "(408) 996-1010",
  "formerNames": [ ... ],
  "filings": {
    "recent": {
      "accessionNumber": ["0000320193-24-000069", ...],
      "filingDate": ["2024-05-03", ...],
      "form": ["10-Q", ...],
      "size": [5304776, ...],
      "isXBRL": [1, ...],
      "primaryDocument": ["aapl-20240330.htm", ...]
    },
    "files": [ ... ]
  }
}
```

**Bulk Download**: Full submissions data in ZIP format.
- URL: `https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip`
- Updated: Nightly at ~3:00 a.m. ET.

**Code Example (Python)**:
```python
import requests

headers = {'User-Agent': 'YourCompany your@email.com'}
response = requests.get('https://data.sec.gov/submissions/CIK0000320193.json', headers=headers)
if response.status_code == 200:
    data = response.json()
    print(data['name'])  # Output: Apple Inc.
else:
    print(f"Error: {response.status_code}")
```

### 2. XBRL Company Concept API

**Description**: Returns all XBRL disclosures for a single company and a specific concept (taxonomy/tag), organized by units (e.g., USD). Facts are from non-custom taxonomies and apply to the entire entity.

**Endpoint**: `/api/xbrl/companyconcept/CIK{10-digit-cik}/{taxonomy}/{tag}.json`

**Method**: GET

**Parameters**:
- `CIK{10-digit-cik}` (required, string): As above.
- `{taxonomy}` (required, string): e.g., `us-gaap`, `ifrs-full`, `dei`, `srt`.
- `{tag}` (required, string): XBRL tag, e.g., `AccountsPayableCurrent`.

**Response Format**: JSON object with concept metadata and facts.
- **Root Keys**:
  - `cik` (integer): Numeric CIK.
  - `taxonomy` (string): Taxonomy used.
  - `tag` (string): Concept tag.
  - `label` (string): Human-readable label.
  - `description` (string): Detailed explanation.
  - `entityName` (string): Company name.
  - `units` (object): e.g., `{ "USD": [array of facts] }`.
    - Each fact: `{ "end": "YYYY-MM-DD", "val": number, "accn": string, "fy": integer, "fp": string, "form": string, "filed": "YYYY-MM-DD", "frame": string (optional) }`.
- Derived from example response.

**Example Request**:
```
GET https://data.sec.gov/api/xbrl/companyconcept/CIK0000320193/us-gaap/AccountsPayableCurrent.json
User-Agent: YourCompany your@email.com
```

**Example Response Snippet**:
```json
{
  "cik": 320193,
  "taxonomy": "us-gaap",
  "tag": "AccountsPayableCurrent",
  "label": "Accounts Payable, Current",
  "description": "Carrying value as of the balance sheet date of liabilities incurred... (truncated)",
  "entityName": "Apple Inc.",
  "units": {
    "USD": [
      {
        "end": "2008-09-27",
        "val": 5520000000,
        "accn": "0001193125-09-214859",
        "fy": 2009,
        "fp": "FY",
        "form": "10-K",
        "filed": "2009-10-27"
      },
      // Additional facts...
    ]
  }
}
```

**Bulk Download**: Not specific; use Company Facts bulk for related data.

**Code Example (Python)**:
```python
import requests

headers = {'User-Agent': 'YourCompany your@email.com'}
url = 'https://data.sec.gov/api/xbrl/companyconcept/CIK0000320193/us-gaap/AccountsPayableCurrent.json'
response = requests.get(url, headers=headers)
if response.status_code == 200:
    data = response.json()
    print(data['label'])  # Output: Accounts Payable, Current
```

### 3. XBRL Company Facts API

**Description**: Aggregates all XBRL facts for a company across concepts, from non-custom taxonomies, for consistent comparison.

**Endpoint**: `/api/xbrl/companyfacts/CIK{10-digit-cik}.json`

**Method**: GET

**Parameters**:
- `CIK{10-digit-cik}` (required, string): As above.

**Response Format**: JSON object with all concepts.
- **Root Keys**:
  - `cik` (string): CIK.
  - `entityName` (string): Company name.
  - `facts` (object): Nested by taxonomy (e.g., `us-gaap`), then concepts (e.g., `Assets`).
    - Each concept: `{ "label": string, "description": string, "units": { "USD": [facts], ... } }`.
    - Each fact: `{ "start": "YYYY-MM-DD" (optional), "end": "YYYY-MM-DD", "val": number, "accn": string, "fy": integer/null, "fp": string/null, "form": string, "filed": "YYYY-MM-DD", "frame": string (optional) }`.
- Derived from example response.

**Example Request**:
```
GET https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json
User-Agent: YourCompany your@email.com
```

**Example Response Snippet**:
```json
{
  "cik": "320193",
  "entityName": "Apple Inc.",
  "facts": {
    "us-gaap": {
      "Assets": {
        "label": "Assets",
        "description": "Sum of the carrying amounts as of the balance sheet date of all assets...",
        "units": {
          "USD": [
            {
              "end": "2014-09-27",
              "val": 23353000000,
              "accn": "0001193125-14-383437",
              "fy": 2014,
              "fp": "FY",
              "form": "10-K",
              "filed": "2014-10-27"
            },
            // Additional facts...
          ]
        }
      },
      // Additional concepts...
    }
  }
}
```

**Bulk Download**: Full company facts ZIP.
- URL: `https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip`
- Updated: Nightly at ~3:00 a.m. ET.

**Code Example (Python)**:
```python
import requests

headers = {'User-Agent': 'YourCompany your@email.com'}
url = 'https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json'
response = requests.get(url, headers=headers)
if response.status_code == 200:
    data = response.json()
    print(data['facts']['us-gaap']['NetIncomeLoss']['label'])  # Output: Net Income (Loss)
```

### 4. XBRL Frames API

**Description**: Aggregates the latest fact for each reporting entity fitting a specified calendrical period (annual, quarterly, or instantaneous). Supports non-custom taxonomies.

**Endpoint**: `/api/xbrl/frames/{taxonomy}/{tag}/{unit}/{period}.json`

**Method**: GET

**Parameters**:
- `{taxonomy}` (required, string): e.g., `us-gaap`.
- `{tag}` (required, string): e.g., `AccountsPayableCurrent`.
- `{unit}` (required, string): e.g., `USD`, `shares`, `pure`.
- `{period}` (required, string): Calendrical period, e.g., `CY2023` (year), `CY2023Q4` (quarter), `CY2023Q4I` (instantaneous).

**Response Format**: JSON object with aggregated facts across entities.
- **Root Keys**:
  - `taxonomy` (string).
  - `tag` (string).
  - `ccp` (string): Period (e.g., `CY2019Q1I`).
  - `uom` (string): Unit.
  - `label` (string).
  - `description` (string).
  - `pts` (integer): Number of points (facts).
  - `data` (array of objects): Each: `{ "accn": string, "cik": integer/string, "entityName": string, "loc": string (e.g., "US-IL"), "end": "YYYY-MM-DD", "val": number }`.
- Derived from example response.

**Example Request**:
```
GET https://data.sec.gov/api/xbrl/frames/us-gaap/AccountsPayableCurrent/USD/CY2019Q1I.json
User-Agent: YourCompany your@email.com
```

**Example Response Snippet**:
```json
{
  "taxonomy": "us-gaap",
  "tag": "AccountsPayableCurrent",
  "ccp": "CY2019Q1I",
  "uom": "USD",
  "label": "Accounts Payable, Current",
  "description": "Carrying value as of the balance sheet date of liabilities incurred... (truncated)",
  "pts": 3390,
  "data": [
    {
      "accn": "0001104659-19-016320",
      "cik": 1750,
      "entityName": "AAR CORP.",
      "loc": "US-IL",
      "end": "2019-02-28",
      "val": 218600000
    },
    // Additional entities...
  ]
}
```

**Bulk Download**: Not specific; use related XBRL ZIPs for bulk access.

**Code Example (Python)**:
```python
import requests

headers = {'User-Agent': 'YourCompany your@email.com'}
url = 'https://data.sec.gov/api/xbrl/frames/us-gaap/AccountsPayableCurrent/USD/CY2019Q1I.json'
response = requests.get(url, headers=headers)
if response.status_code == 200:
    data = response.json()
    print(data['pts'])  # Output: Number of aggregated facts
```

## Additional Resources

- **[Webmaster FAQ — Developers](https://www.sec.gov/about/webmaster-frequently-asked-questions#developers)** — User-Agent, rate limits, APIs, lag, RSS, and mapping files.
- **[Developer Resources](https://www.sec.gov/developer)** — SEC’s developer landing page.
- **[Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)** — Directory layout and access patterns.
- **[Internet Security Policy](https://www.sec.gov/privacy.htm#security)** — Fair access and automated access expectations.
- **Bulk data**: Daily index under `https://www.sec.gov/Archives/edgar/daily-index/`.
- **Libraries**: Community tools (for example `sec-edgar-downloader` in Python or `edgar` in R) can simplify interactions; they are not endorsed by the SEC.

This document combines the SEC’s published guidance (including the Webmaster FAQ Developers section last noted as reviewed August 2024 on that page) with endpoint notes and examples maintained in this repository. Always verify against [sec.gov](https://www.sec.gov/).