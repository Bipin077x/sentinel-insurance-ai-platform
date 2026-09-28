# Generic Legacy Insurance Integration Contract

## ⚠️ DISCLAIMER
This is a realistic **COMPOSITE** pattern drawn from public knowledge of how legacy enterprise insurance systems typically behave. It does **NOT** represent, simulate, or claim compatibility with any specific vendor's actual API contract (e.g., Guidewire, Duck Creek, etc.). No proprietary vendor documentation was used to build this contract.

## Overview
Many legacy insurance core systems expose APIs that predate modern REST conventions. They frequently rely on SOAP-style XML payloads, explicit state polling (eventual consistency), and strict idempotency handling for writes. This contract simulates these common legacy patterns to validate the structural robustness of the POC's adapter layer.

## Contract Requirements

### 1. Payload Format
- All requests and responses must use SOAP-style XML envelopes.
- E.g., `<Envelope><Header>...</Header><Body>...</Body></Envelope>`

### 2. Required Headers
- **`CorrelationId`**: Required on every request. Must be a UUID used to trace a single logical transaction across systems. It will be echoed back in the response.
- **`IdempotencyKey`**: Required on all write operations (e.g., policy update). If a write operation is retried with the same `IdempotencyKey`, the server must return the previously cached outcome without double-applying the state change.

### 3. Asynchronous Writes (Eventual Consistency)
- A write request (e.g., updating a policy) does not immediately return a finalized success state.
- The server will return `202 Accepted` with a `JobId`.
- The client must poll a status endpoint (`/status/<JobId>`) with exponential backoff.
- The status can be `PENDING`, `CONFIRMED`, or `FAILED`.

### 4. Partial Failure Scenarios
- Some operations touch multiple downstream systems (e.g., Policy system and Billing system).
- The server may simulate a partial failure where the Policy system updates successfully, but the Billing system throws an error.
- The status endpoint will return a `PARTIAL_SUCCESS` state, explicitly declaring which subsystem failed. The adapter must handle this explicitly without retrying the successful half.
