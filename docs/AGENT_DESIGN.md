# Agent workflow

```mermaid
flowchart TD
    A[Chat request] --> B[Safety Gate]
    B -->|Emergency| C[Fixed 115 response]
    B -->|Medication change| D[Refusal and clinician review]
    B -->|Normal| E[Intent router]
    E --> F[At most five tools]
    F --> G[Optional evidence-only Claude composer or deterministic fallback]
    G --> H[Backend citation validator]
    H --> I[Vietnamese response + tool trace]
```

Five tools are implemented: `predict_risk`, `classify_lab`, `search_kb`, `get_history`, and `calculate_bmi`. The router supports combinations for lab-plus-KB and risk-plus-history requests. Fusion preserves `ml`, `clinical_rules`, `evidence`, `safety_level`, and `profile_type` as separate fields; model risk is never added to retrieval relevance. The optional Claude composer can explain approved KB excerpts for KB-only or combined requests. When enabled, it receives the question after common measurements and identifiers are masked, plus the approved excerpt after medication and dose sentences are removed. It does not receive profile data, tool outputs, lab findings, BMI, risk scores, SHAP values, or history. It is disabled by default; citations and answer checks must pass or the deterministic answer is returned. Safety and medication refusal routes bypass it. Unknown or unsupported requests use the approved-only KB path and state when evidence is insufficient.

`session_id` is a request correlation value only; messages and long-term memory are not written to the database. Changing the selected profile resets the browser conversation.
