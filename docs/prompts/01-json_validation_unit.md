# JSON Validation Unit Implementation - Cline Oneshot Prompt

## Task Overview
You are implementing the `json_validation_unit` (Phase 0.0) from the Logist master development plan. This unit establishes the foundational JSON schema validation infrastructure for LLM communication. Consult this prompts file throughout implementation to ensure every requirement is met - reference it explicitly after each major step to verify compliance.

## Critical Requirements - Bidirectional JSON Schema Validation
Logist must validate JSON in both directions:

### Logist → LLM (Request Validation)
All prompts sent TO the LLM must validate against the schema, ensuring only well-formed requests are accepted by LLMs.

### LLM → Logist (Response Validation)
All responses FROM the LLM must validate against the schema. If invalid, escalate to INTERVENTION_REQUIRED with descriptive error containing all known information about the malformed response.

### Schema File Location
Use `logist/schemas/llm-chat-schema.json` - the JSON Schema Draft 07 specification that defines valid structure for requests and responses.

## Deliverables - Exact Files to Create

### 1. Library Addition
**File:** `logist/requirements.txt`  
**Action:** Add jsonschema library (use version ^4.17.0 or latest stable)  
**Verification:** Run `pip install -r requirements.txt` successfully

### 2. Validation Helper Module
**File:** `logist/logist/validation.py` (new module)  
**Contents:**
- Import jsonschema and json libraries
- Function `validate_llm_request(data)` - validates request objects against schema
- Function `validate_llm_response(data)` - validates response objects against schema
- Error handling that returns descriptive messages for validation failures

### 3. System Instructions Template
**File:** `logist/docs/examples/system-instructions-template.md` (new file)  
**Contents:**
Comprehensive template that commands LLMs to:
- Produce ONLY valid JSON responses
- Use exact enum values (COMPLETED/STUCK/RETRY)
- Include all required fields per schema
- Handle quote escaping properly for JSON
- Example template text that LLMs must follow

### 4. Example JSON Files
Create directory structure: `logist/docs/examples/llm-exchange/`

**valid-llm-request.json:**
```json
{
  "request": {
    "action": "step",
    "job_id": "demo-job",
    "options": {"resume": false, "model": "gpt-4"}
  }
}
```

**invalid-llm-request.json:**
```json
{
  "request": {"job_id": "demo-job"}
}
```
(Missing required "action" field to make invalid)

**valid-llm-response.json:**
```json
{
  "response": {
    "action": "COMPLETED",
    "evidence_files": ["task.txt", "output.log"],
    "summary_for_supervisor": "Task completed successfully - analysis shows 100% accuracy.",
    "job_manifest_url": "https://example.com/manifest.json"
  }
}
```

**invalid-llm-response.json:**
```json
{
  "response": {
    "action": "FINISHED",
    "evidence_files": []
  }
}
```
(Action enum not in schema, missing summary to make invalid)

### 5. Demo Script
**File:** `logist/scripts/demo-schema.py`  
**Contents:**
- Import validation functions from logist.validation
- Load schema from logist/schemas/llm-chat-schema.json
- Test all four example files
- Print "VALID: [filename]" or "INVALID: [filename] - [error description]"
- Successfully validate valid files, reject invalid files

**Example Output:**
```
Loading schema from logist/schemas/llm-chat-schema.json...

Testing valid-llm-request.json...
VALID: valid-llm-request.json

Testing invalid-llm-request.json...
INVALID: invalid-llm-request.json - 'action' is a required property

[...continue for all files]
```

### 6. Unit Tests
**File:** `logist/tests/test_validation.py` (new file)  
**Contents:**
- Test successful validation of valid examples
- Test error messages for invalid examples
- Test system instructions template loads correctly
- Validation must pass/fail exactly as demonstrated in demo script

## Implementation Sequence

1. **Start:** Read `logist/schemas/llm-chat-schema.json` to understand validation rules
2. **Library:** Add jsonschema to requirements.txt and install
3. **Validation Module:** Create `logist/logist/validation.py` with wrapper functions
4. **System Instructions:** Create template in docs explaining JSON requirements
5. **Example Files:** Create all four JSON examples that demonstrate valid/invalid cases
6. **Demo Script:** Create demonstrator that shows validation working on examples
7. **Unit Tests:** Add comprehensive test coverage
8. **Verify:** Run demo and tests, ensuring exact match with expected outputs

## Verification Standards
- Demo script output must match the example shown above exactly
- All unit tests pass
- System instructions template clearly explains JSON requirements
- Error messages are descriptive and actionable for INTERVENTION_REQUIRED escalation

## Dependencies Check
- After each step, consult this prompts file to ensure all requirements are met
- No external LLM calls needed - this is pure validation infrastructure
- Python standard library + jsonschema dependency only

Implement systematically, consulting this specification file at each milestone to maintain 100% requirements coverage.