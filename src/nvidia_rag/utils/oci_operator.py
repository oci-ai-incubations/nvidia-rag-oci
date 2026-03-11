# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""OCI Object Storage operator module — drop-in replacement for MinioOperator.

Provides the same interface as MinioOperator so all callers (ingestor, rag-server,
vlm, summarization) work without modification.
"""

import io
import json
import logging

try:
    import oci

    _OCI_AVAILABLE = True
except ImportError:
    oci = None  # type: ignore[assignment]
    _OCI_AVAILABLE = False

logger = logging.getLogger(__name__)

DEFAULT_BUCKET_NAME = "nvidia-rag-thumbnails"


class OciObjectStorageOperator:
    """OCI Object Storage operator with the same interface as MinioOperator."""

    def __init__(
        self,
        namespace: str,
        bucket_name: str = DEFAULT_BUCKET_NAME,
        region: str = "",
        auth_type: str = "instance_principal",
        config_file: str = "~/.oci/config",
        config_profile: str = "DEFAULT",
    ):
        if not _OCI_AVAILABLE:
            raise ImportError(
                "oci package is not installed. Install with: pip install 'nvidia_rag[oci]'"
            )

        self.namespace = namespace
        self.default_bucket_name = bucket_name

        if auth_type == "instance_principal":
            signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
            oci_config: dict = {"region": region} if region else {}
            self.client = oci.object_storage.ObjectStorageClient(oci_config, signer=signer)
        elif auth_type == "resource_principal":
            signer = oci.auth.signers.get_resource_principals_signer()
            oci_config = {"region": region} if region else {}
            self.client = oci.object_storage.ObjectStorageClient(oci_config, signer=signer)
        else:  # api_key / config_file
            oci_config = oci.config.from_file(
                file_location=config_file, profile_name=config_profile
            )
            self.client = oci.object_storage.ObjectStorageClient(oci_config)

        try:
            self._make_bucket(bucket_name=self.default_bucket_name)
        except Exception as e:
            logger.warning(
                "OCI Object Storage bucket '%s' not accessible in namespace '%s' "
                "— operations will fail at runtime: %s",
                bucket_name,
                namespace,
                e,
            )

    def _make_bucket(self, bucket_name: str):
        """Verify the bucket exists (bucket creation requires a compartment OCID; assume pre-created)."""
        try:
            self.client.get_bucket(self.namespace, bucket_name)
            logger.info("OCI bucket verified: %s", bucket_name)
        except Exception as e:
            logger.warning(
                "OCI bucket '%s' not accessible in namespace '%s': %s",
                bucket_name,
                self.namespace,
                e,
            )

    def put_payload(self, payload: dict, object_name: str):
        """Upload a JSON payload to OCI Object Storage."""
        json_data = json.dumps(payload).encode("utf-8")
        self.client.put_object(
            self.namespace,
            self.default_bucket_name,
            object_name,
            io.BytesIO(json_data),
            content_length=len(json_data),
            content_type="application/json",
        )

    def put_payloads_bulk(self, payloads: list[dict], object_names: list[str]):
        """Upload multiple JSON payloads sequentially (OCI has no native bulk-upload API)."""
        for payload, object_name in zip(payloads, object_names, strict=False):
            self.put_payload(payload, object_name)

    def get_payload(self, object_name: str) -> dict:
        """Download a JSON payload from OCI Object Storage."""
        try:
            response = self.client.get_object(
                self.namespace, self.default_bucket_name, object_name
            )
            return json.loads(response.data.content.decode("utf-8"))
        except Exception as e:
            logger.warning(
                "Error while getting object from OCI Object Storage! Object name: %s",
                object_name,
            )
            logger.debug("Error while getting object from OCI Object Storage: %s", e)
            return {}

    def list_payloads(self, prefix: str = "") -> list[str]:
        """List object names with the given prefix, handling pagination."""
        result = []
        start = None
        while True:
            kwargs: dict = {"prefix": prefix, "limit": 1000}
            if start:
                kwargs["start"] = start
            resp = self.client.list_objects(self.namespace, self.default_bucket_name, **kwargs)
            result.extend([o.name for o in resp.data.objects])
            if resp.data.next_start_after:
                start = resp.data.next_start_after
            else:
                break
        return result

    def delete_payloads(self, object_names: list[str]) -> None:
        """Delete objects from OCI Object Storage."""
        for object_name in object_names:
            self.client.delete_object(self.namespace, self.default_bucket_name, object_name)
