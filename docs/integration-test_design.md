# Integration Test Design — microservices-demo

## Objective

This document captures:

- The approach taken to identify a suitable integration test seam
- The reasoning behind the final design decision
- Trade-offs considered during implementation
- The resulting test strategy and execution model

The goal was to deliver a **single, high-signal integration test** demonstrating service cooperation, with minimal implementation overhead and a clear CI execution path.

---

## Problem Context

The task required:

- Adding an **integration test between two services**
- Verifying **real cooperation between running services**
- Providing **automation compatible with CI execution**
- Optimising for **approach clarity**, not coverage completeness

Constraints:

- Timeboxed (~2 days)
- Existing system is a **multi-service Kubernetes-based architecture**
- Repo already includes:
  - Unit tests (Go, C#)
  - CI workflows
  - Deployment + smoke validation

---

## Strategy

We followed a structured, staged approach.

### 1. Environment Bring-up

Before designing tests, we ensured:

- Docker, Kubernetes, kubectl, and Skaffold were operational
- The full system could be deployed via:

```
skaffold run
```

- All services were running and reachable

Rationale:

Integration testing depends entirely on system runtime stability. This step removed infrastructure uncertainty early.

---

### 2. Candidate Seam Identification

We analysed the service architecture to identify plausible seams:

| Caller                | Callee                 | Type         |
|----------------------|------------------------|--------------|
| frontend             | productcatalogservice  | HTTP → gRPC  |
| frontend             | currencyservice        | HTTP → gRPC  |
| checkoutservice      | paymentservice         | gRPC         |
| checkoutservice      | shippingservice        | gRPC         |
| recommendationservice| productcatalogservice  | gRPC         |

---

### 3. Evaluation Criteria

Each seam was evaluated against:

- Implementation simplicity
- Stability / flake risk
- Data independence (low brittleness)
- Observability (ease of assertion)
- CI friendliness
- Interview signal

---

### 4. Key Observations

#### Frontend-based seams

Pros:
- Easy to drive via HTTP
- Human-readable outputs

Cons:
- Coupled to UI rendering
- Often pull in multiple downstream services
- Require complex environment setup

#### Checkoutservice seams

Pros:
- Architecturally meaningful

Cons:
- High orchestration complexity
- Depend on multiple services
- Increased flake and setup cost

#### Recommendationservice seam

Pros:
- Clean one-to-one dependency on productcatalogservice
- True service-to-service interaction
- Minimal dependency surface

Cons:
- Output is non-deterministic (random sampling)

---

### 5. Final Seam Selection

#### Selected Seam

recommendationservice → productcatalogservice

Reasoning:

This seam provides the best balance of:

- Minimal runtime dependencies
- Clear service boundary
- Strong demonstration of integration testing principles
- Low setup and execution complexity

#### Fallback Seam

frontend → productcatalogservice (/product-meta/{id})

Reasoning:

- Deterministic JSON response
- Simple assertion surface

Rejected as primary due to:

- Frontend startup complexity
- Not a pure two-service interaction

---

## Test Design

### Test Type

Service Integration Test (gRPC boundary)

### Assertion Strategy

Due to nondeterminism in recommendation output:

Use invariant-based assertions, not exact value matching.

### Test Validates

Given a valid product ID, assert:

- Recommendations are returned
- Returned IDs are:
  - Unique
  - Not equal to the input product
  - Present in the product catalog
  - Count is between 1 and 5

### Why This Is Correct

This verifies:

- recommendationservice successfully calls productcatalogservice
- productcatalogservice returns valid data
- integration contract is functioning

Without coupling to:

- exact data
- ordering
- random selection behaviour

---

## Implementation Approach

### Execution Model

Run only the required services:

1. productcatalogservice
2. recommendationservice

Then run a Python integration script.

### Harness Choice

Plain Python script

Reasons:

- Minimal overhead
- Easy to read and explain
- No need for full test framework
- Reuses existing gRPC stubs

### File Location

src/recommendationservice/integration_check.py

### Local Execution

Start services:

```powershell
# productcatalogservice
go run .

# recommendationservice
$env:PRODUCT_CATALOG_SERVICE_ADDR='127.0.0.1:3550'
python recommendation_server.py
```

Run test:

```powershell
python integration_check.py
```

---

## CI Strategy

### Existing CI Capabilities

The repo already provides:

- Deployment via Skaffold
- Pod readiness checks
- Post-deploy smoke validation

### Integration Strategy

Rather than introducing a new pipeline:

Extend existing CI with a post-deploy validation step.

### Execution Method

Run test inside the cluster:

```
kubectl exec deploy/recommendationservice -- \
  python /recommendationservice/integration_check.py
```

### Why This Approach

- Reuses existing deployment pipeline
- Avoids rebuilding infrastructure
- Keeps test colocated with service runtime
- Minimises CI complexity

---

## Trade-offs

| Decision                  | Trade-off                                      |
|--------------------------|-----------------------------------------------|
| Use Python script        | Not aligned with existing Go/C# test frameworks|
| Invariant assertions     | Less strict than snapshot tests               |
| Direct service startup   | Not identical to full production deployment   |
| kubectl exec in CI       | Slightly less pure than standalone CI runner  |

---

## Summary

We deliberately chose:

- A true service-to-service seam
- A minimal, high-signal test
- An invariant-based assertion model
- A low-friction execution path
- A CI integration that reuses existing workflows

This results in:

- Demonstration focused displaying testing judgment
- Clearly explanable
- Low implementation risk
- High signal-to-effort ratio

---
