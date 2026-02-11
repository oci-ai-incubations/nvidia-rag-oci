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

"""
Helper functions for Nemotron Parse pipeline.
"""

import logging

logger = logging.getLogger(__name__)


def pull_text(
    element,
    enable_text: bool,
    enable_charts: bool,
    enable_tables: bool,
    enable_images: bool,
    enable_infographics: bool,
    enable_audio: bool,
):
    text = None
    if element["document_type"] == "text" and enable_text:
        text = element["metadata"]["content"]
    elif element["document_type"] == "structured":
        text = element["metadata"]["table_metadata"]["table_content"]
        if element["metadata"]["content_metadata"]["subtype"] == "chart" and not enable_charts:
            text = None
        elif element["metadata"]["content_metadata"]["subtype"] == "table" and not enable_tables:
            text = None
        elif element["metadata"]["content_metadata"]["subtype"] == "infographic" and not enable_infographics:
            text = None
    elif element["document_type"] == "image" and enable_images:
        if element["metadata"]["content_metadata"]["subtype"] == "page_image":
            text = element["metadata"]["image_metadata"]["text"]
        else:
            text = element["metadata"]["image_metadata"]["caption"]
    elif element["document_type"] == "audio" and enable_audio:
        text = element["metadata"]["audio_metadata"]["audio_transcript"]
    return text