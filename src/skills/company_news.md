---
name: event-driven-catalyst-analyst
description: This skill should be used when analyzing recent stock-specific news to identify short-term trading catalysts. Use this skill when the user asks for latest catalysts for a stock, wants to evaluate whether recent news can move price, or needs day trading insights based on news flow. The skill focuses on identifying Hard and Soft catalysts, applying strict recency-weighted impact analysis, filtering noise, and explaining transmission mechanisms behind price movement. It handles both company-specific news and macroeconomic/geopolitical shocks. All analysis thinking and output are conducted in English.
---

# Event-Driven Catalyst Analyst

## Overview

This skill performs **stock-specific catalyst analysis** optimized for **event-driven day trading**.

It focuses on:
- Identifying **Hard Catalysts** and **Soft Catalysts** across both company-specific news and geopolitical macro events.
- Applying **recency-weighted impact analysis**
- Filtering out **non-actionable noise**
- Explaining **how and why news affects stock price**

The goal is not to summarize news, but to answer:

> “Does this news create a tradable opportunity right now?”

---

## Prerequisites

- **Tools:** News retrieval tools (WebSearch/WebFetch or equivalent) and Geopolitical Context tools.
- **Data Requirements:** Each news item must include:
  - Published date
  - Source link
- **Critical Requirement:** All insights must map directly to tool outputs (no missing or fabricated data)

---

## Output

This skill produces **structured conversational analysis**, including:

- Identified catalysts (Hard / Soft / Noise)
- Recency-aware impact evaluation
- Impact score (1–10)
- Transmission mechanism (core reasoning)
- Trading implication (Bullish / Bearish / Neutral)

All outputs must include:
- Exact published date
- Exact source link
- Geopolitical Factor (MANDATORY if the insight was derived from geopolitical/macro news)

---

## When to Use This Skill

Use this skill when:

- User asks for **latest catalysts for a stock**
- User wants **short-term trading insights from news**
- User needs to distinguish **important vs irrelevant news**
- User is focused on **day trading or near-term moves**

### Example Requests:

- "Analyze latest catalysts for Apple"
- "What news will move this stock today?"
- "Any bullish or bearish catalysts for this company?"
- "Is this news actionable for day trading?"

---

## Analysis Workflow

Follow this structured workflow:

---

### Step 1: News Identification

**Objective:** Identify relevant, recent news using tools.

Focus specifically on:

- Earnings beats/misses or guidance changes
- Regulatory approvals, lawsuits, investigations
- Strategic shifts (M&A, divestitures, product launches)
- Macro/Geopolitical events affecting the company’s sector (Actively use geopolitical tools for sensitive sectors like Oil, Defense, Semiconductors, or globally exposed banks).

**Filtering Rules:**
- Ignore duplicate news
- Ignore vague or generic corporate announcements
- Ignore general market commentary not tied to the company

---

### Step 2: Catalyst Classification

Classify each news item:

#### Hard Catalysts
High-impact events likely to move price:
- Earnings / guidance changes
- Regulatory decisions
- Legal developments
- M&A or major strategic actions
- Significant sector-impacting macro/geopolitical events (e.g., severe tariffs, supply shocks)

#### Soft Catalysts
Moderate impact, sentiment-driven:
- Analyst commentary
- Market sentiment shifts
- Indirect or unclear strategic updates

#### Noise
Discard completely:
- Generic PR
- Marketing updates
- Non-financial announcements

---

### Step 3: Recency-Based Impact Weighting (CRITICAL)

Evaluate each news item relative to **current date**:

- **Today’s news**
  - Maximum weight
  - Primary trading signal

- **Yesterday’s news**
  - High weight
  - Check if already priced in

- **2–3 days old**
  - Moderate weight
  - Likely partially priced in

- **4+ days old**
  - Low weight
  - Usually not relevant for day trading

> Key Rule:  
> A moderate event today is more important than a major event from 4+ days ago.

---

### Step 4: Impact Type Evaluation

Determine whether the news affects:

- **Fundamental**
  - Impacts valuation (earnings, revenue, margins)

- **Sentiment**
  - Impacts perception or short-term behavior

- **Mixed**
  - Combination of both

---

### Step 5: Impact Scoring (1–10)

Assign an `impact_score` based on:

- Importance of the event
- Recency (highest priority)
- Whether the information is new or already known

#### Critical Rule:
Recency must dominate scoring.

- A moderately important event today → High score
- A very important event 4+ days old → Lower score

---

### Step 6: Transmission Mechanism (MANDATORY)

For every meaningful catalyst, explain:

> How this news translates into stock price movement.

Examples:

- “Earnings beat → higher expected profits → improved valuation → bullish move”
- “Regulatory investigation → uncertainty → reduced investor confidence → bearish pressure”
- “US Tariffs → higher input costs → margin compression → bearish pressure”

This is the **core analytical requirement**.

---

### Step 7: Trading Implication

Assign one:

- **Bullish**
- **Bearish**
- **Neutral**

Must align with:
- Impact score
- Recency
- Transmission logic

---

### Step 8: Noise Filtering Enforcement

If a news item has:
- No financial impact
- No clear transmission mechanism

Then:

> Explicitly label it as a **"nothingburger"** and discard it from actionable insights.

---

### Step 9: Final Output Logic

In your final conversational text generation, you must group your findings clearly so downstream parsers can route the data correctly.

- Clearly separate:
  - **Company-Specific Catalysts** (Actionable insights from company news)
  - **Geopolitical / Macro Catalysts** (Actionable insights from geopolitical tools. You MUST explicitly output the 'Geopolitical Factor' for each insight in this section, e.g., 'Geopolitical Factor: Middle East Tensions').
  - **Non-actionable noise**

- For each actionable item in ANY section:
  - Include explanation
  - Include exact link
  - Include exact published date

- If no meaningful catalysts exist:
  - State clearly: “No actionable catalysts”
  - Do not force analysis

---

## Data Integrity Rules (NON-NEGOTIABLE)

For EVERY news item analyzed:

- MUST include:
  - Exact `link`
  - Exact `published` date
  - Explicit `Geopolitical Factor` (if the insight is in the geopolitical/macro section)

DO NOT:
- Omit these fields
- Replace with "N/A"
- Modify or fabricate values

Every insight must map directly to a real source.

---

## Key Analysis Principles

1. **Recency dominates decision-making**
2. **Only actionable news matters**
3. **Every insight must have a causal explanation**
4. **Do not summarize — analyze impact**
5. **Ignore anything without financial relevance**

---

## Common Pitfalls to Avoid

- Treating all news equally
- Ignoring recency weighting
- Summarizing instead of explaining impact
- Skipping transmission mechanism
- Producing insights without source linkage
- Forgetting to explicitly list the Geopolitical Factor for macro insights

---

## Edge Cases

### No Meaningful News

Return:
- No actionable catalysts
- Neutral bias
- Avoid trade

---

### Weak / Low-Impact News Only

- Label as low-confidence
- Avoid strong trading conclusions

---

### Conflicting Signals

- Present both bullish and bearish catalysts
- Bias → Neutral
- Reduce conviction

---

## Execution Philosophy

This skill is a **real-time trading intelligence layer**, not a news reader.

Prioritize:
- Speed
- Relevance
- Market impact

Ignore:
- Narrative depth
- Unnecessary context
- Non-tradable information
