# EDGAR Public Dissemination Service (PDS) Specification Summary

> Summary of the SEC EDGAR Public Dissemination Service (PDS) specification for real-time filing feeds.

## Overview
The EDGAR Public Dissemination Service (PDS) is a system provided by the U.S. Securities and Exchange Commission (SEC) to disseminate public filings in real-time. The PDS Specification (as detailed in `pds_dissemination_spec.pdf`) outlines the technical requirements, protocols, and formats for accessing disseminated EDGAR filings. This service is crucial for applications needing timely access to submissions like 10-Ks, 10-Qs, and 8-Ks.

Key purposes:
- Enable third-party vendors and users to receive real-time notifications and data feeds of EDGAR filings.
- Support structured data formats (e.g., XBRL) for automated parsing.
- Ensure compliance with SEC dissemination rules, including authentication and rate limits.

## Key Specifications from the PDF

### 1. **System Architecture**
   - **PDS Components**: Includes dissemination servers, subscription models, and data feeds.
   - **Access Methods**: Real-time push (e.g., via WebSocket or FTP) and pull mechanisms (e.g., API queries).
   - **Data Formats**: Filings are disseminated in ZIP archives containing HTML, XML (XBRL), and TXT files.

### 2. **Authentication and Security**
   - Requires user authentication via API keys or certificates.
   - Secure connections (HTTPS/TLS) mandatory.
   - Rate limiting: Similar to EDGAR APIs (e.g., 10 requests/second per IP).

### 3. **Data Feed Details**
   - **Filing Types**: Covers all EDGAR forms (e.g., submissions, amendments).
   - **Metadata**: Includes CIK, accession number, filing date, form type.
   - **XBRL Support**: Disseminated filings include inline XBRL for financial data extraction.
   - **Error Handling**: Specs for retry logic, error codes (e.g., 404 for missing filings).

### 4. **Integration Guidelines**
   - Subscribers must handle large volumes of data with efficient parsing.
   - Compliance with SEC's fair access rules (no redistribution without permission).
   - Testing: Use EDGAR's test environment for development.

For full details, refer to the original `pds_dissemination_spec.pdf` in this directory.

## Incorporation into This Repository

This repo focuses on parsing EDGAR data via the public `data.sec.gov` APIs. To incorporate PDS specs for real-time capabilities, build on the current Django architecture (the pre-Django `src/*.py` scripts have been removed):

### 1. **SEC client (`src/sec_edgar/client.py`)**
   - Add PDS-specific methods alongside the existing submissions/companyfacts calls: e.g. subscribe to real-time feeds, respecting rate limits with the existing `tenacity` retry decorator.

### 2. **Ingest/sync services (`src/sec_edgar/services/`)**
   - Extend the submissions/facts sync services to process PDS-disseminated XBRL, persisting into the `warehouse` models (`Filing`, `Fact`).
   - Trigger downstream processing (statements, derived metrics) on new-filing arrival — ideally as Celery tasks (see the async-processing phase of the roadmap).

### 3. **Management commands (`src/sec_edgar/management/commands/`)**
   - Add a command (e.g. `stream_pds`) to enable PDS streaming, mirroring the existing `sync_submissions` / `sync_company_facts` commands.

### 4. **Compliance Notes**
   - Update `README.md` and `src/.env.example` with PDS-specific setup (e.g. obtaining SEC credentials).
   - Add structured logging for PDS interactions to monitor compliance.
   - Add any new dependencies to `requirements.in` and recompile the pinned `requirements.txt` with `pip-compile`.

By integrating PDS, this app could evolve from batch parsing to a real-time EDGAR monitoring tool. Future work: implement full PDS subscription logic.
