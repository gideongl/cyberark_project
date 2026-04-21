# recommendationservice integration check

This service includes a narrow integration check for the live gRPC boundary from
`recommendationservice` to `productcatalogservice`.

## What it proves

The script verifies that a running recommendation service can fetch the live
catalog and return recommendation IDs that:

- are unique
- exclude the requested product ID
- exist in the live product catalog
- contain between 1 and 5 results

The assertions are invariant-based. The script does not assume a fixed ordering
or a fixed set of recommendation IDs.

## Local two-service run

Start `productcatalogservice` from its own directory so it can read
`products.json`:

```powershell
Set-Location c:\Users\ggluc\Cyberark_project\cyberark_project\src\productcatalogservice
$env:DISABLE_PROFILER='1'
go run .
```

Start `recommendationservice` with only the catalog address configured:

```powershell
Set-Location c:\Users\ggluc\Cyberark_project\cyberark_project\src\recommendationservice
$env:DISABLE_PROFILER='1'
$env:PORT='18080'
$env:PRODUCT_CATALOG_SERVICE_ADDR='127.0.0.1:3550'
python recommendation_server.py
```

`PORT` is optional, but using an explicit local port helps avoid collisions with
other services already bound to `8080`.

Run the integration check:

```powershell
Set-Location c:\Users\ggluc\Cyberark_project\cyberark_project\src\recommendationservice
python integration_check.py --recommendation-addr 127.0.0.1:18080 --catalog-addr 127.0.0.1:3550
```

## CI-style invocation after deploy

After the existing deploy and readiness steps complete, the same script can run
inside the recommendationservice container:

```bash
kubectl exec deploy/recommendationservice -- \
  python /recommendationservice/integration_check.py \
  --recommendation-addr localhost:8080 \
  --catalog-addr productcatalogservice:3550
```

## Verified in-cluster execution

The deployed execution path below was validated successfully against the
rebuilt and redeployed `recommendationservice` image.

```powershell
kubectl rollout status deployment/recommendationservice
kubectl get pods -l app=recommendationservice
kubectl exec deploy/recommendationservice -- ls /recommendationservice
kubectl exec deploy/recommendationservice -- python /recommendationservice/integration_check.py --recommendation-addr localhost:8080 --catalog-addr productcatalogservice:3550
```

```text
Integration check passed: 5 recommendation(s) returned, excluded=OLJCESPC7Z, catalog_size=9
```

The earlier missing-script failure was caused by a stale deployed image. After
rebuilding and redeploying from the current repository state,
`integration_check.py` was present at `/recommendationservice` and executed as
documented.
