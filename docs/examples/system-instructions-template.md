# System Instructions Template for LLM JSON Compliance

## Purpose
This template provides the system instructions that must be included in all LLM prompts to ensure responses conform to the `logist/schemas/llm-chat-schema.json` JSON Schema specification.

## Required System Instructions

### JSON Response Format Requirements
- You MUST respond with valid JSON only
- Do NOT include any text outside of the JSON structure
- Your response must validate against the provided JSON schema
- Use exact enum values: "COMPLETED", "STUCK", or "RETRY" for action field

### Schema Compliance Rules
- **For request objects:** Include exactly one of "request" or "response" wrapper
- **For response objects:**
  - action: Must be exactly "COMPLETED", "STUCK", or "RETRY"
  - evidence_files: Array of strings (can be empty [])
  - summary_for_supervisor: String between 1-1000 characters
  - job_manifest_url: Valid URI string

### Error Prevention
- Do not truncate or abbreviate field values
- Handle quotes and special characters properly for JSON
- If response type is "request", include action, job_id (required fields)
- If response type is "response", include all required fields: action, evidence_files, summary_for_supervisor

### Example Valid Response Structure
```json
{
  "response": {
    "action": "COMPLETED",
    "evidence_files": ["results.txt", "log.txt"],
    "summary_for_supervisor": "Analysis completed with full compliance",
    "job_manifest_url": "https://api.logist.dev/manifest/123"
  }
}
```

### Invalid Response Examples to Avoid
- Missing required fields like summary_for_supervisor
- Wrong enum values like "DONE" instead of "COMPLETED"
- Extra properties not defined in schema
- Malformed JSON with syntax errors

## Template Usage
Include this instruction block at the beginning of all LLM prompts sent by Logist to ensure schema-compliant responses.