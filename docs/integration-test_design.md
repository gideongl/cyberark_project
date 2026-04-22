# Integration Test Design — microservices-demo

## Objective

This document records the selection and implementation approach for a narrowly
scoped service-level integration test within `microservices-demo`.

It captures:

- the integration-boundary selection process
- the design constraints that shaped the choice
- the resulting test structure and assertion model
- the execution model for local and CI-style validation

The design goal is to validate real cooperation between running services while
keeping the dependency surface, setup cost, and flake risk low.

---

## System Context

`microservices-demo` is a distributed system composed of multiple services that
communicate primarily through gRPC, with selected HTTP entry points at the
frontend boundary.

Integration-boundary selection matters in this system because unnecessary
orchestration complexity increases setup cost, broadens the dependency surface,
and raises flake risk. A useful integration test should therefore exercise a
real service boundary without implicitly depending on unrelated parts of the
application.

---

## Problem Context

The design requirements were:

- add a single integration test between two services
- verify real cooperation between running services
- support execution as part of the existing CI deploy-validation flow
- optimise for boundary clarity rather than broad coverage

Existing repository capabilities:

- unit tests in Go and C#
- GitHub Actions workflows
- deployment and post-deployment smoke validation

---

## Approach

The design was developed in a staged manner.

### 1. Environment Bring-up

Before selecting a boundary, the runtime environment was checked to confirm
that:

- Docker, Kubernetes, `kubectl`, and Skaffold were operational
- the full system could be deployed via:

```bash
skaffold run
```

- services became reachable after deployment

This establishes a stable execution baseline before introducing test logic.

---

### 2. Candidate Seam Identification

The following service boundaries were identified as plausible candidates:

| Caller | Callee | Type |
| --- | --- | --- |
| `frontend` | `productcatalogservice` | HTTP → gRPC |
| `frontend` | `currencyservice` | HTTP → gRPC |
| `checkoutservice` | `paymentservice` | gRPC |
| `checkoutservice` | `shippingservice` | gRPC |
| `recommendationservice` | `productcatalogservice` | gRPC |

---

### 3. Evaluation Criteria

Each candidate boundary was evaluated against:

- implementation simplicity
- stability and flake risk
- data independence and low brittleness
- observability and ease of assertion
- CI friendliness
- architectural clarity

---

### 4. Key Observations

#### Frontend-based boundaries

Strengths:

- straightforward to drive through HTTP
- outputs are easy to inspect

Limitations:

- coupled to frontend runtime behaviour
- frequently pull in multiple downstream services
- require a larger startup surface than the boundary itself suggests

#### Checkoutservice boundaries

Strengths:

- operationally meaningful service interactions

Limitations:

- high orchestration complexity
- dependence on multiple additional services
- increased setup cost and flake exposure

#### Recommendationservice boundary

Strengths:

- direct one-to-one dependency on `productcatalogservice`
- true service-to-service interaction
- minimal dependency surface

Limitation:

- output is nondeterministic because recommendations are randomly sampled

---

### 5. Selected Integration Boundary

The selected integration boundary is `recommendationservice → productcatalogservice`.

This boundary provides the best overall balance of:

- minimal runtime dependencies
- a clear service boundary
- a narrow and intelligible assertion surface
- low setup and execution complexity

#### Fallback Design Option

Fallback boundary: `frontend → productcatalogservice` via `/product-meta/{id}`

This remains a viable alternative because it provides:

- a deterministic JSON response
- a simple assertion surface

It was not selected as the primary design because:

- frontend startup requires a broader dependency configuration
- it is less pure as a two-service boundary

---

## Test Design

### Test Type

Service integration test at the gRPC boundary

### Assertion Strategy

Because recommendation output is nondeterministic, the test uses invariant-based
assertions rather than exact-value matching.

### Test Verifies

Given a valid product ID, the test asserts that:

- recommendations are returned
- returned IDs are unique
- returned IDs do not include the excluded product ID
- returned IDs exist in the live product catalog
- returned count is between 1 and 5

### Test Execution Flow

The integration check executes the following steps against the live system:

1. Fetch the full product catalog from `productcatalogservice`
2. Validate that the excluded product ID exists in the live catalog
3. Request recommendations from `recommendationservice` using the excluded product ID
4. Validate the returned recommendation IDs against the catalog using invariant-based checks:
   - non-empty response
   - maximum count constraint
   - uniqueness
   - exclusion of the requested product ID
   - existence of all IDs in the live catalog

This ordering ensures that all assertions are grounded in the current runtime state of the system rather than static assumptions.

### Validation Scope

This validates:

- `recommendationservice` successfully calls `productcatalogservice`
- `productcatalogservice` returns catalog data that is usable by the caller
- the service boundary is functioning with live runtime dependencies

This intentionally avoids coupling to:

- exact recommendation values
- ordering
- random sampling output

---

## Implementation Approach

### Execution Model

Run only the required services:

1. `productcatalogservice`
2. `recommendationservice`

Then execute a Python integration script against their live gRPC endpoints.

### Harness Choice

Plain Python script

Rationale:

- minimal implementation overhead
- easy to audit
- no need for an additional test framework
- direct reuse of existing generated gRPC stubs

### File Location

`src/recommendationservice/integration_check.py`

### Local Execution

Start services:

```powershell
# productcatalogservice
go run .

# recommendationservice
$env:PORT='18080'
$env:PRODUCT_CATALOG_SERVICE_ADDR='127.0.0.1:3550'
python recommendation_server.py
```

Run the test:

```powershell
python integration_check.py --recommendation-addr 127.0.0.1:18080 --catalog-addr 127.0.0.1:3550
```

---

## CI Strategy

### Existing CI Capabilities

The repository already provides:

- deployment via Skaffold
- pod readiness checks
- post-deployment smoke validation

### Integration Strategy

The integration check is wired into the repository's existing GitHub Actions
deploy-validation workflows as a post-deployment validation step. It runs after
deployment readiness is confirmed and before the existing loadgenerator-based
smoke test.

### Execution Method

Run the check inside the deployed cluster:

```bash
kubectl exec deploy/recommendationservice -- \
  python /recommendationservice/integration_check.py \
  --recommendation-addr localhost:8080 \
  --catalog-addr productcatalogservice:3550
```

This keeps execution aligned with the deployed runtime while reusing the
existing deployment and readiness flow.

### Deployment Validation Note

The GitHub Actions wiring was added to the repository's existing post-deploy
validation path in `.github/workflows/ci-pr.yaml` and
`.github/workflows/ci-main.yaml`.

The in-cluster execution path was also manually validated successfully against a
rebuilt and redeployed `recommendationservice` image. After rollout
completion, `integration_check.py` was present in `/recommendationservice` and
the documented `kubectl exec` command completed successfully against the
deployed environment.

Hosted end-to-end execution of the updated GitHub Actions workflows was not run
from the fork used for this work, because the upstream repository's secrets and
self-hosted runners do not transfer to forks.

The previously observed missing-script failure was caused by a stale deployed
image rather than a Dockerfile or packaging design defect.

---

## Trade-offs

| Decision | Trade-off |
| --- | --- |
| Use a Python script | Uses a different runtime from the existing unit-test suites |
| Invariant-based assertions | Trades strictness for robustness under nondeterministic behaviour |
| Direct service startup | Simpler than full-environment execution but not identical to full deployment topology |
| `kubectl exec` post-deploy execution | Relies on the deployed runtime instead of introducing a separate dedicated test runner |

---

## Design Rationale Summary

The selected boundary keeps the dependency surface small, exercises a clear
service-to-service interaction, and supports invariant-based validation without
coupling to unstable recommendation output. The resulting test is locally
executable with a small runtime footprint and fits naturally into the existing
deployment validation workflow as a post-deployment check.
