---
kb_id: sector_financials_lending
layer: sector
entity: Financials - Lending
schema_version: 1.0
status: active
last_updated: 2026-09-27
updated_by: sector_agent
---

# Financials — Lending Sector Structure

## Scope

This sector covers regulated lending businesses whose economics are primarily driven by credit creation, funding, spreads, asset quality, capital and operating leverage.

Primary downstream industries:
- Banks
- NBFC / Lending

Insurance, asset management, exchanges and other fee-led financials should be modelled separately unless explicitly included later.

## Sector economic engine

At sector level, earnings are broadly a function of:

`Balance-sheet growth × net spread + fee income - operating cost - credit cost - capital drag`

The exact translation differs materially by industry and company. Banks and NBFCs therefore inherit this sector state but use different funding, liquidity, capital and asset-quality models downstream.

## Core sector drivers

1. Credit demand and nominal growth
2. Deposit / liability availability
3. Cost of funds and policy transmission
4. System liquidity
5. Competitive intensity for deposits and loans
6. Asset-quality cycle
7. Capital adequacy / regulatory requirements
8. Yield curve and treasury conditions
9. Household and corporate leverage
10. Regulatory intervention and underwriting standards

## Structural questions

- Is credit growth above or below nominal economic growth?
- Are deposits/liabilities keeping pace with loan growth?
- Is competition forcing faster repricing of assets or liabilities?
- Is liquidity abundant, neutral or tight?
- Are credit costs below, near or above through-cycle levels?
- Is sector capital abundant enough to support growth?
- Are regulators tightening underwriting/capital/liquidity rules?
- Is the sector early-, mid- or late-cycle?

## Downstream inheritance

The sector layer should pass only broad state and transmission variables downstream.

Banks must additionally model:
- CASA and deposit franchise
- NIM / deposit repricing
- liquidity coverage
- treasury book
- regulated capital
- fee pools

NBFC / Lending must additionally model:
- wholesale / securitisation / bank funding mix
- ALM and refinancing
- spreads by product
- collection efficiency
- leverage
- regulator-defined scale layer / capital requirements

## Non-negotiable separation

Do not use a single 'financials score' to substitute for industry analysis.

A macro condition can benefit banks and hurt an NBFC, or vice versa, depending on funding mix, asset repricing and liquidity sensitivity.
