# Security Policy

## What this repository contains

- Architecture and reference implementation of an on-prem AI agent
- Demo aliases and dry-run Tracker responses
- `.env.example` with **empty** credentials

## What must never be committed

- `.env`, OAuth tokens, bot tokens, webhook secrets
- Production employee directories / real org aliases
- Internal hostnames, VPN-only URLs, customer data
- Model weight dumps if license/policy forbids redistribution

## Reporting

If you find a leaked secret in history, rotate credentials immediately and purge the commit from the remote.
