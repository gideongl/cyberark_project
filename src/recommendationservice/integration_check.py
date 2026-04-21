#!/usr/bin/env python
#
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import sys

import grpc

import demo_pb2
import demo_pb2_grpc


DEFAULT_CATALOG_ADDR = "127.0.0.1:3550"
DEFAULT_RECOMMENDATION_ADDR = "127.0.0.1:8080"
DEFAULT_EXCLUDED_PRODUCT_ID = "OLJCESPC7Z"
DEFAULT_TIMEOUT_SECONDS = 10.0


def _wait_for_channel(channel, target, timeout_seconds):
    try:
        grpc.channel_ready_future(channel).result(timeout=timeout_seconds)
    except grpc.FutureTimeoutError as exc:
        raise RuntimeError(
            f"Timed out waiting for gRPC channel to become ready: {target}"
        ) from exc


def _fetch_catalog(catalog_addr, timeout_seconds):
    channel = grpc.insecure_channel(catalog_addr)
    _wait_for_channel(channel, catalog_addr, timeout_seconds)
    stub = demo_pb2_grpc.ProductCatalogServiceStub(channel)
    response = stub.ListProducts(demo_pb2.Empty(), timeout=timeout_seconds)
    return response.products


def _fetch_recommendations(recommendation_addr, excluded_product_id, timeout_seconds):
    channel = grpc.insecure_channel(recommendation_addr)
    _wait_for_channel(channel, recommendation_addr, timeout_seconds)
    stub = demo_pb2_grpc.RecommendationServiceStub(channel)
    response = stub.ListRecommendations(
        demo_pb2.ListRecommendationsRequest(
            user_id="integration-check",
            product_ids=[excluded_product_id],
        ),
        timeout=timeout_seconds,
    )
    return response.product_ids


def _assert_valid_recommendations(recommendation_ids, excluded_product_id, catalog_ids):
    if not recommendation_ids:
        raise AssertionError("Recommendation response was empty")

    if len(recommendation_ids) > 5:
        raise AssertionError(
            f"Recommendation response exceeded limit: {len(recommendation_ids)} > 5"
        )

    if len(set(recommendation_ids)) != len(recommendation_ids):
        raise AssertionError(
            f"Recommendation response contained duplicate IDs: {recommendation_ids}"
        )

    if excluded_product_id in recommendation_ids:
        raise AssertionError(
            "Recommendation response included the excluded product ID: "
            f"{excluded_product_id}"
        )

    unknown_ids = sorted(set(recommendation_ids) - catalog_ids)
    if unknown_ids:
        raise AssertionError(
            f"Recommendation response included unknown product IDs: {unknown_ids}"
        )


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Verify live cooperation between recommendationservice and "
            "productcatalogservice."
        )
    )
    parser.add_argument(
        "--recommendation-addr",
        default=DEFAULT_RECOMMENDATION_ADDR,
        help=f"gRPC address for recommendationservice (default: {DEFAULT_RECOMMENDATION_ADDR})",
    )
    parser.add_argument(
        "--catalog-addr",
        default=DEFAULT_CATALOG_ADDR,
        help=f"gRPC address for productcatalogservice (default: {DEFAULT_CATALOG_ADDR})",
    )
    parser.add_argument(
        "--excluded-product-id",
        default=DEFAULT_EXCLUDED_PRODUCT_ID,
        help=(
            "Product ID to exclude from the recommendation request "
            f"(default: {DEFAULT_EXCLUDED_PRODUCT_ID})"
        ),
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"gRPC timeout in seconds (default: {DEFAULT_TIMEOUT_SECONDS})",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    catalog = _fetch_catalog(args.catalog_addr, args.timeout_seconds)
    catalog_ids = {product.id for product in catalog}
    if args.excluded_product_id not in catalog_ids:
        raise AssertionError(
            "Excluded product ID was not present in the live catalog: "
            f"{args.excluded_product_id}"
        )

    recommendation_ids = list(
        _fetch_recommendations(
            args.recommendation_addr,
            args.excluded_product_id,
            args.timeout_seconds,
        )
    )
    _assert_valid_recommendations(
        recommendation_ids,
        args.excluded_product_id,
        catalog_ids,
    )

    print(
        "Integration check passed: "
        f"{len(recommendation_ids)} recommendation(s) returned, "
        f"excluded={args.excluded_product_id}, "
        f"catalog_size={len(catalog_ids)}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, RuntimeError, grpc.RpcError) as exc:
        print(f"Integration check failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
